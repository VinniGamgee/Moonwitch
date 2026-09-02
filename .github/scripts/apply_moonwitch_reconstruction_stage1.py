#!/usr/bin/env python3
from pathlib import Path


def replace_once(path: str, old: str, new: str, marker: str) -> None:
    p = Path(path)
    text = p.read_text()
    if marker in text:
        print(f"[stage1] {path}: already patched")
        return
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one anchor, found {count}")
    p.write_text(text.replace(old, new, 1))
    print(f"[stage1] {path}: patched")


# Native settings. These are deliberately restart-only because Vulkan samplers are cached.
replace_once(
    "src/common/settings.h",
    '''    SwitchableSetting<AspectRatio, true> aspect_ratio{linkage,\n''',
    '''    // Moonwitch Reconstruction stage 1: preserve source texture detail for a higher\n    // reconstruction target without increasing the guest render resolution. The temporal\n    // SGSR2 pass will consume this cleaner source in a later stage.\n    SwitchableSetting<bool> moonwitch_reconstruction{\n        linkage, false, "moonwitch_reconstruction", Category::Renderer,\n        Specialization::Paired, true, false};\n    SwitchableSetting<int, true> moonwitch_reconstruction_target{\n        linkage, 150, 100, 200, "moonwitch_reconstruction_target", Category::Renderer,\n        Specialization::Scalar | Specialization::Percentage, true, false,\n        &moonwitch_reconstruction};\n\n    SwitchableSetting<AspectRatio, true> aspect_ratio{linkage,\n''',
    "moonwitch_reconstruction_target",
)

# Android native setting wrappers.
replace_once(
    "src/android/app/src/main/java/org/yuzu/yuzu_emu/features/settings/model/BooleanSetting.kt",
    '''    SMART_ADAPTIVE_FRAME_SKIP("smart_adaptive_frame_skip"),\n''',
    '''    SMART_ADAPTIVE_FRAME_SKIP("smart_adaptive_frame_skip"),\n    MOONWITCH_RECONSTRUCTION("moonwitch_reconstruction"),\n''',
    "MOONWITCH_RECONSTRUCTION",
)

replace_once(
    "src/android/app/src/main/java/org/yuzu/yuzu_emu/features/settings/model/IntSetting.kt",
    '''    FSR_SHARPENING_SLIDER("fsr_sharpening_slider"),\n''',
    '''    FSR_SHARPENING_SLIDER("fsr_sharpening_slider"),\n    MOONWITCH_RECONSTRUCTION_TARGET("moonwitch_reconstruction_target"),\n''',
    "MOONWITCH_RECONSTRUCTION_TARGET",
)

# Register functional UI items. Target is paired with the toggle, so the existing settings
# machinery hides it while reconstruction preparation is disabled.
replace_once(
    "src/android/app/src/main/java/org/yuzu/yuzu_emu/features/settings/model/view/SettingsItem.kt",
    '''            put(\n                SliderSetting(\n                    IntSetting.FSR_SHARPENING_SLIDER,\n''',
    '''            put(\n                SwitchSetting(\n                    BooleanSetting.MOONWITCH_RECONSTRUCTION,\n                    titleId = R.string.mw_reconstruction_stage1,\n                    descriptionId = R.string.mw_reconstruction_stage1_desc\n                )\n            )\n            put(\n                SliderSetting(\n                    IntSetting.MOONWITCH_RECONSTRUCTION_TARGET,\n                    titleId = R.string.mw_reconstruction_target,\n                    descriptionId = R.string.mw_reconstruction_target_desc,\n                    min = 100,\n                    max = 200,\n                    units = "%"\n                )\n            )\n            put(\n                SliderSetting(\n                    IntSetting.FSR_SHARPENING_SLIDER,\n''',
    "BooleanSetting.MOONWITCH_RECONSTRUCTION",
)

# Surface it in the real Moonwitch performance center, not as a dead shortcut.
replace_once(
    "src/android/app/src/main/java/org/yuzu/yuzu_emu/features/settings/ui/SettingsFragmentPresenter.kt",
    '''        sl.apply {\n            add(HeaderSetting(R.string.mw_pacing_and_latency))\n''',
    '''        sl.apply {\n            add(HeaderSetting(R.string.mw_reconstruction_and_detail))\n            add(BooleanSetting.MOONWITCH_RECONSTRUCTION.key)\n            add(IntSetting.MOONWITCH_RECONSTRUCTION_TARGET.key)\n\n            add(HeaderSetting(R.string.mw_pacing_and_latency))\n''',
    "R.string.mw_reconstruction_and_detail",
)

# Portuguese UI copy is intentionally explicit: stage 1 is real LOD/MIP preparation and is not
# pretending to be the complete temporal SGSR2 implementation yet.
replace_once(
    "src/android/app/src/main/res/values/moonwitch_ui_strings.xml",
    '''    <string name="mw_pacing_and_latency">PACING E LATÊNCIA</string>\n''',
    '''    <string name="mw_reconstruction_and_detail">RECONSTRUÇÃO E DETALHE</string>\n    <string name="mw_reconstruction_stage1">Reconstrução Moonwitch • preparação</string>\n    <string name="mw_reconstruction_stage1_desc">Preserva detalhe real de textura com compensação dinâmica de MIP/LOD sem aumentar a resolução interna. Requer reiniciar o jogo.</string>\n    <string name="mw_reconstruction_target">Alvo de qualidade da reconstrução</string>\n    <string name="mw_reconstruction_target_desc">Qualidade-alvo relativa ao 1×. Em 1×, 150% prepara mipmaps para uma reconstrução equivalente a 1,5× sem renderizar a cena em 1,5×.</string>\n\n    <string name="mw_pacing_and_latency">PACING E LATÊNCIA</string>\n''',
    "mw_reconstruction_stage1_desc",
)

# Dynamic MIP/LOD preservation. This is resolution-agnostic: the compensation depends on the
# current guest render scale and the independent reconstruction target. Depth-compare samplers
# are excluded to avoid destabilising shadow maps. Compensation itself is capped at -2 LODs to
# keep the first mobile experiment conservative against shimmering.
replace_once(
    "src/video_core/renderer_vulkan/vk_texture_cache.cpp",
    '''#include <algorithm>\n#include <limits>\n''',
    '''#include <algorithm>\n#include <cmath>\n#include <limits>\n''',
    "#include <cmath>",
)

replace_once(
    "src/video_core/renderer_vulkan/vk_texture_cache.cpp",
    '''        .mipLodBias = tsc.LodBias(),\n''',
    '''        .mipLodBias = [&] {\n            const f32 guest_bias = tsc.LodBias();\n            if (!Settings::values.moonwitch_reconstruction.GetValue() ||\n                tsc.depth_compare_enabled || tsc.mipmap_filter == TextureMipmapFilter::None) {\n                return guest_bias;\n            }\n\n            const auto& resolution = Settings::values.resolution_info;\n            const f32 render_scale = static_cast<f32>(resolution.up_scale) /\n                                     static_cast<f32>(1U << resolution.down_shift);\n            const f32 target_scale =\n                static_cast<f32>(Settings::values.moonwitch_reconstruction_target.GetValue()) /\n                100.0f;\n            if (render_scale <= 0.0f || target_scale <= render_scale) {\n                return guest_bias;\n            }\n\n            const f32 reconstruction_bias =\n                std::clamp(std::log2(render_scale / target_scale), -2.0f, 0.0f);\n            // Guest samplers are already valid for the physical device. Keep the extra negative\n            // bias inside a conservative Vulkan-safe range while preserving the guest intent.\n            return (std::max)(guest_bias + reconstruction_bias, -15.0f);\n        }(),\n''',
    "reconstruction_bias =",
)

print("[stage1] Moonwitch Reconstruction source patch completed")
