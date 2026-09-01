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
    print(f"EXP4 patched: {label}")


# Experiment #4: restore the reactive-flushing behavior that historically fixed
# TOTK's disappearing grass on desktop Yuzu. Moonwitch/Eden still carries the
# setting and fastmem side of the feature, but Android defaults it off and the
# current BufferCache no longer gates predictive downloads on preflushability.

replace_once(
    "src/common/settings.h",
    '''    SwitchableSetting<bool> use_reactive_flushing{linkage,\n#ifdef __ANDROID__\n                                                  false,\n#else\n                                                  true,\n#endif\n                                                  "use_reactive_flushing",\n                                                  Category::RendererAdvanced};\n''',
    '''    SwitchableSetting<bool> use_reactive_flushing{linkage,\n                                                  true,\n                                                  "use_reactive_flushing",\n                                                  Category::RendererAdvanced};\n''',
    "enable reactive flushing by default on Android",
)

replace_once(
    "src/core/memory.cpp",
    '''            Common::MemoryPermission perm{};\n            if (!Settings::values.use_reactive_flushing.GetValue() || !cached) {\n                perm |= Common::MemoryPermission::Read;\n            }\n''',
    '''            Common::MemoryPermission perm{};\n#if defined(__ANDROID__)\n            // Moonwitch graphics research EXP4: force reactive-flushing fastmem\n            // semantics regardless of a stale persisted Android setting. Cached\n            // GPU pages lose CPU read permission and fault reactively when read.\n            if (!cached) {\n#else\n            if (!Settings::values.use_reactive_flushing.GetValue() || !cached) {\n#endif\n                perm |= Common::MemoryPermission::Read;\n            }\n''',
    "force reactive fastmem protection on Android",
)

replace_once(
    "src/video_core/buffer_cache/buffer_cache.h",
    '''        tmp_intervals.push_back({new_base_address, size});\n        uncommitted_gpu_modified_ranges.Add(new_base_address, size);\n''',
    '''        tmp_intervals.push_back({new_base_address, size});\n#if defined(__ANDROID__)\n        // Reactive flushing: only queue a predictive download after a CPU read\n        // has made this region preflushable. GPU ownership is still tracked below.\n        if (memory_tracker.IsRegionPreflushable(new_base_address, size)) {\n            uncommitted_gpu_modified_ranges.Add(new_base_address, size);\n        }\n#else\n        if (!Settings::values.use_reactive_flushing.GetValue() ||\n            memory_tracker.IsRegionPreflushable(new_base_address, size)) {\n            uncommitted_gpu_modified_ranges.Add(new_base_address, size);\n        }\n#endif\n''',
    "restore reactive DMA-copy download gating",
)

replace_once(
    "src/video_core/buffer_cache/buffer_cache.h",
    '''    memory_tracker.MarkRegionAsGpuModified(device_addr, size);\n    gpu_modified_ranges.Add(device_addr, size);\n    uncommitted_gpu_modified_ranges.Add(device_addr, size);\n}\n''',
    '''    memory_tracker.MarkRegionAsGpuModified(device_addr, size);\n    gpu_modified_ranges.Add(device_addr, size);\n#if defined(__ANDROID__)\n    // Reactive flushing: do not schedule a predictive GPU->CPU download until\n    // the guest actually reads this GPU-owned region and marks it preflushable.\n    if (!memory_tracker.IsRegionPreflushable(device_addr, size)) {\n        return;\n    }\n#else\n    if (Settings::values.use_reactive_flushing.GetValue() &&\n        !memory_tracker.IsRegionPreflushable(device_addr, size)) {\n        return;\n    }\n#endif\n    uncommitted_gpu_modified_ranges.Add(device_addr, size);\n}\n''',
    "restore reactive written-buffer download gating",
)

print("Applied graphics research experiment #4: forced functional reactive flushing on Android.")
