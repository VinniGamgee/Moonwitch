#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path


def replace_once(path: Path, old: str, new: str, marker: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if marker in text:
        print(f"[totk-visibility-v2] {label}: already patched")
        return
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one anchor for {label}, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"[totk-visibility-v2] {label}: patched")


root = Path(".")
compute_h = root / "src/video_core/renderer_vulkan/vk_compute_pipeline.h"
rasterizer_cpp = root / "src/video_core/renderer_vulkan/vk_rasterizer.cpp"

# The original TOTK foliage workaround records a broad compute->graphics visibility barrier after
# every compute dispatch. Preserve the barrier for shaders that can actually write guest-visible
# data, but skip it for read-only compute passes. Shader::Info already tracks all storage/image/
# global write routes, so this removes unnecessary stalls without weakening write-producing passes.
replace_once(
    compute_h,
    "    bool IsBound() const noexcept {\n"
    "        return static_cast<bool>(pipeline);\n"
    "    }\n\n"
    "private:\n",
    "    bool IsBound() const noexcept {\n"
    "        return static_cast<bool>(pipeline);\n"
    "    }\n\n"
    "    [[nodiscard]] bool MayWriteGuestMemory() const noexcept {\n"
    "        if (info.stores_global_memory || info.uses_global_increment ||\n"
    "            info.uses_global_decrement || info.uses_atomic_f32_add ||\n"
    "            info.uses_atomic_f16x2_add || info.uses_atomic_f16x2_min ||\n"
    "            info.uses_atomic_f16x2_max || info.uses_atomic_f32x2_add ||\n"
    "            info.uses_atomic_f32x2_min || info.uses_atomic_f32x2_max ||\n"
    "            info.uses_atomic_s32_min || info.uses_atomic_s32_max ||\n"
    "            info.uses_int64_bit_atomics || info.uses_atomic_image_u32) {\n"
    "            return true;\n"
    "        }\n"
    "        for (const auto& desc : info.storage_buffers_descriptors) {\n"
    "            if (desc.is_written) {\n"
    "                return true;\n"
    "            }\n"
    "        }\n"
    "        for (const auto& desc : info.image_buffer_descriptors) {\n"
    "            if (desc.is_written) {\n"
    "                return true;\n"
    "            }\n"
    "        }\n"
    "        for (const auto& desc : info.image_descriptors) {\n"
    "            if (desc.is_written) {\n"
    "                return true;\n"
    "            }\n"
    "        }\n"
    "        return false;\n"
    "    }\n\n"
    "private:\n",
    "MayWriteGuestMemory() const noexcept",
    "expose compute write metadata",
)

replace_once(
    rasterizer_cpp,
    "    const auto record_totk_compute_visibility_barrier =\n"
    "        [this, apply_totk_compute_visibility_workaround] {\n"
    "            if (!apply_totk_compute_visibility_workaround) {\n"
    "                return;\n"
    "            }\n",
    "    const bool totk_compute_may_write_guest_memory =\n"
    "        apply_totk_compute_visibility_workaround && pipeline->MayWriteGuestMemory();\n"
    "    const auto record_totk_compute_visibility_barrier =\n"
    "        [this, totk_compute_may_write_guest_memory] {\n"
    "            if (!totk_compute_may_write_guest_memory) {\n"
    "                return;\n"
    "            }\n",
    "totk_compute_may_write_guest_memory",
    "gate TOTK visibility barrier to write-producing compute",
)

print("Applied TOTK compute visibility v2: skip foliage barrier on read-only compute passes.")
