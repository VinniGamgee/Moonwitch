#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path


TAG = "[moonwitch-core-director-android]"


def replace_once(path: Path, old: str, new: str, marker: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if marker in text:
        print(f"{TAG} {label}: already patched")
        return
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one anchor for {label}, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"{TAG} {label}: patched")


def replace_exact_count(
    path: Path, old: str, new: str, marker: str, expected: int, label: str
) -> None:
    text = path.read_text(encoding="utf-8")
    if marker in text:
        print(f"{TAG} {label}: already patched")
        return
    count = text.count(old)
    if count != expected:
        raise RuntimeError(f"{path}: expected {expected} anchors for {label}, found {count}")
    path.write_text(text.replace(old, new), encoding="utf-8")
    print(f"{TAG} {label}: patched")


root = Path(".")
native_config = root / "src/android/app/src/main/jni/native_config.cpp"
native_lab = root / "src/android/app/src/main/jni/native_performance_lab.cpp"
boolean_setting = root / (
    "src/android/app/src/main/java/org/yuzu/yuzu_emu/features/settings/model/BooleanSetting.kt"
)
settings_model = root / (
    "src/android/app/src/main/java/org/yuzu/yuzu_emu/features/settings/model/Settings.kt"
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
performance_native = root / (
    "src/android/app/src/main/java/org/yuzu/yuzu_emu/utils/PerformanceLabNative.kt"
)
performance_overlay = root / (
    "src/android/app/src/main/java/org/yuzu/yuzu_emu/views/PerformanceLabOverlayView.kt"
)
strings_xml = root / "src/android/app/src/main/res/values/strings.xml"
strings_pt_xml = root / "src/android/app/src/main/res/values-pt-rBR/strings.xml"


replace_once(
    native_config,
    '#include "common/moonwitch_unleashed.h"\n',
    '#include "common/moonwitch_unleashed.h"\n#include "common/moonwitch_core_director.h"\n',
    '#include "common/moonwitch_core_director.h"',
    "include native Core Director",
)

replace_once(
    native_config,
    "void SyncMoonwitchUnleashedSetting() {\n"
    "    Common::MoonwitchUnleashed::SetEnabled(\n"
    "        Settings::values.moonwitch_unleashed.GetValue());\n"
    "}\n",
    "void SyncMoonwitchUnleashedSetting() {\n"
    "    Common::MoonwitchUnleashed::SetEnabled(\n"
    "        Settings::values.moonwitch_unleashed.GetValue());\n"
    "}\n\n"
    "void SyncMoonwitchCoreDirectorSetting() {\n"
    "    Common::MoonwitchCoreDirector::SetEnabled(\n"
    "        Settings::values.moonwitch_core_director.GetValue());\n"
    "}\n",
    "void SyncMoonwitchCoreDirectorSetting()",
    "add setting-to-runtime synchronization",
)

replace_exact_count(
    native_config,
    "    SyncMoonwitchUnleashedSetting();\n",
    "    SyncMoonwitchUnleashedSetting();\n    SyncMoonwitchCoreDirectorSetting();\n",
    "SyncMoonwitchUnleashedSetting();\n    SyncMoonwitchCoreDirectorSetting();",
    3,
    "synchronize all configuration loads",
)

replace_once(
    native_config,
    "    Common::MoonwitchUnleashed::SetEnabled(false);\n"
    "    global_config.reset();\n",
    "    Common::MoonwitchCoreDirector::SetEnabled(false);\n"
    "    Common::MoonwitchUnleashed::SetEnabled(false);\n"
    "    global_config.reset();\n",
    "MoonwitchCoreDirector::SetEnabled(false);",
    "restore affinity when global configuration unloads",
)

replace_once(
    native_config,
    "    if (setting == &Settings::values.moonwitch_unleashed) {\n"
    "        Common::MoonwitchUnleashed::SetEnabled(static_cast<bool>(value));\n"
    "    }\n",
    "    if (setting == &Settings::values.moonwitch_unleashed) {\n"
    "        Common::MoonwitchUnleashed::SetEnabled(static_cast<bool>(value));\n"
    "    }\n"
    "    if (setting == &Settings::values.moonwitch_core_director) {\n"
    "        Common::MoonwitchCoreDirector::SetEnabled(static_cast<bool>(value));\n"
    "    }\n",
    "setting == &Settings::values.moonwitch_core_director",
    "apply Core Director toggle live",
)


replace_once(
    native_lab,
    '#include "common/moonwitch_unleashed.h"\n',
    '#include "common/moonwitch_unleashed.h"\n#include "common/moonwitch_core_director.h"\n',
    '#include "common/moonwitch_core_director.h"',
    "include Core Director telemetry",
)

replace_once(
    native_lab,
    "    constexpr jsize StatCount = 50;\n",
    "    constexpr jsize StatCount = 63;\n",
    "constexpr jsize StatCount = 63;",
    "extend telemetry payload",
)

replace_once(
    native_lab,
    "    values[49] = static_cast<double>(unleashed.active.sample_count);\n\n",
    "    values[49] = static_cast<double>(unleashed.active.sample_count);\n\n"
    "    const auto core_director = Common::MoonwitchCoreDirector::GetTelemetry();\n"
    "    values[50] = core_director.enabled ? 1.0 : 0.0;\n"
    "    values[51] = core_director.snapdragon_detected ? 1.0 : 0.0;\n"
    "    values[52] = core_director.topology_available ? 1.0 : 0.0;\n"
    "    values[53] = static_cast<double>(core_director.registered_threads);\n"
    "    values[54] = static_cast<double>(core_director.applied_threads);\n"
    "    values[55] = static_cast<double>(core_director.failed_threads);\n"
    "    values[56] = static_cast<double>(core_director.allowed_core_count);\n"
    "    values[57] = static_cast<double>(core_director.performance_core_count);\n"
    "    values[58] = static_cast<double>(core_director.performance_core_mask);\n"
    "    values[59] = static_cast<double>(core_director.prime_core);\n"
    "    values[60] = static_cast<double>(core_director.apply_events);\n"
    "    values[61] = static_cast<double>(core_director.drift_repairs);\n"
    "    values[62] = static_cast<double>(core_director.restore_events);\n\n",
    "const auto core_director = Common::MoonwitchCoreDirector::GetTelemetry();",
    "export Core Director telemetry",
)


replace_once(
    boolean_setting,
    '    MOONWITCH_UNLEASHED("moonwitch_unleashed"),\n',
    '    MOONWITCH_UNLEASHED("moonwitch_unleashed"),\n'
    '    MOONWITCH_CORE_DIRECTOR("moonwitch_core_director"),\n',
    "MOONWITCH_CORE_DIRECTOR",
    "expose runtime setting to Kotlin",
)

replace_once(
    settings_model,
    "        SECTION_MOONWITCH_UNLEASHED(R.string.mw_unleashed_title),\n",
    "        SECTION_MOONWITCH_UNLEASHED(R.string.mw_unleashed_title),\n"
    "        SECTION_MOONWITCH_CORE_DIRECTOR(R.string.mw_core_director_title),\n",
    "SECTION_MOONWITCH_CORE_DIRECTOR",
    "register dedicated settings page",
)

replace_once(
    settings_item,
    """            put(
                SwitchSetting(
                    BooleanSetting.MOONWITCH_UNLEASHED,
                    titleId = R.string.mw_unleashed_title,
                    descriptionId = R.string.mw_unleashed_description
                )
            )
            put(
                SwitchSetting(
                    BooleanSetting.SHOW_PERFORMANCE_OVERLAY,
""",
    """            put(
                SwitchSetting(
                    BooleanSetting.MOONWITCH_UNLEASHED,
                    titleId = R.string.mw_unleashed_title,
                    descriptionId = R.string.mw_unleashed_description
                )
            )
            put(
                SwitchSetting(
                    BooleanSetting.MOONWITCH_CORE_DIRECTOR,
                    titleId = R.string.mw_core_director_title,
                    descriptionId = R.string.mw_core_director_description
                )
            )
            put(
                SwitchSetting(
                    BooleanSetting.SHOW_PERFORMANCE_OVERLAY,
""",
    "BooleanSetting.MOONWITCH_CORE_DIRECTOR,",
    "register Core Director switch item",
)


replace_once(
    presenter,
    "            MenuTag.SECTION_MOONWITCH_UNLEASHED -> addMoonwitchUnleashedSettings(sl)\n",
    "            MenuTag.SECTION_MOONWITCH_UNLEASHED -> addMoonwitchUnleashedSettings(sl)\n"
    "            MenuTag.SECTION_MOONWITCH_CORE_DIRECTOR -> addMoonwitchCoreDirectorSettings(sl)\n",
    "SECTION_MOONWITCH_CORE_DIRECTOR ->",
    "route dedicated settings page",
)

replace_once(
    presenter,
    """            add(
                SubmenuSetting(
                    titleId = R.string.mw_unleashed_title,
                    descriptionId = R.string.mw_unleashed_menu_description,
                    iconId = R.drawable.ic_mw_gauge,
                    menuKey = MenuTag.SECTION_MOONWITCH_UNLEASHED
                )
            )
            add(BooleanSetting.RENDERER_USE_SPEED_LIMIT.key)
""",
    """            add(
                SubmenuSetting(
                    titleId = R.string.mw_unleashed_title,
                    descriptionId = R.string.mw_unleashed_menu_description,
                    iconId = R.drawable.ic_mw_gauge,
                    menuKey = MenuTag.SECTION_MOONWITCH_UNLEASHED
                )
            )
            add(
                SubmenuSetting(
                    titleId = R.string.mw_core_director_title,
                    descriptionId = R.string.mw_core_director_menu_description,
                    iconId = R.drawable.ic_mw_gauge,
                    menuKey = MenuTag.SECTION_MOONWITCH_CORE_DIRECTOR
                )
            )
            add(BooleanSetting.RENDERER_USE_SPEED_LIMIT.key)
""",
    "menuKey = MenuTag.SECTION_MOONWITCH_CORE_DIRECTOR",
    "add Core Director entry to Performance Center",
)

replace_once(
    presenter,
    "    private fun addDriversComponentsSettings(sl: ArrayList<SettingsItem>) {\n",
    '''    private fun addMoonwitchCoreDirectorSettings(sl: ArrayList<SettingsItem>) {
        val snapshot = runCatching { PerformanceLabNative.snapshot() }.getOrNull()
        val mask = snapshot?.coreDirectorPerformanceMask ?: 0L
        val maskText = (0 until 64)
            .filter { cpu -> (mask and (1L shl cpu)) != 0L }
            .joinToString(",")
            .ifEmpty { "—" }
        val status = when {
            snapshot == null -> context.getString(R.string.mw_core_director_unavailable)
            !snapshot.coreDirectorEnabled -> context.getString(R.string.mw_core_director_off)
            !snapshot.coreDirectorSnapdragonDetected ->
                context.getString(R.string.mw_core_director_non_snapdragon)
            !snapshot.coreDirectorTopologyAvailable ->
                context.getString(R.string.mw_core_director_topology_unavailable)
            !NativeLibrary.isRunning() -> context.getString(
                R.string.mw_core_director_armed,
                maskText,
                snapshot.coreDirectorPerformanceCores,
                snapshot.coreDirectorAllowedCores
            )
            snapshot.coreDirectorRegisteredThreads == 0 ->
                context.getString(R.string.mw_core_director_waiting_threads)
            snapshot.coreDirectorAppliedThreads == snapshot.coreDirectorRegisteredThreads ->
                context.getString(
                    R.string.mw_core_director_active,
                    snapshot.coreDirectorAppliedThreads,
                    snapshot.coreDirectorRegisteredThreads,
                    maskText,
                    snapshot.coreDirectorPrimeCore,
                    snapshot.coreDirectorDriftRepairs
                )
            snapshot.coreDirectorAppliedThreads == 0 ->
                context.getString(R.string.mw_core_director_rejected)
            else -> context.getString(
                R.string.mw_core_director_partial,
                snapshot.coreDirectorAppliedThreads,
                snapshot.coreDirectorRegisteredThreads,
                snapshot.coreDirectorFailedThreads,
                maskText
            )
        }

        sl.apply {
            add(HeaderSetting(R.string.mw_core_director_control_header))
            add(BooleanSetting.MOONWITCH_CORE_DIRECTOR.key)
            add(
                RunnableSetting(
                    titleId = R.string.mw_core_director_refresh,
                    descriptionString = status,
                    isRunnable = true,
                    iconId = R.drawable.ic_refresh
                ) { loadSettingsList(true) }
            )
        }
    }

    private fun addDriversComponentsSettings(sl: ArrayList<SettingsItem>) {
''',
    "private fun addMoonwitchCoreDirectorSettings",
    "add live Core Director status page",
)


replace_once(
    emulation_fragment,
    """            quickSettings.addBooleanSetting(
                R.string.mw_unleashed_title,
                container,
                BooleanSetting.MOONWITCH_UNLEASHED
            )
            quickSettings.addDivider(container)
""",
    """            quickSettings.addBooleanSetting(
                R.string.mw_unleashed_title,
                container,
                BooleanSetting.MOONWITCH_UNLEASHED
            )
            quickSettings.addBooleanSetting(
                R.string.mw_core_director_title,
                container,
                BooleanSetting.MOONWITCH_CORE_DIRECTOR
            )
            quickSettings.addDivider(container)
""",
    "R.string.mw_core_director_title,\n                container,\n                BooleanSetting.MOONWITCH_CORE_DIRECTOR",
    "add live Quick Settings toggle",
)


replace_once(
    performance_native,
    "        val unleashedActiveP99Ms: Double,\n"
    "        val unleashedActiveSamples: Int\n",
    "        val unleashedActiveP99Ms: Double,\n"
    "        val unleashedActiveSamples: Int,\n"
    "        val coreDirectorEnabled: Boolean,\n"
    "        val coreDirectorSnapdragonDetected: Boolean,\n"
    "        val coreDirectorTopologyAvailable: Boolean,\n"
    "        val coreDirectorRegisteredThreads: Int,\n"
    "        val coreDirectorAppliedThreads: Int,\n"
    "        val coreDirectorFailedThreads: Int,\n"
    "        val coreDirectorAllowedCores: Int,\n"
    "        val coreDirectorPerformanceCores: Int,\n"
    "        val coreDirectorPerformanceMask: Long,\n"
    "        val coreDirectorPrimeCore: Int,\n"
    "        val coreDirectorApplyEvents: Long,\n"
    "        val coreDirectorDriftRepairs: Long,\n"
    "        val coreDirectorRestoreEvents: Long\n",
    "val coreDirectorEnabled: Boolean",
    "model Core Director telemetry",
)

replace_once(
    performance_native,
    "        if (values.size < 50) {\n",
    "        if (values.size < 63) {\n",
    "if (values.size < 63)",
    "require extended telemetry payload",
)

replace_once(
    performance_native,
    "                0.0, 0.0, 0.0, 0, 0.0, 0.0, 0.0, 0\n"
    "            )\n",
    "                0.0, 0.0, 0.0, 0, 0.0, 0.0, 0.0, 0,\n"
    "                false, false, false, 0, 0, 0, 0, 0, 0L, 0, 0L, 0L, 0L\n"
    "            )\n",
    "false, false, false, 0, 0, 0, 0, 0, 0L, 0, 0L, 0L, 0L",
    "add safe telemetry fallback",
)

replace_once(
    performance_native,
    "            unleashedActiveP99Ms = values[48],\n"
    "            unleashedActiveSamples = values[49].toInt()\n",
    "            unleashedActiveP99Ms = values[48],\n"
    "            unleashedActiveSamples = values[49].toInt(),\n"
    "            coreDirectorEnabled = values[50] != 0.0,\n"
    "            coreDirectorSnapdragonDetected = values[51] != 0.0,\n"
    "            coreDirectorTopologyAvailable = values[52] != 0.0,\n"
    "            coreDirectorRegisteredThreads = values[53].toInt(),\n"
    "            coreDirectorAppliedThreads = values[54].toInt(),\n"
    "            coreDirectorFailedThreads = values[55].toInt(),\n"
    "            coreDirectorAllowedCores = values[56].toInt(),\n"
    "            coreDirectorPerformanceCores = values[57].toInt(),\n"
    "            coreDirectorPerformanceMask = values[58].toLong(),\n"
    "            coreDirectorPrimeCore = values[59].toInt(),\n"
    "            coreDirectorApplyEvents = values[60].toLong(),\n"
    "            coreDirectorDriftRepairs = values[61].toLong(),\n"
    "            coreDirectorRestoreEvents = values[62].toLong()\n",
    "coreDirectorEnabled = values[50]",
    "map Core Director telemetry",
)


replace_once(
    performance_overlay,
    '''        val baseText = "$metrics\\n$unleashedStatus\\n$adpfStatus\\n$pacingStatus\\n$frameSkipStatus"
''',
    '''        val coreMaskText = (0 until 64)
            .filter { cpu -> (snapshot.coreDirectorPerformanceMask and (1L shl cpu)) != 0L }
            .joinToString(",")
            .ifEmpty { "—" }
        val coreDirectorStatus = when {
            !snapshot.coreDirectorEnabled -> "CORE DIRECTOR | OFF"
            !snapshot.coreDirectorSnapdragonDetected -> "CORE DIRECTOR | SNAPDRAGON REQUIRED"
            !snapshot.coreDirectorTopologyAvailable -> "CORE DIRECTOR | TOPOLOGY UNAVAILABLE"
            snapshot.coreDirectorRegisteredThreads == 0 ->
                "CORE DIRECTOR | waiting for critical threads | CPU[$coreMaskText]"
            snapshot.coreDirectorAppliedThreads == snapshot.coreDirectorRegisteredThreads ->
                String.format(
                    Locale.US,
                    "CORE DIRECTOR | ACTIVE | %d/%dT | CPU[%s] | prime %d | repair %d",
                    snapshot.coreDirectorAppliedThreads,
                    snapshot.coreDirectorRegisteredThreads,
                    coreMaskText,
                    snapshot.coreDirectorPrimeCore,
                    snapshot.coreDirectorDriftRepairs
                )
            else -> String.format(
                Locale.US,
                "CORE DIRECTOR | PARTIAL | %d/%dT | failures %d | CPU[%s]",
                snapshot.coreDirectorAppliedThreads,
                snapshot.coreDirectorRegisteredThreads,
                snapshot.coreDirectorFailedThreads,
                coreMaskText
            )
        }
        val baseText = "$metrics\\n$unleashedStatus\\n$coreDirectorStatus\\n$adpfStatus\\n$pacingStatus\\n$frameSkipStatus"
''',
    "val coreDirectorStatus = when",
    "show Core Director in Performance Lab overlay",
)


english_strings = '''

    <!-- Moonwitch Core Director -->
    <string name="mw_core_director_title">Moonwitch Core Director</string>
    <string name="mw_core_director_description">Snapdragon-only maximum-performance mode. Hard-pins CPUCore, GPU, and VulkanWorker to the detected high-performance cluster, continuously verifies the real affinity, and repairs vendor-kernel overrides. No thermal fallback or automatic reduction is used. Original masks are restored when disabled or when the game closes.</string>
    <string name="mw_core_director_menu_description">Hard Snapdragon performance-core affinity, live verification, and automatic drift repair with no thermal fallback</string>
    <string name="mw_core_director_control_header">SNAPDRAGON CORE CONTROL</string>
    <string name="mw_core_director_refresh">Refresh real affinity</string>
    <string name="mw_core_director_off">Disabled. The original scheduler affinity remains unchanged.</string>
    <string name="mw_core_director_armed">Armed for Snapdragon • performance CPUs %1$s • %2$d/%3$d allowed cores • no thermal fallback</string>
    <string name="mw_core_director_waiting_threads">Enabled; waiting for CPUCore, GPU, and VulkanWorker threads to start.</string>
    <string name="mw_core_director_unavailable">Native Core Director telemetry is unavailable.</string>
    <string name="mw_core_director_non_snapdragon">Unsupported device: Core Director deliberately applies affinity only to Qualcomm Snapdragon SoCs.</string>
    <string name="mw_core_director_topology_unavailable">Snapdragon detected, but the allowed CPU topology could not be read safely. No affinity was applied.</string>
    <string name="mw_core_director_active">Active on %1$d/%2$d threads • performance CPUs %3$s • prime CPU %4$d • drift repairs %5$d</string>
    <string name="mw_core_director_partial">Partial: active on %1$d/%2$d threads • %3$d failures • requested CPUs %4$s</string>
    <string name="mw_core_director_rejected">The Snapdragon kernel rejected the affinity mask for every registered critical thread.</string>
'''

portuguese_strings = '''

    <!-- Moonwitch Core Director -->
    <string name="mw_core_director_title">Moonwitch Core Director</string>
    <string name="mw_core_director_description">Modo de desempenho máximo exclusivo para Snapdragon. Fixa CPUCore, GPU e VulkanWorker no cluster de alto desempenho detectado, verifica continuamente a afinidade real e corrige sobrescritas do kernel do fabricante. Não há recuo térmico nem redução automática. As máscaras originais são restauradas ao desativar ou fechar o jogo.</string>
    <string name="mw_core_director_menu_description">Afinidade rígida aos núcleos de desempenho Snapdragon, verificação ao vivo e correção automática sem recuo térmico</string>
    <string name="mw_core_director_control_header">CONTROLE DE NÚCLEOS SNAPDRAGON</string>
    <string name="mw_core_director_refresh">Atualizar afinidade real</string>
    <string name="mw_core_director_off">Desativado. A afinidade original do escalonador permanece inalterada.</string>
    <string name="mw_core_director_armed">Armado para Snapdragon • CPUs de desempenho %1$s • %2$d/%3$d núcleos permitidos • sem recuo térmico</string>
    <string name="mw_core_director_waiting_threads">Ativado; aguardando as threads CPUCore, GPU e VulkanWorker iniciarem.</string>
    <string name="mw_core_director_unavailable">A telemetria nativa do Core Director não está disponível.</string>
    <string name="mw_core_director_non_snapdragon">Dispositivo não suportado: o Core Director aplica afinidade deliberadamente apenas em SoCs Qualcomm Snapdragon.</string>
    <string name="mw_core_director_topology_unavailable">Snapdragon detectado, mas a topologia de CPUs permitidas não pôde ser lida com segurança. Nenhuma afinidade foi aplicada.</string>
    <string name="mw_core_director_active">Ativo em %1$d/%2$d threads • CPUs de desempenho %3$s • CPU prime %4$d • correções de desvio %5$d</string>
    <string name="mw_core_director_partial">Parcial: ativo em %1$d/%2$d threads • %3$d falhas • CPUs solicitadas %4$s</string>
    <string name="mw_core_director_rejected">O kernel Snapdragon recusou a máscara de afinidade em todas as threads críticas registradas.</string>
'''

replace_once(
    strings_xml,
    "</resources>\n",
    english_strings + "</resources>\n",
    'name="mw_core_director_title"',
    "add English strings",
)

replace_once(
    strings_pt_xml,
    "</resources>\n",
    portuguese_strings + "</resources>\n",
    'name="mw_core_director_title"',
    "add Brazilian Portuguese strings",
)

print("Applied Moonwitch Core Director Android controls and telemetry.")
