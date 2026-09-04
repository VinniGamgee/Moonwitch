// SPDX-FileCopyrightText: Copyright 2026 Eden Emulator Project
// SPDX-License-Identifier: GPL-3.0-or-later

package org.yuzu.yuzu_emu.fragments

import android.content.Intent
import android.graphics.Color
import android.net.Uri
import android.graphics.BitmapFactory
import android.graphics.RenderEffect
import android.graphics.Shader
import android.content.pm.ShortcutInfo
import android.content.pm.ShortcutManager
import android.os.Build
import android.os.Bundle
import android.text.format.DateUtils
import android.provider.DocumentsContract
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.view.WindowManager
import android.widget.FrameLayout
import android.widget.ImageView
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.updatePadding
import androidx.core.content.edit
import androidx.documentfile.provider.DocumentFile
import androidx.fragment.app.Fragment
import androidx.fragment.app.activityViewModels
import androidx.lifecycle.lifecycleScope
import androidx.navigation.findNavController
import androidx.navigation.fragment.navArgs
import androidx.preference.PreferenceManager
import androidx.recyclerview.widget.LinearLayoutManager
import com.google.android.material.bottomsheet.BottomSheetBehavior
import com.google.android.material.bottomsheet.BottomSheetDialog
import com.google.android.material.transition.MaterialSharedAxis
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.yuzu.yuzu_emu.HomeNavigationDirections
import org.yuzu.yuzu_emu.NativeLibrary
import org.yuzu.yuzu_emu.R
import org.yuzu.yuzu_emu.YuzuApplication
import org.yuzu.yuzu_emu.adapters.GamePropertiesAdapter
import org.yuzu.yuzu_emu.databinding.FragmentGamePropertiesBinding
import org.yuzu.yuzu_emu.features.DocumentProvider
import org.yuzu.yuzu_emu.features.settings.model.Settings
import org.yuzu.yuzu_emu.features.settings.ui.SettingsSubscreen
import org.yuzu.yuzu_emu.model.AddonViewModel
import org.yuzu.yuzu_emu.model.GameProperty
import org.yuzu.yuzu_emu.model.GamesViewModel
import org.yuzu.yuzu_emu.model.HomeViewModel
import org.yuzu.yuzu_emu.model.InstallableProperty
import org.yuzu.yuzu_emu.model.SubMenuPropertySecondaryAction
import org.yuzu.yuzu_emu.model.SubmenuProperty
import org.yuzu.yuzu_emu.model.TaskState
import org.yuzu.yuzu_emu.utils.DeviceProfileManager
import org.yuzu.yuzu_emu.utils.DirectoryInitialization
import org.yuzu.yuzu_emu.utils.FileUtil
import org.yuzu.yuzu_emu.utils.GameHelper
import org.yuzu.yuzu_emu.utils.GameIconUtils
import org.yuzu.yuzu_emu.utils.GameSessionStats
import org.yuzu.yuzu_emu.utils.MemoryUtil
import org.yuzu.yuzu_emu.utils.collect
import java.io.BufferedOutputStream
import java.io.File

class GamePropertiesFragment : Fragment() {
    private var _binding: FragmentGamePropertiesBinding? = null
    private val binding get() = _binding!!

    private val homeViewModel: HomeViewModel by activityViewModels()
    private val gamesViewModel: GamesViewModel by activityViewModels()
    private val addonViewModel: AddonViewModel by activityViewModels()

    private val args by navArgs<GamePropertiesFragmentArgs>()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enterTransition = MaterialSharedAxis(MaterialSharedAxis.Y, true)
        returnTransition = MaterialSharedAxis(MaterialSharedAxis.Y, false)
        reenterTransition = MaterialSharedAxis(MaterialSharedAxis.X, false)
    }

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentGamePropertiesBinding.inflate(layoutInflater)
        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        homeViewModel.setStatusBarShadeVisibility(true)

        binding.buttonBack.setOnClickListener {
            view.findNavController().popBackStack()
        }

        binding.buttonShortcut.setOnClickListener { showMoreActions() }

        binding.title.text = args.game.title
        setupGameCover()
        setupGameArtwork()
        setupGameLogo()
        binding.developer.text = args.game.developer.ifBlank {
            getString(R.string.mw_gamehub_unknown_developer)
        }
        binding.developer.visibility = View.GONE
        setupQuickActions()
        refreshOverview()

        binding.buttonStart.setOnClickListener {
            LaunchGameDialogFragment.newInstance(args.game)
                .show(childFragmentManager, LaunchGameDialogFragment.TAG)
        }

        if (GameHelper.cachedGameList.isEmpty()) {
            binding.buttonStart.isEnabled = false
            viewLifecycleOwner.lifecycleScope.launch {
                withContext(Dispatchers.IO) {
                    GameHelper.restoreContentForGame(args.game)
                }
                if (_binding == null) {
                    return@launch
                }
                addonViewModel.onAddonsViewStarted(args.game)
                binding.buttonStart.isEnabled = true
            }
        }

        reloadList()

        homeViewModel.openImportSaves.collect(
            viewLifecycleOwner,
            resetState = { homeViewModel.setOpenImportSaves(false) }
        ) { if (it) importSaves.launch(arrayOf("application/zip")) }
        homeViewModel.reloadPropertiesList.collect(
            viewLifecycleOwner,
            resetState = { homeViewModel.reloadPropertiesList(false) }
        ) { if (it) reloadList() }

        setInsets()
    }

    override fun onDestroy() {
        val isChangingConfigurations = activity?.isChangingConfigurations == true
        super.onDestroy()
        if (!isChangingConfigurations) {
            gamesViewModel.reloadGames(true)
        }
    }

    private fun showDeviceProfileDialog() {
        val preview = DeviceProfileManager.preview(args.game)
        val recommendation = preview.recommendation

        if (recommendation == null) {
            com.google.android.material.dialog.MaterialAlertDialogBuilder(requireContext())
                .setTitle(R.string.device_profile_title)
                .setMessage(
                    getString(
                        R.string.device_profile_unavailable_message,
                        preview.deviceName,
                        preview.socName
                    )
                )
                .setPositiveButton(android.R.string.ok, null)
                .show()
            return
        }

        val driverName = DeviceProfileManager.driverName(requireContext(), recommendation)
        val driverStatus = if (DeviceProfileManager.isRecommendedDriverInstalled()) {
            getString(R.string.device_profile_driver_installed, driverName)
        } else {
            getString(R.string.device_profile_driver_missing, driverName)
        }

        com.google.android.material.dialog.MaterialAlertDialogBuilder(requireContext())
            .setTitle(R.string.device_profile_dialog_title)
            .setMessage(
                getString(
                    R.string.device_profile_dialog_message,
                    preview.deviceName,
                    preview.socName,
                    getString(recommendation.profileNameId),
                    driverStatus,
                    getString(recommendation.changesId)
                )
            )
            .setNegativeButton(android.R.string.cancel, null)
            .setPositiveButton(R.string.device_profile_apply) { _, _ ->
                applyDeviceProfile(recommendation)
            }
            .show()
    }

    private fun applyDeviceProfile(recommendation: DeviceProfileManager.Recommendation) {
        viewLifecycleOwner.lifecycleScope.launch {
            val result = withContext(Dispatchers.IO) {
                DeviceProfileManager.apply(requireContext(), args.game, recommendation)
            }

            val driverName = DeviceProfileManager.driverName(requireContext(), recommendation)
            val message = when (result.driverOutcome) {
                DeviceProfileManager.DriverOutcome.SELECTED ->
                    getString(R.string.device_profile_applied_driver_selected, driverName)

                DeviceProfileManager.DriverOutcome.ALREADY_SELECTED ->
                    getString(R.string.device_profile_applied_driver_ready, driverName)

                DeviceProfileManager.DriverOutcome.NOT_INSTALLED ->
                    getString(R.string.device_profile_applied_driver_missing, driverName)

                DeviceProfileManager.DriverOutcome.BUSY ->
                    getString(R.string.device_profile_apply_busy)

                DeviceProfileManager.DriverOutcome.FAILED ->
                    getString(R.string.device_profile_apply_failed)
            }

            Toast.makeText(requireContext(), message, Toast.LENGTH_LONG).show()
            if (result.applied) {
                homeViewModel.reloadPropertiesList(true)
            }
        }
    }

    private fun readablePlayTime(): String {
        val playTimeSeconds = NativeLibrary.playTimeManagerGetPlayTime(args.game.programId)
        return readableDuration(playTimeSeconds)
    }

    private fun readableDuration(playTimeSeconds: Long): String {
        val hours = playTimeSeconds / 3600
        val minutes = (playTimeSeconds % 3600) / 60
        val seconds = playTimeSeconds % 60

        return when {
            hours > 0 -> "$hours${getString(R.string.hours_abbr)} $minutes${getString(R.string.minutes_abbr)} $seconds${getString(R.string.seconds_abbr)}"
            minutes > 0 -> "$minutes${getString(R.string.minutes_abbr)} $seconds${getString(R.string.seconds_abbr)}"
            else -> "$seconds${getString(R.string.seconds_abbr)}"
        }
    }

    private fun getPlayTime() {
        binding.statPlaytimeValue.text = readablePlayTime()
    }

    private fun buildGameMeta(): String {
        val developer = args.game.developer.ifBlank {
            getString(R.string.mw_gamehub_unknown_developer)
        }
        return if (args.game.version.isBlank()) developer
        else getString(R.string.mw_gamehub_v2_meta, developer, args.game.version)
    }

    private fun gameAssetDirectory(): File = File(
        DirectoryInitialization.userDirectory +
            "/moonwitch/metadata/" + args.game.settingsName
    )

    private fun gameDescription(): String {
        val assetDirectory = gameAssetDirectory()
        val legacyMetadata = File(
            DirectoryInitialization.userDirectory +
                "/moonwitch/metadata/" + args.game.settingsName + ".txt"
        )
        val candidates = listOf(
            File(assetDirectory, "description.txt"),
            File(assetDirectory, "description.pt-BR.txt"),
            legacyMetadata
        )
        val customDescription = candidates.firstNotNullOfOrNull { file ->
            runCatching {
                if (file.isFile) file.readText().trim().takeIf(String::isNotBlank) else null
            }.getOrNull()
        }
        return customDescription ?: getString(R.string.mw_gamehub_v2_description_fallback)
    }

    private fun findArtwork(names: List<String>): File? {
        val directory = gameAssetDirectory()
        runCatching { directory.mkdirs() }
        return names.asSequence()
            .map { File(directory, it) }
            .firstOrNull(File::isFile)
    }

    private fun findHeroArtwork(): File? = findArtwork(
        listOf(
            "hero.jpg", "hero.jpeg", "hero.png", "hero.webp",
            "background.jpg", "background.jpeg", "background.png", "background.webp"
        )
    )

    private fun findCoverArtwork(): File? = findArtwork(
        listOf(
            "cover.jpg", "cover.jpeg", "cover.png", "cover.webp",
            "poster.jpg", "poster.jpeg", "poster.png", "poster.webp",
            "boxart.jpg", "boxart.jpeg", "boxart.png", "boxart.webp"
        )
    )

    private fun findLogoArtwork(): File? = findArtwork(
        listOf("logo.png", "logo.webp", "logo.jpg", "logo.jpeg")
    )

    private fun setupGameCover() {
        val coverArtwork = findCoverArtwork()
        if (coverArtwork == null) {
            applyFallbackCover()
            return
        }

        (binding.imageGameScreen.parent as? View)?.let { updateViewHeight(it, 164) }
        viewLifecycleOwner.lifecycleScope.launch {
            val bitmap = withContext(Dispatchers.IO) { decodeArtwork(coverArtwork, 1200) }
            if (_binding == null || bitmap == null) {
                if (_binding != null) applyFallbackCover()
                return@launch
            }

            binding.imageGameScreen.apply {
                setPadding(0, 0, 0, 0)
                scaleType = ImageView.ScaleType.CENTER_CROP
                setImageBitmap(bitmap)
            }
        }
    }

    private fun applyFallbackCover() {
        GameIconUtils.loadGameIcon(args.game, binding.imageGameScreen)
        val inset = (6 * resources.displayMetrics.density).toInt()
        binding.imageGameScreen.apply {
            setPadding(inset, inset, inset, inset)
            scaleType = ImageView.ScaleType.FIT_CENTER
        }
        (binding.imageGameScreen.parent as? View)?.let { updateViewHeight(it, 118) }
    }

    private fun setupGameArtwork() {
        val heroArtwork = findHeroArtwork()
        if (heroArtwork == null) {
            applyFallbackBackdrop()
            return
        }

        (binding.imageGameBackdrop.parent as? View)?.let { updateViewHeight(it, 430) }
        viewLifecycleOwner.lifecycleScope.launch {
            val bitmap = withContext(Dispatchers.IO) { decodeArtwork(heroArtwork, 1920) }
            if (_binding == null || bitmap == null) {
                if (_binding != null) applyFallbackBackdrop()
                return@launch
            }

            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                binding.imageGameBackdrop.setRenderEffect(null)
            }
            binding.imageGameBackdrop.scaleX = 1f
            binding.imageGameBackdrop.scaleY = 1f
            binding.imageGameBackdrop.alpha = 0.82f
            binding.imageGameBackdrop.setImageBitmap(bitmap)
        }
    }

    private fun setupGameLogo() {
        val logoArtwork = findLogoArtwork()
        if (logoArtwork == null) {
            binding.imageGameLogo.setImageDrawable(null)
            binding.imageGameLogo.visibility = View.GONE
            binding.title.visibility = View.VISIBLE
            return
        }

        viewLifecycleOwner.lifecycleScope.launch {
            val bitmap = withContext(Dispatchers.IO) { decodeArtwork(logoArtwork, 900) }
            if (_binding == null) return@launch
            if (bitmap == null) {
                binding.imageGameLogo.setImageDrawable(null)
                binding.imageGameLogo.visibility = View.GONE
                binding.title.visibility = View.VISIBLE
                return@launch
            }
            binding.imageGameLogo.setImageBitmap(bitmap)
            binding.imageGameLogo.visibility = View.VISIBLE
            binding.title.visibility = View.GONE
        }
    }

    private fun applyFallbackBackdrop() {
        (binding.imageGameBackdrop.parent as? View)?.let { updateViewHeight(it, 330) }
        GameIconUtils.loadGameIcon(args.game, binding.imageGameBackdrop)
        binding.imageGameBackdrop.alpha = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) 0.30f else 0.16f
        binding.imageGameBackdrop.scaleX = 1.28f
        binding.imageGameBackdrop.scaleY = 1.28f
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            binding.imageGameBackdrop.setRenderEffect(
                RenderEffect.createBlurEffect(36f, 36f, Shader.TileMode.CLAMP)
            )
        }
    }

    private fun updateViewHeight(view: View, heightDp: Int) {
        val params = view.layoutParams
        params.height = (heightDp * resources.displayMetrics.density).toInt()
        view.layoutParams = params
    }

    private fun decodeArtwork(file: File, maxDimension: Int) = runCatching {
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeFile(file.absolutePath, bounds)
        var sampleSize = 1
        while (
            bounds.outWidth > 0 && bounds.outHeight > 0 &&
            (bounds.outWidth / sampleSize > maxDimension || bounds.outHeight / sampleSize > maxDimension)
        ) {
            sampleSize *= 2
        }
        BitmapFactory.decodeFile(
            file.absolutePath,
            BitmapFactory.Options().apply { inSampleSize = sampleSize }
        )
    }.getOrNull()

    private fun importArtwork(uri: Uri, stem: String) {
        viewLifecycleOwner.lifecycleScope.launch {
            val imported = withContext(Dispatchers.IO) {
                runCatching {
                    val directory = gameAssetDirectory().apply { mkdirs() }
                    val resolver = requireContext().contentResolver
                    val extension = when (resolver.getType(uri)) {
                        "image/jpeg" -> "jpg"
                        "image/webp" -> "webp"
                        else -> "png"
                    }
                    listOf("jpg", "jpeg", "png", "webp").forEach {
                        File(directory, "$stem.$it").delete()
                    }
                    val target = File(directory, "$stem.$extension")
                    resolver.openInputStream(uri)?.use { input ->
                        target.outputStream().use { output -> input.copyTo(output) }
                    } ?: return@runCatching false
                    target.isFile && target.length() > 0L
                }.getOrDefault(false)
            }

            if (_binding == null) return@launch
            if (imported) {
                when (stem) {
                    "cover" -> setupGameCover()
                    "logo" -> setupGameLogo()
                    else -> setupGameArtwork()
                }
                Toast.makeText(
                    requireContext(),
                    when (stem) {
                        "cover" -> R.string.mw_gamehub_v22_cover_updated
                        "logo" -> R.string.mw_gamehub_v23_logo_updated
                        else -> R.string.mw_gamehub_v22_hero_updated
                    },
                    Toast.LENGTH_SHORT
                ).show()
            } else {
                Toast.makeText(
                    requireContext(),
                    R.string.mw_gamehub_v22_artwork_failed,
                    Toast.LENGTH_SHORT
                ).show()
            }
        }
    }

    private fun readableLastPlayed(): String {
        val value = PreferenceManager.getDefaultSharedPreferences(requireContext())
            .getLong(args.game.keyLastPlayedTime, 0L)
        if (value <= 0L) return getString(R.string.mw_gamehub_v2_never)

        return DateUtils.getRelativeTimeSpanString(
            value,
            System.currentTimeMillis(),
            DateUtils.MINUTE_IN_MILLIS,
            DateUtils.FORMAT_ABBREV_RELATIVE
        ).toString()
    }

    private fun readableGameSize(): String {
        val bytes = DocumentFile.fromSingleUri(
            requireContext(),
            android.net.Uri.parse(args.game.path)
        )?.length() ?: 0L
        return if (bytes > 0L) MemoryUtil.bytesToSizeUnit(bytes.toFloat())
        else getString(R.string.mw_gamehub_v2_unknown_value)
    }

    private fun refreshOverview() {
        binding.gameMeta.text = buildGameMeta()
        binding.gameDescription.text = gameDescription()
        getPlayTime()
        binding.statLastPlayedValue.text = readableLastPlayed()
        binding.statSizeValue.text = readableGameSize()
        binding.statVersionValue.text = args.game.version.ifBlank {
            getString(R.string.mw_gamehub_v2_base_version)
        }
        binding.statTitleIdValue.text = args.game.programIdHex
    }

    private fun setupQuickActions() {
        binding.actionFavorite.setOnClickListener { toggleFavorite() }
        binding.actionPerformance.setOnClickListener {
            openSettings(Settings.MenuTag.SECTION_MOONWITCH_PERFORMANCE)
        }
        binding.actionGraphics.setOnClickListener {
            openSettings(Settings.MenuTag.SECTION_RENDERER)
        }
        binding.actionMods.setOnClickListener {
            openContent(SettingsSubscreen.ADDONS_MODS)
        }
        binding.actionUpdates.setOnClickListener {
            openContent(SettingsSubscreen.ADDONS_UPDATES_DLC)
        }
        binding.actionDriver.setOnClickListener { openDriverManager() }
        binding.actionStatistics.setOnClickListener { showStatistics() }
        binding.actionCustomize.setOnClickListener { showCustomizeActions() }
        binding.statPlaytimeRow.setOnClickListener { showStatistics() }
        val contentVisibility = if (args.game.isHomebrew) View.GONE else View.VISIBLE
        binding.actionMods.visibility = contentVisibility
        binding.actionUpdates.visibility = contentVisibility
        refreshFavoriteAction()
    }

    private fun refreshFavoriteAction() {
        binding.actionFavoriteIcon.setImageResource(
            if (isFavorite()) R.drawable.ic_mw_star_filled else R.drawable.ic_mw_star
        )
    }

    private fun openRootSettings() {
        openSettings(Settings.MenuTag.SECTION_ROOT)
    }

    private fun openSettings(menuTag: Settings.MenuTag) {
        val action = HomeNavigationDirections.actionGlobalSettingsActivity(
            args.game,
            menuTag
        )
        binding.root.findNavController().navigate(action)
    }

    private fun openContent(destination: SettingsSubscreen) {
        if (args.game.isHomebrew) return
        val action = HomeNavigationDirections.actionGlobalSettingsSubscreenActivity(
            destination,
            args.game
        )
        binding.root.findNavController().navigate(action)
    }

    private fun openDriverManager() {
        val action = HomeNavigationDirections.actionGlobalSettingsSubscreenActivity(
            SettingsSubscreen.DRIVER_MANAGER,
            args.game
        )
        binding.root.findNavController().navigate(action)
    }

    private fun showStatistics() {
        refreshOverview()
        val statistics = GameSessionStats.snapshot(requireContext(), args.game)
        val sheet = layoutInflater.inflate(R.layout.bottom_sheet_gamehub_statistics, null)
        sheet.findViewById<android.widget.TextView>(R.id.statistics_game_title).text = args.game.title
        sheet.findViewById<android.widget.TextView>(R.id.statistics_total_value).text =
            readablePlayTime()
        sheet.findViewById<android.widget.TextView>(R.id.statistics_last_played_value).text =
            readableLastPlayed()
        sheet.findViewById<android.widget.TextView>(R.id.statistics_sessions_value).text =
            statistics.sessionCount.toString()
        sheet.findViewById<android.widget.TextView>(R.id.statistics_longest_value).text =
            readableDuration(statistics.longestSessionSeconds)
        sheet.findViewById<android.widget.TextView>(R.id.statistics_average_value).text =
            readableDuration(statistics.averageSessionSeconds)

        showExpandedBottomSheet(sheet)
    }

    private fun showCustomizeActions() {
        val sheet = layoutInflater.inflate(R.layout.bottom_sheet_gamehub_customize, null)
        sheet.findViewById<android.widget.TextView>(R.id.customize_game_title).text = args.game.title
        val dialog = BottomSheetDialog(requireContext())
        dialog.setContentView(sheet)

        fun bindAction(viewId: Int, action: () -> Unit) {
            sheet.findViewById<View>(viewId).setOnClickListener {
                dialog.dismiss()
                action()
            }
        }

        bindAction(R.id.customize_cover) { importCoverArtwork.launch(arrayOf("image/*")) }
        bindAction(R.id.customize_hero) { importHeroArtwork.launch(arrayOf("image/*")) }
        bindAction(R.id.customize_logo) { importLogoArtwork.launch(arrayOf("image/*")) }
        bindAction(R.id.customize_reset) { confirmResetArtwork() }
        showExpandedBottomSheet(dialog)
    }

    private fun confirmResetArtwork() {
        com.google.android.material.dialog.MaterialAlertDialogBuilder(requireContext())
            .setTitle(R.string.mw_gamehub_v23_reset_artwork)
            .setMessage(R.string.mw_gamehub_v23_reset_artwork_confirm)
            .setNegativeButton(android.R.string.cancel, null)
            .setPositiveButton(android.R.string.ok) { _, _ -> resetArtwork() }
            .show()
    }

    private fun resetArtwork() {
        val stems = listOf("cover", "poster", "boxart", "hero", "background", "logo")
        val extensions = listOf("jpg", "jpeg", "png", "webp")
        stems.forEach { stem ->
            extensions.forEach { extension -> File(gameAssetDirectory(), "$stem.$extension").delete() }
        }
        setupGameCover()
        setupGameArtwork()
        setupGameLogo()
        Toast.makeText(
            requireContext(),
            R.string.mw_gamehub_v23_artwork_reset,
            Toast.LENGTH_SHORT
        ).show()
    }

    private fun showExpandedBottomSheet(sheet: View) {
        val dialog = BottomSheetDialog(requireContext())
        dialog.setContentView(sheet)
        showExpandedBottomSheet(dialog)
    }

    private fun showExpandedBottomSheet(dialog: BottomSheetDialog) {
        dialog.setOnShowListener {
            dialog.findViewById<FrameLayout>(com.google.android.material.R.id.design_bottom_sheet)?.let {
                it.setBackgroundColor(Color.TRANSPARENT)
                BottomSheetBehavior.from(it).apply {
                    state = BottomSheetBehavior.STATE_EXPANDED
                    skipCollapsed = true
                }
            }
            dialog.window?.apply {
                addFlags(WindowManager.LayoutParams.FLAG_DIM_BEHIND)
                attributes = attributes.apply { dimAmount = 0.64f }
            }
        }
        dialog.show()
    }

    private fun requestPinnedShortcut() {
        val shortcutManager = requireActivity().getSystemService(ShortcutManager::class.java)
        if (!shortcutManager.isRequestPinShortcutSupported) return
        viewLifecycleOwner.lifecycleScope.launch {
            withContext(Dispatchers.IO) {
                val shortcut = ShortcutInfo.Builder(requireContext(), args.game.title)
                    .setShortLabel(args.game.title)
                    .setIcon(
                        GameIconUtils.getShortcutIcon(requireActivity(), args.game)
                            .toIcon(requireContext())
                    )
                    .setIntent(args.game.launchIntent)
                    .build()
                shortcutManager.requestPinShortcut(shortcut, null)
            }
        }
    }

    private fun showMoreActions() {
        val sheet = layoutInflater.inflate(R.layout.bottom_sheet_gamehub_more, null)
        sheet.findViewById<android.widget.TextView>(R.id.more_game_title).text = args.game.title

        val dialog = BottomSheetDialog(requireContext())
        dialog.setContentView(sheet)

        fun bindAction(viewId: Int, action: () -> Unit) {
            sheet.findViewById<View>(viewId).setOnClickListener {
                dialog.dismiss()
                action()
            }
        }

        bindAction(R.id.more_device_profile) { showDeviceProfileDialog() }
        bindAction(R.id.more_cover) { importCoverArtwork.launch(arrayOf("image/*")) }
        bindAction(R.id.more_hero) { importHeroArtwork.launch(arrayOf("image/*")) }
        bindAction(R.id.more_game_info) {
            val action = HomeNavigationDirections.actionGlobalSettingsSubscreenActivity(
                SettingsSubscreen.GAME_INFO,
                args.game
            )
            binding.root.findNavController().navigate(action)
        }
        bindAction(R.id.more_shortcut) { requestPinnedShortcut() }
        bindAction(R.id.more_playtime) { showEditPlaytimeDialog() }
        bindAction(R.id.more_advanced) { openRootSettings() }

        val shortcutManager = requireActivity().getSystemService(ShortcutManager::class.java)
        sheet.findViewById<View>(R.id.more_shortcut).visibility =
            if (shortcutManager.isRequestPinShortcutSupported) View.VISIBLE else View.GONE

        dialog.setOnShowListener {
            dialog.findViewById<FrameLayout>(com.google.android.material.R.id.design_bottom_sheet)?.let {
                it.setBackgroundColor(Color.TRANSPARENT)
                BottomSheetBehavior.from(it).apply {
                    state = BottomSheetBehavior.STATE_EXPANDED
                    skipCollapsed = true
                }
            }
            dialog.window?.apply {
                addFlags(WindowManager.LayoutParams.FLAG_DIM_BEHIND)
                attributes = attributes.apply { dimAmount = 0.64f }
            }
        }
        dialog.show()
    }

    private fun showEditPlaytimeDialog() {
        val dialogView = layoutInflater.inflate(R.layout.dialog_edit_playtime, null)
        val hoursLayout =
            dialogView.findViewById<com.google.android.material.textfield.TextInputLayout>(R.id.layout_hours)
        val minutesLayout =
            dialogView.findViewById<com.google.android.material.textfield.TextInputLayout>(R.id.layout_minutes)
        val secondsLayout =
            dialogView.findViewById<com.google.android.material.textfield.TextInputLayout>(R.id.layout_seconds)
        val hoursInput =
            dialogView.findViewById<com.google.android.material.textfield.TextInputEditText>(R.id.input_hours)
        val minutesInput =
            dialogView.findViewById<com.google.android.material.textfield.TextInputEditText>(R.id.input_minutes)
        val secondsInput =
            dialogView.findViewById<com.google.android.material.textfield.TextInputEditText>(R.id.input_seconds)

        val playTimeSeconds = NativeLibrary.playTimeManagerGetPlayTime(args.game.programId)
        val hours = playTimeSeconds / 3600
        val minutes = (playTimeSeconds % 3600) / 60
        val seconds = playTimeSeconds % 60

        hoursInput.setText(hours.toString())
        minutesInput.setText(minutes.toString())
        secondsInput.setText(seconds.toString())

        val dialog = com.google.android.material.dialog.MaterialAlertDialogBuilder(requireContext())
            .setTitle(R.string.edit_playtime)
            .setView(dialogView)
            .setPositiveButton(android.R.string.ok, null)
            .setNegativeButton(android.R.string.cancel, null)
            .create()

        dialog.setOnShowListener {
            val positiveButton = dialog.getButton(android.app.AlertDialog.BUTTON_POSITIVE)
            positiveButton.setOnClickListener {
                hoursLayout.error = null
                minutesLayout.error = null
                secondsLayout.error = null

                val hoursText = hoursInput.text.toString()
                val minutesText = minutesInput.text.toString()
                val secondsText = secondsInput.text.toString()

                val hoursValue = hoursText.toLongOrNull() ?: 0
                val minutesValue = minutesText.toLongOrNull() ?: 0
                val secondsValue = secondsText.toLongOrNull() ?: 0

                var hasError = false

                // normally cant be above 9999
                if (hoursValue < 0 || hoursValue > 9999) {
                    hoursLayout.error = getString(R.string.hours_must_be_between_0_and_9999)
                    hasError = true
                }

                if (minutesValue < 0 || minutesValue > 59) {
                    minutesLayout.error = getString(R.string.minutes_must_be_between_0_and_59)
                    hasError = true
                }

                if (secondsValue < 0 || secondsValue > 59) {
                    secondsLayout.error = getString(R.string.seconds_must_be_between_0_and_59)
                    hasError = true
                }

                if (!hasError) {
                    val totalSeconds = hoursValue * 3600 + minutesValue * 60 + secondsValue
                    NativeLibrary.playTimeManagerSetPlayTime(args.game.programId, totalSeconds)
                    getPlayTime()
                    Toast.makeText(
                        requireContext(),
                        R.string.playtime_updated_successfully,
                        Toast.LENGTH_SHORT
                    ).show()
                    dialog.dismiss()
                }
            }
        }

        dialog.show()
    }

    private fun reloadList() {
        _binding ?: return

        val properties = mutableListOf<GameProperty>().apply {
            add(
                SubmenuProperty(
                    R.string.mw_ui_performance,
                    R.string.mw_gamehub_performance_desc,
                    R.drawable.ic_mw_gauge,
                    action = {
                        val action = HomeNavigationDirections.actionGlobalSettingsActivity(
                            args.game,
                            Settings.MenuTag.SECTION_MOONWITCH_PERFORMANCE
                        )
                        binding.root.findNavController().navigate(action)
                    }
                )
            )
            add(
                SubmenuProperty(
                    R.string.mw_ui_graphics,
                    R.string.mw_gamehub_graphics_desc,
                    R.drawable.ic_graphics,
                    action = {
                        val action = HomeNavigationDirections.actionGlobalSettingsActivity(
                            args.game,
                            Settings.MenuTag.SECTION_RENDERER
                        )
                        binding.root.findNavController().navigate(action)
                    }
                )
            )
            add(
                SubmenuProperty(
                    R.string.mw_drivers_components,
                    R.string.mw_drivers_components_desc,
                    R.drawable.ic_build,
                    action = {
                        val action = HomeNavigationDirections.actionGlobalSettingsActivity(
                            args.game,
                            Settings.MenuTag.SECTION_DRIVERS_COMPONENTS
                        )
                        binding.root.findNavController().navigate(action)
                    }
                )
            )
            add(
                SubmenuProperty(
                    R.string.device_profile_title,
                    R.string.device_profile_description,
                    R.drawable.ic_graphics,
                    details = { DeviceProfileManager.cardDetails(requireContext(), args.game) },
                    action = { showDeviceProfileDialog() }
                )
            )
            add(
                SubmenuProperty(
                    R.string.mw_gamehub_advanced,
                    R.string.mw_gamehub_advanced_desc,
                    R.drawable.ic_settings,
                    action = {
                        val action = HomeNavigationDirections.actionGlobalSettingsActivity(
                            args.game,
                            Settings.MenuTag.SECTION_ROOT
                        )
                        binding.root.findNavController().navigate(action)
                    },
                    secondaryActions = buildList {
                        val configExists = File(
                            DirectoryInitialization.userDirectory +
                                "/config/custom/" + args.game.settingsName + ".ini"
                        ).exists()

                        add(SubMenuPropertySecondaryAction(
                            isShown = configExists,
                            descriptionId = R.string.import_config,
                            iconId = R.drawable.ic_import,
                            action = { importConfig.launch(arrayOf("text/ini", "application/octet-stream")) }
                        ))
                        add(SubMenuPropertySecondaryAction(
                            isShown = configExists,
                            descriptionId = R.string.export_config,
                            iconId = R.drawable.ic_export,
                            action = { exportConfig.launch(args.game.settingsName + ".ini") }
                        ))
                        add(SubMenuPropertySecondaryAction(
                            isShown = configExists,
                            descriptionId = R.string.share_game_settings,
                            iconId = R.drawable.ic_share,
                            action = {
                                val configFile = File(
                                    DirectoryInitialization.userDirectory +
                                        "/config/custom/" + args.game.settingsName + ".ini"
                                )
                                if (configFile.exists()) shareConfigFile(configFile)
                            }
                        ))
                    }
                )
            )
            if (!args.game.isHomebrew) {
                add(
                    InstallableProperty(
                        R.string.save_data,
                        R.string.save_data_description,
                        R.drawable.ic_save,
                        {
                            MessageDialogFragment.newInstance(
                                requireActivity(),
                                titleId = R.string.import_save_warning,
                                descriptionId = R.string.import_save_warning_description,
                                positiveAction = { homeViewModel.setOpenImportSaves(true) }
                            ).show(parentFragmentManager, MessageDialogFragment.TAG)
                        },
                        if (File(args.game.saveDir).exists()) {
                            { exportSaves.launch(args.game.saveZipName) }
                        } else {
                            null
                        }
                    )
                )

                val saveDirFile = File(args.game.saveDir)
                if (saveDirFile.exists()) {
                    add(
                        SubmenuProperty(
                            R.string.delete_save_data,
                            R.string.delete_save_data_description,
                            R.drawable.ic_delete,
                            action = {
                                MessageDialogFragment.newInstance(
                                    requireActivity(),
                                    titleId = R.string.delete_save_data,
                                    descriptionId = R.string.delete_save_data_warning_description,
                                    positiveButtonTitleId = android.R.string.cancel,
                                    negativeButtonTitleId = android.R.string.ok,
                                    negativeAction = {
                                        File(args.game.saveDir).deleteRecursively()
                                        Toast.makeText(
                                            YuzuApplication.appContext,
                                            R.string.save_data_deleted_successfully,
                                            Toast.LENGTH_SHORT
                                        ).show()
                                        homeViewModel.reloadPropertiesList(true)
                                    }
                                ).show(parentFragmentManager, MessageDialogFragment.TAG)
                            }
                        )
                    )
                }

                val shaderCacheDir = File(
                    DirectoryInitialization.userDirectory +
                        "/cache/shader/" + args.game.settingsName.lowercase()
                )
                if (shaderCacheDir.exists()) {
                    add(
                        SubmenuProperty(
                            R.string.clear_shader_cache,
                            R.string.clear_shader_cache_description,
                            R.drawable.ic_delete,
                            details = {
                                if (shaderCacheDir.exists()) {
                                    val bytes = shaderCacheDir.walkTopDown().filter { it.isFile }
                                        .map { it.length() }.sum()
                                    MemoryUtil.bytesToSizeUnit(bytes.toFloat())
                                } else {
                                    MemoryUtil.bytesToSizeUnit(0f)
                                }
                            },
                            action = {
                                MessageDialogFragment.newInstance(
                                    requireActivity(),
                                    titleId = R.string.clear_shader_cache,
                                    descriptionId = R.string.clear_shader_cache_warning_description,
                                    positiveAction = {
                                        shaderCacheDir.deleteRecursively()
                                        Toast.makeText(
                                            YuzuApplication.appContext,
                                            R.string.cleared_shaders_successfully,
                                            Toast.LENGTH_SHORT
                                        ).show()
                                        homeViewModel.reloadPropertiesList(true)
                                    }
                                ).show(parentFragmentManager, MessageDialogFragment.TAG)
                            }
                        )
                    )
                }
                if (NativeLibrary.playTimeManagerGetPlayTime(args.game.programId) > 0) {
                    add(
                        SubmenuProperty(
                            R.string.reset_playtime,
                            R.string.reset_playtime_description,
                            R.drawable.ic_delete,
                            action = {
                                MessageDialogFragment.newInstance(
                                    requireActivity(),
                                    titleId = R.string.reset_playtime,
                                    descriptionId = R.string.reset_playtime_warning_description,
                                    positiveAction = {
                                        NativeLibrary.playTimeManagerResetProgramPlayTime(args.game.programId)
                                        Toast.makeText(
                                            YuzuApplication.appContext,
                                            R.string.playtime_reset_successfully,
                                            Toast.LENGTH_SHORT
                                        ).show()
                                        getPlayTime()
                                        homeViewModel.reloadPropertiesList(true)
                                    }
                                ).show(parentFragmentManager, MessageDialogFragment.TAG)
                            }
                        )
                    )
                }
            }
        }
        binding.listProperties.apply {
            layoutManager = LinearLayoutManager(requireContext())
            adapter = GamePropertiesAdapter(viewLifecycleOwner, properties)
            isNestedScrollingEnabled = false
        }
    }

    private fun isFavorite(): Boolean =
        PreferenceManager.getDefaultSharedPreferences(requireContext())
            .getBoolean(args.game.keyFavorite, false)

    private fun toggleFavorite() {
        val preferences = PreferenceManager.getDefaultSharedPreferences(requireContext())
        preferences.edit {
            putBoolean(args.game.keyFavorite, !preferences.getBoolean(args.game.keyFavorite, false))
        }
        gamesViewModel.setShouldSwapData(true)
        refreshFavoriteAction()
    }

    override fun onResume() {
        super.onResume()
        refreshOverview()
        refreshFavoriteAction()
        reloadList()
    }

    private fun setInsets() =
        ViewCompat.setOnApplyWindowInsetsListener(binding.root) { _: View, windowInsets: WindowInsetsCompat ->
            val barInsets = windowInsets.getInsets(WindowInsetsCompat.Type.systemBars())
            val cutoutInsets = windowInsets.getInsets(WindowInsetsCompat.Type.displayCutout())
            binding.layoutAll.updatePadding(
                left = barInsets.left + cutoutInsets.left,
                top = barInsets.top,
                right = barInsets.right + cutoutInsets.right,
                bottom = barInsets.bottom + (24 * resources.displayMetrics.density).toInt()
            )
            windowInsets
        }

    private val importCoverArtwork =
        registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
            if (uri != null) importArtwork(uri, "cover")
        }

    private val importHeroArtwork =
        registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
            if (uri != null) importArtwork(uri, "hero")
        }

    private val importLogoArtwork =
        registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
            if (uri != null) importArtwork(uri, "logo")
        }

    private val importSaves =
        registerForActivityResult(ActivityResultContracts.OpenDocument()) { result ->
            if (result == null) {
                return@registerForActivityResult
            }

            val savesFolder = File(args.game.saveDir)
            val cacheSaveDir = File("${requireContext().cacheDir.path}/saves/")
            cacheSaveDir.mkdir()

            ProgressDialogFragment.newInstance(
                requireActivity(),
                R.string.save_files_importing,
                false
            ) { _, _ ->
                try {
                    FileUtil.unzipToInternalStorage(result.toString(), cacheSaveDir)
                    val files = cacheSaveDir.listFiles()
                    var savesFolderFile: File? = null
                    if (files != null) {
                        val savesFolderName = args.game.programIdHex
                        for (file in files) {
                            if (file.isDirectory && file.name == savesFolderName) {
                                savesFolderFile = file
                                break
                            }
                        }
                    }

                    if (savesFolderFile != null) {
                        savesFolder.deleteRecursively()
                        savesFolder.mkdir()
                        savesFolderFile.copyRecursively(savesFolder)
                        savesFolderFile.deleteRecursively()
                    }

                    withContext(Dispatchers.Main) {
                        if (savesFolderFile == null) {
                            MessageDialogFragment.newInstance(
                                requireActivity(),
                                titleId = R.string.save_file_invalid_zip_structure,
                                descriptionId = R.string.save_file_invalid_zip_structure_description
                            ).show(parentFragmentManager, MessageDialogFragment.TAG)
                            return@withContext
                        }
                        Toast.makeText(
                            YuzuApplication.appContext,
                            getString(R.string.save_file_imported_success),
                            Toast.LENGTH_LONG
                        ).show()
                        homeViewModel.reloadPropertiesList(true)
                    }

                    cacheSaveDir.deleteRecursively()
                } catch (e: Exception) {
                    Toast.makeText(
                        YuzuApplication.appContext,
                        getString(R.string.fatal_error),
                        Toast.LENGTH_LONG
                    ).show()
                }
            }.show(parentFragmentManager, ProgressDialogFragment.TAG)
        }

    /**
     * Exports the save file located in the given folder path by creating a zip file and opening a
     * file picker to save.
     */
    private val exportSaves = registerForActivityResult(
        ActivityResultContracts.CreateDocument("application/zip")
    ) { result ->
        if (result == null) {
            return@registerForActivityResult
        }

        ProgressDialogFragment.newInstance(
            requireActivity(),
            R.string.save_files_exporting,
            false
        ) { _, _ ->
            val saveLocation = args.game.saveDir
            val zipResult = FileUtil.zipFromInternalStorage(
                File(saveLocation),
                saveLocation.replaceAfterLast("/", ""),
                BufferedOutputStream(requireContext().contentResolver.openOutputStream(result)),
                compression = false
            )
            return@newInstance when (zipResult) {
                TaskState.Completed -> getString(R.string.export_success)
                TaskState.Cancelled, TaskState.Failed -> getString(R.string.export_failed)
            }
        }.show(parentFragmentManager, ProgressDialogFragment.TAG)
    }

    /**
     * Imports an ini file from external storage to internal app directory and override per-game config
     */
    private val importConfig = registerForActivityResult(
        ActivityResultContracts.OpenDocument()
    ) { result ->
        if (result == null) {
            return@registerForActivityResult
        }

        val iniResult = FileUtil.copyUriToInternalStorage(
            sourceUri = result,
            destinationParentPath =
                DirectoryInitialization.userDirectory + "/config/custom/",
            destinationFilename = args.game.settingsName + ".ini"
        )
        if (iniResult?.exists() == true) {
            Toast.makeText(
                requireContext(),
                getString(R.string.import_success),
                Toast.LENGTH_SHORT
            ).show()
            homeViewModel.reloadPropertiesList(true)
        } else {
            Toast.makeText(
                requireContext(),
                getString(R.string.import_failed),
                Toast.LENGTH_SHORT
            ).show()
        }
    }

    /**
     * Exports game's config ini to the specified location in external storage
     */
    private val exportConfig = registerForActivityResult(
        ActivityResultContracts.CreateDocument("text/ini")
    ) { result ->
        if (result == null) {
            return@registerForActivityResult
        }

        ProgressDialogFragment.newInstance(
            requireActivity(),
            R.string.save_files_exporting,
            false
        ) { _, _ ->
            val configLocation = DirectoryInitialization.userDirectory +
                "/config/custom/" + args.game.settingsName + ".ini"

            val iniResult = FileUtil.copyToExternalStorage(
                sourcePath = configLocation,
                destUri = result
            )
            return@newInstance when (iniResult) {
                TaskState.Completed -> getString(R.string.export_success)
                TaskState.Cancelled, TaskState.Failed -> getString(R.string.export_failed)
            }
        }.show(parentFragmentManager, ProgressDialogFragment.TAG)
    }

    private fun shareConfigFile(configFile: File) {
        val file = DocumentFile.fromSingleUri(
            requireContext(),
            DocumentsContract.buildDocumentUri(
                DocumentProvider.AUTHORITY,
                "${DocumentProvider.ROOT_ID}/${configFile}"
            )
        )!!

        val intent = Intent(Intent.ACTION_SEND)
            .setDataAndType(file.uri, FileUtil.TEXT_PLAIN)
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        if (file.exists()) {
            intent.putExtra(Intent.EXTRA_STREAM, file.uri)
            startActivity(Intent.createChooser(intent, getText(R.string.share_game_settings)))
        } else {
            Toast.makeText(
                requireContext(),
                getText(R.string.share_config_failed),
                Toast.LENGTH_SHORT
            ).show()
        }
    }
}
