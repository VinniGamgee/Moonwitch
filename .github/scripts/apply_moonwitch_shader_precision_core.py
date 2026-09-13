#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path


def replace_once(path: Path, old: str, new: str, marker: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if marker in text:
        print(f"[moonwitch-shader-precision-core] {label}: already patched")
        return
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one anchor for {label}, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"[moonwitch-shader-precision-core] {label}: patched")


root = Path(".")
settings_h = root / "src/common/settings.h"
profile_h = root / "src/shader_recompiler/profile.h"
floating_point = root / (
    "src/shader_recompiler/backend/spirv/emit_spirv_floating_point.cpp"
)
image = root / "src/shader_recompiler/backend/spirv/emit_spirv_image.cpp"
graphics_pipeline_h = root / "src/video_core/renderer_vulkan/vk_graphics_pipeline.h"
pipeline_cache_h = root / "src/video_core/renderer_vulkan/vk_pipeline_cache.h"
pipeline_cache_cpp = root / "src/video_core/renderer_vulkan/vk_pipeline_cache.cpp"


replace_once(
    settings_h,
    '    SwitchableSetting<bool> barrier_feedback_loops{linkage, true, "barrier_feedback_loops",\n'
    '                                                   Category::RendererAdvanced};\n',
    '    // Opt-in SPIR-V precision variants. Mode 0 preserves upstream behavior; mode 1 is\n'
    '    // limited to FP32 fragment math; mode 2 extends the policy to every shader stage.\n'
    '    SwitchableSetting<int, true> moonwitch_shader_precision_mode{\n'
    '        linkage, 0, 0, 2, "moonwitch_shader_precision_mode",\n'
    '        Category::RendererAdvanced, Specialization::Default, true, true};\n\n'
    '    SwitchableSetting<bool> barrier_feedback_loops{linkage, true, "barrier_feedback_loops",\n'
    '                                                   Category::RendererAdvanced};\n',
    "moonwitch_shader_precision_mode{",
    "register runtime/per-game precision mode",
)

replace_once(
    profile_h,
    "    u64 min_ssbo_alignment{};\n"
    "    u32 max_user_clip_distances{};\n\n"
    "    bool SupportsSubgroupStage(Stage stage) const {\n",
    "    u64 min_ssbo_alignment{};\n"
    "    u32 max_user_clip_distances{};\n\n"
    "    // Moonwitch SPIR-V policy captured by the pipeline cache key.\n"
    "    // 0 = upstream, 1 = selective fragment FP32, 2 = strict all stages.\n"
    "    u32 moonwitch_shader_precision_mode{};\n\n"
    "    bool SupportsSubgroupStage(Stage stage) const {\n",
    "u32 moonwitch_shader_precision_mode{};",
    "carry the precision policy into SPIR-V emission",
)

replace_once(
    floating_point,
    "Id Decorate(EmitContext& ctx, IR::Inst* inst, Id op) {\n"
    "    const auto flags{inst->Flags<IR::FpControl>()};\n"
    "    if (flags.no_contraction) {\n"
    "        ctx.Decorate(op, spv::Decoration::NoContraction);\n"
    "    }\n"
    "    return op;\n"
    "}\n",
    "bool ShouldForceNoContraction(const EmitContext& ctx, bool is_fp32) {\n"
    "    const u32 mode{ctx.profile.moonwitch_shader_precision_mode};\n"
    "    return mode >= 2 ||\n"
    "           (mode == 1 && is_fp32 && ctx.stage == Stage::Fragment);\n"
    "}\n\n"
    "Id Decorate(EmitContext& ctx, IR::Inst* inst, Id op, bool is_fp32) {\n"
    "    const auto flags{inst->Flags<IR::FpControl>()};\n"
    "    if (flags.no_contraction || ShouldForceNoContraction(ctx, is_fp32)) {\n"
    "        ctx.Decorate(op, spv::Decoration::NoContraction);\n"
    "    }\n"
    "    return op;\n"
    "}\n",
    "ShouldForceNoContraction",
    "make NoContraction precision-aware",
)

for operation, width, is_fp32 in (
    ("OpFAdd", "F16", "false"),
    ("OpFAdd", "F32", "true"),
    ("OpFAdd", "F64", "false"),
    ("OpFma", "F16", "false"),
    ("OpFma", "F32", "true"),
    ("OpFma", "F64", "false"),
    ("OpFMul", "F16", "false"),
    ("OpFMul", "F32", "true"),
    ("OpFMul", "F64", "false"),
):
    arguments = "a, b, c" if operation == "OpFma" else "a, b"
    old = f"    return Decorate(ctx, inst, ctx.{operation}(ctx.{width}[1], {arguments}));\n"
    new = (
        f"    return Decorate(ctx, inst, ctx.{operation}(ctx.{width}[1], {arguments}), "
        f"{is_fp32});\n"
    )
    replace_once(
        floating_point,
        old,
        new,
        new.strip(),
        f"tag {operation} {width} precision",
    )

replace_once(
    image,
    "Id Decorate(EmitContext& ctx, IR::Inst* inst, Id sample) {\n"
    "    const auto info{inst->Flags<IR::TextureInstInfo>()};\n"
    "    if (info.relaxed_precision != 0) {\n"
    "        ctx.Decorate(sample, spv::Decoration::RelaxedPrecision);\n"
    "    }\n"
    "    return sample;\n"
    "}\n",
    "bool ShouldKeepRelaxedPrecision(const EmitContext& ctx) {\n"
    "    const u32 mode{ctx.profile.moonwitch_shader_precision_mode};\n"
    "    return mode == 0 || (mode == 1 && ctx.stage != Stage::Fragment);\n"
    "}\n\n"
    "Id Decorate(EmitContext& ctx, IR::Inst* inst, Id sample) {\n"
    "    const auto info{inst->Flags<IR::TextureInstInfo>()};\n"
    "    if (info.relaxed_precision != 0 && ShouldKeepRelaxedPrecision(ctx)) {\n"
    "        ctx.Decorate(sample, spv::Decoration::RelaxedPrecision);\n"
    "    }\n"
    "    return sample;\n"
    "}\n",
    "ShouldKeepRelaxedPrecision",
    "suppress relaxed texture precision only in selected stages",
)

replace_once(
    graphics_pipeline_h,
    "struct GraphicsPipelineCacheKey {\n"
    "    std::array<u64, 6> unique_hashes;\n"
    "    FixedPipelineState state;\n",
    "struct GraphicsPipelineCacheKey {\n"
    "    std::array<u64, 6> unique_hashes;\n"
    "    u64 moonwitch_shader_precision_mode;\n"
    "    FixedPipelineState state;\n",
    "u64 moonwitch_shader_precision_mode;",
    "key graphics pipelines by precision mode",
)

replace_once(
    graphics_pipeline_h,
    "        return sizeof(unique_hashes) + state.Size();\n",
    "        return sizeof(unique_hashes) + sizeof(moonwitch_shader_precision_mode) +\n"
    "               state.Size();\n",
    "sizeof(moonwitch_shader_precision_mode)",
    "hash the graphics precision variant",
)

replace_once(
    pipeline_cache_h,
    "struct ComputePipelineCacheKey {\n"
    "    u64 unique_hash;\n"
    "    u32 shared_memory_size;\n",
    "struct ComputePipelineCacheKey {\n"
    "    u64 unique_hash;\n"
    "    u64 moonwitch_shader_precision_mode;\n"
    "    u32 shared_memory_size;\n",
    "u64 moonwitch_shader_precision_mode;",
    "key compute pipelines by precision mode",
)

replace_once(
    pipeline_cache_cpp,
    '#include "common/fs/path_util.h"\n',
    '#include "common/fs/path_util.h"\n'
    '#include "common/settings.h"\n',
    '#include "common/settings.h"',
    "include runtime settings explicitly",
)

replace_once(
    pipeline_cache_cpp,
    "constexpr u32 CACHE_VERSION = 18;\n",
    "// Pipeline keys now contain the Moonwitch shader-precision variant.\n"
    "constexpr u32 CACHE_VERSION = 19;\n",
    "constexpr u32 CACHE_VERSION = 19;",
    "invalidate incompatible serialized pipeline keys",
)

replace_once(
    pipeline_cache_cpp,
    "template <typename Container>\n"
    "auto MakeSpan(Container& container) {\n"
    "    return std::span(container.data(), container.size());\n"
    "}\n",
    "template <typename Container>\n"
    "auto MakeSpan(Container& container) {\n"
    "    return std::span(container.data(), container.size());\n"
    "}\n\n"
    "u64 CurrentShaderPrecisionMode() {\n"
    "    return static_cast<u64>(std::clamp(\n"
    "        Settings::values.moonwitch_shader_precision_mode.GetValue(), 0, 2));\n"
    "}\n\n"
    "Shader::Profile ShaderProfileForPrecisionMode(const Shader::Profile& base_profile,\n"
    "                                               u64 mode) {\n"
    "    Shader::Profile shader_profile{base_profile};\n"
    "    shader_profile.moonwitch_shader_precision_mode =\n"
    "        static_cast<u32>(std::min<u64>(mode, 2));\n"
    "    return shader_profile;\n"
    "}\n",
    "ShaderProfileForPrecisionMode",
    "capture a bounded precision profile per pipeline variant",
)

replace_once(
    pipeline_cache_cpp,
    "GraphicsPipeline* PipelineCache::CurrentGraphicsPipeline() {\n\n"
    "    if (!RefreshStages(graphics_key.unique_hashes)) {\n",
    "GraphicsPipeline* PipelineCache::CurrentGraphicsPipeline() {\n\n"
    "    graphics_key.moonwitch_shader_precision_mode = CurrentShaderPrecisionMode();\n"
    "    if (!RefreshStages(graphics_key.unique_hashes)) {\n",
    "graphics_key.moonwitch_shader_precision_mode = CurrentShaderPrecisionMode();",
    "refresh graphics precision live",
)

replace_once(
    pipeline_cache_cpp,
    "    const ComputePipelineCacheKey key{\n"
    "        .unique_hash = shader->unique_hash,\n"
    "        .shared_memory_size = qmd.shared_alloc,\n",
    "    const ComputePipelineCacheKey key{\n"
    "        .unique_hash = shader->unique_hash,\n"
    "        .moonwitch_shader_precision_mode = CurrentShaderPrecisionMode(),\n"
    "        .shared_memory_size = qmd.shared_alloc,\n",
    ".moonwitch_shader_precision_mode = CurrentShaderPrecisionMode(),",
    "refresh compute precision live",
)

replace_once(
    pipeline_cache_cpp,
    "    const Shader::IR::Program* previous_stage{};\n"
    "    Shader::Backend::Bindings binding;\n",
    "    const Shader::Profile shader_profile{ShaderProfileForPrecisionMode(\n"
    "        profile, key.moonwitch_shader_precision_mode)};\n"
    "    const Shader::IR::Program* previous_stage{};\n"
    "    Shader::Backend::Bindings binding;\n",
    "const Shader::Profile shader_profile{ShaderProfileForPrecisionMode(",
    "bind graphics compilation to the keyed precision profile",
)

replace_once(
    pipeline_cache_cpp,
    "        const std::vector<u32> code{EmitSPIRV(profile, runtime_info, program, binding)};\n",
    "        const std::vector<u32> code{\n"
    "            EmitSPIRV(shader_profile, runtime_info, program, binding)};\n",
    "EmitSPIRV(shader_profile, runtime_info, program, binding)",
    "emit graphics SPIR-V with the keyed profile",
)

replace_once(
    pipeline_cache_cpp,
    "    const std::vector<u32> code{EmitSPIRV(profile, program)};\n",
    "    const Shader::Profile shader_profile{ShaderProfileForPrecisionMode(\n"
    "        profile, key.moonwitch_shader_precision_mode)};\n"
    "    const std::vector<u32> code{EmitSPIRV(shader_profile, program)};\n",
    "EmitSPIRV(shader_profile, program)",
    "emit compute SPIR-V with the keyed profile",
)

print("Applied Moonwitch Selective Shader Precision core.")
