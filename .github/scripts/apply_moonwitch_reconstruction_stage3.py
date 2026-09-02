#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def write_if_changed(path: Path, content: str) -> None:
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


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


runtime_inputs_h = r'''// SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#include <array>

#include <vulkan/vulkan_core.h>

#include "common/common_types.h"

namespace Vulkan {

// Runtime contract between the guest presentation layer and the SGSR2 temporal path.
// Stage 3 wires only data that is genuinely available. Missing depth/motion data remains
// explicitly invalid so the temporal passes can never be dispatched with placeholders.
struct SGSR2RuntimeInputs {
    VkImage color_image{VK_NULL_HANDLE};
    VkImageView color_view{VK_NULL_HANDLE};
    VkExtent2D render_extent{};
    VkExtent2D display_extent{};

    VkImage depth_image{VK_NULL_HANDLE};
    VkImageView depth_view{VK_NULL_HANDLE};
    VkImage motion_image{VK_NULL_HANDLE};
    VkImageView motion_view{VK_NULL_HANDLE};

    std::array<f32, 2> jitter{};
    std::array<std::array<f32, 4>, 4> clip_to_prev_clip{};

    bool color_valid{};
    bool depth_valid{};
    bool motion_valid{};
    bool camera_motion_valid{};
    bool jitter_valid{};
    bool source_is_accelerated{};

    [[nodiscard]] bool HasMotionSource() const {
        return motion_valid || camera_motion_valid;
    }

    [[nodiscard]] bool ReadyForTemporalDispatch() const {
        return color_valid && depth_valid && HasMotionSource();
    }
};

} // namespace Vulkan
'''

write_if_changed(
    ROOT / "src/video_core/renderer_vulkan/present/sgsr2_runtime_inputs.h", runtime_inputs_h
)

layer_h = ROOT / "src/video_core/renderer_vulkan/present/layer.h"
insert_once(
    layer_h,
    '#include "video_core/renderer_vulkan/present/sgsr.h"\n',
    '#include "video_core/renderer_vulkan/present/sgsr2_runtime_inputs.h"\n',
)
insert_once(
    layer_h,
    '                       const Layout::FramebufferLayout& layout);\n',
    '\n    [[nodiscard]] const SGSR2RuntimeInputs& GetSGSR2RuntimeInputs() const {\n'
    '        return sgsr2_inputs;\n'
    '    }\n',
)
insert_once(
    layer_h,
    '    std::optional<CAS> cas_pass{};\n',
    '    SGSR2RuntimeInputs sgsr2_inputs{};\n',
)

layer_cpp = ROOT / "src/video_core/renderer_vulkan/present/layer.cpp"
replace_once(
    layer_cpp,
    '    VkImageView source_image_view =\n'
    '        texture_info ? texture_info->image_view : *raw_image_views[image_index];\n\n'
    '    if (auto* fxaa = std::get_if<FXAA>(&anti_alias)) {\n',
    '    VkImageView source_image_view =\n'
    '        texture_info ? texture_info->image_view : *raw_image_views[image_index];\n\n'
    '    const VkExtent2D render_extent{\n'
    '        .width = scaled_width,\n'
    '        .height = scaled_height,\n'
    '    };\n\n'
    '    // Capture the real guest color surface before any host AA/upscale/CAS pass.\n'
    '    // Depth and motion remain invalid until we can identify legitimate guest resources.\n'
    '    sgsr2_inputs = {};\n'
    '    sgsr2_inputs.color_image = source_image;\n'
    '    sgsr2_inputs.color_view = source_image_view;\n'
    '    sgsr2_inputs.render_extent = render_extent;\n'
    '    sgsr2_inputs.display_extent = output_size_extent;\n'
    '    sgsr2_inputs.color_valid = source_image != VK_NULL_HANDLE &&\n'
    '                              source_image_view != VK_NULL_HANDLE &&\n'
    '                              render_extent.width != 0 && render_extent.height != 0;\n'
    '    sgsr2_inputs.source_is_accelerated = use_accelerated;\n\n'
    '    if (auto* fxaa = std::get_if<FXAA>(&anti_alias)) {\n',
)
replace_once(
    layer_cpp,
    '    auto crop_rect = Tegra::NormalizeCrop(framebuffer, texture_width, texture_height);\n'
    '    const VkExtent2D render_extent{\n'
    '        .width = scaled_width,\n'
    '        .height = scaled_height,\n'
    '    };\n\n',
    '    auto crop_rect = Tegra::NormalizeCrop(framebuffer, texture_width, texture_height);\n\n',
)

blit_h = ROOT / "src/video_core/renderer_vulkan/vk_blit_screen.h"
insert_once(
    blit_h,
    '    void PrepareFrame(const Device& device, Frame* frame, const Layout::FramebufferLayout& layout);\n',
    '\n    [[nodiscard]] const SGSR2RuntimeInputs* GetPrimarySGSR2RuntimeInputs() const {\n'
    '        if (layers.empty()) {\n'
    '            return nullptr;\n'
    '        }\n'
    '        return &layers.front().GetSGSR2RuntimeInputs();\n'
    '    }\n',
)

video_cmake = ROOT / "src/video_core/CMakeLists.txt"
insert_once(
    video_cmake,
    '    renderer_vulkan/present/sgsr2_resources.h\n',
    '    renderer_vulkan/present/sgsr2_runtime_inputs.h\n',
)

print("Moonwitch Reconstruction Stage 3 runtime input plumbing applied.")
print("Real guest color capture: enabled before host AA/upscale/CAS.")
print("Temporal dispatch remains gated until valid depth + motion/camera data exists.")
