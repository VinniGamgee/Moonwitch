// SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
// SPDX-License-Identifier: GPL-3.0-or-later

package org.yuzu.yuzu_emu.features.settings.model

import org.yuzu.yuzu_emu.utils.NativeConfig

object MoonwitchCasSettings {
    const val ENABLED_KEY = "cas_enabled"
    const val SHARPNESS_KEY = "cas_sharpness"

    val enabled: AbstractBooleanSetting = object : AbstractBooleanSetting {
        override val key = ENABLED_KEY

        override fun getBoolean(needsGlobal: Boolean): Boolean =
            NativeConfig.getBoolean(key, needsGlobal)

        override fun setBoolean(value: Boolean) {
            if (NativeConfig.isPerGameConfigLoaded()) {
                global = false
            }
            NativeConfig.setBoolean(key, value)
        }

        override val defaultValue: Boolean by lazy {
            NativeConfig.getDefaultToString(key).toBoolean()
        }

        override fun getValueAsString(needsGlobal: Boolean): String =
            getBoolean(needsGlobal).toString()

        override fun reset() = NativeConfig.setBoolean(key, defaultValue)
    }

    val sharpness: AbstractIntSetting = object : AbstractIntSetting {
        override val key = SHARPNESS_KEY

        override fun getInt(needsGlobal: Boolean): Int = NativeConfig.getInt(key, needsGlobal)

        override fun setInt(value: Int) {
            if (NativeConfig.isPerGameConfigLoaded()) {
                global = false
            }
            NativeConfig.setInt(key, value.coerceIn(0, 100))
        }

        override val defaultValue: Int by lazy {
            NativeConfig.getDefaultToString(key).toInt()
        }

        override fun getValueAsString(needsGlobal: Boolean): String =
            getInt(needsGlobal).toString()

        override fun reset() = NativeConfig.setInt(key, defaultValue)
    }
}
