#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path


def replace_once(path: Path, old: str, new: str, marker: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if marker in text:
        print(f"[moonwitch-maximum-compatibility-core] {label}: already patched")
        return
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one anchor for {label}, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"[moonwitch-maximum-compatibility-core] {label}: patched")


root = Path(".")
settings_h = root / "src/common/settings.h"
texture_cache = root / "src/video_core/texture_cache/texture_cache.h"
vk_rasterizer = root / "src/video_core/renderer_vulkan/vk_rasterizer.cpp"
pipeline_cache = root / "src/video_core/renderer_vulkan/vk_pipeline_cache.cpp"


replace_once(
    settings_h,
    "    // Optional Vulkan memory dependencies for games or drivers that expose stale render\n"
    "    // targets. Mode 0 preserves upstream behavior; 1 is scoped; 2 is global/strict.\n",
    "    // Master diagnostic override for the four Moonwitch Vulkan compatibility fixes.\n"
    "    // Individual values remain stored and become effective again when this is disabled.\n"
    "    SwitchableSetting<bool> moonwitch_maximum_compatibility{\n"
    "        linkage, false, \"moonwitch_maximum_compatibility\",\n"
    "        Category::RendererAdvanced, Specialization::Default, true, true};\n\n"
    "    // Optional Vulkan memory dependencies for games or drivers that expose stale render\n"
    "    // targets. Mode 0 preserves upstream behavior; 1 is scoped; 2 is global/strict.\n",
    "moonwitch_maximum_compatibility{",
    "register runtime/per-game master override",
)

replace_once(
    vk_rasterizer,
    "void RasterizerVulkan::ApplyMoonwitchGpuBarrier(bool tiled) {\n"
    "    const s32 mode = std::clamp(\n"
    "        Settings::values.moonwitch_safe_gpu_barriers_mode.GetValue(), 0, 2);\n",
    "void RasterizerVulkan::ApplyMoonwitchGpuBarrier(bool tiled) {\n"
    "    const bool maximum_compatibility =\n"
    "        Settings::values.moonwitch_maximum_compatibility.GetValue();\n"
    "    const s32 mode = maximum_compatibility\n"
    "                         ? 2\n"
    "                         : std::clamp(\n"
    "                               Settings::values.moonwitch_safe_gpu_barriers_mode.GetValue(),\n"
    "                               0, 2);\n",
    "const bool maximum_compatibility =",
    "force strict GPU barriers while the profile is active",
)

replace_once(
    texture_cache,
    """    PrepareImage(image_id, is_modification, invalidate);
    if (is_modification &&
        Settings::values.moonwitch_render_target_init_alias_guard.GetValue()) {
        runtime.ApplyRenderTargetInitAliasGuard(slot_images[image_id], alias_needs_visibility);
    }
    if (!is_modification && Settings::values.moonwitch_texture_coherency.GetValue()) {
        runtime.ApplyTextureCoherency(slot_images[image_id]);
    }
}
""",
    """    PrepareImage(image_id, is_modification, invalidate);
    const bool maximum_compatibility =
        Settings::values.moonwitch_maximum_compatibility.GetValue();
    if (is_modification &&
        (maximum_compatibility ||
         Settings::values.moonwitch_render_target_init_alias_guard.GetValue())) {
        runtime.ApplyRenderTargetInitAliasGuard(slot_images[image_id], alias_needs_visibility);
    }
    if (!is_modification &&
        (maximum_compatibility ||
         Settings::values.moonwitch_texture_coherency.GetValue())) {
        runtime.ApplyTextureCoherency(slot_images[image_id]);
    }
}
""",
    "Settings::values.moonwitch_maximum_compatibility.GetValue();",
    "override render-target and texture guards",
)

replace_once(
    pipeline_cache,
    "u64 CurrentShaderPrecisionMode() {\n"
    "    return static_cast<u64>(std::clamp(\n"
    "        Settings::values.moonwitch_shader_precision_mode.GetValue(), 0, 2));\n"
    "}\n",
    "u64 CurrentShaderPrecisionMode() {\n"
    "    if (Settings::values.moonwitch_maximum_compatibility.GetValue()) {\n"
    "        return 2;\n"
    "    }\n"
    "    return static_cast<u64>(std::clamp(\n"
    "        Settings::values.moonwitch_shader_precision_mode.GetValue(), 0, 2));\n"
    "}\n",
    "if (Settings::values.moonwitch_maximum_compatibility.GetValue())",
    "force the strict keyed shader variant while active",
)

print("Applied Moonwitch Maximum Compatibility core override.")
