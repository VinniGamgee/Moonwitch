#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path


def replace_once(path: Path, old: str, new: str, marker: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if marker in text:
        print(f"[moonwitch-texture-coherency-android] {label}: already patched")
        return
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one anchor for {label}, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"[moonwitch-texture-coherency-android] {label}: patched")


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
    '    MOONWITCH_RENDER_TARGET_INIT_ALIAS_GUARD('
    '"moonwitch_render_target_init_alias_guard"),\n'
    '    MOONWITCH_TEXTURE_COHERENCY("moonwitch_texture_coherency"),\n',
    "MOONWITCH_TEXTURE_COHERENCY",
    "expose Texture Coherency to Android",
)

replace_once(
    settings_item,
    """            put(
                SwitchSetting(
                    BooleanSetting.MOONWITCH_RENDER_TARGET_INIT_ALIAS_GUARD,
                    titleId = R.string.mw_render_target_guard_title,
                    descriptionId = R.string.mw_render_target_guard_description
                )
            )
            put(
                SwitchSetting(
                    BooleanSetting.SYNC_MEMORY_OPERATIONS,
""",
    """            put(
                SwitchSetting(
                    BooleanSetting.MOONWITCH_RENDER_TARGET_INIT_ALIAS_GUARD,
                    titleId = R.string.mw_render_target_guard_title,
                    descriptionId = R.string.mw_render_target_guard_description
                )
            )
            put(
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
    "BooleanSetting.MOONWITCH_TEXTURE_COHERENCY,",
    "register Texture Coherency setting item",
)

replace_once(
    presenter,
    """            add(IntSetting.MOONWITCH_SAFE_GPU_BARRIERS_MODE.key)
            add(BooleanSetting.MOONWITCH_RENDER_TARGET_INIT_ALIAS_GUARD.key)

            add(BooleanSetting.SYNC_MEMORY_OPERATIONS.key)
""",
    """            add(IntSetting.MOONWITCH_SAFE_GPU_BARRIERS_MODE.key)
            add(BooleanSetting.MOONWITCH_RENDER_TARGET_INIT_ALIAS_GUARD.key)
            add(BooleanSetting.MOONWITCH_TEXTURE_COHERENCY.key)

            add(BooleanSetting.SYNC_MEMORY_OPERATIONS.key)
""",
    "MOONWITCH_TEXTURE_COHERENCY.key",
    "show Texture Coherency in graphics settings",
)

replace_once(
    strings_xml,
    """    <!-- Moonwitch Render Target Guard -->
    <string name="mw_render_target_guard_title">Render Target Init/Alias Guard</string>
    <string name="mw_render_target_guard_description">Initializes the Vulkan state of new render targets and adds targeted visibility after a newer image alias is synchronized. It does not clear pixel data or force GPU WaitIdle.</string>

    <!-- Screen Layouts -->
""",
    """    <!-- Moonwitch Render Target Guard -->
    <string name="mw_render_target_guard_title">Render Target Init/Alias Guard</string>
    <string name="mw_render_target_guard_description">Initializes the Vulkan state of new render targets and adds targeted visibility after a newer image alias is synchronized. It does not clear pixel data or force GPU WaitIdle.</string>

    <!-- Moonwitch Texture Coherency -->
    <string name="mw_texture_coherency_title">Texture Coherency</string>
    <string name="mw_texture_coherency_description">Adds a targeted Vulkan visibility barrier when a GPU-modified image is consumed again as a texture. It runs once per modification and does not force GPU WaitIdle.</string>

    <!-- Screen Layouts -->
""",
    "mw_texture_coherency_title",
    "add English strings",
)

replace_once(
    strings_pt_xml,
    """    <!-- Moonwitch Render Target Guard -->
    <string name="mw_render_target_guard_title">Render Target Init/Alias Guard</string>
    <string name="mw_render_target_guard_description">Inicializa o estado Vulkan de render targets novos e adiciona visibilidade direcionada após sincronizar um alias de imagem mais recente. Não limpa pixels nem força GPU WaitIdle.</string>

    <!-- Screen Layouts -->
""",
    """    <!-- Moonwitch Render Target Guard -->
    <string name="mw_render_target_guard_title">Render Target Init/Alias Guard</string>
    <string name="mw_render_target_guard_description">Inicializa o estado Vulkan de render targets novos e adiciona visibilidade direcionada após sincronizar um alias de imagem mais recente. Não limpa pixels nem força GPU WaitIdle.</string>

    <!-- Moonwitch Texture Coherency -->
    <string name="mw_texture_coherency_title">Coerência de texturas</string>
    <string name="mw_texture_coherency_description">Adiciona uma barreira Vulkan direcionada quando uma imagem modificada pela GPU volta a ser usada como textura. Atua uma vez por modificação e não força GPU WaitIdle.</string>

    <!-- Screen Layouts -->
""",
    "mw_texture_coherency_title",
    "add Brazilian Portuguese strings",
)

replace_once(
    emulation_fragment,
    """            quickSettings.addBooleanSetting(
                R.string.mw_render_target_guard_title,
                container,
                BooleanSetting.MOONWITCH_RENDER_TARGET_INIT_ALIAS_GUARD
            )
""",
    """            quickSettings.addBooleanSetting(
                R.string.mw_render_target_guard_title,
                container,
                BooleanSetting.MOONWITCH_RENDER_TARGET_INIT_ALIAS_GUARD
            )

            quickSettings.addBooleanSetting(
                R.string.mw_texture_coherency_title,
                container,
                BooleanSetting.MOONWITCH_TEXTURE_COHERENCY
            )
""",
    "BooleanSetting.MOONWITCH_TEXTURE_COHERENCY",
    "add Texture Coherency to Quick Settings",
)

print("Applied Moonwitch Texture Coherency Android UI.")
