#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path


def replace_once(path: Path, old: str, new: str, marker: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if marker in text:
        print(f"[moonwitch-rt-guard-core] {label}: already patched")
        return
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one anchor for {label}, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"[moonwitch-rt-guard-core] {label}: patched")


root = Path(".")
settings_h = root / "src/common/settings.h"
texture_cache = root / "src/video_core/texture_cache/texture_cache.h"
vk_header = root / "src/video_core/renderer_vulkan/vk_texture_cache.h"
vk_source = root / "src/video_core/renderer_vulkan/vk_texture_cache.cpp"
gl_header = root / "src/video_core/renderer_opengl/gl_texture_cache.h"


replace_once(
    settings_h,
    '    SwitchableSetting<bool> barrier_feedback_loops{linkage, true, "barrier_feedback_loops",\n'
    '                                                   Category::RendererAdvanced};\n',
    '    // Opt-in guard for freshly allocated Vulkan render targets and synchronized aliases.\n'
    '    SwitchableSetting<bool> moonwitch_render_target_init_alias_guard{\n'
    '        linkage, false, "moonwitch_render_target_init_alias_guard",\n'
    '        Category::RendererAdvanced, Specialization::Default, true, true};\n\n'
    '    SwitchableSetting<bool> barrier_feedback_loops{linkage, true, "barrier_feedback_loops",\n'
    '                                                   Category::RendererAdvanced};\n',
    "moonwitch_render_target_init_alias_guard",
    "register runtime/per-game setting",
)

replace_once(
    texture_cache,
    """void TextureCache<P>::PrepareImageView(ImageViewId image_view_id, bool is_modification,
                                       bool invalidate) {
    if (!image_view_id) {
        return;
    }
    const ImageViewBase& image_view = slot_image_views[image_view_id];
    if (image_view.IsBuffer()) {
        return;
    }
    PrepareImage(image_view.image_id, is_modification, invalidate);
}
""",
    """void TextureCache<P>::PrepareImageView(ImageViewId image_view_id, bool is_modification,
                                       bool invalidate) {
    if (!image_view_id) {
        return;
    }
    const ImageViewBase& image_view = slot_image_views[image_view_id];
    if (image_view.IsBuffer()) {
        return;
    }

    const ImageId image_id = image_view.image_id;
    const Image& image_before_prepare = slot_images[image_id];
    const bool alias_needs_visibility =
        is_modification && !invalidate &&
        std::ranges::any_of(image_before_prepare.aliased_images, [this, &image_before_prepare](
                                                                  const AliasedImage& aliased) {
            return image_before_prepare.modification_tick <
                   slot_images[aliased.id].modification_tick;
        });

    PrepareImage(image_id, is_modification, invalidate);
    if (is_modification &&
        Settings::values.moonwitch_render_target_init_alias_guard.GetValue()) {
        runtime.ApplyRenderTargetInitAliasGuard(slot_images[image_id], alias_needs_visibility);
    }
}
""",
    "ApplyRenderTargetInitAliasGuard",
    "guard render targets after alias synchronization",
)

replace_once(
    vk_header,
    "    void TransitionImageLayout(Image& image);\n",
    "    bool TransitionImageLayout(Image& image);\n\n"
    "    void ApplyRenderTargetInitAliasGuard(Image& image, bool alias_was_synchronized);\n",
    "ApplyRenderTargetInitAliasGuard",
    "declare Vulkan guard",
)

replace_once(
    vk_header,
    "    std::vector<std::pair<u64, ResolveShadow>> pending_resolve_shadows;\n",
    "    std::vector<std::pair<u64, ResolveShadow>> pending_resolve_shadows;\n\n"
    "    u64 moonwitch_rt_initializations = 0;\n"
    "    u64 moonwitch_rt_alias_barriers = 0;\n"
    "    u32 moonwitch_rt_guard_report_frames = 0;\n"
    "    bool moonwitch_rt_guard_announced = false;\n",
    "moonwitch_rt_initializations",
    "store Vulkan guard diagnostics",
)

replace_once(
    gl_header,
    "    void TransitionImageLayout(Image& image) {}\n",
    "    bool TransitionImageLayout(Image& image) {\n"
    "        return false;\n"
    "    }\n\n"
    "    void ApplyRenderTargetInitAliasGuard(Image&, bool) {}\n",
    "ApplyRenderTargetInitAliasGuard",
    "keep OpenGL runtime interface compatible",
)

replace_once(
    vk_source,
    """void TextureCacheRuntime::TickFrame() {
    static constexpr u32 MAX_UNUSED_SCRATCH_FRAMES = 60;
    std::erase_if(msaa_scratch_images, [this](MsaaScratchImage& scratch) {
        if (!scheduler.IsFree(scratch.tick)) {
            scratch.unused_frames = 0;
            return false;
        }
        return ++scratch.unused_frames > MAX_UNUSED_SCRATCH_FRAMES;
    });
    std::erase_if(pending_resolve_shadows, [this](const auto& pending) {
        return scheduler.IsFree(pending.first);
    });
}
""",
    """void TextureCacheRuntime::TickFrame() {
    static constexpr u32 MAX_UNUSED_SCRATCH_FRAMES = 60;
    std::erase_if(msaa_scratch_images, [this](MsaaScratchImage& scratch) {
        if (!scheduler.IsFree(scratch.tick)) {
            scratch.unused_frames = 0;
            return false;
        }
        return ++scratch.unused_frames > MAX_UNUSED_SCRATCH_FRAMES;
    });
    std::erase_if(pending_resolve_shadows, [this](const auto& pending) {
        return scheduler.IsFree(pending.first);
    });

    if (++moonwitch_rt_guard_report_frames >= 300) {
        if (moonwitch_rt_initializations != 0 || moonwitch_rt_alias_barriers != 0) {
            LOG_DEBUG(Render_Vulkan,
                      "Moonwitch RT Init/Alias Guard (last 300 frames): initialized={}, "
                      "alias_barriers={}",
                      moonwitch_rt_initializations, moonwitch_rt_alias_barriers);
        }
        moonwitch_rt_initializations = 0;
        moonwitch_rt_alias_barriers = 0;
        moonwitch_rt_guard_report_frames = 0;
    }
}
""",
    "RT Init/Alias Guard (last 300 frames)",
    "report Vulkan guard activity",
)

replace_once(
    vk_source,
    """void TextureCacheRuntime::TransitionImageLayout(Image& image) {
    if (!image.ExchangeInitialization()) {
        VkImageMemoryBarrier barrier{
            .sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER,
            .pNext = nullptr,
            .srcAccessMask = VK_ACCESS_NONE,
            .dstAccessMask = VK_ACCESS_MEMORY_READ_BIT | VK_ACCESS_MEMORY_WRITE_BIT,
            .oldLayout = VK_IMAGE_LAYOUT_UNDEFINED,
            .newLayout = VK_IMAGE_LAYOUT_GENERAL,
            .srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
            .dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
            .image = image.Handle(),
            .subresourceRange{
                .aspectMask = image.AspectMask(),
                .baseMipLevel = 0,
                .levelCount = VK_REMAINING_MIP_LEVELS,
                .baseArrayLayer = 0,
                .layerCount = VK_REMAINING_ARRAY_LAYERS,
            },
        };
        scheduler.RequestOutsideRenderPassOperationContext();
        scheduler.Record([barrier](vk::CommandBuffer cmdbuf) {
            cmdbuf.PipelineBarrier(vk::PIPELINE_STAGE_GRAPHICS_COMPUTE,
                                   vk::PIPELINE_STAGE_GRAPHICS_COMPUTE, 0, barrier);
        });
    }
}
""",
    """bool TextureCacheRuntime::TransitionImageLayout(Image& image) {
    if (image.ExchangeInitialization()) {
        return false;
    }
    const VkImageMemoryBarrier barrier{
        .sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER,
        .pNext = nullptr,
        .srcAccessMask = VK_ACCESS_NONE,
        .dstAccessMask = VK_ACCESS_MEMORY_READ_BIT | VK_ACCESS_MEMORY_WRITE_BIT,
        .oldLayout = VK_IMAGE_LAYOUT_UNDEFINED,
        .newLayout = VK_IMAGE_LAYOUT_GENERAL,
        .srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
        .dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
        .image = image.Handle(),
        .subresourceRange{
            .aspectMask = image.AspectMask(),
            .baseMipLevel = 0,
            .levelCount = VK_REMAINING_MIP_LEVELS,
            .baseArrayLayer = 0,
            .layerCount = VK_REMAINING_ARRAY_LAYERS,
        },
    };
    scheduler.RequestOutsideRenderPassOperationContext();
    scheduler.Record([barrier](vk::CommandBuffer cmdbuf) {
        cmdbuf.PipelineBarrier(vk::PIPELINE_STAGE_GRAPHICS_COMPUTE,
                               vk::PIPELINE_STAGE_GRAPHICS_COMPUTE, 0, barrier);
    });
    return true;
}

void TextureCacheRuntime::ApplyRenderTargetInitAliasGuard(Image& image,
                                                           bool alias_was_synchronized) {
    if (!moonwitch_rt_guard_announced) {
        LOG_INFO(Render_Vulkan, "Moonwitch Render Target Init/Alias Guard enabled");
        moonwitch_rt_guard_announced = true;
    }

    // Initialize only Vulkan layout/state. Pixel contents remain owned by guest uploads or clears.
    if (TransitionImageLayout(image)) {
        ++moonwitch_rt_initializations;
    }
    if (!alias_was_synchronized) {
        return;
    }

    const VkAccessFlags source_access = static_cast<VkAccessFlags>(
        VK_ACCESS_TRANSFER_WRITE_BIT | VK_ACCESS_SHADER_WRITE_BIT |
        VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT | VK_ACCESS_DEPTH_STENCIL_ATTACHMENT_WRITE_BIT);
    const VkAccessFlags destination_access = static_cast<VkAccessFlags>(
        VK_ACCESS_COLOR_ATTACHMENT_READ_BIT | VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT |
        VK_ACCESS_DEPTH_STENCIL_ATTACHMENT_READ_BIT |
        VK_ACCESS_DEPTH_STENCIL_ATTACHMENT_WRITE_BIT);
    const VkPipelineStageFlags destination_stages = static_cast<VkPipelineStageFlags>(
        VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT |
        VK_PIPELINE_STAGE_EARLY_FRAGMENT_TESTS_BIT | VK_PIPELINE_STAGE_LATE_FRAGMENT_TESTS_BIT);
    const VkImageMemoryBarrier alias_barrier{
        .sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER,
        .pNext = nullptr,
        .srcAccessMask = source_access,
        .dstAccessMask = destination_access,
        .oldLayout = VK_IMAGE_LAYOUT_GENERAL,
        .newLayout = VK_IMAGE_LAYOUT_GENERAL,
        .srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
        .dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
        .image = image.Handle(),
        .subresourceRange{
            .aspectMask = image.AspectMask(),
            .baseMipLevel = 0,
            .levelCount = VK_REMAINING_MIP_LEVELS,
            .baseArrayLayer = 0,
            .layerCount = VK_REMAINING_ARRAY_LAYERS,
        },
    };
    scheduler.RequestOutsideRenderPassOperationContext();
    scheduler.Record([alias_barrier, destination_stages](vk::CommandBuffer cmdbuf) {
        cmdbuf.PipelineBarrier(vk::PIPELINE_STAGE_GRAPHICS_COMPUTE_TRANSFER,
                               destination_stages, 0, alias_barrier);
    });
    ++moonwitch_rt_alias_barriers;
}
""",
    "Moonwitch Render Target Init/Alias Guard enabled",
    "initialize render-target layouts and guard synchronized aliases",
)

print("Applied Moonwitch Render Target Init/Alias Guard core.")
