#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Expected fragment not found ({label}): {old!r}")
    return text.replace(old, new, 1)


# Normalize the CI-only EmulationFragment routing patch.
fragment_path = Path(
    "src/android/app/src/main/java/org/yuzu/yuzu_emu/fragments/EmulationFragment.kt"
)
fragment = fragment_path.read_text(encoding="utf-8")

fragment_replacements = [
    (
        "    private inner class EmulationState(\n",
        "    private class EmulationState(\n",
        "restore non-inner EmulationState",
    ),
    (
        "                if (usesKenji) emulationViewModel.setEmulationStopped(true)\n",
        "",
        "remove outer ViewModel stop callback",
    ),
    (
        "                                    requireContext().applicationContext,\n",
        "                                    org.yuzu.yuzu_emu.YuzuApplication.appContext,\n",
        "use application context",
    ),
    (
        "                                    emulationViewModel.setEmulationStarted(true)\n",
        "",
        "remove outer ViewModel start callback",
    ),
    (
        "                                emulationViewModel.setEmulationStarted(false)\n",
        "",
        "remove outer ViewModel started=false callback",
    ),
    (
        "                                emulationViewModel.setEmulationStopped(true)\n",
        "",
        "remove outer ViewModel stopped callback",
    ),
]

for old, new, label in fragment_replacements:
    fragment = replace_once(fragment, old, new, label)

fragment_path.write_text(fragment, encoding="utf-8")


# Runtime stabilization for the Kenji host.
# Keep heavy preparation on KenjiEmulation, but mirror upstream Kenji's hard
# requirement that deviceInitialize() executes on Android's main/UI thread.
# Also persist a tiny stage breadcrumb so a native process death can be located
# on the next launch even without an in-app log viewer.
core_path = Path(
    "src/android/app/src/main/java/org/yuzu/yuzu_emu/core/MoonwitchKenjiCore.kt"
)
core = core_path.read_text(encoding="utf-8")

core = replace_once(
    core,
    "    private var inputThread: Thread? = null\n\n    @Synchronized\n",
    "    private var inputThread: Thread? = null\n"
    "    private var bootTraceFile: File? = null\n\n"
    "    @Synchronized\n",
    "add boot trace state",
)

core = replace_once(
    core,
    "            val appContext = context.applicationContext\n"
    "            val basePath = prepareDataDirectory(appContext)\n"
    "            bindSurface(surface, width, height)\n",
    "            val appContext = context.applicationContext\n"
    "            val basePath = prepareDataDirectory(appContext)\n"
    "            bootTraceFile = File(basePath, \"last-boot-stage.txt\")\n"
    "            reportPreviousIncompleteBoot(appContext)\n"
    "            markBootStage(\"01-bind-surface\")\n"
    "            bindSurface(surface, width, height)\n",
    "initialize boot trace",
)

core = replace_once(
    core,
    "            if (!initialized) {\n"
    "                Log.info(\"$TAG Initializing LibKenjinx at $basePath\")\n"
    "                if (!KenjinxNative.javaInitialize(basePath, JNIEnv.CURRENT)) {\n",
    "            if (!initialized) {\n"
    "                Log.info(\"$TAG Initializing LibKenjinx at $basePath\")\n"
    "                markBootStage(\"02-java-initialize\")\n"
    "                if (!KenjinxNative.javaInitialize(basePath, JNIEnv.CURRENT)) {\n",
    "trace javaInitialize",
)

core = replace_once(
    core,
    "                initialized = true\n"
    "            } else {\n"
    "                KenjinxNative.deviceReinitEmulation()\n"
    "            }\n\n"
    "            if (!KenjinxNative.initializeGraphicsStable()) {\n",
    "                initialized = true\n"
    "            } else {\n"
    "                markBootStage(\"02-device-reinit\")\n"
    "                KenjinxNative.deviceReinitEmulation()\n"
    "            }\n\n"
    "            markBootStage(\"03-graphics-initialize\")\n"
    "            if (!KenjinxNative.initializeGraphicsStable()) {\n",
    "trace reinit and graphics init",
)

core = replace_once(
    core,
    "            val extensions = arrayOf(\"VK_KHR_surface\", \"VK_KHR_android_surface\")\n"
    "            if (!KenjinxNative.graphicsInitializeRenderer(extensions, extensions.size, 0L)) {\n",
    "            val extensions = arrayOf(\"VK_KHR_surface\", \"VK_KHR_android_surface\")\n"
    "            markBootStage(\"04-renderer-initialize\")\n"
    "            if (!KenjinxNative.graphicsInitializeRenderer(extensions, extensions.size, 0L)) {\n",
    "trace renderer init",
)

old_device_init = '''            val docked = BooleanSetting.USE_DOCKED_MODE.getBoolean()
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
'''

new_device_init = '''            val docked = BooleanSetting.USE_DOCKED_MODE.getBoolean()
            markBootStage("05-device-initialize-main-thread")
            val initializeDevice = {
                KenjinxNative.deviceInitialize(
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
            }
            val deviceReady = if (
                android.os.Looper.myLooper() == android.os.Looper.getMainLooper()
            ) {
                initializeDevice()
            } else {
                val task = java.util.concurrent.FutureTask<Boolean> { initializeDevice() }
                android.os.Handler(android.os.Looper.getMainLooper()).post(task)
                task.get()
            }
'''
core = replace_once(core, old_device_init, new_device_init, "main-thread deviceInitialize")

core = replace_once(
    core,
    "            gameDescriptor = openGameDescriptor(appContext, gamePath)\n",
    "            markBootStage(\"06-open-game-descriptor\")\n"
    "            gameDescriptor = openGameDescriptor(appContext, gamePath)\n",
    "trace descriptor open",
)

core = replace_once(
    core,
    "            if (!KenjinxNative.deviceLoadDescriptor(gameDescriptor!!.fd, gameType, -1)) {\n",
    "            markBootStage(\"07-load-game-descriptor\")\n"
    "            if (!KenjinxNative.deviceLoadDescriptor(gameDescriptor!!.fd, gameType, -1)) {\n",
    "trace descriptor load",
)

core = replace_once(
    core,
    "            isPaused = false\n"
    "            isRunning = true\n"
    "            startInputPump()\n"
    "            Log.info(\"$TAG Kenji core prepared successfully (${lastWidth}x$lastHeight)\")\n",
    "            isPaused = false\n"
    "            isRunning = true\n"
    "            startInputPump()\n"
    "            markBootStage(\"READY\")\n"
    "            Log.info(\"$TAG Kenji core prepared successfully (${lastWidth}x$lastHeight)\")\n",
    "mark ready",
)

breadcrumb_helpers = '''    private fun markBootStage(stage: String) {
        runCatching { bootTraceFile?.writeText(stage) }
        Log.info("$TAG Boot stage: $stage")
    }

    private fun reportPreviousIncompleteBoot(context: Context) {
        val previous = runCatching {
            bootTraceFile?.takeIf { it.isFile }?.readText()?.trim()
        }.getOrNull()

        if (previous.isNullOrBlank() || previous == "READY") {
            return
        }

        Log.warning("$TAG Previous Kenji process ended during stage: $previous")
        android.os.Handler(android.os.Looper.getMainLooper()).post {
            android.widget.Toast.makeText(
                context,
                "Kenji anterior parou em: $previous",
                android.widget.Toast.LENGTH_LONG
            ).show()
        }
    }

'''
core = replace_once(
    core,
    "    private fun startInputPump() {\n",
    breadcrumb_helpers + "    private fun startInputPump() {\n",
    "add breadcrumb helpers",
)

core_path.write_text(core, encoding="utf-8")
print("Kenji first-boot host normalized and runtime stabilization applied.")
