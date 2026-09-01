#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Expected fragment not found ({label}): {old!r}")
    return text.replace(old, new, 1)


# Persist the boot stage in a tiny internal file. Do not use SharedPreferences.commit()
# on every stage: #22 reached 01d4, and there is no native work between 01d4 and 01e,
# making synchronous preferences I/O itself a possible blocker in the hot boot path.
core_path = Path(
    "src/android/app/src/main/java/org/yuzu/yuzu_emu/core/MoonwitchKenjiCore.kt"
)
core = core_path.read_text(encoding="utf-8")
core = replace_once(
    core,
    '''    private fun markBootStage(stage: String) {
        runCatching { bootTraceFile?.writeText(stage) }
        Log.info("$TAG Boot stage: $stage")
    }
''',
    '''    private fun markBootStage(stage: String) {
        // Keep the Kenji-local trace for low-level recovery/debugging.
        runCatching { bootTraceFile?.writeText(stage) }

        // Also mirror to app-internal storage so Application.onCreate() can read it
        // without waiting for DirectoryInitialization or touching SharedPreferences.
        runCatching {
            java.io.File(
                org.yuzu.yuzu_emu.YuzuApplication.appContext.filesDir,
                "kenji-last-stage.txt"
            ).writeText(stage)
        }

        Log.info("$TAG Boot stage: $stage")
    }
''',
    "persist boot breadcrumb without synchronous preferences",
)
core_path.write_text(core, encoding="utf-8")


# Report the previous incomplete Kenji boot as soon as the Android process starts,
# before the user can enter the emulation screen. Toast is supplemented by a normal
# notification so the diagnostic remains readable even if the next attempt enters ANR.
app_path = Path(
    "src/android/app/src/main/java/org/yuzu/yuzu_emu/YuzuApplication.kt"
)
app = app_path.read_text(encoding="utf-8")

app = replace_once(
    app,
    '''        createNotificationChannels()
    }
''',
    '''        createNotificationChannels()
        reportKenjiBootDiagnostic()
    }

    private fun reportKenjiBootDiagnostic() {
        val traceFile = java.io.File(filesDir, "kenji-last-stage.txt")
        val stage = runCatching {
            traceFile.takeIf { it.isFile }?.readText()?.trim()
        }.getOrNull()
        if (stage.isNullOrEmpty() || stage == "READY") return

        val message = "Kenji anterior parou em: $stage"
        Log.warning("[MoonwitchKenjiDiagnostic] $message")

        android.os.Handler(android.os.Looper.getMainLooper()).postDelayed({
            android.widget.Toast.makeText(this, message, android.widget.Toast.LENGTH_LONG).show()
        }, 600L)

        runCatching {
            val notification = if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.O) {
                android.app.Notification.Builder(this, getString(R.string.notice_notification_channel_id))
            } else {
                @Suppress("DEPRECATION")
                android.app.Notification.Builder(this)
            }
                .setSmallIcon(applicationInfo.icon)
                .setContentTitle("Moonwitch — diagnóstico Kenji")
                .setContentText(message)
                .setStyle(android.app.Notification.BigTextStyle().bigText(message))
                .setAutoCancel(true)
                .build()

            getSystemService(NotificationManager::class.java).notify(0x4B454E4A, notification)
        }.onFailure {
            Log.warning("[MoonwitchKenjiDiagnostic] Notification unavailable: ${it.message}")
        }
    }
''',
    "report Kenji breadcrumb at application startup",
)

app_path.write_text(app, encoding="utf-8")
print("Kenji breadcrumb now uses a lightweight internal file with no synchronous preferences commit.")
