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

# #20 proved that libkenjinxjni itself can load. #21 then proved that
# ANativeWindow_fromSurface() returns successfully on the isolated worker, but
# the durable breadcrumb stopped at the worker-return point. Remove FutureTask
# from this path completely and use a CountDownLatch + atomics so there is no
# FutureTask state transition between the native return and the caller.
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
        markBootStage("01d4-native-window-assigned")
        if (nativeWindow <= 0L) {
            error("Unable to acquire ANativeWindow")
        }
        markBootStage("01e-native-window-ready")
'''
text = replace_once(text, old_acquire, new_acquire, "move ANativeWindow acquisition off UI thread")

# Insert the bounded worker helper immediately before installNativeWindowProviders.
# All durable breadcrumbs are written by the caller thread, not by the worker,
# so their ordering cannot regress due to two concurrent SharedPreferences commits.
needle = '''    private fun installNativeWindowProviders() {
'''
helper = '''    private fun acquireNativeWindowWithTimeout(
        helpers: NativeHelpers,
        surface: Surface
    ): Long {
        val result = java.util.concurrent.atomic.AtomicLong(-1L)
        val failure = java.util.concurrent.atomic.AtomicReference<Throwable?>(null)
        val completed = java.util.concurrent.CountDownLatch(1)

        markBootStage("01d1-native-window-worker-start")
        val worker = Thread({
            try {
                result.set(helpers.getNativeWindow(surface))
            } catch (throwable: Throwable) {
                failure.set(throwable)
            } finally {
                completed.countDown()
            }
        }, "KenjiNativeWindowAcquire").apply {
            isDaemon = true
            start()
        }

        val finished = try {
            completed.await(5, java.util.concurrent.TimeUnit.SECONDS)
        } catch (_: InterruptedException) {
            Thread.currentThread().interrupt()
            false
        }

        if (!finished) {
            val returnedWindow = result.get()
            markBootStage(
                if (returnedWindow > 0L) {
                    "01d-timeout-after-native-return"
                } else {
                    "01d-timeout-inside-native-window"
                }
            )
            worker.interrupt()
            error("Timed out acquiring ANativeWindow")
        }

        markBootStage("01d2-native-window-worker-finished")
        failure.get()?.let { throw it }
        val window = result.get()
        markBootStage("01d3-native-window-result-read")
        return window
    }

    private fun installNativeWindowProviders() {
'''
text = replace_once(text, needle, helper, "add latch-based ANativeWindow worker")

# EmulationFragment marks its state RUNNING immediately after starting the Kenji
# thread, while MoonwitchKenjiCore.isRunning is only true after prepare succeeds.
# A second Surface callback in that gap must not start a second bind concurrently
# with first boot. Keep the newest Surface and let prepare rebind it later.
text = replace_once(
    text,
    '''        if (isPreparing) {
            pendingSurface = surface
            Log.debug("$TAG Surface update deferred while Kenji is preparing")
            return
        }
        bindSurface(surface, lastWidth, lastHeight)
''',
    '''        if ((!isRunning && !initialized) || isPreparing) {
            pendingSurface = surface
            Log.debug("$TAG Surface update deferred until Kenji first boot is ready")
            return
        }
        bindSurface(surface, lastWidth, lastHeight)
''',
    "prevent concurrent first-boot Surface bind",
)

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
print("Kenji ANativeWindow path now uses latch/atomics and serializes first-boot Surface binding.")
