// SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
// SPDX-License-Identifier: GPL-3.0-or-later

package org.yuzu.yuzu_emu.utils

/**
 * Lightweight JNI bridge for Moonwitch Performance Lab metrics.
 *
 * These values come from individual system-frame measurements in the native core. They are not
 * percentiles calculated from the Android overlay's 800 ms aggregate samples.
 */
object PerformanceLabNative {
    data class FrameTimeSnapshot(
        val meanMs: Double,
        val medianMs: Double,
        val p95Ms: Double,
        val p99Ms: Double,
        val maxMs: Double,
        val samples: Int,
        val totalFrames: Long
    ) {
        val ready: Boolean
            get() = samples >= 120

        val fullWindow: Boolean
            get() = samples >= 600
    }

    external fun getRecentFrameTimeStats(): DoubleArray

    fun snapshot(): FrameTimeSnapshot {
        val values = getRecentFrameTimeStats()
        if (values.size < 7) {
            return FrameTimeSnapshot(0.0, 0.0, 0.0, 0.0, 0.0, 0, 0L)
        }

        return FrameTimeSnapshot(
            meanMs = values[0],
            medianMs = values[1],
            p95Ms = values[2],
            p99Ms = values[3],
            maxMs = values[4],
            samples = values[5].toInt(),
            totalFrames = values[6].toLong()
        )
    }
}
