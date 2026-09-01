#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path


def replace_once(path_str: str, old: str, new: str, label: str) -> None:
    path = Path(path_str)
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"EXP6 patched: {label}")


# Experiment #6: isolate the cost of reactive fastmem read faults on Android.
# Keep Reactive Flushing enabled so the modern TextureCache/DMA machinery remains
# available, but allow direct CPU reads from cached fastmem pages on Android.
# Writes remain protected. This A/B tells us whether the huge EXP4/EXP5 slowdown
# comes from global read faults and whether TOTK actually needs those faults to
# keep foliage coherent.

replace_once(
    "src/common/settings.h",
    '''    SwitchableSetting<bool> use_reactive_flushing{linkage,\n#ifdef __ANDROID__\n                                                  false,\n#else\n                                                  true,\n#endif\n                                                  "use_reactive_flushing",\n                                                  Category::RendererAdvanced};\n''',
    '''    SwitchableSetting<bool> use_reactive_flushing{linkage,\n                                                  true,\n                                                  "use_reactive_flushing",\n                                                  Category::RendererAdvanced};\n''',
    "enable reactive flushing by default on Android",
)

replace_once(
    "src/core/memory.cpp",
    '''            Common::MemoryPermission perm{};\n            if (!Settings::values.use_reactive_flushing.GetValue() || !cached) {\n                perm |= Common::MemoryPermission::Read;\n            }\n''',
    '''            Common::MemoryPermission perm{};\n#if defined(__ANDROID__)\n            // EXP6 ablation: keep cached pages CPU-readable on Android so normal\n            // gameplay does not pay a page fault for every reactive read. Writes\n            // are still protected below, and TextureCache/DMA accuracy paths stay\n            // intact. If foliage regresses, the read-fault mechanism is necessary\n            // and must be narrowed rather than globally enabled.\n            perm |= Common::MemoryPermission::Read;\n#else\n            if (!Settings::values.use_reactive_flushing.GetValue() || !cached) {\n                perm |= Common::MemoryPermission::Read;\n            }\n#endif\n''',
    "bypass global reactive fastmem read faults on Android",
)

print("Applied graphics research experiment #6: reactive-flushing read-fault ablation on Android.")
