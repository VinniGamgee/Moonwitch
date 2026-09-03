from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRAGMENT = ROOT / "src/android/app/src/main/java/org/yuzu/yuzu_emu/fragments/GamePropertiesFragment.kt"
LAUNCH = ROOT / "src/android/app/src/main/java/org/yuzu/yuzu_emu/fragments/LaunchGameDialogFragment.kt"
LAYOUT = ROOT / "src/android/app/src/main/res/layout/fragment_game_properties.xml"
LAYOUT_WIDE = ROOT / "src/android/app/src/main/res/layout-w600dp/fragment_game_properties.xml"
VALUES = ROOT / "src/android/app/src/main/res/values/moonwitch_gamehub_v2.xml"
VALUES_PT = ROOT / "src/android/app/src/main/res/values-pt-rBR/moonwitch_gamehub_v2.xml"
MORE_ICON = ROOT / "src/android/app/src/main/res/drawable/mw_gamehub_v2_more.xml"
CLOCK_ICON = ROOT / "src/android/app/src/main/res/drawable/mw_gamehub_v2_clock.xml"
HISTORY_ICON = ROOT / "src/android/app/src/main/res/drawable/mw_gamehub_v2_history.xml"
STORAGE_ICON = ROOT / "src/android/app/src/main/res/drawable/mw_gamehub_v2_storage.xml"


def must_replace(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Missing expected block: {label}")
    return text.replace(old, new, 1)


fragment = FRAGMENT.read_text()
fragment = must_replace(
    fragment,
    "import android.os.Bundle\n",
    "import android.os.Bundle\nimport android.text.format.DateUtils\n",
    "DateUtils import",
)

old_shortcut = '''        val shortcutManager = requireActivity().getSystemService(ShortcutManager::class.java)
        binding.buttonShortcut.isEnabled = shortcutManager.isRequestPinShortcutSupported
        binding.buttonShortcut.setOnClickListener {
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
'''
fragment = must_replace(
    fragment,
    old_shortcut,
    '''        binding.buttonShortcut.setOnClickListener { showMoreActions() }
''',
    "shortcut button",
)

old_header = '''        binding.developer.text = args.game.developer.ifBlank {
            getString(R.string.mw_gamehub_unknown_developer)
        }

        getPlayTime()
'''
fragment = must_replace(
    fragment,
    old_header,
    '''        binding.developer.text = args.game.developer.ifBlank {
            getString(R.string.mw_gamehub_unknown_developer)
        }
        setupQuickActions()
        refreshOverview()
''',
    "hub header wiring",
)

old_get_playtime = '''    private fun getPlayTime() {
        binding.playtime.text = getString(R.string.mw_gamehub_playtime_value, readablePlayTime())
        binding.playtime.setOnClickListener { showEditPlaytimeDialog() }
    }
'''
new_helpers = '''    private fun getPlayTime() {
        binding.statPlaytimeValue.text = readablePlayTime()
    }

    private fun buildGameMeta(): String {
        val developer = args.game.developer.ifBlank {
            getString(R.string.mw_gamehub_unknown_developer)
        }
        return if (args.game.version.isBlank()) developer
        else getString(R.string.mw_gamehub_v2_meta, developer, args.game.version)
    }

    private fun gameDescription(): String {
        val metadataFile = File(
            DirectoryInitialization.userDirectory +
                "/moonwitch/metadata/" + args.game.settingsName + ".txt"
        )
        val customDescription = runCatching {
            if (metadataFile.isFile) metadataFile.readText().trim() else ""
        }.getOrDefault("")
        if (customDescription.isNotBlank()) return customDescription

        val developer = args.game.developer.ifBlank {
            getString(R.string.mw_gamehub_unknown_developer)
        }
        return getString(
            R.string.mw_gamehub_v2_description_fallback,
            args.game.title,
            developer
        )
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
        binding.actionSettings.setOnClickListener { openRootSettings() }
        binding.actionContent.setOnClickListener { openContent() }
        binding.actionMore.setOnClickListener { showMoreActions() }
        binding.statPlaytimeRow.setOnClickListener { showEditPlaytimeDialog() }
        binding.actionContent.visibility = if (args.game.isHomebrew) View.GONE else View.VISIBLE
        refreshFavoriteAction()
    }

    private fun refreshFavoriteAction() {
        binding.actionFavoriteIcon.setImageResource(
            if (isFavorite()) R.drawable.ic_mw_star_filled else R.drawable.ic_mw_star
        )
    }

    private fun openRootSettings() {
        val action = HomeNavigationDirections.actionGlobalSettingsActivity(
            args.game,
            Settings.MenuTag.SECTION_ROOT
        )
        binding.root.findNavController().navigate(action)
    }

    private fun openContent() {
        if (args.game.isHomebrew) return
        val action = HomeNavigationDirections.actionGlobalSettingsSubscreenActivity(
            SettingsSubscreen.ADDONS,
            args.game
        )
        binding.root.findNavController().navigate(action)
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
        val actions = mutableListOf<Pair<String, () -> Unit>>()
        actions += getString(R.string.device_profile_title) to { showDeviceProfileDialog() }
        actions += getString(R.string.mw_gamehub_info) to {
            val action = HomeNavigationDirections.actionGlobalSettingsSubscreenActivity(
                SettingsSubscreen.GAME_INFO,
                args.game
            )
            binding.root.findNavController().navigate(action)
        }
        val shortcutManager = requireActivity().getSystemService(ShortcutManager::class.java)
        if (shortcutManager.isRequestPinShortcutSupported) {
            actions += getString(R.string.mw_gamehub_v2_create_shortcut) to { requestPinnedShortcut() }
        }
        actions += getString(R.string.mw_gamehub_v2_edit_playtime) to { showEditPlaytimeDialog() }
        actions += getString(R.string.mw_gamehub_advanced) to { openRootSettings() }

        com.google.android.material.dialog.MaterialAlertDialogBuilder(requireContext())
            .setTitle(args.game.title)
            .setItems(actions.map { it.first }.toTypedArray()) { _, which ->
                actions[which].second.invoke()
            }
            .setNegativeButton(android.R.string.cancel, null)
            .show()
    }
'''
fragment = must_replace(fragment, old_get_playtime, new_helpers, "playtime helpers")

content_block = '''            if (!args.game.isHomebrew) {
                add(
                    SubmenuProperty(
                        R.string.mw_gamehub_content,
                        R.string.mw_gamehub_content_desc,
                        R.drawable.ic_edit,
                        action = {
                            val action = HomeNavigationDirections.actionGlobalSettingsSubscreenActivity(
                                SettingsSubscreen.ADDONS,
                                args.game
                            )
                            binding.root.findNavController().navigate(action)
                        }
                    )
                )
            }
'''
fragment = must_replace(fragment, content_block, "", "duplicate Content card")

statistics_block = '''            add(
                SubmenuProperty(
                    R.string.mw_gamehub_statistics,
                    R.string.mw_gamehub_statistics_desc,
                    R.drawable.ic_info_outline,
                    details = { readablePlayTime() },
                    action = { showEditPlaytimeDialog() }
                )
            )
'''
fragment = must_replace(fragment, statistics_block, "", "duplicate Statistics card")

info_block = '''            add(
                SubmenuProperty(
                    R.string.mw_gamehub_info,
                    R.string.mw_gamehub_info_desc,
                    R.drawable.ic_info_outline,
                    action = {
                        val action = HomeNavigationDirections.actionGlobalSettingsSubscreenActivity(
                            SettingsSubscreen.GAME_INFO,
                            args.game
                        )
                        binding.root.findNavController().navigate(action)
                    }
                )
            )
'''
fragment = must_replace(fragment, info_block, "", "duplicate info card")

favorite_block = '''            val favorite = isFavorite()
            add(
                SubmenuProperty(
                    R.string.mw_ui_favorite,
                    R.string.mw_favorite_game_desc,
                    if (favorite) R.drawable.ic_mw_star_filled else R.drawable.ic_mw_star,
                    details = {
                        getString(
                            if (isFavorite()) R.string.mw_favorite_enabled
                            else R.string.mw_favorite_disabled
                        )
                    },
                    action = { toggleFavorite() }
                )
            )

'''
fragment = must_replace(fragment, favorite_block, "", "duplicate favorite card")

fragment = must_replace(
    fragment,
    '''        gamesViewModel.setShouldSwapData(true)
        reloadList()
    }

    override fun onResume() {
        super.onResume()
        getPlayTime()
        reloadList()
    }
''',
    '''        gamesViewModel.setShouldSwapData(true)
        refreshFavoriteAction()
    }

    override fun onResume() {
        super.onResume()
        refreshOverview()
        refreshFavoriteAction()
        reloadList()
    }
''',
    "favorite/onResume refresh",
)
FRAGMENT.write_text(fragment)

launch = LAUNCH.read_text()
launch = must_replace(
    launch,
    "import androidx.fragment.app.DialogFragment\n",
    "import androidx.core.content.edit\nimport androidx.fragment.app.DialogFragment\nimport androidx.preference.PreferenceManager\n",
    "launch imports",
)
launch = must_replace(
    launch,
    '''            .setPositiveButton(android.R.string.ok) { _: DialogInterface, _: Int ->
                val action = HomeNavigationDirections
                    .actionGlobalEmulationActivity(game, selectedItem != 0)
                requireParentFragment().findNavController().navigate(action)
            }
''',
    '''            .setPositiveButton(android.R.string.ok) { _: DialogInterface, _: Int ->
                PreferenceManager.getDefaultSharedPreferences(requireContext()).edit {
                    putLong(game.keyLastPlayedTime, System.currentTimeMillis())
                }
                val action = HomeNavigationDirections
                    .actionGlobalEmulationActivity(game, selectedItem != 0)
                requireParentFragment().findNavController().navigate(action)
            }
''',
    "last played tracking",
)
LAUNCH.write_text(launch)

layout = r'''<?xml version="1.0" encoding="utf-8"?>
<FrameLayout xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:app="http://schemas.android.com/apk/res-auto"
    xmlns:tools="http://schemas.android.com/tools"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    android:background="@color/ic_launcher_background">

    <androidx.core.widget.NestedScrollView
        android:id="@+id/list_all"
        android:layout_width="match_parent"
        android:layout_height="match_parent"
        android:clipToPadding="false"
        android:fillViewport="true"
        android:scrollbars="none">

        <LinearLayout
            android:id="@+id/layout_all"
            android:layout_width="match_parent"
            android:layout_height="wrap_content"
            android:orientation="vertical">

            <FrameLayout
                android:layout_width="match_parent"
                android:layout_height="430dp">

                <ImageView
                    android:id="@+id/image_game_backdrop"
                    android:layout_width="match_parent"
                    android:layout_height="match_parent"
                    android:alpha="0.58"
                    android:contentDescription="@null"
                    android:scaleType="centerCrop"
                    tools:src="@drawable/default_icon" />

                <View
                    android:layout_width="match_parent"
                    android:layout_height="match_parent"
                    android:background="@drawable/mw_game_hub_hero_scrim" />

                <LinearLayout
                    android:layout_width="match_parent"
                    android:layout_height="wrap_content"
                    android:layout_gravity="top"
                    android:gravity="center_vertical"
                    android:orientation="horizontal"
                    android:paddingHorizontal="16dp"
                    android:paddingTop="10dp">

                    <com.google.android.material.button.MaterialButton
                        android:id="@+id/button_back"
                        style="?attr/materialIconButtonStyle"
                        android:layout_width="50dp"
                        android:layout_height="50dp"
                        android:backgroundTint="@color/mw_gamehub_v2_circle"
                        android:contentDescription="@null"
                        app:cornerRadius="25dp"
                        app:icon="@drawable/ic_back"
                        app:iconSize="23dp"
                        app:iconTint="@color/moonwitch_text" />

                    <Space
                        android:layout_width="0dp"
                        android:layout_height="1dp"
                        android:layout_weight="1" />

                    <com.google.android.material.button.MaterialButton
                        android:id="@+id/button_shortcut"
                        style="?attr/materialIconButtonStyle"
                        android:layout_width="50dp"
                        android:layout_height="50dp"
                        android:backgroundTint="@color/mw_gamehub_v2_circle"
                        android:contentDescription="@string/mw_gamehub_v2_more"
                        app:cornerRadius="25dp"
                        app:icon="@drawable/mw_gamehub_v2_more"
                        app:iconSize="23dp"
                        app:iconTint="@color/moonwitch_text" />
                </LinearLayout>

                <LinearLayout
                    android:layout_width="match_parent"
                    android:layout_height="wrap_content"
                    android:layout_gravity="bottom"
                    android:gravity="bottom"
                    android:orientation="horizontal"
                    android:paddingHorizontal="20dp"
                    android:paddingBottom="28dp">

                    <com.google.android.material.card.MaterialCardView
                        android:layout_width="118dp"
                        android:layout_height="164dp"
                        app:cardBackgroundColor="@color/moonwitch_panel_high"
                        app:cardCornerRadius="18dp"
                        app:cardElevation="0dp"
                        app:strokeColor="@color/mw_gamehub_v2_accent"
                        app:strokeWidth="1dp">

                        <com.google.android.material.imageview.ShapeableImageView
                            android:id="@+id/image_game_screen"
                            android:layout_width="match_parent"
                            android:layout_height="match_parent"
                            android:padding="3dp"
                            android:scaleType="fitCenter"
                            app:shapeAppearance="@style/ShapeAppearance.Material3.Corner.Medium"
                            tools:src="@drawable/default_icon" />
                    </com.google.android.material.card.MaterialCardView>

                    <LinearLayout
                        android:layout_width="0dp"
                        android:layout_height="wrap_content"
                        android:layout_marginStart="16dp"
                        android:layout_weight="1"
                        android:orientation="vertical"
                        android:paddingBottom="4dp">

                        <TextView
                            android:id="@+id/title"
                            android:layout_width="match_parent"
                            android:layout_height="wrap_content"
                            android:ellipsize="end"
                            android:fontFamily="sans-serif-medium"
                            android:maxLines="3"
                            android:textColor="@color/moonwitch_text"
                            android:textSize="23sp"
                            tools:text="The Legend of Zelda: Tears of the Kingdom" />

                        <TextView
                            android:id="@+id/developer"
                            android:layout_width="match_parent"
                            android:layout_height="wrap_content"
                            android:layout_marginTop="6dp"
                            android:ellipsize="end"
                            android:maxLines="1"
                            android:textColor="@color/moonwitch_text_muted"
                            android:textSize="11sp"
                            tools:text="Nintendo" />

                        <TextView
                            android:id="@+id/game_meta"
                            android:layout_width="match_parent"
                            android:layout_height="wrap_content"
                            android:layout_marginTop="3dp"
                            android:ellipsize="end"
                            android:maxLines="1"
                            android:textColor="@color/moonwitch_text_muted"
                            android:textSize="10sp"
                            tools:text="Nintendo • 1.4.3" />

                        <TextView
                            android:layout_width="wrap_content"
                            android:layout_height="wrap_content"
                            android:layout_marginTop="12dp"
                            android:background="@drawable/mw_game_hub_stat_pill"
                            android:fontFamily="sans-serif-medium"
                            android:paddingHorizontal="10dp"
                            android:paddingVertical="5dp"
                            android:text="@string/mw_gamehub_v2_library_chip"
                            android:textColor="@color/mw_gamehub_v2_accent"
                            android:textSize="9sp" />
                    </LinearLayout>
                </LinearLayout>
            </FrameLayout>

            <com.google.android.material.button.MaterialButton
                android:id="@+id/button_start"
                android:layout_width="match_parent"
                android:layout_height="60dp"
                android:layout_marginHorizontal="20dp"
                android:layout_marginTop="8dp"
                android:fontFamily="sans-serif-medium"
                android:text="@string/mw_gamehub_v2_play"
                android:textColor="@color/moonwitch_text"
                android:textSize="15sp"
                app:backgroundTint="@color/mw_gamehub_v2_play"
                app:cornerRadius="18dp"
                app:icon="@drawable/ic_play"
                app:iconGravity="textStart"
                app:iconTint="@color/moonwitch_text" />

            <com.google.android.material.card.MaterialCardView
                android:layout_width="match_parent"
                android:layout_height="wrap_content"
                android:layout_marginHorizontal="20dp"
                android:layout_marginTop="12dp"
                app:cardBackgroundColor="@color/mw_gamehub_v2_panel"
                app:cardCornerRadius="22dp"
                app:cardElevation="0dp"
                app:strokeColor="@color/moonwitch_border_soft"
                app:strokeWidth="1dp">

                <LinearLayout
                    android:layout_width="match_parent"
                    android:layout_height="96dp"
                    android:gravity="center"
                    android:orientation="horizontal">

                    <LinearLayout
                        android:id="@+id/action_favorite"
                        android:layout_width="0dp"
                        android:layout_height="match_parent"
                        android:layout_weight="1"
                        android:clickable="true"
                        android:focusable="true"
                        android:gravity="center"
                        android:orientation="vertical"
                        android:padding="8dp">
                        <ImageView
                            android:id="@+id/action_favorite_icon"
                            android:layout_width="28dp"
                            android:layout_height="28dp"
                            android:contentDescription="@null"
                            android:src="@drawable/ic_mw_star"
                            app:tint="@color/moonwitch_text" />
                        <TextView
                            android:layout_width="wrap_content"
                            android:layout_height="wrap_content"
                            android:layout_marginTop="8dp"
                            android:text="@string/mw_gamehub_v2_favorite"
                            android:textColor="@color/moonwitch_text_muted"
                            android:textSize="10sp" />
                    </LinearLayout>

                    <LinearLayout
                        android:id="@+id/action_settings"
                        android:layout_width="0dp"
                        android:layout_height="match_parent"
                        android:layout_weight="1"
                        android:clickable="true"
                        android:focusable="true"
                        android:gravity="center"
                        android:orientation="vertical"
                        android:padding="8dp">
                        <ImageView
                            android:layout_width="28dp"
                            android:layout_height="28dp"
                            android:contentDescription="@null"
                            android:src="@drawable/ic_settings"
                            app:tint="@color/moonwitch_text" />
                        <TextView
                            android:layout_width="wrap_content"
                            android:layout_height="wrap_content"
                            android:layout_marginTop="8dp"
                            android:text="@string/mw_gamehub_v2_settings"
                            android:textColor="@color/moonwitch_text_muted"
                            android:textSize="10sp" />
                    </LinearLayout>

                    <LinearLayout
                        android:id="@+id/action_content"
                        android:layout_width="0dp"
                        android:layout_height="match_parent"
                        android:layout_weight="1"
                        android:clickable="true"
                        android:focusable="true"
                        android:gravity="center"
                        android:orientation="vertical"
                        android:padding="8dp">
                        <ImageView
                            android:layout_width="28dp"
                            android:layout_height="28dp"
                            android:contentDescription="@null"
                            android:src="@drawable/ic_edit"
                            app:tint="@color/moonwitch_text" />
                        <TextView
                            android:layout_width="wrap_content"
                            android:layout_height="wrap_content"
                            android:layout_marginTop="8dp"
                            android:text="@string/mw_gamehub_v2_content"
                            android:textColor="@color/moonwitch_text_muted"
                            android:textSize="10sp" />
                    </LinearLayout>

                    <LinearLayout
                        android:id="@+id/action_more"
                        android:layout_width="0dp"
                        android:layout_height="match_parent"
                        android:layout_weight="1"
                        android:clickable="true"
                        android:focusable="true"
                        android:gravity="center"
                        android:orientation="vertical"
                        android:padding="8dp">
                        <ImageView
                            android:layout_width="28dp"
                            android:layout_height="28dp"
                            android:contentDescription="@null"
                            android:src="@drawable/mw_gamehub_v2_more"
                            app:tint="@color/moonwitch_text" />
                        <TextView
                            android:layout_width="wrap_content"
                            android:layout_height="wrap_content"
                            android:layout_marginTop="8dp"
                            android:text="@string/mw_gamehub_v2_more"
                            android:textColor="@color/moonwitch_text_muted"
                            android:textSize="10sp" />
                    </LinearLayout>
                </LinearLayout>
            </com.google.android.material.card.MaterialCardView>

            <com.google.android.material.card.MaterialCardView
                android:layout_width="match_parent"
                android:layout_height="wrap_content"
                android:layout_marginHorizontal="20dp"
                android:layout_marginTop="16dp"
                app:cardBackgroundColor="@color/mw_gamehub_v2_panel"
                app:cardCornerRadius="22dp"
                app:cardElevation="0dp"
                app:strokeColor="@color/moonwitch_border_soft"
                app:strokeWidth="1dp">

                <LinearLayout
                    android:layout_width="match_parent"
                    android:layout_height="wrap_content"
                    android:orientation="vertical"
                    android:padding="18dp">

                    <TextView
                        android:layout_width="match_parent"
                        android:layout_height="wrap_content"
                        android:fontFamily="sans-serif-medium"
                        android:text="@string/mw_gamehub_v2_description"
                        android:textColor="@color/moonwitch_text"
                        android:textSize="15sp" />

                    <TextView
                        android:id="@+id/game_description"
                        android:layout_width="match_parent"
                        android:layout_height="wrap_content"
                        android:layout_marginTop="10dp"
                        android:lineSpacingExtra="3dp"
                        android:textColor="@color/moonwitch_text_muted"
                        android:textSize="12sp"
                        tools:text="Explore Hyrule and manage this title with Moonwitch." />

                    <View android:layout_width="match_parent" android:layout_height="1dp" android:layout_marginTop="18dp" android:background="@color/moonwitch_border_soft" />

                    <LinearLayout
                        android:id="@+id/stat_playtime_row"
                        android:layout_width="match_parent"
                        android:layout_height="56dp"
                        android:clickable="true"
                        android:focusable="true"
                        android:gravity="center_vertical"
                        android:orientation="horizontal">
                        <ImageView android:layout_width="22dp" android:layout_height="22dp" android:contentDescription="@null" android:src="@drawable/mw_gamehub_v2_clock" app:tint="@color/moonwitch_text" />
                        <TextView android:layout_width="0dp" android:layout_height="wrap_content" android:layout_marginStart="12dp" android:layout_weight="1" android:text="@string/mw_gamehub_v2_playtime" android:textColor="@color/moonwitch_text" android:textSize="12sp" />
                        <TextView android:id="@+id/stat_playtime_value" android:layout_width="wrap_content" android:layout_height="wrap_content" android:textColor="@color/moonwitch_text_muted" android:textSize="12sp" tools:text="125h 30m" />
                    </LinearLayout>

                    <View android:layout_width="match_parent" android:layout_height="1dp" android:background="@color/moonwitch_border_soft" />

                    <LinearLayout android:layout_width="match_parent" android:layout_height="56dp" android:gravity="center_vertical" android:orientation="horizontal">
                        <ImageView android:layout_width="22dp" android:layout_height="22dp" android:contentDescription="@null" android:src="@drawable/mw_gamehub_v2_history" app:tint="@color/moonwitch_text" />
                        <TextView android:layout_width="0dp" android:layout_height="wrap_content" android:layout_marginStart="12dp" android:layout_weight="1" android:text="@string/mw_gamehub_v2_last_played" android:textColor="@color/moonwitch_text" android:textSize="12sp" />
                        <TextView android:id="@+id/stat_last_played_value" android:layout_width="wrap_content" android:layout_height="wrap_content" android:textColor="@color/moonwitch_text_muted" android:textSize="12sp" tools:text="Hoje" />
                    </LinearLayout>

                    <View android:layout_width="match_parent" android:layout_height="1dp" android:background="@color/moonwitch_border_soft" />

                    <LinearLayout android:layout_width="match_parent" android:layout_height="56dp" android:gravity="center_vertical" android:orientation="horizontal">
                        <ImageView android:layout_width="22dp" android:layout_height="22dp" android:contentDescription="@null" android:src="@drawable/mw_gamehub_v2_storage" app:tint="@color/moonwitch_text" />
                        <TextView android:layout_width="0dp" android:layout_height="wrap_content" android:layout_marginStart="12dp" android:layout_weight="1" android:text="@string/mw_gamehub_v2_size" android:textColor="@color/moonwitch_text" android:textSize="12sp" />
                        <TextView android:id="@+id/stat_size_value" android:layout_width="wrap_content" android:layout_height="wrap_content" android:textColor="@color/moonwitch_text_muted" android:textSize="12sp" tools:text="16.2 GB" />
                    </LinearLayout>
                </LinearLayout>
            </com.google.android.material.card.MaterialCardView>

            <com.google.android.material.card.MaterialCardView
                android:layout_width="match_parent"
                android:layout_height="wrap_content"
                android:layout_marginHorizontal="20dp"
                android:layout_marginTop="14dp"
                app:cardBackgroundColor="@color/mw_gamehub_v2_panel"
                app:cardCornerRadius="22dp"
                app:cardElevation="0dp"
                app:strokeColor="@color/moonwitch_border_soft"
                app:strokeWidth="1dp">
                <LinearLayout android:layout_width="match_parent" android:layout_height="wrap_content" android:orientation="vertical" android:padding="18dp">
                    <TextView android:layout_width="match_parent" android:layout_height="wrap_content" android:fontFamily="sans-serif-medium" android:text="@string/mw_gamehub_v2_technical" android:textColor="@color/moonwitch_text" android:textSize="15sp" />
                    <LinearLayout android:layout_width="match_parent" android:layout_height="48dp" android:layout_marginTop="6dp" android:gravity="center_vertical" android:orientation="horizontal">
                        <TextView android:layout_width="0dp" android:layout_height="wrap_content" android:layout_weight="1" android:text="@string/mw_gamehub_v2_version" android:textColor="@color/moonwitch_text_muted" android:textSize="11sp" />
                        <TextView android:id="@+id/stat_version_value" android:layout_width="wrap_content" android:layout_height="wrap_content" android:textColor="@color/moonwitch_text" android:textSize="11sp" tools:text="1.4.3" />
                    </LinearLayout>
                    <View android:layout_width="match_parent" android:layout_height="1dp" android:background="@color/moonwitch_border_soft" />
                    <LinearLayout android:layout_width="match_parent" android:layout_height="48dp" android:gravity="center_vertical" android:orientation="horizontal">
                        <TextView android:layout_width="0dp" android:layout_height="wrap_content" android:layout_weight="1" android:text="@string/mw_gamehub_v2_title_id" android:textColor="@color/moonwitch_text_muted" android:textSize="11sp" />
                        <TextView android:id="@+id/stat_title_id_value" android:layout_width="wrap_content" android:layout_height="wrap_content" android:fontFamily="monospace" android:textColor="@color/moonwitch_text" android:textSize="10sp" tools:text="0100F2C0115B6000" />
                    </LinearLayout>
                </LinearLayout>
            </com.google.android.material.card.MaterialCardView>

            <TextView
                android:layout_width="match_parent"
                android:layout_height="wrap_content"
                android:layout_marginHorizontal="22dp"
                android:layout_marginTop="22dp"
                android:layout_marginBottom="7dp"
                android:fontFamily="sans-serif-medium"
                android:letterSpacing="0.08"
                android:text="@string/mw_gamehub_v2_game_settings"
                android:textAllCaps="true"
                android:textColor="@color/moonwitch_text_muted"
                android:textSize="10sp" />

            <androidx.recyclerview.widget.RecyclerView
                android:id="@+id/list_properties"
                android:layout_width="match_parent"
                android:layout_height="wrap_content"
                android:clipToPadding="false"
                android:nestedScrollingEnabled="false"
                android:paddingBottom="24dp" />
        </LinearLayout>
    </androidx.core.widget.NestedScrollView>
</FrameLayout>
'''
LAYOUT.write_text(layout)
LAYOUT_WIDE.write_text(layout)

VALUES.write_text(r'''<?xml version="1.0" encoding="utf-8"?>
<resources>
    <color name="mw_gamehub_v2_play">#7C35E8</color>
    <color name="mw_gamehub_v2_accent">#B98CFF</color>
    <color name="mw_gamehub_v2_panel">#E80B101C</color>
    <color name="mw_gamehub_v2_circle">#B01A2230</color>
    <string name="mw_gamehub_v2_play">Play</string>
    <string name="mw_gamehub_v2_library_chip">IN LIBRARY</string>
    <string name="mw_gamehub_v2_favorite">Favorite</string>
    <string name="mw_gamehub_v2_settings">Settings</string>
    <string name="mw_gamehub_v2_content">Content</string>
    <string name="mw_gamehub_v2_more">More</string>
    <string name="mw_gamehub_v2_description">Description</string>
    <string name="mw_gamehub_v2_playtime">Play time</string>
    <string name="mw_gamehub_v2_last_played">Last played</string>
    <string name="mw_gamehub_v2_size">Base file size</string>
    <string name="mw_gamehub_v2_technical">Technical information</string>
    <string name="mw_gamehub_v2_version">Version</string>
    <string name="mw_gamehub_v2_title_id">Title ID</string>
    <string name="mw_gamehub_v2_game_settings">Per-game controls</string>
    <string name="mw_gamehub_v2_meta">%1$s • %2$s</string>
    <string name="mw_gamehub_v2_description_fallback">%1$s is a Nintendo Switch title published by %2$s. Moonwitch does not have an external synopsis for this title yet; real activity and technical metadata are shown below.</string>
    <string name="mw_gamehub_v2_never">Never</string>
    <string name="mw_gamehub_v2_unknown_value">—</string>
    <string name="mw_gamehub_v2_base_version">Base</string>
    <string name="mw_gamehub_v2_create_shortcut">Create home screen shortcut</string>
    <string name="mw_gamehub_v2_edit_playtime">Edit play time</string>
</resources>
''')
VALUES_PT.write_text(r'''<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="mw_gamehub_v2_play">Jogar</string>
    <string name="mw_gamehub_v2_library_chip">NA BIBLIOTECA</string>
    <string name="mw_gamehub_v2_favorite">Favorito</string>
    <string name="mw_gamehub_v2_settings">Configurações</string>
    <string name="mw_gamehub_v2_content">Conteúdo</string>
    <string name="mw_gamehub_v2_more">Mais</string>
    <string name="mw_gamehub_v2_description">Descrição</string>
    <string name="mw_gamehub_v2_playtime">Tempo de jogo</string>
    <string name="mw_gamehub_v2_last_played">Última vez jogado</string>
    <string name="mw_gamehub_v2_size">Tamanho do arquivo base</string>
    <string name="mw_gamehub_v2_technical">Informações técnicas</string>
    <string name="mw_gamehub_v2_version">Versão</string>
    <string name="mw_gamehub_v2_title_id">Title ID</string>
    <string name="mw_gamehub_v2_game_settings">Ajustes por jogo</string>
    <string name="mw_gamehub_v2_meta">%1$s • %2$s</string>
    <string name="mw_gamehub_v2_description_fallback">%1$s é um título de Nintendo Switch publicado por %2$s. O Moonwitch ainda não possui uma sinopse externa para este título; abaixo ficam atividade real e metadados técnicos do jogo.</string>
    <string name="mw_gamehub_v2_never">Nunca</string>
    <string name="mw_gamehub_v2_unknown_value">—</string>
    <string name="mw_gamehub_v2_base_version">Base</string>
    <string name="mw_gamehub_v2_create_shortcut">Criar atalho na tela inicial</string>
    <string name="mw_gamehub_v2_edit_playtime">Editar tempo de jogo</string>
</resources>
''')

MORE_ICON.write_text(r'''<vector xmlns:android="http://schemas.android.com/apk/res/android" android:width="24dp" android:height="24dp" android:viewportWidth="24" android:viewportHeight="24"><path android:fillColor="#FFFFFFFF" android:pathData="M5,10a2,2 0,1 0,0 4a2,2 0,0 0,0 -4M12,10a2,2 0,1 0,0 4a2,2 0,0 0,0 -4M19,10a2,2 0,1 0,0 4a2,2 0,0 0,0 -4"/></vector>''')
CLOCK_ICON.write_text(r'''<vector xmlns:android="http://schemas.android.com/apk/res/android" android:width="24dp" android:height="24dp" android:viewportWidth="24" android:viewportHeight="24"><path android:fillColor="#FFFFFFFF" android:pathData="M12,2A10,10 0,1 0,12 22A10,10 0,0 0,12 2M12,4A8,8 0,1 1,12 20A8,8 0,0 1,12 4M11,6L13,6L13,11.6L16.8,13.8L15.8,15.5L11,12.7Z"/></vector>''')
HISTORY_ICON.write_text(r'''<vector xmlns:android="http://schemas.android.com/apk/res/android" android:width="24dp" android:height="24dp" android:viewportWidth="24" android:viewportHeight="24"><path android:fillColor="#FFFFFFFF" android:pathData="M13,3A9,9 0,0 0,4.2 10L2,10L5.5,13.5L9,10L6.2,10A7,7 0,1 1,7.1 16.4L5.7,17.8A9,9 0,1 0,13 3M12,7L14,7L14,12.2L17.2,14.1L16.2,15.8L12,13.3Z"/></vector>''')
STORAGE_ICON.write_text(r'''<vector xmlns:android="http://schemas.android.com/apk/res/android" android:width="24dp" android:height="24dp" android:viewportWidth="24" android:viewportHeight="24"><path android:fillColor="#FFFFFFFF" android:pathData="M4,4L20,4A2,2 0,0 1,22 6L22,18A2,2 0,0 1,20 20L4,20A2,2 0,0 1,2 18L2,6A2,2 0,0 1,4 4M4,6L4,18L20,18L20,6ZM7,8L17,8L17,10L7,10ZM7,12L17,12L17,14L7,14Z"/></vector>''')

print("Moonwitch Game Hub V2 applied")
