#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path


def replace_once(path: Path, old: str, new: str, marker: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if marker in text:
        print(f"[moonwitch-safe-barriers-core] {label}: already patched")
        return
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one anchor for {label}, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"[moonwitch-safe-barriers-core] {label}: patched")


root = Path(".")
settings_h = root / "src/common/settings.h"
rasterizer_h = root / "src/video_core/renderer_vulkan/vk_rasterizer.h"
rasterizer_cpp = root / "src/video_core/renderer_vulkan/vk_rasterizer.cpp"


replace_once(
    settings_h,
    '    SwitchableSetting<bool> barrier_feedback_loops{linkage, true, "barrier_feedback_loops",\n'
    '                                                   Category::RendererAdvanced};\n',
    '    // Optional Vulkan memory dependencies for games or drivers that expose stale render\n'
    '    // targets. Mode 0 preserves upstream behavior; 1 is scoped; 2 is global/strict.\n'
    '    SwitchableSetting<int, true> moonwitch_safe_gpu_barriers_mode{\n'
    '        linkage, 0, 0, 2, "moonwitch_safe_gpu_barriers_mode",\n'
    '        Category::RendererAdvanced, Specialization::Default, true, true};\n\n'
    '    SwitchableSetting<bool> barrier_feedback_loops{linkage, true, "barrier_feedback_loops",\n'
    '                                                   Category::RendererAdvanced};\n',
    "moonwitch_safe_gpu_barriers_mode",
    "register per-game barrier mode",
)

replace_once(
    rasterizer_h,
    "    void FlushWork();\n",
    "    void FlushWork();\n\n"
    "    void ApplyMoonwitchGpuBarrier(bool tiled);\n",
    "ApplyMoonwitchGpuBarrier",
    "declare barrier helper",
)

replace_once(
    rasterizer_h,
    "    u32 draw_counter = 0;\n",
    "    u64 moonwitch_fragment_barrier_count = 0;\n"
    "    u64 moonwitch_tiled_barrier_count = 0;\n"
    "    u32 moonwitch_barrier_report_frames = 0;\n"
    "    s32 moonwitch_last_barrier_mode = -1;\n\n"
    "    u32 draw_counter = 0;\n",
    "moonwitch_fragment_barrier_count",
    "store diagnostics counters",
)

replace_once(
    rasterizer_cpp,
    """void RasterizerVulkan::FragmentBarrier() {
    // We already put barriers when a render pass finishes
    scheduler.RequestOutsideRenderPassOperationContext();
}

void RasterizerVulkan::TiledCacheBarrier() {
    // TODO: Implementing tiled barriers requires rewriting a good chunk of the Vulkan backend
}
""",
    """void RasterizerVulkan::ApplyMoonwitchGpuBarrier(bool tiled) {
    const s32 mode = std::clamp(
        Settings::values.moonwitch_safe_gpu_barriers_mode.GetValue(), 0, 2);

    if (mode != moonwitch_last_barrier_mode) {
        LOG_INFO(Render_Vulkan, "Moonwitch Safe GPU Barriers mode: {}", mode);
        moonwitch_last_barrier_mode = mode;
    }
    if (mode == 0) {
        return;
    }

    scheduler.RequestOutsideRenderPassOperationContext();
    const VkDependencyFlags dependency_flags =
        mode == 1 && tiled ? VK_DEPENDENCY_BY_REGION_BIT : VkDependencyFlags{};

    scheduler.Record([mode, dependency_flags](vk::CommandBuffer cmdbuf) {
        const bool strict = mode >= 2;
        const VkAccessFlags destination_access =
            strict ? static_cast<VkAccessFlags>(VK_ACCESS_MEMORY_READ_BIT |
                                                VK_ACCESS_MEMORY_WRITE_BIT)
                   : static_cast<VkAccessFlags>(VK_ACCESS_MEMORY_READ_BIT);
        const VkMemoryBarrier memory_barrier{
            .sType = VK_STRUCTURE_TYPE_MEMORY_BARRIER,
            .pNext = nullptr,
            .srcAccessMask = VK_ACCESS_MEMORY_WRITE_BIT,
            .dstAccessMask = destination_access,
        };
        const VkPipelineStageFlags stages =
            strict ? VkPipelineStageFlags{VK_PIPELINE_STAGE_ALL_COMMANDS_BIT}
                   : vk::PIPELINE_STAGE_GRAPHICS_COMPUTE_TRANSFER;
        cmdbuf.PipelineBarrier(stages, stages, dependency_flags, memory_barrier);
    });

    if (tiled) {
        ++moonwitch_tiled_barrier_count;
    } else {
        ++moonwitch_fragment_barrier_count;
    }
}

void RasterizerVulkan::FragmentBarrier() {
    // Preserve the upstream render-pass boundary even when the Moonwitch mode is disabled.
    scheduler.RequestOutsideRenderPassOperationContext();
    ApplyMoonwitchGpuBarrier(false);
}

void RasterizerVulkan::TiledCacheBarrier() {
    // Upstream leaves this unimplemented on Vulkan. The opt-in modes approximate the guest's
    // tile-cache visibility requirement without forcing a CPU/GPU WaitIdle.
    ApplyMoonwitchGpuBarrier(true);
}
""",
    "Moonwitch Safe GPU Barriers mode:",
    "implement safe and strict Vulkan barriers",
)

replace_once(
    rasterizer_cpp,
    """void RasterizerVulkan::TickFrame() {
    draw_counter = 0;
    guest_descriptor_queue.TickFrame();
""",
    """void RasterizerVulkan::TickFrame() {
    draw_counter = 0;

    if (++moonwitch_barrier_report_frames >= 300) {
        if (moonwitch_fragment_barrier_count != 0 || moonwitch_tiled_barrier_count != 0) {
            LOG_DEBUG(Render_Vulkan,
                      "Moonwitch Safe GPU Barriers (last 300 frames): fragment={}, tiled={}",
                      moonwitch_fragment_barrier_count, moonwitch_tiled_barrier_count);
        }
        moonwitch_fragment_barrier_count = 0;
        moonwitch_tiled_barrier_count = 0;
        moonwitch_barrier_report_frames = 0;
    }

    guest_descriptor_queue.TickFrame();
""",
    "last 300 frames",
    "report barrier activity",
)

print("Applied Moonwitch Safe GPU Barriers core: default, safe and strict modes.")
