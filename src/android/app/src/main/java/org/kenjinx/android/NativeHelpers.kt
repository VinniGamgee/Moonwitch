// SPDX-FileCopyrightText: Copyright Kenji-NX Team and Contributors
// SPDX-License-Identifier: MIT

package org.kenjinx.android

import android.view.Surface

/**
 * JNI compatibility shim required by libkenjinxjni.so.
 * The package/class/method names intentionally match Kenji-NX's Android ABI.
 */
class NativeHelpers {
    companion object {
        val instance = NativeHelpers()

        init {
            System.loadLibrary("kenjinxjni")
        }
    }

    external fun releaseNativeWindow(window: Long)
    external fun getCreateSurfacePtr(): Long
    external fun getNativeWindow(surface: Surface): Long

    external fun loadDriver(
        nativeLibPath: String,
        privateAppsPath: String,
        driverName: String
    ): Long

    external fun setTurboMode(enable: Boolean)
    external fun getMaxSwapInterval(nativeWindow: Long): Int
    external fun getMinSwapInterval(nativeWindow: Long): Int
    external fun setSwapInterval(nativeWindow: Long, swapInterval: Int): Int
    external fun getStringJava(ptr: Long): String
    external fun setIsInitialOrientationFlipped(isFlipped: Boolean)
}
