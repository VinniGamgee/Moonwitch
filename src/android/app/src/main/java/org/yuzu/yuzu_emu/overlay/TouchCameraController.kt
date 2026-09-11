// SPDX-FileCopyrightText: 2026 Moonwitch Project
// SPDX-License-Identifier: GPL-3.0-or-later

package org.yuzu.yuzu_emu.overlay

/**
 * Converts relative finger movement into camera-axis samples.
 *
 * Unlike a virtual joystick, the initial touch position is never used as a stick centre. Only the
 * distance moved since the previous sample affects the output.
 */
class TouchCameraController(
    private val sensitivity: Int = DEFAULT_SENSITIVITY
) {
    private var activePointerId = INVALID_POINTER_ID
    private var lastX = 0f
    private var lastY = 0f
    private var lastEventTime = 0L

    var xAxis = 0f
        private set
    var yAxis = 0f
        private set

    val isActive: Boolean
        get() = activePointerId != INVALID_POINTER_ID

    fun begin(pointerId: Int, x: Float, y: Float, eventTime: Long): Boolean {
        if (isActive) {
            return false
        }
        activePointerId = pointerId
        lastX = x
        lastY = y
        lastEventTime = eventTime
        xAxis = 0f
        yAxis = 0f
        return true
    }

    fun owns(pointerId: Int): Boolean = pointerId == activePointerId

    fun move(pointerId: Int, x: Float, y: Float, eventTime: Long): Boolean {
        if (!owns(pointerId)) {
            return false
        }

        val deltaX = x - lastX
        val deltaY = y - lastY
        val elapsedMillis = (eventTime - lastEventTime).coerceIn(
            MIN_SAMPLE_INTERVAL_MILLIS,
            MAX_SAMPLE_INTERVAL_MILLIS
        )

        lastX = x
        lastY = y
        lastEventTime = eventTime

        if (deltaX == 0f && deltaY == 0f) {
            return false
        }

        val sampleScale = REFERENCE_SAMPLE_MILLIS / elapsedMillis.toFloat()
        val sensitivityMultiplier = sensitivity.coerceIn(MIN_SENSITIVITY, MAX_SENSITIVITY) / 50f

        xAxis = (deltaX * BASE_SENSITIVITY * sensitivityMultiplier * sampleScale)
            .coerceIn(-1f, 1f)
        yAxis = (-deltaY * BASE_SENSITIVITY * sensitivityMultiplier * sampleScale)
            .coerceIn(-1f, 1f)
        return true
    }

    fun end(pointerId: Int): Boolean {
        if (!owns(pointerId)) {
            return false
        }
        activePointerId = INVALID_POINTER_ID
        return true
    }

    fun recenter() {
        xAxis = 0f
        yAxis = 0f
    }

    fun cancel(): Boolean {
        if (!isActive) {
            return false
        }
        activePointerId = INVALID_POINTER_ID
        recenter()
        return true
    }

    companion object {
        private const val INVALID_POINTER_ID = -1
        private const val MIN_SENSITIVITY = 1
        private const val MAX_SENSITIVITY = 100
        private const val DEFAULT_SENSITIVITY = 70
        private const val BASE_SENSITIVITY = 0.012f
        private const val REFERENCE_SAMPLE_MILLIS = 16f
        private const val MIN_SAMPLE_INTERVAL_MILLIS = 4L
        private const val MAX_SAMPLE_INTERVAL_MILLIS = 32L
    }
}
