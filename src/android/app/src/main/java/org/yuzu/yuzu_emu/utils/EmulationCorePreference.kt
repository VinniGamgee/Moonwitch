// SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
// SPDX-License-Identifier: GPL-3.0-or-later

package org.yuzu.yuzu_emu.utils

import android.content.Context
import androidx.preference.PreferenceManager

/**
 * Selects the actual emulation engine used to launch a game.
 *
 * This is intentionally kept outside NativeConfig because the Kenji/Ryujinx engine has its own
 * configuration model and lifecycle. The setting changes which native core is executed; it is not
 * a presentation-only toggle.
 */
object EmulationCorePreference {
    private const val PREF_KEY = "moonwitch_emulation_core"

    enum class Core(val storedValue: String) {
        Moonwitch("moonwitch"),
        Kenji("kenji")
    }

    fun get(context: Context): Core {
        val stored = PreferenceManager.getDefaultSharedPreferences(context)
            .getString(PREF_KEY, Core.Moonwitch.storedValue)
        return Core.entries.firstOrNull { it.storedValue == stored } ?: Core.Moonwitch
    }

    fun set(context: Context, core: Core) {
        PreferenceManager.getDefaultSharedPreferences(context)
            .edit()
            .putString(PREF_KEY, core.storedValue)
            .apply()
    }
}
