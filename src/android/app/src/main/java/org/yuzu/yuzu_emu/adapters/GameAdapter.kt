// SPDX-FileCopyrightText: Copyright 2025 Eden Emulator Project
// SPDX-License-Identifier: GPL-3.0-or-later

package org.yuzu.yuzu_emu.adapters

import android.content.DialogInterface
import android.content.res.ColorStateList
import android.text.Html
import android.view.LayoutInflater
import android.view.ViewGroup
import android.widget.ImageView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.core.content.edit
import androidx.core.content.pm.ShortcutInfoCompat
import androidx.core.content.pm.ShortcutManagerCompat
import androidx.core.net.toUri
import androidx.documentfile.provider.DocumentFile
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.lifecycleScope
import androidx.navigation.findNavController
import androidx.preference.PreferenceManager
import androidx.viewbinding.ViewBinding
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.yuzu.yuzu_emu.HomeNavigationDirections
import org.yuzu.yuzu_emu.NativeLibrary
import org.yuzu.yuzu_emu.R
import org.yuzu.yuzu_emu.YuzuApplication
import org.yuzu.yuzu_emu.databinding.CardGameCarouselBinding
import org.yuzu.yuzu_emu.databinding.CardGameGridBinding
import org.yuzu.yuzu_emu.databinding.CardGameGridCompactBinding
import org.yuzu.yuzu_emu.databinding.CardGameListBinding
import org.yuzu.yuzu_emu.model.Game
import org.yuzu.yuzu_emu.model.GamesViewModel
import org.yuzu.yuzu_emu.utils.GameIconUtils
import org.yuzu.yuzu_emu.utils.ViewUtils.marquee
import org.yuzu.yuzu_emu.viewholder.AbstractViewHolder

class GameAdapter(private val activity: AppCompatActivity) :
    AbstractDiffAdapter<Game, GameAdapter.GameViewHolder>(exact = false) {

    companion object {
        const val VIEW_TYPE_GRID = 0
        const val VIEW_TYPE_GRID_COMPACT = 1
        const val VIEW_TYPE_LIST = 2
        const val VIEW_TYPE_CAROUSEL = 3
    }

    private val preferences = PreferenceManager.getDefaultSharedPreferences(YuzuApplication.appContext)
    private var viewType = VIEW_TYPE_GRID

    fun setViewType(type: Int) {
        viewType = type
        notifyDataSetChanged()
    }

    var cardSize: Int = 0
        private set

    fun setCardSize(size: Int) {
        if (cardSize != size && size > 0) {
            cardSize = size
            notifyDataSetChanged()
        }
    }

    override fun getItemViewType(position: Int): Int = viewType

    override fun onBindViewHolder(holder: GameViewHolder, position: Int) {
        super.onBindViewHolder(holder, position)
        when (getItemViewType(position)) {
            VIEW_TYPE_LIST -> {
                val b = holder.binding as CardGameListBinding
                b.cardGameList.scaleX = 1f
                b.cardGameList.scaleY = 1f
                b.cardGameList.alpha = 1f
                b.root.layoutParams.width = ViewGroup.LayoutParams.MATCH_PARENT
                b.root.layoutParams.height = ViewGroup.LayoutParams.WRAP_CONTENT
            }
            VIEW_TYPE_GRID -> {
                val b = holder.binding as CardGameGridBinding
                b.cardGameGrid.scaleX = 1f
                b.cardGameGrid.scaleY = 1f
                b.cardGameGrid.alpha = 1f
                b.root.layoutParams.width = ViewGroup.LayoutParams.MATCH_PARENT
                b.root.layoutParams.height = ViewGroup.LayoutParams.WRAP_CONTENT
            }
            VIEW_TYPE_GRID_COMPACT -> {
                val b = holder.binding as CardGameGridCompactBinding
                b.cardGameGridCompact.scaleX = 1f
                b.cardGameGridCompact.scaleY = 1f
                b.cardGameGridCompact.alpha = 1f
                b.root.layoutParams.width = ViewGroup.LayoutParams.MATCH_PARENT
                b.root.layoutParams.height = ViewGroup.LayoutParams.WRAP_CONTENT
            }
            VIEW_TYPE_CAROUSEL -> {
                val b = holder.binding as CardGameCarouselBinding
                b.cardGameCarousel.scaleY = 0f
                b.cardGameCarousel.alpha = 0f
            }
        }
    }

    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): GameViewHolder {
        val binding = when (viewType) {
            VIEW_TYPE_LIST -> CardGameListBinding.inflate(LayoutInflater.from(parent.context), parent, false)
            VIEW_TYPE_GRID -> CardGameGridBinding.inflate(LayoutInflater.from(parent.context), parent, false)
            VIEW_TYPE_GRID_COMPACT -> CardGameGridCompactBinding.inflate(LayoutInflater.from(parent.context), parent, false)
            VIEW_TYPE_CAROUSEL -> CardGameCarouselBinding.inflate(LayoutInflater.from(parent.context), parent, false)
            else -> throw IllegalArgumentException("Invalid view type")
        }
        return GameViewHolder(binding, viewType)
    }

    inner class GameViewHolder(
        internal val binding: ViewBinding,
        private val viewType: Int
    ) : AbstractViewHolder<Game>(binding) {

        override fun bind(model: Game) {
            when (viewType) {
                VIEW_TYPE_LIST -> bindListView(model)
                VIEW_TYPE_GRID -> bindGridView(model)
                VIEW_TYPE_CAROUSEL -> bindCarouselView(model)
                VIEW_TYPE_GRID_COMPACT -> bindGridCompactView(model)
            }
        }

        private fun metadata(model: Game): String {
            val developer = model.developer.ifBlank { activity.getString(R.string.app_name) }
            return if (model.version.isBlank()) developer else "$developer • ${model.version}"
        }

        private fun bindListView(model: Game) {
            val b = binding as CardGameListBinding
            b.imageGameScreen.scaleType = ImageView.ScaleType.FIT_CENTER
            GameIconUtils.loadGameIcon(model, b.imageGameScreen)
            b.textGameTitle.text = model.title.replace("[\\t\\n\\r]+".toRegex(), " ")
            b.textGameDeveloper.text = metadata(model)
            b.cardGameList.setOnClickListener { openDetails(model) }
            b.cardGameList.setOnLongClickListener { onLongClick(model) }
            b.moreButton.setOnClickListener { openDetails(model) }
            updateFavoriteButton(b.favoriteButton, model)
            b.favoriteButton.setOnClickListener {
                val next = !preferences.getBoolean(model.keyFavorite, false)
                preferences.edit { putBoolean(model.keyFavorite, next) }
                updateFavoriteButton(b.favoriteButton, model)
                ViewModelProvider(activity)[GamesViewModel::class.java].setShouldSwapData(true)
            }
            b.root.layoutParams.width = ViewGroup.LayoutParams.MATCH_PARENT
            b.root.layoutParams.height = ViewGroup.LayoutParams.WRAP_CONTENT
        }

        private fun updateFavoriteButton(button: android.widget.ImageButton, model: Game) {
            val favorite = preferences.getBoolean(model.keyFavorite, false)
            button.setImageResource(if (favorite) R.drawable.ic_mw_star_filled else R.drawable.ic_mw_star)
            val tint = ContextCompat.getColor(
                button.context,
                if (favorite) R.color.mw_ui_accent_hi else R.color.mw_ui_text_2
            )
            button.imageTintList = ColorStateList.valueOf(tint)
        }

        private fun bindGridView(model: Game) {
            val b = binding as CardGameGridBinding
            b.imageGameScreen.scaleType = ImageView.ScaleType.FIT_CENTER
            GameIconUtils.loadGameIcon(model, b.imageGameScreen)
            b.textGameTitle.text = model.title.replace("[\\t\\n\\r]+".toRegex(), " ")
            b.textGameDeveloper.text = metadata(model)
            b.cardGameGrid.setOnClickListener { openDetails(model) }
            b.cardGameGrid.setOnLongClickListener { onLongClick(model) }
            b.moreButton.setOnClickListener { openDetails(model) }
            b.root.layoutParams.width = ViewGroup.LayoutParams.MATCH_PARENT
            b.root.layoutParams.height = ViewGroup.LayoutParams.WRAP_CONTENT
        }

        private fun bindGridCompactView(model: Game) {
            val b = binding as CardGameGridCompactBinding
            b.imageGameScreenCompact.scaleType = ImageView.ScaleType.CENTER_CROP
            GameIconUtils.loadGameIcon(model, b.imageGameScreenCompact)
            b.textGameTitleCompact.text = model.title.replace("[\\t\\n\\r]+".toRegex(), " ")
            b.textGameTitleCompact.marquee()
            b.cardGameGridCompact.setOnClickListener { openDetails(model) }
            b.cardGameGridCompact.setOnLongClickListener { onLongClick(model) }
            b.root.layoutParams.width = ViewGroup.LayoutParams.MATCH_PARENT
            b.root.layoutParams.height = ViewGroup.LayoutParams.WRAP_CONTENT
        }

        private fun bindCarouselView(model: Game) {
            val b = binding as CardGameCarouselBinding
            b.imageGameScreen.scaleType = ImageView.ScaleType.CENTER_CROP
            GameIconUtils.loadGameIcon(model, b.imageGameScreen)
            b.textGameTitle.text = model.title.replace("[\\t\\n\\r]+".toRegex(), " ")
            b.textGameTitle.marquee()
            b.cardGameCarousel.setOnClickListener { openDetails(model) }
            b.cardGameCarousel.setOnLongClickListener { onLongClick(model) }
            b.imageGameScreen.contentDescription = binding.root.context.getString(R.string.game_image_desc, model.title)
            b.root.layoutParams.width = cardSize
        }

        private fun openDetails(game: Game) {
            val action = HomeNavigationDirections.actionGlobalPerGamePropertiesFragment(game)
            binding.root.findNavController().navigate(action)
        }

        fun onClick(game: Game) {
            val gameExists = DocumentFile.fromSingleUri(YuzuApplication.appContext, game.path.toUri())?.exists() == true
            if (!gameExists) {
                Toast.makeText(YuzuApplication.appContext, R.string.loader_error_file_not_found, Toast.LENGTH_LONG).show()
                ViewModelProvider(activity)[GamesViewModel::class.java].reloadGames(true)
                return
            }

            val launch: () -> Unit = {
                preferences.edit { putLong(game.keyLastPlayedTime, System.currentTimeMillis()) }
                activity.lifecycleScope.launch {
                    withContext(Dispatchers.IO) {
                        val shortcut = ShortcutInfoCompat.Builder(YuzuApplication.appContext, game.path)
                            .setShortLabel(game.title)
                            .setIcon(GameIconUtils.getShortcutIcon(activity, game))
                            .setIntent(game.launchIntent)
                            .build()
                        ShortcutManagerCompat.pushDynamicShortcut(YuzuApplication.appContext, shortcut)
                    }
                }
                val action = HomeNavigationDirections.actionGlobalEmulationActivity(game, true)
                binding.root.findNavController().navigate(action)
            }

            if (NativeLibrary.gameRequiresFirmware(game.programId) && !NativeLibrary.isFirmwareAvailable()) {
                MaterialAlertDialogBuilder(activity)
                    .setTitle(R.string.loader_requires_firmware)
                    .setMessage(Html.fromHtml(activity.getString(R.string.loader_requires_firmware_description), Html.FROM_HTML_MODE_LEGACY))
                    .setPositiveButton(android.R.string.ok) { _: DialogInterface?, _: Int -> launch() }
                    .setNegativeButton(android.R.string.cancel) { _, _ -> }
                    .show()
            } else {
                launch()
            }
        }

        fun onLongClick(game: Game): Boolean {
            openDetails(game)
            return true
        }
    }
}
