#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise RuntimeError(f"anchor not found in {path}: {old!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def insert_once(path: Path, anchor: str, addition: str) -> None:
    text = path.read_text(encoding="utf-8")
    if addition.strip() in text:
        return
    if anchor not in text:
        raise RuntimeError(f"anchor not found in {path}: {anchor!r}")
    path.write_text(text.replace(anchor, anchor + addition, 1), encoding="utf-8")


# Stage 10 addresses the Stage 8/9 runtime result seen on TOTK: the framebuffer and
# image-lineage rings fill correctly, but reverse walking by host VkImage never reaches
# the displayed image. A rescaled/aliased guest image can change host VkImage while the
# guest GPU address stays stable. Record that address and use an exact guest-address
# match as a second, stronger scene-identity path. No temporal dispatch is enabled here.
# This branch is based directly on successful BUILD 140 and preserves its classic UI.

texture_h = ROOT / "src/video_core/renderer_vulkan/vk_texture_cache.h"
insert_once(
    texture_h,
    "    VkImageView view{VK_NULL_HANDLE};\n",
    "    GPUVAddr gpu_addr{};\n",
)
insert_once(
    texture_h,
    "    bool exact_presented_color_match{};\n",
    "    bool guest_address_match{};\n",
)
replace_once(
    texture_h,
    "    SGSR2FindSceneHistory(VkImage displayed_color_image);\n",
    "    SGSR2FindSceneHistory(VkImage displayed_color_image, GPUVAddr displayed_guest_addr);\n",
)

texture_cpp = ROOT / "src/video_core/renderer_vulkan/vk_texture_cache.cpp"
insert_once(
    texture_cpp,
    "        dst.view = color->RenderTarget();\n",
    "        dst.gpu_addr = color->GpuAddr();\n",
)
replace_once(
    texture_cpp,
    "TextureCacheRuntime::SGSR2FindSceneHistory(VkImage displayed_color_image) {\n",
    "TextureCacheRuntime::SGSR2FindSceneHistory(VkImage displayed_color_image,\n"
    "                                           GPUVAddr displayed_guest_addr) {\n",
)
replace_once(
    texture_cpp,
    "    auto find_framebuffer = [this](VkImage image, u32 hops)\n"
    "        -> std::optional<SGSR2SceneHistoryMatch> {\n",
    "    auto find_framebuffer = [this, displayed_guest_addr](VkImage image, u32 hops)\n"
    "        -> std::optional<SGSR2SceneHistoryMatch> {\n",
)
replace_once(
    texture_cpp,
    "            for (u32 color_index = 0; color_index < entry.color_count; ++color_index) {\n"
    "                if (entry.colors[color_index].image != image) {\n"
    "                    continue;\n"
    "                }\n"
    "                return SGSR2SceneHistoryMatch{\n"
    "                    .framebuffer = entry,\n"
    "                    .matched_scene_color = image,\n"
    "                    .lineage_hops = hops,\n"
    "                    .exact_presented_color_match = hops == 0,\n"
    "                };\n"
    "            }\n",
    "            for (u32 color_index = 0; color_index < entry.color_count; ++color_index) {\n"
    "                const auto& color = entry.colors[color_index];\n"
    "                const bool image_match = color.image == image;\n"
    "                const bool guest_match = hops == 0 && displayed_guest_addr != 0 &&\n"
    "                                         color.gpu_addr == displayed_guest_addr;\n"
    "                if (!image_match && !guest_match) {\n"
    "                    continue;\n"
    "                }\n"
    "                return SGSR2SceneHistoryMatch{\n"
    "                    .framebuffer = entry,\n"
    "                    .matched_scene_color = color.image,\n"
    "                    .lineage_hops = hops,\n"
    "                    .exact_presented_color_match = hops == 0 && image_match,\n"
    "                    .guest_address_match = guest_match,\n"
    "                };\n"
    "            }\n",
)
replace_once(
    texture_cpp,
    "                 \"Moonwitch SGSR2 scene history: no match after reverse walk; framebuffers={} lineage={}\",\n"
    "                 sgsr2_scene_history_count, sgsr2_lineage_count);\n",
    "                 \"Moonwitch SGSR2 scene history: no match after reverse walk; framebuffers={} lineage={} guest_addr=0x{:x}\",\n"
    "                 sgsr2_scene_history_count, sgsr2_lineage_count, displayed_guest_addr);\n",
)

rasterizer_h = ROOT / "src/video_core/renderer_vulkan/vk_rasterizer.h"
insert_once(
    rasterizer_h,
    "    bool scene_history_correlated{};\n",
    "    bool guest_address_correlated{};\n",
)
replace_once(
    rasterizer_h,
    "    GetSGSR2DepthCandidate(VkImage displayed_color_image) {\n"
    "        const auto history = texture_cache_runtime.SGSR2FindSceneHistory(displayed_color_image);\n",
    "    GetSGSR2DepthCandidate(VkImage displayed_color_image, GPUVAddr displayed_guest_addr) {\n"
    "        const auto history =\n"
    "            texture_cache_runtime.SGSR2FindSceneHistory(displayed_color_image, displayed_guest_addr);\n",
)
insert_once(
    rasterizer_h,
    "            .scene_history_correlated = true,\n",
    "            .guest_address_correlated = history->guest_address_match,\n",
)

runtime_inputs = ROOT / "src/video_core/renderer_vulkan/present/sgsr2_runtime_inputs.h"
insert_once(
    runtime_inputs,
    "    bool depth_scene_history_correlated{};\n",
    "    bool depth_guest_address_correlated{};\n",
)

layer_cpp = ROOT / "src/video_core/renderer_vulkan/present/layer.cpp"
replace_once(
    layer_cpp,
    "    if (const auto depth_candidate = rasterizer.GetSGSR2DepthCandidate(source_image)) {\n",
    "    const GPUVAddr sgsr2_display_guest_addr =\n"
    "        static_cast<GPUVAddr>(framebuffer.address + framebuffer.offset);\n"
    "    if (const auto depth_candidate =\n"
    "            rasterizer.GetSGSR2DepthCandidate(source_image, sgsr2_display_guest_addr)) {\n",
)
insert_once(
    layer_cpp,
    "        sgsr2_inputs.depth_scene_history_correlated =\n"
    "            depth_candidate->scene_history_correlated;\n",
    "        sgsr2_inputs.depth_guest_address_correlated =\n"
    "            depth_candidate->guest_address_correlated;\n",
)
replace_once(
    layer_cpp,
    "                     \"Moonwitch SGSR2 scene history match: lineage_hops={} extent={}x{} siblings={}\",\n"
    "                     depth_candidate->lineage_hops, depth_candidate->extent.width,\n"
    "                     depth_candidate->extent.height, depth_candidate->sibling_count);\n",
    "                     \"Moonwitch SGSR2 scene history match: lineage_hops={} guest_addr_match={} extent={}x{} siblings={}\",\n"
    "                     depth_candidate->lineage_hops,\n"
    "                     depth_candidate->guest_address_correlated, depth_candidate->extent.width,\n"
    "                     depth_candidate->extent.height, depth_candidate->sibling_count);\n",
)

print("Moonwitch Reconstruction Stage 10 guest-address correlation applied.")
print("Scene history now matches exact guest GPU address when host VkImage identity changes.")
print("Classic UI/base branch changes are untouched; vk_rasterizer.cpp is untouched.")
print("motion_valid remains false; SGSR2 temporal dispatch remains gated.")
