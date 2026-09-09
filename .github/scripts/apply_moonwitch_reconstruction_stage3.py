#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path


def replace_once(path: Path, old: str, new: str, marker: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if marker in text:
        print(f"[reconstruction-stage3] {label}: already patched")
        return
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one anchor for {label}, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"[reconstruction-stage3] {label}: patched")


root = Path(".")
cmake = root / "src/video_core/host_shaders/CMakeLists.txt"
sgsr_h = root / "src/video_core/renderer_vulkan/present/sgsr.h"
sgsr_cpp = root / "src/video_core/renderer_vulkan/present/sgsr.cpp"

# Register a Moonwitch-only adaptive shader. Manual SGSR and SGSR Edge selections keep Qualcomm's
# original shaders; Stage 3 is selected only for the reconstruction path inserted by Stage 2.
replace_once(
    cmake,
    "    ${CMAKE_CURRENT_SOURCE_DIR}/sgsr1_shader_mobile_edge_direction.frag\n",
    "    ${CMAKE_CURRENT_SOURCE_DIR}/sgsr1_shader_mobile_edge_direction.frag\n"
    "    ${CMAKE_CURRENT_SOURCE_DIR}/moonwitch_reconstruction_adaptive.frag\n",
    "moonwitch_reconstruction_adaptive.frag",
    "register adaptive reconstruction shader",
)

replace_once(
    sgsr_h,
    "    bool m_images_ready{};\n    bool m_edge_dir{};\n",
    "    bool m_images_ready{};\n    bool m_edge_dir{};\n    bool m_moonwitch_adaptive{};\n",
    "m_moonwitch_adaptive",
    "store adaptive reconstruction mode",
)

replace_once(
    sgsr_cpp,
    '#include "video_core/host_shaders/sgsr1_shader_mobile_edge_direction_frag_spv.h"\n',
    '#include "video_core/host_shaders/sgsr1_shader_mobile_edge_direction_frag_spv.h"\n'
    '#include "video_core/host_shaders/moonwitch_reconstruction_adaptive_frag_spv.h"\n',
    "moonwitch_reconstruction_adaptive_frag_spv.h",
    "include adaptive reconstruction shader",
)

# Stage 2 creates an edge-directed SGSR instance only when the selected scaling filter is not an
# explicit FSR/SGSR mode. Use that distinction to select Stage 3 without changing Layer's Stage 2
# call site (and without changing the behaviour of the user's manual SGSR Edge option).
replace_once(
    sgsr_cpp,
    "    , m_extent{extent}\n    , m_edge_dir{edge_dir}\n",
    "    , m_extent{extent}\n"
    "    , m_edge_dir{edge_dir}\n"
    "    , m_moonwitch_adaptive{\n"
    "          edge_dir && Settings::values.moonwitch_reconstruction.GetValue() &&\n"
    "          Settings::values.scaling_filter.GetValue() != Settings::ScalingFilter::SgsrEdge}\n",
    "Settings::ScalingFilter::SgsrEdge}",
    "identify Moonwitch Stage 3 instances",
)

replace_once(
    sgsr_cpp,
    "    m_stage_shader = m_edge_dir\n"
    "        ? BuildShader(device, SGSR1_SHADER_MOBILE_EDGE_DIRECTION_FRAG_SPV)\n"
    "        : BuildShader(device, SGSR1_SHADER_MOBILE_FRAG_SPV);\n",
    "    m_stage_shader = m_moonwitch_adaptive\n"
    "        ? BuildShader(device, MOONWITCH_RECONSTRUCTION_ADAPTIVE_FRAG_SPV)\n"
    "        : m_edge_dir\n"
    "              ? BuildShader(device, SGSR1_SHADER_MOBILE_EDGE_DIRECTION_FRAG_SPV)\n"
    "              : BuildShader(device, SGSR1_SHADER_MOBILE_FRAG_SPV);\n",
    "MOONWITCH_RECONSTRUCTION_ADAPTIVE_FRAG_SPV",
    "select Moonwitch adaptive shader",
)

# Do not let Moonwitch Reconstruction silently inherit the unrelated generic FSR sharpening slider.
# Its spatial strength follows the existing reconstruction target instead and stays deliberately
# conservative: 150% -> 1.35, 200% -> 1.55 versus SGSR Edge's possible 2.0 maximum.
replace_once(
    sgsr_cpp,
    "    static constexpr f32 EDGE_SHARPNESS_MAX = 2.0f;\n"
    "    const f32 edge_sharpness =\n"
    "        EDGE_SHARPNESS_MAX - f32(Settings::values.fsr_sharpening_slider.GetValue()) / 200.0f;\n",
    "    static constexpr f32 EDGE_SHARPNESS_MAX = 2.0f;\n"
    "    const f32 user_edge_sharpness =\n"
    "        EDGE_SHARPNESS_MAX - f32(Settings::values.fsr_sharpening_slider.GetValue()) / 200.0f;\n"
    "    const f32 reconstruction_target =\n"
    "        static_cast<f32>(Settings::values.moonwitch_reconstruction_target.GetValue());\n"
    "    const f32 reconstruction_strength =\n"
    "        std::clamp((reconstruction_target - 100.0f) / 100.0f, 0.0f, 1.0f);\n"
    "    const f32 edge_sharpness = m_moonwitch_adaptive\n"
    "        ? 1.15f + 0.40f * reconstruction_strength\n"
    "        : user_edge_sharpness;\n",
    "reconstruction_strength =",
    "derive conservative Moonwitch edge strength",
)

print("Applied Moonwitch Reconstruction Stage 3 adaptive spatial reconstruction.")

# Reuse the existing workflow hook to apply an independent renderer correctness/performance pass.
# The implementation lives in its own script so reconstruction and TOTK synchronization remain
# logically separate even though both are invoked from the same build step for now.
totk_visibility_script = Path(".github/scripts/apply_totk_compute_visibility_v2.py")
if not totk_visibility_script.is_file():
    raise SystemExit("TOTK compute visibility v2 script is missing")
exec(compile(totk_visibility_script.read_text(encoding="utf-8"), str(totk_visibility_script), "exec"),
     {"__name__": "__main__"})

# NIS is a separate presentation feature. Reuse this pre-build hook so its official NVIDIA SDK
# sources are pinned/verified before CMake generates the host shader headers.
nis_script = Path(".github/scripts/apply_nvidia_image_scaling.py")
if not nis_script.is_file():
    raise SystemExit("NVIDIA Image Scaling integration script is missing")
exec(compile(nis_script.read_text(encoding="utf-8"), str(nis_script), "exec"),
     {"__name__": "__main__"})
