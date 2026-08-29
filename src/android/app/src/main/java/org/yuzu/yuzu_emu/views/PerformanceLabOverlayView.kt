// SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
// SPDX-License-Identifier: GPL-3.0-or-later

package org.yuzu.yuzu_emu.views

import android.content.Context
import android.os.Handler
import android.os.Looper
import android.util.AttributeSet
import android.view.View
import com.google.android.material.textview.MaterialTextView
import org.yuzu.yuzu_emu.NativeLibrary
import org.yuzu.yuzu_emu.features.settings.model.BooleanSetting
import org.yuzu.yuzu_emu.utils.NativeConfig
import org.yuzu.yuzu_emu.utils.PerformanceLabNative
import org.yuzu.yuzu_emu.utils.PipelineWorkerAutoTuner
import java.util.Locale

/**
 * Lightweight Moonwitch Performance Lab readout.
 *
 * The normal Eden overlay samples aggregate performance counters every 800 ms. This view reads the
 * rolling native frame history instead, so P95/P99 are calculated from individual system frames.
 * On the validated TOTK/POCO F5 target it also feeds the cross-session pipeline-worker tuner.
 */
class PerformanceLabOverlayView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
    defStyleAttr: Int = 0
) : MaterialTextView(context, attrs, defStyleAttr) {

    private val updateHandler = Handler(Looper.getMainLooper())

    private val updateRunnable = object : Runnable {
        override fun run() {
            updateSnapshot()
            if (isAttachedToWindow) {
                updateHandler.postDelayed(this, UPDATE_INTERVAL_MS)
            }
        }
    }

    override fun onAttachedToWindow() {
        super.onAttachedToWindow()
        updateHandler.removeCallbacks(updateRunnable)
        updateHandler.post(updateRunnable)
    }

    override fun onDetachedFromWindow() {
        updateHandler.removeCallbacks(updateRunnable)
        super.onDetachedFromWindow()
    }

    private fun updateSnapshot() {
        val showPerformanceOverlay = BooleanSetting.SHOW_PERFORMANCE_OVERLAY.getBoolean()
        val perGameConfigLoaded = NativeConfig.isPerGameConfigLoaded()
        val showFrametime = BooleanSetting.SHOW_FRAMETIME.getBoolean(perGameConfigLoaded)

        if (!showPerformanceOverlay || !showFrametime || !NativeLibrary.isRunning()) {
            visibility = View.GONE
            return
        }

        val snapshot = runCatching { PerformanceLabNative.snapshot() }.getOrNull()
        if (snapshot == null || snapshot.samples <= 0) {
            visibility = View.GONE
            return
        }

        visibility = View.VISIBLE
        if (!snapshot.ready) {
            text = "MW LAB | warm-up ${snapshot.samples}/$READY_SAMPLES"
            return
        }

        val metrics = String.format(
            Locale.US,
            "MW LAB | Mean %.1fms | P95 %.1f | P99 %.1f | Max %.1f",
            snapshot.meanMs,
            snapshot.p95Ms,
            snapshot.p99Ms,
            snapshot.maxMs
        )

        val tuningStatus = runCatching {
            PipelineWorkerAutoTuner.observe(context, snapshot)
        }.getOrNull()

        text = if (tuningStatus == null) {
            metrics
        } else {
            val tuningText = when {
                tuningStatus.winner != null ->
                    "TUNE | W${tuningStatus.activeWorker} done | winner W${tuningStatus.winner} • restart"

                tuningStatus.nextWorker != null ->
                    "TUNE | W${tuningStatus.activeWorker} done | next W${tuningStatus.nextWorker} • restart"

                else ->
                    "TUNE | W${tuningStatus.activeWorker} ${tuningStatus.windowsCollected}/${tuningStatus.windowsRequired}"
            }
            "$metrics\n$tuningText"
        }
    }

    private companion object {
        const val UPDATE_INTERVAL_MS = 800L
        const val READY_SAMPLES = 120
    }
}
