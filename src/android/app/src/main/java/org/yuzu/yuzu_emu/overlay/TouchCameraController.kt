// SPDX-FileCopyrightText: 2026 Moonwitch Project
// SPDX-License-Identifier: GPL-3.0-or-later

package org.yuzu.yuzu_emu.overlay

/**
 * Stage 1 Touch Camera controller.
 *
 * Converts raw finger movement into right-stick camera input.
 * This is not a virtual joystick: the finger movement itself is the input.
 */
class TouchCameraController {
    private var activePointerId = -1
    private var lastX = 0f
    private var lastY = 0f

    var enabled = true

    private val sensitivity = 0.0045f

    fun begin(pointerId: Int, x: Float, y: Float) {
        activePointerId = pointerId
        lastX = x
        lastY = y
    }

    fun move(pointerId: Int, x: Float, y: Float): FloatArray? {
        if (!enabled || pointerId != activePointerId) {
            return null
        }

        val deltaX = x - lastX
        val deltaY = y - lastY

        lastX = x
        lastY = y

        return floatArrayOf(
            (deltaX * sensitivity).coerceIn(-1f, 1f),
            (-deltaY * sensitivity).coerceIn(-1f, 1f)
        )
    }

    fun end(pointerId: Int) {
        if (pointerId == activePointerId) {
            activePointerId = -1
        }
    }
}
