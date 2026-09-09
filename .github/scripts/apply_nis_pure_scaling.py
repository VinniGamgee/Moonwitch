#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from pathlib import Path


def replace_once(path: Path, old: str, new: str, marker: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if marker in text:
        print(f"[nis-pure] {label}: already patched")
        return
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one anchor for {label}, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"[nis-pure] {label}: patched")


root = Path(".")
settings_h = root / "src/common/settings.h"
settings_cpp = root / "src/common/settings.cpp"
int_setting = root / "src/android/app/src/main/java/org/yuzu/yuzu_emu/features/settings/model/IntSetting.kt"
settings_item = root / "src/android/app/src/main/java/org/yuzu/yuzu_emu/features/settings/model/view/SettingsItem.kt"
presenter = root / "src/android/app/src/main/java/org/yuzu/yuzu_emu/features/settings/ui/SettingsFragmentPresenter.kt"
arrays_xml = root / "src/android/app/src/main/res/values/arrays.xml"
strings_xml = root / "src/android/app/src/main/res/values/strings.xml"
texture_cache_h = root / "src/video_core/texture_cache/texture_cache.h"
vk_texture_cache_cpp = root / "src/video_core/renderer_vulkan/vk_texture_cache.cpp"
layer_cpp = root / "src/video_core/renderer_vulkan/present/layer.cpp"

# The legacy yuzu/Eden scale representation is optimized for ratios whose denominator is a
# power of two (0.5x, 0.75x, 1.5x, ...). Official NIS presets are 85/77/67/59/50 percent,
# so preserve the legacy representation for every other filter and add an exact rational path
# only while NIS is selected.
replace_once(
    settings_h,
    """    u32 up_scale{1};
    u32 down_shift{0};
    f32 up_factor{1.0f};
    f32 down_factor{1.0f};
    bool active{};
    bool downscale{};

    s32 ScaleUp(s32 value) const {
        if (value == 0) {
            return 0;
        }
        return (std::max)((value * static_cast<s32>(up_scale)) >> static_cast<s32>(down_shift), 1);
    }

    u32 ScaleUp(u32 value) const {
        if (value == 0U) {
            return 0U;
        }
        return (std::max)((value * up_scale) >> down_shift, 1U);
    }
""",
    """    u32 up_scale{1};
    u32 down_shift{0};
    f32 up_factor{1.0f};
    f32 down_factor{1.0f};
    u32 exact_numerator{1};
    u32 exact_denominator{1};
    bool exact_ratio{};
    bool active{};
    bool downscale{};

    s32 ScaleUp(s32 value) const {
        if (value == 0) {
            return 0;
        }
        if (exact_ratio) {
            const s64 scaled = static_cast<s64>(value) * static_cast<s64>(exact_numerator) /
                               static_cast<s64>(exact_denominator);
            return (std::max)(static_cast<s32>(scaled), 1);
        }
        return (std::max)((value * static_cast<s32>(up_scale)) >> static_cast<s32>(down_shift), 1);
    }

    u32 ScaleUp(u32 value) const {
        if (value == 0U) {
            return 0U;
        }
        if (exact_ratio) {
            const u64 scaled = static_cast<u64>(value) * static_cast<u64>(exact_numerator) /
                               static_cast<u64>(exact_denominator);
            return (std::max)(static_cast<u32>(scaled), 1U);
        }
        return (std::max)((value * up_scale) >> down_shift, 1U);
    }
""",
    "u32 exact_numerator{1};",
    "add exact rational render scale support",
)

# Keep NVIDIA's two user-facing controls separate: render scale and adaptive sharpening.
replace_once(
    settings_h,
    """    SwitchableSetting<int, true> nis_sharpening_slider{
        linkage, 50, 0, 100, "nis_sharpening_slider", Category::Renderer,
        Specialization::Scalar | Specialization::Percentage, true, true};

    // Moonwitch Reconstruction stage 1: preserve source texture detail for a higher
""",
    """    SwitchableSetting<int, true> nis_sharpening_slider{
        linkage, 50, 0, 100, "nis_sharpening_slider", Category::Renderer,
        Specialization::Scalar | Specialization::Percentage, true, true};
    SwitchableSetting<int, true> nis_render_scale{
        linkage, 77, 50, 85, "nis_render_scale", Category::Renderer,
        Specialization::Countable | Specialization::Percentage, true, false};

    // Moonwitch Reconstruction stage 1: preserve source texture detail for a higher
""",
    '"nis_render_scale"',
    "add official NIS render-scale setting",
)

replace_once(
    int_setting,
    '    NIS_SHARPENING_SLIDER("nis_sharpening_slider"),\n',
    '    NIS_SHARPENING_SLIDER("nis_sharpening_slider"),\n'
    '    NIS_RENDER_SCALE("nis_render_scale"),\n',
    'NIS_RENDER_SCALE("nis_render_scale")',
    "register Android NIS render scale",
)

replace_once(
    settings_item,
    """            put(
                SliderSetting(
                    IntSetting.NIS_SHARPENING_SLIDER,
                    titleId = R.string.nis_sharpness,
                    descriptionId = R.string.nis_sharpness_description,
                    min = 0,
                    max = 100,
                    units = "%"
                )
            )
""",
    """            put(
                SingleChoiceSetting(
                    IntSetting.NIS_RENDER_SCALE,
                    titleId = R.string.nis_render_scale,
                    descriptionId = R.string.nis_render_scale_description,
                    choicesId = R.array.nisRenderScaleNames,
                    valuesId = R.array.nisRenderScaleValues
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
""",
    "IntSetting.NIS_RENDER_SCALE",
    "register NIS preset selector",
)

replace_once(
    arrays_xml,
    """    <string-array name="rendererAntiAliasingNames">
""",
    """    <string-array name="nisRenderScaleNames">
        <item>85%</item>
        <item>77%</item>
        <item>67%</item>
        <item>59%</item>
        <item>50%</item>
    </string-array>

    <integer-array name="nisRenderScaleValues">
        <item>85</item>
        <item>77</item>
        <item>67</item>
        <item>59</item>
        <item>50</item>
    </integer-array>

    <string-array name="rendererAntiAliasingNames">
""",
    'name="nisRenderScaleNames"',
    "add official NIS preset arrays",
)

replace_once(
    strings_xml,
    """    <string name="nis_sharpness">NIS sharpness</string>
    <string name="nis_sharpness_description">Controls the adaptive sharpening built into NVIDIA Image Scaling from 0% to 100%. This control is used only when NIS is selected.</string>
""",
    """    <string name="nis_render_scale">NIS render resolution</string>
    <string name="nis_render_scale_description">Official NVIDIA Image Scaling input preset. While NIS is selected, this replaces the normal resolution multiplier: the game is rendered at 85%, 77%, 67%, 59% or 50% of native 1x and NVScaler reconstructs it to the display resolution.</string>
    <string name="nis_sharpness">NIS sharpness</string>
    <string name="nis_sharpness_description">Controls the adaptive sharpening built into NVScaler from 0% to 100%. Scaling and sharpening are performed by the NVIDIA Image Scaling algorithm in the same compute pass.</string>
""",
    'name="nis_render_scale"',
    "describe pure NIS controls",
)

replace_once(
    presenter,
    """            if (isNisScalingFilterSelected()) {
                add(IntSetting.NIS_SHARPENING_SLIDER.key)
            }
""",
    """            if (isNisScalingFilterSelected()) {
                add(IntSetting.NIS_RENDER_SCALE.key)
                add(IntSetting.NIS_SHARPENING_SLIDER.key)
            }
""",
    "add(IntSetting.NIS_RENDER_SCALE.key)",
    "show NIS render scale with NIS",
)

# Reset exact-ratio state whenever the normal resolution translation runs.
replace_once(
    settings_cpp,
    """void TranslateResolutionInfo(ResolutionSetup setup, ResolutionScalingInfo& info) {
    info.downscale = false;
""",
    """void TranslateResolutionInfo(ResolutionSetup setup, ResolutionScalingInfo& info) {
    info.exact_numerator = 1;
    info.exact_denominator = 1;
    info.exact_ratio = false;
    info.downscale = false;
""",
    "info.exact_ratio = false;",
    "reset exact ratio for legacy resolution modes",
)

# NIS works like the driver implementation: selecting NIS chooses one of NVIDIA's lower render
# resolutions relative to native 1x, then NVScaler reconstructs to the final output. Do not stack
# the legacy 0.5x/0.75x multiplier on top; that would no longer match NIS preset semantics.
replace_once(
    settings_cpp,
    """void UpdateRescalingInfo() {
    const auto setup = values.resolution_setup.GetValue();
    auto& info = values.resolution_info;
    TranslateResolutionInfo(setup, info);
}
""",
    """void UpdateRescalingInfo() {
    const auto setup = values.resolution_setup.GetValue();
    auto& info = values.resolution_info;
    TranslateResolutionInfo(setup, info);

    if (values.scaling_filter.GetValue() == ScalingFilter::Nis) {
        int preset = values.nis_render_scale.GetValue();
        switch (preset) {
        case 85:
        case 77:
        case 67:
        case 59:
        case 50:
            break;
        default:
            preset = 77;
            break;
        }

        // Official NIS render-resolution presets are exact percentages of native 1x.
        info.up_scale = 1;
        info.down_shift = 0;
        info.exact_numerator = static_cast<u32>(preset);
        info.exact_denominator = 100;
        info.exact_ratio = true;
        info.up_factor = static_cast<f32>(preset) / 100.0f;
        info.down_factor = 100.0f / static_cast<f32>(preset);
        info.active = preset != 100;
        info.downscale = preset < 100;
    }
}
""",
    "Official NIS render-resolution presets are exact percentages",
    "apply official NIS presets to internal rendering",
)

# Any code that only needs the scalar factor must use up_factor so exact NIS ratios survive.
replace_once(
    vk_texture_cache_cpp,
    """            const auto& resolution = Settings::values.resolution_info;
            const f32 render_scale = static_cast<f32>(resolution.up_scale) /
                                     static_cast<f32>(1U << resolution.down_shift);
""",
    """            const auto& resolution = Settings::values.resolution_info;
            const f32 render_scale = resolution.up_factor;
""",
    "const f32 render_scale = resolution.up_factor;",
    "make texture-detail logic exact-ratio aware",
)

replace_once(
    layer_cpp,
    """        const auto& resolution = Settings::values.resolution_info;
        const f32 render_scale = static_cast<f32>(resolution.up_scale) /
                                 static_cast<f32>(1U << resolution.down_shift);
""",
    """        const auto& resolution = Settings::values.resolution_info;
        const f32 render_scale = resolution.up_factor;
""",
    "const f32 render_scale = resolution.up_factor;",
    "make reconstruction layer exact-ratio aware",
)

replace_once(
    texture_cache_h,
    """u64 TextureCache<P>::GetScaledImageSizeBytes(const ImageBase& image) {
    const u64 scale_up = static_cast<u64>(Settings::values.resolution_info.up_scale *
                                          Settings::values.resolution_info.up_scale);
    const u64 down_shift = static_cast<u64>(Settings::values.resolution_info.down_shift +
                                            Settings::values.resolution_info.down_shift);
    const u64 image_size_bytes =
        static_cast<u64>((std::max)(image.guest_size_bytes, image.unswizzled_size_bytes));
    const u64 tentative_size = (image_size_bytes * scale_up) >> down_shift;
    const u64 fitted_size = Common::AlignUp(tentative_size, 1024);
    return fitted_size;
}
""",
    """u64 TextureCache<P>::GetScaledImageSizeBytes(const ImageBase& image) {
    const f64 scale = static_cast<f64>(Settings::values.resolution_info.up_factor);
    const u64 image_size_bytes =
        static_cast<u64>((std::max)(image.guest_size_bytes, image.unswizzled_size_bytes));
    const u64 tentative_size =
        static_cast<u64>(static_cast<f64>(image_size_bytes) * scale * scale);
    const u64 fitted_size = Common::AlignUp(tentative_size, 1024);
    return fitted_size;
}
""",
    "const f64 scale = static_cast<f64>(Settings::values.resolution_info.up_factor);",
    "make scaled-image memory accounting exact-ratio aware",
)

# Refuse to build if a direct legacy scale calculation remains in core source. ScaleUp() itself,
# TranslateResolutionInfo(), and generic helper parameters are fine; this specifically catches
# consumers bypassing ResolutionScalingInfo::ScaleUp()/up_factor.
offenders = []
for path in (root / "src").rglob("*"):
    if path.suffix not in {".h", ".hpp", ".cpp", ".cc", ".cxx"}:
        continue
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        continue
    for line_no, line in enumerate(lines, 1):
        if "resolution_info.up_scale" in line or "resolution_info.down_shift" in line:
            offenders.append(f"{path}:{line_no}: {line.strip()}")

if offenders:
    print("[nis-pure] Direct legacy resolution-ratio consumers remain:")
    for offender in offenders:
        print(f"  {offender}")
    raise RuntimeError(
        "Pure NIS requires every direct resolution_info ratio consumer to use ScaleUp()/up_factor"
    )

print("[nis-pure] Pure NVIDIA Image Scaling enabled: exact 85/77/67/59/50% internal render presets + NVScaler.")
