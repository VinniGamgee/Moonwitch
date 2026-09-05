#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def rep(path, old, new):
    p = ROOT / path
    text = p.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"Missing expected block in {path}: {old[:80]!r}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


def write_asset(name, xml):
    path = ROOT / "src/android/app/src/main/res/drawable" / name
    path.write_text(xml.strip() + "\n", encoding="utf-8")


def tune_existing_glass_assets():
    drawable_dir = ROOT / "src/android/app/src/main/res/drawable"
    names = [
        "facebutton_a.xml", "facebutton_b.xml", "facebutton_x.xml", "facebutton_y.xml",
        "facebutton_a_depressed.xml", "facebutton_b_depressed.xml",
        "facebutton_x_depressed.xml", "facebutton_y_depressed.xml",
        "l_shoulder.xml", "r_shoulder.xml", "zl_trigger.xml", "zr_trigger.xml",
        "l_shoulder_depressed.xml", "r_shoulder_depressed.xml",
        "zl_trigger_depressed.xml", "zr_trigger_depressed.xml",
        "dpad_standard.xml", "dpad_standard_cardinal_depressed.xml",
        "dpad_standard_diagonal_depressed.xml",
        "joystick_range.xml", "joystick.xml", "joystick_depressed.xml",
    ]

    replacements = {
        "#E60B1018": "#66101824",
        "#D90B1018": "#5A101824",
        "#401F2936": "#261E2B3A",
        "#E615202B": "#8035D8FF",
        "#E635D8FF": "#9935D8FF",
    }
    for name in names:
        path = drawable_dir / name
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for old, new in replacements.items():
            text = text.replace(old, new)

        if name.startswith(("facebutton_a", "facebutton_b", "facebutton_x", "facebutton_y")):
            text = text.replace(
                "M51.8,51.8m-49,0a49,49 0,1 1,98 0a49,49 0,1 1,-98 0",
                "M26,3H77.6C91.2,3 100.6,12.4 100.6,26V77.6C100.6,91.2 91.2,100.6 77.6,100.6H26C12.4,100.6 3,91.2 3,77.6V26C3,12.4 12.4,3 26,3Z",
            )
            text = text.replace(
                "M51.8,51.8m-40,0a40,40 0,1 1,80 0a40,40 0,1 1,-80 0",
                "M29,12H74.6C84,12 91.6,19.6 91.6,29V74.6C91.6,84 84,91.6 74.6,91.6H29C19.6,91.6 12,84 12,74.6V29C12,19.6 19.6,12 29,12Z",
            )
            highlight = (
                '    <path android:fillColor="#00000000" '
                'android:pathData="M20,27C30,15 44,10 61,10" '
                'android:strokeColor="#66FFFFFF" android:strokeWidth="2.2" '
                'android:strokeLineCap="round"/>\n'
            )
            if "strokeLineCap" not in text:
                text = text.replace("</vector>", highlight + "</vector>")

        path.write_text(text, encoding="utf-8")


def install_identity_assets():
    base_prefix = """<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:alpha="{alpha}" android:height="72dp" android:width="72dp"
    android:viewportHeight="72" android:viewportWidth="72">
    <path android:fillColor="{fill}"
        android:pathData="M22,4H50C60,4 68,12 68,22V50C68,60 60,68 50,68H22C12,68 4,60 4,50V22C4,12 12,4 22,4Z"
        android:strokeColor="{stroke}" android:strokeWidth="2.4"/>
    <path android:fillColor="#00000000"
        android:pathData="M19,13C28,7 39,7 49,10"
        android:strokeColor="{highlight}" android:strokeWidth="2"
        android:strokeLineCap="round"/>
"""
    suffix = "</vector>\n"

    def utility(icon_path, pressed=False):
        return (
            base_prefix.format(
                alpha="0.92" if not pressed else "0.98",
                fill="#56101824" if not pressed else "#9935D8FF",
                stroke="#B835D8FF" if not pressed else "#FFF4FBFF",
                highlight="#66FFFFFF" if not pressed else "#AAFFFFFF",
            )
            + f'    <path android:fillColor="{"#EAF4FBFF" if not pressed else "#FF071016"}" android:pathData="{icon_path}"/>\n'
            + suffix
        )

    plus = "M33,18H39V33H54V39H39V54H33V39H18V33H33Z"
    minus = "M18,33H54V39H18Z"
    capture = "M20,22H52V50H20ZM36,28m-8,0a8,8 0,1 1,16 0a8,8 0,1 1,-16 0"
    moon = "M48,16C39,18 32,27 32,37C32,48 41,56 51,56C55,56 58,55 61,53C56,62 46,67 35,64C22,61 14,49 17,36C20,23 33,14 46,17Z"

    for pressed in (False, True):
        tag = "_depressed" if pressed else ""
        write_asset(f"facebutton_plus{tag}.xml", utility(plus, pressed))
        write_asset(f"facebutton_minus{tag}.xml", utility(minus, pressed))
        write_asset(f"facebutton_screenshot{tag}.xml", utility(capture, pressed))
        write_asset(f"facebutton_home{tag}.xml", utility(moon, pressed))

    def stick_asset(letter, pressed=False):
        color = "#EAF4FBFF" if not pressed else "#FF071016"
        if letter == "L":
            glyph = (
                f'    <path android:fillColor="#00000000" android:pathData="M22,20V48H36" '
                f'android:strokeColor="{color}" android:strokeWidth="4" android:strokeLineCap="round"/>\n'
                f'    <path android:fillColor="#00000000" android:pathData="M43,24C50,20 57,23 57,29C57,34 53,36 48,36C54,36 58,39 58,45C58,52 51,55 43,51" '
                f'android:strokeColor="{color}" android:strokeWidth="3.4" android:strokeLineCap="round"/>\n'
            )
        else:
            glyph = (
                f'    <path android:fillColor="#00000000" android:pathData="M20,49V21H31C39,21 43,25 43,31C43,36 40,39 34,40L44,49" '
                f'android:strokeColor="{color}" android:strokeWidth="3.6" android:strokeLineCap="round" android:strokeLineJoin="round"/>\n'
                f'    <path android:fillColor="#00000000" android:pathData="M47,24C53,20 59,23 59,29C59,34 55,36 50,36C56,36 60,39 60,45C60,52 53,55 46,51" '
                f'android:strokeColor="{color}" android:strokeWidth="3.2" android:strokeLineCap="round"/>\n'
            )
        return (
            base_prefix.format(
                alpha="0.92" if not pressed else "0.98",
                fill="#56101824" if not pressed else "#9935D8FF",
                stroke="#B835D8FF" if not pressed else "#FFF4FBFF",
                highlight="#66FFFFFF" if not pressed else "#AAFFFFFF",
            )
            + glyph
            + suffix
        )

    for pressed in (False, True):
        tag = "_depressed" if pressed else ""
        write_asset(f"button_l3{tag}.xml", stick_asset("L", pressed))
        write_asset(f"button_r3{tag}.xml", stick_asset("R", pressed))


def main():
    overlay = "src/android/app/src/main/java/org/yuzu/yuzu_emu/overlay/InputOverlay.kt"
    fragment = "src/android/app/src/main/java/org/yuzu/yuzu_emu/fragments/EmulationFragment.kt"
    control = "src/android/app/src/main/java/org/yuzu/yuzu_emu/overlay/model/OverlayControl.kt"
    integers = ROOT / "src/android/app/src/main/res/values/integers.xml"
    menu = "src/android/app/src/main/res/menu/menu_overlay_options.xml"

    # Moonwitch Glass must remain visually distinct from the inherited Eden/Yuzu overlay.
    tune_existing_glass_assets()
    install_identity_assets()

    rep(
        overlay,
        "    var touchEventListener: ((MotionEvent) -> Unit)? = null\n",
        "    var touchEventListener: ((MotionEvent) -> Unit)? = null\n"
        "    var moonwitchHomeListener: (() -> Unit)? = null\n",
    )

    rep(
        overlay,
        "            checkForNewControls(overlayControlData)\n        }\n\n        // Load the controls.\n",
        "            checkForNewControls(overlayControlData)\n        }\n\n"
        "        ensureMoonwitchHomeShortcutEnabled()\n\n        // Load the controls.\n",
    )

    old_button = """            NativeInput.onOverlayButtonEvent(
                playerIndex,
                button.button,
                button.status
            )
            playHaptics(event)
            shouldUpdateView = true
"""
    new_button = """            if (button.button == NativeButton.Home) {
                if (event.actionMasked == MotionEvent.ACTION_UP ||
                    event.actionMasked == MotionEvent.ACTION_POINTER_UP
                ) {
                    moonwitchHomeListener?.invoke()
                }
                playHaptics(event)
                shouldUpdateView = true
                continue
            }
            NativeInput.onOverlayButtonEvent(
                playerIndex,
                button.button,
                button.status
            )
            playHaptics(event)
            shouldUpdateView = true
"""
    rep(overlay, old_button, new_button)

    ensure = """    private fun ensureMoonwitchHomeShortcutEnabled() {
        val prefs = context.getSharedPreferences(MOONWITCH_OVERLAY_PREFS, Context.MODE_PRIVATE)
        if (prefs.getBoolean(KEY_HOME_INITIALIZED, false)) return
        val controls = NativeConfig.getOverlayControlData()
        controls.firstOrNull { it.id == OverlayControl.BUTTON_HOME.id }?.let { home ->
            home.enabled = true
            home.landscapePosition = OverlayControl.BUTTON_HOME.getDefaultPositionForLayout(OverlayLayout.Landscape)
            home.portraitPosition = OverlayControl.BUTTON_HOME.getDefaultPositionForLayout(OverlayLayout.Portrait)
            home.foldablePosition = OverlayControl.BUTTON_HOME.getDefaultPositionForLayout(OverlayLayout.Foldable)
            NativeConfig.setOverlayControlData(controls)
            NativeConfig.saveGlobalConfig()
        }
        prefs.edit().putBoolean(KEY_HOME_INITIALIZED, true).apply()
    }

"""
    rep(overlay, "    fun refreshControls(gameless: Boolean = false) {\n", ensure + "    fun refreshControls(gameless: Boolean = false) {\n")

    companion = """    companion object {
        private const val MOONWITCH_OVERLAY_PREFS = "moonwitch_overlay_ui"
        private const val KEY_TRANSPARENT_STYLE = "transparent_controls"
        private const val KEY_HOME_INITIALIZED = "home_shortcut_initialized"

        fun isTransparentStyle(context: Context): Boolean =
            context.getSharedPreferences(MOONWITCH_OVERLAY_PREFS, Context.MODE_PRIVATE)
                .getBoolean(KEY_TRANSPARENT_STYLE, true)

        fun setTransparentStyle(context: Context, enabled: Boolean) {
            context.getSharedPreferences(MOONWITCH_OVERLAY_PREFS, Context.MODE_PRIVATE)
                .edit().putBoolean(KEY_TRANSPARENT_STYLE, enabled).apply()
        }

"""
    rep(overlay, "    companion object {\n\n", companion)

    rep(
        overlay,
        "            val vectorDrawable = ContextCompat.getDrawable(context, drawableId) as VectorDrawable\n",
        "            val vectorDrawable = (ContextCompat.getDrawable(context, drawableId) as VectorDrawable).mutate() as VectorDrawable\n"
        "            // Moonwitch Glass preserves the authored cyan/graphite palette instead of\n"
        "            // blanket-tinting inherited controls white.\n"
        "            if (isTransparentStyle(context)) {\n"
        "                vectorDrawable.alpha = 220\n"
        "            }\n",
    )

    rep(
        fragment,
        "import org.yuzu.yuzu_emu.overlay.model.OverlayControl\n",
        "import org.yuzu.yuzu_emu.overlay.InputOverlay\nimport org.yuzu.yuzu_emu.overlay.model.OverlayControl\n",
    )

    rep(
        fragment,
        "        binding.doneControlConfig.setOnClickListener { stopConfiguringControls() }\n",
        "        binding.doneControlConfig.setOnClickListener { stopConfiguringControls() }\n"
        "        binding.surfaceInputOverlay.moonwitchHomeListener = { openMoonwitchInGameDrawer() }\n",
    )

    rep(
        fragment,
        "        _binding?.surfaceInputOverlay?.touchEventListener = null\n        _binding = null\n",
        "        _binding?.surfaceInputOverlay?.touchEventListener = null\n"
        "        _binding?.surfaceInputOverlay?.moonwitchHomeListener = null\n        _binding = null\n",
    )

    open_drawer = """    private fun openMoonwitchInGameDrawer() {
        val b = _binding ?: return
        if (b.drawerLayout.isDrawerOpen(b.quickSettingsSheet)) {
            b.drawerLayout.closeDrawer(b.quickSettingsSheet, false)
        }
        b.drawerLayout.setDrawerLockMode(DrawerLayout.LOCK_MODE_UNLOCKED, b.inGameMenu)
        b.drawerLayout.openDrawer(b.inGameMenu)
        b.inGameMenu.requestFocus()
    }

"""
    rep(fragment, "    private fun openQuickSettingsMenu() {\n", open_drawer + "    private fun openQuickSettingsMenu() {\n")

    rep(
        fragment,
        "            findItem(R.id.menu_touchscreen).isChecked = BooleanSetting.TOUCHSCREEN.getBoolean()\n",
        "            findItem(R.id.menu_touchscreen).isChecked = BooleanSetting.TOUCHSCREEN.getBoolean()\n"
        "            findItem(R.id.menu_transparent_overlay).isChecked = InputOverlay.isTransparentStyle(requireContext())\n",
    )

    rep(
        fragment,
        "                R.id.menu_toggle_controls -> {\n",
        "                R.id.menu_transparent_overlay -> {\n"
        "                    it.isChecked = !it.isChecked\n"
        "                    InputOverlay.setTransparentStyle(requireContext(), it.isChecked)\n"
        "                    binding.surfaceInputOverlay.refreshControls()\n"
        "                    true\n"
        "                }\n\n"
        "                R.id.menu_toggle_controls -> {\n",
    )

    rep(
        control,
        '    BUTTON_HOME(\n        "button_home",\n        false,\n',
        '    BUTTON_HOME(\n        "button_home",\n        true,\n',
    )

    text = integers.read_text(encoding="utf-8")
    for old, new in [
        ('<integer name="BUTTON_HOME_X">600</integer>', '<integer name="BUTTON_HOME_X">500</integer>'),
        ('<integer name="BUTTON_HOME_X_PORTRAIT">680</integer>', '<integer name="BUTTON_HOME_X_PORTRAIT">500</integer>'),
        ('<integer name="BUTTON_HOME_X_FOLDABLE">680</integer>', '<integer name="BUTTON_HOME_X_FOLDABLE">500</integer>'),
    ]:
        if old not in text:
            raise RuntimeError(f"Missing position: {old}")
        text = text.replace(old, new, 1)
    integers.write_text(text, encoding="utf-8")

    rep(
        menu,
        '    <item\n        android:id="@+id/menu_toggle_controls"\n',
        '    <item\n        android:id="@+id/menu_transparent_overlay"\n'
        '        android:title="@string/mw_overlay_transparent_controls"\n'
        '        android:checkable="true" />\n\n'
        '    <item\n        android:id="@+id/menu_toggle_controls"\n',
    )

    (ROOT / "src/android/app/src/main/res/values/moonwitch_overlay_strings.xml").write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n<resources>\n'
        '    <string name="mw_overlay_transparent_controls">Moonwitch Glass style</string>\n'
        '</resources>\n',
        encoding="utf-8",
    )
    pt = ROOT / "src/android/app/src/main/res/values-pt-rBR"
    pt.mkdir(parents=True, exist_ok=True)
    (pt / "moonwitch_overlay_strings.xml").write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n<resources>\n'
        '    <string name="mw_overlay_transparent_controls">Estilo Moonwitch Glass</string>\n'
        '</resources>\n',
        encoding="utf-8",
    )

    print("Moonwitch Glass controls and Home drawer shortcut applied.")


if __name__ == "__main__":
    main()
