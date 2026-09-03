from pathlib import Path

TARGET = Path('src/android/app/src/main')

def once(text: str, old: str, new: str, label: str) -> str:
    n = text.count(old)
    if n != 1:
        raise SystemExit(f'{label}: expected exactly one match, found {n}')
    return text.replace(old, new, 1)

p = TARGET / 'java/org/yuzu/yuzu_emu/features/settings/model/Settings.kt'
s = p.read_text()
s = once(s, '        SECTION_MOONWITCH_PERFORMANCE(R.string.mw_performance_center),\n', '        SECTION_MOONWITCH_PERFORMANCE(R.string.mw_performance_center),\n        SECTION_DRIVERS_COMPONENTS(R.string.mw_drivers_components),\n', 'menu tag')
p.write_text(s)

p = TARGET / 'java/org/yuzu/yuzu_emu/features/settings/ui/SettingsFragmentPresenter.kt'
s = p.read_text()
s = once(s, '            MenuTag.SECTION_MOONWITCH_PERFORMANCE -> addMoonwitchPerformanceSettings(sl)\n', '            MenuTag.SECTION_MOONWITCH_PERFORMANCE -> addMoonwitchPerformanceSettings(sl)\n            MenuTag.SECTION_DRIVERS_COMPONENTS -> addDriversComponentsSettings(sl)\n', 'menu dispatch')
start = s.index('            add(HeaderSetting(R.string.mw_performance_management))')
end = s.index('        }\n    }\n\n    private fun createSubscreenIntent', start)
s = s[:start] + s[end:]
drivers_fn = '''    private fun addDriversComponentsSettings(sl: ArrayList<SettingsItem>) {\n        sl.apply {\n            add(LaunchableSetting(titleId = R.string.mw_gpu_drivers, descriptionId = R.string.mw_gpu_drivers_desc) { launchContext ->\n                createSubscreenIntent(launchContext, SettingsSubscreen.DRIVER_MANAGER)\n            })\n            add(LaunchableSetting(titleId = R.string.mw_freedreno, descriptionId = R.string.mw_freedreno_desc) { launchContext ->\n                createSubscreenIntent(launchContext, SettingsSubscreen.FREEDRENO_SETTINGS)\n            })\n            add(LaunchableSetting(titleId = R.string.mw_lossless_scaling, descriptionId = R.string.mw_lossless_scaling_desc) { launchContext ->\n                createSubscreenIntent(launchContext, SettingsSubscreen.LOSSLESS_MANAGER)\n            })\n        }\n    }\n\n'''
s = once(s, '    private fun createSubscreenIntent(\n', drivers_fn + '    private fun createSubscreenIntent(\n', 'drivers function')
perf_entry = '''            add(\n                SubmenuSetting(\n                    titleId = R.string.mw_performance_center,\n                    descriptionId = R.string.mw_performance_center_desc,\n                    iconId = R.drawable.ic_mw_gauge,\n                    menuKey = MenuTag.SECTION_MOONWITCH_PERFORMANCE\n                )\n            )\n'''
per_game = perf_entry + '''            if (NativeConfig.isPerGameConfigLoaded()) {\n                add(SubmenuSetting(\n                    titleId = R.string.mw_drivers_components,\n                    descriptionId = R.string.mw_drivers_components_desc,\n                    iconId = R.drawable.ic_build,\n                    menuKey = MenuTag.SECTION_DRIVERS_COMPONENTS\n                ))\n            }\n'''
s = once(s, perf_entry, per_game, 'per-game category')
p.write_text(s)

p = TARGET / 'java/org/yuzu/yuzu_emu/fragments/HomeSettingsFragment.kt'
s = p.read_text()
for old in ['import org.yuzu.yuzu_emu.model.DriverViewModel\n', 'import org.yuzu.yuzu_emu.utils.GpuDriverHelper\n', 'import org.yuzu.yuzu_emu.utils.LosslessScalingHelper\n', '    private val driverViewModel: DriverViewModel by activityViewModels()\n']:
    s = s.replace(old, '')
start = s.index('            add(\n                HomeSetting(\n                    R.string.gpu_driver_manager,')
end = s.index('            add(\n                HomeSetting(\n                    R.string.multiplayer,', start)
card = '''            add(\n                HomeSetting(\n                    R.string.mw_drivers_components,\n                    R.string.mw_drivers_components_desc,\n                    R.drawable.ic_build,\n                    {\n                        val action = HomeNavigationDirections.actionGlobalSettingsActivity(\n                            null,\n                            Settings.MenuTag.SECTION_DRIVERS_COMPONENTS\n                        )\n                        binding.root.findNavController().navigate(action)\n                    }\n                )\n            )\n'''
s = s[:start] + card + s[end:]
s = s.replace('''    override fun onResume() {\n        super.onResume()\n        driverViewModel.updateDriverNameForGame(null)\n        LosslessScalingHelper.refreshStatus()\n    }\n\n''', '')
p.write_text(s)

p = TARGET / 'res/values/strings.xml'
s = p.read_text()
marker = '    <string name="moonwitch_system_menu">System menu</string>\n'
s = once(s, marker, marker + '    <string name="mw_drivers_components">Drivers and Components</string>\n    <string name="mw_drivers_components_desc">GPU drivers, Freedreno/Turnip and Lossless Scaling</string>\n', 'default labels')
p.write_text(s)

p = TARGET / 'res/values-pt-rBR/strings.xml'
s = p.read_text()
marker = '<resources xmlns:tools="http://schemas.android.com/tools" tools:ignore="MissingTranslation">\n'
s = once(s, marker, marker + '    <string name="mw_drivers_components">Drivers e componentes</string>\n    <string name="mw_drivers_components_desc">Drivers de GPU, Freedreno/Turnip e Lossless Scaling</string>\n\n', 'pt-BR labels')
p.write_text(s)

presenter = (TARGET / 'java/org/yuzu/yuzu_emu/features/settings/ui/SettingsFragmentPresenter.kt').read_text()
home = (TARGET / 'java/org/yuzu/yuzu_emu/fragments/HomeSettingsFragment.kt').read_text()
for token in ['SettingsSubscreen.DRIVER_MANAGER', 'SettingsSubscreen.FREEDRENO_SETTINGS', 'SettingsSubscreen.LOSSLESS_MANAGER']:
    if presenter.count(token) != 1:
        raise SystemExit(f'{token}: canonical count {presenter.count(token)}')
    if token in home:
        raise SystemExit(f'{token}: direct Home shortcut remains')

print('Drivers and Components organization finalized successfully.')
