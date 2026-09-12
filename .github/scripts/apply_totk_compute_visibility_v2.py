#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path


root = Path(".")
compute_h = root / "src/video_core/renderer_vulkan/vk_compute_pipeline.h"
rasterizer_cpp = root / "src/video_core/renderer_vulkan/vk_rasterizer.cpp"

compute_text = compute_h.read_text(encoding="utf-8")
rasterizer_text = rasterizer_cpp.read_text(encoding="utf-8")

# SYNC-A is a deliberately conservative diagnostic for Tears of the Kingdom. BUILD #244 normally
# applies the v2 write-metadata predicate here, but a false negative can skip visibility for guest
# resources that alias storage buffers/images. Keep the original title-gated barrier after every
# guest compute dispatch so we can test correctness without changing any other #244 renderer path.
unexpected_markers = (
    (compute_h, compute_text, "MayWriteGuestMemory() const noexcept"),
    (rasterizer_cpp, rasterizer_text, "totk_compute_may_write_guest_memory"),
)
for path, text, marker in unexpected_markers:
    if marker in text:
        raise RuntimeError(f"{path}: v2 compute visibility pruning is still active ({marker})")

required_rasterizer_markers = (
    "static constexpr u64 TOTK_PROGRAM_ID = 0x0100F2C0115B6000ULL;",
    "const bool apply_totk_compute_visibility_workaround = program_id == TOTK_PROGRAM_ID;",
    "const auto record_totk_compute_visibility_barrier =",
    "[this, apply_totk_compute_visibility_workaround] {",
    "if (!apply_totk_compute_visibility_workaround) {",
    "VK_ACCESS_SHADER_WRITE_BIT | VK_ACCESS_MEMORY_WRITE_BIT",
    "VK_ACCESS_INDIRECT_COMMAND_READ_BIT",
    "VK_ACCESS_SHADER_READ_BIT",
    "cmdbuf.PipelineBarrier(VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT, destination_stages,",
)
missing = [marker for marker in required_rasterizer_markers if marker not in rasterizer_text]
if missing:
    raise RuntimeError(
        f"{rasterizer_cpp}: BUILD #244 broad TOTK barrier is incomplete; missing {missing}"
    )

barrier_calls = rasterizer_text.count("record_totk_compute_visibility_barrier();")
if barrier_calls != 2:
    raise RuntimeError(
        f"{rasterizer_cpp}: expected the barrier after direct and indirect compute dispatches, "
        f"found {barrier_calls} calls"
    )

print(
    "Applied TOTK compute visibility SYNC-A: broad title-gated barrier preserved after every "
    "guest compute dispatch."
)
