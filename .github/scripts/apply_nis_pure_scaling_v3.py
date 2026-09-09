#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path

root = Path(".")
v2_path = root / ".github/scripts/apply_nis_pure_scaling_v2.py"
v2_source = v2_path.read_text(encoding="utf-8")
scan_marker = "# Strict validation: no core consumer may bypass exact-ratio-aware helpers"
if scan_marker not in v2_source:
    raise RuntimeError("Pure NIS v2 scan marker not found")

# Run V2 through all renderer propagation patches, stopping before its final scan. V2's original
# idempotence marker for DownScale overlaps Scale's denominator check, so complete that one patch
# explicitly below before validating the tree.
exec(compile(v2_source.split(scan_marker, 1)[0], str(v2_path), "exec"),
     {"__name__": "__main__"})

rescaling_pass = root / "src/shader_recompiler/ir_opt/rescaling_pass.cpp"
text = rescaling_pass.read_text(encoding="utf-8")
old = """[[nodiscard]] IR::U32 DownScale(IR::IREmitter& ir, const IR::U1& is_scaled, const IR::U32& value) {
    IR::U32 scaled_value{value};
    if (const u32 down_shift = Settings::values.resolution_info.down_shift; down_shift != 0) {
        scaled_value = ir.ShiftLeftLogical(scaled_value, ir.Imm32(down_shift));
    }
    if (const u32 up_scale = Settings::values.resolution_info.up_scale; up_scale != 1) {
        scaled_value = ir.IDiv(scaled_value, ir.Imm32(up_scale));
    }
    return IR::U32{ir.Select(is_scaled, scaled_value, value)};
}
"""
new = """[[nodiscard]] IR::U32 DownScale(IR::IREmitter& ir, const IR::U1& is_scaled, const IR::U32& value) {
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
"""
if old in text:
    if text.count(old) != 1:
        raise RuntimeError("DownScale legacy anchor is not unique")
    rescaling_pass.write_text(text.replace(old, new, 1), encoding="utf-8")
    print("[nis-pure-v3] shader integer downscale: patched")
elif "scaled_value = ir.IMul(scaled_value, ir.Imm32(resolution.exact_denominator));" in text:
    print("[nis-pure-v3] shader integer downscale: already patched")
else:
    raise RuntimeError("DownScale exact-ratio patch anchor not found")

# Final hard guard. If this passes, every direct old resolution_info ratio consumer discovered in
# the renderer has been replaced by an exact-aware path.
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
    print("[nis-pure-v3] Direct legacy resolution-ratio consumers remain:")
    for offender in offenders:
        print(f"  {offender}")
    raise RuntimeError("Exact NIS scale has not reached every renderer consumer")

print("[nis-pure-v3] PURE NIS: exact 85/77/67/59/50% internal rendering reaches the full rescaling path before official NVScaler output.")
