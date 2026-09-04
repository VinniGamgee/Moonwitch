from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRAGMENT = ROOT / "src/android/app/src/main/java/org/yuzu/yuzu_emu/fragments/GamePropertiesFragment.kt"
LAYOUTS = [
    ROOT / "src/android/app/src/main/res/layout/fragment_game_properties.xml",
    ROOT / "src/android/app/src/main/res/layout-w600dp/fragment_game_properties.xml",
]
VALUES = ROOT / "src/android/app/src/main/res/values/moonwitch_gamehub_v2.xml"
VALUES_PT = ROOT / "src/android/app/src/main/res/values-pt-rBR/moonwitch_gamehub_v2.xml"
SCRIM = ROOT / "src/android/app/src/main/res/drawable/mw_game_hub_hero_scrim.xml"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


# Kotlin: real hero-art support, sane fallback, static title and clean metadata.
text = FRAGMENT.read_text()
text = replace_once(
    text,
    "import android.content.Intent\n",
    "import android.content.Intent\nimport android.graphics.BitmapFactory\nimport android.graphics.RenderEffect\nimport android.graphics.Shader\n",
    "graphics imports",
)
text = replace_once(
    text,
    "import android.os.Bundle\n",
    "import android.os.Build\nimport android.os.Bundle\n",
    "Build import",
)
text = text.replace("import org.yuzu.yuzu_emu.utils.ViewUtils.marquee\n", "")
text = replace_once(
    text,
    "        GameIconUtils.loadGameIcon(args.game, binding.imageGameScreen)\n        GameIconUtils.loadGameIcon(args.game, binding.imageGameBackdrop)\n        binding.title.text = args.game.title\n        binding.title.marquee()\n        binding.developer.text = args.game.developer.ifBlank {\n            getString(R.string.mw_gamehub_unknown_developer)\n        }\n",
    "        GameIconUtils.loadGameIcon(args.game, binding.imageGameScreen)\n        setupGameArtwork()\n        binding.title.text = args.game.title\n        binding.developer.text = args.game.developer.ifBlank {\n            getString(R.string.mw_gamehub_unknown_developer)\n        }\n        binding.developer.visibility = View.GONE\n",
    "hero initialization",
)

old_description = '''    private fun gameDescription(): String {\n        val metadataFile = File(\n            DirectoryInitialization.userDirectory +\n                "/moonwitch/metadata/" + args.game.settingsName + ".txt"\n        )\n        val customDescription = runCatching {\n            if (metadataFile.isFile) metadataFile.readText().trim() else ""\n        }.getOrDefault("")\n        if (customDescription.isNotBlank()) return customDescription\n\n        val developer = args.game.developer.ifBlank {\n            getString(R.string.mw_gamehub_unknown_developer)\n        }\n        return getString(\n            R.string.mw_gamehub_v2_description_fallback,\n            args.game.title,\n            developer\n        )\n    }\n'''
new_description = '''    private fun gameAssetDirectory(): File = File(\n        DirectoryInitialization.userDirectory +\n            "/moonwitch/metadata/" + args.game.settingsName\n    )\n\n    private fun gameDescription(): String {\n        val assetDirectory = gameAssetDirectory()\n        val legacyMetadata = File(\n            DirectoryInitialization.userDirectory +\n                "/moonwitch/metadata/" + args.game.settingsName + ".txt"\n        )\n        val candidates = listOf(\n            File(assetDirectory, "description.txt"),\n            File(assetDirectory, "description.pt-BR.txt"),\n            legacyMetadata\n        )\n        val customDescription = candidates.firstNotNullOfOrNull { file ->\n            runCatching {\n                if (file.isFile) file.readText().trim().takeIf(String::isNotBlank) else null\n            }.getOrNull()\n        }\n        return customDescription ?: getString(R.string.mw_gamehub_v2_description_fallback)\n    }\n\n    private fun findHeroArtwork(): File? {\n        val directory = gameAssetDirectory()\n        runCatching { directory.mkdirs() }\n        return listOf(\n            "hero.jpg",\n            "hero.jpeg",\n            "hero.png",\n            "hero.webp",\n            "background.jpg",\n            "background.jpeg",\n            "background.png",\n            "background.webp"\n        ).asSequence()\n            .map { File(directory, it) }\n            .firstOrNull(File::isFile)\n    }\n\n    private fun setupGameArtwork() {\n        val heroArtwork = findHeroArtwork()\n        if (heroArtwork == null) {\n            applyFallbackBackdrop()\n            return\n        }\n\n        viewLifecycleOwner.lifecycleScope.launch {\n            val bitmap = withContext(Dispatchers.IO) { decodeHeroArtwork(heroArtwork) }\n            if (_binding == null || bitmap == null) {\n                if (_binding != null) applyFallbackBackdrop()\n                return@launch\n            }\n\n            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {\n                binding.imageGameBackdrop.setRenderEffect(null)\n            }\n            binding.imageGameBackdrop.scaleX = 1f\n            binding.imageGameBackdrop.scaleY = 1f\n            binding.imageGameBackdrop.alpha = 0.78f\n            binding.imageGameBackdrop.setImageBitmap(bitmap)\n        }\n    }\n\n    private fun applyFallbackBackdrop() {\n        GameIconUtils.loadGameIcon(args.game, binding.imageGameBackdrop)\n        binding.imageGameBackdrop.alpha = 0.34f\n        binding.imageGameBackdrop.scaleX = 1.18f\n        binding.imageGameBackdrop.scaleY = 1.18f\n        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {\n            binding.imageGameBackdrop.setRenderEffect(\n                RenderEffect.createBlurEffect(32f, 32f, Shader.TileMode.CLAMP)\n            )\n        }\n    }\n\n    private fun decodeHeroArtwork(file: File) = runCatching {\n        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }\n        BitmapFactory.decodeFile(file.absolutePath, bounds)\n        var sampleSize = 1\n        while (bounds.outWidth / sampleSize > 1920 || bounds.outHeight / sampleSize > 1920) {\n            sampleSize *= 2\n        }\n        BitmapFactory.decodeFile(\n            file.absolutePath,\n            BitmapFactory.Options().apply { inSampleSize = sampleSize }\n        )\n    }.getOrNull()\n'''
text = replace_once(text, old_description, new_description, "description + hero helpers")
FRAGMENT.write_text(text)

# Layout: title is static/multiline, developer duplication disappears, and the technical section
# gets a softer transition instead of looking like another app pasted underneath.
old_title = '''                        <TextView\n                            android:id="@+id/title"\n                            android:layout_width="match_parent"\n                            android:layout_height="wrap_content"\n                            android:ellipsize="end"\n                            android:fontFamily="sans-serif-medium"\n                            android:maxLines="3"\n                            android:textColor="@color/moonwitch_text"\n                            android:textSize="23sp"\n                            tools:text="The Legend of Zelda: Tears of the Kingdom" />'''
new_title = '''                        <TextView\n                            android:id="@+id/title"\n                            android:layout_width="match_parent"\n                            android:layout_height="wrap_content"\n                            android:fontFamily="sans-serif-medium"\n                            android:includeFontPadding="false"\n                            android:lineSpacingExtra="1dp"\n                            android:maxLines="3"\n                            android:textColor="@color/moonwitch_text"\n                            android:textSize="24sp"\n                            tools:text="The Legend of Zelda: Tears of the Kingdom" />'''

old_section = '''            <TextView\n                android:layout_width="match_parent"\n                android:layout_height="wrap_content"\n                android:layout_marginHorizontal="22dp"\n                android:layout_marginTop="22dp"\n                android:layout_marginBottom="7dp"\n                android:fontFamily="sans-serif-medium"\n                android:letterSpacing="0.08"\n                android:text="@string/mw_gamehub_v2_game_settings"\n                android:textAllCaps="true"\n                android:textColor="@color/moonwitch_text_muted"\n                android:textSize="10sp" />'''
new_section = '''            <LinearLayout\n                android:layout_width="match_parent"\n                android:layout_height="wrap_content"\n                android:layout_marginHorizontal="22dp"\n                android:layout_marginTop="24dp"\n                android:layout_marginBottom="8dp"\n                android:orientation="vertical">\n\n                <TextView\n                    android:layout_width="match_parent"\n                    android:layout_height="wrap_content"\n                    android:fontFamily="sans-serif-medium"\n                    android:text="@string/mw_gamehub_v2_game_settings"\n                    android:textColor="@color/moonwitch_text"\n                    android:textSize="15sp" />\n\n                <TextView\n                    android:layout_width="match_parent"\n                    android:layout_height="wrap_content"\n                    android:layout_marginTop="4dp"\n                    android:lineSpacingExtra="1dp"\n                    android:text="@string/mw_gamehub_v21_settings_intro"\n                    android:textColor="@color/moonwitch_text_muted"\n                    android:textSize="11sp" />\n            </LinearLayout>'''

for layout in LAYOUTS:
    xml = layout.read_text()
    xml = replace_once(xml, old_title, new_title, f"title block in {layout}")
    xml = replace_once(xml, old_section, new_section, f"settings transition in {layout}")
    # The separate developer TextView is retained for ViewBinding compatibility but hidden in Kotlin.
    layout.write_text(xml)

# Copy is short and frontend-like; no technical placeholder paragraph pretending to be a synopsis.
values = VALUES.read_text()
values = replace_once(
    values,
    '<string name="mw_gamehub_v2_description_fallback">%1$s is a Nintendo Switch title published by %2$s. Moonwitch does not have an external synopsis for this title yet; real activity and technical metadata are shown below.</string>',
    '<string name="mw_gamehub_v2_description_fallback">No synopsis is available for this game yet.</string>\n    <string name="mw_gamehub_v21_settings_intro">Tune performance, graphics and components for this title.</string>',
    "English V2.1 strings",
)
VALUES.write_text(values)

values_pt = VALUES_PT.read_text()
values_pt = replace_once(
    values_pt,
    '<string name="mw_gamehub_v2_description_fallback">%1$s é um título de Nintendo Switch publicado por %2$s. O Moonwitch ainda não possui uma sinopse externa para este título; abaixo ficam atividade real e metadados técnicos do jogo.</string>',
    '<string name="mw_gamehub_v2_description_fallback">Ainda não há uma sinopse disponível para este jogo.</string>\n    <string name="mw_gamehub_v21_settings_intro">Ajuste desempenho, gráficos e componentes especificamente para este jogo.</string>',
    "Portuguese V2.1 strings",
)
VALUES_PT.write_text(values_pt)

# Slightly stronger scrim keeps fallback cover art atmospheric instead of readable/blown-up.
scrim = SCRIM.read_text()
scrim = scrim.replace('android:startColor="#22050814"', 'android:startColor="#44050814"')
scrim = scrim.replace('android:centerColor="#99050814"', 'android:centerColor="#B3050814"')
SCRIM.write_text(scrim)

# Cheap structural checks so CI fails before a 20-minute Android build if the V2.1 wiring regresses.
final_fragment = FRAGMENT.read_text()
assert "binding.title.marquee()" not in final_fragment
assert "findHeroArtwork" in final_fragment
assert "RenderEffect.createBlurEffect(32f, 32f" in final_fragment
assert '"hero.webp"' in final_fragment
assert "mw_gamehub_v21_settings_intro" in LAYOUTS[0].read_text()
print("Moonwitch Game Hub V2.1 applied successfully")
