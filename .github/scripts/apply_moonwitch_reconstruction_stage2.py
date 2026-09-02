#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
QUALCOMM_COMMIT = "8177ad3c0498cc92a2588ef6c170148cbcf7ae16"
QUALCOMM_BASE = (
    "https://raw.githubusercontent.com/SnapdragonGameStudios/"
    "adreno-gpu-vulkan-code-sample-framework/" + QUALCOMM_COMMIT + "/samples/sgsr2/shaders/"
)


def write_if_changed(path: Path, content: str) -> None:
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def download_if_missing(name: str) -> None:
    destination = ROOT / "src/video_core/host_shaders" / name
    if destination.exists() and destination.stat().st_size > 0:
        return
    with urlopen(QUALCOMM_BASE + name, timeout=30) as response:
        data = response.read()
    destination.write_bytes(data)


def insert_once(path: Path, anchor: str, addition: str) -> None:
    text = path.read_text(encoding="utf-8")
    if addition.strip() in text:
        return
    if anchor not in text:
        raise RuntimeError(f"anchor not found in {path}: {anchor!r}")
    text = text.replace(anchor, anchor + addition, 1)
    path.write_text(text, encoding="utf-8")


for shader in ("sgsr2_convert.comp", "sgsr2_activate.comp", "sgsr2_upscale.comp"):
    download_if_missing(shader)

resources_h = r'''// SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#include <array>
#include <cstddef>
#include "common/common_types.h"
#include "video_core/vulkan_common/vulkan_memory_allocator.h"
#include "video_core/vulkan_common/vulkan_wrapper.h"

namespace Vulkan {

class Device;
class Scheduler;

// CPU-side mirror of the uniform block consumed by Qualcomm SGSR2.
// Stage 2 deliberately does not dispatch the temporal passes yet: valid depth and
// motion inputs must be wired first. Keeping the exact data model here lets us build
// and validate the real shader/resource path without feeding fake motion vectors.
struct alignas(16) SGSR2Params {
    std::array<u32, 2> render_size{};
    std::array<u32, 2> display_size{};
    std::array<f32, 2> render_size_rcp{};
    std::array<f32, 2> display_size_rcp{};
    std::array<f32, 2> jitter_offset{};
    std::array<f32, 2> padding{};
    std::array<std::array<f32, 4>, 4> clip_to_prev_clip{};
    f32 pre_exposure{1.0f};
    f32 camera_fov_angle_hor{1.0f};
    f32 camera_near{0.1f};
    f32 min_lerp_contribution{0.0f};
    u32 same_camera{};
    u32 reset{1};
    std::array<u32, 2> tail_padding{};
};

class SGSR2Resources {
public:
    SGSR2Resources(const Device& device, MemoryAllocator& allocator, VkExtent2D render_extent,
                   VkExtent2D display_extent);

    SGSR2Resources(const SGSR2Resources&) = delete;
    SGSR2Resources& operator=(const SGSR2Resources&) = delete;

    void Clear(Scheduler& scheduler);
    void AdvanceFrame();

    [[nodiscard]] bool Matches(VkExtent2D render_extent, VkExtent2D display_extent) const;
    [[nodiscard]] bool HasValidHistory() const { return history_valid; }
    void InvalidateHistory() { history_valid = false; }

    [[nodiscard]] VkImageView YCoCgColorView() const { return *ycocg_color.view; }
    [[nodiscard]] VkImageView MotionDepthAlphaView() const { return *motion_depth_alpha.view; }
    [[nodiscard]] VkImageView MotionDepthClipAlphaView() const {
        return *motion_depth_clip_alpha.view;
    }
    [[nodiscard]] VkImageView PreviousLumaHistoryView() const {
        return *luma_history[PreviousIndex()].view;
    }
    [[nodiscard]] VkImageView CurrentLumaHistoryView() const {
        return *luma_history[history_index].view;
    }
    [[nodiscard]] VkImageView PreviousHistoryOutputView() const {
        return *history_output[PreviousIndex()].view;
    }
    [[nodiscard]] VkImageView CurrentHistoryOutputView() const {
        return *history_output[history_index].view;
    }
    [[nodiscard]] VkImageView SceneColorView() const { return *scene_color.view; }

private:
    struct ImageResource {
        vk::Image image;
        vk::ImageView view;
    };

    [[nodiscard]] size_t PreviousIndex() const { return history_index ^ 1U; }

    VkExtent2D render_extent{};
    VkExtent2D display_extent{};
    ImageResource ycocg_color;
    ImageResource motion_depth_alpha;
    ImageResource motion_depth_clip_alpha;
    std::array<ImageResource, 2> luma_history;
    std::array<ImageResource, 2> history_output;
    ImageResource scene_color;
    size_t history_index{};
    bool history_valid{};
};

} // namespace Vulkan
'''

resources_cpp = r'''// SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
// SPDX-License-Identifier: GPL-3.0-or-later

#include "video_core/renderer_vulkan/present/sgsr2_resources.h"

#include "video_core/renderer_vulkan/present/util.h"
#include "video_core/renderer_vulkan/vk_scheduler.h"
#include "video_core/vulkan_common/vulkan_device.h"

namespace Vulkan {
namespace {

SGSR2Resources::ImageResource MakeImage(const Device& device, MemoryAllocator& allocator,
                                        VkExtent2D extent, VkFormat format) {
    auto image = CreateWrappedImage(allocator, extent, format);
    auto view = CreateWrappedImageView(device, image, format);
    return SGSR2Resources::ImageResource{std::move(image), std::move(view)};
}

} // namespace

SGSR2Resources::SGSR2Resources(const Device& device, MemoryAllocator& allocator,
                               VkExtent2D render_extent_, VkExtent2D display_extent_)
    : render_extent{render_extent_}, display_extent{display_extent_},
      ycocg_color{MakeImage(device, allocator, render_extent, VK_FORMAT_R32_UINT)},
      motion_depth_alpha{MakeImage(device, allocator, render_extent,
                                   VK_FORMAT_R16G16B16A16_SFLOAT)},
      motion_depth_clip_alpha{MakeImage(device, allocator, render_extent,
                                        VK_FORMAT_R16G16B16A16_SFLOAT)},
      luma_history{MakeImage(device, allocator, render_extent, VK_FORMAT_R32_UINT),
                   MakeImage(device, allocator, render_extent, VK_FORMAT_R32_UINT)},
      history_output{MakeImage(device, allocator, display_extent, VK_FORMAT_R16G16B16A16_SFLOAT),
                     MakeImage(device, allocator, display_extent, VK_FORMAT_R16G16B16A16_SFLOAT)},
      scene_color{MakeImage(device, allocator, display_extent, VK_FORMAT_R16G16B16A16_SFLOAT)} {}

void SGSR2Resources::Clear(Scheduler& scheduler) {
    scheduler.RequestOutsideRenderPassOperationContext();
    scheduler.Record([this](vk::CommandBuffer cmdbuf) {
        ClearColorImage(cmdbuf, *ycocg_color.image);
        ClearColorImage(cmdbuf, *motion_depth_alpha.image);
        ClearColorImage(cmdbuf, *motion_depth_clip_alpha.image);
        for (auto& image : luma_history) {
            ClearColorImage(cmdbuf, *image.image);
        }
        for (auto& image : history_output) {
            ClearColorImage(cmdbuf, *image.image);
        }
        ClearColorImage(cmdbuf, *scene_color.image);
    });
    history_index = 0;
    history_valid = false;
}

void SGSR2Resources::AdvanceFrame() {
    history_index ^= 1U;
    history_valid = true;
}

bool SGSR2Resources::Matches(VkExtent2D other_render_extent,
                             VkExtent2D other_display_extent) const {
    return render_extent.width == other_render_extent.width &&
           render_extent.height == other_render_extent.height &&
           display_extent.width == other_display_extent.width &&
           display_extent.height == other_display_extent.height;
}

} // namespace Vulkan
'''

# Make ImageResource accessible to the local MakeImage helper while keeping the rest private.
resources_h = resources_h.replace(
    "private:\n    struct ImageResource {",
    "public:\n    struct ImageResource {"
).replace(
    "    };\n\n    [[nodiscard]] size_t PreviousIndex() const",
    "    };\n\nprivate:\n    [[nodiscard]] size_t PreviousIndex() const",
    1,
)

write_if_changed(ROOT / "src/video_core/renderer_vulkan/present/sgsr2_resources.h", resources_h)
write_if_changed(ROOT / "src/video_core/renderer_vulkan/present/sgsr2_resources.cpp", resources_cpp)

host_cmake = ROOT / "src/video_core/host_shaders/CMakeLists.txt"
insert_once(
    host_cmake,
    "    ${CMAKE_CURRENT_SOURCE_DIR}/sgsr1_shader_mobile_edge_direction.frag\n",
    "    # Snapdragon Game Super Resolution 2 (official Qualcomm compute path)\n"
    "    ${CMAKE_CURRENT_SOURCE_DIR}/sgsr2_convert.comp\n"
    "    ${CMAKE_CURRENT_SOURCE_DIR}/sgsr2_activate.comp\n"
    "    ${CMAKE_CURRENT_SOURCE_DIR}/sgsr2_upscale.comp\n",
)

video_cmake = ROOT / "src/video_core/CMakeLists.txt"
insert_once(
    video_cmake,
    "    renderer_vulkan/present/sgsr.h\n",
    "    renderer_vulkan/present/sgsr2_resources.cpp\n"
    "    renderer_vulkan/present/sgsr2_resources.h\n",
)

print("Moonwitch Reconstruction Stage 2 temporal backbone applied.")
print(f"Pinned Qualcomm SGSR2 source commit: {QUALCOMM_COMMIT}")
