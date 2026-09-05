// SPDX-FileCopyrightText: Copyright 2025 Eden Emulator Project
// SPDX-License-Identifier: GPL-3.0-or-later

package org.yuzu.yuzu_emu.overlay.model

import kotlin.math.abs

data class OverlayControlData(
    val id: String,
    var enabled: Boolean,
    var landscapePosition: Pair<Double, Double>,
    var portraitPosition: Pair<Double, Double>,
    var foldablePosition: Pair<Double, Double>,
    var individualScale: Float
) {
    init {
        migrateLegacyLandscapeDefault()
    }

    fun positionFromLayout(layout: OverlayLayout): Pair<Double, Double> =
        when (layout) {
            OverlayLayout.Landscape -> landscapePosition
            OverlayLayout.Portrait -> portraitPosition
            OverlayLayout.Foldable -> foldablePosition
        }

    /**
     * Existing Moonwitch installs already have the old landscape defaults serialized in the native
     * config. Migrate only controls that are still sitting on those untouched defaults so the new
     * reference layout appears immediately after updating without trampling a genuinely custom
     * layout. A customized position remains exactly as the user saved it.
     */
    private fun migrateLegacyLandscapeDefault() {
        val legacy = LEGACY_LANDSCAPE_DEFAULTS[id] ?: return
        if (!landscapePosition.approximatelyEquals(legacy)) return

        REFERENCE_LANDSCAPE_DEFAULTS[id]?.let { landscapePosition = it }

        // Old untouched controls used scale 1.0. Preserve an explicitly customized scale.
        if (abs(individualScale - 1.0f) < 0.0001f) {
            REFERENCE_SCALES[id]?.let { individualScale = it }
        }

        // The small unlabelled top-centre circle in the supplied reference is the Home button.
        if (id == "button_home") {
            enabled = true
        }
    }

    private fun Pair<Double, Double>.approximatelyEquals(other: Pair<Double, Double>): Boolean =
        abs(first - other.first) < 0.00001 && abs(second - other.second) < 0.00001

    companion object {
        private val LEGACY_LANDSCAPE_DEFAULTS = mapOf(
            "button_a" to Pair(0.760, 0.790),
            "button_b" to Pair(0.710, 0.900),
            "button_x" to Pair(0.710, 0.680),
            "button_y" to Pair(0.660, 0.790),
            "button_plus" to Pair(0.540, 0.950),
            "button_minus" to Pair(0.460, 0.950),
            "button_home" to Pair(0.600, 0.950),
            "button_capture" to Pair(0.400, 0.950),
            "button_l" to Pair(0.070, 0.220),
            "button_r" to Pair(0.930, 0.220),
            "button_zl" to Pair(0.070, 0.090),
            "button_zr" to Pair(0.930, 0.090),
            "button_stick_l" to Pair(0.870, 0.400),
            "button_stick_r" to Pair(0.960, 0.430),
            "stick_l" to Pair(0.100, 0.670),
            "stick_r" to Pair(0.900, 0.670),
            "combined_dpad" to Pair(0.260, 0.790)
        )

        private val REFERENCE_LANDSCAPE_DEFAULTS = mapOf(
            "button_a" to Pair(0.934, 0.695),
            "button_b" to Pair(0.872, 0.832),
            "button_x" to Pair(0.872, 0.557),
            "button_y" to Pair(0.811, 0.695),
            "button_plus" to Pair(0.563, 0.919),
            "button_minus" to Pair(0.452, 0.919),
            "button_home" to Pair(0.510, 0.054),
            "button_l" to Pair(0.115, 0.274),
            "button_r" to Pair(0.907, 0.274),
            "button_zl" to Pair(0.178, 0.103),
            "button_zr" to Pair(0.844, 0.103),
            "button_stick_l" to Pair(0.743, 0.430),
            "button_stick_r" to Pair(0.811, 0.430),
            "stick_l" to Pair(0.137, 0.770),
            "stick_r" to Pair(0.703, 0.645),
            "combined_dpad" to Pair(0.303, 0.663)
        )

        private val REFERENCE_SCALES = mapOf(
            "button_a" to 1.185f,
            "button_b" to 1.185f,
            "button_x" to 1.185f,
            "button_y" to 1.185f,
            "button_plus" to 1.282f,
            "button_minus" to 1.282f,
            "button_home" to 1.116f,
            "button_l" to 1.076f,
            "button_r" to 1.076f,
            "button_zl" to 1.076f,
            "button_zr" to 1.076f,
            "button_stick_l" to 0.840f,
            "button_stick_r" to 0.840f,
            "stick_l" to 1.023f,
            "stick_r" to 1.023f,
            "combined_dpad" to 1.233f
        )
    }
}
