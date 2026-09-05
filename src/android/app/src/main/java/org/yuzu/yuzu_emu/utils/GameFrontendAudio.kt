// SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
// SPDX-License-Identifier: GPL-3.0-or-later

package org.yuzu.yuzu_emu.utils

import android.animation.ValueAnimator
import android.content.Context
import android.media.AudioAttributes
import android.media.AudioFocusRequest
import android.media.AudioManager
import android.media.MediaPlayer
import android.os.Build
import org.yuzu.yuzu_emu.model.Game
import java.io.File

/**
 * Owns the optional per-game music used by Moonwitch's frontend.
 *
 * Tracks are user supplied and live beside the game's custom frontend artwork.
 * Nothing is bundled or downloaded by Moonwitch.
 */
object GameFrontendAudio {
    private const val TARGET_VOLUME = 0.30f
    private const val DUCK_VOLUME = 0.08f
    private const val FADE_IN_MS = 450L

    val supportedExtensions: Set<String> = linkedSetOf("mp3", "ogg", "m4a", "wav", "aac", "flac")

    private val audioAttributes = AudioAttributes.Builder()
        .setUsage(AudioAttributes.USAGE_GAME)
        .setContentType(AudioAttributes.CONTENT_TYPE_MUSIC)
        .build()

    private var mediaPlayer: MediaPlayer? = null
    private var currentTrackKey: String? = null
    private var fadeAnimator: ValueAnimator? = null
    private var audioManager: AudioManager? = null
    private var audioFocusRequest: AudioFocusRequest? = null
    private var hasAudioFocus = false

    private val focusChangeListener = AudioManager.OnAudioFocusChangeListener { change ->
        when (change) {
            AudioManager.AUDIOFOCUS_GAIN -> {
                mediaPlayer?.let { player ->
                    runCatching {
                        player.setVolume(TARGET_VOLUME, TARGET_VOLUME)
                        if (!player.isPlaying) player.start()
                    }
                }
            }

            AudioManager.AUDIOFOCUS_LOSS_TRANSIENT_CAN_DUCK -> {
                mediaPlayer?.let { player ->
                    runCatching { player.setVolume(DUCK_VOLUME, DUCK_VOLUME) }
                }
            }

            AudioManager.AUDIOFOCUS_LOSS_TRANSIENT -> {
                mediaPlayer?.let { player ->
                    runCatching { if (player.isPlaying) player.pause() }
                }
            }

            AudioManager.AUDIOFOCUS_LOSS -> stop()
        }
    }

    fun musicFile(game: Game): File? {
        val directory = File(
            DirectoryInitialization.userDirectory + "/moonwitch/metadata/" + game.settingsName
        )
        return supportedExtensions.asSequence()
            .map { extension -> File(directory, "music.$extension") }
            .firstOrNull(File::isFile)
    }

    fun deleteMusicFiles(game: Game): Boolean {
        val directory = File(
            DirectoryInitialization.userDirectory + "/moonwitch/metadata/" + game.settingsName
        )
        var removed = false
        supportedExtensions.forEach { extension ->
            val file = File(directory, "music.$extension")
            if (file.exists()) removed = file.delete() || removed
        }
        return removed
    }

    @Synchronized
    fun play(context: Context, game: Game) {
        val track = musicFile(game)
        if (track == null) {
            stop()
            return
        }

        val trackKey = "${game.settingsName}:${track.absolutePath}:${track.lastModified()}:${track.length()}"
        if (currentTrackKey == trackKey && mediaPlayer != null) return

        stop()
        if (!requestAudioFocus(context.applicationContext)) return

        currentTrackKey = trackKey
        val player = MediaPlayer()
        mediaPlayer = player

        runCatching {
            player.setAudioAttributes(audioAttributes)
            player.isLooping = true
            player.setVolume(0f, 0f)
            player.setOnPreparedListener { prepared ->
                if (mediaPlayer !== prepared || currentTrackKey != trackKey) {
                    runCatching { prepared.release() }
                    return@setOnPreparedListener
                }
                runCatching {
                    prepared.start()
                    fadeIn(prepared, trackKey)
                }.onFailure {
                    if (mediaPlayer === prepared) stop()
                }
            }
            player.setOnErrorListener { failed, _, _ ->
                if (mediaPlayer === failed) stop()
                true
            }
            player.setDataSource(track.absolutePath)
            player.prepareAsync()
        }.onFailure {
            stop()
        }
    }

    @Synchronized
    fun stop() {
        fadeAnimator?.cancel()
        fadeAnimator = null
        currentTrackKey = null

        mediaPlayer?.let { player ->
            player.setOnPreparedListener(null)
            player.setOnErrorListener(null)
            runCatching { if (player.isPlaying) player.stop() }
            runCatching { player.reset() }
            runCatching { player.release() }
        }
        mediaPlayer = null
        abandonAudioFocus()
    }

    private fun fadeIn(player: MediaPlayer, trackKey: String) {
        fadeAnimator?.cancel()
        fadeAnimator = ValueAnimator.ofFloat(0f, TARGET_VOLUME).apply {
            duration = FADE_IN_MS
            addUpdateListener { animator ->
                if (mediaPlayer !== player || currentTrackKey != trackKey) {
                    cancel()
                    return@addUpdateListener
                }
                val volume = animator.animatedValue as Float
                runCatching { player.setVolume(volume, volume) }
            }
            start()
        }
    }

    private fun requestAudioFocus(context: Context): Boolean {
        val manager = context.getSystemService(Context.AUDIO_SERVICE) as? AudioManager ?: return true
        audioManager = manager
        val result = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val request = AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN)
                .setAudioAttributes(audioAttributes)
                .setAcceptsDelayedFocusGain(false)
                .setOnAudioFocusChangeListener(focusChangeListener)
                .build()
            audioFocusRequest = request
            manager.requestAudioFocus(request)
        } else {
            @Suppress("DEPRECATION")
            manager.requestAudioFocus(
                focusChangeListener,
                AudioManager.STREAM_MUSIC,
                AudioManager.AUDIOFOCUS_GAIN
            )
        }
        hasAudioFocus = result == AudioManager.AUDIOFOCUS_REQUEST_GRANTED
        return hasAudioFocus
    }

    private fun abandonAudioFocus() {
        if (!hasAudioFocus) return
        val manager = audioManager ?: return
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            audioFocusRequest?.let { request -> manager.abandonAudioFocusRequest(request) }
        } else {
            @Suppress("DEPRECATION")
            manager.abandonAudioFocus(focusChangeListener)
        }
        hasAudioFocus = false
        audioFocusRequest = null
        audioManager = null
    }
}
