#!/usr/bin/env python3
from pathlib import Path


def replace_once(path: str, old: str, new: str, marker: str) -> None:
    p = Path(path)
    text = p.read_text()
    if marker in text:
        print(f"[texture-detail] {path}: already patched")
        return
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one anchor, found {count}")
    p.write_text(text.replace(old, new, 1))
    print(f"[texture-detail] {path}: patched")


# Moonwitch texture-detail feature. These settings are restart-only because Vulkan samplers
# are cached. The historical internal keys are intentionally kept for config compatibility.
replace_once(
    "src/common/settings.h",
    '''    SwitchableSetting<AspectRatio, true> aspect_ratio{linkage,\n''',
    '''    // Moonwitch texture-detail enhancement: preserve finer source texture detail\n    // through conservative dynamic MIP/LOD compensation without changing render resolution.\n    SwitchableSetting<bool> moonwitch_reconstruction{\n        linkage, false, "moonwitch_reconstruction", Category::Renderer,\n        Specialization::Paired, true, false};\n    SwitchableSetting<int, true> moonwitch_reconstruction_target{\n        linkage, 150, 100, 200, "moonwitch_reconstruction_target", Category::Renderer,\n        Specialization::Scalar | Specialization::Percentage, true, false,\n        &moonwitch_reconstruction};\n\n    SwitchableSetting<AspectRatio, true> aspect_ratio{linkage,\n''',
    "moonwitch_reconstruction_target",
)

# Android native setting wrappers. Names are retained internally to avoid breaking existing INIs.
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

# Register the functional UI items. The target stays paired with the toggle so the existing
# settings machinery hides the intensity control while texture-detail enhancement is disabled.
replace_once(
    "src/android/app/src/main/java/org/yuzu/yuzu_emu/features/settings/model/view/SettingsItem.kt",
    '''            put(\n                SliderSetting(\n                    IntSetting.FSR_SHARPENING_SLIDER,\n''',
    '''            put(\n                SwitchSetting(\n                    BooleanSetting.MOONWITCH_RECONSTRUCTION,\n                    titleId = R.string.mw_reconstruction_stage1,\n                    descriptionId = R.string.mw_reconstruction_stage1_desc\n                )\n            )\n            put(\n                SliderSetting(\n                    IntSetting.MOONWITCH_RECONSTRUCTION_TARGET,\n                    titleId = R.string.mw_reconstruction_target,\n                    descriptionId = R.string.mw_reconstruction_target_desc,\n                    min = 100,\n                    max = 200,\n                    units = "%"\n                )\n            )\n            put(\n                SliderSetting(\n                    IntSetting.FSR_SHARPENING_SLIDER,\n''',
    "BooleanSetting.MOONWITCH_RECONSTRUCTION",
)

# Surface it in the Moonwitch performance center.
replace_once(
    "src/android/app/src/main/java/org/yuzu/yuzu_emu/features/settings/ui/SettingsFragmentPresenter.kt",
    '''        sl.apply {\n            add(HeaderSetting(R.string.mw_pacing_and_latency))\n''',
    '''        sl.apply {\n            add(HeaderSetting(R.string.mw_reconstruction_and_detail))\n            add(BooleanSetting.MOONWITCH_RECONSTRUCTION.key)\n            add(IntSetting.MOONWITCH_RECONSTRUCTION_TARGET.key)\n\n            add(HeaderSetting(R.string.mw_pacing_and_latency))\n''',
    "R.string.mw_reconstruction_and_detail",
)

# UI copy describes only what the feature really does: MIP/LOD detail preservation. It makes no
# temporal-upscaling or SGSR2 claim.
replace_once(
    "src/android/app/src/main/res/values/moonwitch_ui_strings.xml",
    '''    <string name="mw_pacing_and_latency">PACING E LATÊNCIA</string>\n''',
    '''    <string name="mw_reconstruction_and_detail">TEXTURAS E DETALHE</string>\n    <string name="mw_reconstruction_stage1">Detalhe de textura aprimorado</string>\n    <string name="mw_reconstruction_stage1_desc">Ajusta dinamicamente MIP/LOD para preservar texturas mais detalhadas sem aumentar a resolução interna. Pode aumentar cintilação em algumas cenas. Requer reiniciar o jogo.</string>\n    <string name="mw_reconstruction_target">Alvo de detalhe de textura</string>\n    <string name="mw_reconstruction_target_desc">Controla a intensidade da compensação MIP/LOD. Valores maiores priorizam mipmaps mais detalhados; não alteram a resolução interna e não equivalem a renderização em 1,5× ou 2×.</string>\n\n    <string name="mw_pacing_and_latency">PACING E LATÊNCIA</string>\n''',
    "mw_reconstruction_stage1_desc",
)

# Dynamic MIP/LOD preservation. Compensation depends on current render scale and the independent
# detail target. Depth-compare samplers are excluded to avoid destabilising shadow maps. The
# extra negative LOD bias is capped at -2 to keep the mobile implementation conservative.
replace_once(
    "src/video_core/renderer_vulkan/vk_texture_cache.cpp",
    '''#include <algorithm>\n#include <limits>\n''',
    '''#include <algorithm>\n#include <cmath>\n#include <limits>\n''',
    "#include <cmath>",
)

replace_once(
    "src/video_core/renderer_vulkan/vk_texture_cache.cpp",
    '''        .mipLodBias = tsc.LodBias(),\n''',
    '''        .mipLodBias = [&] {\n            const f32 guest_bias = tsc.LodBias();\n            if (!Settings::values.moonwitch_reconstruction.GetValue() ||\n                tsc.depth_compare_enabled || tsc.mipmap_filter == TextureMipmapFilter::None) {\n                return guest_bias;\n            }\n\n            const auto& resolution = Settings::values.resolution_info;\n            const f32 render_scale = static_cast<f32>(resolution.up_scale) /\n                                     static_cast<f32>(1U << resolution.down_shift);\n            const f32 target_scale =\n                static_cast<f32>(Settings::values.moonwitch_reconstruction_target.GetValue()) /\n                100.0f;\n            if (render_scale <= 0.0f || target_scale <= render_scale) {\n                return guest_bias;\n            }\n\n            const f32 reconstruction_bias =\n                std::clamp(std::log2(render_scale / target_scale), -2.0f, 0.0f);\n            // Preserve guest sampler intent while allowing a conservative extra detail bias.\n            return (std::max)(guest_bias + reconstruction_bias, -15.0f);\n        }(),\n''',
    "reconstruction_bias =",
)

print("[texture-detail] Moonwitch MIP/LOD texture-detail feature applied")
