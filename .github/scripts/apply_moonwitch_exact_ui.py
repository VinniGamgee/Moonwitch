#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise RuntimeError(f"anchor not found in {path}: {old!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


path = ROOT / "src/android/app/src/main/java/org/yuzu/yuzu_emu/fragments/GamePropertiesFragment.kt"

replace_once(
    path,
    "        GameIconUtils.loadGameIcon(args.game, binding.imageGameScreen)\n",
    "        GameIconUtils.loadGameIcon(args.game, binding.imageGameScreen)\n"
    "        GameIconUtils.loadGameIcon(args.game, binding.heroGameImage)\n",
)

replace_once(
    path,
    "        binding.title.marquee()\n\n        getPlayTime()\n",
    "        binding.title.marquee()\n        setupExactFrontend()\n\n        getPlayTime()\n",
)

helper = r'''
    private fun setupExactFrontend() {
        val prefs = androidx.preference.PreferenceManager.getDefaultSharedPreferences(requireContext())

        binding.gameMetadata.text = buildString {
            append(args.game.developer.ifBlank { getString(R.string.app_name) })
            if (args.game.version.isNotBlank()) {
                append(" • ")
                append(args.game.version)
            }
        }
        binding.gameDescription.text = "ID do programa: ${args.game.programIdHex}"

        val lastPlayed = prefs.getLong(args.game.keyLastPlayedTime, 0L)
        binding.lastPlayed.text = if (lastPlayed <= 0L) {
            "Nunca"
        } else {
            java.text.DateFormat.getDateTimeInstance(
                java.text.DateFormat.SHORT,
                java.text.DateFormat.SHORT
            ).format(java.util.Date(lastPlayed))
        }

        val document = androidx.documentfile.provider.DocumentFile.fromSingleUri(
            requireContext(),
            android.net.Uri.parse(args.game.path)
        )
        val bytes = document?.length() ?: 0L
        binding.fileSize.text = when {
            bytes >= 1024L * 1024L * 1024L -> String.format(
                java.util.Locale.getDefault(),
                "%.1f GB",
                bytes.toDouble() / (1024.0 * 1024.0 * 1024.0)
            )
            bytes >= 1024L * 1024L -> String.format(
                java.util.Locale.getDefault(),
                "%.1f MB",
                bytes.toDouble() / (1024.0 * 1024.0)
            )
            bytes > 0L -> "${bytes / 1024L} KB"
            else -> "—"
        }

        fun refreshFavorite() {
            val favorite = prefs.getBoolean(args.game.keyFavorite, false)
            binding.favoriteIcon.setImageResource(
                if (favorite) R.drawable.ic_mw_star_filled else R.drawable.ic_mw_star
            )
            binding.favoriteIcon.imageTintList = android.content.res.ColorStateList.valueOf(
                androidx.core.content.ContextCompat.getColor(
                    requireContext(),
                    if (favorite) R.color.mw_ui_accent_hi else R.color.mw_ui_text
                )
            )
        }
        refreshFavorite()

        binding.buttonFavorite.setOnClickListener {
            val next = !prefs.getBoolean(args.game.keyFavorite, false)
            prefs.edit().putBoolean(args.game.keyFavorite, next).apply()
            refreshFavorite()
        }

        binding.buttonGameSettings.setOnClickListener {
            val action = HomeNavigationDirections.actionGlobalSettingsActivity(
                args.game,
                Settings.MenuTag.SECTION_ROOT
            )
            binding.root.findNavController().navigate(action)
        }

        binding.buttonCheats.setOnClickListener {
            val action = HomeNavigationDirections.actionGlobalSettingsSubscreenActivity(
                SettingsSubscreen.ADDONS,
                args.game
            )
            binding.root.findNavController().navigate(action)
        }

        val showMore = View.OnClickListener {
            binding.listAll.post {
                binding.listAll.smoothScrollTo(0, binding.moreOptionsLabel.top)
            }
        }
        binding.buttonMore.setOnClickListener(showMore)
        binding.heroMoreButton.setOnClickListener(showMore)

        binding.navHome.setOnClickListener {
            prefs.edit().putInt("MoonwitchFrontendPage", 0).apply()
            binding.root.findNavController().popBackStack(R.id.gamesFragment, false)
        }
        binding.navGames.setOnClickListener {
            prefs.edit().putInt("MoonwitchFrontendPage", 1).apply()
            binding.root.findNavController().popBackStack(R.id.gamesFragment, false)
        }
        binding.navSettings.setOnClickListener {
            binding.root.findNavController().navigate(R.id.homeSettingsFragment)
        }
    }

'''
replace_once(
    path,
    "    private fun getPlayTime() {\n",
    helper + "    private fun getPlayTime() {\n",
)

replace_once(
    path,
    "            append(getString(R.string.playtime) + \" \" + readablePlayTime)\n",
    "            append(readablePlayTime)\n",
)

games = ROOT / "src/android/app/src/main/java/org/yuzu/yuzu_emu/ui/GamesFragment.kt"
games_text = games.read_text(encoding="utf-8")
# In Jogos mode the hidden search row must keep its measured height so the tabs and
# list never overlap. INVISIBLE keeps layout space while remaining visually absent.
games_text = games_text.replace(
    "binding.searchTools.visibility = View.GONE",
    "binding.searchTools.visibility = View.INVISIBLE",
)
games.write_text(games_text, encoding="utf-8")

print("Moonwitch exact UI runtime wiring applied")
