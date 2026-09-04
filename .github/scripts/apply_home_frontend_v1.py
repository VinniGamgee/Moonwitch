from pathlib import Path
p=Path('src/android/app/src/main/java/org/yuzu/yuzu_emu/ui/GamesFragment.kt')
s=p.read_text()
for a,b in [
('import android.content.res.Configuration\n','import android.content.res.Configuration\nimport android.graphics.BitmapFactory\nimport android.graphics.RenderEffect\nimport android.graphics.Shader\n'),
('import android.os.Bundle\n','import android.os.Build\nimport android.os.Bundle\n'),
('import android.widget.PopupMenu\n','import android.widget.ImageView\nimport android.widget.PopupMenu\n'),
('import androidx.fragment.app.activityViewModels\n','import androidx.fragment.app.activityViewModels\nimport androidx.lifecycle.lifecycleScope\n'),
('import org.yuzu.yuzu_emu.utils.ViewUtils.setVisible\n','import org.yuzu.yuzu_emu.utils.DirectoryInitialization\nimport org.yuzu.yuzu_emu.utils.GameIconUtils\nimport org.yuzu.yuzu_emu.utils.ViewUtils.setVisible\n'),
('import info.debatty.java.stringsimilarity.Jaccard\n','import info.debatty.java.stringsimilarity.Jaccard\nimport kotlinx.coroutines.Dispatchers\nimport kotlinx.coroutines.launch\nimport kotlinx.coroutines.withContext\n'),
('import java.util.Locale\n','import java.io.File\nimport java.util.Locale\n')]:
    assert a in s,a
    s=s.replace(a,b,1)

anchor='    private var committedGameListSubmitGeneration = 0\n'
assert anchor in s
s=s.replace(anchor,'''    private var committedGameListSubmitGeneration = 0
    private var highlightedGame: Game? = null
    private var displayedGames: List<Game> = emptyList()
    private var heroLoadGeneration = 0

    private val heroScrollListener = object : RecyclerView.OnScrollListener() {
        override fun onScrolled(recyclerView: RecyclerView, dx: Int, dy: Int) = updateLibraryHeroFromScroll()
        override fun onScrollStateChanged(recyclerView: RecyclerView, newState: Int) {
            if (newState == RecyclerView.SCROLL_STATE_IDLE) updateLibraryHeroFromScroll()
        }
    }
''',1)

anchor='        applyGridGamesBinding()\n\n'
assert anchor in s
s=s.replace(anchor,'''        applyGridGamesBinding()

        binding.libraryHeroOpen.setOnClickListener {
            highlightedGame?.let(::openGameHub)
        }

''',1)

anchor='''            adapter = gameAdapter
            lastViewType = savedViewType
'''
assert anchor in s
s=s.replace(anchor,'''            adapter = gameAdapter
            removeOnScrollListener(heroScrollListener)
            addOnScrollListener(heroScrollListener)
            post { updateLibraryHeroFromScroll() }
            lastViewType = savedViewType
''',1)

anchor='''    private fun submitGameList(games: List<Game>) {
        val adapter = (binding.gridGames as? RecyclerView)?.adapter as? GameAdapter
'''
assert anchor in s
s=s.replace(anchor,'''    private fun submitGameList(games: List<Game>) {
        displayedGames = games
        updateLibraryHeroSelection(games)
        val adapter = (binding.gridGames as? RecyclerView)?.adapter as? GameAdapter
''',1)

anchor='''        if (getCurrentViewType() == GameAdapter.VIEW_TYPE_CAROUSEL) {
            (binding.gridGames as? CarouselRecyclerView)?.setupCarousel(true)
            (binding.gridGames as? CarouselRecyclerView)?.restoreScrollState(gamesViewModel.lastScrollPosition)
        }
    }
'''
assert anchor in s
s=s.replace(anchor,'''        if (getCurrentViewType() == GameAdapter.VIEW_TYPE_CAROUSEL) {
            (binding.gridGames as? CarouselRecyclerView)?.setupCarousel(true)
            (binding.gridGames as? CarouselRecyclerView)?.restoreScrollState(gamesViewModel.lastScrollPosition)
        }
        highlightedGame?.let { showLibraryHero(it, true) }
    }
''',1)

anchor='    private fun focusSearch() {\n'
assert anchor in s
methods=r'''    private fun updateLibraryHeroSelection(games: List<Game>) {
        if (_binding == null) return
        if (games.isEmpty()) {
            highlightedGame = null
            binding.libraryHeroTitle.setText(R.string.mw_home_frontend_empty_title)
            binding.libraryHeroMeta.setText(R.string.mw_home_frontend_empty_meta)
            binding.libraryHeroOpen.isEnabled = false
            binding.libraryHeroBackdrop.setImageDrawable(null)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) binding.libraryHeroBackdrop.setRenderEffect(null)
            return
        }
        val current = highlightedGame?.let { selected ->
            games.firstOrNull { it.programId == selected.programId && it.path == selected.path }
        }
        val target = current ?: games.maxByOrNull { preferences.getLong(it.keyLastPlayedTime, 0L) } ?: games.first()
        showLibraryHero(target)
    }

    private fun updateLibraryHeroFromScroll() {
        if (_binding == null || displayedGames.isEmpty()) return
        val recycler = binding.gridGames as? RecyclerView ?: return
        val position = when (val lm = recycler.layoutManager) {
            is GridLayoutManager -> lm.findFirstVisibleItemPosition()
            is LinearLayoutManager -> if (getCurrentViewType() == GameAdapter.VIEW_TYPE_CAROUSEL)
                (recycler as? CarouselRecyclerView)?.getClosestChildPosition() ?: lm.findFirstVisibleItemPosition()
            else lm.findFirstVisibleItemPosition()
            else -> RecyclerView.NO_POSITION
        }
        if (position in displayedGames.indices) showLibraryHero(displayedGames[position])
    }

    private fun showLibraryHero(game: Game, forceArtworkReload: Boolean = false) {
        if (_binding == null) return
        val same = highlightedGame?.let { it.programId == game.programId && it.path == game.path } == true
        highlightedGame = game
        binding.libraryHeroTitle.text = game.title.replace("[\\t\\n\\r]+".toRegex(), " ")
        binding.libraryHeroMeta.text = buildHeroMeta(game)
        binding.libraryHeroOpen.isEnabled = true
        if (!same || forceArtworkReload) loadLibraryHeroArtwork(game)
    }

    private fun buildHeroMeta(game: Game): String {
        val parts = buildList {
            if (game.developer.isNotBlank()) add(game.developer)
            if (game.version.isNotBlank()) add(game.version)
        }
        return if (parts.isEmpty()) getString(R.string.mw_home_frontend_switch_game) else parts.joinToString(" • ")
    }

    private fun gameAssetDirectory(game: Game) = File(
        DirectoryInitialization.userDirectory + "/moonwitch/metadata/" + game.settingsName
    )

    private fun findLibraryArtwork(game: Game): Pair<File, Boolean>? {
        val dir = gameAssetDirectory(game)
        val heroes = listOf("hero.jpg","hero.jpeg","hero.png","hero.webp","background.jpg","background.jpeg","background.png","background.webp")
        heroes.asSequence().map { File(dir,it) }.firstOrNull(File::isFile)?.let { return it to true }
        val covers = listOf("cover.jpg","cover.jpeg","cover.png","cover.webp","poster.jpg","poster.jpeg","poster.png","poster.webp","boxart.jpg","boxart.jpeg","boxart.png","boxart.webp")
        return covers.asSequence().map { File(dir,it) }.firstOrNull(File::isFile)?.let { it to false }
    }

    private fun loadLibraryHeroArtwork(game: Game) {
        val generation = ++heroLoadGeneration
        val custom = findLibraryArtwork(game)
        if (custom == null) return applyLibraryHeroFallback(game, generation)
        viewLifecycleOwner.lifecycleScope.launch {
            val bitmap = withContext(Dispatchers.IO) { decodeLibraryArtwork(custom.first) }
            if (_binding == null || generation != heroLoadGeneration) return@launch
            if (bitmap == null) return@launch applyLibraryHeroFallback(game, generation)
            binding.libraryHeroBackdrop.animate().cancel()
            binding.libraryHeroBackdrop.alpha = 0f
            binding.libraryHeroBackdrop.setImageBitmap(bitmap)
            binding.libraryHeroBackdrop.scaleType = ImageView.ScaleType.CENTER_CROP
            binding.libraryHeroBackdrop.scaleX = 1f
            binding.libraryHeroBackdrop.scaleY = 1f
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                binding.libraryHeroBackdrop.setRenderEffect(
                    if (custom.second) null else RenderEffect.createBlurEffect(18f,18f,Shader.TileMode.CLAMP)
                )
            }
            binding.libraryHeroBackdrop.animate().alpha(if (custom.second) 0.88f else 0.44f).setDuration(180L).start()
        }
    }

    private fun applyLibraryHeroFallback(game: Game, generation: Int) {
        if (_binding == null || generation != heroLoadGeneration) return
        binding.libraryHeroBackdrop.animate().cancel()
        binding.libraryHeroBackdrop.alpha = 0.28f
        binding.libraryHeroBackdrop.scaleType = ImageView.ScaleType.CENTER_CROP
        binding.libraryHeroBackdrop.scaleX = 1.22f
        binding.libraryHeroBackdrop.scaleY = 1.22f
        GameIconUtils.loadGameIcon(game, binding.libraryHeroBackdrop)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            binding.libraryHeroBackdrop.setRenderEffect(RenderEffect.createBlurEffect(34f,34f,Shader.TileMode.CLAMP))
        }
    }

    private fun decodeLibraryArtwork(file: File) = runCatching {
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeFile(file.absolutePath,bounds)
        var sample = 1
        while (bounds.outWidth > 0 && bounds.outHeight > 0 && (bounds.outWidth/sample > 1920 || bounds.outHeight/sample > 1920)) sample *= 2
        BitmapFactory.decodeFile(file.absolutePath, BitmapFactory.Options().apply { inSampleSize = sample })
    }.getOrNull()

    private fun openGameHub(game: Game) {
        val exists = DocumentFile.fromSingleUri(requireContext(), android.net.Uri.parse(game.path))?.exists() == true
        if (!exists) {
            Toast.makeText(requireContext(), R.string.loader_error_file_not_found, Toast.LENGTH_LONG).show()
            gamesViewModel.reloadGames(true)
            return
        }
        findNavController().navigate(HomeNavigationDirections.actionGlobalPerGamePropertiesFragment(game))
    }

    private fun focusSearch() {
'''
s=s.replace(anchor,methods,1)
p.write_text(s)
