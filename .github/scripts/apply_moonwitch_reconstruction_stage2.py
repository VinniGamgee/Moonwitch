#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path

layer_cpp = Path("src/video_core/renderer_vulkan/present/layer.cpp")
text = layer_cpp.read_text(encoding="utf-8")

old = '''    CreateDescriptorPool(device);
    CreateDescriptorSets(device, layout);
    if (filters.get_scaling_filter() == Settings::ScalingFilter::Fsr) {
        sr_filter.emplace<FSR>(device, memory_allocator, image_count, output_size);
    } else if (filters.get_scaling_filter() == Settings::ScalingFilter::Sgsr) {
        sr_filter.emplace<SGSR>(device, memory_allocator, image_count, output_size, false);
    } else if (filters.get_scaling_filter() == Settings::ScalingFilter::SgsrEdge) {
        sr_filter.emplace<SGSR>(device, memory_allocator, image_count, output_size, true);
    }
'''

new = '''    CreateDescriptorPool(device);
    CreateDescriptorSets(device, layout);

    const auto scaling_filter = filters.get_scaling_filter();
    if (scaling_filter == Settings::ScalingFilter::Fsr) {
        sr_filter.emplace<FSR>(device, memory_allocator, image_count, output_size);
    } else if (scaling_filter == Settings::ScalingFilter::Sgsr) {
        sr_filter.emplace<SGSR>(device, memory_allocator, image_count, output_size, false);
    } else if (scaling_filter == Settings::ScalingFilter::SgsrEdge) {
        sr_filter.emplace<SGSR>(device, memory_allocator, image_count, output_size, true);
    } else if (Settings::values.moonwitch_reconstruction.GetValue()) {
        const auto& resolution = Settings::values.resolution_info;
        const f32 render_scale = static_cast<f32>(resolution.up_scale) /
                                 static_cast<f32>(1U << resolution.down_shift);
        const f32 target_scale =
            static_cast<f32>(Settings::values.moonwitch_reconstruction_target.GetValue()) /
            100.0f;

        // Moonwitch Reconstruction Stage 2: when the requested reconstruction target is above
        // the guest render scale, reuse the existing one-pass edge-directed SGSR spatial stage.
        // Explicit FSR/SGSR selections above always take priority, so this adds no duplicate SR
        // pass. The edge-directed shader clamps its correction to the local neighborhood, which
        // keeps ringing under control while reconstructing edges at the output resolution.
        if (render_scale > 0.0f && target_scale > render_scale) {
            sr_filter.emplace<SGSR>(device, memory_allocator, image_count, output_size, true);
        }
    }
'''

if old not in text:
    raise SystemExit("Moonwitch reconstruction Stage 2 anchor not found in layer.cpp")

if text.count(old) != 1:
    raise SystemExit("Moonwitch reconstruction Stage 2 anchor is not unique")

layer_cpp.write_text(text.replace(old, new, 1), encoding="utf-8")
print("Applied Moonwitch Reconstruction Stage 2 spatial edge reconstruction.")

# Stage 3 intentionally layers on top of the proven Stage 2 call site. Keeping the orchestration
# here means the existing workflow still validates the Stage 2 wiring before the full Android build.
stage3_script = Path(".github/scripts/apply_moonwitch_reconstruction_stage3.py")
if not stage3_script.is_file():
    raise SystemExit("Moonwitch Reconstruction Stage 3 script is missing")
exec(compile(stage3_script.read_text(encoding="utf-8"), str(stage3_script), "exec"),
     {"__name__": "__main__"})

# Pure NIS scaling must run after Stage 3 because Stage 3 invokes the pinned official NVScaler.
# V2 propagates NVIDIA's exact 85/77/67/59/50% ratios through every renderer consumer before
# allowing CI to proceed.
nis_pure_script = Path(".github/scripts/apply_nis_pure_scaling_v2.py")
if not nis_pure_script.is_file():
    raise SystemExit("Pure NVIDIA Image Scaling v2 integration script is missing")
exec(compile(nis_pure_script.read_text(encoding="utf-8"), str(nis_pure_script), "exec"),
     {"__name__": "__main__"})
