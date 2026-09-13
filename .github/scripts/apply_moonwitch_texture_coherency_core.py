#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path


def replace_once(path: Path, old: str, new: str, marker: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if marker in text:
        print(f"[moonwitch-texture-coherency-core] {label}: already patched")
        return
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one anchor for {label}, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"[moonwitch-texture-coherency-core] {label}: patched")


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
    '    // Opt-in visibility guard when a GPU-modified image is consumed as a texture.\n'
    '    SwitchableSetting<bool> moonwitch_texture_coherency{\n'
    '        linkage, false, "moonwitch_texture_coherency", Category::RendererAdvanced,\n'
    '        Specialization::Default, true, true};\n\n'
    '    SwitchableSetting<bool> barrier_feedback_loops{linkage, true, "barrier_feedback_loops",\n'
    '                                                   Category::RendererAdvanced};\n',
    "moonwitch_texture_coherency",
    "register runtime/per-game setting",
)

replace_once(
    texture_cache,
    """    if (is_modification &&
        Settings::values.moonwitch_render_target_init_alias_guard.GetValue()) {
        runtime.ApplyRenderTargetInitAliasGuard(slot_images[image_id], alias_needs_visibility);
    }
}
""",
    """    if (is_modification &&
        Settings::values.moonwitch_render_target_init_alias_guard.GetValue()) {
        runtime.ApplyRenderTargetInitAliasGuard(slot_images[image_id], alias_needs_visibility);
    }
    if (!is_modification && Settings::values.moonwitch_texture_coherency.GetValue()) {
        runtime.ApplyTextureCoherency(slot_images[image_id]);
    }
}
""",
    "runtime.ApplyTextureCoherency",
    "guard GPU-modified images before texture consumption",
)

replace_once(
    vk_header,
    "    void ApplyRenderTargetInitAliasGuard(Image& image, bool alias_was_synchronized);\n",
    "    void ApplyRenderTargetInitAliasGuard(Image& image, bool alias_was_synchronized);\n\n"
    "    void ApplyTextureCoherency(Image& image);\n",
    "void ApplyTextureCoherency",
    "declare Vulkan coherency guard",
)

replace_once(
    vk_header,
    "    bool moonwitch_rt_guard_announced = false;\n",
    "    bool moonwitch_rt_guard_announced = false;\n\n"
    "    u64 moonwitch_texture_coherency_barriers = 0;\n"
    "    u32 moonwitch_texture_coherency_report_frames = 0;\n"
    "    bool moonwitch_texture_coherency_announced = false;\n",
    "moonwitch_texture_coherency_barriers",
    "store Vulkan coherency diagnostics",
)

replace_once(
    vk_header,
    """    [[nodiscard]] bool ExchangeInitialization() noexcept {
        return std::exchange(initialized, true);
    }
""",
    """    [[nodiscard]] bool ExchangeInitialization() noexcept {
        return std::exchange(initialized, true);
    }

    [[nodiscard]] bool NeedsMoonwitchTextureCoherency() const noexcept {
        return moonwitch_texture_coherent_tick != modification_tick ||
               moonwitch_texture_coherent_image != Handle();
    }

    void MarkMoonwitchTextureCoherent() noexcept {
        moonwitch_texture_coherent_tick = modification_tick;
        moonwitch_texture_coherent_image = Handle();
    }
""",
    "NeedsMoonwitchTextureCoherency",
    "track coherency per image generation and Vulkan handle",
)

replace_once(
    vk_header,
    "    bool initialized = false;\n",
    "    bool initialized = false;\n"
    "    u64 moonwitch_texture_coherent_tick = 0;\n"
    "    VkImage moonwitch_texture_coherent_image = VK_NULL_HANDLE;\n",
    "moonwitch_texture_coherent_tick = 0",
    "store per-image coherency generation",
)

replace_once(
    gl_header,
    "    void ApplyRenderTargetInitAliasGuard(Image&, bool) {}\n",
    "    void ApplyRenderTargetInitAliasGuard(Image&, bool) {}\n\n"
    "    void ApplyTextureCoherency(Image&) {}\n",
    "ApplyTextureCoherency",
    "keep OpenGL runtime interface compatible",
)

replace_once(
    vk_source,
    """        moonwitch_rt_initializations = 0;
        moonwitch_rt_alias_barriers = 0;
        moonwitch_rt_guard_report_frames = 0;
    }
}
""",
    """        moonwitch_rt_initializations = 0;
        moonwitch_rt_alias_barriers = 0;
        moonwitch_rt_guard_report_frames = 0;
    }

    if (++moonwitch_texture_coherency_report_frames >= 300) {
        if (moonwitch_texture_coherency_barriers != 0) {
            LOG_DEBUG(Render_Vulkan,
                      "Moonwitch Texture Coherency (last 300 frames): barriers={}",
                      moonwitch_texture_coherency_barriers);
        }
        moonwitch_texture_coherency_barriers = 0;
        moonwitch_texture_coherency_report_frames = 0;
    }
}
""",
    "Texture Coherency (last 300 frames)",
    "report Vulkan coherency activity",
)

replace_once(
    vk_source,
    """    ++moonwitch_rt_alias_barriers;
}
""",
    """    ++moonwitch_rt_alias_barriers;
}

void TextureCacheRuntime::ApplyTextureCoherency(Image& image) {
    if (!moonwitch_texture_coherency_announced) {
        LOG_INFO(Render_Vulkan, "Moonwitch Texture Coherency enabled");
        moonwitch_texture_coherency_announced = true;
    }
    if (False(image.flags & ImageFlagBits::GpuModified) ||
        !image.NeedsMoonwitchTextureCoherency()) {
        return;
    }

    const VkAccessFlags source_access = static_cast<VkAccessFlags>(
        VK_ACCESS_TRANSFER_WRITE_BIT | VK_ACCESS_SHADER_WRITE_BIT |
        VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT | VK_ACCESS_DEPTH_STENCIL_ATTACHMENT_WRITE_BIT);
    const VkAccessFlags destination_access = static_cast<VkAccessFlags>(
        VK_ACCESS_SHADER_READ_BIT | VK_ACCESS_SHADER_WRITE_BIT |
        VK_ACCESS_INPUT_ATTACHMENT_READ_BIT);
    const VkImageMemoryBarrier coherency_barrier{
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
    scheduler.Record([coherency_barrier](vk::CommandBuffer cmdbuf) {
        cmdbuf.PipelineBarrier(vk::PIPELINE_STAGE_GRAPHICS_COMPUTE_TRANSFER,
                               vk::PIPELINE_STAGE_GRAPHICS_COMPUTE, 0,
                               coherency_barrier);
    });
    image.MarkMoonwitchTextureCoherent();
    ++moonwitch_texture_coherency_barriers;
}
""",
    "Moonwitch Texture Coherency enabled",
    "record one targeted barrier per GPU modification",
)

print("Applied Moonwitch Texture Coherency core.")
