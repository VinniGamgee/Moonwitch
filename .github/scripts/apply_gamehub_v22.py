from pathlib import Path


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise SystemExit(f"Missing expected marker for {label}")
    return text.replace(old, new, 1)


root = Path(".")
fragment_path = root / "src/android/app/src/main/java/org/yuzu/yuzu_emu/fragments/GamePropertiesFragment.kt"
fragment = fragment_path.read_text()

fragment = replace_once(
    fragment,
    "import android.content.Intent\n",
    "import android.content.Intent\nimport android.graphics.Color\nimport android.net.Uri\n",
    "graphics imports",
)
fragment = replace_once(
    fragment,
    "import android.view.ViewGroup\n",
    "import android.view.ViewGroup\nimport android.view.WindowManager\n",
    "window import",
)
fragment = replace_once(
    fragment,
    "import android.widget.Toast\n",
    "import android.widget.FrameLayout\nimport android.widget.ImageView\nimport android.widget.Toast\n",
    "widget imports",
)
fragment = replace_once(
    fragment,
    "import com.google.android.material.transition.MaterialSharedAxis\n",
    "import com.google.android.material.bottomsheet.BottomSheetBehavior\nimport com.google.android.material.bottomsheet.BottomSheetDialog\nimport com.google.android.material.transition.MaterialSharedAxis\n",
    "bottom sheet imports",
)
fragment = replace_once(
    fragment,
    "        GameIconUtils.loadGameIcon(args.game, binding.imageGameScreen)\n        setupGameArtwork()\n",
    "        setupGameCover()\n        setupGameArtwork()\n",
    "cover setup",
)

start = fragment.index("    private fun findHeroArtwork(): File?")
end = fragment.index("    private fun readableLastPlayed(): String", start)
artwork_block = '''    private fun findArtwork(names: List<String>): File? {
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
                if (stem == "cover") setupGameCover() else setupGameArtwork()
                Toast.makeText(
                    requireContext(),
                    if (stem == "cover") R.string.mw_gamehub_v22_cover_updated
                    else R.string.mw_gamehub_v22_hero_updated,
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

'''
fragment = fragment[:start] + artwork_block + fragment[end:]

start = fragment.index("    private fun showMoreActions() {")
end = fragment.index("    private fun showEditPlaytimeDialog()", start)
more_block = '''    private fun showMoreActions() {
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

'''
fragment = fragment[:start] + more_block + fragment[end:]

launcher_marker = "    private val importSaves =\n"
launchers = '''    private val importCoverArtwork =
        registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
            if (uri != null) importArtwork(uri, "cover")
        }

    private val importHeroArtwork =
        registerForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
            if (uri != null) importArtwork(uri, "hero")
        }

'''
fragment = replace_once(fragment, launcher_marker, launchers + launcher_marker, "artwork launchers")
fragment_path.write_text(fragment)

sheet_layout = r'''<?xml version="1.0" encoding="utf-8"?>
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:app="http://schemas.android.com/apk/res-auto"
    android:layout_width="match_parent"
    android:layout_height="wrap_content"
    android:background="@drawable/mw_gamehub_sheet_background"
    android:orientation="vertical"
    android:paddingBottom="20dp">

    <View
        android:layout_width="42dp"
        android:layout_height="4dp"
        android:layout_gravity="center_horizontal"
        android:layout_marginTop="10dp"
        android:background="@drawable/mw_gamehub_sheet_handle" />

    <TextView
        android:id="@+id/more_game_title"
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:layout_marginHorizontal="22dp"
        android:layout_marginTop="18dp"
        android:ellipsize="end"
        android:fontFamily="sans-serif-medium"
        android:maxLines="2"
        android:textColor="@color/moonwitch_text"
        android:textSize="19sp" />

    <TextView
        android:layout_width="match_parent"
        android:layout_height="wrap_content"
        android:layout_marginHorizontal="22dp"
        android:layout_marginTop="4dp"
        android:layout_marginBottom="10dp"
        android:text="@string/mw_gamehub_v22_more_subtitle"
        android:textColor="@color/moonwitch_text_muted"
        android:textSize="11sp" />

    <LinearLayout
        android:id="@+id/more_device_profile"
        android:layout_width="match_parent"
        android:layout_height="72dp"
        android:background="?attr/selectableItemBackground"
        android:clickable="true"
        android:focusable="true"
        android:gravity="center_vertical"
        android:orientation="horizontal"
        android:paddingHorizontal="22dp">
        <ImageView android:layout_width="44dp" android:layout_height="44dp" android:background="@drawable/mw_gamehub_sheet_icon_bg" android:contentDescription="@null" android:padding="10dp" android:src="@drawable/ic_graphics" app:tint="@color/mw_gamehub_v2_accent" />
        <LinearLayout android:layout_width="0dp" android:layout_height="wrap_content" android:layout_marginStart="14dp" android:layout_weight="1" android:orientation="vertical">
            <TextView android:layout_width="match_parent" android:layout_height="wrap_content" android:text="@string/device_profile_title" android:textColor="@color/moonwitch_text" android:textSize="14sp" />
            <TextView android:layout_width="match_parent" android:layout_height="wrap_content" android:layout_marginTop="2dp" android:text="@string/mw_gamehub_v22_profile_desc" android:textColor="@color/moonwitch_text_muted" android:textSize="10sp" />
        </LinearLayout>
    </LinearLayout>

    <LinearLayout
        android:id="@+id/more_cover"
        android:layout_width="match_parent"
        android:layout_height="72dp"
        android:background="?attr/selectableItemBackground"
        android:clickable="true"
        android:focusable="true"
        android:gravity="center_vertical"
        android:orientation="horizontal"
        android:paddingHorizontal="22dp">
        <ImageView android:layout_width="44dp" android:layout_height="44dp" android:background="@drawable/mw_gamehub_sheet_icon_bg" android:contentDescription="@null" android:padding="10dp" android:src="@drawable/ic_edit" app:tint="@color/mw_gamehub_v2_accent" />
        <LinearLayout android:layout_width="0dp" android:layout_height="wrap_content" android:layout_marginStart="14dp" android:layout_weight="1" android:orientation="vertical">
            <TextView android:layout_width="match_parent" android:layout_height="wrap_content" android:text="@string/mw_gamehub_v22_cover" android:textColor="@color/moonwitch_text" android:textSize="14sp" />
            <TextView android:layout_width="match_parent" android:layout_height="wrap_content" android:layout_marginTop="2dp" android:text="@string/mw_gamehub_v22_cover_desc" android:textColor="@color/moonwitch_text_muted" android:textSize="10sp" />
        </LinearLayout>
    </LinearLayout>

    <LinearLayout
        android:id="@+id/more_hero"
        android:layout_width="match_parent"
        android:layout_height="72dp"
        android:background="?attr/selectableItemBackground"
        android:clickable="true"
        android:focusable="true"
        android:gravity="center_vertical"
        android:orientation="horizontal"
        android:paddingHorizontal="22dp">
        <ImageView android:layout_width="44dp" android:layout_height="44dp" android:background="@drawable/mw_gamehub_sheet_icon_bg" android:contentDescription="@null" android:padding="10dp" android:src="@drawable/ic_graphics" app:tint="@color/mw_gamehub_v2_accent" />
        <LinearLayout android:layout_width="0dp" android:layout_height="wrap_content" android:layout_marginStart="14dp" android:layout_weight="1" android:orientation="vertical">
            <TextView android:layout_width="match_parent" android:layout_height="wrap_content" android:text="@string/mw_gamehub_v22_hero" android:textColor="@color/moonwitch_text" android:textSize="14sp" />
            <TextView android:layout_width="match_parent" android:layout_height="wrap_content" android:layout_marginTop="2dp" android:text="@string/mw_gamehub_v22_hero_desc" android:textColor="@color/moonwitch_text_muted" android:textSize="10sp" />
        </LinearLayout>
    </LinearLayout>

    <View android:layout_width="match_parent" android:layout_height="1dp" android:layout_marginHorizontal="22dp" android:background="@color/moonwitch_border_soft" />

    <LinearLayout
        android:id="@+id/more_game_info"
        android:layout_width="match_parent"
        android:layout_height="72dp"
        android:background="?attr/selectableItemBackground"
        android:clickable="true"
        android:focusable="true"
        android:gravity="center_vertical"
        android:orientation="horizontal"
        android:paddingHorizontal="22dp">
        <ImageView android:layout_width="44dp" android:layout_height="44dp" android:background="@drawable/mw_gamehub_sheet_icon_bg" android:contentDescription="@null" android:padding="10dp" android:src="@drawable/ic_build" app:tint="@color/mw_gamehub_v2_accent" />
        <LinearLayout android:layout_width="0dp" android:layout_height="wrap_content" android:layout_marginStart="14dp" android:layout_weight="1" android:orientation="vertical">
            <TextView android:layout_width="match_parent" android:layout_height="wrap_content" android:text="@string/mw_gamehub_info" android:textColor="@color/moonwitch_text" android:textSize="14sp" />
            <TextView android:layout_width="match_parent" android:layout_height="wrap_content" android:layout_marginTop="2dp" android:text="@string/mw_gamehub_v22_info_desc" android:textColor="@color/moonwitch_text_muted" android:textSize="10sp" />
        </LinearLayout>
    </LinearLayout>

    <LinearLayout
        android:id="@+id/more_shortcut"
        android:layout_width="match_parent"
        android:layout_height="72dp"
        android:background="?attr/selectableItemBackground"
        android:clickable="true"
        android:focusable="true"
        android:gravity="center_vertical"
        android:orientation="horizontal"
        android:paddingHorizontal="22dp">
        <ImageView android:layout_width="44dp" android:layout_height="44dp" android:background="@drawable/mw_gamehub_sheet_icon_bg" android:contentDescription="@null" android:padding="10dp" android:src="@drawable/mw_gamehub_v2_more" app:tint="@color/mw_gamehub_v2_accent" />
        <LinearLayout android:layout_width="0dp" android:layout_height="wrap_content" android:layout_marginStart="14dp" android:layout_weight="1" android:orientation="vertical">
            <TextView android:layout_width="match_parent" android:layout_height="wrap_content" android:text="@string/mw_gamehub_v2_create_shortcut" android:textColor="@color/moonwitch_text" android:textSize="14sp" />
            <TextView android:layout_width="match_parent" android:layout_height="wrap_content" android:layout_marginTop="2dp" android:text="@string/mw_gamehub_v22_shortcut_desc" android:textColor="@color/moonwitch_text_muted" android:textSize="10sp" />
        </LinearLayout>
    </LinearLayout>

    <LinearLayout
        android:id="@+id/more_playtime"
        android:layout_width="match_parent"
        android:layout_height="72dp"
        android:background="?attr/selectableItemBackground"
        android:clickable="true"
        android:focusable="true"
        android:gravity="center_vertical"
        android:orientation="horizontal"
        android:paddingHorizontal="22dp">
        <ImageView android:layout_width="44dp" android:layout_height="44dp" android:background="@drawable/mw_gamehub_sheet_icon_bg" android:contentDescription="@null" android:padding="10dp" android:src="@drawable/mw_gamehub_v2_clock" app:tint="@color/mw_gamehub_v2_accent" />
        <LinearLayout android:layout_width="0dp" android:layout_height="wrap_content" android:layout_marginStart="14dp" android:layout_weight="1" android:orientation="vertical">
            <TextView android:layout_width="match_parent" android:layout_height="wrap_content" android:text="@string/mw_gamehub_v2_edit_playtime" android:textColor="@color/moonwitch_text" android:textSize="14sp" />
            <TextView android:layout_width="match_parent" android:layout_height="wrap_content" android:layout_marginTop="2dp" android:text="@string/mw_gamehub_v22_playtime_desc" android:textColor="@color/moonwitch_text_muted" android:textSize="10sp" />
        </LinearLayout>
    </LinearLayout>

    <LinearLayout
        android:id="@+id/more_advanced"
        android:layout_width="match_parent"
        android:layout_height="72dp"
        android:background="?attr/selectableItemBackground"
        android:clickable="true"
        android:focusable="true"
        android:gravity="center_vertical"
        android:orientation="horizontal"
        android:paddingHorizontal="22dp">
        <ImageView android:layout_width="44dp" android:layout_height="44dp" android:background="@drawable/mw_gamehub_sheet_icon_bg" android:contentDescription="@null" android:padding="10dp" android:src="@drawable/ic_settings" app:tint="@color/mw_gamehub_v2_accent" />
        <LinearLayout android:layout_width="0dp" android:layout_height="wrap_content" android:layout_marginStart="14dp" android:layout_weight="1" android:orientation="vertical">
            <TextView android:layout_width="match_parent" android:layout_height="wrap_content" android:text="@string/mw_gamehub_advanced" android:textColor="@color/moonwitch_text" android:textSize="14sp" />
            <TextView android:layout_width="match_parent" android:layout_height="wrap_content" android:layout_marginTop="2dp" android:text="@string/mw_gamehub_v22_advanced_desc" android:textColor="@color/moonwitch_text_muted" android:textSize="10sp" />
        </LinearLayout>
    </LinearLayout>
</LinearLayout>
'''

(root / "src/android/app/src/main/res/layout/bottom_sheet_gamehub_more.xml").write_text(sheet_layout)

(root / "src/android/app/src/main/res/drawable/mw_gamehub_sheet_background.xml").write_text(r'''<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">
    <solid android:color="#FF090E18" />
    <corners android:topLeftRadius="28dp" android:topRightRadius="28dp" />
    <stroke android:width="1dp" android:color="#332F8FFF" />
</shape>
''')
(root / "src/android/app/src/main/res/drawable/mw_gamehub_sheet_icon_bg.xml").write_text(r'''<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="oval">
    <solid android:color="#252C1F48" />
</shape>
''')
(root / "src/android/app/src/main/res/drawable/mw_gamehub_sheet_handle.xml").write_text(r'''<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">
    <solid android:color="#55FFFFFF" />
    <corners android:radius="2dp" />
</shape>
''')


def add_strings(path: Path, lines: str) -> None:
    text = path.read_text()
    if "mw_gamehub_v22_more_subtitle" in text:
        return
    text = text.replace("</resources>", lines + "\n</resources>")
    path.write_text(text)


add_strings(
    root / "src/android/app/src/main/res/values/moonwitch_gamehub_v2.xml",
    '''    <string name="mw_gamehub_v22_more_subtitle">Quick actions and artwork for this title.</string>
    <string name="mw_gamehub_v22_profile_desc">Apply a real device-aware recommendation.</string>
    <string name="mw_gamehub_v22_cover">Game cover</string>
    <string name="mw_gamehub_v22_cover_desc">Choose a portrait cover from your device.</string>
    <string name="mw_gamehub_v22_hero">Hero / background</string>
    <string name="mw_gamehub_v22_hero_desc">Choose the wide artwork shown behind the game.</string>
    <string name="mw_gamehub_v22_info_desc">Version, title ID and game details.</string>
    <string name="mw_gamehub_v22_shortcut_desc">Pin this game directly to your home screen.</string>
    <string name="mw_gamehub_v22_playtime_desc">Adjust the play-time counter for this title.</string>
    <string name="mw_gamehub_v22_advanced_desc">Open every remaining per-game override.</string>
    <string name="mw_gamehub_v22_cover_updated">Game cover updated.</string>
    <string name="mw_gamehub_v22_hero_updated">Hero artwork updated.</string>
    <string name="mw_gamehub_v22_artwork_failed">Could not import this image.</string>''',
)

add_strings(
    root / "src/android/app/src/main/res/values-pt-rBR/moonwitch_gamehub_v2.xml",
    '''    <string name="mw_gamehub_v22_more_subtitle">Ações rápidas e personalização deste jogo.</string>
    <string name="mw_gamehub_v22_profile_desc">Aplique uma recomendação real baseada no dispositivo.</string>
    <string name="mw_gamehub_v22_cover">Capa do jogo</string>
    <string name="mw_gamehub_v22_cover_desc">Escolha uma capa vertical salva no aparelho.</string>
    <string name="mw_gamehub_v22_hero">Hero / fundo</string>
    <string name="mw_gamehub_v22_hero_desc">Escolha a arte horizontal exibida atrás do jogo.</string>
    <string name="mw_gamehub_v22_info_desc">Versão, Title ID e detalhes do jogo.</string>
    <string name="mw_gamehub_v22_shortcut_desc">Fixe este jogo diretamente na tela inicial.</string>
    <string name="mw_gamehub_v22_playtime_desc">Ajuste o contador de tempo deste jogo.</string>
    <string name="mw_gamehub_v22_advanced_desc">Abra todos os demais ajustes específicos do jogo.</string>
    <string name="mw_gamehub_v22_cover_updated">Capa do jogo atualizada.</string>
    <string name="mw_gamehub_v22_hero_updated">Hero do jogo atualizado.</string>
    <string name="mw_gamehub_v22_artwork_failed">Não foi possível importar esta imagem.</string>''',
)

# Guard the intended V2.2 shape before committing.
final_fragment = fragment_path.read_text()
for marker in (
    "findCoverArtwork",
    "BottomSheetDialog(requireContext())",
    "importCoverArtwork",
    "updateViewHeight(it, 330)",
):
    if marker not in final_fragment:
        raise SystemExit(f"V2.2 validation failed: {marker}")

print("Moonwitch Game Hub V2.2 source patch applied")
