// SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
// SPDX-License-Identifier: GPL-3.0-or-later

package org.yuzu.yuzu_emu.core

import android.view.InputDevice
import android.view.KeyEvent
import android.view.MotionEvent
import kotlin.math.abs
import org.kenjinx.android.KenjinxNative
import org.yuzu.yuzu_emu.features.input.NativeInput
import org.yuzu.yuzu_emu.features.input.model.NativeAnalog
import org.yuzu.yuzu_emu.features.input.model.NativeButton
import org.yuzu.yuzu_emu.utils.Log

/** Translates Moonwitch/Yuzu Android control identifiers into LibKenjinx input identifiers. */
object KenjiInputBridge {
    private const val TAG = "[KenjiInputBridge]"

    // GamePadButtonInputId ordinals from the pinned Kenji Android ABI.
    private const val A = 1
    private const val B = 2
    private const val X = 3
    private const val Y = 4
    private const val L_STICK = 5
    private const val R_STICK = 6
    private const val L = 7
    private const val R = 8
    private const val ZL = 9
    private const val ZR = 10
    private const val DPAD_UP = 11
    private const val DPAD_DOWN = 12
    private const val DPAD_LEFT = 13
    private const val DPAD_RIGHT = 14
    private const val MINUS = 15
    private const val PLUS = 16

    // StickInputId ordinals used by Kenji Android.
    private const val LEFT_STICK = 1
    private const val RIGHT_STICK = 2

    @Volatile
    private var controllerId = -1

    private var leftTriggerPressed = false
    private var rightTriggerPressed = false

    fun connect() {
        if (controllerId >= 0) return
        controllerId = runCatching { KenjinxNative.inputConnectGamepad(0) }.getOrElse {
            Log.error("$TAG Failed to connect virtual gamepad: ${it.message}")
            -1
        }
        Log.info("$TAG Kenji gamepad id=$controllerId")
    }

    fun disconnect() {
        releaseAllCommonButtons()
        controllerId = -1
        leftTriggerPressed = false
        rightTriggerPressed = false
    }

    fun onOverlayButton(button: NativeButton, action: Int): Boolean {
        if (!MoonwitchKenjiCore.isRunning) return false
        connect()
        val id = mapNativeButton(button) ?: return false
        setButton(id, action == NativeInput.ButtonState.PRESSED)
        return true
    }

    fun onOverlayJoystick(stick: NativeAnalog, x: Float, y: Float): Boolean {
        if (!MoonwitchKenjiCore.isRunning) return false
        connect()
        val stickId = if (stick == NativeAnalog.LStick) LEFT_STICK else RIGHT_STICK
        runCatching { KenjinxNative.inputSetStickAxis(stickId, x, y, controllerId) }
        return true
    }

    fun onKeyEvent(event: KeyEvent): Boolean {
        if (!MoonwitchKenjiCore.isRunning) return false
        val pressed = when (event.action) {
            KeyEvent.ACTION_DOWN -> true
            KeyEvent.ACTION_UP -> false
            else -> return false
        }
        val button = when (event.keyCode) {
            KeyEvent.KEYCODE_BUTTON_A -> A
            KeyEvent.KEYCODE_BUTTON_B -> B
            KeyEvent.KEYCODE_BUTTON_X -> X
            KeyEvent.KEYCODE_BUTTON_Y -> Y
            KeyEvent.KEYCODE_BUTTON_L1 -> L
            KeyEvent.KEYCODE_BUTTON_R1 -> R
            KeyEvent.KEYCODE_BUTTON_L2 -> ZL
            KeyEvent.KEYCODE_BUTTON_R2 -> ZR
            KeyEvent.KEYCODE_BUTTON_THUMBL -> L_STICK
            KeyEvent.KEYCODE_BUTTON_THUMBR -> R_STICK
            KeyEvent.KEYCODE_BUTTON_START -> PLUS
            KeyEvent.KEYCODE_BUTTON_SELECT -> MINUS
            KeyEvent.KEYCODE_DPAD_UP -> DPAD_UP
            KeyEvent.KEYCODE_DPAD_DOWN -> DPAD_DOWN
            KeyEvent.KEYCODE_DPAD_LEFT -> DPAD_LEFT
            KeyEvent.KEYCODE_DPAD_RIGHT -> DPAD_RIGHT
            else -> return false
        }
        connect()
        setButton(button, pressed)
        return true
    }

    fun onMotionEvent(event: MotionEvent): Boolean {
        if (!MoonwitchKenjiCore.isRunning || event.action != MotionEvent.ACTION_MOVE) return false
        connect()

        val device = event.device ?: return false
        fun hasAxis(axis: Int): Boolean =
            device.getMotionRange(axis, InputDevice.SOURCE_JOYSTICK) != null ||
                device.getMotionRange(axis) != null

        fun value(axis: Int): Float = event.getAxisValue(axis)

        val rightX = when {
            hasAxis(MotionEvent.AXIS_RX) -> MotionEvent.AXIS_RX
            else -> MotionEvent.AXIS_Z
        }
        val rightY = when {
            hasAxis(MotionEvent.AXIS_RY) -> MotionEvent.AXIS_RY
            else -> MotionEvent.AXIS_RZ
        }

        runCatching {
            KenjinxNative.inputSetStickAxis(
                LEFT_STICK,
                if (hasAxis(MotionEvent.AXIS_X)) value(MotionEvent.AXIS_X) else 0f,
                if (hasAxis(MotionEvent.AXIS_Y)) -value(MotionEvent.AXIS_Y) else 0f,
                controllerId
            )
            KenjinxNative.inputSetStickAxis(
                RIGHT_STICK,
                if (hasAxis(rightX)) value(rightX) else 0f,
                if (hasAxis(rightY)) -value(rightY) else 0f,
                controllerId
            )
        }

        val lt = when {
            hasAxis(MotionEvent.AXIS_LTRIGGER) -> value(MotionEvent.AXIS_LTRIGGER)
            hasAxis(MotionEvent.AXIS_BRAKE) -> value(MotionEvent.AXIS_BRAKE)
            else -> 0f
        }.let { if (abs(it) < 0.02f) 0f else it.coerceIn(0f, 1f) }

        val rt = when {
            hasAxis(MotionEvent.AXIS_RTRIGGER) -> value(MotionEvent.AXIS_RTRIGGER)
            hasAxis(MotionEvent.AXIS_GAS) -> value(MotionEvent.AXIS_GAS)
            else -> 0f
        }.let { if (abs(it) < 0.02f) 0f else it.coerceIn(0f, 1f) }

        if (!leftTriggerPressed && lt >= 0.65f) {
            leftTriggerPressed = true
            setButton(ZL, true)
        } else if (leftTriggerPressed && lt <= 0.45f) {
            leftTriggerPressed = false
            setButton(ZL, false)
        }

        if (!rightTriggerPressed && rt >= 0.65f) {
            rightTriggerPressed = true
            setButton(ZR, true)
        } else if (rightTriggerPressed && rt <= 0.45f) {
            rightTriggerPressed = false
            setButton(ZR, false)
        }

        val hatX = if (hasAxis(MotionEvent.AXIS_HAT_X)) value(MotionEvent.AXIS_HAT_X) else 0f
        val hatY = if (hasAxis(MotionEvent.AXIS_HAT_Y)) value(MotionEvent.AXIS_HAT_Y) else 0f
        setButton(DPAD_LEFT, hatX < -0.5f)
        setButton(DPAD_RIGHT, hatX > 0.5f)
        setButton(DPAD_UP, hatY < -0.5f)
        setButton(DPAD_DOWN, hatY > 0.5f)
        return true
    }

    private fun setButton(button: Int, pressed: Boolean) {
        if (controllerId < 0) return
        runCatching {
            if (pressed) {
                KenjinxNative.inputSetButtonPressed(button, controllerId)
            } else {
                KenjinxNative.inputSetButtonReleased(button, controllerId)
            }
        }
    }

    private fun mapNativeButton(button: NativeButton): Int? = when (button) {
        NativeButton.A -> A
        NativeButton.B -> B
        NativeButton.X -> X
        NativeButton.Y -> Y
        NativeButton.LStick -> L_STICK
        NativeButton.RStick -> R_STICK
        NativeButton.L -> L
        NativeButton.R -> R
        NativeButton.ZL -> ZL
        NativeButton.ZR -> ZR
        NativeButton.Plus -> PLUS
        NativeButton.Minus -> MINUS
        NativeButton.DLeft -> DPAD_LEFT
        NativeButton.DUp -> DPAD_UP
        NativeButton.DRight -> DPAD_RIGHT
        NativeButton.DDown -> DPAD_DOWN
        else -> null
    }

    private fun releaseAllCommonButtons() {
        if (controllerId < 0) return
        intArrayOf(
            A, B, X, Y, L_STICK, R_STICK, L, R, ZL, ZR,
            DPAD_UP, DPAD_DOWN, DPAD_LEFT, DPAD_RIGHT, MINUS, PLUS
        ).forEach { setButton(it, false) }
    }
}
