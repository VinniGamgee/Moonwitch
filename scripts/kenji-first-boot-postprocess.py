#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path

path = Path(
    "src/android/app/src/main/java/org/yuzu/yuzu_emu/fragments/EmulationFragment.kt"
)
text = path.read_text(encoding="utf-8")

replacements = [
    (
        "    private inner class EmulationState(\n",
        "    private class EmulationState(\n",
    ),
    (
        "                if (usesKenji) emulationViewModel.setEmulationStopped(true)\n",
        "",
    ),
    (
        "                                    requireContext().applicationContext,\n",
        "                                    org.yuzu.yuzu_emu.YuzuApplication.appContext,\n",
    ),
    (
        "                                    emulationViewModel.setEmulationStarted(true)\n",
        "",
    ),
    (
        "                                emulationViewModel.setEmulationStarted(false)\n",
        "",
    ),
    (
        "                                emulationViewModel.setEmulationStopped(true)\n",
        "",
    ),
]

for old, new in replacements:
    if old not in text:
        raise SystemExit(f"Expected first-boot fragment not found: {old!r}")
    text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
print("Kenji first-boot state host normalized for Kotlin.")
