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

# prepare() used to hold MoonwitchKenjiCore's object monitor for the entire
# NativeAOT/Ryujinx initialization. Android Surface callbacks run on the UI
# thread and call other @Synchronized methods on the same object, which can
# block the UI behind a long-running prepare and trigger an ANR. Keep only a
# tiny state guard and never hold the monitor across native initialization.
text = replace_once(
    text,
    "    private var bootTraceFile: File? = null\n\n    @Synchronized\n    fun prepare(\n",
    "    private var bootTraceFile: File? = null\n"
    "    @Volatile private var isPreparing = false\n"
    "    @Volatile private var pendingSurface: Surface? = null\n\n"
    "    fun prepare(\n",
    "remove long prepare monitor and add preparing state",
)

text = replace_once(
    text,
    '''    ): Boolean {
        if (isRunning) {
            Log.warning("$TAG prepare called while already running")
            return false
        }

        return runCatching {
''',
    '''    ): Boolean {
        synchronized(this) {
            if (isRunning || isPreparing) {
                Log.warning("$TAG prepare called while running/preparing")
                return false
            }
            isPreparing = true
            pendingSurface = null
        }

        return try {
            runCatching {
''',
    "short prepare state guard",
)

text = replace_once(
    text,
    '''            true
        }.getOrElse { throwable ->
            Log.error("$TAG Failed to prepare Kenji core: ${throwable.message}")
            cleanupFailedStart()
            false
        }
    }

    fun runLoop() {
''',
    '''            true
            }.getOrElse { throwable ->
                Log.error("$TAG Failed to prepare Kenji core: ${throwable.message}")
                cleanupFailedStart()
                false
            }
        } finally {
            isPreparing = false
        }
    }

    fun runLoop() {
''',
    "release prepare state in finally",
)

# Match upstream Kenji: javaInitialize receives JNIEnv.CURRENT on the Android
# main thread. The JNIEnv value itself is thread-local, even though LibKenjinx
# subsequently stores the JavaVM and can attach worker threads safely.
text = replace_once(
    text,
    '''                markBootStage("02-java-initialize")
                if (!KenjinxNative.javaInitialize(basePath, JNIEnv.CURRENT)) {
                    error("LibKenjinx javaInitialize returned false")
                }
''',
    '''                markBootStage("02-java-initialize-main-thread")
                val javaReady = callOnMainThread("02-java-initialize-main-thread") {
                    KenjinxNative.javaInitialize(basePath, JNIEnv.CURRENT)
                }
                if (!javaReady) {
                    error("LibKenjinx javaInitialize returned false")
                }
''',
    "initialize LibKenjinx with main-thread JNIEnv",
)

# Do not let Surface lifecycle callbacks compete with a boot in progress. They
# only record the newest Surface and return immediately, keeping Android's main
# thread responsive. The deferred Surface is rebound after device loading.
text = replace_once(
    text,
    '''    fun updateSurface(surface: Surface, width: Int = 0, height: Int = 0) {
        if (width > 0) lastWidth = width
        if (height > 0) lastHeight = height
        bindSurface(surface, lastWidth, lastHeight)
''',
    '''    fun updateSurface(surface: Surface, width: Int = 0, height: Int = 0) {
        if (width > 0) lastWidth = width
        if (height > 0) lastHeight = height
        if (isPreparing) {
            pendingSurface = surface
            Log.debug("$TAG Surface update deferred while Kenji is preparing")
            return
        }
        bindSurface(surface, lastWidth, lastHeight)
''',
    "defer Surface rebind during prepare",
)

text = replace_once(
    text,
    '''            KenjinxNative.inputInitialize(lastWidth, lastHeight)
            KenjinxNative.inputSetClientSize(lastWidth, lastHeight)
            KenjiInputBridge.connect()
''',
    '''            pendingSurface?.takeIf { it.isValid }?.let { deferred ->
                markBootStage("07b-bind-deferred-surface")
                bindSurface(deferred, lastWidth, lastHeight)
                installNativeWindowProviders()
                KenjinxNative.deviceSetWindowHandle(nativeWindow)
                pendingSurface = null
            }

            KenjinxNative.inputInitialize(lastWidth, lastHeight)
            KenjinxNative.inputSetClientSize(lastWidth, lastHeight)
            KenjiInputBridge.connect()
''',
    "rebind deferred Surface before input/run loop",
)

# Use the same main-thread helper for deviceInitialize and add a watchdog. The
# watchdog writes a persistent breadcrumb from a worker thread if Android's
# main thread spends >4s inside a native stage, so the next launch can report
# the exact blocking call even after an ANR/force-stop.
old_device_dispatch = '''            val deviceReady = if (
                android.os.Looper.myLooper() == android.os.Looper.getMainLooper()
            ) {
                initializeDevice()
            } else {
                val task = java.util.concurrent.FutureTask<Boolean> { initializeDevice() }
                android.os.Handler(android.os.Looper.getMainLooper()).post(task)
                task.get()
            }
'''
new_device_dispatch = '''            val deviceReady = callOnMainThread("05-device-initialize-main-thread") {
                initializeDevice()
            }
'''
text = replace_once(text, old_device_dispatch, new_device_dispatch, "watch deviceInitialize")

text = replace_once(
    text,
    '''        val helpers = callOnMainThread { NativeHelpers.instance }

        markBootStage("01d-get-native-window")
        nativeWindow = callOnMainThread { helpers.getNativeWindow(surface) }
''',
    '''        val helpers = callOnMainThread("01c-load-kenjinxjni") { NativeHelpers.instance }

        markBootStage("01d-get-native-window")
        nativeWindow = callOnMainThread("01d-get-native-window") { helpers.getNativeWindow(surface) }
''',
    "label native-window main-thread calls",
)

old_helper = '''    private fun <T> callOnMainThread(block: () -> T): T {
        if (android.os.Looper.myLooper() == android.os.Looper.getMainLooper()) {
            return block()
        }

        val task = java.util.concurrent.FutureTask<T> { block() }
        android.os.Handler(android.os.Looper.getMainLooper()).post(task)
        return task.get()
    }
'''

new_helper = '''    private fun <T> callOnMainThread(stage: String, block: () -> T): T {
        val completed = java.util.concurrent.atomic.AtomicBoolean(false)
        Thread({
            try {
                Thread.sleep(4000)
                if (!completed.get()) {
                    markBootStage("$stage-blocked-over-4s")
                }
            } catch (_: InterruptedException) {
            }
        }, "KenjiMainThreadWatchdog").apply {
            isDaemon = true
            start()
        }

        if (android.os.Looper.myLooper() == android.os.Looper.getMainLooper()) {
            return try {
                block()
            } finally {
                completed.set(true)
            }
        }

        val task = java.util.concurrent.FutureTask<T> {
            try {
                block()
            } finally {
                completed.set(true)
            }
        }
        android.os.Handler(android.os.Looper.getMainLooper()).post(task)
        return task.get()
    }
'''
text = replace_once(text, old_helper, new_helper, "add main-thread watchdog")

path.write_text(text, encoding="utf-8")
print("Kenji first-boot ANR lock inversion removed and watchdog enabled.")
