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


# Stage 6 does NOT promote a sibling render target to motion_valid. It classifies only
# technically plausible velocity encodings and tracks whether the best candidate is stable
# across presented frames. Content/temporal validation comes next.
runtime_inputs = ROOT / "src/video_core/renderer_vulkan/present/sgsr2_runtime_inputs.h"
insert_once(
    runtime_inputs,
    "    u32 guest_pixel_format{};\n",
    "    u32 plausibility_score{};\n"
    "    bool format_plausible{};\n",
)
insert_once(
    runtime_inputs,
    "    u32 motion_candidate_count{};\n",
    "    u32 motion_probe_candidate_index{};\n"
    "    u32 motion_probe_plausibility_score{};\n"
    "    u32 motion_probe_stable_frames{};\n"
    "    bool motion_probe_candidate_valid{};\n",
)

layer_h = ROOT / "src/video_core/renderer_vulkan/present/layer.h"
insert_once(
    layer_h,
    "    SGSR2RuntimeInputs sgsr2_inputs{};\n",
    "    VkImage sgsr2_motion_probe_image{VK_NULL_HANDLE};\n"
    "    u32 sgsr2_motion_probe_format{};\n"
    "    u32 sgsr2_motion_probe_stable_frames{};\n",
)

layer_cpp = ROOT / "src/video_core/renderer_vulkan/present/layer.cpp"
insert_once(
    layer_cpp,
    '#include "common/settings.h"\n',
    '#include "common/logging.h"\n',
)
insert_once(
    layer_cpp,
    '#include "video_core/framebuffer_config.h"\n',
    '#include "video_core/surface.h"\n',
)
insert_once(
    layer_cpp,
    "} // Anonymous namespace\n",
    "\n",
)
# Replace the anonymous-namespace close so the classifier lives inside it.
replace_once(
    layer_cpp,
    "} // Anonymous namespace\n",
    "u32 SGSR2MotionFormatScore(u32 guest_pixel_format) {\n"
    "    using PixelFormat = VideoCore::Surface::PixelFormat;\n"
    "    switch (static_cast<PixelFormat>(guest_pixel_format)) {\n"
    "    case PixelFormat::R16G16_FLOAT:\n"
    "        return 100;\n"
    "    case PixelFormat::R32G32_FLOAT:\n"
    "        return 95;\n"
    "    case PixelFormat::R16G16_SNORM:\n"
    "        return 85;\n"
    "    case PixelFormat::R8G8_SNORM:\n"
    "        return 75;\n"
    "    case PixelFormat::R16G16B16A16_FLOAT:\n"
    "        return 60;\n"
    "    case PixelFormat::R32G32B32A32_FLOAT:\n"
    "        return 55;\n"
    "    default:\n"
    "        return 0;\n"
    "    }\n"
    "}\n\n"
    "} // Anonymous namespace\n",
)

# Classify the same-framebuffer siblings after Stage 5 has collected them. The best
# candidate is merely a probe target. A stable VkImage/format across frames is useful
# evidence for the later content probe, but it is not proof of velocity semantics.
anchor = (
    "        // Depth is now promoted only under exact same-framebuffer correlation. Sibling\n"
    "        // color attachments are still candidates only: motion_valid remains false until\n"
    "        // their velocity encoding and temporal behavior are verified.\n"
)
addition = (
    "        u32 best_motion_index = sgsr2_inputs.motion_candidate_count;\n"
    "        u32 best_motion_score = 0;\n"
    "        for (u32 index = 0; index < sgsr2_inputs.motion_candidate_count; ++index) {\n"
    "            auto& candidate = sgsr2_inputs.motion_candidates[index];\n"
    "            candidate.plausibility_score = SGSR2MotionFormatScore(candidate.guest_pixel_format);\n"
    "            candidate.format_plausible = candidate.plausibility_score != 0;\n"
    "            if (candidate.plausibility_score > best_motion_score) {\n"
    "                best_motion_score = candidate.plausibility_score;\n"
    "                best_motion_index = index;\n"
    "            }\n"
    "        }\n\n"
    "        if (best_motion_index < sgsr2_inputs.motion_candidate_count) {\n"
    "            const auto& probe = sgsr2_inputs.motion_candidates[best_motion_index];\n"
    "            sgsr2_inputs.motion_probe_candidate_valid = true;\n"
    "            sgsr2_inputs.motion_probe_candidate_index = best_motion_index;\n"
    "            sgsr2_inputs.motion_probe_plausibility_score = best_motion_score;\n"
    "            if (sgsr2_motion_probe_image == probe.image &&\n"
    "                sgsr2_motion_probe_format == probe.guest_pixel_format) {\n"
    "                if (sgsr2_motion_probe_stable_frames < 1000000) {\n"
    "                    ++sgsr2_motion_probe_stable_frames;\n"
    "                }\n"
    "            } else {\n"
    "                sgsr2_motion_probe_image = probe.image;\n"
    "                sgsr2_motion_probe_format = probe.guest_pixel_format;\n"
    "                sgsr2_motion_probe_stable_frames = 1;\n"
    "                LOG_INFO(Render_Vulkan,\n"
    "                         \"Moonwitch SGSR2 motion probe candidate selected: format={} score={} extent={}x{}\",\n"
    "                         probe.guest_pixel_format, best_motion_score, probe.extent.width,\n"
    "                         probe.extent.height);\n"
    "            }\n"
    "            sgsr2_inputs.motion_probe_stable_frames = sgsr2_motion_probe_stable_frames;\n"
    "            if (sgsr2_motion_probe_stable_frames == 120) {\n"
    "                LOG_INFO(Render_Vulkan,\n"
    "                         \"Moonwitch SGSR2 motion probe candidate stable for 120 presented frames: format={} score={}\",\n"
    "                         probe.guest_pixel_format, best_motion_score);\n"
    "            }\n"
    "        } else {\n"
    "            sgsr2_motion_probe_image = VK_NULL_HANDLE;\n"
    "            sgsr2_motion_probe_format = 0;\n"
    "            sgsr2_motion_probe_stable_frames = 0;\n"
    "        }\n\n"
)
text = layer_cpp.read_text(encoding="utf-8")
if addition.strip() not in text:
    if anchor not in text:
        raise RuntimeError("Stage 5 motion-candidate anchor not found in layer.cpp")
    layer_cpp.write_text(text.replace(anchor, addition + anchor, 1), encoding="utf-8")

print("Moonwitch Reconstruction Stage 6 motion candidate classifier applied.")
print("Plausible RG float/SNORM targets are ranked and tracked across frames.")
print("motion_valid remains false; no SGSR2 temporal dispatch is enabled by this stage.")
