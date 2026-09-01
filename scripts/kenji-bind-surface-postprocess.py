#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Expected fragment not found ({label}): {old!r}")
    return text.replace(old, new, 1)


path = Path(
    "src/android/app/src/main/java/org/yuzu/yuzu_emu/core/MoonwitchKenjiCore.kt"
)
text = path.read_text(encoding="utf-8")

# The first-boot host used to touch KenjinxNative from bindSurface() through
# clear/setNativeWindowProviders(). Because KenjinxNative delegates to a lazy JNA
# instance, merely touching that object can load libkenjinx.so before
# javaInitialize(). Keep ANativeWindow acquisition isolated to libkenjinxjni and
# only touch the NativeAOT/JNA bridge after javaInitialize starts explicitly.
text = replace_once(
    text,
    '''                initialized = true
            } else {
                markBootStage("02-device-reinit")
                KenjinxNative.deviceReinitEmulation()
            }

            markBootStage("03-graphics-initialize")
''',
    '''                initialized = true
            } else {
                markBootStage("02-device-reinit")
                KenjinxNative.deviceReinitEmulation()
            }

            markBootStage("02b-install-native-window-providers")
            installNativeWindowProviders()
            markBootStage("03-graphics-initialize")
''',
    "install providers after explicit LibKenjinx init",
)

text = replace_once(
    text,
    '''        bindSurface(surface, lastWidth, lastHeight)
        if (initialized) {
            runCatching { KenjinxNative.deviceSetWindowHandle(nativeWindow) }
''',
    '''        bindSurface(surface, lastWidth, lastHeight)
        if (initialized) {
            installNativeWindowProviders()
            runCatching { KenjinxNative.deviceSetWindowHandle(nativeWindow) }
''',
    "restore providers after surface rebind",
)

old_binding = '''    private fun bindSurface(surface: Surface, width: Int, height: Int) {
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
'''

new_binding = '''    private fun bindSurface(surface: Surface, width: Int, height: Int) {
        lastSurface = surface
        if (width > 0) lastWidth = width
        if (height > 0) lastHeight = height

        markBootStage("01a-validate-surface")
        if (!surface.isValid) {
            error("Android Surface is not valid")
        }

        markBootStage("01b-release-old-native-window")
        // On the first boot do not touch KenjinxNative here: that would load
        // libkenjinx.so via JNA before javaInitialize().
        releaseNativeWindow(clearProviders = false)

        markBootStage("01c-load-kenjinxjni")
        val helpers = callOnMainThread { NativeHelpers.instance }

        markBootStage("01d-get-native-window")
        nativeWindow = callOnMainThread { helpers.getNativeWindow(surface) }
        if (nativeWindow <= 0L) {
            error("Unable to acquire ANativeWindow")
        }
        markBootStage("01e-native-window-ready")
    }

    private fun installNativeWindowProviders() {
        KenjinxNative.setNativeWindowProviders(
            surface = { nativeWindow },
            window = { nativeWindow }
        )
    }

    private fun releaseNativeWindow(clearProviders: Boolean = initialized) {
        val window = nativeWindow
        nativeWindow = -1L
        if (window > 0L) {
            runCatching { NativeHelpers.instance.releaseNativeWindow(window) }
        }
        if (clearProviders) {
            runCatching { KenjinxNative.clearNativeWindowProviders() }
        }
    }

    private fun <T> callOnMainThread(block: () -> T): T {
        if (android.os.Looper.myLooper() == android.os.Looper.getMainLooper()) {
            return block()
        }

        val task = java.util.concurrent.FutureTask<T> { block() }
        android.os.Handler(android.os.Looper.getMainLooper()).post(task)
        return task.get()
    }
'''

text = replace_once(text, old_binding, new_binding, "split Surface/JNA boot stages")

path.write_text(text, encoding="utf-8")
print("Kenji native-window binding isolated from premature JNA loading.")
