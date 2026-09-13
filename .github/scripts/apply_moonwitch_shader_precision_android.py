#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path


def replace_once(path: Path, old: str, new: str, marker: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if marker in text:
        print(f"[moonwitch-shader-precision-android] {label}: already patched")
        return
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one anchor for {label}, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"[moonwitch-shader-precision-android] {label}: patched")


root = Path(".")
int_setting = root / (
    "src/android/app/src/main/java/org/yuzu/yuzu_emu/features/settings/model/IntSetting.kt"
)
settings_item = root / (
    "src/android/app/src/main/java/org/yuzu/yuzu_emu/features/settings/model/view/SettingsItem.kt"
)
presenter = root / (
    "src/android/app/src/main/java/org/yuzu/yuzu_emu/features/settings/ui/"
    "SettingsFragmentPresenter.kt"
)
emulation_fragment = root / (
    "src/android/app/src/main/java/org/yuzu/yuzu_emu/fragments/EmulationFragment.kt"
)
arrays_xml = root / "src/android/app/src/main/res/values/arrays.xml"
strings_xml = root / "src/android/app/src/main/res/values/strings.xml"
strings_pt_xml = root / "src/android/app/src/main/res/values-pt-rBR/strings.xml"


replace_once(
    int_setting,
    '    MOONWITCH_SAFE_GPU_BARRIERS_MODE("moonwitch_safe_gpu_barriers_mode"),\n',
    '    MOONWITCH_SAFE_GPU_BARRIERS_MODE("moonwitch_safe_gpu_barriers_mode"),\n'
    '    MOONWITCH_SHADER_PRECISION_MODE("moonwitch_shader_precision_mode"),\n',
    "MOONWITCH_SHADER_PRECISION_MODE",
    "expose shader precision mode to Android",
)

replace_once(
    settings_item,
    """            put(
                SwitchSetting(
                    BooleanSetting.MOONWITCH_TEXTURE_COHERENCY,
                    titleId = R.string.mw_texture_coherency_title,
                    descriptionId = R.string.mw_texture_coherency_description
                )
            )
            put(
                SwitchSetting(
                    BooleanSetting.SYNC_MEMORY_OPERATIONS,
""",
    """            put(
                SwitchSetting(
                    BooleanSetting.MOONWITCH_TEXTURE_COHERENCY,
                    titleId = R.string.mw_texture_coherency_title,
                    descriptionId = R.string.mw_texture_coherency_description
                )
            )
            put(
                SingleChoiceSetting(
                    IntSetting.MOONWITCH_SHADER_PRECISION_MODE,
                    titleId = R.string.mw_shader_precision_title,
                    descriptionId = R.string.mw_shader_precision_description,
                    choicesId = R.array.moonwitchShaderPrecisionNames,
                    valuesId = R.array.moonwitchShaderPrecisionValues
                )
            )
            put(
                SwitchSetting(
                    BooleanSetting.SYNC_MEMORY_OPERATIONS,
""",
    "IntSetting.MOONWITCH_SHADER_PRECISION_MODE,",
    "register shader precision settings item",
)

replace_once(
    presenter,
    """            add(IntSetting.MOONWITCH_SAFE_GPU_BARRIERS_MODE.key)
            add(BooleanSetting.MOONWITCH_RENDER_TARGET_INIT_ALIAS_GUARD.key)
            add(BooleanSetting.MOONWITCH_TEXTURE_COHERENCY.key)

            add(BooleanSetting.SYNC_MEMORY_OPERATIONS.key)
""",
    """            add(IntSetting.MOONWITCH_SAFE_GPU_BARRIERS_MODE.key)
            add(BooleanSetting.MOONWITCH_RENDER_TARGET_INIT_ALIAS_GUARD.key)
            add(BooleanSetting.MOONWITCH_TEXTURE_COHERENCY.key)
            add(IntSetting.MOONWITCH_SHADER_PRECISION_MODE.key)

            add(BooleanSetting.SYNC_MEMORY_OPERATIONS.key)
""",
    "MOONWITCH_SHADER_PRECISION_MODE.key",
    "show shader precision under Moonwitch graphics fixes",
)

replace_once(
    arrays_xml,
    """    <integer-array name="moonwitchSafeGpuBarrierValues">
        <item>0</item>
        <item>1</item>
        <item>2</item>
    </integer-array>

    <string-array name="statsPosition">
""",
    """    <integer-array name="moonwitchSafeGpuBarrierValues">
        <item>0</item>
        <item>1</item>
        <item>2</item>
    </integer-array>

    <string-array name="moonwitchShaderPrecisionNames">
        <item>@string/mw_shader_precision_default</item>
        <item>@string/mw_shader_precision_selective</item>
        <item>@string/mw_shader_precision_strict</item>
    </string-array>

    <integer-array name="moonwitchShaderPrecisionValues">
        <item>0</item>
        <item>1</item>
        <item>2</item>
    </integer-array>

    <string-array name="statsPosition">
""",
    "moonwitchShaderPrecisionNames",
    "add shader precision mode arrays",
)

replace_once(
    strings_xml,
    """    <!-- Moonwitch Texture Coherency -->
    <string name="mw_texture_coherency_title">Texture Coherency</string>
    <string name="mw_texture_coherency_description">Adds a targeted Vulkan visibility barrier when a GPU-modified image is consumed again as a texture. It runs once per modification and does not force GPU WaitIdle.</string>

    <!-- Screen Layouts -->
""",
    """    <!-- Moonwitch Texture Coherency -->
    <string name="mw_texture_coherency_title">Texture Coherency</string>
    <string name="mw_texture_coherency_description">Adds a targeted Vulkan visibility barrier when a GPU-modified image is consumed again as a texture. It runs once per modification and does not force GPU WaitIdle.</string>

    <!-- Moonwitch Selective Shader Precision -->
    <string name="mw_shader_precision_title">Selective shader precision</string>
    <string name="mw_shader_precision_description">Default preserves upstream SPIR-V. Selective requests full precision for fragment texture results and applies NoContraction to FP32 add, multiply, and FMA in fragment shaders. Strict extends the policy to every shader stage and floating-point width. Changing mode creates the matching pipeline variants and may cause temporary compilation stutter.</string>
    <string name="mw_shader_precision_default">Default (off)</string>
    <string name="mw_shader_precision_selective">Selective</string>
    <string name="mw_shader_precision_strict">Strict</string>

    <!-- Screen Layouts -->
""",
    "mw_shader_precision_title",
    "add English shader precision strings",
)

replace_once(
    strings_pt_xml,
    """    <!-- Moonwitch Texture Coherency -->
    <string name="mw_texture_coherency_title">Coerência de texturas</string>
    <string name="mw_texture_coherency_description">Adiciona uma barreira Vulkan direcionada quando uma imagem modificada pela GPU volta a ser usada como textura. Atua uma vez por modificação e não força GPU WaitIdle.</string>

    <!-- Screen Layouts -->
""",
    """    <!-- Moonwitch Texture Coherency -->
    <string name="mw_texture_coherency_title">Coerência de texturas</string>
    <string name="mw_texture_coherency_description">Adiciona uma barreira Vulkan direcionada quando uma imagem modificada pela GPU volta a ser usada como textura. Atua uma vez por modificação e não força GPU WaitIdle.</string>

    <!-- Moonwitch Selective Shader Precision -->
    <string name="mw_shader_precision_title">Precisão seletiva de shaders</string>
    <string name="mw_shader_precision_description">Padrão preserva o SPIR-V original. Seletiva solicita precisão completa nos resultados de textura e aplica NoContraction a soma, multiplicação e FMA FP32 em shaders de fragmento. Rigorosa estende a política a todos os estágios e larguras de ponto flutuante. Trocar o modo cria as variantes de pipeline correspondentes e pode causar travadas temporárias de compilação.</string>
    <string name="mw_shader_precision_default">Padrão (desligado)</string>
    <string name="mw_shader_precision_selective">Seletiva</string>
    <string name="mw_shader_precision_strict">Rigorosa</string>

    <!-- Screen Layouts -->
""",
    "mw_shader_precision_title",
    "add Brazilian Portuguese shader precision strings",
)

replace_once(
    emulation_fragment,
    """            quickSettings.addBooleanSetting(
                R.string.mw_texture_coherency_title,
                container,
                BooleanSetting.MOONWITCH_TEXTURE_COHERENCY
            )
""",
    """            quickSettings.addBooleanSetting(
                R.string.mw_texture_coherency_title,
                container,
                BooleanSetting.MOONWITCH_TEXTURE_COHERENCY
            )

            quickSettings.addIntSetting(
                R.string.mw_shader_precision_title,
                container,
                IntSetting.MOONWITCH_SHADER_PRECISION_MODE,
                R.array.moonwitchShaderPrecisionNames,
                R.array.moonwitchShaderPrecisionValues
            )
""",
    "IntSetting.MOONWITCH_SHADER_PRECISION_MODE,",
    "add shader precision to Quick Settings",
)

print("Applied Moonwitch Selective Shader Precision Android UI.")
