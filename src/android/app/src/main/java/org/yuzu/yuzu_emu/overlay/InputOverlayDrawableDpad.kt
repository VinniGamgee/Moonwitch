// SPDX-FileCopyrightText: Copyright 2025 Eden Emulator Project
// SPDX-License-Identifier: GPL-3.0-or-later

package org.yuzu.yuzu_emu.overlay

import android.content.res.Resources
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Rect
import android.graphics.drawable.BitmapDrawable
import android.view.MotionEvent
import org.yuzu.yuzu_emu.features.input.NativeInput.ButtonState
import org.yuzu.yuzu_emu.features.input.model.NativeButton
import org.yuzu.yuzu_emu.features.settings.model.BooleanSetting
import org.yuzu.yuzu_emu.features.settings.model.IntSetting

/**
 * Custom [BitmapDrawable] that is capable
 * of storing it's own ID.
 *
 * @param res                             [Resources] instance.
 * @param defaultStateBitmap              [Bitmap] of the default state.
 * @param pressedOneDirectionStateBitmap  [Bitmap] of the pressed state in one direction.
 * @param pressedTwoDirectionsStateBitmap [Bitmap] of the pressed state in two direction.
 */
class InputOverlayDrawableDpad(
    res: Resources,
    defaultStateBitmap: Bitmap,
    pressedOneDirectionStateBitmap: Bitmap,
    pressedTwoDirectionsStateBitmap: Bitmap
) {
    /**
     * Gets one of the InputOverlayDrawableDpad's button IDs.
     *
     * @return the requested InputOverlayDrawableDpad's button ID.
     */
    // The ID identifying what type of button this Drawable represents.
    val up = NativeButton.DUp
    val down = NativeButton.DDown
    val left = NativeButton.DLeft
    val right = NativeButton.DRight
    var trackId: Int

    val width: Int
    val height: Int

    var individualScale: Float = 1.0f

    private val defaultStateBitmap: BitmapDrawable
    private val pressedOneDirectionStateBitmap: BitmapDrawable
    private val pressedTwoDirectionsStateBitmap: BitmapDrawable
    private var opacity = 255

    private var previousTouchX = 0
    private var previousTouchY = 0
    private var controlPositionX = 0
    private var controlPositionY = 0

    private var upButtonState = false
    private var downButtonState = false
    private var leftButtonState = false
    private var rightButtonState = false

    init {
        this.defaultStateBitmap = BitmapDrawable(res, defaultStateBitmap)
        this.pressedOneDirectionStateBitmap = BitmapDrawable(res, pressedOneDirectionStateBitmap)
        this.pressedTwoDirectionsStateBitmap = BitmapDrawable(res, pressedTwoDirectionsStateBitmap)
        width = this.defaultStateBitmap.intrinsicWidth
        height = this.defaultStateBitmap.intrinsicHeight
        trackId = -1
    }

    fun updateStatus(event: MotionEvent, dpad_slide: Boolean): Boolean {
        val pointerIndex = event.actionIndex
        val xPosition = event.getX(pointerIndex).toInt()
        val yPosition = event.getY(pointerIndex).toInt()
        val pointerId = event.getPointerId(pointerIndex)
        val motionEvent = event.action and MotionEvent.ACTION_MASK
        val isActionDown =
            motionEvent == MotionEvent.ACTION_DOWN || motionEvent == MotionEvent.ACTION_POINTER_DOWN
        val isActionUp =
            motionEvent == MotionEvent.ACTION_UP || motionEvent == MotionEvent.ACTION_POINTER_UP
        if (isActionDown) {
            if (!bounds.contains(xPosition, yPosition)) {
                return false
            }
            trackId = pointerId
        }
        if (isActionUp) {
            if (trackId != pointerId) {
                return false
            }
            trackId = -1
            upButtonState = false
            downButtonState = false
            leftButtonState = false
            rightButtonState = false
            return true
        }
        if (trackId == -1) {
            return false
        }
        if (!dpad_slide && !isActionDown) {
            return false
        }
        for (i in 0 until event.pointerCount) {
            if (trackId != event.getPointerId(i)) {
                continue
            }

            var touchX = event.getX(i)
            var touchY = event.getY(i)
            var maxY = bounds.bottom.toFloat()
            var maxX = bounds.right.toFloat()
            touchX -= bounds.centerX().toFloat()
            maxX -= bounds.centerX().toFloat()
            touchY -= bounds.centerY().toFloat()
            maxY -= bounds.centerY().toFloat()
            val axisX = touchX / maxX
            val axisY = touchY / maxY
            val oldUpState = upButtonState
            val oldDownState = downButtonState
            val oldLeftState = leftButtonState
            val oldRightState = rightButtonState

            upButtonState = axisY < -VIRT_AXIS_DEADZONE
            downButtonState = axisY > VIRT_AXIS_DEADZONE
            leftButtonState = axisX < -VIRT_AXIS_DEADZONE
            rightButtonState = axisX > VIRT_AXIS_DEADZONE
            return oldUpState != upButtonState ||
                oldDownState != downButtonState ||
                oldLeftState != leftButtonState ||
                oldRightState != rightButtonState
        }
        return false
    }

    fun draw(canvas: Canvas) {
        MoonwitchOverlayStyle.drawDpad(
            canvas,
            bounds,
            upButtonState,
            downButtonState,
            leftButtonState,
            rightButtonState,
            opacity
        )
    }

    val upStatus: Int
        get() = if (upButtonState) ButtonState.PRESSED else ButtonState.RELEASED
    val downStatus: Int
        get() = if (downButtonState) ButtonState.PRESSED else ButtonState.RELEASED
    val leftStatus: Int
        get() = if (leftButtonState) ButtonState.PRESSED else ButtonState.RELEASED
    val rightStatus: Int
        get() = if (rightButtonState) ButtonState.PRESSED else ButtonState.RELEASED

    fun onConfigureTouch(event: MotionEvent): Boolean {
        val pointerIndex = event.actionIndex
        val fingerPositionX = event.getX(pointerIndex).toInt()
        val fingerPositionY = event.getY(pointerIndex).toInt()

        when (event.action) {
            MotionEvent.ACTION_DOWN -> {
                previousTouchX = fingerPositionX
                previousTouchY = fingerPositionY
            }

            MotionEvent.ACTION_MOVE -> {
                controlPositionX += fingerPositionX - previousTouchX
                controlPositionY += fingerPositionY - previousTouchY

                val finalX = if (BooleanSetting.OVERLAY_SNAP_TO_GRID.getBoolean()) {
                    snapToGrid(controlPositionX)
                } else {
                    controlPositionX
                }
                val finalY = if (BooleanSetting.OVERLAY_SNAP_TO_GRID.getBoolean()) {
                    snapToGrid(controlPositionY)
                } else {
                    controlPositionY
                }

                setBounds(
                    finalX,
                    finalY,
                    width + finalX,
                    height + finalY
                )
                previousTouchX = fingerPositionX
                previousTouchY = fingerPositionY
            }
        }
        return true
    }

    private fun snapToGrid(value: Int): Int {
        val gridSize = IntSetting.OVERLAY_GRID_SIZE.getInt()
        return ((value + gridSize / 2) / gridSize) * gridSize
    }

    fun setPosition(x: Int, y: Int) {
        controlPositionX = x
        controlPositionY = y
    }

    fun setBounds(left: Int, top: Int, right: Int, bottom: Int) {
        defaultStateBitmap.setBounds(left, top, right, bottom)
        pressedOneDirectionStateBitmap.setBounds(left, top, right, bottom)
        pressedTwoDirectionsStateBitmap.setBounds(left, top, right, bottom)
    }

    fun setOpacity(value: Int) {
        opacity = value.coerceIn(0, 255)
        defaultStateBitmap.alpha = opacity
        pressedOneDirectionStateBitmap.alpha = opacity
        pressedTwoDirectionsStateBitmap.alpha = opacity
    }

    val bounds: Rect
        get() = defaultStateBitmap.bounds

    companion object {
        const val VIRT_AXIS_DEADZONE = 0.5f
    }
}
