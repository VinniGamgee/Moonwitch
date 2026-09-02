#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def write_if_changed(path: Path, content: str) -> None:
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def insert_once(path: Path, anchor: str, addition: str) -> None:
    text = path.read_text(encoding="utf-8")
    if addition.strip() in text:
        return
    if anchor not in text:
        raise RuntimeError(f"anchor not found in {path}: {anchor!r}")
    path.write_text(text.replace(anchor, anchor + addition, 1), encoding="utf-8")


probe_h = r'''// SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#include <array>

#include <vulkan/vulkan_core.h>

#include "common/common_types.h"

namespace Vulkan {

class MemoryAllocator;
class Scheduler;

struct SGSR2MotionProbeResult {
    bool sampled{};
    bool content_plausible{};
    u32 finite_samples{};
    u32 active_samples{};
    f32 zero_ratio{};
    f32 mean_magnitude{};
    f32 max_magnitude{};
    f32 changed_ratio{};
};

// Diagnostic Stage 7 probe. It sparsely reads a stable, format-plausible sibling
// render target and characterizes its first two channels. This is evidence gathering
// only: it never promotes the candidate to motion_valid.
class SGSR2MotionProbe {
public:
    SGSR2MotionProbe(MemoryAllocator& memory_allocator, Scheduler& scheduler);

    [[nodiscard]] SGSR2MotionProbeResult Probe(VkImage image, VkExtent2D extent,
                                                u32 guest_pixel_format);

private:
    MemoryAllocator& memory_allocator;
    Scheduler& scheduler;
    std::array<std::array<f32, 2>, 64> previous_samples{};
    VkImage previous_image{VK_NULL_HANDLE};
    u32 previous_format{};
    bool have_previous{};
};

} // namespace Vulkan
'''

probe_cpp = r'''// SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
// SPDX-License-Identifier: GPL-3.0-or-later

#include "video_core/renderer_vulkan/present/sgsr2_motion_probe.h"

#include <algorithm>
#include <array>
#include <bit>
#include <cmath>
#include <cstring>

#include "video_core/renderer_vulkan/present/util.h"
#include "video_core/renderer_vulkan/vk_scheduler.h"
#include "video_core/surface.h"
#include "video_core/vulkan_common/vulkan_memory_allocator.h"

namespace Vulkan {
namespace {

constexpr u32 SAMPLE_GRID = 8;
constexpr u32 SAMPLE_COUNT = SAMPLE_GRID * SAMPLE_GRID;
constexpr f32 ACTIVE_EPSILON = 1.0e-4f;
constexpr f32 CHANGE_EPSILON = 2.0e-4f;

[[nodiscard]] u32 MotionTexelSize(u32 guest_pixel_format) {
    using PixelFormat = VideoCore::Surface::PixelFormat;
    switch (static_cast<PixelFormat>(guest_pixel_format)) {
    case PixelFormat::R8G8_SNORM:
        return 2;
    case PixelFormat::R16G16_FLOAT:
    case PixelFormat::R16G16_SNORM:
        return 4;
    case PixelFormat::R32G32_FLOAT:
    case PixelFormat::R16G16B16A16_FLOAT:
        return 8;
    case PixelFormat::R32G32B32A32_FLOAT:
        return 16;
    default:
        return 0;
    }
}

[[nodiscard]] f32 HalfToFloat(u16 value) {
    const u32 sign = static_cast<u32>(value & 0x8000u) << 16;
    u32 exponent = (value >> 10) & 0x1fu;
    u32 mantissa = value & 0x03ffu;
    u32 bits{};
    if (exponent == 0) {
        if (mantissa == 0) {
            bits = sign;
        } else {
            s32 shift = 0;
            while ((mantissa & 0x0400u) == 0) {
                mantissa <<= 1;
                ++shift;
            }
            mantissa &= 0x03ffu;
            const u32 float_exp = static_cast<u32>(127 - 15 + 1 - shift);
            bits = sign | (float_exp << 23) | (mantissa << 13);
        }
    } else if (exponent == 0x1fu) {
        bits = sign | 0x7f800000u | (mantissa << 13);
    } else {
        exponent = exponent + (127 - 15);
        bits = sign | (exponent << 23) | (mantissa << 13);
    }
    return std::bit_cast<f32>(bits);
}

[[nodiscard]] std::array<f32, 2> DecodeVector(const u8* ptr, u32 guest_pixel_format) {
    using PixelFormat = VideoCore::Surface::PixelFormat;
    switch (static_cast<PixelFormat>(guest_pixel_format)) {
    case PixelFormat::R8G8_SNORM: {
        s8 x{};
        s8 y{};
        std::memcpy(&x, ptr, sizeof(x));
        std::memcpy(&y, ptr + 1, sizeof(y));
        return {std::max(-1.0f, static_cast<f32>(x) / 127.0f),
                std::max(-1.0f, static_cast<f32>(y) / 127.0f)};
    }
    case PixelFormat::R16G16_SNORM: {
        s16 x{};
        s16 y{};
        std::memcpy(&x, ptr, sizeof(x));
        std::memcpy(&y, ptr + sizeof(x), sizeof(y));
        return {std::max(-1.0f, static_cast<f32>(x) / 32767.0f),
                std::max(-1.0f, static_cast<f32>(y) / 32767.0f)};
    }
    case PixelFormat::R16G16_FLOAT:
    case PixelFormat::R16G16B16A16_FLOAT: {
        u16 x{};
        u16 y{};
        std::memcpy(&x, ptr, sizeof(x));
        std::memcpy(&y, ptr + sizeof(x), sizeof(y));
        return {HalfToFloat(x), HalfToFloat(y)};
    }
    case PixelFormat::R32G32_FLOAT:
    case PixelFormat::R32G32B32A32_FLOAT: {
        f32 x{};
        f32 y{};
        std::memcpy(&x, ptr, sizeof(x));
        std::memcpy(&y, ptr + sizeof(x), sizeof(y));
        return {x, y};
    }
    default:
        return {};
    }
}

} // Anonymous namespace

SGSR2MotionProbe::SGSR2MotionProbe(MemoryAllocator& memory_allocator_, Scheduler& scheduler_)
    : memory_allocator{memory_allocator_}, scheduler{scheduler_} {}

SGSR2MotionProbeResult SGSR2MotionProbe::Probe(VkImage image, VkExtent2D extent,
                                               u32 guest_pixel_format) {
    SGSR2MotionProbeResult result{};
    const u32 texel_size = MotionTexelSize(guest_pixel_format);
    if (image == VK_NULL_HANDLE || texel_size == 0 || extent.width == 0 || extent.height == 0) {
        have_previous = false;
        return result;
    }

    const VkDeviceSize buffer_size = static_cast<VkDeviceSize>(SAMPLE_COUNT) * texel_size;
    vk::Buffer readback = CreateWrappedBuffer(memory_allocator, buffer_size, MemoryUsage::Download);

    std::array<VkBufferImageCopy, SAMPLE_COUNT> regions{};
    for (u32 index = 0; index < SAMPLE_COUNT; ++index) {
        const u32 grid_x = index % SAMPLE_GRID;
        const u32 grid_y = index / SAMPLE_GRID;
        const u32 x = std::min(extent.width - 1,
                               ((2 * grid_x + 1) * extent.width) / (2 * SAMPLE_GRID));
        const u32 y = std::min(extent.height - 1,
                               ((2 * grid_y + 1) * extent.height) / (2 * SAMPLE_GRID));
        regions[index] = VkBufferImageCopy{
            .bufferOffset = static_cast<VkDeviceSize>(index) * texel_size,
            .bufferRowLength = 0,
            .bufferImageHeight = 0,
            .imageSubresource{
                .aspectMask = VK_IMAGE_ASPECT_COLOR_BIT,
                .mipLevel = 0,
                .baseArrayLayer = 0,
                .layerCount = 1,
            },
            .imageOffset = {static_cast<s32>(x), static_cast<s32>(y), 0},
            .imageExtent = {1, 1, 1},
        };
    }

    const VkBuffer dst = *readback;
    scheduler.RequestOutsideRenderPassOperationContext();
    scheduler.Record([image, dst, regions](vk::CommandBuffer cmdbuf) {
        const VkImageMemoryBarrier before{
            .sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER,
            .pNext = nullptr,
            .srcAccessMask = VK_ACCESS_SHADER_WRITE_BIT | VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT |
                             VK_ACCESS_TRANSFER_WRITE_BIT,
            .dstAccessMask = VK_ACCESS_TRANSFER_READ_BIT,
            .oldLayout = VK_IMAGE_LAYOUT_GENERAL,
            .newLayout = VK_IMAGE_LAYOUT_GENERAL,
            .srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
            .dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
            .image = image,
            .subresourceRange{
                .aspectMask = VK_IMAGE_ASPECT_COLOR_BIT,
                .baseMipLevel = 0,
                .levelCount = 1,
                .baseArrayLayer = 0,
                .layerCount = 1,
            },
        };
        cmdbuf.PipelineBarrier(VK_PIPELINE_STAGE_ALL_COMMANDS_BIT, VK_PIPELINE_STAGE_TRANSFER_BIT, 0,
                               {}, {}, before);
        cmdbuf.CopyImageToBuffer(image, VK_IMAGE_LAYOUT_GENERAL, dst, regions);
        const VkMemoryBarrier after{
            .sType = VK_STRUCTURE_TYPE_MEMORY_BARRIER,
            .pNext = nullptr,
            .srcAccessMask = VK_ACCESS_TRANSFER_WRITE_BIT,
            .dstAccessMask = VK_ACCESS_HOST_READ_BIT,
        };
        cmdbuf.PipelineBarrier(VK_PIPELINE_STAGE_TRANSFER_BIT, VK_PIPELINE_STAGE_HOST_BIT, 0, after);
    });
    scheduler.Finish();

    readback.Invalidate();
    const std::span<const u8> mapped = readback.Mapped();
    if (mapped.size() < static_cast<size_t>(buffer_size)) {
        have_previous = false;
        return result;
    }

    const bool comparable = have_previous && previous_image == image &&
                            previous_format == guest_pixel_format;
    std::array<std::array<f32, 2>, SAMPLE_COUNT> current{};
    f32 magnitude_sum = 0.0f;
    u32 zero_samples = 0;
    u32 changed_samples = 0;

    for (u32 index = 0; index < SAMPLE_COUNT; ++index) {
        const auto vector = DecodeVector(mapped.data() + static_cast<size_t>(index) * texel_size,
                                         guest_pixel_format);
        current[index] = vector;
        if (!std::isfinite(vector[0]) || !std::isfinite(vector[1])) {
            continue;
        }
        ++result.finite_samples;
        const f32 magnitude = std::hypot(vector[0], vector[1]);
        magnitude_sum += magnitude;
        result.max_magnitude = std::max(result.max_magnitude, magnitude);
        if (magnitude <= ACTIVE_EPSILON) {
            ++zero_samples;
        } else {
            ++result.active_samples;
        }
        if (comparable) {
            const f32 dx = vector[0] - previous_samples[index][0];
            const f32 dy = vector[1] - previous_samples[index][1];
            if (std::hypot(dx, dy) > CHANGE_EPSILON) {
                ++changed_samples;
            }
        }
    }

    result.sampled = result.finite_samples != 0;
    if (result.finite_samples != 0) {
        result.zero_ratio = static_cast<f32>(zero_samples) / result.finite_samples;
        result.mean_magnitude = magnitude_sum / result.finite_samples;
    }
    if (comparable) {
        result.changed_ratio = static_cast<f32>(changed_samples) / SAMPLE_COUNT;
    }

    // Conservative diagnostic heuristic only. A plausible result is still NOT proof that
    // this target is velocity; Stage 7 deliberately leaves motion_valid false.
    result.content_plausible = result.finite_samples >= 60 &&
                               result.max_magnitude < 64.0f &&
                               result.mean_magnitude < 8.0f &&
                               result.zero_ratio > 0.01f && result.zero_ratio < 0.999f;

    previous_samples = current;
    previous_image = image;
    previous_format = guest_pixel_format;
    have_previous = true;
    return result;
}

} // namespace Vulkan
'''

write_if_changed(ROOT / "src/video_core/renderer_vulkan/present/sgsr2_motion_probe.h", probe_h)
write_if_changed(ROOT / "src/video_core/renderer_vulkan/present/sgsr2_motion_probe.cpp", probe_cpp)

runtime_inputs = ROOT / "src/video_core/renderer_vulkan/present/sgsr2_runtime_inputs.h"
insert_once(
    runtime_inputs,
    "    bool motion_probe_candidate_valid{};\n",
    "    bool motion_probe_content_sampled{};\n"
    "    bool motion_probe_content_plausible{};\n"
    "    u32 motion_probe_finite_samples{};\n"
    "    u32 motion_probe_active_samples{};\n"
    "    f32 motion_probe_zero_ratio{};\n"
    "    f32 motion_probe_mean_magnitude{};\n"
    "    f32 motion_probe_max_magnitude{};\n"
    "    f32 motion_probe_changed_ratio{};\n",
)

layer_h = ROOT / "src/video_core/renderer_vulkan/present/layer.h"
insert_once(
    layer_h,
    '#include "video_core/renderer_vulkan/present/sgsr2_runtime_inputs.h"\n',
    '#include "video_core/renderer_vulkan/present/sgsr2_motion_probe.h"\n',
)
insert_once(
    layer_h,
    "    u32 sgsr2_motion_probe_stable_frames{};\n",
    "    std::optional<SGSR2MotionProbe> sgsr2_motion_content_probe{};\n"
    "    u32 sgsr2_motion_content_probe_counter{};\n",
)

layer_cpp = ROOT / "src/video_core/renderer_vulkan/present/layer.cpp"
anchor = (
    "        // Depth is now promoted only under exact same-framebuffer correlation. Sibling\n"
    "        // color attachments are still candidates only: motion_valid remains false until\n"
    "        // their velocity encoding and temporal behavior are verified.\n"
)
addition = (
    "        if (Settings::values.moonwitch_reconstruction.GetValue() &&\n"
    "            sgsr2_inputs.motion_probe_candidate_valid &&\n"
    "            sgsr2_inputs.motion_probe_stable_frames >= 120) {\n"
    "            ++sgsr2_motion_content_probe_counter;\n"
    "            if (sgsr2_motion_content_probe_counter >= 180) {\n"
    "                sgsr2_motion_content_probe_counter = 0;\n"
    "                if (!sgsr2_motion_content_probe) {\n"
    "                    sgsr2_motion_content_probe.emplace(memory_allocator, scheduler);\n"
    "                }\n"
    "                const auto& probe = sgsr2_inputs.motion_candidates[\n"
    "                    sgsr2_inputs.motion_probe_candidate_index];\n"
    "                const auto probe_result = sgsr2_motion_content_probe->Probe(\n"
    "                    probe.image, probe.extent, probe.guest_pixel_format);\n"
    "                sgsr2_inputs.motion_probe_content_sampled = probe_result.sampled;\n"
    "                sgsr2_inputs.motion_probe_content_plausible = probe_result.content_plausible;\n"
    "                sgsr2_inputs.motion_probe_finite_samples = probe_result.finite_samples;\n"
    "                sgsr2_inputs.motion_probe_active_samples = probe_result.active_samples;\n"
    "                sgsr2_inputs.motion_probe_zero_ratio = probe_result.zero_ratio;\n"
    "                sgsr2_inputs.motion_probe_mean_magnitude = probe_result.mean_magnitude;\n"
    "                sgsr2_inputs.motion_probe_max_magnitude = probe_result.max_magnitude;\n"
    "                sgsr2_inputs.motion_probe_changed_ratio = probe_result.changed_ratio;\n"
    "                LOG_INFO(Render_Vulkan,\n"
    "                         \"Moonwitch SGSR2 motion content probe: format={} plausible={} finite={} active={} zero_ratio={:.3f} mean_mag={:.6f} max_mag={:.6f} changed={:.3f}\",\n"
    "                         probe.guest_pixel_format, probe_result.content_plausible,\n"
    "                         probe_result.finite_samples, probe_result.active_samples,\n"
    "                         probe_result.zero_ratio, probe_result.mean_magnitude,\n"
    "                         probe_result.max_magnitude, probe_result.changed_ratio);\n"
    "            }\n"
    "        } else {\n"
    "            sgsr2_motion_content_probe_counter = 0;\n"
    "        }\n\n"
)
text = layer_cpp.read_text(encoding="utf-8")
if addition.strip() not in text:
    if anchor not in text:
        raise RuntimeError("Stage 6 motion-probe anchor not found in layer.cpp")
    layer_cpp.write_text(text.replace(anchor, anchor + addition, 1), encoding="utf-8")

video_cmake = ROOT / "src/video_core/CMakeLists.txt"
insert_once(
    video_cmake,
    "    renderer_vulkan/present/sgsr2_runtime_inputs.h\n",
    "    renderer_vulkan/present/sgsr2_motion_probe.cpp\n"
    "    renderer_vulkan/present/sgsr2_motion_probe.h\n",
)

print("Moonwitch Reconstruction Stage 7 sparse motion content probe applied.")
print("A stable candidate is sampled every 180 presented frames after a 120-frame warm-up.")
print("Probe readback is diagnostic and sparse; motion_valid and SGSR2 dispatch remain disabled.")
