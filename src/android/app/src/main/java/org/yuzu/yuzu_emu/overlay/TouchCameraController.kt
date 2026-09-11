// SPDX-FileCopyrightText: 2026 Moonwitch Project
// SPDX-License-Identifier: GPL-3.0-or-later

package org.yuzu.yuzu_emu.overlay

import kotlin.math.pow
import kotlin.math.sqrt

/**
 * Converts relative finger movement into camera-axis samples.
 *
 * The initial touch position is never treated as a virtual-stick centre. Only movement since the
 * previous Android touch sample affects the emulated right stick.
 */
class TouchCameraController {
    private var activePointerId = INVALID_POINTER_ID
    private var lastX = 0f
    private var lastY = 0f
    private var lastEventTime = 0L

    private var sensitivityLevel = DEFAULT_SENSITIVITY_LEVEL
    private var accelerationEnabled = false
    private var smoothingEnabled = false
    private var invertX = false
    private var invertY = false

    var xAxis = 0f
        private set
    var yAxis = 0f
        private set

    val isActive: Boolean
        get() = activePointerId != INVALID_POINTER_ID

    fun configure(
        sensitivityLevel: Int,
        accelerationEnabled: Boolean,
        smoothingEnabled: Boolean,
        invertX: Boolean,
        invertY: Boolean
    ) {
        this.sensitivityLevel = sensitivityLevel.coerceIn(
            MIN_SENSITIVITY_LEVEL,
            MAX_SENSITIVITY_LEVEL
        )
        this.accelerationEnabled = accelerationEnabled
        this.smoothingEnabled = smoothingEnabled
        this.invertX = invertX
        this.invertY = invertY
    }

    fun begin(pointerId: Int, x: Float, y: Float, eventTime: Long): Boolean {
        if (isActive) {
            return false
        }

        activePointerId = pointerId
        lastX = x
        lastY = y
        lastEventTime = eventTime
        recenter()
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

        // Keep the same perceived speed on 60/120/240 Hz touch panels.
        val sampleScale = REFERENCE_SAMPLE_MILLIS / elapsedMillis.toFloat()
        val sensitivity = BASE_SENSITIVITY *
            (sensitivityLevel.toFloat() / DEFAULT_SENSITIVITY_LEVEL.toFloat())
        val accelerationGain = calculateAccelerationGain(deltaX, deltaY, sampleScale)

        val xDirection = if (invertX) -1f else 1f
        // Android Y grows downwards while the Switch stick Y grows upwards.
        val yDirection = if (invertY) 1f else -1f
        val targetX = deltaX * sensitivity * sampleScale * accelerationGain * xDirection
        val targetY = deltaY * sensitivity * sampleScale * accelerationGain * yDirection

        if (smoothingEnabled) {
            // Time-aware exponential smoothing avoids making 120/240 Hz panels feel heavier.
            val alpha = 1f - (1f - SMOOTHING_ALPHA_AT_60_HZ).pow(
                elapsedMillis.toFloat() / REFERENCE_SAMPLE_MILLIS
            )
            xAxis += (targetX - xAxis) * alpha
            yAxis += (targetY - yAxis) * alpha
        } else {
            xAxis = targetX
            yAxis = targetY
        }

        xAxis = xAxis.coerceIn(-1f, 1f)
        yAxis = yAxis.coerceIn(-1f, 1f)
        return true
    }

    private fun calculateAccelerationGain(deltaX: Float, deltaY: Float, sampleScale: Float): Float {
        if (!accelerationEnabled) {
            return 1f
        }

        // Slow movements retain 1:1 precision. The quadratic ramp only boosts deliberate swipes.
        val distanceAtReferenceRate = sqrt(deltaX * deltaX + deltaY * deltaY) * sampleScale
        val progress = (
            (distanceAtReferenceRate - ACCELERATION_START_DISTANCE) /
                (ACCELERATION_FULL_DISTANCE - ACCELERATION_START_DISTANCE)
            ).coerceIn(0f, 1f)
        return 1f + ACCELERATION_MAX_EXTRA_GAIN * progress * progress
    }

    fun end(pointerId: Int): Boolean {
        if (!owns(pointerId)) {
            return false
        }
        // Keep the final sample until InputOverlay's short recenter timeout so flicks are not lost
        // before the emulated game has a chance to sample the right stick.
        activePointerId = INVALID_POINTER_ID
        return true
    }

    fun recenter() {
        xAxis = 0f
        yAxis = 0f
    }

    fun cancel(): Boolean {
        val wasActive = isActive
        activePointerId = INVALID_POINTER_ID
        recenter()
        return wasActive
    }

    companion object {
        const val MIN_SENSITIVITY_LEVEL = 1
        const val MAX_SENSITIVITY_LEVEL = 10
        const val DEFAULT_SENSITIVITY_LEVEL = 5

        private const val INVALID_POINTER_ID = -1
        private const val BASE_SENSITIVITY = 0.012f
        private const val REFERENCE_SAMPLE_MILLIS = 16f
        private const val MIN_SAMPLE_INTERVAL_MILLIS = 4L
        private const val MAX_SAMPLE_INTERVAL_MILLIS = 32L

        private const val ACCELERATION_START_DISTANCE = 4f
        private const val ACCELERATION_FULL_DISTANCE = 24f
        private const val ACCELERATION_MAX_EXTRA_GAIN = 1.25f
        private const val SMOOTHING_ALPHA_AT_60_HZ = 0.5f
    }
}
