#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path


def replace_once(path: Path, old: str, new: str, marker: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if marker in text:
        print(f"[moonwitch-safe-barriers-android] {label}: already patched")
        return
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one anchor for {label}, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"[moonwitch-safe-barriers-android] {label}: patched")


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
    '    DMA_ACCURACY("dma_accuracy"),\n',
    '    DMA_ACCURACY("dma_accuracy"),\n'
    '    MOONWITCH_SAFE_GPU_BARRIERS_MODE("moonwitch_safe_gpu_barriers_mode"),\n',
    "MOONWITCH_SAFE_GPU_BARRIERS_MODE",
    "expose barrier mode to Android",
)

replace_once(
    settings_item,
    """            put(
                SwitchSetting(
                    BooleanSetting.SYNC_MEMORY_OPERATIONS,
                    titleId = R.string.sync_memory_operations,
                    descriptionId = R.string.sync_memory_operations_description
                )
            )
""",
    """            put(
                SingleChoiceSetting(
                    IntSetting.MOONWITCH_SAFE_GPU_BARRIERS_MODE,
                    titleId = R.string.mw_safe_gpu_barriers_title,
                    descriptionId = R.string.mw_safe_gpu_barriers_description,
                    choicesId = R.array.moonwitchSafeGpuBarrierNames,
                    valuesId = R.array.moonwitchSafeGpuBarrierValues
                )
            )
            put(
                SwitchSetting(
                    BooleanSetting.SYNC_MEMORY_OPERATIONS,
                    titleId = R.string.sync_memory_operations,
                    descriptionId = R.string.sync_memory_operations_description
                )
            )
""",
    "IntSetting.MOONWITCH_SAFE_GPU_BARRIERS_MODE",
    "register barrier setting item",
)

replace_once(
    presenter,
    """            add(BooleanSetting.BUFFER_REORDER_DISABLE.key)

            add(BooleanSetting.SYNC_MEMORY_OPERATIONS.key)
""",
    """            add(BooleanSetting.BUFFER_REORDER_DISABLE.key)

            add(HeaderSetting(R.string.mw_graphics_fixes_header))
            add(IntSetting.MOONWITCH_SAFE_GPU_BARRIERS_MODE.key)

            add(BooleanSetting.SYNC_MEMORY_OPERATIONS.key)
""",
    "mw_graphics_fixes_header",
    "show setting in graphics",
)

replace_once(
    arrays_xml,
    '    <string-array name="statsPosition">\n',
    """    <string-array name="moonwitchSafeGpuBarrierNames">
        <item>@string/mw_safe_gpu_barriers_default</item>
        <item>@string/mw_safe_gpu_barriers_safe</item>
        <item>@string/mw_safe_gpu_barriers_strict</item>
    </string-array>

    <integer-array name="moonwitchSafeGpuBarrierValues">
        <item>0</item>
        <item>1</item>
        <item>2</item>
    </integer-array>

    <string-array name="statsPosition">
""",
    "moonwitchSafeGpuBarrierNames",
    "add barrier mode arrays",
)

replace_once(
    strings_xml,
    '    <!-- Screen Layouts -->\n',
    """    <!-- Moonwitch Graphics Fixes -->
    <string name="mw_graphics_fixes_header">Moonwitch graphics fixes</string>
    <string name="mw_safe_gpu_barriers_title">Safe GPU barriers</string>
    <string name="mw_safe_gpu_barriers_description">Adds Vulkan memory visibility only when the game requests a fragment or tiled-cache barrier. Safe targets stale reads; Strict also serializes later writes and may cost more performance.</string>
    <string name="mw_safe_gpu_barriers_default">Default (off)</string>
    <string name="mw_safe_gpu_barriers_safe">Safe</string>
    <string name="mw_safe_gpu_barriers_strict">Strict</string>

    <!-- Screen Layouts -->
""",
    "mw_safe_gpu_barriers_title",
    "add English strings",
)

replace_once(
    strings_pt_xml,
    '    <!-- Screen Layouts -->\n',
    """    <!-- Moonwitch Graphics Fixes -->
    <string name="mw_graphics_fixes_header">Correções gráficas Moonwitch</string>
    <string name="mw_safe_gpu_barriers_title">Barreiras seguras de GPU</string>
    <string name="mw_safe_gpu_barriers_description">Adiciona visibilidade de memória Vulkan somente quando o jogo solicita uma barreira de fragmento ou cache em blocos. Seguro corrige leituras antigas; Estrito também serializa escritas posteriores e pode custar mais desempenho.</string>
    <string name="mw_safe_gpu_barriers_default">Padrão (desligado)</string>
    <string name="mw_safe_gpu_barriers_safe">Seguro</string>
    <string name="mw_safe_gpu_barriers_strict">Estrito</string>

    <!-- Screen Layouts -->
""",
    "mw_safe_gpu_barriers_title",
    "add Brazilian Portuguese strings",
)

replace_once(
    emulation_fragment,
    """            quickSettings.addSliderSetting(
                R.string.mw_color_grading_strength,
                container,
                IntSetting.MOONWITCH_COLOR_GRADING_STRENGTH,
                minValue = 0,
                maxValue = 100,
                units = "%"
            )
""",
    """            quickSettings.addSliderSetting(
                R.string.mw_color_grading_strength,
                container,
                IntSetting.MOONWITCH_COLOR_GRADING_STRENGTH,
                minValue = 0,
                maxValue = 100,
                units = "%"
            )

            quickSettings.addDivider(container)

            quickSettings.addIntSetting(
                R.string.mw_safe_gpu_barriers_title,
                container,
                IntSetting.MOONWITCH_SAFE_GPU_BARRIERS_MODE,
                R.array.moonwitchSafeGpuBarrierNames,
                R.array.moonwitchSafeGpuBarrierValues
            )
""",
    "IntSetting.MOONWITCH_SAFE_GPU_BARRIERS_MODE",
    "add barrier mode to Quick Settings",
)

print("Applied Moonwitch Safe GPU Barriers Android settings and Quick Settings UI.")
