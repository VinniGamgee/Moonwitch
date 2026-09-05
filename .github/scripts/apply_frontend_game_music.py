from pathlib import Path

ROOT = Path('.')


def replace_once(path: str, old: str, new: str) -> None:
    file = ROOT / path
    text = file.read_text()
    if old not in text:
        raise SystemExit(f'Expected anchor not found in {path}: {old[:120]!r}')
    file.write_text(text.replace(old, new, 1))


def write_new(path: str, content: str) -> None:
    file = ROOT / path
    if file.exists():
        raise SystemExit(f'Refusing to overwrite existing file: {path}')
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(content)


# ---------------------------------------------------------------------------
# Shared frontend audio controller
# ---------------------------------------------------------------------------
write_new(
    'src/android/app/src/main/java/org/yuzu/yuzu_emu/utils/GameFrontendAudio.kt',
    '''// SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
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
'''
)


# ---------------------------------------------------------------------------
# Home: follow highlighted game, stop when frontend leaves the foreground.
# ---------------------------------------------------------------------------
games_path = 'src/android/app/src/main/java/org/yuzu/yuzu_emu/ui/GamesFragment.kt'
replace_once(
    games_path,
    'import org.yuzu.yuzu_emu.utils.GameIconUtils\n',
    'import org.yuzu.yuzu_emu.utils.GameIconUtils\nimport org.yuzu.yuzu_emu.utils.GameFrontendAudio\n'
)
replace_once(
    games_path,
    '''    override fun onPause() {
        super.onPause()
        if (getCurrentViewType() == GameAdapter.VIEW_TYPE_CAROUSEL) {
''',
    '''    override fun onPause() {
        GameFrontendAudio.stop()
        super.onPause()
        if (getCurrentViewType() == GameAdapter.VIEW_TYPE_CAROUSEL) {
'''
)
replace_once(
    games_path,
    '''        if (games.isEmpty()) {
            highlightedGame = null
            heroTitle.setText(R.string.mw_home_frontend_empty_title)
''',
    '''        if (games.isEmpty()) {
            highlightedGame = null
            GameFrontendAudio.stop()
            heroTitle.setText(R.string.mw_home_frontend_empty_title)
'''
)
replace_once(
    games_path,
    '''        highlightedGame = game
        heroTitle.text = game.title.replace("[\\\\t\\\\n\\\\r]+".toRegex(), " ")
''',
    '''        highlightedGame = game
        GameFrontendAudio.play(requireContext(), game)
        heroTitle.text = game.title.replace("[\\\\t\\\\n\\\\r]+".toRegex(), " ")
'''
)
replace_once(
    games_path,
    '''    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }
''',
    '''    override fun onDestroyView() {
        GameFrontendAudio.stop()
        super.onDestroyView()
        _binding = null
    }
'''
)


# ---------------------------------------------------------------------------
# Game Hub: choose/remove a real per-game track and keep it playing in the hub.
# ---------------------------------------------------------------------------
props_path = 'src/android/app/src/main/java/org/yuzu/yuzu_emu/fragments/GamePropertiesFragment.kt'
replace_once(
    props_path,
    'import android.provider.DocumentsContract\n',
    'import android.provider.DocumentsContract\nimport android.provider.OpenableColumns\n'
)
replace_once(
    props_path,
    'import org.yuzu.yuzu_emu.utils.GameIconUtils\n',
    'import org.yuzu.yuzu_emu.utils.GameIconUtils\nimport org.yuzu.yuzu_emu.utils.GameFrontendAudio\n'
)
replace_once(
    props_path,
    '''        bindAction(R.id.customize_logo) { importLogoArtwork.launch(arrayOf("image/*")) }
        bindAction(R.id.customize_reset) { confirmResetArtwork() }
        showExpandedBottomSheet(dialog)
''',
    '''        bindAction(R.id.customize_logo) { importLogoArtwork.launch(arrayOf("image/*")) }
        bindAction(R.id.customize_music) { importMusic.launch(arrayOf("audio/*")) }
        sheet.findViewById<View>(R.id.customize_remove_music).apply {
            visibility = if (GameFrontendAudio.musicFile(args.game) != null) View.VISIBLE else View.GONE
            setOnClickListener {
                dialog.dismiss()
                removeGameMusic()
            }
        }
        bindAction(R.id.customize_reset) { confirmResetArtwork() }
        showExpandedBottomSheet(dialog)
'''
)
replace_once(
    props_path,
    '''    private fun readableLastPlayed(): String {
''',
    '''    private fun resolveMusicExtension(uri: Uri): String? {
        val resolver = requireContext().contentResolver
        val mimeExtension = when (resolver.getType(uri)?.lowercase()) {
            "audio/mpeg", "audio/mp3" -> "mp3"
            "audio/ogg", "application/ogg" -> "ogg"
            "audio/mp4", "audio/x-m4a", "audio/m4a" -> "m4a"
            "audio/wav", "audio/x-wav", "audio/wave" -> "wav"
            "audio/aac", "audio/aacp" -> "aac"
            "audio/flac", "audio/x-flac" -> "flac"
            else -> null
        }
        if (mimeExtension != null) return mimeExtension

        val displayName = runCatching {
            resolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
                if (!cursor.moveToFirst()) null
                else cursor.getString(cursor.getColumnIndexOrThrow(OpenableColumns.DISPLAY_NAME))
            }
        }.getOrNull()
        return displayName
            ?.substringAfterLast('.', "")
            ?.lowercase()
            ?.takeIf { it in GameFrontendAudio.supportedExtensions }
    }

    private fun importGameMusic(uri: Uri) {
        GameFrontendAudio.stop()
        viewLifecycleOwner.lifecycleScope.launch {
            val imported = withContext(Dispatchers.IO) {
                runCatching {
                    val extension = resolveMusicExtension(uri) ?: return@runCatching false
                    val directory = gameAssetDirectory().apply { mkdirs() }
                    GameFrontendAudio.deleteMusicFiles(args.game)
                    val target = File(directory, "music.$extension")
                    requireContext().contentResolver.openInputStream(uri)?.use { input ->
                        target.outputStream().use { output -> input.copyTo(output) }
                    } ?: return@runCatching false
                    target.isFile && target.length() > 0L
                }.getOrDefault(false)
            }

            if (_binding == null) return@launch
            if (imported) {
                GameFrontendAudio.play(requireContext(), args.game)
                Toast.makeText(requireContext(), R.string.mw_gamehub_music_updated, Toast.LENGTH_SHORT).show()
            } else {
                Toast.makeText(requireContext(), R.string.mw_gamehub_music_failed, Toast.LENGTH_SHORT).show()
            }
        }
    }

    private fun removeGameMusic() {
        GameFrontendAudio.stop()
        viewLifecycleOwner.lifecycleScope.launch {
            withContext(Dispatchers.IO) { GameFrontendAudio.deleteMusicFiles(args.game) }
            if (_binding == null) return@launch
            Toast.makeText(requireContext(), R.string.mw_gamehub_music_removed, Toast.LENGTH_SHORT).show()
        }
    }

    private fun readableLastPlayed(): String {
'''
)
replace_once(
    props_path,
    '''    override fun onResume() {
        super.onResume()
        refreshOverview()
        refreshFavoriteAction()
        reloadList()
    }
''',
    '''    override fun onResume() {
        super.onResume()
        refreshOverview()
        refreshFavoriteAction()
        reloadList()
        GameFrontendAudio.play(requireContext(), args.game)
    }

    override fun onPause() {
        GameFrontendAudio.stop()
        super.onPause()
    }
'''
)
replace_once(
    props_path,
    '''    private val importSaves =
''',
    '''    private val importMusic =
        registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
            if (uri != null) importGameMusic(uri)
        }

    private val importSaves =
'''
)


# ---------------------------------------------------------------------------
# Customize sheet UI
# ---------------------------------------------------------------------------
layout_path = 'src/android/app/src/main/res/layout/bottom_sheet_gamehub_customize.xml'
music_rows = '''    <LinearLayout
        android:id="@+id/customize_music"
        android:layout_width="match_parent"
        android:layout_height="72dp"
        android:background="?attr/selectableItemBackground"
        android:clickable="true"
        android:focusable="true"
        android:gravity="center_vertical"
        android:orientation="horizontal"
        android:paddingHorizontal="22dp">
        <ImageView android:layout_width="44dp" android:layout_height="44dp" android:background="@drawable/mw_gamehub_sheet_icon_bg" android:contentDescription="@null" android:padding="10dp" android:src="@drawable/ic_mw_music" app:tint="@color/mw_gamehub_v2_accent" />
        <LinearLayout android:layout_width="0dp" android:layout_height="wrap_content" android:layout_marginStart="14dp" android:layout_weight="1" android:orientation="vertical">
            <TextView android:layout_width="match_parent" android:layout_height="wrap_content" android:text="@string/mw_gamehub_music" android:textColor="@color/moonwitch_text" android:textSize="14sp" />
            <TextView android:layout_width="match_parent" android:layout_height="wrap_content" android:layout_marginTop="2dp" android:text="@string/mw_gamehub_music_desc" android:textColor="@color/moonwitch_text_muted" android:textSize="10sp" />
        </LinearLayout>
    </LinearLayout>

    <LinearLayout
        android:id="@+id/customize_remove_music"
        android:layout_width="match_parent"
        android:layout_height="72dp"
        android:background="?attr/selectableItemBackground"
        android:clickable="true"
        android:focusable="true"
        android:gravity="center_vertical"
        android:orientation="horizontal"
        android:paddingHorizontal="22dp"
        android:visibility="gone">
        <ImageView android:layout_width="44dp" android:layout_height="44dp" android:background="@drawable/mw_gamehub_sheet_icon_bg" android:contentDescription="@null" android:padding="10dp" android:src="@drawable/ic_delete" app:tint="@color/moonwitch_red" />
        <LinearLayout android:layout_width="0dp" android:layout_height="wrap_content" android:layout_marginStart="14dp" android:layout_weight="1" android:orientation="vertical">
            <TextView android:layout_width="match_parent" android:layout_height="wrap_content" android:text="@string/mw_gamehub_music_remove" android:textColor="@color/moonwitch_text" android:textSize="14sp" />
            <TextView android:layout_width="match_parent" android:layout_height="wrap_content" android:layout_marginTop="2dp" android:text="@string/mw_gamehub_music_remove_desc" android:textColor="@color/moonwitch_text_muted" android:textSize="10sp" />
        </LinearLayout>
    </LinearLayout>

'''
replace_once(
    layout_path,
    '    <View android:layout_width="match_parent" android:layout_height="1dp" android:layout_marginHorizontal="22dp" android:background="@color/moonwitch_border_soft" />\n',
    music_rows + '    <View android:layout_width="match_parent" android:layout_height="1dp" android:layout_marginHorizontal="22dp" android:background="@color/moonwitch_border_soft" />\n'
)


# ---------------------------------------------------------------------------
# New icon and localized resource bundle.
# ---------------------------------------------------------------------------
write_new(
    'src/android/app/src/main/res/drawable/ic_mw_music.xml',
    '''<?xml version="1.0" encoding="utf-8"?>
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="24dp"
    android:height="24dp"
    android:viewportWidth="24"
    android:viewportHeight="24">
    <path
        android:fillColor="#FFFFFFFF"
        android:pathData="M12,3V13.55C11.41,13.21 10.73,13 10,13C7.79,13 6,14.34 6,16C6,17.66 7.79,19 10,19C12.21,19 14,17.66 14,16V7H18V3H12Z" />
</vector>
'''
)

write_new(
    'src/android/app/src/main/res/values/moonwitch_frontend_music.xml',
    '''<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="mw_gamehub_music">Game music</string>
    <string name="mw_gamehub_music_desc">Play a custom track while this game is highlighted in the frontend</string>
    <string name="mw_gamehub_music_remove">Remove game music</string>
    <string name="mw_gamehub_music_remove_desc">Stop using the custom track for this game</string>
    <string name="mw_gamehub_music_updated">Game music updated</string>
    <string name="mw_gamehub_music_removed">Game music removed</string>
    <string name="mw_gamehub_music_failed">Could not import this audio file</string>
</resources>
'''
)

write_new(
    'src/android/app/src/main/res/values-pt-rBR/moonwitch_frontend_music.xml',
    '''<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="mw_gamehub_music">Música do jogo</string>
    <string name="mw_gamehub_music_desc">Toca uma faixa personalizada enquanto este jogo estiver em destaque no frontend</string>
    <string name="mw_gamehub_music_remove">Remover música do jogo</string>
    <string name="mw_gamehub_music_remove_desc">Deixa de usar a faixa personalizada deste jogo</string>
    <string name="mw_gamehub_music_updated">Música do jogo atualizada</string>
    <string name="mw_gamehub_music_removed">Música do jogo removida</string>
    <string name="mw_gamehub_music_failed">Não foi possível importar este arquivo de áudio</string>
</resources>
'''
)

print('Moonwitch per-game frontend music implementation applied.')
