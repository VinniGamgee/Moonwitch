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
    print(f"EXP5 patched: {label}")


# Experiment #5: keep the final upstream reactive-flushing model and remove the
# heavy intermediate BufferCache gating used by EXP4.
#
# Yuzu's final reactive-flushing merge deliberately backed the feature out of
# the general BufferCache and kept the accuracy-critical behavior in fastmem /
# texture-cache paths. Moonwitch already carries the final texture-cache pieces
# (PreemtiveDownload, forced_flushed and dma_downloaded), so Android only needs
# reactive flushing enabled and its CPU-read fault semantics restored.

replace_once(
    "src/common/settings.h",
    '''    SwitchableSetting<bool> use_reactive_flushing{linkage,\n#ifdef __ANDROID__\n                                                  false,\n#else\n                                                  true,\n#endif\n                                                  "use_reactive_flushing",\n                                                  Category::RendererAdvanced};\n''',
    '''    SwitchableSetting<bool> use_reactive_flushing{linkage,\n                                                  true,\n                                                  "use_reactive_flushing",\n                                                  Category::RendererAdvanced};\n''',
    "enable reactive flushing by default on Android",
)

replace_once(
    "src/core/memory.cpp",
    '''            Common::MemoryPermission perm{};\n            if (!Settings::values.use_reactive_flushing.GetValue() || !cached) {\n                perm |= Common::MemoryPermission::Read;\n            }\n''',
    '''            Common::MemoryPermission perm{};\n#if defined(__ANDROID__)\n            // EXP5: use the final upstream reactive-flushing model on Android.\n            // Cached GPU-owned pages fault only when the guest CPU actually reads\n            // them; BufferCache remains on its modern asynchronous/predictive path.\n            if (!cached) {\n#else\n            if (!Settings::values.use_reactive_flushing.GetValue() || !cached) {\n#endif\n                perm |= Common::MemoryPermission::Read;\n            }\n''',
    "force reactive fastmem read protection on Android",
)

print("Applied graphics research experiment #5: final-path Android reactive flushing without BufferCache gating.")
