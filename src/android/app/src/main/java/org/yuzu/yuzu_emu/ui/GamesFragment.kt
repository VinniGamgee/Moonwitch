// SPDX-FileCopyrightText: Copyright 2026 Eden Emulator Project
// SPDX-License-Identifier: GPL-3.0-or-later

package org.yuzu.yuzu_emu.ui

import android.annotation.SuppressLint
import android.content.Context
import android.content.Intent
import android.content.res.ColorStateList
import android.content.res.Configuration
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.view.inputmethod.InputMethodManager
import android.widget.PopupMenu
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.core.content.edit
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.doOnNextLayout
import androidx.core.view.doOnPreDraw
import androidx.core.view.updatePadding
import androidx.core.widget.doOnTextChanged
import androidx.fragment.app.Fragment
import androidx.fragment.app.activityViewModels
import androidx.navigation.fragment.findNavController
import androidx.preference.PreferenceManager
import androidx.recyclerview.widget.GridLayoutManager
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout
import info.debatty.java.stringsimilarity.Jaccard
import info.debatty.java.stringsimilarity.JaroWinkler
import java.util.Locale
import org.yuzu.yuzu_emu.HomeNavigationDirections
import org.yuzu.yuzu_emu.R
import org.yuzu.yuzu_emu.YuzuApplication
import org.yuzu.yuzu_emu.adapters.GameAdapter
import org.yuzu.yuzu_emu.databinding.FragmentGamesBinding
import org.yuzu.yuzu_emu.features.settings.ui.SettingsSubscreen
import org.yuzu.yuzu_emu.model.Game
import org.yuzu.yuzu_emu.model.GamesViewModel
import org.yuzu.yuzu_emu.model.HomeViewModel
import org.yuzu.yuzu_emu.ui.main.MainActivity
import org.yuzu.yuzu_emu.utils.ViewUtils.setVisible
import org.yuzu.yuzu_emu.utils.collect

class GamesFragment : Fragment() {
    private var _binding: FragmentGamesBinding? = null
    private val binding get() = _binding!!

    private var lastViewType: Int = GameAdapter.VIEW_TYPE_GRID
    private var fallbackBottomInset: Int = 0
    private var pendingPostReloadListSettle = false
    private var pendingPostReloadListSettleGeneration = 0
    private var gameListSubmitGeneration = 0
    private var committedGameListSubmitGeneration = 0
    private var frontendPage = 0
    private var frontendFilter = 0

    companion object {
        private const val SEARCH_TEXT = "SearchText"
        private const val PREF_SORT_TYPE = "GamesSortType"
        private const val PREF_FRONTEND_PAGE = "MoonwitchFrontendPage"
        private const val MENU_ADD_FOLDER = 7001
        private const val MENU_MANAGE_FOLDERS = 7002
        private const val MENU_VIEW = 7003
    }

    private val gamesViewModel: GamesViewModel by activityViewModels()
    private val homeViewModel: HomeViewModel by activityViewModels()
    private lateinit var gameAdapter: GameAdapter

    private val preferences = PreferenceManager.getDefaultSharedPreferences(YuzuApplication.appContext)

    private lateinit var mainActivity: MainActivity
    private val getGamesDirectory = registerForActivityResult(ActivityResultContracts.OpenDocumentTree()) { result ->
        if (result != null) mainActivity.processGamesDir(result, true)
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

    override fun onCreateView(inflater: LayoutInflater, container: ViewGroup?, savedInstanceState: Bundle?): View {
        _binding = FragmentGamesBinding.inflate(inflater)
        return binding.root
    }

    @SuppressLint("NotifyDataSetChanged")
    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        homeViewModel.setStatusBarShadeVisibility(true)
        mainActivity = requireActivity() as MainActivity

        if (savedInstanceState != null) binding.searchText.setText(savedInstanceState.getString(SEARCH_TEXT))

        gameAdapter = GameAdapter(requireActivity() as AppCompatActivity)
        applyGridGamesBinding()

        binding.swipeRefresh.apply {
            (this as? SwipeRefreshLayout)?.setOnRefreshListener { gamesViewModel.reloadGames(false) }
            (this as? SwipeRefreshLayout)?.setProgressBackgroundColorSchemeColor(
                ContextCompat.getColor(requireContext(), R.color.mw_ui_surface)
            )
            (this as? SwipeRefreshLayout)?.setColorSchemeColors(
                ContextCompat.getColor(requireContext(), R.color.mw_ui_accent)
            )
            post {
                if (_binding != null) (binding.swipeRefresh as? SwipeRefreshLayout)?.isRefreshing = gamesViewModel.isReloading.value
            }
        }

        gamesViewModel.isReloading.collect(viewLifecycleOwner) {
            (binding.swipeRefresh as? SwipeRefreshLayout)?.isRefreshing = it
            binding.noticeText.setVisible(gamesViewModel.games.value.isEmpty() && !it, gone = false)
        }
        gamesViewModel.games.collect(viewLifecycleOwner) {
            updateLibraryCount(it.size)
            setAdapter(it)
        }
        gamesViewModel.shouldSwapData.collect(viewLifecycleOwner, resetState = { gamesViewModel.setShouldSwapData(false) }) {
            if (it) setAdapter(gamesViewModel.games.value)
        }
        gamesViewModel.shouldScrollToTop.collect(viewLifecycleOwner, resetState = { gamesViewModel.setShouldScrollToTop(false) }) {
            if (it) scrollToTop()
        }
        gamesViewModel.shouldScrollAfterReload.collect(viewLifecycleOwner) { shouldScroll ->
            if (shouldScroll) {
                pendingPostReloadListSettle = true
                pendingPostReloadListSettleGeneration = gameListSubmitGeneration
                schedulePostReloadListSettle()
                gamesViewModel.setShouldScrollAfterReload(false)
            }
        }

        setupTopView()
        setupFrontendNavigation()
        setFrontendPage(preferences.getInt(PREF_FRONTEND_PAGE, 0), persist = false)
        setInsets()
    }

    val applyGridGamesBinding = {
        (binding.gridGames as? RecyclerView)?.apply {
            val isLandscape = resources.configuration.orientation == Configuration.ORIENTATION_LANDSCAPE
            val currentViewType = getCurrentViewType()
            val savedViewType = if (isLandscape || currentViewType != GameAdapter.VIEW_TYPE_CAROUSEL) currentViewType else GameAdapter.VIEW_TYPE_GRID
            adapter = null
            recycledViewPool.clear()
            gameAdapter.setViewType(savedViewType)
            currentFilter = normalizeStoredFilter(preferences.getInt(PREF_SORT_TYPE, View.NO_ID))
            preferences.edit { putInt(PREF_SORT_TYPE, currentFilter) }
            layoutManager = when (savedViewType) {
                GameAdapter.VIEW_TYPE_GRID -> GridLayoutManager(context, if (isLandscape) 5 else 3)
                GameAdapter.VIEW_TYPE_GRID_COMPACT -> GridLayoutManager(context, if (isLandscape) 6 else 3)
                GameAdapter.VIEW_TYPE_LIST -> LinearLayoutManager(context)
                GameAdapter.VIEW_TYPE_CAROUSEL -> LinearLayoutManager(context, RecyclerView.HORIZONTAL, false)
                else -> GridLayoutManager(context, if (isLandscape) 5 else 3)
            }
            if (savedViewType == GameAdapter.VIEW_TYPE_CAROUSEL) {
                (this as? CarouselRecyclerView)?.let { carousel ->
                    ViewCompat.requestApplyInsets(carousel)
                    doOnNextLayout { carousel.notifyLaidOut(fallbackBottomInset) }
                }
            } else {
                (this as? CarouselRecyclerView)?.setupCarousel(false)
            }
            adapter = gameAdapter
            lastViewType = savedViewType
        }
    }

    override fun onSaveInstanceState(outState: Bundle) {
        super.onSaveInstanceState(outState)
        if (_binding != null) outState.putString(SEARCH_TEXT, binding.searchText.text.toString())
    }

    override fun onPause() {
        super.onPause()
        if (getCurrentViewType() == GameAdapter.VIEW_TYPE_CAROUSEL) {
            gamesViewModel.lastScrollPosition = (binding.gridGames as? CarouselRecyclerView)?.getClosestChildPosition() ?: 0
        }
    }

    override fun onResume() {
        super.onResume()
        if (_binding != null) {
            val requestedPage = preferences.getInt(PREF_FRONTEND_PAGE, frontendPage)
            if (requestedPage != frontendPage) setFrontendPage(requestedPage, persist = false)
            if (getCurrentViewType() == GameAdapter.VIEW_TYPE_CAROUSEL) {
                (binding.gridGames as? CarouselRecyclerView)?.setupCarousel(true)
                (binding.gridGames as? CarouselRecyclerView)?.restoreScrollState(gamesViewModel.lastScrollPosition)
            }
        }
    }

    private fun setAdapter(games: List<Game>) = filterAndSearch(games)

    private fun submitGameList(games: List<Game>) {
        val adapter = (binding.gridGames as? RecyclerView)?.adapter as? GameAdapter ?: return
        val submitGeneration = ++gameListSubmitGeneration
        adapter.submitList(games) {
            if (committedGameListSubmitGeneration < submitGeneration) committedGameListSubmitGeneration = submitGeneration
            schedulePostReloadListSettle()
        }
    }

    private fun updateLibraryCount(count: Int) {
        binding.tabAllText.text = "${getString(R.string.mw_ui_all)}  $count"
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
        binding.searchText.doOnTextChanged { text: CharSequence?, _: Int, _: Int, _: Int ->
            binding.clearButton.visibility = if (text.isNullOrEmpty()) View.INVISIBLE else View.VISIBLE
            filterAndSearch()
        }
        binding.clearButton.setOnClickListener { binding.searchText.setText("") }
        binding.searchBackground.setOnClickListener { focusSearch() }
        binding.viewButton.setOnClickListener { showViewMenu(it) }
        binding.filterButton.setOnClickListener { showFilterMenu(it) }
        binding.headerSearchButton.setOnClickListener {
            if (frontendPage == 1) {
                binding.tabsContainer.visibility = View.GONE
                binding.searchTools.visibility = View.VISIBLE
            }
            focusSearch()
        }
        binding.headerMoreButton.setOnClickListener { showFrontendMenu(it) }
    }

    private fun setupFrontendNavigation() {
        binding.navHome.setOnClickListener { setFrontendPage(0) }
        binding.navGames.setOnClickListener { setFrontendPage(1) }
        binding.navSettings.setOnClickListener { navigateToSettings() }
        binding.tabAll.setOnClickListener { setFrontendFilter(0) }
        binding.tabRecent.setOnClickListener { setFrontendFilter(1) }
        binding.tabFavorites.setOnClickListener { setFrontendFilter(2) }
    }

    private fun setFrontendPage(page: Int, persist: Boolean = true) {
        frontendPage = if (page == 1) 1 else 0
        if (persist) preferences.edit { putInt(PREF_FRONTEND_PAGE, frontendPage) }
        frontendFilter = 0
        binding.searchText.setText("")
        if (frontendPage == 0) {
            binding.screenTitle.setText(R.string.mw_ui_library)
            binding.searchTools.visibility = View.VISIBLE
            binding.tabsContainer.visibility = View.GONE
            setCurrentViewType(GameAdapter.VIEW_TYPE_GRID)
        } else {
            binding.screenTitle.setText(R.string.mw_ui_games)
            binding.searchTools.visibility = View.GONE
            binding.tabsContainer.visibility = View.VISIBLE
            setCurrentViewType(GameAdapter.VIEW_TYPE_LIST)
        }
        updateNavState()
        updateTabState()
        applyGridGamesBinding()
        filterAndSearch()
        scrollToTop()
    }

    private fun setFrontendFilter(filter: Int) {
        frontendFilter = filter.coerceIn(0, 2)
        binding.searchTools.visibility = View.GONE
        binding.tabsContainer.visibility = View.VISIBLE
        updateTabState()
        filterAndSearch()
        scrollToTop()
    }

    private fun updateNavState() {
        val active = ContextCompat.getColor(requireContext(), R.color.mw_ui_accent)
        val activeText = ContextCompat.getColor(requireContext(), R.color.mw_ui_accent_hi)
        val muted = ContextCompat.getColor(requireContext(), R.color.mw_ui_text_2)
        val activeBg = ContextCompat.getColor(requireContext(), R.color.mw_ui_accent_soft)
        val clear = ContextCompat.getColor(requireContext(), android.R.color.transparent)

        val homeActive = frontendPage == 0
        binding.navHomeShell.setCardBackgroundColor(if (homeActive) activeBg else clear)
        binding.navGamesShell.setCardBackgroundColor(if (!homeActive) activeBg else clear)
        binding.navSettingsShell.setCardBackgroundColor(clear)
        binding.navHomeIcon.imageTintList = ColorStateList.valueOf(if (homeActive) active else muted)
        binding.navGamesIcon.imageTintList = ColorStateList.valueOf(if (!homeActive) active else muted)
        binding.navSettingsIcon.imageTintList = ColorStateList.valueOf(muted)
        binding.navHomeText.setTextColor(if (homeActive) activeText else muted)
        binding.navGamesText.setTextColor(if (!homeActive) activeText else muted)
        binding.navSettingsText.setTextColor(muted)
    }

    private fun updateTabState() {
        val accent = ContextCompat.getColor(requireContext(), R.color.mw_ui_accent)
        val activeBg = ContextCompat.getColor(requireContext(), R.color.mw_ui_accent_soft)
        val idleBg = ContextCompat.getColor(requireContext(), R.color.mw_ui_surface)
        val activeText = ContextCompat.getColor(requireContext(), R.color.mw_ui_accent_hi)
        val idleText = ContextCompat.getColor(requireContext(), R.color.mw_ui_text_2)
        val tabs = listOf(binding.tabAll, binding.tabRecent, binding.tabFavorites)
        val labels = listOf(binding.tabAllText, binding.tabRecentText, binding.tabFavoritesText)
        tabs.forEachIndexed { index, card ->
            val selected = index == frontendFilter
            card.setCardBackgroundColor(if (selected) activeBg else idleBg)
            card.strokeWidth = if (selected) resources.getDimensionPixelSize(R.dimen.mtrl_card_checked_icon_margin) / 8 + 1 else 0
            card.strokeColor = accent
            labels[index].setTextColor(if (selected) activeText else idleText)
        }
    }

    private fun navigateToSettings() {
        findNavController().navigate(R.id.action_gamesFragment_to_homeSettingsFragment)
    }

    private fun showFrontendMenu(anchor: View) {
        val popup = PopupMenu(requireContext(), anchor)
        popup.menu.add(0, MENU_ADD_FOLDER, 0, "Adicionar pasta de jogos")
        popup.menu.add(0, MENU_MANAGE_FOLDERS, 1, "Gerenciar pastas")
        popup.menu.add(0, MENU_VIEW, 2, "Visualização")
        popup.setOnMenuItemClickListener { item ->
            when (item.itemId) {
                MENU_ADD_FOLDER -> getGamesDirectory.launch(Intent(Intent.ACTION_OPEN_DOCUMENT_TREE).data)
                MENU_MANAGE_FOLDERS -> {
                    val action = HomeNavigationDirections.actionGlobalSettingsSubscreenActivity(SettingsSubscreen.GAME_FOLDERS, null)
                    findNavController().navigate(action)
                }
                MENU_VIEW -> showViewMenu(anchor)
            }
            true
        }
        popup.show()
    }

    private fun showViewMenu(anchor: View) {
        val popup = PopupMenu(requireContext(), anchor)
        popup.menuInflater.inflate(R.menu.menu_game_views, popup.menu)
        val isLandscape = resources.configuration.orientation == Configuration.ORIENTATION_LANDSCAPE
        if (!isLandscape) popup.menu.findItem(R.id.view_carousel)?.isVisible = false
        when (getCurrentViewType()) {
            GameAdapter.VIEW_TYPE_LIST -> popup.menu.findItem(R.id.view_list).isChecked = true
            GameAdapter.VIEW_TYPE_GRID_COMPACT -> popup.menu.findItem(R.id.view_grid_compact).isChecked = true
            GameAdapter.VIEW_TYPE_GRID -> popup.menu.findItem(R.id.view_grid).isChecked = true
            GameAdapter.VIEW_TYPE_CAROUSEL -> popup.menu.findItem(R.id.view_carousel).isChecked = true
        }
        popup.setOnMenuItemClickListener { item ->
            val next = when (item.itemId) {
                R.id.view_grid -> GameAdapter.VIEW_TYPE_GRID
                R.id.view_grid_compact -> GameAdapter.VIEW_TYPE_GRID_COMPACT
                R.id.view_list -> GameAdapter.VIEW_TYPE_LIST
                R.id.view_carousel -> GameAdapter.VIEW_TYPE_CAROUSEL
                else -> return@setOnMenuItemClickListener false
            }
            if (getCurrentViewType() == GameAdapter.VIEW_TYPE_CAROUSEL) onPause()
            setCurrentViewType(next)
            applyGridGamesBinding()
            filterAndSearch()
            item.isChecked = true
            if (next == GameAdapter.VIEW_TYPE_CAROUSEL) onResume()
            true
        }
        popup.show()
    }

    private fun showFilterMenu(anchor: View) {
        val popup = PopupMenu(requireContext(), anchor)
        popup.menuInflater.inflate(R.menu.menu_game_filters, popup.menu)
        when (currentFilter) {
            R.id.alphabetical -> popup.menu.findItem(R.id.alphabetical).isChecked = true
            R.id.filter_recently_added -> popup.menu.findItem(R.id.filter_recently_added).isChecked = true
        }
        popup.setOnMenuItemClickListener { item ->
            currentFilter = item.itemId
            preferences.edit { putInt(PREF_SORT_TYPE, currentFilter) }
            filterAndSearch()
            true
        }
        popup.show()
    }

    private var currentFilter = preferences.getInt(PREF_SORT_TYPE, View.NO_ID)

    private fun filterAndSearch(baseList: List<Game> = gamesViewModel.games.value) {
        var filteredList: List<Game> = when (currentFilter) {
            R.id.alphabetical -> baseList.sortedBy { it.title.lowercase(Locale.getDefault()) }
            R.id.filter_recently_added -> baseList
                .filter { preferences.getLong(it.keyAddedToLibraryTime, 0L) > 0L }
                .sortedByDescending { preferences.getLong(it.keyAddedToLibraryTime, 0L) }
            else -> baseList
        }

        if (frontendPage == 1) {
            filteredList = when (frontendFilter) {
                1 -> filteredList
                    .filter { preferences.getLong(it.keyLastPlayedTime, 0L) > 0L }
                    .sortedByDescending { preferences.getLong(it.keyLastPlayedTime, 0L) }
                2 -> filteredList.filter { preferences.getBoolean(it.keyFavorite, false) }
                else -> filteredList
            }
        }

        val searchTerm = binding.searchText.text.toString().trim().lowercase(Locale.getDefault())
        if (searchTerm.isEmpty()) {
            submitGameList(filteredList)
            gamesViewModel.setFilteredGames(filteredList)
            return
        }
        val searchAlgorithm = if (searchTerm.length > 1) Jaccard(2) else JaroWinkler()
        val sortedList = filteredList.mapNotNull { game ->
            val score = searchAlgorithm.similarity(searchTerm, game.title.lowercase(Locale.getDefault()))
            if (score > 0.03) ScoredGame(score, game) else null
        }.sortedByDescending { it.score }.map { it.item }
        submitGameList(sortedList)
        gamesViewModel.setFilteredGames(sortedList)
    }

    private inner class ScoredGame(val score: Double, val item: Game)

    private fun focusSearch() {
        binding.searchText.requestFocus()
        val imm = requireActivity().getSystemService(Context.INPUT_METHOD_SERVICE) as InputMethodManager?
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
        R.id.alphabetical, R.id.filter_recently_added -> filter
        else -> View.NO_ID
    }

    private fun setInsets() = ViewCompat.setOnApplyWindowInsetsListener(binding.root) { _, windowInsets ->
        val barInsets = windowInsets.getInsets(WindowInsetsCompat.Type.systemBars())
        val cutoutInsets = windowInsets.getInsets(WindowInsetsCompat.Type.displayCutout())
        val leftInset = barInsets.left + cutoutInsets.left
        val rightInset = barInsets.right + cutoutInsets.right
        val topInset = maxOf(barInsets.top, cutoutInsets.top)
        val navInsets = windowInsets.getInsets(WindowInsetsCompat.Type.navigationBars())
        val gestureInsets = windowInsets.getInsets(WindowInsetsCompat.Type.systemGestures())
        val bottomInset = maxOf(navInsets.bottom, gestureInsets.bottom, cutoutInsets.bottom)
        fallbackBottomInset = bottomInset
        binding.root.updatePadding(left = leftInset, right = rightInset, top = topInset, bottom = bottomInset)
        (binding.swipeRefresh as? SwipeRefreshLayout)?.setProgressViewEndTarget(false, topInset + resources.getDimensionPixelSize(R.dimen.spacing_refresh_end))
        (binding.gridGames as? CarouselRecyclerView)?.notifyInsetsReady(bottomInset)
        windowInsets
    }
}
