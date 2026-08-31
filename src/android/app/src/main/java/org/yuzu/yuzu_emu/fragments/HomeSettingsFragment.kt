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

    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?): View {
        _binding = FragmentHomeSettingsBinding.inflate(inflater)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        homeViewModel.setStatusBarShadeVisibility(false)

        options = buildCategories()
        binding.homeSettingsList.apply {
            layoutManager = GridLayoutManager(requireContext(), 2)
            isNestedScrollingEnabled = false
            val spacing = resources.getDimensionPixelSize(R.dimen.spacing_small)
            addItemDecoration(SpacingItemDecoration(spacing))
        }
        renderOptions(options)

        binding.settingsSearchText.doOnTextChanged { text, _, _, _ ->
            val query = text?.toString()?.trim().orEmpty()
            val filtered = if (query.isEmpty()) options else options.filter {
                getString(it.titleId).contains(query, ignoreCase = true) ||
                    getString(it.descriptionId).contains(query, ignoreCase = true)
            }
            renderOptions(filtered)
        }

        binding.settingsShortcutCard.setOnClickListener { openSettings(Settings.MenuTag.SECTION_ROOT) }
        binding.performanceCard.setOnClickListener { openSettings(Settings.MenuTag.SECTION_PERFORMANCE_STATS) }
        binding.helpCard.setOnClickListener {
            val action = HomeNavigationDirections.actionGlobalSettingsSubscreenActivity(SettingsSubscreen.ABOUT, null)
            binding.root.findNavController().navigate(action)
        }

        setInsets()
    }

    private fun buildCategories(): List<HomeSetting> = listOf(
        HomeSetting(
            R.string.mw_cat_general,
            R.string.mw_cat_general_desc,
            R.drawable.ic_settings,
            onClick = { openSettings(Settings.MenuTag.SECTION_ROOT) }
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
            onClick = { openSettings(Settings.MenuTag.SECTION_PERFORMANCE_STATS) }
        )
    )

    private fun renderOptions(items: List<HomeSetting>) {
        binding.homeSettingsList.adapter = HomeSettingAdapter(
            requireActivity() as AppCompatActivity,
            viewLifecycleOwner,
            items
        )
    }

    private fun openSettings(menuTag: Settings.MenuTag) {
        val action = HomeNavigationDirections.actionGlobalSettingsActivity(null, menuTag)
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
