from pathlib import Path

ROOT = Path('src/android/app/src/main')


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'{label}: expected exactly one match, found {count}')
    return text.replace(old, new, 1)


# 1) Library: selecting a game opens the Moonwitch Game Hub instead of launching immediately.
p = ROOT / 'java/org/yuzu/yuzu_emu/adapters/GameAdapter.kt'
s = p.read_text()
start = s.index('        fun onClick(game: Game) {')
end = s.index('        fun onLongClick(game: Game): Boolean {', start)
new_click = '''        fun onClick(game: Game) {
            val gameExists = DocumentFile.fromSingleUri(
                YuzuApplication.appContext,
                game.path.toUri()
            )?.exists() == true

            if (!gameExists) {
                Toast.makeText(
                    YuzuApplication.appContext,
                    R.string.loader_error_file_not_found,
                    Toast.LENGTH_LONG
                ).show()

                ViewModelProvider(activity)[GamesViewModel::class.java].reloadGames(true)
                return
            }

            val action = HomeNavigationDirections.actionGlobalPerGamePropertiesFragment(game)
            binding.root.findNavController().navigate(action)
        }

'''
s = s[:start] + new_click + s[end:]
p.write_text(s)


# 2) Game Hub controller: hero data, real statistics, canonical semantic sections.
p = ROOT / 'java/org/yuzu/yuzu_emu/fragments/GamePropertiesFragment.kt'
s = p.read_text()
s = s.replace('import androidx.recyclerview.widget.StaggeredGridLayoutManager\n', 'import androidx.recyclerview.widget.LinearLayoutManager\n')
s = s.replace('import org.yuzu.yuzu_emu.model.DriverViewModel\n', '')
s = s.replace('import org.yuzu.yuzu_emu.utils.GpuDriverHelper\n', '')
s = s.replace('import org.yuzu.yuzu_emu.utils.ViewUtils.updateMargins\n', '')
s = s.replace('    private val driverViewModel: DriverViewModel by activityViewModels()\n', '')

s = replace_once(
    s,
    '''        GameIconUtils.loadGameIcon(args.game, binding.imageGameScreen)
        binding.title.text = args.game.title
        binding.title.marquee()
''',
    '''        GameIconUtils.loadGameIcon(args.game, binding.imageGameScreen)
        GameIconUtils.loadGameIcon(args.game, binding.imageGameBackdrop)
        binding.title.text = args.game.title
        binding.title.marquee()
        binding.developer.text = args.game.developer.ifBlank {
            getString(R.string.mw_gamehub_unknown_developer)
        }
''',
    'game hub hero binding'
)

get_play_start = s.index('    private fun getPlayTime() {')
get_play_end = s.index('    private fun showEditPlaytimeDialog() {', get_play_start)
play_block = '''    private fun readablePlayTime(): String {
        val playTimeSeconds = NativeLibrary.playTimeManagerGetPlayTime(args.game.programId)
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
        binding.playtime.text = getString(R.string.mw_gamehub_playtime_value, readablePlayTime())
        binding.playtime.setOnClickListener { showEditPlaytimeDialog() }
    }

'''
s = s[:get_play_start] + play_block + s[get_play_end:]

reload_anchor = s.index('    private fun reloadList() {')
prefix_start = s.index('        driverViewModel.updateDriverNameForGame(args.game)\n', reload_anchor)
save_marker = '''            if (!args.game.isHomebrew) {
                add(
                    InstallableProperty(
                        R.string.save_data,'''
prefix_end = s.index(save_marker, prefix_start)
new_prefix = '''        val properties = mutableListOf<GameProperty>().apply {
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
            if (!args.game.isHomebrew) {
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
            add(
                SubmenuProperty(
                    R.string.mw_gamehub_statistics,
                    R.string.mw_gamehub_statistics_desc,
                    R.drawable.ic_info_outline,
                    details = { readablePlayTime() },
                    action = { showEditPlaytimeDialog() }
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
            add(
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
            val favorite = isFavorite()
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
s = s[:prefix_start] + new_prefix + s[prefix_end:]

old_manager = '''        binding.listProperties.apply {
            val spanCount = resources.getInteger(R.integer.grid_columns)
            val staggered = StaggeredGridLayoutManager(
                spanCount,
                StaggeredGridLayoutManager.VERTICAL
            ).apply {
                gapStrategy = StaggeredGridLayoutManager.GAP_HANDLING_MOVE_ITEMS_BETWEEN_SPANS
            }
            layoutManager = staggered
            adapter = GamePropertiesAdapter(viewLifecycleOwner, properties)
        }
'''
new_manager = '''        binding.listProperties.apply {
            layoutManager = LinearLayoutManager(requireContext())
            adapter = GamePropertiesAdapter(viewLifecycleOwner, properties)
            isNestedScrollingEnabled = false
        }
'''
s = replace_once(s, old_manager, new_manager, 'game hub list layout manager')

s = s.replace('''        driverViewModel.updateDriverNameForGame(args.game)
        getPlayTime()
''', '''        getPlayTime()
''')

insets_start = s.index('    private fun setInsets() =')
insets_end = s.index('    private val importSaves =', insets_start)
new_insets = '''    private fun setInsets() =
        ViewCompat.setOnApplyWindowInsetsListener(binding.root) { _: View, windowInsets: WindowInsetsCompat ->
            val barInsets = windowInsets.getInsets(WindowInsetsCompat.Type.systemBars())
            val cutoutInsets = windowInsets.getInsets(WindowInsetsCompat.Type.displayCutout())
            binding.layoutAll.updatePadding(
                left = barInsets.left + cutoutInsets.left,
                top = barInsets.top,
                right = barInsets.right + cutoutInsets.right,
                bottom = barInsets.bottom + resources.getDimensionPixelSize(R.dimen.spacing_large)
            )
            windowInsets
        }

'''
s = s[:insets_start] + new_insets + s[insets_end:]
p.write_text(s)


# 3) Reuse the dedicated Moonwitch property card rather than the generic emulator card.
p = ROOT / 'java/org/yuzu/yuzu_emu/adapters/GamePropertiesAdapter.kt'
s = p.read_text()
s = s.replace('import org.yuzu.yuzu_emu.databinding.CardSimpleOutlinedBinding\n', 'import org.yuzu.yuzu_emu.databinding.CardMoonwitchGamePropertyBinding\n')
s = s.replace('CardSimpleOutlinedBinding.inflate(', 'CardMoonwitchGamePropertyBinding.inflate(')
s = s.replace('inner class SubmenuPropertyViewHolder(val binding: CardSimpleOutlinedBinding) :', 'inner class SubmenuPropertyViewHolder(val binding: CardMoonwitchGamePropertyBinding) :')
p.write_text(s)


# 4) New portrait-first Moonwitch Game Hub layout.
p = ROOT / 'res/layout/fragment_game_properties.xml'
p.write_text('''<?xml version="1.0" encoding="utf-8"?>
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
                android:layout_height="350dp">

                <ImageView
                    android:id="@+id/image_game_backdrop"
                    android:layout_width="match_parent"
                    android:layout_height="match_parent"
                    android:alpha="0.30"
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
                    android:paddingHorizontal="14dp"
                    android:paddingTop="8dp">

                    <com.google.android.material.button.MaterialButton
                        android:id="@+id/button_back"
                        style="?attr/materialIconButtonStyle"
                        android:layout_width="48dp"
                        android:layout_height="48dp"
                        android:backgroundTint="@color/moonwitch_panel_soft"
                        android:contentDescription="@string/back"
                        app:icon="@drawable/ic_back"
                        app:iconSize="22dp"
                        app:iconTint="@color/moonwitch_text"
                        app:strokeColor="@color/moonwitch_border_soft"
                        app:strokeWidth="1dp" />

                    <Space
                        android:layout_width="0dp"
                        android:layout_height="1dp"
                        android:layout_weight="1" />

                    <com.google.android.material.button.MaterialButton
                        android:id="@+id/button_shortcut"
                        style="?attr/materialIconButtonStyle"
                        android:layout_width="48dp"
                        android:layout_height="48dp"
                        android:backgroundTint="@color/moonwitch_panel_soft"
                        android:contentDescription="@string/add_to_home_screen"
                        app:icon="@drawable/ic_shortcut"
                        app:iconSize="22dp"
                        app:iconTint="@color/moonwitch_cyan"
                        app:strokeColor="@color/moonwitch_border_soft"
                        app:strokeWidth="1dp" />
                </LinearLayout>

                <LinearLayout
                    android:layout_width="match_parent"
                    android:layout_height="wrap_content"
                    android:layout_gravity="bottom"
                    android:gravity="bottom"
                    android:orientation="horizontal"
                    android:paddingHorizontal="18dp"
                    android:paddingBottom="22dp">

                    <com.google.android.material.card.MaterialCardView
                        android:layout_width="108dp"
                        android:layout_height="108dp"
                        app:cardBackgroundColor="@color/moonwitch_panel_high"
                        app:cardCornerRadius="22dp"
                        app:cardElevation="0dp"
                        app:strokeColor="@color/moonwitch_cyan"
                        app:strokeWidth="1dp">

                        <com.google.android.material.imageview.ShapeableImageView
                            android:id="@+id/image_game_screen"
                            android:layout_width="match_parent"
                            android:layout_height="match_parent"
                            android:padding="2dp"
                            android:scaleType="fitCenter"
                            app:shapeAppearance="@style/ShapeAppearance.Material3.Corner.Medium"
                            tools:src="@drawable/default_icon" />
                    </com.google.android.material.card.MaterialCardView>

                    <LinearLayout
                        android:layout_width="0dp"
                        android:layout_height="wrap_content"
                        android:layout_marginStart="16dp"
                        android:layout_weight="1"
                        android:orientation="vertical">

                        <TextView
                            android:layout_width="wrap_content"
                            android:layout_height="wrap_content"
                            android:fontFamily="sans-serif-medium"
                            android:letterSpacing="0.12"
                            android:text="@string/mw_gamehub_kicker"
                            android:textAllCaps="true"
                            android:textColor="@color/moonwitch_cyan"
                            android:textSize="9sp" />

                        <TextView
                            android:id="@+id/title"
                            android:layout_width="match_parent"
                            android:layout_height="wrap_content"
                            android:layout_marginTop="5dp"
                            android:ellipsize="end"
                            android:fontFamily="sans-serif-medium"
                            android:maxLines="2"
                            android:textColor="@color/moonwitch_text"
                            android:textSize="22sp"
                            tools:text="The Legend of Zelda: Tears of the Kingdom" />

                        <TextView
                            android:id="@+id/developer"
                            android:layout_width="match_parent"
                            android:layout_height="wrap_content"
                            android:layout_marginTop="3dp"
                            android:ellipsize="end"
                            android:maxLines="1"
                            android:textColor="@color/moonwitch_text_muted"
                            android:textSize="11sp"
                            tools:text="Nintendo" />

                        <com.google.android.material.textview.MaterialTextView
                            android:id="@+id/playtime"
                            android:layout_width="wrap_content"
                            android:layout_height="wrap_content"
                            android:layout_marginTop="10dp"
                            android:background="@drawable/mw_game_hub_stat_pill"
                            android:clickable="true"
                            android:focusable="true"
                            android:paddingHorizontal="10dp"
                            android:paddingVertical="5dp"
                            android:textColor="@color/moonwitch_text"
                            android:textSize="10sp"
                            tools:text="Tempo jogado • 82h 14m" />
                    </LinearLayout>
                </LinearLayout>
            </FrameLayout>

            <com.google.android.material.button.MaterialButton
                android:id="@+id/button_start"
                android:layout_width="match_parent"
                android:layout_height="56dp"
                android:layout_marginHorizontal="18dp"
                android:layout_marginTop="2dp"
                android:fontFamily="sans-serif-medium"
                android:text="@string/mw_gamehub_play"
                android:textColor="@color/ic_launcher_background"
                android:textSize="14sp"
                app:backgroundTint="@color/moonwitch_cyan"
                app:cornerRadius="18dp"
                app:icon="@drawable/ic_play"
                app:iconGravity="textStart"
                app:iconTint="@color/ic_launcher_background" />

            <TextView
                android:layout_width="match_parent"
                android:layout_height="wrap_content"
                android:layout_marginHorizontal="20dp"
                android:layout_marginTop="24dp"
                android:layout_marginBottom="6dp"
                android:fontFamily="sans-serif-medium"
                android:letterSpacing="0.10"
                android:text="@string/mw_gamehub_panel"
                android:textAllCaps="true"
                android:textColor="@color/moonwitch_text_muted"
                android:textSize="10sp" />

            <androidx.recyclerview.widget.RecyclerView
                android:id="@+id/list_properties"
                android:layout_width="match_parent"
                android:layout_height="wrap_content"
                android:clipToPadding="false"
                android:nestedScrollingEnabled="false"
                android:paddingBottom="20dp" />
        </LinearLayout>
    </androidx.core.widget.NestedScrollView>
</FrameLayout>
''')

# Hero overlays.
p = ROOT / 'res/drawable/mw_game_hub_hero_scrim.xml'
p.write_text('''<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">
    <gradient
        android:angle="270"
        android:startColor="#22050814"
        android:centerColor="#99050814"
        android:endColor="#FF050814" />
</shape>
''')

p = ROOT / 'res/drawable/mw_game_hub_stat_pill.xml'
p.write_text('''<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">
    <solid android:color="#CC10182A" />
    <corners android:radius="999dp" />
    <stroke android:width="1dp" android:color="#5535D8FF" />
</shape>
''')

# 5) Library cards: preserve the full artwork/icon instead of cropping it.
p = ROOT / 'res/layout/card_game_grid.xml'
s = p.read_text()
s = replace_once(s, 'android:scaleType="centerCrop"', 'android:scaleType="fitCenter"\n                android:background="@color/moonwitch_panel_high"\n                android:padding="2dp"', 'grid artwork fit')
p.write_text(s)

# 6) New frontend copy, localized.
for rel, values in [
    ('res/values/strings.xml', '''
    <string name="mw_gamehub_kicker">Moonwitch Game Hub</string>
    <string name="mw_gamehub_play">Play</string>
    <string name="mw_gamehub_panel">Game panel</string>
    <string name="mw_gamehub_unknown_developer">Nintendo Switch title</string>
    <string name="mw_gamehub_playtime_value">Play time • %1$s</string>
    <string name="mw_gamehub_performance_desc">SAFS, frame pacing, frame generation, clocks and performance tuning</string>
    <string name="mw_gamehub_graphics_desc">Resolution, reconstruction, filtering and image quality</string>
    <string name="mw_gamehub_content">Content</string>
    <string name="mw_gamehub_content_desc">Mods, updates and DLC installed for this game</string>
    <string name="mw_gamehub_statistics">Statistics</string>
    <string name="mw_gamehub_statistics_desc">Registered play time and game activity</string>
    <string name="mw_gamehub_advanced">Advanced settings</string>
    <string name="mw_gamehub_advanced_desc">System, audio, controls and additional per-game overrides</string>
    <string name="mw_gamehub_info">Game information</string>
    <string name="mw_gamehub_info_desc">Title ID, version and technical information</string>
'''),
    ('res/values-pt-rBR/strings.xml', '''
    <string name="mw_gamehub_kicker">Central do jogo Moonwitch</string>
    <string name="mw_gamehub_play">Jogar</string>
    <string name="mw_gamehub_panel">Painel do jogo</string>
    <string name="mw_gamehub_unknown_developer">Título de Nintendo Switch</string>
    <string name="mw_gamehub_playtime_value">Tempo jogado • %1$s</string>
    <string name="mw_gamehub_performance_desc">SAFS, frame pacing, geração de quadros, clocks e ajustes de desempenho</string>
    <string name="mw_gamehub_graphics_desc">Resolução, reconstrução, filtros e qualidade de imagem</string>
    <string name="mw_gamehub_content">Conteúdo</string>
    <string name="mw_gamehub_content_desc">Mods, updates e DLC instalados para este jogo</string>
    <string name="mw_gamehub_statistics">Estatísticas</string>
    <string name="mw_gamehub_statistics_desc">Tempo de jogo registrado e atividade do título</string>
    <string name="mw_gamehub_advanced">Configurações avançadas</string>
    <string name="mw_gamehub_advanced_desc">Sistema, áudio, controles e outros ajustes específicos do jogo</string>
    <string name="mw_gamehub_info">Informações do jogo</string>
    <string name="mw_gamehub_info_desc">Title ID, versão e informações técnicas</string>
''')
]:
    p = ROOT / rel
    s = p.read_text()
    if 'name="mw_gamehub_kicker"' in s:
        raise SystemExit(f'{rel}: Frontend V1 strings already exist')
    s = replace_once(s, '</resources>', values + '\n</resources>', f'{rel} strings close')
    p.write_text(s)

# Validation: no canonical shortcuts duplicated in the Game Hub prefix.
props = (ROOT / 'java/org/yuzu/yuzu_emu/fragments/GamePropertiesFragment.kt').read_text()
for token in [
    'Settings.MenuTag.SECTION_MOONWITCH_PERFORMANCE',
    'Settings.MenuTag.SECTION_RENDERER',
    'Settings.MenuTag.SECTION_DRIVERS_COMPONENTS',
]:
    if props.count(token) != 1:
        raise SystemExit(f'{token}: expected one Game Hub route, found {props.count(token)}')
if 'driverViewModel' in props or 'GpuDriverHelper' in props:
    raise SystemExit('legacy direct driver shortcuts still present in GamePropertiesFragment')

adapter = (ROOT / 'java/org/yuzu/yuzu_emu/adapters/GameAdapter.kt').read_text()
click_section = adapter[adapter.index('        fun onClick(game: Game) {'):adapter.index('        fun onLongClick(game: Game): Boolean {')]
if 'actionGlobalEmulationActivity' in click_section:
    raise SystemExit('library tap still launches emulation directly')
if 'actionGlobalPerGamePropertiesFragment' not in click_section:
    raise SystemExit('library tap does not open Game Hub')

print('Moonwitch Frontend V1 transformation validated.')
