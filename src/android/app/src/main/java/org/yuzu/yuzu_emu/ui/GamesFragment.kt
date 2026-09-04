// SPDX-FileCopyrightText: Copyright 2026 Eden Emulator Project
// SPDX-License-Identifier: GPL-3.0-or-later

package org.yuzu.yuzu_emu.ui

import android.annotation.SuppressLint
import android.content.Context
import android.content.Intent
import android.content.res.Configuration
import android.graphics.BitmapFactory
import android.graphics.RenderEffect
import android.graphics.Shader
import android.os.Build
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.view.inputmethod.InputMethodManager
import android.widget.ImageView
import android.widget.PopupMenu
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.doOnPreDraw
import androidx.core.view.updatePadding
import androidx.core.widget.doOnTextChanged
import androidx.documentfile.provider.DocumentFile
import androidx.fragment.app.Fragment
import androidx.fragment.app.activityViewModels
import androidx.lifecycle.lifecycleScope
import androidx.navigation.fragment.findNavController
import androidx.preference.PreferenceManager
import androidx.recyclerview.widget.RecyclerView
import androidx.recyclerview.widget.GridLayoutManager
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout
import org.yuzu.yuzu_emu.HomeNavigationDirections
import org.yuzu.yuzu_emu.NativeLibrary
import org.yuzu.yuzu_emu.R
import org.yuzu.yuzu_emu.YuzuApplication
import org.yuzu.yuzu_emu.adapters.GameAdapter
import org.yuzu.yuzu_emu.databinding.FragmentGamesBinding
import org.yuzu.yuzu_emu.features.settings.model.BooleanSetting
import org.yuzu.yuzu_emu.model.AppletInfo
import org.yuzu.yuzu_emu.model.Game
import org.yuzu.yuzu_emu.model.GamesViewModel
import org.yuzu.yuzu_emu.model.HomeViewModel
import org.yuzu.yuzu_emu.ui.main.MainActivity
import org.yuzu.yuzu_emu.utils.DirectoryInitialization
import org.yuzu.yuzu_emu.utils.GameIconUtils
import org.yuzu.yuzu_emu.utils.ViewUtils.setVisible
import org.yuzu.yuzu_emu.utils.collect
import info.debatty.java.stringsimilarity.Jaccard
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import info.debatty.java.stringsimilarity.JaroWinkler
import java.io.File
import java.util.Locale
import androidx.core.content.edit
import androidx.core.view.doOnNextLayout

class GamesFragment : Fragment() {
    private var _binding: FragmentGamesBinding? = null
    private val binding get() = _binding!!

    private var originalHeaderTopMargin: Int? = null
    private var originalHeaderBottomMargin: Int? = null
    private var originalHeaderRightMargin: Int? = null
    private var originalHeaderLeftMargin: Int? = null

    private var lastViewType: Int = GameAdapter.VIEW_TYPE_GRID
    private var fallbackBottomInset: Int = 0
    private var pendingPostReloadListSettle = false
    private var pendingPostReloadListSettleGeneration = 0
    private var gameListSubmitGeneration = 0
    private var committedGameListSubmitGeneration = 0
    private var highlightedGame: Game? = null
    private var displayedGames: List<Game> = emptyList()
    private var heroLoadGeneration = 0

    private val heroScrollListener = object : RecyclerView.OnScrollListener() {
        override fun onScrolled(recyclerView: RecyclerView, dx: Int, dy: Int) = updateLibraryHeroFromScroll()
        override fun onScrollStateChanged(recyclerView: RecyclerView, newState: Int) {
            if (newState == RecyclerView.SCROLL_STATE_IDLE) updateLibraryHeroFromScroll()
        }
    }

    companion object {
        private const val SEARCH_TEXT = "SearchText"
        private const val PREF_SORT_TYPE = "GamesSortType"
    }

    private val gamesViewModel: GamesViewModel by activityViewModels()
    private val homeViewModel: HomeViewModel by activityViewModels()
    private lateinit var gameAdapter: GameAdapter

    private val preferences =
        PreferenceManager.getDefaultSharedPreferences(YuzuApplication.appContext)

    private lateinit var mainActivity: MainActivity
    private val getGamesDirectory =
        registerForActivityResult(ActivityResultContracts.OpenDocumentTree()) { result ->
            if (result != null) {
                mainActivity.processGamesDir(result, true)
            }
        }

    private fun getCurrentViewType(): Int {
        val isLandscape = resources.configuration.orientation == Configuration.ORIENTATION_LANDSCAPE
        val key = if (isLandscape) CarouselRecyclerView.CAROUSEL_VIEW_TYPE_LANDSCAPE else CarouselRecyclerView.CAROUSEL_VIEW_TYPE_PORTRAIT
        val fallback = if (isLandscape) GameAdapter.VIEW_TYPE_CAROUSEL else GameAdapter.VIEW_TYPE_GRID
        return preferences.getInt(key, fallback)
    }

    private fun setCurrentViewType(type: Int) {
        val isLandscape = resources.configuration.orientation == Configuration.ORIENTATION_LANDSCAPE
        val key = if (isLandscape) CarouselRecyclerView.CAROUSEL_VIEW_TYPE_LANDSCAPE else CarouselRecyclerView.CAROUSEL_VIEW_TYPE_PORTRAIT
        preferences.edit { putInt(key, type) }
    }
    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        _binding = FragmentGamesBinding.inflate(inflater)
        return binding.root
    }

    @SuppressLint("NotifyDataSetChanged")
    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        homeViewModel.setStatusBarShadeVisibility(true)
        mainActivity = requireActivity() as MainActivity

        if (savedInstanceState != null) {
            binding.searchText.setText(savedInstanceState.getString(SEARCH_TEXT))
        }

        gameAdapter = GameAdapter(
            requireActivity() as AppCompatActivity
        )

        applyGridGamesBinding()

        binding.libraryHeroOpen.setOnClickListener {
            highlightedGame?.let(::openGameHub)
        }

        binding.swipeRefresh.apply {
            (binding.swipeRefresh as? SwipeRefreshLayout)?.setOnRefreshListener {
                gamesViewModel.reloadGames(false)
            }
            (binding.swipeRefresh as? SwipeRefreshLayout)?.setProgressBackgroundColorSchemeColor(
                com.google.android.material.color.MaterialColors.getColor(
                    binding.swipeRefresh,
                    com.google.android.material.R.attr.colorPrimary
                )
            )
            (binding.swipeRefresh as? SwipeRefreshLayout)?.setColorSchemeColors(
                com.google.android.material.color.MaterialColors.getColor(
                    binding.swipeRefresh,
                    com.google.android.material.R.attr.colorOnPrimary
                )
            )
            post {
                if (_binding == null) {
                    return@post
                }
                (binding.swipeRefresh as? SwipeRefreshLayout)?.isRefreshing = gamesViewModel.isReloading.value
            }
        }

        gamesViewModel.isReloading.collect(viewLifecycleOwner) {
            (binding.swipeRefresh as? SwipeRefreshLayout)?.isRefreshing = it
            binding.noticeText.setVisible(
                visible = gamesViewModel.games.value.isEmpty() && !it,
                gone = false
            )
        }
        gamesViewModel.games.collect(viewLifecycleOwner) {
            setAdapter(it)
        }
        gamesViewModel.shouldSwapData.collect(
            viewLifecycleOwner,
            resetState = { gamesViewModel.setShouldSwapData(false) }
        ) {
            if (it) {
                setAdapter(gamesViewModel.games.value)
            }
        }
        gamesViewModel.shouldScrollToTop.collect(
            viewLifecycleOwner,
            resetState = { gamesViewModel.setShouldScrollToTop(false) }
        ) { if (it) scrollToTop() }

        gamesViewModel.shouldScrollAfterReload.collect(viewLifecycleOwner) { shouldScroll ->
            if (shouldScroll) {
                pendingPostReloadListSettle = true
                pendingPostReloadListSettleGeneration = gameListSubmitGeneration
                schedulePostReloadListSettle()
                gamesViewModel.setShouldScrollAfterReload(false)
            }
        }

        setupTopView()

        updateButtonsVisibility()

        binding.addDirectory.setOnClickListener {
            getGamesDirectory.launch(Intent(Intent.ACTION_OPEN_DOCUMENT_TREE).data)
        }

        binding.launchQlaunch?.setOnClickListener {
            launchQLaunch()
        }

        setInsets()
    }

    val applyGridGamesBinding = {
        (binding.gridGames as? RecyclerView)?.apply {
            val isLandscape = resources.configuration.orientation == Configuration.ORIENTATION_LANDSCAPE
            val currentViewType = getCurrentViewType()
            val savedViewType = if (isLandscape || currentViewType != GameAdapter.VIEW_TYPE_CAROUSEL) currentViewType else GameAdapter.VIEW_TYPE_GRID

            //This prevents Grid/List views from reusing scaled or otherwise modified ViewHolders left over from the carousel.
            adapter = null
            recycledViewPool.clear()

            gameAdapter.setViewType(savedViewType)
            currentFilter = normalizeStoredFilter(
                preferences.getInt(PREF_SORT_TYPE, R.id.alphabetical)
            )
            preferences.edit { putInt(PREF_SORT_TYPE, currentFilter) }

            // Set the correct layout manager
            layoutManager = when (savedViewType) {
                GameAdapter.VIEW_TYPE_GRID -> {
                    val columns = resources.getInteger(R.integer.game_columns_grid)
                    GridLayoutManager(context, columns)
                }
                GameAdapter.VIEW_TYPE_GRID_COMPACT -> {
                    val columns = resources.getInteger(R.integer.game_columns_grid)
                    GridLayoutManager(context, columns)
                }
                GameAdapter.VIEW_TYPE_LIST -> {
                    val columns = resources.getInteger(R.integer.game_columns_list)
                    GridLayoutManager(context, columns)
                }
                GameAdapter.VIEW_TYPE_CAROUSEL -> {
                    LinearLayoutManager(context, RecyclerView.HORIZONTAL, false)
                }
                else -> throw IllegalArgumentException("Invalid view type: $savedViewType")
            }
            if (savedViewType == GameAdapter.VIEW_TYPE_CAROUSEL) {
                (binding.gridGames as? View)?.let { it -> ViewCompat.requestApplyInsets(it)}
                doOnNextLayout { //Carousel: important to avoid overlap issues
                    (this as? CarouselRecyclerView)?.notifyLaidOut(fallbackBottomInset)
                }
            } else {
                (this as? CarouselRecyclerView)?.setupCarousel(false)
            }
            adapter = gameAdapter
            removeOnScrollListener(heroScrollListener)
            addOnScrollListener(heroScrollListener)
            post { updateLibraryHeroFromScroll() }
            lastViewType = savedViewType
        }
    }

    override fun onSaveInstanceState(outState: Bundle) {
        super.onSaveInstanceState(outState)
        if (_binding != null) {
            outState.putString(SEARCH_TEXT, binding.searchText.text.toString())
        }
    }
    override fun onPause() {
        super.onPause()
        if (getCurrentViewType() == GameAdapter.VIEW_TYPE_CAROUSEL) {
            gamesViewModel.lastScrollPosition = (binding.gridGames as? CarouselRecyclerView)?.getClosestChildPosition() ?: 0
        }
    }

    override fun onResume() {
        super.onResume()
        if (_binding == null) return
        updateButtonsVisibility()
        if (getCurrentViewType() == GameAdapter.VIEW_TYPE_CAROUSEL) {
            (binding.gridGames as? CarouselRecyclerView)?.setupCarousel(true)
            (binding.gridGames as? CarouselRecyclerView)?.restoreScrollState(gamesViewModel.lastScrollPosition)
        }
        highlightedGame?.let { showLibraryHero(it, true) }
    }

    private fun setAdapter(games: List<Game>) = filterAndSearch(games)

    private fun submitGameList(games: List<Game>) {
        displayedGames = games
        updateLibraryHeroSelection(games)
        val adapter = (binding.gridGames as? RecyclerView)?.adapter as? GameAdapter
        if (adapter == null) {
            schedulePostReloadListSettle()
            return
        }

        val submitGeneration = ++gameListSubmitGeneration
        adapter.submitList(games) {
            if (committedGameListSubmitGeneration < submitGeneration) {
                committedGameListSubmitGeneration = submitGeneration
            }
            schedulePostReloadListSettle()
        }
    }


    private fun schedulePostReloadListSettle() {
        if (!pendingPostReloadListSettle || _binding == null) return

        binding.gridGames.doOnPreDraw {
            if (!pendingPostReloadListSettle || _binding == null) return@doOnPreDraw
            if (committedGameListSubmitGeneration < pendingPostReloadListSettleGeneration) {
                schedulePostReloadListSettle()
                return@doOnPreDraw
            }
            pendingPostReloadListSettle = false

            (binding.gridGames as? CarouselRecyclerView)?.refreshView()
        }
    }
    private fun setupTopView() {
        binding.searchText.doOnTextChanged() { text: CharSequence?, _: Int, _: Int, _: Int ->
            if (text.toString().isNotEmpty()) {
                binding.clearButton.visibility = View.VISIBLE
            } else {
                binding.clearButton.visibility = View.INVISIBLE
            }
            filterAndSearch()
        }

        binding.clearButton.setOnClickListener { binding.searchText.setText("") }
        binding.searchBackground.setOnClickListener { focusSearch() }

        // Setup view button
        binding.viewButton.setOnClickListener { showViewMenu(it) }

        // Setup filter button
        binding.filterButton.setOnClickListener { view ->
            showFilterMenu(view)
        }

        // Setup settings button
        binding.settingsButton.setOnClickListener { navigateToSettings() }
    }

    private fun navigateToSettings() {
        val navController = findNavController()
        navController.navigate(R.id.action_gamesFragment_to_homeSettingsFragment)
    }

    private fun showViewMenu(anchor: View) {
        val popup = PopupMenu(requireContext(), anchor)
        popup.menuInflater.inflate(R.menu.menu_game_views, popup.menu)
        val isLandscape = resources.configuration.orientation == Configuration.ORIENTATION_LANDSCAPE
        if (!isLandscape) {
            popup.menu.findItem(R.id.view_carousel)?.isVisible = false
        }

        val currentViewType = getCurrentViewType()
        when (currentViewType) {
            GameAdapter.VIEW_TYPE_LIST -> popup.menu.findItem(R.id.view_list).isChecked = true
            GameAdapter.VIEW_TYPE_GRID_COMPACT -> popup.menu.findItem(R.id.view_grid_compact).isChecked = true
            GameAdapter.VIEW_TYPE_GRID -> popup.menu.findItem(R.id.view_grid).isChecked = true
            GameAdapter.VIEW_TYPE_CAROUSEL -> popup.menu.findItem(R.id.view_carousel).isChecked = true
        }

        popup.setOnMenuItemClickListener { item ->
            when (item.itemId) {
                R.id.view_grid -> {
                    if (getCurrentViewType() == GameAdapter.VIEW_TYPE_CAROUSEL) onPause()
                    setCurrentViewType(GameAdapter.VIEW_TYPE_GRID)
                    applyGridGamesBinding()
                    filterAndSearch()
                    item.isChecked = true
                    true
                }

                R.id.view_grid_compact -> {
                    if (getCurrentViewType() == GameAdapter.VIEW_TYPE_CAROUSEL) onPause()
                    setCurrentViewType(GameAdapter.VIEW_TYPE_GRID_COMPACT)
                    applyGridGamesBinding()
                    filterAndSearch()
                    item.isChecked = true
                    true
                }

                R.id.view_list -> {
                    if (getCurrentViewType() == GameAdapter.VIEW_TYPE_CAROUSEL) onPause()
                    setCurrentViewType(GameAdapter.VIEW_TYPE_LIST)
                    applyGridGamesBinding()
                    filterAndSearch()
                    item.isChecked = true
                    true
                }

                R.id.view_carousel -> {
                    if (!item.isChecked || getCurrentViewType() != GameAdapter.VIEW_TYPE_CAROUSEL) {
                        setCurrentViewType(GameAdapter.VIEW_TYPE_CAROUSEL)
                        applyGridGamesBinding()
                        filterAndSearch()
                        item.isChecked = true
                        onResume()
                    }
                    true
                }

                else -> false
            }
        }

        popup.show()
    }

    private fun showFilterMenu(anchor: View) {
        val popup = PopupMenu(requireContext(), anchor)
        popup.menuInflater.inflate(R.menu.menu_game_filters, popup.menu)

        // Set checked state based on current filter
        when (currentFilter) {
            R.id.alphabetical -> popup.menu.findItem(R.id.alphabetical).isChecked = true
            R.id.filter_recently_played -> popup.menu.findItem(R.id.filter_recently_played).isChecked =
                true

            R.id.filter_recently_added -> popup.menu.findItem(R.id.filter_recently_added).isChecked =
                true
            R.id.filter_favorites -> popup.menu.findItem(R.id.filter_favorites).isChecked = true
        }

        popup.setOnMenuItemClickListener { item ->
            currentFilter = item.itemId
            preferences.edit { putInt(PREF_SORT_TYPE, currentFilter) }
            filterAndSearch()
            true
        }

        popup.show()
    }

    // Track current filter
    private var currentFilter = normalizeStoredFilter(
        preferences.getInt(PREF_SORT_TYPE, R.id.alphabetical)
    )

    private fun filterAndSearch(baseList: List<Game> = gamesViewModel.games.value) {
        val filteredList: List<Game> = when (currentFilter) {
            R.id.alphabetical -> baseList.sortedBy { it.title.lowercase(Locale.getDefault()) }
            R.id.filter_recently_played -> baseList
                .filter { preferences.getLong(it.keyLastPlayedTime, 0L) > 0L }
                .sortedByDescending { preferences.getLong(it.keyLastPlayedTime, 0L) }
            R.id.filter_recently_added -> baseList
                .filter { preferences.getLong(it.keyAddedToLibraryTime, 0L) > 0L }
                .sortedByDescending { preferences.getLong(it.keyAddedToLibraryTime, 0L) }
            R.id.filter_favorites -> baseList
                .filter { preferences.getBoolean(it.keyFavorite, false) }
                .sortedBy { it.title.lowercase(Locale.getDefault()) }
            else -> baseList
        }

        val searchTerm = binding.searchText.text.toString().trim().lowercase(Locale.getDefault())
        if (searchTerm.isEmpty()) {
            submitGameList(filteredList)
            gamesViewModel.setFilteredGames(filteredList)
            return
        }

        val searchAlgorithm = if (searchTerm.length > 1) Jaccard(2) else JaroWinkler()
        val sortedList = filteredList.mapNotNull { game ->
            val title = game.title.lowercase(Locale.getDefault())
            val score = searchAlgorithm.similarity(searchTerm, title)
            if (score > 0.03) {
                ScoredGame(score, game)
            } else {
                null
            }
        }.sortedByDescending { it.score }.map { it.item }

        submitGameList(sortedList)
        gamesViewModel.setFilteredGames(sortedList)
    }

    private inner class ScoredGame(val score: Double, val item: Game)

    private fun updateLibraryHeroSelection(games: List<Game>) {
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
            is LinearLayoutManager -> {
                if (getCurrentViewType() == GameAdapter.VIEW_TYPE_CAROUSEL) {
                    (recycler as? CarouselRecyclerView)?.getClosestChildPosition()
                        ?: lm.findFirstVisibleItemPosition()
                } else {
                    lm.findFirstVisibleItemPosition()
                }
            }
            else -> RecyclerView.NO_POSITION
        }
        if (position in displayedGames.indices) {
            showLibraryHero(displayedGames[position])
        }
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
        binding.searchText.requestFocus()
        val imm = requireActivity()
            .getSystemService(Context.INPUT_METHOD_SERVICE) as InputMethodManager?
        imm?.showSoftInput(binding.searchText, InputMethodManager.SHOW_IMPLICIT)
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _binding = null
    }

    private fun scrollToTop() {
        if (_binding == null) return
        (binding.gridGames as? RecyclerView)?.let { gamesView ->
            if (gamesView.adapter?.itemCount != 0) gamesView.scrollToPosition(0)
        }
    }

    private fun normalizeStoredFilter(filter: Int): Int = when (filter) {
        R.id.alphabetical,
        R.id.filter_recently_played,
        R.id.filter_recently_added,
        R.id.filter_favorites -> filter
        else -> R.id.alphabetical
    }

    private fun launchQLaunch() {
        try {
            val appletPath = NativeLibrary.getAppletLaunchPath(AppletInfo.QLaunch.entryId)
            if (appletPath.isEmpty()) {
                Toast.makeText(
                    requireContext(),
                    R.string.applets_error_applet,
                    Toast.LENGTH_SHORT
                ).show()
                return
            }

            NativeLibrary.setCurrentAppletId(AppletInfo.QLaunch.appletId)

            val qlaunchGame = Game(
                title = getString(R.string.qlaunch_applet),
                path = appletPath
            )

            val action = HomeNavigationDirections.actionGlobalEmulationActivity(qlaunchGame)
            findNavController().navigate(action)
        } catch (e: Exception) {
            Toast.makeText(
                requireContext(),
                "Failed to launch QLaunch: ${e.message}",
                Toast.LENGTH_SHORT
            ).show()
        }
    }

    private fun updateButtonsVisibility() {
        val showQLaunch = BooleanSetting.ENABLE_QLAUNCH_BUTTON.getBoolean()
        val showFolder = BooleanSetting.ENABLE_FOLDER_BUTTON.getBoolean()
        val isFirmwareAvailable = NativeLibrary.isFirmwareAvailable()

        val shouldShowQLaunch = showQLaunch && isFirmwareAvailable
        binding.launchQlaunch.visibility = if (shouldShowQLaunch) View.VISIBLE else View.GONE

        binding.addDirectory.visibility = if (showFolder) View.VISIBLE else View.GONE
    }

    private fun setInsets() =
        ViewCompat.setOnApplyWindowInsetsListener(
            binding.root
        ) { _: View, windowInsets: WindowInsetsCompat ->
            val barInsets = windowInsets.getInsets(WindowInsetsCompat.Type.systemBars())
            val cutoutInsets = windowInsets.getInsets(WindowInsetsCompat.Type.displayCutout())
            val spacingNavigation = resources.getDimensionPixelSize(R.dimen.spacing_navigation)
            resources.getDimensionPixelSize(R.dimen.spacing_navigation_rail)

            (binding.swipeRefresh as? SwipeRefreshLayout)?.setProgressViewEndTarget(
                false,
                barInsets.top + resources.getDimensionPixelSize(R.dimen.spacing_refresh_end)
            )

            val leftInset = barInsets.left + cutoutInsets.left
            val rightInset = barInsets.right + cutoutInsets.right
            val topInset = maxOf(barInsets.top, cutoutInsets.top)

            val mlpSwipe = binding.swipeRefresh.layoutParams as ViewGroup.MarginLayoutParams
            mlpSwipe.leftMargin = leftInset
            mlpSwipe.rightMargin = rightInset
            binding.swipeRefresh.layoutParams = mlpSwipe

            val mlpHeader = binding.header.layoutParams as ViewGroup.MarginLayoutParams

            // Store original margins only once
            if (originalHeaderTopMargin == null) {
                originalHeaderTopMargin = mlpHeader.topMargin
                originalHeaderRightMargin = mlpHeader.rightMargin
                originalHeaderLeftMargin = mlpHeader.leftMargin
            }

            // Always set margin as original + insets
            mlpHeader.leftMargin = (originalHeaderLeftMargin ?: 0) + leftInset
            mlpHeader.rightMargin = (originalHeaderRightMargin ?: 0) + rightInset
            mlpHeader.topMargin = (originalHeaderTopMargin ?: 0) + topInset + resources.getDimensionPixelSize(
                R.dimen.spacing_med
            )
            binding.header.layoutParams = mlpHeader

            binding.noticeText.updatePadding(bottom = spacingNavigation)

            binding.gridGames.updatePadding(
                top = resources.getDimensionPixelSize(R.dimen.spacing_med)
            )

            val mlpFab = binding.addDirectory.layoutParams as ViewGroup.MarginLayoutParams
            val fabPadding = resources.getDimensionPixelSize(R.dimen.spacing_large)
            mlpFab.leftMargin = leftInset + fabPadding
            mlpFab.bottomMargin = barInsets.bottom + fabPadding
            mlpFab.rightMargin = rightInset + fabPadding
            binding.addDirectory.layoutParams = mlpFab

            binding.launchQlaunch?.let { qlaunchButton ->
                val mlpQLaunch = qlaunchButton.layoutParams as ViewGroup.MarginLayoutParams
                mlpQLaunch.leftMargin = leftInset + fabPadding
                mlpQLaunch.bottomMargin = barInsets.bottom + fabPadding
                qlaunchButton.layoutParams = mlpQLaunch
            }

            val navInsets = windowInsets.getInsets(WindowInsetsCompat.Type.navigationBars())
            val gestureInsets = windowInsets.getInsets(WindowInsetsCompat.Type.systemGestures())
            val bottomInset = maxOf(navInsets.bottom, gestureInsets.bottom, cutoutInsets.bottom)
            fallbackBottomInset = bottomInset
            (binding.gridGames as? CarouselRecyclerView)?.notifyInsetsReady(bottomInset)
            windowInsets
        }
}