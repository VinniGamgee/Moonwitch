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


# Stage 5 strengthens depth semantics: a depth surface is only promoted when the exact
# color VkImage being presented was an attachment of the same Vulkan framebuffer.
# It also exposes sibling color attachments as motion-vector CANDIDATES, without ever
# marking them motion_valid until a later semantic/encoding validation step.
runtime_inputs = ROOT / "src/video_core/renderer_vulkan/present/sgsr2_runtime_inputs.h"
insert_once(
    runtime_inputs,
    "namespace Vulkan {\n",
    "\nstruct SGSR2MotionCandidate {\n"
    "    VkImage image{VK_NULL_HANDLE};\n"
    "    VkImageView view{VK_NULL_HANDLE};\n"
    "    VkExtent2D extent{};\n"
    "    VkSampleCountFlagBits samples{VK_SAMPLE_COUNT_1_BIT};\n"
    "    u32 guest_pixel_format{};\n"
    "    bool same_framebuffer_as_color{};\n"
    "};\n",
)
insert_once(
    runtime_inputs,
    "    bool depth_single_sample{};\n",
    "    bool depth_same_framebuffer_as_color{};\n"
    "    bool depth_scene_correlated{};\n",
)
insert_once(
    runtime_inputs,
    "    bool source_is_accelerated{};\n",
    "\n    std::array<SGSR2MotionCandidate, 7> motion_candidates{};\n"
    "    u32 motion_candidate_count{};\n",
)

# Record the real color attachments that belong to each cached Vulkan framebuffer.
texture_h = ROOT / "src/video_core/renderer_vulkan/vk_texture_cache.h"
insert_once(
    texture_h,
    "class Framebuffer {\n",
    "",
)
# insert_once cannot prepend using an empty addition, so replace the class anchor once.
replace_once(
    texture_h,
    "class Framebuffer {\n",
    "struct SGSR2FramebufferColorAttachmentInfo {\n"
    "    VkImage image{VK_NULL_HANDLE};\n"
    "    VkImageView view{VK_NULL_HANDLE};\n"
    "    VkExtent2D extent{};\n"
    "    VkSampleCountFlagBits samples{VK_SAMPLE_COUNT_1_BIT};\n"
    "    u32 guest_pixel_format{};\n"
    "};\n\n"
    "class Framebuffer {\n",
)
insert_once(
    texture_h,
    "    [[nodiscard]] bool HasAspectDepthBit() const noexcept {\n"
    "        return has_depth;\n"
    "    }\n",
    "\n    [[nodiscard]] bool SGSR2ContainsColorImage(VkImage image) const noexcept {\n"
    "        for (u32 index = 0; index < sgsr2_color_attachment_count; ++index) {\n"
    "            if (sgsr2_color_attachments[index].image == image) {\n"
    "                return true;\n"
    "            }\n"
    "        }\n"
    "        return false;\n"
    "    }\n\n"
    "    [[nodiscard]] std::span<const SGSR2FramebufferColorAttachmentInfo>\n"
    "    SGSR2ColorAttachments() const noexcept {\n"
    "        return {sgsr2_color_attachments.data(), sgsr2_color_attachment_count};\n"
    "    }\n",
)
insert_once(
    texture_h,
    "    std::array<VkImageSubresourceRange, 9> image_ranges{};\n",
    "    std::array<SGSR2FramebufferColorAttachmentInfo, NUM_RT> sgsr2_color_attachments{};\n"
    "    u32 sgsr2_color_attachment_count{};\n",
)

texture_cpp = ROOT / "src/video_core/renderer_vulkan/vk_texture_cache.cpp"
insert_once(
    texture_cpp,
    "    s32 num_layers = 1;\n",
    "    sgsr2_color_attachment_count = 0;\n",
)
insert_once(
    texture_cpp,
    "        samples = color_buffer->Samples();\n",
    "        const VkExtent2D sgsr2_color_extent{\n"
    "            .width = is_rescaled ? resolution.ScaleUp(color_buffer->size.width)\n"
    "                                 : color_buffer->size.width,\n"
    "            .height = is_rescaled ? resolution.ScaleUp(color_buffer->size.height)\n"
    "                                  : color_buffer->size.height,\n"
    "        };\n"
    "        sgsr2_color_attachments[sgsr2_color_attachment_count++] =\n"
    "            SGSR2FramebufferColorAttachmentInfo{\n"
    "                .image = color_buffer->ImageHandle(),\n"
    "                .view = color_buffer->RenderTarget(),\n"
    "                .extent = sgsr2_color_extent,\n"
    "                .samples = color_buffer->Samples(),\n"
    "                .guest_pixel_format = static_cast<u32>(color_buffer->format),\n"
    "            };\n",
)

# Enrich the existing Stage 4 depth candidate with exact same-framebuffer correlation
# and sibling render-target metadata. vk_rasterizer.cpp remains untouched.
rasterizer_h = ROOT / "src/video_core/renderer_vulkan/vk_rasterizer.h"
replace_once(
    rasterizer_h,
    "struct SGSR2DepthCandidateInfo {\n"
    "    VkImage image{VK_NULL_HANDLE};\n"
    "    VkImageView view{VK_NULL_HANDLE};\n"
    "    VkExtent2D extent{};\n"
    "    VkSampleCountFlagBits samples{VK_SAMPLE_COUNT_1_BIT};\n"
    "};\n",
    "struct SGSR2SiblingColorCandidateInfo {\n"
    "    VkImage image{VK_NULL_HANDLE};\n"
    "    VkImageView view{VK_NULL_HANDLE};\n"
    "    VkExtent2D extent{};\n"
    "    VkSampleCountFlagBits samples{VK_SAMPLE_COUNT_1_BIT};\n"
    "    u32 guest_pixel_format{};\n"
    "};\n\n"
    "struct SGSR2DepthCandidateInfo {\n"
    "    VkImage image{VK_NULL_HANDLE};\n"
    "    VkImageView view{VK_NULL_HANDLE};\n"
    "    VkExtent2D extent{};\n"
    "    VkSampleCountFlagBits samples{VK_SAMPLE_COUNT_1_BIT};\n"
    "    bool same_framebuffer_as_display{};\n"
    "    std::array<SGSR2SiblingColorCandidateInfo, 8> sibling_colors{};\n"
    "    u32 sibling_count{};\n"
    "};\n",
)
replace_once(
    rasterizer_h,
    "    [[nodiscard]] std::optional<SGSR2DepthCandidateInfo> GetSGSR2DepthCandidate() {\n"
    "        Framebuffer* framebuffer = texture_cache.GetFramebuffer();\n"
    "        if (!framebuffer || !framebuffer->HasAspectDepthBit() ||\n"
    "            framebuffer->SGSR2DepthImage() == VK_NULL_HANDLE ||\n"
    "            framebuffer->SGSR2DepthView() == VK_NULL_HANDLE) {\n"
    "            return std::nullopt;\n"
    "        }\n"
    "        return SGSR2DepthCandidateInfo{\n"
    "            .image = framebuffer->SGSR2DepthImage(),\n"
    "            .view = framebuffer->SGSR2DepthView(),\n"
    "            .extent = framebuffer->RenderArea(),\n"
    "            .samples = framebuffer->Samples(),\n"
    "        };\n"
    "    }\n",
    "    [[nodiscard]] std::optional<SGSR2DepthCandidateInfo>\n"
    "    GetSGSR2DepthCandidate(VkImage displayed_color_image) {\n"
    "        Framebuffer* framebuffer = texture_cache.GetFramebuffer();\n"
    "        if (!framebuffer || displayed_color_image == VK_NULL_HANDLE ||\n"
    "            !framebuffer->SGSR2ContainsColorImage(displayed_color_image) ||\n"
    "            !framebuffer->HasAspectDepthBit() ||\n"
    "            framebuffer->SGSR2DepthImage() == VK_NULL_HANDLE ||\n"
    "            framebuffer->SGSR2DepthView() == VK_NULL_HANDLE) {\n"
    "            return std::nullopt;\n"
    "        }\n"
    "        SGSR2DepthCandidateInfo result{\n"
    "            .image = framebuffer->SGSR2DepthImage(),\n"
    "            .view = framebuffer->SGSR2DepthView(),\n"
    "            .extent = framebuffer->RenderArea(),\n"
    "            .samples = framebuffer->Samples(),\n"
    "            .same_framebuffer_as_display = true,\n"
    "        };\n"
    "        for (const auto& attachment : framebuffer->SGSR2ColorAttachments()) {\n"
    "            if (attachment.image == displayed_color_image ||\n"
    "                result.sibling_count >= result.sibling_colors.size()) {\n"
    "                continue;\n"
    "            }\n"
    "            result.sibling_colors[result.sibling_count++] =\n"
    "                SGSR2SiblingColorCandidateInfo{\n"
    "                    .image = attachment.image,\n"
    "                    .view = attachment.view,\n"
    "                    .extent = attachment.extent,\n"
    "                    .samples = attachment.samples,\n"
    "                    .guest_pixel_format = attachment.guest_pixel_format,\n"
    "                };\n"
    "        }\n"
    "        return result;\n"
    "    }\n",
)

layer_cpp = ROOT / "src/video_core/renderer_vulkan/present/layer.cpp"
replace_once(
    layer_cpp,
    "    if (const auto depth_candidate = rasterizer.GetSGSR2DepthCandidate()) {\n",
    "    if (const auto depth_candidate = rasterizer.GetSGSR2DepthCandidate(source_image)) {\n",
)
insert_once(
    layer_cpp,
    "        sgsr2_inputs.depth_single_sample = depth_candidate->samples == VK_SAMPLE_COUNT_1_BIT;\n",
    "        sgsr2_inputs.depth_same_framebuffer_as_color =\n"
    "            depth_candidate->same_framebuffer_as_display;\n"
    "        sgsr2_inputs.depth_scene_correlated =\n"
    "            sgsr2_inputs.depth_candidate_valid &&\n"
    "            sgsr2_inputs.depth_same_framebuffer_as_color &&\n"
    "            sgsr2_inputs.depth_extent_matches_color &&\n"
    "            sgsr2_inputs.depth_single_sample && sgsr2_inputs.source_is_accelerated;\n"
    "        sgsr2_inputs.depth_valid = sgsr2_inputs.depth_scene_correlated;\n"
    "\n"
    "        for (u32 index = 0; index < depth_candidate->sibling_count &&\n"
    "                            sgsr2_inputs.motion_candidate_count <\n"
    "                                sgsr2_inputs.motion_candidates.size(); ++index) {\n"
    "            const auto& sibling = depth_candidate->sibling_colors[index];\n"
    "            if (sibling.image == VK_NULL_HANDLE || sibling.view == VK_NULL_HANDLE ||\n"
    "                sibling.extent.width != render_extent.width ||\n"
    "                sibling.extent.height != render_extent.height ||\n"
    "                sibling.samples != VK_SAMPLE_COUNT_1_BIT) {\n"
    "                continue;\n"
    "            }\n"
    "            auto& candidate =\n"
    "                sgsr2_inputs.motion_candidates[sgsr2_inputs.motion_candidate_count++];\n"
    "            candidate.image = sibling.image;\n"
    "            candidate.view = sibling.view;\n"
    "            candidate.extent = sibling.extent;\n"
    "            candidate.samples = sibling.samples;\n"
    "            candidate.guest_pixel_format = sibling.guest_pixel_format;\n"
    "            candidate.same_framebuffer_as_color = true;\n"
    "        }\n",
)
replace_once(
    layer_cpp,
    "        // Intentionally NOT setting depth_valid here. A technically valid Vulkan depth\n"
    "        // attachment is only a candidate until it is correlated with the displayed scene.\n",
    "        // Depth is now promoted only under exact same-framebuffer correlation. Sibling\n"
    "        // color attachments are still candidates only: motion_valid remains false until\n"
    "        // their velocity encoding and temporal behavior are verified.\n",
)

print("Moonwitch Reconstruction Stage 5 scene correlation applied.")
print("Depth promotion now requires the exact displayed color image in the same framebuffer.")
print("Sibling color render targets are exposed only as velocity candidates; motion_valid stays false.")
