#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import hashlib
import time
import urllib.request
from pathlib import Path


SDK_COMMIT = "35e13ba316c98eeecf16f37eae70ce88019911f6"
OFFICIAL_FILES = (
    (
        "NIS/NIS_Config.h",
        Path("src/video_core/renderer_vulkan/present/NIS_Config.h"),
        "b8982217d7c4ad99a4725af54336d7a5b24de443",
    ),
    (
        "NIS/NIS_Scaler.h",
        Path("src/video_core/host_shaders/NIS_Scaler.h"),
        "02f645c2c01b0235d340d25c6cfc913000f7cc1b",
    ),
)


def git_blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode()
    return hashlib.sha1(header + data).hexdigest()


def fetch_pinned_sdk_file(remote_path: str, destination: Path, expected_blob: str) -> None:
    url = (
        "https://raw.githubusercontent.com/NVIDIAGameWorks/NVIDIAImageScaling/"
        f"{SDK_COMMIT}/{remote_path}"
    )
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            request = urllib.request.Request(
                url, headers={"User-Agent": "Moonwitch-NIS-integration/1.0"}
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                data = response.read()
            actual_blob = git_blob_sha(data)
            if actual_blob != expected_blob:
                raise RuntimeError(
                    f"{remote_path}: pinned NVIDIA source hash mismatch: "
                    f"expected {expected_blob}, got {actual_blob}"
                )
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
            print(f"[nis] verified NVIDIA SDK {remote_path} ({actual_blob})")
            return
        except Exception as exc:
            last_error = exc
            if attempt != 2:
                time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Failed to fetch pinned NVIDIA SDK file {remote_path}: {last_error}")


def replace_once(path: Path, old: str, new: str, marker: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if marker in text:
        print(f"[nis] {label}: already patched")
        return
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one anchor for {label}, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"[nis] {label}: patched")


for remote_path, destination, expected_blob in OFFICIAL_FILES:
    fetch_pinned_sdk_file(remote_path, destination, expected_blob)

root = Path(".")

settings_enums = root / "src/common/settings_enums.h"
settings_h = root / "src/common/settings.h"
int_setting = root / "src/android/app/src/main/java/org/yuzu/yuzu_emu/features/settings/model/IntSetting.kt"
settings_item = root / "src/android/app/src/main/java/org/yuzu/yuzu_emu/features/settings/model/view/SettingsItem.kt"
presenter = root / "src/android/app/src/main/java/org/yuzu/yuzu_emu/features/settings/ui/SettingsFragmentPresenter.kt"
arrays_xml = root / "src/android/app/src/main/res/values/arrays.xml"
strings_xml = root / "src/android/app/src/main/res/values/strings.xml"
shader_cmake = root / "src/video_core/host_shaders/CMakeLists.txt"
video_cmake = root / "src/video_core/CMakeLists.txt"
layer_h = root / "src/video_core/renderer_vulkan/present/layer.h"
layer_cpp = root / "src/video_core/renderer_vulkan/present/layer.cpp"
blit_cpp = root / "src/video_core/renderer_vulkan/vk_blit_screen.cpp"

replace_once(
    settings_enums,
    "ENUM(ScalingFilter, NearestNeighbor, Bilinear, Bicubic, Gaussian, Lanczos, ScaleForce, Fsr, Area, ZeroTangent, BSpline, Mitchell, Spline1, Mmpx, Sgsr, SgsrEdge);",
    "ENUM(ScalingFilter, NearestNeighbor, Bilinear, Bicubic, Gaussian, Lanczos, ScaleForce, Fsr, Area, ZeroTangent, BSpline, Mitchell, Spline1, Mmpx, Sgsr, SgsrEdge, Nis);",
    "SgsrEdge, Nis);",
    "add NIS scaling filter enum",
)

replace_once(
    settings_h,
    "    // Moonwitch Reconstruction stage 1: preserve source texture detail for a higher\n",
    """    SwitchableSetting<int, true> nis_sharpening_slider{
        linkage, 50, 0, 100, "nis_sharpening_slider", Category::Renderer,
        Specialization::Scalar | Specialization::Percentage, true, true};

    // Moonwitch Reconstruction stage 1: preserve source texture detail for a higher
""",
    '"nis_sharpening_slider"',
    "add NIS 0-100 sharpness setting",
)

replace_once(
    int_setting,
    '    FSR_SHARPENING_SLIDER("fsr_sharpening_slider"),\n'
    '    MOONWITCH_RECONSTRUCTION_TARGET("moonwitch_reconstruction_target"),\n',
    '    FSR_SHARPENING_SLIDER("fsr_sharpening_slider"),\n'
    '    NIS_SHARPENING_SLIDER("nis_sharpening_slider"),\n'
    '    MOONWITCH_RECONSTRUCTION_TARGET("moonwitch_reconstruction_target"),\n',
    'NIS_SHARPENING_SLIDER("nis_sharpening_slider")',
    "register Android NIS sharpness setting",
)

replace_once(
    settings_item,
    """            put(
                SliderSetting(
                    IntSetting.FSR_SHARPENING_SLIDER,
                    titleId = R.string.fsr_sharpness,
                    descriptionId = R.string.fsr_sharpness_description,
                    max = 200,
                    units = "%"
                )
            )
            put(
                SliderSetting(
                    IntSetting.ANDROID_PIPELINE_WORKERS,
""",
    """            put(
                SliderSetting(
                    IntSetting.FSR_SHARPENING_SLIDER,
                    titleId = R.string.fsr_sharpness,
                    descriptionId = R.string.fsr_sharpness_description,
                    max = 200,
                    units = "%"
                )
            )
            put(
                SliderSetting(
                    IntSetting.NIS_SHARPENING_SLIDER,
                    titleId = R.string.nis_sharpness,
                    descriptionId = R.string.nis_sharpness_description,
                    min = 0,
                    max = 100,
                    units = "%"
                )
            )
            put(
                SliderSetting(
                    IntSetting.ANDROID_PIPELINE_WORKERS,
""",
    "IntSetting.NIS_SHARPENING_SLIDER",
    "register Android NIS sharpness slider",
)

replace_once(
    arrays_xml,
    """        <item>@string/scaling_filter_sgsr</item>
        <item>@string/scaling_filter_sgsr_edge</item>
    </string-array>
""",
    """        <item>@string/scaling_filter_sgsr</item>
        <item>@string/scaling_filter_sgsr_edge</item>
        <item>@string/scaling_filter_nis</item>
    </string-array>
""",
    "@string/scaling_filter_nis",
    "add NIS filter name",
)

replace_once(
    arrays_xml,
    """        <item>13</item>
        <item>14</item>
    </integer-array>

    <string-array name="rendererAntiAliasingNames">
""",
    """        <item>13</item>
        <item>14</item>
        <item>15</item>
    </integer-array>

    <string-array name="rendererAntiAliasingNames">
""",
    "<item>15</item>\n    </integer-array>\n\n    <string-array name=\"rendererAntiAliasingNames\">",
    "add NIS filter value",
)

replace_once(
    strings_xml,
    """    <string name="fsr_sharpness">FSR/SGSR sharpness</string>
    <string name="fsr_sharpness_description">Determines how sharpened the image will look while using FSR or SGSR filters</string>
    <string name="renderer_anti_aliasing">Anti-aliasing method</string>
""",
    """    <string name="fsr_sharpness">FSR/SGSR sharpness</string>
    <string name="fsr_sharpness_description">Determines how sharpened the image will look while using FSR or SGSR filters</string>
    <string name="scaling_filter_nis">NVIDIA Image Scaling (NIS)</string>
    <string name="nis_sharpness">NIS sharpness</string>
    <string name="nis_sharpness_description">Controls the adaptive sharpening built into NVIDIA Image Scaling from 0% to 100%. This control is used only when NIS is selected.</string>
    <string name="renderer_anti_aliasing">Anti-aliasing method</string>
""",
    'name="nis_sharpness"',
    "add NIS Android strings",
)

replace_once(
    presenter,
    """    private fun resolveSharpnessScalingFilterValues(): Set<Int> {
""",
    """    private fun isNisScalingFilterSelected(): Boolean {
        val needsGlobal = getNeedsGlobalForKey(IntSetting.RENDERER_SCALING_FILTER.key)
        val selectedFilter = IntSetting.RENDERER_SCALING_FILTER.getInt(needsGlobal)
        val names = context.resources.getStringArray(R.array.rendererScalingFilterNames)
        val values = context.resources.getIntArray(R.array.rendererScalingFilterValues)
        val nisIndex = names.indexOf(context.getString(R.string.scaling_filter_nis))
        return nisIndex >= 0 && nisIndex < values.size && selectedFilter == values[nisIndex]
    }

    private fun resolveSharpnessScalingFilterValues(): Set<Int> {
""",
    "private fun isNisScalingFilterSelected()",
    "add NIS selected-filter helper",
)

replace_once(
    presenter,
    """            if (isSharpnessScalingFilterSelected()) {
                add(IntSetting.FSR_SHARPENING_SLIDER.key)
            }
            add(IntSetting.RENDERER_ANTI_ALIASING.key)
""",
    """            if (isSharpnessScalingFilterSelected()) {
                add(IntSetting.FSR_SHARPENING_SLIDER.key)
            }
            if (isNisScalingFilterSelected()) {
                add(IntSetting.NIS_SHARPENING_SLIDER.key)
            }
            add(IntSetting.RENDERER_ANTI_ALIASING.key)
""",
    "add(IntSetting.NIS_SHARPENING_SLIDER.key)",
    "show NIS slider only for NIS",
)

replace_once(
    shader_cmake,
    """    ${CMAKE_CURRENT_SOURCE_DIR}/sgsr1_shader_mobile_edge_direction.frag
    ${CMAKE_CURRENT_SOURCE_DIR}/moonwitch_reconstruction_adaptive.frag
)
""",
    """    ${CMAKE_CURRENT_SOURCE_DIR}/sgsr1_shader_mobile_edge_direction.frag
    ${CMAKE_CURRENT_SOURCE_DIR}/moonwitch_reconstruction_adaptive.frag

    # NVIDIA Image Scaling SDK NVScaler
    ${CMAKE_CURRENT_SOURCE_DIR}/nvidia_nis.comp
)
""",
    "${CMAKE_CURRENT_SOURCE_DIR}/nvidia_nis.comp",
    "register NIS compute shader",
)

replace_once(
    shader_cmake,
    '${GLSLANGVALIDATOR} -V ${QUIET_FLAG} -I"${FIDELITYFX_INCLUDE_DIR}" ${GLSL_FLAGS} --variable-name',
    '${GLSLANGVALIDATOR} -V ${QUIET_FLAG} -I"${FIDELITYFX_INCLUDE_DIR}" -I"${CMAKE_CURRENT_SOURCE_DIR}" ${GLSL_FLAGS} --variable-name',
    '-I"${CMAKE_CURRENT_SOURCE_DIR}" ${GLSL_FLAGS}',
    "allow host shader local includes",
)

replace_once(
    video_cmake,
    """    renderer_vulkan/present/fsr.cpp
    renderer_vulkan/present/fsr.h
    renderer_vulkan/present/fxaa.cpp
""",
    """    renderer_vulkan/present/fsr.cpp
    renderer_vulkan/present/fsr.h
    renderer_vulkan/present/nis.cpp
    renderer_vulkan/present/nis.h
    renderer_vulkan/present/fxaa.cpp
""",
    "renderer_vulkan/present/nis.cpp",
    "register NIS Vulkan sources",
)

replace_once(
    layer_h,
    '#include "video_core/renderer_vulkan/present/fsr.h"\n'
    '#include "video_core/renderer_vulkan/present/sgsr.h"\n',
    '#include "video_core/renderer_vulkan/present/fsr.h"\n'
    '#include "video_core/renderer_vulkan/present/nis.h"\n'
    '#include "video_core/renderer_vulkan/present/sgsr.h"\n',
    '#include "video_core/renderer_vulkan/present/nis.h"',
    "include NIS in Layer",
)

replace_once(
    layer_h,
    "    std::variant<std::monostate, SGSR, FSR> sr_filter{};\n",
    "    std::variant<std::monostate, SGSR, FSR, NIS> sr_filter{};\n",
    "SGSR, FSR, NIS",
    "add NIS to scaling variant",
)

replace_once(
    layer_cpp,
    '#include "video_core/renderer_vulkan/present/fsr.h"\n'
    '#include "video_core/renderer_vulkan/present/sgsr.h"\n',
    '#include "video_core/renderer_vulkan/present/fsr.h"\n'
    '#include "video_core/renderer_vulkan/present/nis.h"\n'
    '#include "video_core/renderer_vulkan/present/sgsr.h"\n',
    '#include "video_core/renderer_vulkan/present/nis.h"',
    "include NIS implementation",
)

replace_once(
    layer_cpp,
    """    } else if (scaling_filter == Settings::ScalingFilter::SgsrEdge) {
        sr_filter.emplace<SGSR>(device, memory_allocator, image_count, output_size, true);
    } else if (Settings::values.moonwitch_reconstruction.GetValue()) {
""",
    """    } else if (scaling_filter == Settings::ScalingFilter::SgsrEdge) {
        sr_filter.emplace<SGSR>(device, memory_allocator, image_count, output_size, true);
    } else if (scaling_filter == Settings::ScalingFilter::Nis) {
        sr_filter.emplace<NIS>(device, memory_allocator, scheduler, image_count, output_size);
    } else if (Settings::values.moonwitch_reconstruction.GetValue()) {
""",
    "ScalingFilter::Nis",
    "instantiate real NIS NVScaler",
)

replace_once(
    layer_cpp,
    """    if (auto* fsr = std::get_if<FSR>(&sr_filter)) {
        source_image_view = fsr->Draw(device, scheduler, image_index, source_image, source_image_view, render_extent, crop_rect);
        crop_rect = {0, 0, 1, 1};
    } else if (auto* sgsr = std::get_if<SGSR>(&sr_filter)) {
        source_image_view = sgsr->Draw(device, scheduler, image_index, source_image, source_image_view, render_extent, crop_rect);
        crop_rect = {0, 0, 1, 1};
    }

    if (Settings::IsCasEnabled()) {
        const VkExtent2D cas_extent = std::holds_alternative<std::monostate>(sr_filter)
                                          ? render_extent
                                          : output_size_extent;
""",
    """    bool sr_filter_applied = false;
    if (auto* fsr = std::get_if<FSR>(&sr_filter)) {
        source_image_view = fsr->Draw(device, scheduler, image_index, source_image, source_image_view,
                                      render_extent, crop_rect);
        crop_rect = {0, 0, 1, 1};
        sr_filter_applied = true;
    } else if (auto* sgsr = std::get_if<SGSR>(&sr_filter)) {
        source_image_view = sgsr->Draw(device, scheduler, image_index, source_image,
                                       source_image_view, render_extent, crop_rect);
        crop_rect = {0, 0, 1, 1};
        sr_filter_applied = true;
    } else if (auto* nis = std::get_if<NIS>(&sr_filter)) {
        if (const auto nis_output = nis->Draw(device, scheduler, image_index, source_image,
                                              source_image_view, render_extent, crop_rect)) {
            source_image_view = *nis_output;
            crop_rect = {0, 0, 1, 1};
            sr_filter_applied = true;
        }
    }

    if (Settings::IsCasEnabled()) {
        const VkExtent2D cas_extent = sr_filter_applied ? output_size_extent : render_extent;
""",
    "sr_filter_applied",
    "execute NIS and preserve fallback/CAS extent",
)

replace_once(
    blit_cpp,
    """    case Settings::ScalingFilter::Fsr:
    case Settings::ScalingFilter::Sgsr:
""",
    """    case Settings::ScalingFilter::Fsr:
    case Settings::ScalingFilter::Nis:
    case Settings::ScalingFilter::Sgsr:
""",
    "case Settings::ScalingFilter::Nis:",
    "route NIS through final bilinear present",
)

print("[nis] NVIDIA Image Scaling NVScaler integration applied")
