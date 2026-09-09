#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path


def replace_once(path: Path, old: str, new: str, marker: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if marker in text:
        print(f"[nis-pure-v2] {label}: already patched")
        return
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one anchor for {label}, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"[nis-pure-v2] {label}: patched")


def replace_count(path: Path, old: str, new: str, expected: int, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != expected:
        raise RuntimeError(f"{path}: expected {expected} anchors for {label}, found {count}")
    path.write_text(text.replace(old, new), encoding="utf-8")
    print(f"[nis-pure-v2] {label}: patched {count} occurrence(s)")


root = Path(".")

# Run all v1 pure-NIS patches, but deliberately stop before its strict legacy-consumer scan.
# V2 patches those consumers below, then performs the same strict scan at the end.
v1_path = root / ".github/scripts/apply_nis_pure_scaling.py"
v1_source = v1_path.read_text(encoding="utf-8")
scan_marker = "# Refuse to build if a direct legacy scale calculation remains in core source."
if scan_marker not in v1_source:
    raise RuntimeError("Pure NIS v1 scan marker not found")
v1_prefix = v1_source.split(scan_marker, 1)[0]
exec(compile(v1_prefix, str(v1_path), "exec"), {"__name__": "__main__"})

rescaling_pass = root / "src/shader_recompiler/ir_opt/rescaling_pass.cpp"
texture_cache_h = root / "src/video_core/texture_cache/texture_cache.h"
texture_cpp = root / "src/video_core/textures/texture.cpp"
rasterizer_cpp = root / "src/video_core/renderer_vulkan/vk_rasterizer.cpp"

# Integer image coordinates in recompiled guest shaders must use the exact NIS ratio too.
# Preserve the old bit-shift path for every legacy resolution mode so this is NIS-only behavior.
replace_once(
    rescaling_pass,
    """[[nodiscard]] IR::U32 Scale(IR::IREmitter& ir, const IR::U1& is_scaled, const IR::U32& value) {
    IR::U32 scaled_value{value};
    if (const u32 up_scale = Settings::values.resolution_info.up_scale; up_scale != 1) {
        scaled_value = ir.IMul(scaled_value, ir.Imm32(up_scale));
    }
    if (const u32 down_shift = Settings::values.resolution_info.down_shift; down_shift != 0) {
        scaled_value = ir.ShiftRightArithmetic(scaled_value, ir.Imm32(down_shift));
    }
    return IR::U32{ir.Select(is_scaled, scaled_value, value)};
}
""",
    """[[nodiscard]] IR::U32 Scale(IR::IREmitter& ir, const IR::U1& is_scaled, const IR::U32& value) {
    IR::U32 scaled_value{value};
    const auto& resolution = Settings::values.resolution_info;
    if (resolution.exact_ratio) {
        if (resolution.exact_numerator != 1) {
            scaled_value = ir.IMul(scaled_value, ir.Imm32(resolution.exact_numerator));
        }
        if (resolution.exact_denominator != 1) {
            scaled_value = ir.IDiv(scaled_value, ir.Imm32(resolution.exact_denominator));
        }
    } else {
        if (resolution.up_scale != 1) {
            scaled_value = ir.IMul(scaled_value, ir.Imm32(resolution.up_scale));
        }
        if (resolution.down_shift != 0) {
            scaled_value = ir.ShiftRightArithmetic(scaled_value, ir.Imm32(resolution.down_shift));
        }
    }
    return IR::U32{ir.Select(is_scaled, scaled_value, value)};
}
""",
    "resolution.exact_numerator != 1",
    "make shader integer upscale exact-ratio aware",
)

replace_once(
    rescaling_pass,
    """[[nodiscard]] IR::U32 DownScale(IR::IREmitter& ir, const IR::U1& is_scaled, const IR::U32& value) {
    IR::U32 scaled_value{value};
    if (const u32 down_shift = Settings::values.resolution_info.down_shift; down_shift != 0) {
        scaled_value = ir.ShiftLeftLogical(scaled_value, ir.Imm32(down_shift));
    }
    if (const u32 up_scale = Settings::values.resolution_info.up_scale; up_scale != 1) {
        scaled_value = ir.IDiv(scaled_value, ir.Imm32(up_scale));
    }
    return IR::U32{ir.Select(is_scaled, scaled_value, value)};
}
""",
    """[[nodiscard]] IR::U32 DownScale(IR::IREmitter& ir, const IR::U1& is_scaled, const IR::U32& value) {
    IR::U32 scaled_value{value};
    const auto& resolution = Settings::values.resolution_info;
    if (resolution.exact_ratio) {
        if (resolution.exact_denominator != 1) {
            scaled_value = ir.IMul(scaled_value, ir.Imm32(resolution.exact_denominator));
        }
        if (resolution.exact_numerator != 1) {
            scaled_value = ir.IDiv(scaled_value, ir.Imm32(resolution.exact_numerator));
        }
    } else {
        if (resolution.down_shift != 0) {
            scaled_value = ir.ShiftLeftLogical(scaled_value, ir.Imm32(resolution.down_shift));
        }
        if (resolution.up_scale != 1) {
            scaled_value = ir.IDiv(scaled_value, ir.Imm32(resolution.up_scale));
        }
    }
    return IR::U32{ir.Select(is_scaled, scaled_value, value)};
}
""",
    "resolution.exact_denominator != 1",
    "make shader integer downscale exact-ratio aware",
)

# Render-target extents must use ResolutionScalingInfo::ScaleUp(), which now understands both
# legacy scales and exact NIS percentages.
replace_once(
    texture_cache_h,
    """    u32 up_scale = 1;
    u32 down_shift = 0;
    if (is_rescaling) {
        up_scale = Settings::values.resolution_info.up_scale;
        down_shift = Settings::values.resolution_info.down_shift;
    }
    render_targets.size = Extent2D{
        (maxwell3d->regs.surface_clip.width * up_scale) >> down_shift,
        (maxwell3d->regs.surface_clip.height * up_scale) >> down_shift,
    };
""",
    """    const auto& resolution = Settings::values.resolution_info;
    render_targets.size = Extent2D{
        is_rescaling ? resolution.ScaleUp(maxwell3d->regs.surface_clip.width)
                     : maxwell3d->regs.surface_clip.width,
        is_rescaling ? resolution.ScaleUp(maxwell3d->regs.surface_clip.height)
                     : maxwell3d->regs.surface_clip.height,
    };
""",
    "is_rescaling ? resolution.ScaleUp(maxwell3d->regs.surface_clip.width)",
    "make render-target extents exact-ratio aware",
)

# Automatic anisotropy only needs the scalar integer multiplier. NIS presets are below 1x,
# so they correctly add no anisotropic level.
replace_once(
    texture_cpp,
    """        const u32 resolution_scale = Settings::values.resolution_info.up_scale >>
                                     Settings::values.resolution_info.down_shift;
""",
    """        const u32 resolution_scale =
            static_cast<u32>(Settings::values.resolution_info.up_factor);
""",
    "static_cast<u32>(Settings::values.resolution_info.up_factor)",
    "make automatic anisotropy scale exact-ratio aware",
)

# Scissors need conservative outward rounding during sub-native rendering. Keep the historical
# integer bit-shift path untouched for legacy modes and use the exact float only for NIS.
replace_once(
    rasterizer_cpp,
    """VkRect2D GetScissorState(const Maxwell& regs, size_t index, u32 up_scale = 1, u32 down_shift = 0) {
    const auto& src = regs.scissor_test[index];
    VkRect2D scissor{};
    const auto scale_up = [&](s32 value) -> s32 {
        if (value == 0) {
            return 0U;
        }
        const s32 upset = value * up_scale;
        s32 acumm = 0;
        if ((up_scale >> down_shift) == 0) {
            acumm = upset % 2;
        }
        const s32 converted_value = (value * up_scale) >> down_shift;
        return value < 0 ? std::min<s32>(converted_value - acumm, -1)
                         : std::max<s32>(converted_value + acumm, 1);
    };
""",
    """VkRect2D GetScissorState(const Maxwell& regs, size_t index, u32 up_scale = 1,
                         u32 down_shift = 0, f32 exact_scale = 0.0f) {
    const auto& src = regs.scissor_test[index];
    VkRect2D scissor{};
    const auto scale_up = [&](s32 value) -> s32 {
        if (value == 0) {
            return 0U;
        }
        if (exact_scale > 0.0f) {
            const f32 scaled = static_cast<f32>(value) * exact_scale;
            const s32 rounded = value < 0 ? static_cast<s32>(std::floor(scaled))
                                          : static_cast<s32>(std::ceil(scaled));
            return value < 0 ? std::min<s32>(rounded, -1) : std::max<s32>(rounded, 1);
        }
        const s32 upset = value * up_scale;
        s32 acumm = 0;
        if ((up_scale >> down_shift) == 0) {
            acumm = upset % 2;
        }
        const s32 converted_value = (value * up_scale) >> down_shift;
        return value < 0 ? std::min<s32>(converted_value - acumm, -1)
                         : std::max<s32>(converted_value + acumm, 1);
    };
""",
    "f32 exact_scale = 0.0f",
    "add exact NIS scissor scale",
)

legacy_scissor_setup = """    u32 up_scale = 1;
    u32 down_shift = 0;
    if (texture_cache.IsRescaling()) {
        up_scale = Settings::values.resolution_info.up_scale;
        down_shift = Settings::values.resolution_info.down_shift;
    }
"""
exact_scissor_setup = """    u32 up_scale = 1;
    u32 down_shift = 0;
    f32 exact_scale = 0.0f;
    if (texture_cache.IsRescaling()) {
        const auto& resolution = Settings::values.resolution_info;
        if (resolution.exact_ratio) {
            exact_scale = resolution.up_factor;
        } else {
            up_scale = resolution.up_scale;
            down_shift = resolution.down_shift;
        }
    }
"""
replace_count(rasterizer_cpp, legacy_scissor_setup, exact_scissor_setup, 2,
              "make clear/dynamic scissors exact-ratio aware")

# One clear-scissor call plus 16 viewport scissors use this exact call suffix.
replace_count(
    rasterizer_cpp,
    ", up_scale, down_shift)",
    ", up_scale, down_shift, exact_scale)",
    17,
    "pass exact NIS scale to scissors",
)

# Strict validation: no core consumer may bypass exact-ratio-aware helpers by reaching directly
# through resolution_info.up_scale/down_shift. Uses through a local 'resolution' object above are
# intentional and explicitly branch on exact_ratio.
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
    print("[nis-pure-v2] Direct legacy resolution-ratio consumers remain:")
    for offender in offenders:
        print(f"  {offender}")
    raise RuntimeError("Exact NIS scale has not reached every renderer consumer")

print("[nis-pure-v2] Exact NIS render scale propagated through shader coordinates, render targets, scissors, texture accounting and rasterizer paths.")
