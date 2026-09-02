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


# 1) Extend the runtime contract with a genuine depth candidate.  It is intentionally
#    distinct from depth_valid: Stage 4 only exposes a real Vulkan depth attachment and
#    records whether its technical properties match the displayed color surface.
runtime_inputs = ROOT / "src/video_core/renderer_vulkan/present/sgsr2_runtime_inputs.h"
insert_once(
    runtime_inputs,
    "    VkImageView depth_view{VK_NULL_HANDLE};\n",
    "    VkExtent2D depth_extent{};\n"
    "    VkSampleCountFlagBits depth_samples{VK_SAMPLE_COUNT_1_BIT};\n"
    "    bool depth_candidate_valid{};\n"
    "    bool depth_extent_matches_color{};\n"
    "    bool depth_single_sample{};\n",
)

# 2) Preserve the actual depth attachment image/view inside the Vulkan framebuffer.
#    Framebuffer already receives the real ImageView* depth_buffer; this merely exposes
#    those handles without changing rendering behavior.
texture_h = ROOT / "src/video_core/renderer_vulkan/vk_texture_cache.h"
insert_once(
    texture_h,
    "    [[nodiscard]] bool HasAspectDepthBit() const noexcept {\n"
    "        return has_depth;\n"
    "    }\n",
    "\n    [[nodiscard]] VkImage SGSR2DepthImage() const noexcept {\n"
    "        return sgsr2_depth_image;\n"
    "    }\n\n"
    "    [[nodiscard]] VkImageView SGSR2DepthView() const noexcept {\n"
    "        return sgsr2_depth_view;\n"
    "    }\n",
)
insert_once(
    texture_h,
    "    std::array<VkImageSubresourceRange, 9> image_ranges{};\n",
    "    VkImage sgsr2_depth_image{VK_NULL_HANDLE};\n"
    "    VkImageView sgsr2_depth_view{VK_NULL_HANDLE};\n",
)

texture_cpp = ROOT / "src/video_core/renderer_vulkan/vk_texture_cache.cpp"
replace_once(
    texture_cpp,
    "    VkImage depth_image = VK_NULL_HANDLE;\n"
    "    VkImageAspectFlags depth_aspect_mask = 0;\n"
    "    if (depth_buffer) {\n",
    "    VkImage depth_image = VK_NULL_HANDLE;\n"
    "    VkImageAspectFlags depth_aspect_mask = 0;\n"
    "    sgsr2_depth_image = VK_NULL_HANDLE;\n"
    "    sgsr2_depth_view = VK_NULL_HANDLE;\n"
    "    if (depth_buffer) {\n",
)
insert_once(
    texture_cpp,
    "        depth_aspect_mask = subresource_range.aspectMask;\n",
    "        sgsr2_depth_image = depth_buffer->ImageHandle();\n"
    "        sgsr2_depth_view = depth_buffer->DepthView();\n",
)

# 3) Expose the currently bound Vulkan framebuffer's depth attachment through the
#    RasterizerVulkan header only.  vk_rasterizer.cpp remains byte-for-byte untouched.
rasterizer_h = ROOT / "src/video_core/renderer_vulkan/vk_rasterizer.h"
insert_once(
    rasterizer_h,
    "struct FramebufferTextureInfo;\n",
    "\nstruct SGSR2DepthCandidateInfo {\n"
    "    VkImage image{VK_NULL_HANDLE};\n"
    "    VkImageView view{VK_NULL_HANDLE};\n"
    "    VkExtent2D extent{};\n"
    "    VkSampleCountFlagBits samples{VK_SAMPLE_COUNT_1_BIT};\n"
    "};\n",
)
insert_once(
    rasterizer_h,
    "    std::optional<FramebufferTextureInfo> AccelerateDisplay(const Tegra::FramebufferConfig& config,\n"
    "                                                            VAddr framebuffer_addr,\n"
    "                                                            u32 pixel_stride);\n",
    "\n    [[nodiscard]] std::optional<SGSR2DepthCandidateInfo> GetSGSR2DepthCandidate() {\n"
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
)

# 4) Capture the candidate next to the genuine display color surface.  Do NOT promote
#    it to depth_valid yet: the last bound depth target may belong to a UI/post pass.
#    Stage 5 will validate temporal/semantic correlation before enabling SGSR2 dispatch.
layer_cpp = ROOT / "src/video_core/renderer_vulkan/present/layer.cpp"
insert_once(
    layer_cpp,
    "    sgsr2_inputs.source_is_accelerated = use_accelerated;\n",
    "\n    if (const auto depth_candidate = rasterizer.GetSGSR2DepthCandidate()) {\n"
    "        sgsr2_inputs.depth_image = depth_candidate->image;\n"
    "        sgsr2_inputs.depth_view = depth_candidate->view;\n"
    "        sgsr2_inputs.depth_extent = depth_candidate->extent;\n"
    "        sgsr2_inputs.depth_samples = depth_candidate->samples;\n"
    "        sgsr2_inputs.depth_candidate_valid =\n"
    "            depth_candidate->image != VK_NULL_HANDLE && depth_candidate->view != VK_NULL_HANDLE &&\n"
    "            depth_candidate->extent.width != 0 && depth_candidate->extent.height != 0;\n"
    "        sgsr2_inputs.depth_extent_matches_color =\n"
    "            depth_candidate->extent.width == render_extent.width &&\n"
    "            depth_candidate->extent.height == render_extent.height;\n"
    "        sgsr2_inputs.depth_single_sample = depth_candidate->samples == VK_SAMPLE_COUNT_1_BIT;\n"
    "        // Intentionally NOT setting depth_valid here. A technically valid Vulkan depth\n"
    "        // attachment is only a candidate until it is correlated with the displayed scene.\n"
    "    }\n",
)

print("Moonwitch Reconstruction Stage 4 depth candidate plumbing applied.")
print("Real Vulkan depth attachment can now reach SGSR2RuntimeInputs as a candidate.")
print("depth_valid remains false; temporal dispatch is still impossible until semantic validation.")
