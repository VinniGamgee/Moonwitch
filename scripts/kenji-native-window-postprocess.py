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

# #20 proved that libkenjinxjni itself can load, while the durable breadcrumb
# consistently reaches 01d-get-native-window before the app enters ANR. Do not
# bounce ANativeWindow_fromSurface back onto Android's UI Looper. JNI external
# calls already receive a valid JNIEnv for the calling thread, and the NDK
# ANativeWindow API does not require the Java main thread.
#
# Run acquisition on an isolated worker with a hard timeout. If a vendor/Surface
# implementation ever blocks, Moonwitch fails this boot without freezing the UI
# and leaves a precise persistent breadcrumb for the next launch.
old_acquire = '''        markBootStage("01c-load-kenjinxjni")
        val helpers = callOnMainThread("01c-load-kenjinxjni") { NativeHelpers.instance }

        markBootStage("01d-get-native-window")
        nativeWindow = callOnMainThread("01d-get-native-window") { helpers.getNativeWindow(surface) }
        if (nativeWindow <= 0L) {
            error("Unable to acquire ANativeWindow")
        }
        markBootStage("01e-native-window-ready")
'''

new_acquire = '''        markBootStage("01c-load-kenjinxjni")
        val helpers = NativeHelpers.instance
        markBootStage("01c2-kenjinxjni-ready")

        markBootStage("01d-get-native-window")
        nativeWindow = acquireNativeWindowWithTimeout(helpers, surface)
        if (nativeWindow <= 0L) {
            error("Unable to acquire ANativeWindow")
        }
        markBootStage("01e-native-window-ready")
'''
text = replace_once(text, old_acquire, new_acquire, "move ANativeWindow acquisition off UI thread")

# Insert the bounded worker helper immediately before installNativeWindowProviders.
needle = '''    private fun installNativeWindowProviders() {
'''
helper = '''    private fun acquireNativeWindowWithTimeout(
        helpers: NativeHelpers,
        surface: Surface
    ): Long {
        val task = java.util.concurrent.FutureTask<Long> {
            markBootStage("01d1-native-window-worker-enter")
            val window = helpers.getNativeWindow(surface)
            markBootStage("01d2-native-window-worker-return")
            window
        }
        val worker = Thread(task, "KenjiNativeWindowAcquire").apply {
            isDaemon = true
            start()
        }

        return try {
            task.get(5, java.util.concurrent.TimeUnit.SECONDS)
        } catch (_: java.util.concurrent.TimeoutException) {
            markBootStage("01d-timeout-after-5s")
            worker.interrupt()
            error("Timed out acquiring ANativeWindow")
        }
    }

    private fun installNativeWindowProviders() {
'''
text = replace_once(text, needle, helper, "add bounded ANativeWindow worker")

# A failure before javaInitialize must not touch the NativeAOT/JNA core from the
# cleanup path; doing so would reintroduce an early libkenjinx load while we are
# specifically diagnosing the Android window layer.
text = replace_once(
    text,
    '''        runCatching { KenjinxNative.deviceCloseEmulation() }
        releaseNativeWindow()
''',
    '''        if (initialized) {
            runCatching { KenjinxNative.deviceCloseEmulation() }
        }
        releaseNativeWindow(clearProviders = initialized)
''',
    "avoid JNA cleanup before javaInitialize",
)

path.write_text(text, encoding="utf-8")
print("Kenji ANativeWindow acquisition moved off the UI thread with a 5s timeout.")
