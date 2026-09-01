// SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
// SPDX-License-Identifier: GPL-3.0-or-later

package org.yuzu.yuzu_emu.core

import android.content.Context
import android.net.Uri
import android.os.ParcelFileDescriptor
import android.system.Os
import android.view.Surface
import com.sun.jna.JNIEnv
import java.io.File
import java.util.TimeZone
import org.kenjinx.android.KenjinxNative
import org.kenjinx.android.NativeHelpers
import org.yuzu.yuzu_emu.features.settings.model.BooleanSetting
import org.yuzu.yuzu_emu.utils.DirectoryInitialization
import org.yuzu.yuzu_emu.utils.Log

/**
 * Minimal Moonwitch host for LibKenjinx/Ryujinx.
 *
 * Phase 1 deliberately focuses on a real graphics/game boot path. Input remapping, custom GPU
 * driver forwarding, applet UI and per-core advanced settings are layered on after this path is
 * proven on-device.
 */
object MoonwitchKenjiCore {
    private const val TAG = "[MoonwitchKenjiCore]"

    @Volatile
    var isRunning: Boolean = false
        private set

    @Volatile
    var isPaused: Boolean = false
        private set

    @Volatile
    private var inputPumpRunning = false

    private var initialized = false
    private var rendererInitialized = false
    private var gameDescriptor: ParcelFileDescriptor? = null
    private var nativeWindow: Long = -1L
    private var lastSurface: Surface? = null
    private var lastWidth = 1280
    private var lastHeight = 720
    private var inputThread: Thread? = null

    @Synchronized
    fun prepare(
        context: Context,
        gamePath: String,
        surface: Surface,
        width: Int = 1280,
        height: Int = 720
    ): Boolean {
        if (isRunning) {
            Log.warning("$TAG prepare called while already running")
            return false
        }

        return runCatching {
            val appContext = context.applicationContext
            val basePath = prepareDataDirectory(appContext)
            bindSurface(surface, width, height)

            if (!initialized) {
                Log.info("$TAG Initializing LibKenjinx at $basePath")
                if (!KenjinxNative.javaInitialize(basePath, JNIEnv.CURRENT)) {
                    error("LibKenjinx javaInitialize returned false")
                }
                initialized = true
            } else {
                KenjinxNative.deviceReinitEmulation()
            }

            if (!KenjinxNative.initializeGraphicsStable()) {
                error("LibKenjinx graphicsInitialize returned false")
            }

            val extensions = arrayOf("VK_KHR_surface", "VK_KHR_android_surface")
            if (!KenjinxNative.graphicsInitializeRenderer(extensions, extensions.size, 0L)) {
                error("LibKenjinx graphicsInitializeRenderer returned false")
            }
            rendererInitialized = true

            val docked = BooleanSetting.USE_DOCKED_MODE.getBoolean()
            val deviceReady = KenjinxNative.deviceInitialize(
                2, // HostMappedUnsafe - Kenji Android default
                false, // NCE stays off for the first compatibility boot
                0, // 4 GiB Switch memory configuration
                17, // BrazilianPortuguese
                1, // USA
                0, // Switch VSync
                docked,
                true, // PPTC
                false, // low-power PPTC
                true, // JIT cache eviction
                false, // guest internet access
                false, // FS integrity checks
                0,
                TimeZone.getDefault().id,
                false
            )
            if (!deviceReady) {
                error("LibKenjinx deviceInitialize returned false")
            }

            gameDescriptor = openGameDescriptor(appContext, gamePath)
                ?: error("Unable to open game descriptor: $gamePath")

            val gameType = resolveGameType(gamePath)
            if (gameType == 0) {
                error("Unsupported Kenji game type: $gamePath")
            }

            if (!KenjinxNative.deviceLoadDescriptor(gameDescriptor!!.fd, gameType, -1)) {
                error("LibKenjinx deviceLoadDescriptor returned false")
            }

            KenjinxNative.deviceSetWindowHandle(nativeWindow)
            KenjinxNative.graphicsRendererSetSize(lastWidth, lastHeight)
            KenjinxNative.inputInitialize(lastWidth, lastHeight)
            KenjinxNative.inputSetClientSize(lastWidth, lastHeight)
            KenjiInputBridge.connect()
            runCatching { KenjinxNative.graphicsSetPresentEnabled(true) }

            isPaused = false
            isRunning = true
            startInputPump()
            Log.info("$TAG Kenji core prepared successfully (${lastWidth}x$lastHeight)")
            true
        }.getOrElse { throwable ->
            Log.error("$TAG Failed to prepare Kenji core: ${throwable.message}")
            cleanupFailedStart()
            false
        }
    }

    fun runLoop() {
        if (!isRunning) return
        Log.info("$TAG Entering Ryujinx renderer run loop")
        try {
            KenjinxNative.graphicsRendererRunLoop()
        } catch (throwable: Throwable) {
            Log.error("$TAG Renderer run loop failed: ${throwable.message}")
        } finally {
            inputPumpRunning = false
            KenjiInputBridge.disconnect()
            isRunning = false
            isPaused = false
            closeDescriptor()
            Log.info("$TAG Ryujinx renderer run loop ended")
        }
    }

    @Synchronized
    fun updateSurface(surface: Surface, width: Int = 0, height: Int = 0) {
        if (width > 0) lastWidth = width
        if (height > 0) lastHeight = height
        bindSurface(surface, lastWidth, lastHeight)
        if (initialized) {
            runCatching { KenjinxNative.deviceSetWindowHandle(nativeWindow) }
            if (rendererInitialized) {
                runCatching { KenjinxNative.graphicsRendererSetSize(lastWidth, lastHeight) }
                runCatching { KenjinxNative.inputSetClientSize(lastWidth, lastHeight) }
            }
        }
    }

    @Synchronized
    fun pause() {
        if (!isRunning || isPaused) return
        runCatching { KenjinxNative.audioSetPaused(true) }
        runCatching { KenjinxNative.graphicsSetPresentEnabled(false) }
        isPaused = true
    }

    @Synchronized
    fun resume(surface: Surface?) {
        if (!isRunning || !isPaused) return
        if (surface != null && surface.isValid) {
            updateSurface(surface, lastWidth, lastHeight)
        }
        runCatching { KenjinxNative.graphicsSetPresentEnabled(true) }
        runCatching { KenjinxNative.audioSetPaused(false) }
        isPaused = false
    }

    @Synchronized
    fun detachSurface() {
        runCatching { KenjinxNative.graphicsSetPresentEnabled(false) }
        lastSurface = null
    }

    @Synchronized
    fun stop() {
        if (!initialized) {
            closeDescriptor()
            return
        }
        Log.info("$TAG Stopping Kenji core")
        inputPumpRunning = false
        KenjiInputBridge.disconnect()
        runCatching { KenjinxNative.graphicsSetPresentEnabled(false) }
        runCatching { KenjinxNative.deviceSignalEmulationClose() }
        runCatching { KenjinxNative.deviceCloseEmulation() }
        isRunning = false
        isPaused = false
        rendererInitialized = false
        closeDescriptor()
        releaseNativeWindow()
        inputThread = null
    }

    fun getPerfStats(): FloatArray = floatArrayOf(
        0f,
        runCatching { KenjinxNative.deviceGetGameFrameRate().toFloat() }.getOrDefault(0f),
        runCatching { KenjinxNative.deviceGetGameFrameTime().toFloat() / 1000f }.getOrDefault(0f)
    )

    private fun startInputPump() {
        inputPumpRunning = true
        inputThread = Thread({
            while (inputPumpRunning && isRunning) {
                runCatching { KenjinxNative.inputUpdate() }
                try {
                    Thread.sleep(1)
                } catch (_: InterruptedException) {
                    break
                }
            }
        }, "KenjiInputPump").also { it.start() }
    }

    private fun bindSurface(surface: Surface, width: Int, height: Int) {
        lastSurface = surface
        if (width > 0) lastWidth = width
        if (height > 0) lastHeight = height

        releaseNativeWindow()
        nativeWindow = NativeHelpers.instance.getNativeWindow(surface)
        if (nativeWindow <= 0L) {
            error("Unable to acquire ANativeWindow")
        }

        KenjinxNative.setNativeWindowProviders(
            surface = { nativeWindow },
            window = { nativeWindow }
        )
    }

    private fun releaseNativeWindow() {
        val window = nativeWindow
        nativeWindow = -1L
        if (window > 0L) {
            runCatching { NativeHelpers.instance.releaseNativeWindow(window) }
        }
        KenjinxNative.clearNativeWindowProviders()
    }

    private fun prepareDataDirectory(context: Context): String {
        if (!DirectoryInitialization.areDirectoriesReady) {
            DirectoryInitialization.start()
        }
        val moonwitchBase = File(
            DirectoryInitialization.userDirectory ?: context.getExternalFilesDir(null)!!.absolutePath
        )
        val kenjiBase = File(moonwitchBase, "kenji-core")
        val kenjiSystem = File(kenjiBase, "system")
        kenjiSystem.mkdirs()

        val moonwitchKeys = File(moonwitchBase, "keys")
        listOf("prod.keys", "title.keys", "console.keys").forEach { name ->
            val source = File(moonwitchKeys, name)
            val destination = File(kenjiSystem, name)
            if (source.isFile && (!destination.isFile || source.length() != destination.length())) {
                source.copyTo(destination, overwrite = true)
            }
        }

        // Ryujinx calls its NAND root "bis" while the Yuzu-derived core calls it "nand".
        // Re-use the existing firmware/NAND without duplicating hundreds of MB when the Android
        // filesystem supports symlinks. Failure is non-fatal and is logged for the first device test.
        val moonwitchNand = File(moonwitchBase, "nand")
        val kenjiBis = File(kenjiBase, "bis")
        if (moonwitchNand.isDirectory && !kenjiBis.exists()) {
            runCatching {
                Os.symlink(moonwitchNand.absolutePath, kenjiBis.absolutePath)
                Log.info("$TAG Reusing Moonwitch NAND through Kenji bis symlink")
            }.onFailure {
                Log.warning("$TAG NAND symlink unavailable; Kenji may require firmware import: ${it.message}")
            }
        }

        kenjiBase.mkdirs()
        return kenjiBase.absolutePath
    }

    private fun openGameDescriptor(context: Context, gamePath: String): ParcelFileDescriptor? {
        val uri = Uri.parse(gamePath)
        return if (!uri.scheme.isNullOrBlank()) {
            context.contentResolver.openFileDescriptor(uri, "rw")
        } else {
            val file = File(gamePath)
            if (file.isFile) {
                ParcelFileDescriptor.open(file, ParcelFileDescriptor.MODE_READ_WRITE)
            } else {
                null
            }
        }
    }

    private fun resolveGameType(gamePath: String): Int {
        val uri = Uri.parse(gamePath)
        val candidate = (uri.lastPathSegment ?: gamePath).substringBefore('?')
        return when (candidate.substringAfterLast('.', "").lowercase()) {
            "nsp" -> 1
            "xci" -> 2
            "nro" -> 3
            else -> 0
        }
    }

    private fun cleanupFailedStart() {
        inputPumpRunning = false
        KenjiInputBridge.disconnect()
        isRunning = false
        isPaused = false
        rendererInitialized = false
        closeDescriptor()
        runCatching { KenjinxNative.deviceCloseEmulation() }
        releaseNativeWindow()
        inputThread = null
    }

    private fun closeDescriptor() {
        runCatching { gameDescriptor?.close() }
        gameDescriptor = null
    }
}
