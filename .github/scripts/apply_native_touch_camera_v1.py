#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def write(rel, text):
    (ROOT / rel).write_text(text, encoding="utf-8")


def replace_once(rel, old, new, label):
    text = read(rel)
    if new in text:
        return
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match in {rel}, found {count}")
    write(rel, text.replace(old, new, 1))


def patch_native_input():
    rel = "src/android/app/src/main/java/org/yuzu/yuzu_emu/features/input/NativeInput.kt"
    old = "    external fun onTouchReleased(fingerId: Int)\n\n    /**\n     * Sends a button input to the global virtual controllers.\n"
    new = "    external fun onTouchReleased(fingerId: Int)\n\n    /**\n     * Starts Moonwitch native relative touch-camera capture. This path is intentionally\n     * independent from Npad / VirtualGamepad / analog stick input.\n     */\n    external fun onNativeTouchCameraBegin()\n\n    /** Sends raw relative finger motion to the guest HID mouse path. */\n    external fun onNativeTouchCameraDelta(deltaX: Float, deltaY: Float)\n\n    /** Ends relative capture and discards any queued mouse delta. */\n    external fun onNativeTouchCameraEnd()\n\n    /**\n     * Sends a button input to the global virtual controllers.\n"
    replace_once(rel, old, new, "NativeInput native camera API")


def patch_input_overlay():
    rel = "src/android/app/src/main/java/org/yuzu/yuzu_emu/overlay/InputOverlay.kt"
    replace_once(
        rel,
        "    private val moveThreshold = 20f\n",
        "    private val moveThreshold = 20f\n\n"
        "    // Moonwitch native touch camera: raw relative pointer state only.\n"
        "    // This state never represents a joystick position.\n"
        "    private var nativeTouchCameraPointerId = MotionEvent.INVALID_POINTER_ID\n"
        "    private var nativeTouchCameraLastX = 0f\n"
        "    private var nativeTouchCameraLastY = 0f\n"
        "    private val nativeTouchCameraPrefs by lazy {\n"
        "        context.getSharedPreferences(\"moonwitch_native_touch_camera\", Context.MODE_PRIVATE)\n"
        "    }\n",
        "InputOverlay native camera state",
    )

    replace_once(
        rel,
        "        if (shouldUpdateView) {\n            invalidate()\n        }\n\n        if (!BooleanSetting.TOUCHSCREEN.getBoolean()) {\n",
        "        if (shouldUpdateView) {\n            invalidate()\n        }\n\n"
        "        // Camera capture owns only a free, non-overlay pointer. Overlay buttons and sticks\n"
        "        // keep their normal paths, but the camera pointer is never translated to R-Stick.\n"
        "        if (handleNativeTouchCamera(event)) {\n            return true\n        }\n\n"
        "        if (!BooleanSetting.TOUCHSCREEN.getBoolean()) {\n",
        "InputOverlay native camera dispatch",
    )

    helper = '''    private fun handleNativeTouchCamera(event: MotionEvent): Boolean {
        val enabled = nativeTouchCameraPrefs.getBoolean("enabled", false)
        if (!enabled) {
            if (nativeTouchCameraPointerId != MotionEvent.INVALID_POINTER_ID) {
                NativeInput.onNativeTouchCameraEnd()
                nativeTouchCameraPointerId = MotionEvent.INVALID_POINTER_ID
            }
            return false
        }

        when (event.actionMasked) {
            MotionEvent.ACTION_DOWN,
            MotionEvent.ACTION_POINTER_DOWN -> {
                if (nativeTouchCameraPointerId != MotionEvent.INVALID_POINTER_ID) {
                    return true
                }
                val index = event.actionIndex
                val pointerId = event.getPointerId(index)
                if (isTouchInputConsumed(pointerId)) {
                    return false
                }

                nativeTouchCameraPointerId = pointerId
                nativeTouchCameraLastX = event.getX(index)
                nativeTouchCameraLastY = event.getY(index)
                NativeInput.onNativeTouchCameraBegin()
                requestUnbufferedDispatch(event)
                return true
            }

            MotionEvent.ACTION_MOVE -> {
                val pointerId = nativeTouchCameraPointerId
                if (pointerId == MotionEvent.INVALID_POINTER_ID) {
                    return false
                }
                val index = event.findPointerIndex(pointerId)
                if (index < 0) {
                    NativeInput.onNativeTouchCameraEnd()
                    nativeTouchCameraPointerId = MotionEvent.INVALID_POINTER_ID
                    return true
                }

                // Consume every coalesced Android sample. This preserves true gesture deltas instead
                // of converting the finger position into an analog-stick magnitude.
                for (historyIndex in 0 until event.historySize) {
                    dispatchNativeTouchCameraDelta(
                        event.getHistoricalX(index, historyIndex),
                        event.getHistoricalY(index, historyIndex)
                    )
                }
                dispatchNativeTouchCameraDelta(event.getX(index), event.getY(index))
                return true
            }

            MotionEvent.ACTION_UP,
            MotionEvent.ACTION_POINTER_UP -> {
                if (event.getPointerId(event.actionIndex) == nativeTouchCameraPointerId) {
                    NativeInput.onNativeTouchCameraEnd()
                    nativeTouchCameraPointerId = MotionEvent.INVALID_POINTER_ID
                    return true
                }
            }

            MotionEvent.ACTION_CANCEL -> {
                if (nativeTouchCameraPointerId != MotionEvent.INVALID_POINTER_ID) {
                    NativeInput.onNativeTouchCameraEnd()
                    nativeTouchCameraPointerId = MotionEvent.INVALID_POINTER_ID
                    return true
                }
            }
        }
        return nativeTouchCameraPointerId != MotionEvent.INVALID_POINTER_ID
    }

    private fun dispatchNativeTouchCameraDelta(x: Float, y: Float) {
        val deltaX = x - nativeTouchCameraLastX
        val deltaY = y - nativeTouchCameraLastY
        nativeTouchCameraLastX = x
        nativeTouchCameraLastY = y
        if (deltaX == 0f && deltaY == 0f) return
        NativeInput.onNativeTouchCameraDelta(deltaX, deltaY)
    }

'''
    replace_once(
        rel,
        "    private fun playHaptics(event: MotionEvent) {\n",
        helper + "    private fun playHaptics(event: MotionEvent) {\n",
        "InputOverlay native camera helpers",
    )


def patch_emulated_devices():
    header = "src/hid_core/frontend/emulated_devices.h"
    replace_once(
        header,
        "struct MousePosition {\n    f32 x;\n    f32 y;\n};\n",
        "struct MousePosition {\n    f32 x;\n    f32 y;\n};\n\n"
        "struct MouseRelativeDelta {\n    s32 x;\n    s32 y;\n};\n",
        "EmulatedDevices relative mouse type",
    )
    replace_once(
        header,
        "    /// Returns the latest mouse wheel change\n    AnalogStickState GetMouseWheel() const;\n",
        "    /// Returns the latest mouse wheel change\n    AnalogStickState GetMouseWheel() const;\n\n"
        "    /// Adds host-relative mouse motion without routing through any gamepad axis.\n"
        "    void AddMouseRelativeDelta(s32 x, s32 y);\n\n"
        "    /// Atomically consumes host-relative mouse motion queued since the last HID sample.\n"
        "    MouseRelativeDelta ConsumeMouseRelativeDelta();\n",
        "EmulatedDevices relative mouse API",
    )
    replace_once(
        header,
        "    // Stores the current status of all external device input\n    DeviceStatus device_status;\n",
        "    // Stores the current status of all external device input\n    DeviceStatus device_status;\n\n"
        "    // Dedicated host-relative mouse queue used by Moonwitch touch camera.\n"
        "    MouseRelativeDelta mouse_relative_delta{};\n",
        "EmulatedDevices relative mouse member",
    )

    cpp = "src/hid_core/frontend/emulated_devices.cpp"
    methods = '''void EmulatedDevices::AddMouseRelativeDelta(s32 x, s32 y) {
    if (x == 0 && y == 0) {
        return;
    }
    std::scoped_lock lock{mutex};
    mouse_relative_delta.x += x;
    mouse_relative_delta.y += y;
}

MouseRelativeDelta EmulatedDevices::ConsumeMouseRelativeDelta() {
    std::scoped_lock lock{mutex};
    const MouseRelativeDelta delta = mouse_relative_delta;
    mouse_relative_delta = {};
    return delta;
}

'''
    replace_once(
        cpp,
        "KeyboardValues EmulatedDevices::GetKeyboardValues() const {\n",
        methods + "KeyboardValues EmulatedDevices::GetKeyboardValues() const {\n",
        "EmulatedDevices relative mouse implementation",
    )


def patch_mouse_hid():
    rel = "src/hid_core/resources/mouse/mouse.cpp"
    old = '''    if (Settings::values.mouse_enabled) {
        const auto& mouse_button_state = emulated_devices->GetMouseButtons();
        const auto& mouse_position_state = emulated_devices->GetMousePosition();
        const auto& mouse_wheel_state = emulated_devices->GetMouseWheel();
        next_state.attribute.is_connected.Assign(1);
        next_state.x = static_cast<s32>(mouse_position_state.x * Layout::ScreenUndocked::Width);
        next_state.y = static_cast<s32>(mouse_position_state.y * Layout::ScreenUndocked::Height);
        next_state.delta_x = next_state.x - last_entry.x;
        next_state.delta_y = next_state.y - last_entry.y;
        next_state.delta_wheel_x = mouse_wheel_state.x - last_mouse_wheel_state.x;
        next_state.delta_wheel_y = mouse_wheel_state.y - last_mouse_wheel_state.y;

        last_mouse_wheel_state = mouse_wheel_state;
        next_state.button = mouse_button_state;
    }
'''
    new = '''    // Moonwitch native touch camera injects directly into the guest HID mouse delta fields.
    // This is a relative-pointer path; it does not synthesize an Npad or any analog stick.
    const auto relative_delta = emulated_devices->ConsumeMouseRelativeDelta();
    const bool has_relative_delta = relative_delta.x != 0 || relative_delta.y != 0;

    if (Settings::values.mouse_enabled || has_relative_delta) {
        next_state.attribute.is_connected.Assign(1);

        if (Settings::values.mouse_enabled) {
            const auto& mouse_button_state = emulated_devices->GetMouseButtons();
            const auto& mouse_position_state = emulated_devices->GetMousePosition();
            const auto& mouse_wheel_state = emulated_devices->GetMouseWheel();
            next_state.x = static_cast<s32>(mouse_position_state.x * Layout::ScreenUndocked::Width);
            next_state.y = static_cast<s32>(mouse_position_state.y * Layout::ScreenUndocked::Height);
            next_state.delta_x = next_state.x - last_entry.x;
            next_state.delta_y = next_state.y - last_entry.y;
            next_state.delta_wheel_x = mouse_wheel_state.x - last_mouse_wheel_state.x;
            next_state.delta_wheel_y = mouse_wheel_state.y - last_mouse_wheel_state.y;
            last_mouse_wheel_state = mouse_wheel_state;
            next_state.button = mouse_button_state;
        } else {
            // Keep the virtual cursor stationary. Only raw delta_x/delta_y move.
            next_state.x = last_entry.x;
            next_state.y = last_entry.y;
        }

        next_state.delta_x += relative_delta.x;
        next_state.delta_y += relative_delta.y;
    }
'''
    replace_once(rel, old, new, "Guest HID relative mouse delivery")


def patch_native_cpp():
    rel = "src/android/app/src/main/jni/native_input.cpp"
    replace_once(
        rel,
        "#include <common/fs/fs.h>\n",
        "#include <cmath>\n#include <common/fs/fs.h>\n",
        "native_input cmath include",
    )
    replace_once(
        rel,
        '#include "hid_core/frontend/emulated_controller.h"\n',
        '#include "hid_core/frontend/emulated_controller.h"\n#include "hid_core/frontend/emulated_devices.h"\n',
        "native_input emulated devices include",
    )

    methods = '''// MOONWITCH_NATIVE_TOUCH_CAMERA_BEGIN
static bool moonwitch_native_touch_camera_active = false;

void Java_org_yuzu_yuzu_1emu_features_input_NativeInput_onNativeTouchCameraBegin(
    JNIEnv* env, jobject j_obj) {
    moonwitch_native_touch_camera_active = EmulationSession::GetInstance().IsRunning();
    if (!moonwitch_native_touch_camera_active) {
        return;
    }
    auto* devices = EmulationSession::GetInstance().System().HIDCore().GetEmulatedDevices();
    devices->ConsumeMouseRelativeDelta();
}

void Java_org_yuzu_yuzu_1emu_features_input_NativeInput_onNativeTouchCameraDelta(
    JNIEnv* env, jobject j_obj, jfloat j_delta_x, jfloat j_delta_y) {
    if (!moonwitch_native_touch_camera_active || !EmulationSession::GetInstance().IsRunning()) {
        return;
    }

    const auto delta_x = static_cast<s32>(std::lround(j_delta_x));
    const auto delta_y = static_cast<s32>(std::lround(j_delta_y));
    if (delta_x == 0 && delta_y == 0) {
        return;
    }

    auto* devices = EmulationSession::GetInstance().System().HIDCore().GetEmulatedDevices();
    devices->AddMouseRelativeDelta(delta_x, delta_y);
}

void Java_org_yuzu_yuzu_1emu_features_input_NativeInput_onNativeTouchCameraEnd(
    JNIEnv* env, jobject j_obj) {
    moonwitch_native_touch_camera_active = false;
    if (!EmulationSession::GetInstance().IsRunning()) {
        return;
    }
    auto* devices = EmulationSession::GetInstance().System().HIDCore().GetEmulatedDevices();
    devices->ConsumeMouseRelativeDelta();
}
// MOONWITCH_NATIVE_TOUCH_CAMERA_END

'''
    replace_once(
        rel,
        "void Java_org_yuzu_yuzu_1emu_features_input_NativeInput_onOverlayButtonEventImpl(\n",
        methods + "void Java_org_yuzu_yuzu_1emu_features_input_NativeInput_onOverlayButtonEventImpl(\n",
        "native_input relative HID JNI",
    )


def patch_menu_and_fragment():
    menu = "src/android/app/src/main/res/menu/menu_overlay_options.xml"
    replace_once(
        menu,
        "    <item\n        android:id=\"@+id/menu_touchscreen\"\n",
        "    <item\n        android:id=\"@+id/menu_native_touch_camera\"\n"
        "        android:title=\"@string/native_touch_camera\"\n"
        "        android:checkable=\"true\" />\n\n"
        "    <item\n        android:id=\"@+id/menu_touchscreen\"\n",
        "native touch camera menu item",
    )

    for rel, value in [
        ("src/android/app/src/main/res/values/strings.xml", "Native touch camera (relative mouse)"),
        ("src/android/app/src/main/res/values-pt-rBR/strings.xml", "Câmera touch nativa (mouse relativo)"),
    ]:
        text = read(rel)
        if 'name="native_touch_camera"' not in text:
            if "</resources>" not in text:
                raise RuntimeError(f"Missing resources end tag in {rel}")
            text = text.replace("</resources>", f'    <string name="native_touch_camera">{value}</string>\n</resources>', 1)
            write(rel, text)

    frag = "src/android/app/src/main/java/org/yuzu/yuzu_emu/fragments/EmulationFragment.kt"
    replace_once(
        frag,
        "            findItem(R.id.menu_touchscreen).isChecked = BooleanSetting.TOUCHSCREEN.getBoolean()\n",
        "            findItem(R.id.menu_touchscreen).isChecked = BooleanSetting.TOUCHSCREEN.getBoolean()\n"
        "            findItem(R.id.menu_native_touch_camera).isChecked =\n"
        "                requireContext().getSharedPreferences(\"moonwitch_native_touch_camera\", Context.MODE_PRIVATE)\n"
        "                    .getBoolean(\"enabled\", false)\n",
        "native camera menu checked state",
    )
    replace_once(
        frag,
        "                R.id.menu_touchscreen -> {\n                    it.isChecked = !it.isChecked\n                    BooleanSetting.TOUCHSCREEN.setBoolean(it.isChecked)\n                    true\n                }\n\n                R.id.menu_reset_overlay -> {\n",
        "                R.id.menu_touchscreen -> {\n                    it.isChecked = !it.isChecked\n                    BooleanSetting.TOUCHSCREEN.setBoolean(it.isChecked)\n                    true\n                }\n\n"
        "                R.id.menu_native_touch_camera -> {\n"
        "                    it.isChecked = !it.isChecked\n"
        "                    requireContext().getSharedPreferences(\"moonwitch_native_touch_camera\", Context.MODE_PRIVATE)\n"
        "                        .edit().putBoolean(\"enabled\", it.isChecked).apply()\n"
        "                    if (!it.isChecked) {\n                        NativeInput.onNativeTouchCameraEnd()\n                    }\n"
        "                    true\n"
        "                }\n\n"
        "                R.id.menu_reset_overlay -> {\n",
        "native camera menu toggle",
    )


def validate_no_stick_bridge():
    cpp = read("src/android/app/src/main/jni/native_input.cpp")
    start = cpp.index("// MOONWITCH_NATIVE_TOUCH_CAMERA_BEGIN")
    end = cpp.index("// MOONWITCH_NATIVE_TOUCH_CAMERA_END", start)
    camera_cpp = cpp[start:end]
    forbidden_cpp = ["VirtualGamepad", "Npad", "RightStick", "SetStickPosition"]
    for token in forbidden_cpp:
        if token in camera_cpp:
            raise RuntimeError(f"Forbidden gamepad token in native touch camera path: {token}")

    overlay = read("src/android/app/src/main/java/org/yuzu/yuzu_emu/overlay/InputOverlay.kt")
    start = overlay.index("private fun handleNativeTouchCamera")
    end = overlay.index("private fun playHaptics", start)
    camera_overlay = overlay[start:end]
    forbidden_overlay = ["onOverlayJoystickEvent", "NativeAnalog.RStick", "xAxis", "yAxis"]
    for token in forbidden_overlay:
        if token in camera_overlay:
            raise RuntimeError(f"Forbidden analog token in Android native touch camera path: {token}")

    mouse_hid = read("src/hid_core/resources/mouse/mouse.cpp")
    if "next_state.delta_x += relative_delta.x" not in mouse_hid:
        raise RuntimeError("Relative HID mouse delta wiring missing")


def main():
    patch_native_input()
    patch_input_overlay()
    patch_emulated_devices()
    patch_mouse_hid()
    patch_native_cpp()
    patch_menu_and_fragment()
    validate_no_stick_bridge()
    print("Moonwitch native relative touch camera v1 applied: Android delta -> guest HID mouse delta; no R-Stick bridge")


if __name__ == "__main__":
    main()
