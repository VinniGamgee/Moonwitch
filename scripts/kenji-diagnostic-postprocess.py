#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Expected fragment not found ({label}): {old!r}")
    return text.replace(old, new, 1)


# Persist the boot stage independently from the Kenji data directory. SharedPreferences
# uses a synchronous commit here on purpose: if Android kills the process for ANR right
# after the native call starts, the last stage must already be durable.
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
        runCatching { bootTraceFile?.writeText(stage) }
        runCatching {
            org.yuzu.yuzu_emu.YuzuApplication.appContext
                .getSharedPreferences("moonwitch_kenji_boot_trace", Context.MODE_PRIVATE)
                .edit()
                .putString("last_stage", stage)
                .putLong("updated_at", System.currentTimeMillis())
                .commit()
        }
        Log.info("$TAG Boot stage: $stage")
    }
''',
    "persist boot breadcrumb in SharedPreferences",
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
        val prefs = getSharedPreferences("moonwitch_kenji_boot_trace", Context.MODE_PRIVATE)
        val stage = prefs.getString("last_stage", null)?.trim()
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
print("Kenji breadcrumb now persists synchronously and reports at app startup.")
