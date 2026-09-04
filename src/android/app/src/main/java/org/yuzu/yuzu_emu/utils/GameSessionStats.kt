// SPDX-FileCopyrightText: Copyright 2026 Eden Emulator Project
// SPDX-License-Identifier: GPL-3.0-or-later

package org.yuzu.yuzu_emu.utils

import android.content.Context
import android.content.SharedPreferences
import androidx.core.content.edit
import androidx.preference.PreferenceManager
import org.yuzu.yuzu_emu.NativeLibrary
import org.yuzu.yuzu_emu.model.Game

/**
 * Persists real, per-game session aggregates around the native play-time manager.
 *
 * A session begins only after native emulation reports that it started. Durations are derived from
 * the native play-time delta instead of wall-clock time, so time spent paused is not counted. The
 * active marker also lets the next frontend visit recover a session after an abnormal process exit.
 */
object GameSessionStats {
    data class Snapshot(
        val sessionCount: Int,
        val longestSessionSeconds: Long,
        val averageSessionSeconds: Long
    )

    private const val PREFERENCES_NAME = "moonwitch_game_session_stats"
    private const val ACTIVE_GAME_KEY = "active_game_key"
    private const val ACTIVE_PROGRAM_ID = "active_program_id"
    private const val ACTIVE_BASELINE_SECONDS = "active_baseline_seconds"
    private var processActiveGameKey: String? = null

    @Synchronized
    fun start(context: Context, game: Game) {
        val preferences = preferences(context)
        val gameKey = gameKey(game)
        val activeGameKey = preferences.getString(ACTIVE_GAME_KEY, null)

        if (activeGameKey == gameKey && processActiveGameKey == gameKey) {
            return
        }
        if (activeGameKey != null) {
            finishActive(preferences)
        }

        val baseline = nativePlayTime(game.programId)
        preferences.edit {
            putString(ACTIVE_GAME_KEY, gameKey)
            putString(ACTIVE_PROGRAM_ID, game.programId)
            putLong(ACTIVE_BASELINE_SECONDS, baseline)
            putInt(sessionCountKey(gameKey), preferences.getInt(sessionCountKey(gameKey), 0) + 1)
        }
        processActiveGameKey = gameKey

        PreferenceManager.getDefaultSharedPreferences(context.applicationContext).edit {
            putLong(game.keyLastPlayedTime, System.currentTimeMillis())
        }
    }

    @Synchronized
    fun stop(context: Context, game: Game) {
        val preferences = preferences(context)
        if (preferences.getString(ACTIVE_GAME_KEY, null) != gameKey(game)) {
            return
        }
        finishActive(preferences)
    }

    @Synchronized
    fun snapshot(context: Context, game: Game): Snapshot {
        val preferences = preferences(context)
        val gameKey = gameKey(game)

        val isNativeRunning = runCatching { NativeLibrary.isRunning() }.getOrDefault(false)
        if (preferences.getString(ACTIVE_GAME_KEY, null) != null && !isNativeRunning) {
            finishActive(preferences)
        }

        val completedSeconds = preferences.getLong(totalDurationKey(gameKey), 0L)
        val completedLongest = preferences.getLong(longestDurationKey(gameKey), 0L)
        val activeSeconds = if (preferences.getString(ACTIVE_GAME_KEY, null) == gameKey) {
            val baseline = preferences.getLong(ACTIVE_BASELINE_SECONDS, 0L)
            (nativePlayTime(game.programId) - baseline).coerceAtLeast(0L)
        } else {
            0L
        }
        val sessionCount = preferences.getInt(sessionCountKey(gameKey), 0)
        val combinedSeconds = completedSeconds + activeSeconds

        return Snapshot(
            sessionCount = sessionCount,
            longestSessionSeconds = maxOf(completedLongest, activeSeconds),
            averageSessionSeconds = if (sessionCount > 0) combinedSeconds / sessionCount else 0L
        )
    }

    private fun finishActive(preferences: SharedPreferences) {
        val activeGameKey = preferences.getString(ACTIVE_GAME_KEY, null) ?: return
        val programId = preferences.getString(ACTIVE_PROGRAM_ID, null).orEmpty()
        val baseline = preferences.getLong(ACTIVE_BASELINE_SECONDS, 0L)
        val duration = (nativePlayTime(programId) - baseline).coerceAtLeast(0L)
        val totalKey = totalDurationKey(activeGameKey)
        val longestKey = longestDurationKey(activeGameKey)

        preferences.edit {
            putLong(totalKey, preferences.getLong(totalKey, 0L) + duration)
            putLong(longestKey, maxOf(preferences.getLong(longestKey, 0L), duration))
            remove(ACTIVE_GAME_KEY)
            remove(ACTIVE_PROGRAM_ID)
            remove(ACTIVE_BASELINE_SECONDS)
        }
        processActiveGameKey = null
    }

    private fun nativePlayTime(programId: String): Long =
        runCatching { NativeLibrary.playTimeManagerGetPlayTime(programId) }.getOrDefault(0L)

    private fun preferences(context: Context) =
        context.applicationContext.getSharedPreferences(PREFERENCES_NAME, Context.MODE_PRIVATE)

    private fun gameKey(game: Game): String = game.settingsName
    private fun sessionCountKey(gameKey: String) = "session_count::$gameKey"
    private fun totalDurationKey(gameKey: String) = "total_duration::$gameKey"
    private fun longestDurationKey(gameKey: String) = "longest_duration::$gameKey"
}
