#!/usr/bin/env python3
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def write(rel, text):
    (ROOT / rel).write_text(text, encoding="utf-8")


def replace_once(rel, old, new):
    text = read(rel)
    if new in text:
        return
    if old not in text:
        raise RuntimeError(f"Missing expected block in {rel}: {old[:120]!r}")
    write(rel, text.replace(old, new, 1))


def replace_between(rel, start, end, replacement):
    text = read(rel)
    if replacement in text:
        return
    start_pos = text.find(start)
    if start_pos < 0:
        raise RuntimeError(f"Missing start marker in {rel}: {start!r}")
    end_pos = text.find(end, start_pos)
    if end_pos < 0:
        raise RuntimeError(f"Missing end marker in {rel}: {end!r}")
    write(rel, text[:start_pos] + replacement + text[end_pos:])


# Exact centres measured from the supplied 1536x691 reference image, normalized to 0..1000.
LANDSCAPE_POSITIONS = {
    "BUTTON_A_X": 934,
    "BUTTON_A_Y": 694,
    "BUTTON_B_X": 873,
    "BUTTON_B_Y": 831,
    "BUTTON_X_X": 873,
    "BUTTON_X_Y": 558,
    "BUTTON_Y_X": 811,
    "BUTTON_Y_Y": 694,
    "BUTTON_PLUS_X": 563,
    "BUTTON_PLUS_Y": 915,
    "BUTTON_MINUS_X": 452,
    "BUTTON_MINUS_Y": 920,
    "BUTTON_HOME_X": 511,
    "BUTTON_HOME_Y": 52,
    "BUTTON_L_X": 115,
    "BUTTON_L_Y": 274,
    "BUTTON_R_X": 907,
    "BUTTON_R_Y": 274,
    "BUTTON_ZL_X": 178,
    "BUTTON_ZL_Y": 103,
    "BUTTON_ZR_X": 845,
    "BUTTON_ZR_Y": 103,
    "BUTTON_STICK_L_X": 744,
    "BUTTON_STICK_L_Y": 429,
    "BUTTON_STICK_R_X": 811,
    "BUTTON_STICK_R_Y": 429,
    "STICK_L_X": 138,
    "STICK_L_Y": 774,
    "STICK_R_X": 703,
    "STICK_R_Y": 646,
    "COMBINED_DPAD_X": 303,
    "COMBINED_DPAD_Y": 661,
}

# Individual scale factors derived from the measured pixel footprint on the same reference.
CONTROL_SCALES = {
    "BUTTON_A": "1.171f",
    "BUTTON_B": "1.171f",
    "BUTTON_X": "1.171f",
    "BUTTON_Y": "1.171f",
    "BUTTON_PLUS": "1.303f",
    "BUTTON_MINUS": "1.303f",
    "BUTTON_HOME": "1.116f",
    "BUTTON_CAPTURE": "1.0f",
    "BUTTON_L": "1.080f",
    "BUTTON_R": "1.080f",
    "BUTTON_ZL": "1.080f",
    "BUTTON_ZR": "1.080f",
    "BUTTON_STICK_L": "0.831f",
    "BUTTON_STICK_R": "0.831f",
    "STICK_L": "1.018f",
    "STICK_R": "1.018f",
    "COMBINED_DPAD": "1.227f",
}


def apply_positions():
    rel = "src/android/app/src/main/res/values/integers.xml"
    text = read(rel)
    for name, value in LANDSCAPE_POSITIONS.items():
        pattern = rf'(<integer name="{re.escape(name)}">)\d+(</integer>)'
        text, count = re.subn(pattern, rf'\g<1>{value}\g<2>', text, count=1)
        if count != 1:
            raise RuntimeError(f"Could not update {name} in {rel}")
    text = text.replace(
        "<!-- Default SWITCH landscape layout -->",
        "<!-- Exact Moonwitch landscape layout measured from supplied 1536x691 reference -->",
        1,
    )
    write(rel, text)


def apply_scales():
    rel = "src/android/app/src/main/java/org/yuzu/yuzu_emu/overlay/model/OverlayControl.kt"
    text = read(rel)
    for enum_name, scale in CONTROL_SCALES.items():
        pattern = rf'(?ms)(    {re.escape(enum_name)}\(.*?\n        )([0-9]+(?:\.[0-9]+)?f)(\n    \)[,;])'
        text, count = re.subn(pattern, rf'\g<1>{scale}\g<3>', text, count=1)
        if count != 1:
            raise RuntimeError(f"Could not update scale for {enum_name}")

    # Home is part of the supplied layout; Capture is not.
    text = text.replace(
        '    BUTTON_HOME(\n        "button_home",\n        false,\n',
        '    BUTTON_HOME(\n        "button_home",\n        true,\n',
        1,
    )
    text = text.replace(
        '    BUTTON_CAPTURE(\n        "button_capture",\n        true,\n',
        '    BUTTON_CAPTURE(\n        "button_capture",\n        false,\n',
        1,
    )
    write(rel, text)


def patch_button_renderer():
    rel = "src/android/app/src/main/java/org/yuzu/yuzu_emu/overlay/InputOverlayDrawableButton.kt"
    replace_once(
        rel,
        "    private var pressedState = false\n",
        "    private var pressedState = false\n    private var opacity = 255\n",
    )
    replace_once(
        rel,
        "    fun draw(canvas: Canvas?) {\n        currentStateBitmapDrawable.draw(canvas!!)\n    }\n",
        "    fun draw(canvas: Canvas?) {\n        canvas ?: return\n        MoonwitchOverlayStyle.drawButton(\n            canvas,\n            bounds,\n            overlayControlData.id,\n            pressedState,\n            opacity\n        )\n    }\n",
    )
    replace_once(
        rel,
        "    fun setOpacity(value: Int) {\n        defaultStateBitmap.alpha = value\n        pressedStateBitmap.alpha = value\n    }\n",
        "    fun setOpacity(value: Int) {\n        opacity = value.coerceIn(0, 255)\n        defaultStateBitmap.alpha = opacity\n        pressedStateBitmap.alpha = opacity\n    }\n",
    )


def patch_dpad_renderer():
    rel = "src/android/app/src/main/java/org/yuzu/yuzu_emu/overlay/InputOverlayDrawableDpad.kt"
    replace_once(
        rel,
        "    private val pressedTwoDirectionsStateBitmap: BitmapDrawable\n",
        "    private val pressedTwoDirectionsStateBitmap: BitmapDrawable\n    private var opacity = 255\n",
    )
    replace_between(
        rel,
        "    fun draw(canvas: Canvas) {\n",
        "    val upStatus: Int\n",
        "    fun draw(canvas: Canvas) {\n        MoonwitchOverlayStyle.drawDpad(\n            canvas,\n            bounds,\n            upButtonState,\n            downButtonState,\n            leftButtonState,\n            rightButtonState,\n            opacity\n        )\n    }\n\n",
    )
    replace_once(
        rel,
        "    fun setOpacity(value: Int) {\n        defaultStateBitmap.alpha = value\n        pressedOneDirectionStateBitmap.alpha = value\n        pressedTwoDirectionsStateBitmap.alpha = value\n    }\n",
        "    fun setOpacity(value: Int) {\n        opacity = value.coerceIn(0, 255)\n        defaultStateBitmap.alpha = opacity\n        pressedOneDirectionStateBitmap.alpha = opacity\n        pressedTwoDirectionsStateBitmap.alpha = opacity\n    }\n",
    )


def patch_joystick_renderer():
    rel = "src/android/app/src/main/java/org/yuzu/yuzu_emu/overlay/InputOverlayDrawableJoystick.kt"
    replace_once(
        rel,
        "    fun draw(canvas: Canvas?) {\n        outerBitmap.draw(canvas!!)\n        currentStateBitmapDrawable.draw(canvas)\n        boundsBoxBitmap.draw(canvas)\n    }\n",
        "    fun draw(canvas: Canvas?) {\n        canvas ?: return\n        val visualBounds = if (pressedState) virtBounds else bounds\n        MoonwitchOverlayStyle.drawJoystick(\n            canvas,\n            visualBounds,\n            xAxis,\n            yAxis,\n            pressedState,\n            opacity\n        )\n    }\n",
    )
    replace_once(
        rel,
        "    fun setOpacity(value: Int) {\n        opacity = value\n\n        defaultStateInnerBitmap.alpha = value\n        pressedStateInnerBitmap.alpha = value\n\n        if (trackId == -1) {\n            outerBitmap.alpha = value\n            boundsBoxBitmap.alpha = 0\n        } else {\n            outerBitmap.alpha = 0\n            boundsBoxBitmap.alpha = value\n        }\n    }\n",
        "    fun setOpacity(value: Int) {\n        opacity = value.coerceIn(0, 255)\n\n        defaultStateInnerBitmap.alpha = opacity\n        pressedStateInnerBitmap.alpha = opacity\n\n        if (trackId == -1) {\n            outerBitmap.alpha = opacity\n            boundsBoxBitmap.alpha = 0\n        } else {\n            outerBitmap.alpha = 0\n            boundsBoxBitmap.alpha = opacity\n        }\n    }\n",
    )


def patch_one_time_layout_migration():
    rel = "src/android/app/src/main/java/org/yuzu/yuzu_emu/overlay/InputOverlay.kt"
    replace_once(
        rel,
        "        ensureMoonwitchHomeShortcutEnabled()\n\n        // Load the controls.\n",
        "        ensureMoonwitchHomeShortcutEnabled()\n        ensureMoonwitchReferenceLayoutApplied()\n\n        // Load the controls.\n",
    )
    replace_once(
        rel,
        '        private const val KEY_HOME_INITIALIZED = "home_shortcut_initialized"\n',
        '        private const val KEY_HOME_INITIALIZED = "home_shortcut_initialized"\n'
        '        private const val KEY_REFERENCE_LAYOUT_APPLIED = "reference_layout_1536x691_v1"\n',
    )

    migration = '''    private fun ensureMoonwitchReferenceLayoutApplied() {
        val prefs = context.getSharedPreferences(MOONWITCH_OVERLAY_PREFS, Context.MODE_PRIVATE)
        if (prefs.getBoolean(KEY_REFERENCE_LAYOUT_APPLIED, false)) return

        val controls = NativeConfig.getOverlayControlData()
        controls.forEach { data ->
            val control = OverlayControl.from(data.id) ?: return@forEach
            data.landscapePosition = control.getDefaultPositionForLayout(OverlayLayout.Landscape)
            data.individualScale = control.defaultIndividualScaleResource
            data.enabled = when (data.id) {
                OverlayControl.BUTTON_CAPTURE.id -> false
                else -> control.defaultVisibility
            }
        }
        NativeConfig.setOverlayControlData(controls)
        NativeConfig.saveGlobalConfig()
        prefs.edit().putBoolean(KEY_REFERENCE_LAYOUT_APPLIED, true).apply()
    }

'''
    replace_once(
        rel,
        "    fun refreshControls(gameless: Boolean = false) {\n",
        migration + "    fun refreshControls(gameless: Boolean = false) {\n",
    )


def main():
    apply_positions()
    apply_scales()
    patch_button_renderer()
    patch_dpad_renderer()
    patch_joystick_renderer()
    patch_one_time_layout_migration()
    print("Moonwitch exact 1536x691 translucent reference layout applied")


if __name__ == "__main__":
    main()
