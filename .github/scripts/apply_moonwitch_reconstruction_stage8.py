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


# Stage 8 moves scene correlation earlier. Stage 5 only checked the framebuffer still
# bound when the display image reached Layer::ConfigureDraw; TOTK can already have moved
# through later passes by then. Keep a short history of real Vulkan framebuffers and
# a short src->dst image lineage for copies/blits/conversions, then walk backwards from
# the displayed VkImage. This remains diagnostic plumbing: motion_valid stays false.
texture_h = ROOT / "src/video_core/renderer_vulkan/vk_texture_cache.h"

insert_once(texture_h, "#include <span>\n", "#include <array>\n#include <optional>\n")

history_types = r'''
struct SGSR2SceneHistoryColorAttachment {
    VkImage image{VK_NULL_HANDLE};
    VkImageView view{VK_NULL_HANDLE};
    VkExtent2D extent{};
    VkSampleCountFlagBits samples{VK_SAMPLE_COUNT_1_BIT};
    u32 guest_pixel_format{};
};

struct SGSR2SceneHistoryEntry {
    std::array<SGSR2SceneHistoryColorAttachment, NUM_RT> colors{};
    u32 color_count{};
    VkImage depth_image{VK_NULL_HANDLE};
    VkImageView depth_view{VK_NULL_HANDLE};
    VkExtent2D depth_extent{};
    VkSampleCountFlagBits depth_samples{VK_SAMPLE_COUNT_1_BIT};
    u64 serial{};
};

struct SGSR2ImageLineageEdge {
    VkImage dst{VK_NULL_HANDLE};
    VkImage src{VK_NULL_HANDLE};
    u64 serial{};
};

struct SGSR2SceneHistoryMatch {
    SGSR2SceneHistoryEntry framebuffer{};
    VkImage matched_scene_color{VK_NULL_HANDLE};
    u32 lineage_hops{};
    bool exact_presented_color_match{};
};
'''
insert_once(texture_h, "class TextureCacheRuntime {\n", history_types + "\n")

history_methods = r'''
    void SGSR2RecordFramebuffer(std::span<ImageView*, NUM_RT> color_buffers,
                                ImageView* depth_buffer, bool is_rescaled);

    void SGSR2RecordImageLineage(VkImage dst, VkImage src);

    [[nodiscard]] std::optional<SGSR2SceneHistoryMatch>
    SGSR2FindSceneHistory(VkImage displayed_color_image);
'''
insert_once(texture_h, "    void TickFrame();\n", history_methods)

history_storage = r'''
    static constexpr size_t SGSR2_SCENE_HISTORY_CAPACITY = 96;
    static constexpr size_t SGSR2_LINEAGE_CAPACITY = 256;
    std::array<SGSR2SceneHistoryEntry, SGSR2_SCENE_HISTORY_CAPACITY> sgsr2_scene_history{};
    std::array<SGSR2ImageLineageEdge, SGSR2_LINEAGE_CAPACITY> sgsr2_image_lineage{};
    size_t sgsr2_scene_history_head{};
    size_t sgsr2_scene_history_count{};
    size_t sgsr2_lineage_head{};
    size_t sgsr2_lineage_count{};
    u64 sgsr2_scene_serial{};
    u32 sgsr2_history_query_counter{};
'''
insert_once(
    texture_h,
    "    std::vector<std::pair<u64, ResolveShadow>> pending_resolve_shadows;\n",
    history_storage,
)

texture_cpp = ROOT / "src/video_core/renderer_vulkan/vk_texture_cache.cpp"

history_impl = r'''
void TextureCacheRuntime::SGSR2RecordFramebuffer(
    std::span<ImageView*, NUM_RT> color_buffers, ImageView* depth_buffer, bool is_rescaled) {
    if (!Settings::values.moonwitch_reconstruction.GetValue() || depth_buffer == nullptr) {
        return;
    }

    SGSR2SceneHistoryEntry entry{};
    const auto& scale = resolution;
    for (ImageView* color : color_buffers) {
        if (color == nullptr || entry.color_count >= entry.colors.size()) {
            continue;
        }
        auto& dst = entry.colors[entry.color_count++];
        dst.image = color->ImageHandle();
        dst.view = color->RenderTarget();
        dst.extent = {
            .width = is_rescaled ? scale.ScaleUp(color->size.width) : color->size.width,
            .height = is_rescaled ? scale.ScaleUp(color->size.height) : color->size.height,
        };
        dst.samples = color->Samples();
        dst.guest_pixel_format = static_cast<u32>(color->format);
    }
    if (entry.color_count == 0) {
        return;
    }

    entry.depth_image = depth_buffer->ImageHandle();
    entry.depth_view = depth_buffer->DepthView();
    entry.depth_extent = {
        .width = is_rescaled ? scale.ScaleUp(depth_buffer->size.width) : depth_buffer->size.width,
        .height = is_rescaled ? scale.ScaleUp(depth_buffer->size.height) : depth_buffer->size.height,
    };
    entry.depth_samples = depth_buffer->Samples();
    if (entry.depth_image == VK_NULL_HANDLE || entry.depth_view == VK_NULL_HANDLE) {
        return;
    }

    entry.serial = ++sgsr2_scene_serial;
    sgsr2_scene_history[sgsr2_scene_history_head] = entry;
    sgsr2_scene_history_head = (sgsr2_scene_history_head + 1) % SGSR2_SCENE_HISTORY_CAPACITY;
    sgsr2_scene_history_count =
        std::min(sgsr2_scene_history_count + 1, SGSR2_SCENE_HISTORY_CAPACITY);
}

void TextureCacheRuntime::SGSR2RecordImageLineage(VkImage dst, VkImage src) {
    if (!Settings::values.moonwitch_reconstruction.GetValue() || dst == VK_NULL_HANDLE ||
        src == VK_NULL_HANDLE || dst == src) {
        return;
    }
    SGSR2ImageLineageEdge edge{
        .dst = dst,
        .src = src,
        .serial = ++sgsr2_scene_serial,
    };
    sgsr2_image_lineage[sgsr2_lineage_head] = edge;
    sgsr2_lineage_head = (sgsr2_lineage_head + 1) % SGSR2_LINEAGE_CAPACITY;
    sgsr2_lineage_count = std::min(sgsr2_lineage_count + 1, SGSR2_LINEAGE_CAPACITY);
}

std::optional<SGSR2SceneHistoryMatch>
TextureCacheRuntime::SGSR2FindSceneHistory(VkImage displayed_color_image) {
    if (!Settings::values.moonwitch_reconstruction.GetValue() ||
        displayed_color_image == VK_NULL_HANDLE) {
        return std::nullopt;
    }

    auto find_framebuffer = [this](VkImage image, u32 hops)
        -> std::optional<SGSR2SceneHistoryMatch> {
        for (size_t age = 0; age < sgsr2_scene_history_count; ++age) {
            const size_t index =
                (sgsr2_scene_history_head + SGSR2_SCENE_HISTORY_CAPACITY - 1 - age) %
                SGSR2_SCENE_HISTORY_CAPACITY;
            const auto& entry = sgsr2_scene_history[index];
            for (u32 color_index = 0; color_index < entry.color_count; ++color_index) {
                if (entry.colors[color_index].image != image) {
                    continue;
                }
                return SGSR2SceneHistoryMatch{
                    .framebuffer = entry,
                    .matched_scene_color = image,
                    .lineage_hops = hops,
                    .exact_presented_color_match = hops == 0,
                };
            }
        }
        return std::nullopt;
    };

    VkImage current = displayed_color_image;
    std::array<VkImage, 9> visited{};
    visited[0] = current;

    for (u32 hops = 0; hops <= 8; ++hops) {
        if (const auto match = find_framebuffer(current, hops)) {
            return match;
        }
        if (hops == 8) {
            break;
        }

        VkImage parent = VK_NULL_HANDLE;
        u64 newest_serial = 0;
        for (size_t age = 0; age < sgsr2_lineage_count; ++age) {
            const size_t index =
                (sgsr2_lineage_head + SGSR2_LINEAGE_CAPACITY - 1 - age) %
                SGSR2_LINEAGE_CAPACITY;
            const auto& edge = sgsr2_image_lineage[index];
            if (edge.dst == current && edge.serial >= newest_serial) {
                parent = edge.src;
                newest_serial = edge.serial;
            }
        }
        if (parent == VK_NULL_HANDLE) {
            break;
        }

        bool cycle = false;
        for (u32 index = 0; index <= hops; ++index) {
            if (visited[index] == parent) {
                cycle = true;
                break;
            }
        }
        if (cycle) {
            break;
        }
        current = parent;
        visited[hops + 1] = current;
    }

    ++sgsr2_history_query_counter;
    if (sgsr2_history_query_counter % 300 == 0) {
        LOG_INFO(Render_Vulkan,
                 "Moonwitch SGSR2 scene history: no match after reverse walk; framebuffers={} lineage={}",
                 sgsr2_scene_history_count, sgsr2_lineage_count);
    }
    return std::nullopt;
}
'''
insert_once(
    texture_cpp,
    "void TextureCacheRuntime::Finish() {\n    scheduler.Finish();\n}\n",
    "\n" + history_impl,
)

replace_once(
    texture_cpp,
    "        .layers = static_cast<u32>((std::max)(num_layers, 1)),\n"
    "    });\n"
    "}\n\n"
    "void Framebuffer::MarkResolveShadowsUpToDate() const {\n",
    "        .layers = static_cast<u32>((std::max)(num_layers, 1)),\n"
    "    });\n"
    "    runtime.SGSR2RecordFramebuffer(color_buffers, depth_buffer, is_rescaled);\n"
    "}\n\n"
    "void Framebuffer::MarkResolveShadowsUpToDate() const {\n",
)

# Track color-image lineage in common copy/blit/convert paths.
insert_once(
    texture_cpp,
    "    const VkImageAspectFlags aspect_mask = ImageAspectMask(src.format);\n",
    "    if (aspect_mask == VK_IMAGE_ASPECT_COLOR_BIT) {\n"
    "        SGSR2RecordImageLineage(dst.ImageHandle(), src.ImageHandle());\n"
    "    }\n",
)

insert_once(
    texture_cpp,
    "    const VkImageAspectFlags dst_aspect_mask = dst.AspectMask();\n"
    "    const VkImageAspectFlags src_aspect_mask = src.AspectMask();\n",
    "    if (dst_aspect_mask == VK_IMAGE_ASPECT_COLOR_BIT &&\n"
    "        src_aspect_mask == VK_IMAGE_ASPECT_COLOR_BIT) {\n"
    "        SGSR2RecordImageLineage(dst.Handle(), src.Handle());\n"
    "    }\n",
)

insert_once(
    texture_cpp,
    "    ASSERT(aspect_mask == src.AspectMask());\n",
    "    if (aspect_mask == VK_IMAGE_ASPECT_COLOR_BIT) {\n"
    "        SGSR2RecordImageLineage(dst.Handle(), src.Handle());\n"
    "    }\n",
)

insert_once(
    texture_cpp,
    "void TextureCacheRuntime::CopyImageMSAA(Image& dst, Image& src,\n"
    "                                        std::span<const VideoCommon::ImageCopy> copies) {\n",
    "    if (dst.AspectMask() == VK_IMAGE_ASPECT_COLOR_BIT &&\n"
    "        src.AspectMask() == VK_IMAGE_ASPECT_COLOR_BIT) {\n"
    "        SGSR2RecordImageLineage(dst.Handle(), src.Handle());\n"
    "    }\n",
)

insert_once(
    texture_cpp,
    "void TextureCacheRuntime::ConvertImage(Framebuffer* dst, ImageView& dst_view, ImageView& src_view) {\n",
    "    if (VideoCore::Surface::GetFormatType(dst_view.format) == SurfaceType::ColorTexture &&\n"
    "        VideoCore::Surface::GetFormatType(src_view.format) == SurfaceType::ColorTexture) {\n"
    "        SGSR2RecordImageLineage(dst_view.ImageHandle(), src_view.ImageHandle());\n"
    "    }\n",
)

rasterizer_h = ROOT / "src/video_core/renderer_vulkan/vk_rasterizer.h"
insert_once(
    rasterizer_h,
    "    bool same_framebuffer_as_display{};\n",
    "    bool scene_history_correlated{};\n"
    "    u32 lineage_hops{};\n",
)

old_query = r'''    [[nodiscard]] std::optional<SGSR2DepthCandidateInfo>
    GetSGSR2DepthCandidate(VkImage displayed_color_image) {
        Framebuffer* framebuffer = texture_cache.GetFramebuffer();
        if (!framebuffer || displayed_color_image == VK_NULL_HANDLE ||
            !framebuffer->SGSR2ContainsColorImage(displayed_color_image) ||
            !framebuffer->HasAspectDepthBit() ||
            framebuffer->SGSR2DepthImage() == VK_NULL_HANDLE ||
            framebuffer->SGSR2DepthView() == VK_NULL_HANDLE) {
            return std::nullopt;
        }
        SGSR2DepthCandidateInfo result{
            .image = framebuffer->SGSR2DepthImage(),
            .view = framebuffer->SGSR2DepthView(),
            .extent = framebuffer->RenderArea(),
            .samples = framebuffer->Samples(),
            .same_framebuffer_as_display = true,
        };
        for (const auto& attachment : framebuffer->SGSR2ColorAttachments()) {
            if (attachment.image == displayed_color_image ||
                result.sibling_count >= result.sibling_colors.size()) {
                continue;
            }
            result.sibling_colors[result.sibling_count++] =
                SGSR2SiblingColorCandidateInfo{
                    .image = attachment.image,
                    .view = attachment.view,
                    .extent = attachment.extent,
                    .samples = attachment.samples,
                    .guest_pixel_format = attachment.guest_pixel_format,
                };
        }
        return result;
    }
'''
new_query = r'''    [[nodiscard]] std::optional<SGSR2DepthCandidateInfo>
    GetSGSR2DepthCandidate(VkImage displayed_color_image) {
        const auto history = texture_cache_runtime.SGSR2FindSceneHistory(displayed_color_image);
        if (!history || history->framebuffer.depth_image == VK_NULL_HANDLE ||
            history->framebuffer.depth_view == VK_NULL_HANDLE) {
            return std::nullopt;
        }
        SGSR2DepthCandidateInfo result{
            .image = history->framebuffer.depth_image,
            .view = history->framebuffer.depth_view,
            .extent = history->framebuffer.depth_extent,
            .samples = history->framebuffer.depth_samples,
            .same_framebuffer_as_display = history->exact_presented_color_match,
            .scene_history_correlated = true,
            .lineage_hops = history->lineage_hops,
        };
        for (u32 index = 0; index < history->framebuffer.color_count &&
                            result.sibling_count < result.sibling_colors.size(); ++index) {
            const auto& attachment = history->framebuffer.colors[index];
            if (attachment.image == history->matched_scene_color) {
                continue;
            }
            result.sibling_colors[result.sibling_count++] =
                SGSR2SiblingColorCandidateInfo{
                    .image = attachment.image,
                    .view = attachment.view,
                    .extent = attachment.extent,
                    .samples = attachment.samples,
                    .guest_pixel_format = attachment.guest_pixel_format,
                };
        }
        return result;
    }
'''
replace_once(rasterizer_h, old_query, new_query)

runtime_inputs = ROOT / "src/video_core/renderer_vulkan/present/sgsr2_runtime_inputs.h"
insert_once(
    runtime_inputs,
    "    bool depth_scene_correlated{};\n",
    "    bool depth_scene_history_correlated{};\n"
    "    u32 depth_lineage_hops{};\n",
)

layer_h = ROOT / "src/video_core/renderer_vulkan/present/layer.h"
insert_once(
    layer_h,
    "    u32 sgsr2_motion_content_probe_counter{};\n",
    "    VkImage sgsr2_history_last_depth{VK_NULL_HANDLE};\n"
    "    u32 sgsr2_history_last_hops{~0u};\n",
)

layer_cpp = ROOT / "src/video_core/renderer_vulkan/present/layer.cpp"
old_depth_logic = r'''        sgsr2_inputs.depth_same_framebuffer_as_color =
            depth_candidate->same_framebuffer_as_display;
        sgsr2_inputs.depth_scene_correlated =
            sgsr2_inputs.depth_candidate_valid &&
            sgsr2_inputs.depth_same_framebuffer_as_color &&
            sgsr2_inputs.depth_extent_matches_color &&
            sgsr2_inputs.depth_single_sample && sgsr2_inputs.source_is_accelerated;
        sgsr2_inputs.depth_valid = sgsr2_inputs.depth_scene_correlated;
'''
new_depth_logic = r'''        sgsr2_inputs.depth_same_framebuffer_as_color =
            depth_candidate->same_framebuffer_as_display;
        sgsr2_inputs.depth_scene_history_correlated =
            depth_candidate->scene_history_correlated;
        sgsr2_inputs.depth_lineage_hops = depth_candidate->lineage_hops;
        sgsr2_inputs.depth_scene_correlated =
            sgsr2_inputs.depth_candidate_valid &&
            (sgsr2_inputs.depth_same_framebuffer_as_color ||
             sgsr2_inputs.depth_scene_history_correlated) &&
            sgsr2_inputs.depth_extent_matches_color &&
            sgsr2_inputs.depth_single_sample && sgsr2_inputs.source_is_accelerated;
        sgsr2_inputs.depth_valid = sgsr2_inputs.depth_scene_correlated;

        if (sgsr2_inputs.depth_scene_history_correlated &&
            (sgsr2_history_last_depth != depth_candidate->image ||
             sgsr2_history_last_hops != depth_candidate->lineage_hops)) {
            sgsr2_history_last_depth = depth_candidate->image;
            sgsr2_history_last_hops = depth_candidate->lineage_hops;
            LOG_INFO(Render_Vulkan,
                     "Moonwitch SGSR2 scene history match: lineage_hops={} extent={}x{} siblings={}",
                     depth_candidate->lineage_hops, depth_candidate->extent.width,
                     depth_candidate->extent.height, depth_candidate->sibling_count);
        }
'''
replace_once(layer_cpp, old_depth_logic, new_depth_logic)

print("Moonwitch Reconstruction Stage 8 scene-history correlation applied.")
print("Recent framebuffers and color-image lineage can now be walked backwards from presentation.")
print("motion_valid remains false; SGSR2 temporal dispatch is still gated.")
