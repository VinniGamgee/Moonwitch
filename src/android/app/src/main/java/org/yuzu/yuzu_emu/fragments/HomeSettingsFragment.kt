// SPDX-FileCopyrightText: Copyright 2026 Eden Emulator Project
// SPDX-License-Identifier: GPL-3.0-or-later

package org.yuzu.yuzu_emu.fragments

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.updatePadding
import androidx.core.widget.doOnTextChanged
import androidx.fragment.app.Fragment
import androidx.fragment.app.activityViewModels
import androidx.navigation.findNavController
import androidx.recyclerview.widget.GridLayoutManager
import org.yuzu.yuzu_emu.HomeNavigationDirections
import org.yuzu.yuzu_emu.R
import org.yuzu.yuzu_emu.adapters.HomeSettingAdapter
import org.yuzu.yuzu_emu.databinding.FragmentHomeSettingsBinding
import org.yuzu.yuzu_emu.features.fetcher.SpacingItemDecoration
import org.yuzu.yuzu_emu.features.settings.model.Settings
import org.yuzu.yuzu_emu.features.settings.ui.SettingsSubscreen
import org.yuzu.yuzu_emu.model.HomeSetting
import org.yuzu.yuzu_emu.model.HomeViewModel

class HomeSettingsFragment : Fragment() {
    private var _binding: FragmentHomeSettingsBinding? = null
    private val binding get() = _binding!!
    private val homeViewModel: HomeViewModel by activityViewModels()
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

    private fun openSettings(menuTag: Settings.MenuTag) {
        val action = HomeNavigationDirections.actionGlobalSettingsActivity(null, menuTag)
        binding.root.findNavController().navigate(action)
    }

    private fun openSubscreen(destination: SettingsSubscreen) {
        val action = HomeNavigationDirections.actionGlobalSettingsSubscreenActivity(destination, null)
        binding.root.findNavController().navigate(action)
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
