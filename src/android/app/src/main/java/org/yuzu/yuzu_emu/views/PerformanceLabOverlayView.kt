// SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
// SPDX-License-Identifier: GPL-3.0-or-later

package org.yuzu.yuzu_emu.views

import android.content.Context
import android.os.Handler
import android.os.Looper
import android.util.AttributeSet
import android.view.HapticFeedbackConstants
import android.view.View
import com.google.android.material.textview.MaterialTextView
import org.yuzu.yuzu_emu.NativeLibrary
import org.yuzu.yuzu_emu.R
import org.yuzu.yuzu_emu.features.settings.model.BooleanSetting
import org.yuzu.yuzu_emu.utils.PerformanceLabNative
import org.yuzu.yuzu_emu.utils.PipelineWorkerAutoTuner
import java.util.Locale

/**
 * Lightweight Moonwitch Performance Lab readout.
 *
 * The normal Eden overlay samples aggregate performance counters every 800 ms. This view reads the
 * rolling native frame history instead, so P95/P99 are calculated from individual system frames.
 * It also exposes native ADPF, frame-pacing and adaptive frame-skip telemetry so every Moonwitch
 * optimization can be validated directly on-device.
 */
class PerformanceLabOverlayView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
    defStyleAttr: Int = 0
) : MaterialTextView(context, attrs, defStyleAttr) {

    private val updateHandler = Handler(Looper.getMainLooper())
    private var latestSnapshot: PerformanceLabNative.FrameTimeSnapshot? = null

    private val updateRunnable = object : Runnable {
        override fun run() {
            updateSnapshot()
            if (isAttachedToWindow) {
                updateHandler.postDelayed(this, UPDATE_INTERVAL_MS)
            }
        }
    }

    init {
        setOnClickListener {
            val snapshot = latestSnapshot ?: return@setOnClickListener
            if (!BooleanSetting.ENABLE_PIPELINE_WORKER_AUTOTUNER.getBoolean()) {
                return@setOnClickListener
            }
            PipelineWorkerAutoTuner.toggleCapture(context, snapshot)
            updateSnapshot()
        }
        setOnLongClickListener {
            val snapshot = latestSnapshot ?: return@setOnLongClickListener false
            if (!BooleanSetting.ENABLE_PIPELINE_WORKER_AUTOTUNER.getBoolean()) {
                return@setOnLongClickListener false
            }
            performHapticFeedback(HapticFeedbackConstants.LONG_PRESS)
            PipelineWorkerAutoTuner.reset(context, snapshot)
            updateSnapshot()
            true
        }
        isClickable = false
        isLongClickable = false
    }

    override fun onAttachedToWindow() {
        super.onAttachedToWindow()
        updateHandler.removeCallbacks(updateRunnable)
        updateHandler.post(updateRunnable)
    }

    override fun onDetachedFromWindow() {
        updateHandler.removeCallbacks(updateRunnable)
        PipelineWorkerAutoTuner.pause()
        latestSnapshot = null
        super.onDetachedFromWindow()
    }

    private fun updateSnapshot() {
        val showPerformanceLab = BooleanSetting.SHOW_MOONWITCH_PERFORMANCE_LAB.getBoolean()

        if (!showPerformanceLab || !NativeLibrary.isRunning()) {
            disableTunerInteraction()
            visibility = View.GONE
            return
        }

        val snapshot = runCatching { PerformanceLabNative.snapshot() }.getOrNull()
        if (snapshot == null || snapshot.samples <= 0) {
            disableTunerInteraction()
            visibility = View.GONE
            return
        }

        visibility = View.VISIBLE
        if (!snapshot.ready) {
            disableTunerInteraction()
            text = "MW LAB | warm-up ${snapshot.samples}/$READY_SAMPLES"
            return
        }
        latestSnapshot = snapshot

        val metrics = String.format(
            Locale.US,
            "MW LAB | Mean %.1fms | P95 %.1f | P99 %.1f | Max %.1f",
            snapshot.meanMs,
            snapshot.p95Ms,
            snapshot.p99Ms,
            snapshot.maxMs
        )
        val adpfStatus = when {
            !snapshot.adpfAvailable -> "ADPF | unavailable - scheduler fallback"
            snapshot.adpfRenderActive -> String.format(
                Locale.US,
                "ADPF | ACTIVE | %dT | target %.1fms | work %.1fms | reports %d",
                snapshot.adpfRenderThreads,
                snapshot.adpfTargetMs,
                snapshot.adpfActualMs,
                snapshot.adpfReports
            )
            else -> "ADPF | available - waiting for render session"
        }
        val pacingStatus = when {
            snapshot.pacingActive -> String.format(
                Locale.US,
                "PACING | ACTIVE | target %.0ffps | source %.1f | delay %.2fms | paced %d | resync %d",
                snapshot.pacingTargetFps,
                snapshot.pacingProducerFps,
                snapshot.pacingDelayMs,
                snapshot.pacingFrames,
                snapshot.pacingResyncs
            )
            snapshot.pacingProducerFps > 0.0 -> String.format(
                Locale.US,
                "PACING | warm-up | source %.1ffps",
                snapshot.pacingProducerFps
            )
            else -> "PACING | idle"
        }
        val frameSkipTotal = snapshot.frameSkipRenderedFrames + snapshot.frameSkipSkippedFrames
        val frameSkipRatio = if (frameSkipTotal > 0L) {
            snapshot.frameSkipSkippedFrames * 100.0 / frameSkipTotal
        } else {
            0.0
        }
        val frameSkipStatus = when {
            !snapshot.frameSkipEnabled -> "SKIP | OFF"
            !snapshot.frameSkipEligible -> "SKIP | BYPASS | incompatible mode or hidden surface"
            snapshot.frameSkipTargetFps <= 0.0 -> String.format(
                Locale.US,
                "SKIP | warm-up | cost %.2fms",
                snapshot.frameSkipEstimatedCompositeMs
            )
            else -> String.format(
                Locale.US,
                "SKIP | %s | drop %d/%d (%.1f%%) | cost %.2fms | P%d | Q %d + %d/%d | cd %d",
                if (snapshot.frameSkipPressureActive) "ACTIVE" else "MONITOR",
                snapshot.frameSkipSkippedFrames,
                frameSkipTotal,
                frameSkipRatio,
                snapshot.frameSkipEstimatedCompositeMs,
                snapshot.frameSkipPressureScore,
                snapshot.frameSkipGpuBacklog,
                snapshot.frameSkipPresentationBacklog,
                snapshot.frameSkipPresentationCapacity,
                snapshot.frameSkipCooldownFrames
            )
        }
        val baseText = "$metrics\n$adpfStatus\n$pacingStatus\n$frameSkipStatus"

        val tunerEnabled = BooleanSetting.ENABLE_PIPELINE_WORKER_AUTOTUNER.getBoolean()
        val tuningStatus = if (tunerEnabled) {
            runCatching { PipelineWorkerAutoTuner.observe(context, snapshot) }.getOrNull()
        } else {
            PipelineWorkerAutoTuner.pause()
            null
        }
        isClickable = tunerEnabled && tuningStatus != null
        isLongClickable = isClickable

        text = if (tuningStatus == null) {
            baseText
        } else {
            val tuningText = formatTuningStatus(tuningStatus)
            "$baseText\n$tuningText"
        }
    }

    private fun disableTunerInteraction() {
        PipelineWorkerAutoTuner.pause()
        latestSnapshot = null
        isClickable = false
        isLongClickable = false
    }

    private fun formatTuningStatus(status: PipelineWorkerAutoTuner.Status): String =
        when (status.phase) {
            PipelineWorkerAutoTuner.Phase.READY -> context.getString(
                R.string.moonwitch_tuner_status_ready,
                status.activeWorker
            )

            PipelineWorkerAutoTuner.Phase.RUNNING -> context.getString(
                R.string.moonwitch_tuner_status_running,
                status.activeWorker,
                status.windowsCollected,
                status.windowsRequired,
                status.framesCollected,
                status.framesRequired
            )

            PipelineWorkerAutoTuner.Phase.PAUSED -> context.getString(
                R.string.moonwitch_tuner_status_paused,
                status.activeWorker,
                status.windowsCollected,
                status.windowsRequired
            )

            PipelineWorkerAutoTuner.Phase.RESTART_REQUIRED -> if (status.wasReset) {
                context.getString(
                    R.string.moonwitch_tuner_status_reset,
                    status.nextWorker ?: status.activeWorker
                )
            } else {
                context.getString(
                    R.string.moonwitch_tuner_status_next,
                    status.activeWorker,
                    status.nextWorker ?: status.activeWorker
                )
            }

            PipelineWorkerAutoTuner.Phase.COMPLETE -> if (status.restartRequired) {
                context.getString(
                    R.string.moonwitch_tuner_status_winner_restart,
                    status.winner ?: status.activeWorker
                )
            } else {
                context.getString(
                    R.string.moonwitch_tuner_status_winner_active,
                    status.winner ?: status.activeWorker
                )
            }

            PipelineWorkerAutoTuner.Phase.ERROR ->
                context.getString(R.string.moonwitch_tuner_status_error)
        }

    private companion object {
        const val UPDATE_INTERVAL_MS = 800L
        const val READY_SAMPLES = 120
    }
}
