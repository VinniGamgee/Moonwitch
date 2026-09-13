#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path


TAG = "[moonwitch-unleashed-android]"


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
    '#include "common/logging.h"\n',
    '#include "common/logging.h"\n#include "common/moonwitch_unleashed.h"\n',
    '#include "common/moonwitch_unleashed.h"',
    "include native scheduler controller",
)

replace_once(
    native_config,
    "std::unique_ptr<AndroidConfig> per_game_config;\n\n",
    "std::unique_ptr<AndroidConfig> per_game_config;\n\n"
    "void SyncMoonwitchUnleashedSetting() {\n"
    "    Common::MoonwitchUnleashed::SetEnabled(\n"
    "        Settings::values.moonwitch_unleashed.GetValue());\n"
    "}\n\n",
    "void SyncMoonwitchUnleashedSetting()",
    "add setting-to-runtime synchronization",
)

replace_once(
    native_config,
    "    if (migrated_legacy_branding) {\n"
    "        global_config->AndroidConfig::SaveAllValues();\n"
    "    }\n"
    "}\n\n"
    "void Java_org_yuzu_yuzu_1emu_utils_NativeConfig_unloadGlobalConfig",
    "    if (migrated_legacy_branding) {\n"
    "        global_config->AndroidConfig::SaveAllValues();\n"
    "    }\n"
    "    SyncMoonwitchUnleashedSetting();\n"
    "}\n\n"
    "void Java_org_yuzu_yuzu_1emu_utils_NativeConfig_unloadGlobalConfig",
    "migrated_legacy_branding) {\n        global_config->AndroidConfig::SaveAllValues();\n    }\n    SyncMoonwitchUnleashedSetting();",
    "synchronize global configuration",
)

replace_once(
    native_config,
    "void Java_org_yuzu_yuzu_1emu_utils_NativeConfig_unloadGlobalConfig(JNIEnv* env, jobject obj) {\n"
    "    global_config.reset();\n"
    "}\n",
    "void Java_org_yuzu_yuzu_1emu_utils_NativeConfig_unloadGlobalConfig(JNIEnv* env, jobject obj) {\n"
    "    Common::MoonwitchUnleashed::SetEnabled(false);\n"
    "    global_config.reset();\n"
    "}\n",
    "NativeConfig_unloadGlobalConfig(JNIEnv* env, jobject obj) {\n    Common::MoonwitchUnleashed::SetEnabled(false);",
    "restore clamps when global configuration unloads",
)

replace_once(
    native_config,
    "void Java_org_yuzu_yuzu_1emu_utils_NativeConfig_reloadGlobalConfig(JNIEnv* env, jobject obj) {\n"
    "    global_config->AndroidConfig::ReloadAllValues();\n"
    "}\n",
    "void Java_org_yuzu_yuzu_1emu_utils_NativeConfig_reloadGlobalConfig(JNIEnv* env, jobject obj) {\n"
    "    global_config->AndroidConfig::ReloadAllValues();\n"
    "    SyncMoonwitchUnleashedSetting();\n"
    "}\n",
    "ReloadAllValues();\n    SyncMoonwitchUnleashedSetting();",
    "synchronize config reload",
)

replace_once(
    native_config,
    "    per_game_config =\n"
    "        std::make_unique<AndroidConfig>(config_file_name, Config::ConfigType::PerGameConfig);\n"
    "}\n",
    "    per_game_config =\n"
    "        std::make_unique<AndroidConfig>(config_file_name, Config::ConfigType::PerGameConfig);\n"
    "    SyncMoonwitchUnleashedSetting();\n"
    "}\n",
    "ConfigType::PerGameConfig);\n    SyncMoonwitchUnleashedSetting();",
    "synchronize per-game configuration",
)

replace_once(
    native_config,
    "    setting->SetValue(static_cast<bool>(value));\n"
    "}\n\n"
    "jbyte Java_org_yuzu_yuzu_1emu_utils_NativeConfig_getByte",
    "    setting->SetValue(static_cast<bool>(value));\n"
    "    if (setting == &Settings::values.moonwitch_unleashed) {\n"
    "        Common::MoonwitchUnleashed::SetEnabled(static_cast<bool>(value));\n"
    "    }\n"
    "}\n\n"
    "jbyte Java_org_yuzu_yuzu_1emu_utils_NativeConfig_getByte",
    "setting == &Settings::values.moonwitch_unleashed",
    "apply toggle live",
)


replace_once(
    native_lab,
    "#include <chrono>\n",
    "#include <algorithm>\n#include <chrono>\n",
    "#include <algorithm>",
    "include telemetry copy helper",
)

replace_once(
    native_lab,
    '#include "common/adpf.h"\n',
    '#include "common/adpf.h"\n#include "common/moonwitch_unleashed.h"\n',
    '#include "common/moonwitch_unleashed.h"',
    "include Unleashed telemetry",
)

replace_once(
    native_lab,
    "    constexpr jsize StatCount = 33;\n"
    "    jdoubleArray j_stats = env->NewDoubleArray(StatCount);\n"
    "    if (j_stats == nullptr || !EmulationSession::GetInstance().IsRunning()) {\n"
    "        return j_stats;\n"
    "    }\n\n",
    "    constexpr jsize StatCount = 50;\n"
    "    constexpr std::size_t LiveStatCount = 33;\n"
    "    jdoubleArray j_stats = env->NewDoubleArray(StatCount);\n"
    "    if (j_stats == nullptr) {\n"
    "        return j_stats;\n"
    "    }\n\n"
    "    jdouble values[StatCount]{};\n"
    "    const auto unleashed = Common::MoonwitchUnleashed::GetTelemetry();\n"
    "    values[33] = unleashed.enabled ? 1.0 : 0.0;\n"
    "    values[34] = unleashed.kernel_supported ? 1.0 : 0.0;\n"
    "    values[35] = unleashed.boost_active ? 1.0 : 0.0;\n"
    "    values[36] = static_cast<double>(unleashed.registered_threads);\n"
    "    values[37] = static_cast<double>(unleashed.applied_threads);\n"
    "    values[38] = static_cast<double>(unleashed.failed_threads);\n"
    "    values[39] = static_cast<double>(unleashed.requested_util_min_percent);\n"
    "    values[40] = static_cast<double>(unleashed.deadline_misses);\n"
    "    values[41] = static_cast<double>(unleashed.boost_events);\n"
    "    values[42] = unleashed.baseline.median_ms;\n"
    "    values[43] = unleashed.baseline.p95_ms;\n"
    "    values[44] = unleashed.baseline.p99_ms;\n"
    "    values[45] = static_cast<double>(unleashed.baseline.sample_count);\n"
    "    values[46] = unleashed.active.median_ms;\n"
    "    values[47] = unleashed.active.p95_ms;\n"
    "    values[48] = unleashed.active.p99_ms;\n"
    "    values[49] = static_cast<double>(unleashed.active.sample_count);\n\n"
    "    if (!EmulationSession::GetInstance().IsRunning()) {\n"
    "        env->SetDoubleArrayRegion(j_stats, 0, StatCount, values);\n"
    "        return j_stats;\n"
    "    }\n\n",
    "constexpr jsize StatCount = 50;",
    "extend native telemetry payload",
)

replace_once(
    native_lab,
    "    const double values[StatCount] = {\n",
    "    const double live_values[LiveStatCount] = {\n",
    "const double live_values[LiveStatCount]",
    "separate live session metrics",
)

replace_once(
    native_lab,
    "        static_cast<double>(frame_skip.presentation_capacity),\n"
    "    };\n"
    "    env->SetDoubleArrayRegion(j_stats, 0, StatCount, values);\n",
    "        static_cast<double>(frame_skip.presentation_capacity),\n"
    "    };\n"
    "    std::copy_n(live_values, LiveStatCount, values);\n"
    "    env->SetDoubleArrayRegion(j_stats, 0, StatCount, values);\n",
    "std::copy_n(live_values, LiveStatCount, values);",
    "combine performance and Unleashed telemetry",
)


replace_once(
    boolean_setting,
    '    SMART_ADAPTIVE_FRAME_SKIP("smart_adaptive_frame_skip"),\n',
    '    SMART_ADAPTIVE_FRAME_SKIP("smart_adaptive_frame_skip"),\n'
    '    MOONWITCH_UNLEASHED("moonwitch_unleashed"),\n',
    "MOONWITCH_UNLEASHED",
    "expose runtime setting to Kotlin",
)

replace_once(
    settings_model,
    "        SECTION_MOONWITCH_PERFORMANCE(R.string.mw_performance_center),\n",
    "        SECTION_MOONWITCH_PERFORMANCE(R.string.mw_performance_center),\n"
    "        SECTION_MOONWITCH_UNLEASHED(R.string.mw_unleashed_title),\n",
    "SECTION_MOONWITCH_UNLEASHED",
    "register dedicated settings page",
)

replace_once(
    settings_item,
    """            put(
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
                    BooleanSetting.SHOW_PERFORMANCE_OVERLAY,
""",
    "BooleanSetting.MOONWITCH_UNLEASHED,",
    "register Unleashed switch item",
)

replace_once(
    presenter,
    "            MenuTag.SECTION_MOONWITCH_PERFORMANCE -> addMoonwitchPerformanceSettings(sl)\n",
    "            MenuTag.SECTION_MOONWITCH_PERFORMANCE -> addMoonwitchPerformanceSettings(sl)\n"
    "            MenuTag.SECTION_MOONWITCH_UNLEASHED -> addMoonwitchUnleashedSettings(sl)\n",
    "SECTION_MOONWITCH_UNLEASHED ->",
    "route dedicated settings page",
)

replace_once(
    presenter,
    "    private fun addMoonwitchPerformanceSettings(sl: ArrayList<SettingsItem>) {\n"
    "        sl.apply {\n"
    "            add(BooleanSetting.RENDERER_USE_SPEED_LIMIT.key)\n",
    "    private fun addMoonwitchPerformanceSettings(sl: ArrayList<SettingsItem>) {\n"
    "        sl.apply {\n"
    "            add(\n"
    "                SubmenuSetting(\n"
    "                    titleId = R.string.mw_unleashed_title,\n"
    "                    descriptionId = R.string.mw_unleashed_menu_description,\n"
    "                    iconId = R.drawable.ic_mw_gauge,\n"
    "                    menuKey = MenuTag.SECTION_MOONWITCH_UNLEASHED\n"
    "                )\n"
    "            )\n"
    "            add(BooleanSetting.RENDERER_USE_SPEED_LIMIT.key)\n",
    "menuKey = MenuTag.SECTION_MOONWITCH_UNLEASHED",
    "add Unleashed entry to Performance Center",
)

replace_once(
    presenter,
    "    private fun addDriversComponentsSettings(sl: ArrayList<SettingsItem>) {\n",
    '''    private fun addMoonwitchUnleashedSettings(sl: ArrayList<SettingsItem>) {
        val snapshot = runCatching { PerformanceLabNative.snapshot() }.getOrNull()
        val status = when {
            snapshot == null -> context.getString(R.string.mw_unleashed_unavailable)
            !snapshot.unleashedEnabled -> context.getString(R.string.mw_unleashed_off)
            !NativeLibrary.isRunning() -> context.getString(R.string.mw_unleashed_armed)
            snapshot.unleashedRegisteredThreads == 0 ->
                context.getString(R.string.mw_unleashed_waiting_threads)
            !snapshot.unleashedKernelSupported || snapshot.unleashedAppliedThreads == 0 ->
                context.getString(R.string.mw_unleashed_unsupported)
            snapshot.unleashedAppliedThreads == snapshot.unleashedRegisteredThreads ->
                context.getString(
                    R.string.mw_unleashed_active,
                    snapshot.unleashedAppliedThreads,
                    snapshot.unleashedRegisteredThreads,
                    snapshot.unleashedUtilMinPercent,
                    if (snapshot.unleashedBoostActive) {
                        context.getString(R.string.mw_unleashed_burst)
                    } else {
                        context.getString(R.string.mw_unleashed_base)
                    }
                )
            else -> context.getString(
                R.string.mw_unleashed_partial,
                snapshot.unleashedAppliedThreads,
                snapshot.unleashedRegisteredThreads,
                snapshot.unleashedFailedThreads
            )
        }

        val comparison = when {
            snapshot == null || snapshot.unleashedBaselineSamples == 0 ->
                context.getString(R.string.mw_unleashed_need_baseline)
            snapshot.unleashedActiveSamples < 30 -> context.getString(
                R.string.mw_unleashed_collecting,
                snapshot.unleashedActiveSamples
            )
            else -> context.getString(
                R.string.mw_unleashed_comparison,
                snapshot.unleashedBaselineMedianMs,
                snapshot.unleashedActiveMedianMs,
                snapshot.unleashedBaselineP95Ms,
                snapshot.unleashedActiveP95Ms,
                snapshot.unleashedBaselineP99Ms,
                snapshot.unleashedActiveP99Ms,
                snapshot.unleashedBaselineSamples,
                snapshot.unleashedActiveSamples
            )
        }

        sl.apply {
            add(HeaderSetting(R.string.mw_unleashed_control_header))
            add(BooleanSetting.MOONWITCH_UNLEASHED.key)
            add(
                RunnableSetting(
                    titleId = R.string.mw_unleashed_refresh,
                    descriptionString = status,
                    isRunnable = true,
                    iconId = R.drawable.ic_refresh
                ) { loadSettingsList(true) }
            )
            add(HeaderSetting(R.string.mw_unleashed_comparison_header))
            add(
                RunnableSetting(
                    titleId = R.string.mw_unleashed_before_after,
                    descriptionString = comparison,
                    isRunnable = true,
                    iconId = R.drawable.ic_mw_gauge
                ) { loadSettingsList(true) }
            )
        }
    }

    private fun addDriversComponentsSettings(sl: ArrayList<SettingsItem>) {
''',
    "private fun addMoonwitchUnleashedSettings",
    "implement live status and before/after page",
)

replace_once(
    emulation_fragment,
    "            if (shouldUseCustom) {\n"
    "                quickSettings.addPerGameConfigStatusIndicator(container)\n"
    "            }\n\n"
    "            lateinit var slowSpeed: MaterialSwitch\n",
    "            if (shouldUseCustom) {\n"
    "                quickSettings.addPerGameConfigStatusIndicator(container)\n"
    "            }\n\n"
    "            quickSettings.addBooleanSetting(\n"
    "                R.string.mw_unleashed_title,\n"
    "                container,\n"
    "                BooleanSetting.MOONWITCH_UNLEASHED\n"
    "            )\n"
    "            quickSettings.addDivider(container)\n\n"
    "            lateinit var slowSpeed: MaterialSwitch\n",
    "BooleanSetting.MOONWITCH_UNLEASHED",
    "add live Quick Settings toggle",
)


replace_once(
    performance_native,
    "        val frameSkipPresentationBacklog: Long,\n"
    "        val frameSkipPresentationCapacity: Long\n",
    "        val frameSkipPresentationBacklog: Long,\n"
    "        val frameSkipPresentationCapacity: Long,\n"
    "        val unleashedEnabled: Boolean,\n"
    "        val unleashedKernelSupported: Boolean,\n"
    "        val unleashedBoostActive: Boolean,\n"
    "        val unleashedRegisteredThreads: Int,\n"
    "        val unleashedAppliedThreads: Int,\n"
    "        val unleashedFailedThreads: Int,\n"
    "        val unleashedUtilMinPercent: Int,\n"
    "        val unleashedDeadlineMisses: Long,\n"
    "        val unleashedBoostEvents: Long,\n"
    "        val unleashedBaselineMedianMs: Double,\n"
    "        val unleashedBaselineP95Ms: Double,\n"
    "        val unleashedBaselineP99Ms: Double,\n"
    "        val unleashedBaselineSamples: Int,\n"
    "        val unleashedActiveMedianMs: Double,\n"
    "        val unleashedActiveP95Ms: Double,\n"
    "        val unleashedActiveP99Ms: Double,\n"
    "        val unleashedActiveSamples: Int\n",
    "val unleashedEnabled: Boolean",
    "extend Kotlin telemetry model",
)

replace_once(
    performance_native,
    "        if (values.size < 33) {\n",
    "        if (values.size < 50) {\n",
    "values.size < 50",
    "require complete telemetry payload",
)

replace_once(
    performance_native,
    "                false, false, false, 0L, 0L, 0, 0, 0.0, 0.0, 0L, 0L, 0L\n"
    "            )\n",
    "                false, false, false, 0L, 0L, 0, 0, 0.0, 0.0, 0L, 0L, 0L,\n"
    "                false, false, false, 0, 0, 0, 0, 0L, 0L,\n"
    "                0.0, 0.0, 0.0, 0, 0.0, 0.0, 0.0, 0\n"
    "            )\n",
    "false, false, false, 0, 0, 0, 0, 0L, 0L,",
    "supply safe telemetry defaults",
)

replace_once(
    performance_native,
    "            frameSkipPresentationBacklog = values[31].toLong(),\n"
    "            frameSkipPresentationCapacity = values[32].toLong()\n",
    "            frameSkipPresentationBacklog = values[31].toLong(),\n"
    "            frameSkipPresentationCapacity = values[32].toLong(),\n"
    "            unleashedEnabled = values[33] != 0.0,\n"
    "            unleashedKernelSupported = values[34] != 0.0,\n"
    "            unleashedBoostActive = values[35] != 0.0,\n"
    "            unleashedRegisteredThreads = values[36].toInt(),\n"
    "            unleashedAppliedThreads = values[37].toInt(),\n"
    "            unleashedFailedThreads = values[38].toInt(),\n"
    "            unleashedUtilMinPercent = values[39].toInt(),\n"
    "            unleashedDeadlineMisses = values[40].toLong(),\n"
    "            unleashedBoostEvents = values[41].toLong(),\n"
    "            unleashedBaselineMedianMs = values[42],\n"
    "            unleashedBaselineP95Ms = values[43],\n"
    "            unleashedBaselineP99Ms = values[44],\n"
    "            unleashedBaselineSamples = values[45].toInt(),\n"
    "            unleashedActiveMedianMs = values[46],\n"
    "            unleashedActiveP95Ms = values[47],\n"
    "            unleashedActiveP99Ms = values[48],\n"
    "            unleashedActiveSamples = values[49].toInt()\n",
    "unleashedActiveSamples = values[49].toInt()",
    "decode native telemetry",
)

replace_once(
    performance_overlay,
    "        val baseText = \"$metrics\\n$adpfStatus\\n$pacingStatus\\n$frameSkipStatus\"\n",
    '''        val unleashedStatus = when {
            !snapshot.unleashedEnabled -> "UNLEASHED | OFF"
            !snapshot.unleashedKernelSupported -> "UNLEASHED | NOT SUPPORTED BY KERNEL"
            snapshot.unleashedRegisteredThreads == 0 -> "UNLEASHED | waiting for critical threads"
            snapshot.unleashedAppliedThreads == snapshot.unleashedRegisteredThreads -> String.format(
                Locale.US,
                "UNLEASHED | %s | %d/%dT | uclamp.min %d%% | miss %d | burst %d | P95 %.1f>%.1f",
                if (snapshot.unleashedBoostActive) "BURST" else "BASE",
                snapshot.unleashedAppliedThreads,
                snapshot.unleashedRegisteredThreads,
                snapshot.unleashedUtilMinPercent,
                snapshot.unleashedDeadlineMisses,
                snapshot.unleashedBoostEvents,
                snapshot.unleashedBaselineP95Ms,
                snapshot.unleashedActiveP95Ms
            )
            else -> String.format(
                Locale.US,
                "UNLEASHED | PARTIAL | %d/%dT | failures %d",
                snapshot.unleashedAppliedThreads,
                snapshot.unleashedRegisteredThreads,
                snapshot.unleashedFailedThreads
            )
        }
        val baseText = "$metrics\\n$unleashedStatus\\n$adpfStatus\\n$pacingStatus\\n$frameSkipStatus"
''',
    "UNLEASHED | PARTIAL",
    "show verified state in Performance Lab",
)


english_strings = '''

    <!-- Moonwitch Unleashed -->
    <string name="mw_unleashed_title">Moonwitch Unleashed</string>
    <string name="mw_unleashed_description">Aggressive scheduler mode for CPUCore, GPU, and VulkanWorker. It requests a verified 75%% uclamp.min floor and temporarily raises it to 90%% after repeated deadline misses. Original values are restored when disabled or when the game closes.</string>
    <string name="mw_unleashed_menu_description">Live 75/90%% scheduler floor, verified thread state, and objective before/after frametime comparison</string>
    <string name="mw_unleashed_control_header">LIVE SCHEDULER CONTROL</string>
    <string name="mw_unleashed_comparison_header">BEFORE / AFTER</string>
    <string name="mw_unleashed_refresh">Refresh real state</string>
    <string name="mw_unleashed_before_after">Frametime comparison</string>
    <string name="mw_unleashed_off">Disabled. No scheduler clamp is being requested.</string>
    <string name="mw_unleashed_armed">Enabled. The scheduler floor will be applied when a game starts.</string>
    <string name="mw_unleashed_waiting_threads">Enabled; waiting for the critical emulation threads to start.</string>
    <string name="mw_unleashed_unavailable">Native Unleashed telemetry is unavailable.</string>
    <string name="mw_unleashed_unsupported">Not supported: the kernel rejected uclamp for every registered critical thread. The switch is not being reported as active.</string>
    <string name="mw_unleashed_active">Active on %1$d/%2$d threads • uclamp.min %3$d%% • %4$s</string>
    <string name="mw_unleashed_partial">Partial: active on %1$d/%2$d threads • %3$d failures</string>
    <string name="mw_unleashed_base">75%% base floor</string>
    <string name="mw_unleashed_burst">90%% adaptive burst</string>
    <string name="mw_unleashed_need_baseline">Run the game with Unleashed off first, then enable it to capture a comparable baseline automatically.</string>
    <string name="mw_unleashed_collecting">Collecting Unleashed samples: %1$d/30 minimum.</string>
    <string name="mw_unleashed_comparison">Median %1$.1f → %2$.1f ms • P95 %3$.1f → %4$.1f ms • P99 %5$.1f → %6$.1f ms • samples %7$d/%8$d</string>
'''

portuguese_strings = '''

    <!-- Moonwitch Unleashed -->
    <string name="mw_unleashed_title">Moonwitch Unleashed</string>
    <string name="mw_unleashed_description">Modo agressivo do escalonador para CPUCore, GPU e VulkanWorker. Solicita um piso uclamp.min verificado de 75%% e sobe temporariamente para 90%% após perdas repetidas do prazo. Os valores originais são restaurados ao desativar ou fechar o jogo.</string>
    <string name="mw_unleashed_menu_description">Piso de escalonamento 75/90%% ao vivo, estado real das threads e comparação objetiva de frametime</string>
    <string name="mw_unleashed_control_header">CONTROLE DO ESCALONADOR AO VIVO</string>
    <string name="mw_unleashed_comparison_header">ANTES / DEPOIS</string>
    <string name="mw_unleashed_refresh">Atualizar estado real</string>
    <string name="mw_unleashed_before_after">Comparação de frametime</string>
    <string name="mw_unleashed_off">Desativado. Nenhum piso do escalonador está sendo solicitado.</string>
    <string name="mw_unleashed_armed">Ativado. O piso do escalonador será aplicado quando um jogo iniciar.</string>
    <string name="mw_unleashed_waiting_threads">Ativado; aguardando as threads críticas da emulação iniciarem.</string>
    <string name="mw_unleashed_unavailable">A telemetria nativa do Unleashed não está disponível.</string>
    <string name="mw_unleashed_unsupported">Não suportado: o kernel recusou uclamp em todas as threads críticas registradas. A opção não será exibida como ativa.</string>
    <string name="mw_unleashed_active">Ativo em %1$d/%2$d threads • uclamp.min %3$d%% • %4$s</string>
    <string name="mw_unleashed_partial">Parcial: ativo em %1$d/%2$d threads • %3$d falhas</string>
    <string name="mw_unleashed_base">piso-base de 75%%</string>
    <string name="mw_unleashed_burst">rajada adaptativa de 90%%</string>
    <string name="mw_unleashed_need_baseline">Rode o jogo primeiro com o Unleashed desligado e depois ative para capturar uma base comparável automaticamente.</string>
    <string name="mw_unleashed_collecting">Coletando amostras com Unleashed: mínimo %1$d/30.</string>
    <string name="mw_unleashed_comparison">Mediana %1$.1f → %2$.1f ms • P95 %3$.1f → %4$.1f ms • P99 %5$.1f → %6$.1f ms • amostras %7$d/%8$d</string>
'''

replace_once(
    strings_xml,
    "</resources>\n",
    english_strings + "</resources>\n",
    'name="mw_unleashed_title"',
    "add English UI strings",
)

replace_once(
    strings_pt_xml,
    "</resources>\n",
    portuguese_strings + "</resources>\n",
    'name="mw_unleashed_title"',
    "add Brazilian Portuguese UI strings",
)

print("Applied Moonwitch Unleashed Android controls and verified telemetry UI.")
