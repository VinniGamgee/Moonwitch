// SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
// SPDX-License-Identifier: GPL-3.0-or-later

package org.yuzu.yuzu_emu.utils

import android.content.Context
import android.os.Build
import java.util.Locale
import org.yuzu.yuzu_emu.NativeLibrary
import org.yuzu.yuzu_emu.features.settings.model.IntSetting

/**
 * Cross-session pipeline-worker tuner for the currently validated Moonwitch target.
 *
 * Vulkan's pipeline ThreadWorker is created with a fixed thread count when PipelineCache is
 * constructed. Changing pipeline_worker_count while a game is running therefore cannot benchmark
 * another worker count correctly. This tuner measures three non-overlapping 600-frame windows for
 * one candidate, writes the next candidate to the game's per-game config, and asks the user to
 * restart. Once every candidate has been measured it persists the best worker count.
 */
object PipelineWorkerAutoTuner {
    private const val TOTK_TITLE_ID = "0100F2C0115B6000"
    private const val FRAMES_PER_WINDOW = 600L
    private const val WINDOWS_PER_CANDIDATE = 3
    private const val PREFS_NAME = "moonwitch_performance_lab"

    // Start with Moonwitch's current validated value, then probe lower/higher contention levels.
    private val candidates = intArrayOf(4, 2, 3, 5)
    private val pocoF5Models = setOf("23049PCD8G", "23049PCD8I")

    data class Status(
        val activeWorker: Int,
        val windowsCollected: Int,
        val windowsRequired: Int = WINDOWS_PER_CANDIDATE,
        val nextWorker: Int? = null,
        val winner: Int? = null
    )

    private data class Score(
        val worker: Int,
        val p99Ms: Double,
        val p95Ms: Double,
        val meanMs: Double
    )

    private var sessionIdentity: String? = null
    private var activeWorker = 0
    private var lastRecordedFrame = 0L
    private var sessionFinished = false
    private val p99Samples = mutableListOf<Double>()
    private val p95Samples = mutableListOf<Double>()
    private val meanSamples = mutableListOf<Double>()
    private var finalStatus: Status? = null

    fun observe(
        context: Context,
        snapshot: PerformanceLabNative.FrameTimeSnapshot
    ): Status? {
        if (!isPocoF5() || !snapshot.fullWindow || !NativeLibrary.isRunning()) {
            return null
        }

        val titleId = currentTitleId() ?: return null
        if (titleId != TOTK_TITLE_ID) {
            return null
        }

        val driverFingerprint = runCatching {
            "${NativeLibrary.getGpuDriver()}|${NativeLibrary.getVulkanDriverVersion()}"
        }.getOrDefault("unknown-driver")
        val identity = "$titleId|$driverFingerprint"

        if (sessionIdentity != identity || snapshot.totalFrames < lastRecordedFrame) {
            resetSession(identity)
        }

        if (activeWorker == 0) {
            // GetValue(false) reflects the currently loaded switchable value used during launch.
            activeWorker = IntSetting.ANDROID_PIPELINE_WORKERS.getInt(false).coerceIn(2, 8)
        }
        if (activeWorker !in candidates) {
            return null
        }
        if (sessionFinished) {
            return finalStatus
        }

        if (lastRecordedFrame != 0L &&
            snapshot.totalFrames - lastRecordedFrame < FRAMES_PER_WINDOW
        ) {
            return Status(activeWorker, p99Samples.size)
        }

        p99Samples += snapshot.p99Ms
        p95Samples += snapshot.p95Ms
        meanSamples += snapshot.meanMs
        lastRecordedFrame = snapshot.totalFrames

        if (p99Samples.size < WINDOWS_PER_CANDIDATE) {
            return Status(activeWorker, p99Samples.size)
        }

        val prefs = context.applicationContext.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val score = Score(
            worker = activeWorker,
            p99Ms = median(p99Samples),
            p95Ms = median(p95Samples),
            meanMs = median(meanSamples)
        )
        saveScore(prefs, identity, score)

        val scores = candidates.mapNotNull { loadScore(prefs, identity, it) }
        val missing = candidates.firstOrNull { candidate -> scores.none { it.worker == candidate } }

        finalStatus = if (missing != null) {
            if (writeWorkerForNextLaunch(titleId, activeWorker, missing)) {
                Status(
                    activeWorker = activeWorker,
                    windowsCollected = WINDOWS_PER_CANDIDATE,
                    nextWorker = missing
                )
            } else {
                Status(activeWorker, WINDOWS_PER_CANDIDATE)
            }
        } else {
            val best = scores.minWithOrNull(
                compareBy<Score> { it.p99Ms }
                    .thenBy { it.p95Ms }
                    .thenBy { it.meanMs }
            ) ?: score
            writeWorkerForNextLaunch(titleId, activeWorker, best.worker)
            prefs.edit().putInt("$identity|winner", best.worker).apply()
            Status(
                activeWorker = activeWorker,
                windowsCollected = WINDOWS_PER_CANDIDATE,
                winner = best.worker
            )
        }
        sessionFinished = true
        return finalStatus
    }

    private fun writeWorkerForNextLaunch(
        titleId: String,
        currentWorker: Int,
        nextWorker: Int
    ): Boolean {
        if (NativeConfig.isPerGameConfigLoaded()) {
            // Avoid racing a settings screen or another owner of the per-game config object.
            return false
        }

        return runCatching {
            // A non-zero program ID determines the custom config filename; fileName can be empty.
            NativeConfig.initializePerGameConfig(titleId, "")
            IntSetting.ANDROID_PIPELINE_WORKERS.setInt(nextWorker)
            NativeConfig.savePerGameConfig()

            // Keep the live switchable value equal to the worker count that actually created this
            // session's PipelineCache. The saved file still contains nextWorker.
            IntSetting.ANDROID_PIPELINE_WORKERS.setInt(currentWorker)
            NativeConfig.unloadPerGameConfig()
            true
        }.getOrElse {
            if (NativeConfig.isPerGameConfigLoaded()) {
                runCatching { NativeConfig.unloadPerGameConfig() }
            }
            Log.error("[PipelineWorkerAutoTuner] Failed to persist next candidate: ${it.message}")
            false
        }
    }

    private fun saveScore(
        prefs: android.content.SharedPreferences,
        identity: String,
        score: Score
    ) {
        prefs.edit()
            .putLong("$identity|w${score.worker}|p99", score.p99Ms.toRawBits())
            .putLong("$identity|w${score.worker}|p95", score.p95Ms.toRawBits())
            .putLong("$identity|w${score.worker}|mean", score.meanMs.toRawBits())
            .apply()
    }

    private fun loadScore(
        prefs: android.content.SharedPreferences,
        identity: String,
        worker: Int
    ): Score? {
        val p99Key = "$identity|w$worker|p99"
        val p95Key = "$identity|w$worker|p95"
        val meanKey = "$identity|w$worker|mean"
        if (!prefs.contains(p99Key) || !prefs.contains(p95Key) || !prefs.contains(meanKey)) {
            return null
        }
        return Score(
            worker = worker,
            p99Ms = Double.fromBits(prefs.getLong(p99Key, 0L)),
            p95Ms = Double.fromBits(prefs.getLong(p95Key, 0L)),
            meanMs = Double.fromBits(prefs.getLong(meanKey, 0L))
        )
    }

    private fun resetSession(identity: String) {
        sessionIdentity = identity
        activeWorker = 0
        lastRecordedFrame = 0L
        sessionFinished = false
        p99Samples.clear()
        p95Samples.clear()
        meanSamples.clear()
        finalStatus = null
    }

    private fun currentTitleId(): String? {
        val raw = runCatching { NativeLibrary.playTimeManagerGetCurrentTitleId() }.getOrDefault(0L)
        if (raw == 0L) {
            return null
        }
        return String.format(Locale.US, "%016X", raw)
    }

    private fun median(values: List<Double>): Double {
        if (values.isEmpty()) {
            return Double.POSITIVE_INFINITY
        }
        val sorted = values.sorted()
        return sorted[sorted.size / 2]
    }

    private fun isPocoF5(): Boolean {
        val model = Build.MODEL.uppercase(Locale.ROOT)
        val device = Build.DEVICE.lowercase(Locale.ROOT)
        return model in pocoF5Models || device == "marble"
    }
}
