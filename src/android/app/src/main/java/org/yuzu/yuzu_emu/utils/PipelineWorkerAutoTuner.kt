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
 * another worker count correctly. The player manually starts each candidate after reaching a
 * repeatable gameplay area. The tuner then measures three non-overlapping 600-frame windows,
 * writes the next candidate to the game's per-game config, and asks the player to restart. Once
 * every candidate has been measured it persists the best worker count.
 */
object PipelineWorkerAutoTuner {
    private const val TOTK_TITLE_ID = "0100F2C0115B6000"
    private const val FRAMES_PER_WINDOW = 600L
    private const val WINDOWS_PER_CANDIDATE = 3
    private const val PREFS_NAME = "moonwitch_performance_lab"
    private const val PREFS_SCHEMA = "v2"

    // Start with Moonwitch's current validated value, then probe lower/higher contention levels.
    private val candidates = intArrayOf(4, 2, 3, 5)
    private val pocoF5Models = setOf("23049PCD8G", "23049PCD8I")

    enum class Phase {
        READY,
        RUNNING,
        PAUSED,
        RESTART_REQUIRED,
        COMPLETE,
        ERROR
    }

    data class Status(
        val activeWorker: Int,
        val windowsCollected: Int,
        val windowsRequired: Int = WINDOWS_PER_CANDIDATE,
        val framesCollected: Long = 0L,
        val framesRequired: Long = FRAMES_PER_WINDOW,
        val phase: Phase = Phase.READY,
        val nextWorker: Int? = null,
        val winner: Int? = null,
        val restartRequired: Boolean = false,
        val wasReset: Boolean = false
    )

    private data class Score(
        val worker: Int,
        val p99Ms: Double,
        val p95Ms: Double,
        val meanMs: Double
    )

    private var sessionIdentity: String? = null
    private var activeWorker = 0
    private var windowStartFrame = 0L
    private var lastObservedFrame = 0L
    private var restoredPersistentState = false
    private var phase = Phase.READY
    private val p99Samples = mutableListOf<Double>()
    private val p95Samples = mutableListOf<Double>()
    private val meanSamples = mutableListOf<Double>()
    private var finalStatus: Status? = null

    @Synchronized
    fun observe(
        context: Context,
        snapshot: PerformanceLabNative.FrameTimeSnapshot
    ): Status? {
        val target = currentTarget() ?: return null
        if (!ensureSession(context, target, snapshot)) {
            return null
        }

        finalStatus?.let { return it }
        if (phase != Phase.RUNNING) {
            return currentStatus()
        }

        val elapsedFrames = (snapshot.totalFrames - windowStartFrame)
            .coerceIn(0L, FRAMES_PER_WINDOW)
        if (elapsedFrames < FRAMES_PER_WINDOW || !snapshot.fullWindow) {
            return currentStatus(elapsedFrames)
        }

        // The native ring buffer contains exactly the latest 600 system frames here. Because the
        // baseline is captured on the user's tap, boot and title-screen frames cannot leak into
        // this measurement window.
        p99Samples += snapshot.p99Ms
        p95Samples += snapshot.p95Ms
        meanSamples += snapshot.meanMs
        windowStartFrame = snapshot.totalFrames

        if (p99Samples.size < WINDOWS_PER_CANDIDATE) {
            return currentStatus()
        }

        val prefs = context.applicationContext.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val score = Score(
            worker = activeWorker,
            p99Ms = median(p99Samples),
            p95Ms = median(p95Samples),
            meanMs = median(meanSamples)
        )
        saveScore(prefs, target.identity, score)

        val scores = candidates.map { loadScore(prefs, target.identity, it) }.filterNotNull()
        val missing = candidates.firstOrNull { candidate -> scores.none { it.worker == candidate } }

        finalStatus = if (missing != null) {
            if (writeWorkerForNextLaunch(target.titleId, activeWorker, missing)) {
                phase = Phase.RESTART_REQUIRED
                Status(
                    activeWorker = activeWorker,
                    windowsCollected = WINDOWS_PER_CANDIDATE,
                    phase = phase,
                    nextWorker = missing,
                    restartRequired = true
                )
            } else {
                phase = Phase.ERROR
                currentStatus()
            }
        } else {
            val best = scores.minWithOrNull(
                compareBy<Score> { it.p99Ms }
                    .thenBy { it.p95Ms }
                    .thenBy { it.meanMs }
            ) ?: score
            if (writeWorkerForNextLaunch(target.titleId, activeWorker, best.worker)) {
                prefs.edit().putInt("${target.identity}|winner", best.worker).apply()
                phase = Phase.COMPLETE
                Status(
                    activeWorker = activeWorker,
                    windowsCollected = WINDOWS_PER_CANDIDATE,
                    phase = phase,
                    winner = best.worker,
                    restartRequired = best.worker != activeWorker
                )
            } else {
                phase = Phase.ERROR
                currentStatus()
            }
        }
        return finalStatus
    }

    /** Starts, pauses, or resumes a candidate without including frames from before the tap. */
    @Synchronized
    fun toggleCapture(
        context: Context,
        snapshot: PerformanceLabNative.FrameTimeSnapshot
    ): Status? {
        val target = currentTarget() ?: return null
        if (!ensureSession(context, target, snapshot)) {
            return null
        }
        finalStatus?.let { return it }

        phase = if (phase == Phase.RUNNING) Phase.PAUSED else Phase.RUNNING
        // Pausing discards only the unfinished part of the current window. Completed windows stay.
        windowStartFrame = snapshot.totalFrames
        return currentStatus()
    }

    /** Pauses an in-progress window when the overlay or tuner is disabled. */
    @Synchronized
    fun pause() {
        if (phase == Phase.RUNNING) {
            phase = Phase.PAUSED
            windowStartFrame = 0L
        }
    }

    /** Clears scores for the current game/driver and restores W4 as the first candidate. */
    @Synchronized
    fun reset(
        context: Context,
        snapshot: PerformanceLabNative.FrameTimeSnapshot
    ): Status? {
        val target = currentTarget() ?: return null
        resetSession(target.identity)
        lastObservedFrame = snapshot.totalFrames
        activeWorker = currentPipelineWorker()
        if (activeWorker !in 2..8) {
            return null
        }

        val prefs = context.applicationContext.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        clearScores(prefs, target.identity)
        restoredPersistentState = true

        val firstWorker = candidates.first()
        return if (activeWorker == firstWorker) {
            phase = Phase.READY
            currentStatus(wasReset = true)
        } else if (writeWorkerForNextLaunch(target.titleId, activeWorker, firstWorker)) {
            phase = Phase.RESTART_REQUIRED
            Status(
                activeWorker = activeWorker,
                windowsCollected = 0,
                phase = phase,
                nextWorker = firstWorker,
                restartRequired = true,
                wasReset = true
            ).also { finalStatus = it }
        } else {
            phase = Phase.ERROR
            currentStatus(wasReset = true)
        }
    }

    private data class Target(val titleId: String, val identity: String)

    private fun currentTarget(): Target? {
        if (!isPocoF5() || !NativeLibrary.isRunning()) {
            return null
        }
        val titleId = currentTitleId() ?: return null
        if (titleId != TOTK_TITLE_ID) {
            return null
        }
        val driverFingerprint = runCatching {
            "${NativeLibrary.getGpuDriver()}|${NativeLibrary.getVulkanDriverVersion()}"
        }.getOrDefault("unknown-driver")
        return Target(titleId, "$PREFS_SCHEMA|$titleId|$driverFingerprint")
    }

    private fun ensureSession(
        context: Context,
        target: Target,
        snapshot: PerformanceLabNative.FrameTimeSnapshot
    ): Boolean {
        if (sessionIdentity != target.identity ||
            (lastObservedFrame != 0L && snapshot.totalFrames < lastObservedFrame)
        ) {
            resetSession(target.identity)
        }
        lastObservedFrame = snapshot.totalFrames

        if (activeWorker == 0) {
            activeWorker = currentPipelineWorker()
        }
        if (activeWorker !in candidates) {
            return false
        }

        if (!restoredPersistentState) {
            restorePersistentState(context, target)
            restoredPersistentState = true
        }
        return true
    }

    private fun restorePersistentState(context: Context, target: Target) {
        val prefs = context.applicationContext.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val scores = candidates.map { loadScore(prefs, target.identity, it) }.filterNotNull()
        val winner = prefs.getInt("${target.identity}|winner", 0)

        if (scores.size == candidates.size && winner in candidates) {
            val saved = winner == activeWorker ||
                writeWorkerForNextLaunch(target.titleId, activeWorker, winner)
            phase = if (saved) Phase.COMPLETE else Phase.ERROR
            finalStatus = if (saved) {
                Status(
                    activeWorker = activeWorker,
                    windowsCollected = WINDOWS_PER_CANDIDATE,
                    phase = phase,
                    winner = winner,
                    restartRequired = winner != activeWorker
                )
            } else {
                currentStatus()
            }
            return
        }

        // Recover cleanly if a candidate was saved before the process restarted but the per-game
        // config did not advance for any reason.
        if (scores.any { it.worker == activeWorker }) {
            val missing = candidates.firstOrNull { candidate -> scores.none { it.worker == candidate } }
            if (missing != null) {
                val saved = writeWorkerForNextLaunch(target.titleId, activeWorker, missing)
                phase = if (saved) Phase.RESTART_REQUIRED else Phase.ERROR
                finalStatus = if (saved) {
                    Status(
                        activeWorker = activeWorker,
                        windowsCollected = WINDOWS_PER_CANDIDATE,
                        phase = phase,
                        nextWorker = missing,
                        restartRequired = true
                    )
                } else {
                    currentStatus()
                }
            }
        }
    }

    private fun currentPipelineWorker(): Int {
        // GetValue(false) reflects the switchable value that constructed this session's cache.
        return IntSetting.ANDROID_PIPELINE_WORKERS.getInt(false).coerceIn(2, 8)
    }

    private fun currentStatus(
        framesCollected: Long = 0L,
        wasReset: Boolean = false
    ): Status = Status(
        activeWorker = activeWorker,
        windowsCollected = p99Samples.size,
        framesCollected = framesCollected,
        phase = phase,
        wasReset = wasReset
    )

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
            // Game.programId is decimal. A non-zero program ID determines the custom config
            // filename, so fileName can be empty here.
            val decimalProgramId = titleId.toLong(16).toString()
            NativeConfig.initializePerGameConfig(decimalProgramId, "")
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

    private fun clearScores(
        prefs: android.content.SharedPreferences,
        identity: String
    ) {
        val editor = prefs.edit().remove("$identity|winner")
        candidates.forEach { worker ->
            editor
                .remove("$identity|w$worker|p99")
                .remove("$identity|w$worker|p95")
                .remove("$identity|w$worker|mean")
        }
        editor.apply()
    }

    private fun resetSession(identity: String) {
        sessionIdentity = identity
        activeWorker = 0
        windowStartFrame = 0L
        lastObservedFrame = 0L
        restoredPersistentState = false
        phase = Phase.READY
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
