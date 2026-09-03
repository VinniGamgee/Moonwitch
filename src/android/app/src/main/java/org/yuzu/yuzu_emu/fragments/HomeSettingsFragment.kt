// SPDX-FileCopyrightText: Copyright 2026 Eden Emulator Project
// SPDX-License-Identifier: GPL-3.0-or-later

package org.yuzu.yuzu_emu.fragments

import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.edit
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.updatePadding
import androidx.fragment.app.Fragment
import androidx.fragment.app.activityViewModels
import androidx.navigation.findNavController
import androidx.preference.PreferenceManager
import androidx.recyclerview.widget.LinearLayoutManager
import org.yuzu.yuzu_emu.HomeNavigationDirections
import org.yuzu.yuzu_emu.R
import org.yuzu.yuzu_emu.adapters.HomeSettingAdapter
import org.yuzu.yuzu_emu.databinding.FragmentHomeSettingsBinding
import org.yuzu.yuzu_emu.features.settings.model.Settings
import org.yuzu.yuzu_emu.features.settings.ui.SettingsSubscreen
import org.yuzu.yuzu_emu.model.HomeSetting
import org.yuzu.yuzu_emu.model.HomeViewModel

class HomeSettingsFragment : Fragment() {
    private var _binding: FragmentHomeSettingsBinding? = null
    private val binding get() = _binding!!
    private val homeViewModel: HomeViewModel by activityViewModels()

    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?): View {
        _binding = FragmentHomeSettingsBinding.inflate(inflater)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        homeViewModel.setStatusBarShadeVisibility(true)

        binding.homeSettingsList.apply {
            layoutManager = LinearLayoutManager(requireContext())
            isNestedScrollingEnabled = false
            adapter = HomeSettingAdapter(
                requireActivity() as AppCompatActivity,
                viewLifecycleOwner,
                buildCategories()
            )
        }

        binding.navHome.setOnClickListener { navigateToLibrary(0) }
        binding.navGames.setOnClickListener { navigateToLibrary(1) }
        binding.navSettings.setOnClickListener { /* already here */ }

        setInsets()
    }

    private fun buildCategories(): List<HomeSetting> = listOf(
        HomeSetting(
            R.string.mw_ui_performance,
            R.string.mw_ui_perf_desc,
            R.drawable.ic_mw_gauge,
            onClick = { openSettings(Settings.MenuTag.SECTION_MOONWITCH_PERFORMANCE) }
        ),
        HomeSetting(
            R.string.mw_ui_graphics,
            R.string.mw_ui_graphics_desc,
            R.drawable.ic_graphics,
            onClick = { openSettings(Settings.MenuTag.SECTION_RENDERER) }
        ),
        HomeSetting(
            R.string.mw_ui_controls,
            R.string.mw_ui_controls_desc,
            R.drawable.ic_controller,
            onClick = { openSettings(Settings.MenuTag.SECTION_INPUT) }
        ),
        HomeSetting(
            R.string.mw_ui_audio,
            R.string.mw_ui_audio_desc,
            R.drawable.ic_audio,
            onClick = { openSettings(Settings.MenuTag.SECTION_AUDIO) }
        ),
        HomeSetting(
            R.string.mw_ui_interface,
            R.string.mw_ui_interface_desc,
            R.drawable.ic_palette,
            onClick = { openSettings(Settings.MenuTag.SECTION_APP_SETTINGS) }
        ),
        HomeSetting(
            R.string.mw_ui_folders_games,
            R.string.mw_ui_folders_desc,
            R.drawable.ic_mw_library,
            onClick = { openSubscreen(SettingsSubscreen.GAME_FOLDERS) }
        ),
        HomeSetting(
            R.string.mw_ui_drivers,
            R.string.mw_ui_drivers_desc,
            R.drawable.ic_mw_system,
            onClick = { openSubscreen(SettingsSubscreen.DRIVER_MANAGER) }
        ),
        HomeSetting(
            R.string.mw_ui_advanced,
            R.string.mw_ui_advanced_desc,
            R.drawable.ic_settings,
            onClick = { openSettings(Settings.MenuTag.SECTION_ROOT) }
        )
    )

    private fun navigateToLibrary(page: Int) {
        PreferenceManager.getDefaultSharedPreferences(requireContext()).edit {
            putInt("MoonwitchFrontendPage", page)
        }
        binding.root.findNavController().popBackStack(R.id.gamesFragment, false)
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
        binding.scrollViewSettings.updatePadding(
            bottom = maxOf(navInsets.bottom, cutoutInsets.bottom) + resources.getDimensionPixelSize(R.dimen.mw_ui_nav_height)
        )
        windowInsets
    }
}
