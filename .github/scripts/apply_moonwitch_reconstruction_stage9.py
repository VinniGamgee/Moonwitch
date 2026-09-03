#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def insert_once(path: Path, anchor: str, addition: str) -> None:
    text = path.read_text(encoding="utf-8")
    if addition.strip() in text:
        return
    if anchor not in text:
        raise RuntimeError(f"anchor not found in {path}: {anchor!r}")
    path.write_text(text.replace(anchor, anchor + addition, 1), encoding="utf-8")


# Stage 9 does not enable temporal dispatch. It connects the Stage 8 scene-history
# correlation with the Stage 6/7 motion-candidate diagnostics and emits compact,
# periodic evidence about every plausible sibling target. The purpose is to identify
# the real guest velocity attachment without guessing from format alone.
runtime_inputs = ROOT / "src/video_core/renderer_vulkan/present/sgsr2_runtime_inputs.h"
insert_once(
    runtime_inputs,
    "    bool motion_probe_content_plausible{};\n",
    "    bool motion_scene_history_evidence{};\n"
    "    u32 motion_scene_history_lineage_hops{};\n",
)

layer_h = ROOT / "src/video_core/renderer_vulkan/present/layer.h"
insert_once(
    layer_h,
    "    u32 sgsr2_history_last_hops{~0u};\n",
    "    u32 sgsr2_stage9_candidate_log_counter{};\n"
    "    u32 sgsr2_stage9_last_candidate_count{~0u};\n",
)

layer_cpp = ROOT / "src/video_core/renderer_vulkan/present/layer.cpp"
anchor = (
    "        // Depth is now promoted only under exact same-framebuffer correlation. Sibling\n"
    "        // color attachments are still candidates only: motion_valid remains false until\n"
    "        // their velocity encoding and temporal behavior are verified.\n"
)
addition = r'''        // Stage 9: join scene-history provenance with the existing motion probes.
        // This is evidence only. Format + activity is not enough to prove velocity semantics.
        sgsr2_inputs.motion_scene_history_evidence =
            sgsr2_inputs.depth_scene_history_correlated &&
            sgsr2_inputs.motion_candidate_count != 0 &&
            sgsr2_inputs.motion_probe_candidate_valid;
        sgsr2_inputs.motion_scene_history_lineage_hops = sgsr2_inputs.depth_lineage_hops;

        if (Settings::values.moonwitch_reconstruction.GetValue() &&
            sgsr2_inputs.motion_scene_history_evidence) {
            ++sgsr2_stage9_candidate_log_counter;
            const bool candidate_set_changed =
                sgsr2_stage9_last_candidate_count != sgsr2_inputs.motion_candidate_count;
            if (candidate_set_changed || sgsr2_stage9_candidate_log_counter >= 300) {
                sgsr2_stage9_candidate_log_counter = 0;
                sgsr2_stage9_last_candidate_count = sgsr2_inputs.motion_candidate_count;
                LOG_INFO(Render_Vulkan,
                         "Moonwitch SGSR2 motion scene-history evidence: candidates={} lineage_hops={} best_index={} best_score={} depth_valid={}",
                         sgsr2_inputs.motion_candidate_count,
                         sgsr2_inputs.motion_scene_history_lineage_hops,
                         sgsr2_inputs.motion_probe_candidate_index,
                         sgsr2_inputs.motion_probe_plausibility_score,
                         sgsr2_inputs.depth_valid);
                for (u32 index = 0; index < sgsr2_inputs.motion_candidate_count; ++index) {
                    const auto& candidate = sgsr2_inputs.motion_candidates[index];
                    LOG_INFO(Render_Vulkan,
                             "Moonwitch SGSR2 motion candidate evidence: index={} format={} score={} format_plausible={} extent={}x{} samples={} selected={}",
                             index, candidate.guest_pixel_format, candidate.plausibility_score,
                             candidate.format_plausible, candidate.extent.width,
                             candidate.extent.height, static_cast<u32>(candidate.samples),
                             index == sgsr2_inputs.motion_probe_candidate_index);
                }
            }
        } else {
            sgsr2_stage9_candidate_log_counter = 0;
            sgsr2_stage9_last_candidate_count = ~0u;
        }

        // Stage 9 intentionally keeps motion_valid false. Promotion requires verified
        // guest velocity semantics (or a valid camera-motion transform), not heuristics.
'''
text = layer_cpp.read_text(encoding="utf-8")
if addition.strip() not in text:
    if anchor not in text:
        raise RuntimeError("Stage 9 motion evidence anchor not found in layer.cpp")
    layer_cpp.write_text(text.replace(anchor, addition + anchor, 1), encoding="utf-8")

print("Moonwitch Reconstruction Stage 9 motion evidence telemetry applied.")
print("Scene-history provenance is now reported alongside every plausible sibling target.")
print("motion_valid remains false; SGSR2 temporal dispatch is still gated.")
