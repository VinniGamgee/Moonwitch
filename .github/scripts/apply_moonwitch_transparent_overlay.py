#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def rep(path, old, new):
    p = ROOT / path
    text = p.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"Missing expected block in {path}: {old[:80]!r}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")


def main():
    overlay = "src/android/app/src/main/java/org/yuzu/yuzu_emu/overlay/InputOverlay.kt"
    fragment = "src/android/app/src/main/java/org/yuzu/yuzu_emu/fragments/EmulationFragment.kt"
    control = "src/android/app/src/main/java/org/yuzu/yuzu_emu/overlay/model/OverlayControl.kt"
    integers = ROOT / "src/android/app/src/main/res/values/integers.xml"
    menu = "src/android/app/src/main/res/menu/menu_overlay_options.xml"

    rep(overlay,
        "    var touchEventListener: ((MotionEvent) -> Unit)? = null\n",
        "    var touchEventListener: ((MotionEvent) -> Unit)? = null\n"
        "    var moonwitchHomeListener: (() -> Unit)? = null\n")

    rep(overlay,
        "            checkForNewControls(overlayControlData)\n        }\n\n        // Load the controls.\n",
        "            checkForNewControls(overlayControlData)\n        }\n\n"
        "        ensureMoonwitchHomeShortcutEnabled()\n\n        // Load the controls.\n")

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

    rep(overlay,
        "            val vectorDrawable = ContextCompat.getDrawable(context, drawableId) as VectorDrawable\n",
        "            val vectorDrawable = (ContextCompat.getDrawable(context, drawableId) as VectorDrawable).mutate() as VectorDrawable\n"
        "            if (isTransparentStyle(context)) {\n"
        "                vectorDrawable.setTint(Color.WHITE)\n"
        "                vectorDrawable.alpha = 165\n"
        "            }\n")

    rep(fragment,
        "import org.yuzu.yuzu_emu.overlay.model.OverlayControl\n",
        "import org.yuzu.yuzu_emu.overlay.InputOverlay\nimport org.yuzu.yuzu_emu.overlay.model.OverlayControl\n")

    rep(fragment,
        "        binding.doneControlConfig.setOnClickListener { stopConfiguringControls() }\n",
        "        binding.doneControlConfig.setOnClickListener { stopConfiguringControls() }\n"
        "        binding.surfaceInputOverlay.moonwitchHomeListener = { openMoonwitchInGameDrawer() }\n")

    rep(fragment,
        "        _binding?.surfaceInputOverlay?.touchEventListener = null\n        _binding = null\n",
        "        _binding?.surfaceInputOverlay?.touchEventListener = null\n"
        "        _binding?.surfaceInputOverlay?.moonwitchHomeListener = null\n        _binding = null\n")

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

    rep(fragment,
        "            findItem(R.id.menu_touchscreen).isChecked = BooleanSetting.TOUCHSCREEN.getBoolean()\n",
        "            findItem(R.id.menu_touchscreen).isChecked = BooleanSetting.TOUCHSCREEN.getBoolean()\n"
        "            findItem(R.id.menu_transparent_overlay).isChecked = InputOverlay.isTransparentStyle(requireContext())\n")

    rep(fragment,
        "                R.id.menu_toggle_controls -> {\n",
        "                R.id.menu_transparent_overlay -> {\n"
        "                    it.isChecked = !it.isChecked\n"
        "                    InputOverlay.setTransparentStyle(requireContext(), it.isChecked)\n"
        "                    binding.surfaceInputOverlay.refreshControls()\n"
        "                    true\n"
        "                }\n\n"
        "                R.id.menu_toggle_controls -> {\n")

    rep(control,
        "    BUTTON_HOME(\n        \"button_home\",\n        false,\n",
        "    BUTTON_HOME(\n        \"button_home\",\n        true,\n")

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

    rep(menu,
        "    <item\n        android:id=\"@+id/menu_toggle_controls\"\n",
        "    <item\n        android:id=\"@+id/menu_transparent_overlay\"\n"
        "        android:title=\"@string/mw_overlay_transparent_controls\"\n"
        "        android:checkable=\"true\" />\n\n"
        "    <item\n        android:id=\"@+id/menu_toggle_controls\"\n")

    (ROOT / "src/android/app/src/main/res/values/moonwitch_overlay_strings.xml").write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n<resources>\n'
        '    <string name="mw_overlay_transparent_controls">Transparent controls</string>\n'
        '</resources>\n', encoding="utf-8")
    pt = ROOT / "src/android/app/src/main/res/values-pt-rBR"
    pt.mkdir(parents=True, exist_ok=True)
    (pt / "moonwitch_overlay_strings.xml").write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n<resources>\n'
        '    <string name="mw_overlay_transparent_controls">Controles transparentes</string>\n'
        '</resources>\n', encoding="utf-8")

    print("Moonwitch transparent controls and Home drawer shortcut applied.")


if __name__ == "__main__":
    main()
