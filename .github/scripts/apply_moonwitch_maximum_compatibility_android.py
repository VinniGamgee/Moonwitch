#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path


def replace_once(path: Path, old: str, new: str, marker: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if marker in text:
        print(f"[moonwitch-maximum-compatibility-android] {label}: already patched")
        return
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one anchor for {label}, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"[moonwitch-maximum-compatibility-android] {label}: patched")


root = Path(".")
boolean_setting = root / (
    "src/android/app/src/main/java/org/yuzu/yuzu_emu/features/settings/model/BooleanSetting.kt"
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
strings_xml = root / "src/android/app/src/main/res/values/strings.xml"
strings_pt_xml = root / "src/android/app/src/main/res/values-pt-rBR/strings.xml"


replace_once(
    boolean_setting,
    '    MOONWITCH_RENDER_TARGET_INIT_ALIAS_GUARD('
    '"moonwitch_render_target_init_alias_guard"),\n',
    '    MOONWITCH_MAXIMUM_COMPATIBILITY("moonwitch_maximum_compatibility"),\n'
    '    MOONWITCH_RENDER_TARGET_INIT_ALIAS_GUARD('
    '"moonwitch_render_target_init_alias_guard"),\n',
    "MOONWITCH_MAXIMUM_COMPATIBILITY",
    "expose the master override to Android",
)

replace_once(
    settings_item,
    """            put(
                SingleChoiceSetting(
                    IntSetting.MOONWITCH_SAFE_GPU_BARRIERS_MODE,
""",
    """            put(
                SwitchSetting(
                    BooleanSetting.MOONWITCH_MAXIMUM_COMPATIBILITY,
                    titleId = R.string.mw_maximum_compatibility_title,
                    descriptionId = R.string.mw_maximum_compatibility_description
                )
            )
            put(
                SingleChoiceSetting(
                    IntSetting.MOONWITCH_SAFE_GPU_BARRIERS_MODE,
""",
    "BooleanSetting.MOONWITCH_MAXIMUM_COMPATIBILITY,",
    "register the master compatibility setting item",
)

replace_once(
    presenter,
    """            add(HeaderSetting(R.string.mw_graphics_fixes_header))
            add(IntSetting.MOONWITCH_SAFE_GPU_BARRIERS_MODE.key)
""",
    """            add(HeaderSetting(R.string.mw_graphics_fixes_header))
            add(BooleanSetting.MOONWITCH_MAXIMUM_COMPATIBILITY.key)
            add(IntSetting.MOONWITCH_SAFE_GPU_BARRIERS_MODE.key)
""",
    "MOONWITCH_MAXIMUM_COMPATIBILITY.key",
    "show the master override above the individual fixes",
)

replace_once(
    emulation_fragment,
    """            quickSettings.addDivider(container)

            quickSettings.addIntSetting(
                R.string.mw_safe_gpu_barriers_title,
""",
    """            quickSettings.addDivider(container)

            quickSettings.addBooleanSetting(
                R.string.mw_maximum_compatibility_title,
                container,
                BooleanSetting.MOONWITCH_MAXIMUM_COMPATIBILITY
            )

            quickSettings.addIntSetting(
                R.string.mw_safe_gpu_barriers_title,
""",
    "BooleanSetting.MOONWITCH_MAXIMUM_COMPATIBILITY",
    "add Maximum Compatibility to Quick Settings",
)

replace_once(
    strings_xml,
    """    <!-- Moonwitch Graphics Fixes -->
    <string name="mw_graphics_fixes_header">Moonwitch graphics fixes</string>
    <string name="mw_safe_gpu_barriers_title">Safe GPU barriers</string>
""",
    """    <!-- Moonwitch Graphics Fixes -->
    <string name="mw_graphics_fixes_header">Moonwitch graphics fixes</string>
    <string name="mw_maximum_compatibility_title">Maximum compatibility</string>
    <string name="mw_maximum_compatibility_description">Master diagnostic override. While enabled, it forces Safe GPU Barriers to Strict, Render Target Init/Alias Guard on, Texture Coherency on, and Shader Precision to Strict. Individual choices remain saved and become effective again when disabled. This mode may reduce performance and cause temporary shader compilation stutter.</string>
    <string name="mw_safe_gpu_barriers_title">Safe GPU barriers</string>
""",
    "mw_maximum_compatibility_title",
    "add English Maximum Compatibility strings",
)

replace_once(
    strings_pt_xml,
    """    <!-- Moonwitch Graphics Fixes -->
    <string name="mw_graphics_fixes_header">Correções gráficas Moonwitch</string>
    <string name="mw_safe_gpu_barriers_title">Barreiras seguras de GPU</string>
""",
    """    <!-- Moonwitch Graphics Fixes -->
    <string name="mw_graphics_fixes_header">Correções gráficas Moonwitch</string>
    <string name="mw_maximum_compatibility_title">Compatibilidade máxima</string>
    <string name="mw_maximum_compatibility_description">Override mestre para diagnóstico. Enquanto estiver ativo, força Barreiras seguras de GPU em Estrito, ativa Render Target Init/Alias Guard e Coerência de texturas, e coloca Precisão de shaders em Rigorosa. As escolhas individuais continuam salvas e voltam a valer ao desativar. Este modo pode reduzir o desempenho e causar travadas temporárias de compilação.</string>
    <string name="mw_safe_gpu_barriers_title">Barreiras seguras de GPU</string>
""",
    "mw_maximum_compatibility_title",
    "add Brazilian Portuguese Maximum Compatibility strings",
)

print("Applied Moonwitch Maximum Compatibility Android UI.")
