// SPDX-FileCopyrightText: Copyright 2026 Eden Emulator Project
// SPDX-License-Identifier: GPL-3.0-or-later

package org.yuzu.yuzu_emu.fragments

import android.content.res.Configuration
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.updatePadding
import androidx.core.widget.doOnTextChanged
import androidx.fragment.app.Fragment
import androidx.fragment.app.activityViewModels
import androidx.navigation.findNavController
import androidx.recyclerview.widget.GridLayoutManager
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import com.google.android.material.materialswitch.MaterialSwitch
import com.google.android.material.slider.Slider
import org.yuzu.yuzu_emu.HomeNavigationDirections
import org.yuzu.yuzu_emu.NativeLibrary
import org.yuzu.yuzu_emu.R
import org.yuzu.yuzu_emu.adapters.HomeSettingAdapter
import org.yuzu.yuzu_emu.databinding.FragmentHomeSettingsBinding
import org.yuzu.yuzu_emu.features.fetcher.SpacingItemDecoration
import org.yuzu.yuzu_emu.features.settings.model.BooleanSetting
import org.yuzu.yuzu_emu.features.settings.model.IntSetting
import org.yuzu.yuzu_emu.features.settings.model.MoonwitchCasSettings
import org.yuzu.yuzu_emu.features.settings.model.Settings
import org.yuzu.yuzu_emu.features.settings.ui.SettingsSubscreen
import org.yuzu.yuzu_emu.model.HomeSetting
import org.yuzu.yuzu_emu.model.HomeViewModel
import org.yuzu.yuzu_emu.model.DriverViewModel
import org.yuzu.yuzu_emu.utils.DeviceProfileManager
import org.yuzu.yuzu_emu.utils.NativeConfig
import org.yuzu.yuzu_emu.utils.PerformanceLabNative
import org.yuzu.yuzu_emu.utils.collect

class HomeSettingsFragment : Fragment() {
    private var _binding: FragmentHomeSettingsBinding? = null
    private val binding get() = _binding!!
    private val homeViewModel: HomeViewModel by activityViewModels()
    private val driverViewModel: DriverViewModel by activityViewModels()
    private lateinit var options: List<HomeSetting>
    private lateinit var performanceOptions: List<HomeSetting>

    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?): View {
        _binding = FragmentHomeSettingsBinding.inflate(inflater)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        homeViewModel.setStatusBarShadeVisibility(false)

        options = buildCategories()
        performanceOptions = buildPerformanceOptions()
        binding.homeSettingsList.apply {
            layoutManager = GridLayoutManager(requireContext(), 2)
            isNestedScrollingEnabled = false
            val spacing = resources.getDimensionPixelSize(R.dimen.spacing_small)
            addItemDecoration(SpacingItemDecoration(spacing))
        }
        binding.performanceSettingsList.apply {
            layoutManager = GridLayoutManager(requireContext(), 1)
            isNestedScrollingEnabled = false
            val spacing = resources.getDimensionPixelSize(R.dimen.spacing_small)
            addItemDecoration(SpacingItemDecoration(spacing))
        }
        renderOptions(options)
        renderPerformanceOptions(performanceOptions)

        binding.settingsSearchText.doOnTextChanged { text, _, _, _ ->
            val query = text?.toString()?.trim().orEmpty()
            val filtered = if (query.isEmpty()) options else options.filter {
                getString(it.titleId).contains(query, ignoreCase = true) ||
                    getString(it.descriptionId).contains(query, ignoreCase = true)
            }
            val filteredPerformance = if (query.isEmpty()) performanceOptions else performanceOptions.filter {
                getString(it.titleId).contains(query, ignoreCase = true) ||
                    getString(it.descriptionId).contains(query, ignoreCase = true)
            }
            renderOptions(filtered)
            renderPerformanceOptions(filteredPerformance)
        }

        binding.settingsShortcutCard.setOnClickListener { openSettings(Settings.MenuTag.SECTION_ROOT) }
        binding.helpCard.setOnClickListener {
            openSubscreen(SettingsSubscreen.ABOUT)
        }

        setupPerformanceDashboard(view)

        setInsets()
    }

    private fun buildCategories(): List<HomeSetting> = listOf(
        HomeSetting(
            R.string.mw_cat_general,
            R.string.mw_cat_general_desc,
            R.drawable.ic_settings,
            onClick = { openSettings(Settings.MenuTag.SECTION_GENERAL) }
        ),
        HomeSetting(
            R.string.mw_cat_graphics,
            R.string.mw_cat_graphics_desc,
            R.drawable.ic_graphics,
            onClick = { openSettings(Settings.MenuTag.SECTION_RENDERER) }
        ),
        HomeSetting(
            R.string.mw_cat_audio,
            R.string.mw_cat_audio_desc,
            R.drawable.ic_mw_audio,
            onClick = { openSettings(Settings.MenuTag.SECTION_AUDIO) }
        ),
        HomeSetting(
            R.string.mw_cat_controls,
            R.string.mw_cat_controls_desc,
            R.drawable.ic_controller,
            onClick = { openSettings(Settings.MenuTag.SECTION_INPUT) }
        ),
        HomeSetting(
            R.string.mw_cat_system,
            R.string.mw_cat_system_desc,
            R.drawable.ic_mw_system,
            onClick = { openSettings(Settings.MenuTag.SECTION_SYSTEM) }
        ),
        HomeSetting(
            R.string.mw_cat_interface,
            R.string.mw_cat_interface_desc,
            R.drawable.ic_palette,
            onClick = { openSettings(Settings.MenuTag.SECTION_APP_SETTINGS) }
        ),
        HomeSetting(
            R.string.mw_cat_library,
            R.string.mw_cat_library_desc,
            R.drawable.ic_mw_library,
            onClick = {
                val action = HomeNavigationDirections.actionGlobalSettingsSubscreenActivity(SettingsSubscreen.GAME_FOLDERS, null)
                binding.root.findNavController().navigate(action)
            }
        ),
        HomeSetting(
            R.string.mw_cat_lab,
            R.string.mw_cat_lab_desc,
            R.drawable.ic_mw_gauge,
            onClick = { openSettings(Settings.MenuTag.SECTION_MOONWITCH_PERFORMANCE) }
        )
    )

    private fun buildPerformanceOptions(): List<HomeSetting> = listOf(
        HomeSetting(
            R.string.mw_safs,
            R.string.mw_safs_desc,
            R.drawable.ic_mw_gauge,
            onClick = { openSettings(Settings.MenuTag.SECTION_SAFS) }
        ),
        HomeSetting(
            R.string.mw_frame_pacing,
            R.string.mw_frame_pacing_desc,
            R.drawable.ic_frames,
            onClick = { openSettings(Settings.MenuTag.SECTION_FRAME_PACING) }
        ),
        HomeSetting(
            R.string.mw_frame_generation,
            R.string.mw_frame_generation_desc,
            R.drawable.ic_graphics,
            onClick = { openSettings(Settings.MenuTag.SECTION_FRAME_GEN) }
        ),
        HomeSetting(
            R.string.mw_adpf_diagnostics,
            R.string.mw_adpf_diagnostics_desc,
            R.drawable.ic_info_outline,
            onClick = { openSettings(Settings.MenuTag.SECTION_ADPF) }
        ),
        HomeSetting(
            R.string.mw_gpu_drivers,
            R.string.mw_gpu_drivers_desc,
            R.drawable.ic_mw_system,
            onClick = { openSubscreen(SettingsSubscreen.DRIVER_MANAGER) }
        ),
        HomeSetting(
            R.string.mw_freedreno,
            R.string.mw_freedreno_desc,
            R.drawable.ic_code,
            onClick = { openSubscreen(SettingsSubscreen.FREEDRENO_SETTINGS) }
        ),
        HomeSetting(
            R.string.mw_performance_monitor,
            R.string.mw_performance_monitor_desc,
            R.drawable.ic_mw_gauge,
            onClick = { openSettings(Settings.MenuTag.SECTION_PERFORMANCE_STATS) }
        ),
        HomeSetting(
            R.string.mw_lossless_scaling,
            R.string.mw_lossless_scaling_desc,
            R.drawable.ic_install,
            onClick = { openSubscreen(SettingsSubscreen.LOSSLESS_MANAGER) }
        )
    )

    private fun renderOptions(items: List<HomeSetting>) {
        binding.homeSettingsList.adapter = HomeSettingAdapter(
            requireActivity() as AppCompatActivity,
            viewLifecycleOwner,
            items
        )
    }

    private fun renderPerformanceOptions(items: List<HomeSetting>) {
        binding.performanceSettingsList.adapter = HomeSettingAdapter(
            requireActivity() as AppCompatActivity,
            viewLifecycleOwner,
            items
        )
    }

    private fun setupPerformanceDashboard(view: View) {
        if (resources.configuration.orientation != Configuration.ORIENTATION_LANDSCAPE) return

        view.findViewById<TextView>(R.id.device_badge_text)?.text =
            DeviceProfileManager.currentDeviceName()

        view.findViewById<View>(R.id.nav_performance_card)?.setOnClickListener {
            openSettings(Settings.MenuTag.SECTION_MOONWITCH_PERFORMANCE)
        }
        view.findViewById<View>(R.id.nav_games_card)?.setOnClickListener {
            binding.root.findNavController().popBackStack()
        }
        view.findViewById<View>(R.id.nav_system_card)?.setOnClickListener {
            openSettings(Settings.MenuTag.SECTION_SYSTEM)
        }
        view.findViewById<View>(R.id.nav_updates_card)?.setOnClickListener {
            openSettings(Settings.MenuTag.SECTION_APP_SETTINGS)
        }

        val dockSwitch = view.findViewById<MaterialSwitch>(R.id.quick_dock_switch)
        val safsSwitch = view.findViewById<MaterialSwitch>(R.id.quick_safs_switch)
        val casSlider = view.findViewById<Slider>(R.id.quick_cas_slider)

        dockSwitch?.isChecked = BooleanSetting.USE_DOCKED_MODE.getBoolean(false)
        safsSwitch?.isChecked = BooleanSetting.SMART_ADAPTIVE_FRAME_SKIP.getBoolean(false)
        casSlider?.value = MoonwitchCasSettings.sharpness.getInt(false).toFloat()
        updateQuickSettingLabels(view)

        dockSwitch?.setOnCheckedChangeListener { _, isChecked ->
            BooleanSetting.USE_DOCKED_MODE.setBoolean(isChecked)
            persistDashboardSettings()
        }
        safsSwitch?.setOnCheckedChangeListener { _, isChecked ->
            BooleanSetting.SMART_ADAPTIVE_FRAME_SKIP.setBoolean(isChecked)
            persistDashboardSettings()
        }
        casSlider?.addOnChangeListener { _, value, fromUser ->
            if (fromUser) {
                MoonwitchCasSettings.sharpness.setInt(value.toInt())
                view.findViewById<TextView>(R.id.quick_cas_value)?.text =
                    getString(R.string.mw_percent_value, value.toInt())
                persistDashboardSettings()
            }
        }

        view.findViewById<View>(R.id.quick_dock)?.setOnClickListener { dockSwitch?.toggle() }
        view.findViewById<View>(R.id.quick_safs)?.setOnClickListener { safsSwitch?.toggle() }
        view.findViewById<View>(R.id.quick_cas)?.setOnClickListener {
            openSettings(Settings.MenuTag.SECTION_RENDERER)
        }
        view.findViewById<View>(R.id.quick_resolution)?.setOnClickListener {
            showIntChoice(
                R.string.mw_resolution,
                R.array.rendererResolutionNames,
                R.array.rendererResolutionValues,
                IntSetting.RENDERER_RESOLUTION,
                view
            )
        }
        view.findViewById<View>(R.id.quick_frame_pacing)?.setOnClickListener {
            showIntChoice(
                R.string.mw_frame_pacing,
                R.array.framePacingModeNames,
                R.array.framePacingModeValues,
                IntSetting.FRAME_PACING_MODE,
                view
            )
        }
        view.findViewById<View>(R.id.quick_adpf)?.setOnClickListener {
            openSettings(Settings.MenuTag.SECTION_ADPF)
        }
        view.findViewById<View>(R.id.quick_driver)?.setOnClickListener {
            openSubscreen(SettingsSubscreen.DRIVER_MANAGER)
        }
        view.findViewById<View>(R.id.quick_per_game)?.setOnClickListener {
            binding.root.findNavController().popBackStack()
        }
        view.findViewById<View>(R.id.quick_details)?.setOnClickListener {
            openSettings(Settings.MenuTag.SECTION_PERFORMANCE_STATS)
        }
        view.findViewById<View>(R.id.quick_apply)?.setOnClickListener {
            persistDashboardSettings(applyRuntime = true)
            Toast.makeText(requireContext(), R.string.mw_changes_applied, Toast.LENGTH_SHORT).show()
        }
        view.findViewById<View>(R.id.quick_reset)?.setOnClickListener {
            MaterialAlertDialogBuilder(requireContext())
                .setTitle(R.string.mw_restore_defaults)
                .setMessage(R.string.mw_restore_defaults_desc)
                .setNegativeButton(android.R.string.cancel, null)
                .setPositiveButton(R.string.mw_restore_defaults) { _, _ ->
                    BooleanSetting.USE_DOCKED_MODE.reset()
                    BooleanSetting.SMART_ADAPTIVE_FRAME_SKIP.reset()
                    IntSetting.RENDERER_RESOLUTION.reset()
                    IntSetting.FRAME_PACING_MODE.reset()
                    MoonwitchCasSettings.enabled.reset()
                    MoonwitchCasSettings.sharpness.reset()
                    persistDashboardSettings(applyRuntime = true)
                    dockSwitch?.isChecked = BooleanSetting.USE_DOCKED_MODE.getBoolean(false)
                    safsSwitch?.isChecked =
                        BooleanSetting.SMART_ADAPTIVE_FRAME_SKIP.getBoolean(false)
                    casSlider?.value = MoonwitchCasSettings.sharpness.getInt(false).toFloat()
                    updateQuickSettingLabels(view)
                    Toast.makeText(
                        requireContext(),
                        R.string.mw_defaults_restored,
                        Toast.LENGTH_SHORT
                    ).show()
                }
                .show()
        }

        driverViewModel.updateDriverNameForGame(null)
        driverViewModel.selectedDriverTitle.collect(viewLifecycleOwner) { driverName ->
            view.findViewById<TextView>(R.id.quick_driver_value)?.text =
                driverName.ifBlank { getString(R.string.mw_system_driver) }
        }

        updatePerformanceSummary(view)
    }

    private fun showIntChoice(
        titleId: Int,
        namesId: Int,
        valuesId: Int,
        setting: IntSetting,
        dashboardView: View
    ) {
        val names = resources.getStringArray(namesId)
        val values = resources.getIntArray(valuesId)
        val checked = values.indexOf(setting.getInt(false)).coerceAtLeast(0)
        MaterialAlertDialogBuilder(requireContext())
            .setTitle(titleId)
            .setSingleChoiceItems(names, checked) { dialog, which ->
                values.getOrNull(which)?.let(setting::setInt)
                persistDashboardSettings(applyRuntime = true)
                updateQuickSettingLabels(dashboardView)
                dialog.dismiss()
            }
            .setNegativeButton(android.R.string.cancel, null)
            .show()
    }

    private fun updateQuickSettingLabels(view: View) {
        val resolutionNames = resources.getStringArray(R.array.rendererResolutionNames)
        val resolutionValues = resources.getIntArray(R.array.rendererResolutionValues)
        val resolutionIndex = resolutionValues.indexOf(
            IntSetting.RENDERER_RESOLUTION.getInt(false)
        )
        view.findViewById<TextView>(R.id.quick_resolution_value)?.text =
            resolutionNames.getOrNull(resolutionIndex)?.substringBefore(' ')
                ?: getString(R.string.mw_not_available)

        val pacingNames = resources.getStringArray(R.array.framePacingModeNames)
        val pacingValues = resources.getIntArray(R.array.framePacingModeValues)
        val pacingIndex = pacingValues.indexOf(IntSetting.FRAME_PACING_MODE.getInt(false))
        view.findViewById<TextView>(R.id.quick_frame_pacing_value)?.text =
            pacingNames.getOrNull(pacingIndex) ?: getString(R.string.mw_not_available)

        val sharpness = MoonwitchCasSettings.sharpness.getInt(false)
        view.findViewById<TextView>(R.id.quick_cas_value)?.text =
            getString(R.string.mw_percent_value, sharpness)

        val adpfSnapshot = if (NativeLibrary.isRunning()) {
            runCatching { PerformanceLabNative.snapshot() }.getOrNull()
        } else {
            null
        }
        view.findViewById<TextView>(R.id.quick_adpf_value)?.text = when {
            !NativeLibrary.isRunning() -> getString(R.string.mw_no_session_short)
            adpfSnapshot == null || !adpfSnapshot.adpfAvailable ->
                getString(R.string.mw_unavailable_short)
            adpfSnapshot.adpfRenderActive -> getString(R.string.mw_active_short)
            else -> getString(R.string.mw_available_short)
        }
    }

    private fun updatePerformanceSummary(view: View) {
        val running = NativeLibrary.isRunning()
        val snapshot = if (running) runCatching { PerformanceLabNative.snapshot() }.getOrNull()
            else null

        val fpsText: String
        val frameTimeText: String
        val stateText: String
        if (!running) {
            fpsText = getString(R.string.mw_metric_unavailable_fps)
            frameTimeText = getString(R.string.mw_metric_unavailable_ms)
            stateText = getString(R.string.mw_no_session)
        } else if (snapshot == null || snapshot.meanMs <= 0.0) {
            fpsText = getString(R.string.mw_metric_unavailable_fps)
            frameTimeText = getString(R.string.mw_metric_unavailable_ms)
            stateText = getString(R.string.mw_unavailable_short)
        } else {
            fpsText = getString(R.string.mw_fps_value, 1000.0 / snapshot.meanMs)
            frameTimeText = getString(R.string.mw_ms_value, snapshot.meanMs)
            stateText = when {
                !snapshot.ready -> getString(R.string.mw_collecting)
                snapshot.p95Ms <= snapshot.meanMs * 1.25 -> getString(R.string.mw_stable)
                else -> getString(R.string.mw_variable)
            }
        }

        view.findViewById<TextView>(R.id.quick_summary_fps)?.text = fpsText
        view.findViewById<TextView>(R.id.quick_summary_frametime)?.text = frameTimeText
        view.findViewById<TextView>(R.id.quick_summary_state)?.text = stateText
    }

    private fun persistDashboardSettings(applyRuntime: Boolean = false) {
        NativeConfig.saveGlobalConfig()
        if (applyRuntime && NativeLibrary.isRunning()) {
            NativeLibrary.applySettings()
        }
    }

    private fun openSettings(menuTag: Settings.MenuTag) {
        val action = HomeNavigationDirections.actionGlobalSettingsActivity(null, menuTag)
        binding.root.findNavController().navigate(action)
    }

    private fun openSubscreen(destination: SettingsSubscreen) {
        val action = HomeNavigationDirections.actionGlobalSettingsSubscreenActivity(destination, null)
        binding.root.findNavController().navigate(action)
    }

    override fun onResume() {
        super.onResume()
        if (resources.configuration.orientation == Configuration.ORIENTATION_LANDSCAPE) {
            view?.let {
                updateQuickSettingLabels(it)
                updatePerformanceSummary(it)
            }
            driverViewModel.updateDriverNameForGame(null)
        }
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }

    private fun setInsets() = ViewCompat.setOnApplyWindowInsetsListener(binding.root) { _, windowInsets ->
        val barInsets = windowInsets.getInsets(WindowInsetsCompat.Type.systemBars())
        val cutoutInsets = windowInsets.getInsets(WindowInsetsCompat.Type.displayCutout())
        val navInsets = windowInsets.getInsets(WindowInsetsCompat.Type.navigationBars())
        binding.root.updatePadding(
            left = barInsets.left + cutoutInsets.left,
            right = barInsets.right + cutoutInsets.right,
            top = maxOf(barInsets.top, cutoutInsets.top)
        )
        binding.scrollViewSettings.updatePadding(bottom = maxOf(navInsets.bottom, cutoutInsets.bottom) + resources.getDimensionPixelSize(R.dimen.spacing_med))
        windowInsets
    }
}
