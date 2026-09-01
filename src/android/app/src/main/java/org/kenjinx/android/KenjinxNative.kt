// SPDX-FileCopyrightText: Copyright Kenji-NX Team and Contributors
// SPDX-License-Identifier: MIT

package org.kenjinx.android

import android.os.Build
import android.util.Log
import com.sun.jna.JNIEnv
import com.sun.jna.Library
import com.sun.jna.Native
import java.util.Collections

/** NativeAOT API exported by libkenjinx.so. */
interface KenjinxNativeJna : Library {
    fun javaInitialize(appPath: String, env: JNIEnv): Boolean
    fun deviceReinitEmulation()
    fun deviceCloseEmulation()
    fun deviceSignalEmulationClose()

    fun graphicsInitialize(
        rescale: Float,
        maxAnisotropy: Float,
        fastGpuTime: Boolean,
        fast2DCopy: Boolean,
        enableMacroJit: Boolean,
        enableMacroHLE: Boolean,
        enableShaderCache: Boolean,
        enableTextureRecompression: Boolean,
        backendThreading: Int
    ): Boolean

    fun graphicsInitializeRenderer(
        extensions: Array<String>,
        extensionsLength: Int,
        driver: Long
    ): Boolean

    fun deviceInitialize(
        memoryManagerMode: Int,
        useNce: Boolean,
        memoryConfiguration: Int,
        systemLanguage: Int,
        regionCode: Int,
        vSyncMode: Int,
        enableDockedMode: Boolean,
        enablePptc: Boolean,
        enableLowPowerPptc: Boolean,
        enableJitCacheEviction: Boolean,
        enableInternetAccess: Boolean,
        enableFsIntegrityChecks: Boolean,
        fsGlobalAccessLogMode: Int,
        timeZone: String,
        ignoreMissingServices: Boolean
    ): Boolean

    fun deviceLoadDescriptor(fileDescriptor: Int, gameType: Int, updateDescriptor: Int): Boolean
    fun deviceReloadFilesystem()
    fun deviceSetWindowHandle(handle: Long)
    fun graphicsRendererSetSize(width: Int, height: Int)
    fun graphicsRendererRunLoop()
    fun graphicsSetPresentEnabled(enabled: Boolean)

    fun inputInitialize(width: Int, height: Int)
    fun inputSetClientSize(width: Int, height: Int)
    fun inputUpdate()
    fun inputConnectGamepad(index: Int): Int
    fun inputSetButtonPressed(button: Int, id: Int)
    fun inputSetButtonReleased(button: Int, id: Int)
    fun inputSetStickAxis(stick: Int, x: Float, y: Float, id: Int)
    fun inputSetTouchPoint(x: Int, y: Int)
    fun inputReleaseTouchPoint()

    fun audioSetPaused(paused: Boolean)
    fun deviceGetGameFrameRate(): Double
    fun deviceGetGameFrameTime(): Double
    fun deviceGetGameFifo(): Double
}

private val jnaInstance: KenjinxNativeJna by lazy {
    Native.load(
        "kenjinx",
        KenjinxNativeJna::class.java,
        Collections.singletonMap(Library.OPTION_ALLOW_OBJECTS, true)
    )
}

/**
 * Compatibility class consumed from both directions:
 * - Moonwitch calls the NativeAOT exports through JNA.
 * - LibKenjinx calls the @JvmStatic callbacks below through JNI.
 */
object KenjinxNative : KenjinxNativeJna by jnaInstance {
    private const val THREADING_AUTO = 0
    private const val THREADING_SINGLE = 1

    @Volatile
    private var surfaceProvider: () -> Long = { -1L }

    @Volatile
    private var windowProvider: () -> Long = { -1L }

    fun setNativeWindowProviders(surface: () -> Long, window: () -> Long) {
        surfaceProvider = surface
        windowProvider = window
    }

    fun clearNativeWindowProviders() {
        surfaceProvider = { -1L }
        windowProvider = { -1L }
    }

    fun initializeGraphicsStable(
        rescale: Float = 1.0f,
        maxAnisotropy: Float = 0.0f,
        enableShaderCache: Boolean = true,
        enableTextureRecompression: Boolean = false,
        enableMacroHle: Boolean = true
    ): Boolean {
        val requested = THREADING_AUTO
        val firstChoice = if ("qcom".equals(Build.HARDWARE, true)) THREADING_SINGLE else requested

        return runCatching {
            graphicsInitialize(
                rescale,
                maxAnisotropy,
                true,
                true,
                false,
                enableMacroHle,
                enableShaderCache,
                enableTextureRecompression,
                firstChoice
            )
        }.getOrElse { firstError ->
            Log.w("MoonwitchKenji", "Initial graphics init failed; retrying single-threaded", firstError)
            runCatching {
                graphicsInitialize(
                    rescale,
                    maxAnisotropy,
                    true,
                    true,
                    false,
                    enableMacroHle,
                    enableShaderCache,
                    enableTextureRecompression,
                    THREADING_SINGLE
                )
            }.getOrDefault(false)
        }
    }

    @JvmStatic
    fun test() = Unit

    @JvmStatic
    fun frameEnded() = Unit

    @JvmStatic
    fun getSurfacePtr(): Long = surfaceProvider()

    @JvmStatic
    fun getWindowHandle(): Long = windowProvider()

    @JvmStatic
    fun updateProgress(infoPtr: Long, progress: Float) {
        val message = runCatching { NativeHelpers.instance.getStringJava(infoPtr) }.getOrNull()
        if (!message.isNullOrBlank()) {
            Log.d("MoonwitchKenji", "Loading: $message (${(progress * 100f).toInt()}%)")
        }
    }

    @JvmStatic
    @Suppress("UNUSED_PARAMETER")
    fun updateUiHandler(
        newTitlePointer: Long,
        newMessagePointer: Long,
        newWatermarkPointer: Long,
        newType: Int,
        min: Int,
        max: Int,
        nMode: Int,
        newSubtitlePointer: Long,
        newInitialTextPointer: Long
    ) {
        // Software-keyboard UI will be wired to Moonwitch after the first core boot is proven.
        Log.d("MoonwitchKenji", "Kenji requested an applet UI (type=$newType)")
    }
}
