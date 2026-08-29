// SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
// SPDX-License-Identifier: GPL-3.0-or-later

package org.yuzu.yuzu_emu.utils

/**
 * Lightweight JNI bridge for Moonwitch Performance Lab metrics.
 *
 * Frame-time values come from individual system-frame measurements in the native core. ADPF and
 * frame-pacing telemetry are read from the native systems that actually drive the emulator, so the
 * overlay reports real behavior rather than frontend switch state.
 */
object PerformanceLabNative {
    data class FrameTimeSnapshot(
        val meanMs: Double,
        val medianMs: Double,
        val p95Ms: Double,
        val p99Ms: Double,
        val maxMs: Double,
        val samples: Int,
        val totalFrames: Long,
        val adpfAvailable: Boolean,
        val adpfRenderActive: Boolean,
        val adpfBackgroundActive: Boolean,
        val adpfRenderThreads: Int,
        val adpfBackgroundThreads: Int,
        val adpfReports: Long,
        val adpfTargetMs: Double,
        val adpfActualMs: Double,
        val pacingActive: Boolean,
        val pacingTargetFps: Double,
        val pacingProducerFps: Double,
        val pacingFrames: Long,
        val pacingResyncs: Long,
        val pacingDelayMs: Double
    ) {
        val ready: Boolean
            get() = samples >= 120

        val fullWindow: Boolean
            get() = samples >= 600
    }

    external fun getRecentFrameTimeStats(): DoubleArray

    fun snapshot(): FrameTimeSnapshot {
        val values = getRecentFrameTimeStats()
        if (values.size < 21) {
            return FrameTimeSnapshot(
                0.0, 0.0, 0.0, 0.0, 0.0, 0, 0L,
                false, false, false, 0, 0, 0L, 0.0, 0.0,
                false, 0.0, 0.0, 0L, 0L, 0.0
            )
        }

        return FrameTimeSnapshot(
            meanMs = values[0],
            medianMs = values[1],
            p95Ms = values[2],
            p99Ms = values[3],
            maxMs = values[4],
            samples = values[5].toInt(),
            totalFrames = values[6].toLong(),
            adpfAvailable = values[7] != 0.0,
            adpfRenderActive = values[8] != 0.0,
            adpfBackgroundActive = values[9] != 0.0,
            adpfRenderThreads = values[10].toInt(),
            adpfBackgroundThreads = values[11].toInt(),
            adpfReports = values[12].toLong(),
            adpfTargetMs = values[13],
            adpfActualMs = values[14],
            pacingActive = values[15] != 0.0,
            pacingTargetFps = values[16],
            pacingProducerFps = values[17],
            pacingFrames = values[18].toLong(),
            pacingResyncs = values[19].toLong(),
            pacingDelayMs = values[20]
        )
    }
}
