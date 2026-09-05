// SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
// SPDX-License-Identifier: GPL-3.0-or-later

package org.yuzu.yuzu_emu.overlay

import android.graphics.Canvas
import android.graphics.Color
import android.graphics.LinearGradient
import android.graphics.Paint
import android.graphics.Path
import android.graphics.RadialGradient
import android.graphics.Rect
import android.graphics.RectF
import android.graphics.Shader
import android.graphics.Typeface
import kotlin.math.max
import kotlin.math.min

/**
 * Moonwitch touch-controller renderer.
 *
 * The geometry and proportions mirror the reference layout supplied for the Moonwitch frontend:
 * near-black controls, a restrained graphite rim, white bold labels, separated D-pad pieces and
 * dual-layer analog sticks. Drawing the controls in Canvas keeps the look identical at every
 * resolution instead of depending on device density or vector drawable tinting.
 */
internal object MoonwitchOverlayStyle {
    private val fillPaint = Paint(Paint.ANTI_ALIAS_FLAG)
    private val strokePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE
    }
    private val textPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.WHITE
        textAlign = Paint.Align.CENTER
        typeface = Typeface.create("sans-serif", Typeface.BOLD)
    }

    fun drawButton(
        canvas: Canvas,
        bounds: Rect,
        controlId: String,
        pressed: Boolean,
        opacity: Int
    ) {
        val alpha = opacity.coerceIn(0, 255)
        when (controlId) {
            "button_zl" -> drawTrigger(canvas, bounds, "ZL", mirror = false, pressed, alpha)
            "button_zr" -> drawTrigger(canvas, bounds, "ZR", mirror = true, pressed, alpha)
            "button_l" -> drawShoulder(canvas, bounds, "L", mirror = false, pressed, alpha)
            "button_r" -> drawShoulder(canvas, bounds, "R", mirror = true, pressed, alpha)
            "button_a" -> drawRoundButton(canvas, bounds, "A", pressed, alpha)
            "button_b" -> drawRoundButton(canvas, bounds, "B", pressed, alpha)
            "button_x" -> drawRoundButton(canvas, bounds, "X", pressed, alpha)
            "button_y" -> drawRoundButton(canvas, bounds, "Y", pressed, alpha)
            "button_stick_l" -> drawRoundButton(canvas, bounds, "L3", pressed, alpha)
            "button_stick_r" -> drawRoundButton(canvas, bounds, "R3", pressed, alpha)
            "button_plus" -> drawRoundButton(canvas, bounds, "+", pressed, alpha, compact = true)
            "button_minus" -> drawRoundButton(canvas, bounds, "-", pressed, alpha, compact = true)
            // The reference has a deliberately unlabelled small button at the top centre.
            "button_home" -> drawRoundButton(canvas, bounds, "", pressed, alpha, compact = true)
            "button_capture" -> drawRoundButton(canvas, bounds, "", pressed, alpha, compact = true)
            else -> drawRoundButton(canvas, bounds, "", pressed, alpha)
        }
    }

    fun drawDpad(
        canvas: Canvas,
        bounds: Rect,
        upPressed: Boolean,
        downPressed: Boolean,
        leftPressed: Boolean,
        rightPressed: Boolean,
        opacity: Int
    ) {
        if (bounds.isEmpty) return
        val r = RectF(bounds)
        val cx = r.centerX()
        val cy = r.centerY()
        val w = r.width()
        val h = r.height()

        // Reference proportions: ~66x81 vertical pieces and ~80x68 horizontal pieces
        // inside a ~210x213 footprint.
        val halfVerticalWidth = w * 0.157f
        val verticalLength = h * 0.382f
        val halfHorizontalHeight = h * 0.160f
        val horizontalLength = w * 0.382f
        val gapX = w * 0.120f
        val gapY = h * 0.118f

        val up = Path().apply {
            moveTo(cx - halfVerticalWidth * 0.76f, r.top)
            quadTo(cx - halfVerticalWidth, r.top, cx - halfVerticalWidth, r.top + h * 0.045f)
            lineTo(cx - halfVerticalWidth, cy - gapY - verticalLength * 0.34f)
            lineTo(cx, cy - gapY)
            lineTo(cx + halfVerticalWidth, cy - gapY - verticalLength * 0.34f)
            lineTo(cx + halfVerticalWidth, r.top + h * 0.045f)
            quadTo(cx + halfVerticalWidth, r.top, cx + halfVerticalWidth * 0.76f, r.top)
            close()
        }
        val down = Path().apply {
            moveTo(cx - halfVerticalWidth, cy + gapY + verticalLength * 0.34f)
            lineTo(cx, cy + gapY)
            lineTo(cx + halfVerticalWidth, cy + gapY + verticalLength * 0.34f)
            lineTo(cx + halfVerticalWidth, r.bottom - h * 0.045f)
            quadTo(cx + halfVerticalWidth, r.bottom, cx + halfVerticalWidth * 0.76f, r.bottom)
            lineTo(cx - halfVerticalWidth * 0.76f, r.bottom)
            quadTo(cx - halfVerticalWidth, r.bottom, cx - halfVerticalWidth, r.bottom - h * 0.045f)
            close()
        }
        val left = Path().apply {
            moveTo(r.left, cy - halfHorizontalHeight * 0.76f)
            quadTo(r.left, cy - halfHorizontalHeight, r.left + w * 0.045f, cy - halfHorizontalHeight)
            lineTo(cx - gapX - horizontalLength * 0.34f, cy - halfHorizontalHeight)
            lineTo(cx - gapX, cy)
            lineTo(cx - gapX - horizontalLength * 0.34f, cy + halfHorizontalHeight)
            lineTo(r.left + w * 0.045f, cy + halfHorizontalHeight)
            quadTo(r.left, cy + halfHorizontalHeight, r.left, cy + halfHorizontalHeight * 0.76f)
            close()
        }
        val right = Path().apply {
            moveTo(cx + gapX + horizontalLength * 0.34f, cy - halfHorizontalHeight)
            lineTo(cx + gapX, cy)
            lineTo(cx + gapX + horizontalLength * 0.34f, cy + halfHorizontalHeight)
            lineTo(r.right - w * 0.045f, cy + halfHorizontalHeight)
            quadTo(r.right, cy + halfHorizontalHeight, r.right, cy + halfHorizontalHeight * 0.76f)
            lineTo(r.right, cy - halfHorizontalHeight * 0.76f)
            quadTo(r.right, cy - halfHorizontalHeight, r.right - w * 0.045f, cy - halfHorizontalHeight)
            close()
        }

        drawDpadPiece(canvas, up, r, upPressed, opacity)
        drawDpadPiece(canvas, down, r, downPressed, opacity)
        drawDpadPiece(canvas, left, r, leftPressed, opacity)
        drawDpadPiece(canvas, right, r, rightPressed, opacity)
    }

    fun drawJoystick(
        canvas: Canvas,
        bounds: Rect,
        xAxis: Float,
        yAxis: Float,
        pressed: Boolean,
        opacity: Int
    ) {
        if (bounds.isEmpty) return
        val rect = RectF(bounds)
        val outerRadius = min(rect.width(), rect.height()) * 0.495f
        val cx = rect.centerX()
        val cy = rect.centerY()
        val alpha = opacity.coerceIn(0, 255)

        fillPaint.alpha = alpha
        fillPaint.style = Paint.Style.FILL
        fillPaint.shader = RadialGradient(
            cx,
            cy,
            outerRadius,
            intArrayOf(
                Color.rgb(if (pressed) 10 else 4, if (pressed) 10 else 4, if (pressed) 10 else 4),
                Color.rgb(0, 0, 0),
                Color.rgb(if (pressed) 25 else 13, if (pressed) 25 else 13, if (pressed) 25 else 13)
            ),
            floatArrayOf(0f, 0.72f, 1f),
            Shader.TileMode.CLAMP
        )
        canvas.drawCircle(cx, cy, outerRadius, fillPaint)

        strokePaint.alpha = alpha
        strokePaint.shader = null
        strokePaint.color = Color.rgb(31, 31, 31)
        strokePaint.strokeWidth = max(1f, outerRadius * 0.012f)
        canvas.drawCircle(cx, cy, outerRadius - strokePaint.strokeWidth / 2f, strokePaint)

        val knobRadius = outerRadius * 0.50f
        val travel = outerRadius - knobRadius * 0.78f
        val knobX = cx + xAxis.coerceIn(-1f, 1f) * travel
        val knobY = cy + yAxis.coerceIn(-1f, 1f) * travel

        fillPaint.alpha = alpha
        fillPaint.shader = LinearGradient(
            knobX,
            knobY - knobRadius,
            knobX,
            knobY + knobRadius,
            if (pressed) Color.rgb(44, 44, 44) else Color.rgb(34, 34, 34),
            if (pressed) Color.rgb(22, 22, 22) else Color.rgb(15, 15, 15),
            Shader.TileMode.CLAMP
        )
        canvas.drawCircle(knobX, knobY, knobRadius, fillPaint)

        strokePaint.color = Color.rgb(42, 42, 42)
        strokePaint.strokeWidth = max(1f, knobRadius * 0.020f)
        canvas.drawCircle(knobX, knobY, knobRadius - strokePaint.strokeWidth / 2f, strokePaint)
        clearShaders()
    }

    private fun drawRoundButton(
        canvas: Canvas,
        bounds: Rect,
        label: String,
        pressed: Boolean,
        opacity: Int,
        compact: Boolean = false
    ) {
        if (bounds.isEmpty) return
        val r = RectF(bounds)
        val radius = min(r.width(), r.height()) * 0.49f
        val cx = r.centerX()
        val cy = r.centerY()

        fillPaint.alpha = opacity
        fillPaint.style = Paint.Style.FILL
        fillPaint.shader = RadialGradient(
            cx,
            cy + radius * 0.08f,
            radius,
            intArrayOf(
                Color.rgb(if (pressed) 22 else 5, if (pressed) 22 else 5, if (pressed) 22 else 5),
                Color.rgb(if (pressed) 10 else 0, if (pressed) 10 else 0, if (pressed) 10 else 0),
                Color.rgb(if (pressed) 42 else 28, if (pressed) 42 else 28, if (pressed) 42 else 28)
            ),
            floatArrayOf(0f, 0.62f, 1f),
            Shader.TileMode.CLAMP
        )
        canvas.drawCircle(cx, cy, radius, fillPaint)

        strokePaint.alpha = opacity
        strokePaint.shader = null
        strokePaint.color = Color.rgb(if (pressed) 70 else 47, if (pressed) 70 else 47, if (pressed) 70 else 47)
        strokePaint.strokeWidth = max(1f, radius * 0.018f)
        canvas.drawCircle(cx, cy, radius - strokePaint.strokeWidth / 2f, strokePaint)

        if (label.isNotEmpty()) {
            textPaint.alpha = opacity
            textPaint.textSize = if (compact) r.height() * 0.43f else r.height() * 0.34f
            val fm = textPaint.fontMetrics
            val baseline = cy - (fm.ascent + fm.descent) / 2f
            canvas.drawText(label, cx, baseline, textPaint)
        }
        clearShaders()
    }

    private fun drawTrigger(
        canvas: Canvas,
        bounds: Rect,
        label: String,
        mirror: Boolean,
        pressed: Boolean,
        opacity: Int
    ) {
        if (bounds.isEmpty) return
        val width = bounds.width().toFloat()
        // The stock trigger vectors are wider than the supplied reference. Keep the exact width
        // supplied by InputOverlay but expand the visual height around the same centre.
        val targetHeight = width / 2.17f
        val r = RectF(
            bounds.left.toFloat(),
            bounds.centerY() - targetHeight / 2f,
            bounds.right.toFloat(),
            bounds.centerY() + targetHeight / 2f
        )
        val p = if (!mirror) leftTriggerPath(r) else mirroredPath(leftTriggerPath(r), r.centerX())
        drawShoulderSurface(canvas, p, r, pressed, opacity)
        drawShoulderLabel(canvas, r, label, opacity, 0.34f)
    }

    private fun drawShoulder(
        canvas: Canvas,
        bounds: Rect,
        label: String,
        mirror: Boolean,
        pressed: Boolean,
        opacity: Int
    ) {
        if (bounds.isEmpty) return
        val width = bounds.width().toFloat()
        val targetHeight = width / 2.20f
        val r = RectF(
            bounds.left.toFloat(),
            bounds.centerY() - targetHeight / 2f,
            bounds.right.toFloat(),
            bounds.centerY() + targetHeight / 2f
        )
        val p = if (!mirror) leftShoulderPath(r) else mirroredPath(leftShoulderPath(r), r.centerX())
        drawShoulderSurface(canvas, p, r, pressed, opacity)
        drawShoulderLabel(canvas, r, label, opacity, 0.35f)
    }

    private fun leftTriggerPath(r: RectF): Path {
        val w = r.width()
        val h = r.height()
        return Path().apply {
            moveTo(r.left + w * 0.20f, r.top)
            quadTo(r.left + w * 0.10f, r.top, r.left + w * 0.075f, r.top + h * 0.18f)
            lineTo(r.left, r.bottom - h * 0.12f)
            quadTo(r.left - w * 0.005f, r.bottom, r.left + w * 0.075f, r.bottom)
            lineTo(r.right - w * 0.075f, r.bottom)
            quadTo(r.right, r.bottom, r.right, r.bottom - h * 0.15f)
            lineTo(r.right, r.top + h * 0.18f)
            quadTo(r.right, r.top, r.right - w * 0.10f, r.top)
            close()
        }
    }

    private fun leftShoulderPath(r: RectF): Path {
        val w = r.width()
        val h = r.height()
        return Path().apply {
            moveTo(r.left + w * 0.04f, r.top)
            lineTo(r.right - w * 0.09f, r.top)
            quadTo(r.right, r.top, r.right, r.top + h * 0.13f)
            lineTo(r.right, r.bottom - h * 0.13f)
            quadTo(r.right, r.bottom, r.right - w * 0.09f, r.bottom)
            lineTo(r.left + w * 0.18f, r.bottom)
            quadTo(r.left + w * 0.13f, r.bottom, r.left + w * 0.10f, r.bottom - h * 0.08f)
            lineTo(r.left, r.top + h * 0.13f)
            quadTo(r.left - w * 0.005f, r.top, r.left + w * 0.04f, r.top)
            close()
        }
    }

    private fun mirroredPath(source: Path, cx: Float): Path {
        val matrix = android.graphics.Matrix().apply {
            setScale(-1f, 1f, cx, 0f)
        }
        return Path(source).apply { transform(matrix) }
    }

    private fun drawShoulderSurface(
        canvas: Canvas,
        path: Path,
        r: RectF,
        pressed: Boolean,
        opacity: Int
    ) {
        fillPaint.alpha = opacity
        fillPaint.style = Paint.Style.FILL
        fillPaint.shader = LinearGradient(
            r.left,
            r.top,
            r.right,
            r.bottom,
            intArrayOf(
                Color.rgb(if (pressed) 33 else 21, if (pressed) 33 else 21, if (pressed) 33 else 21),
                Color.rgb(if (pressed) 11 else 0, if (pressed) 11 else 0, if (pressed) 11 else 0),
                Color.rgb(if (pressed) 26 else 10, if (pressed) 26 else 10, if (pressed) 26 else 10)
            ),
            floatArrayOf(0f, 0.58f, 1f),
            Shader.TileMode.CLAMP
        )
        canvas.drawPath(path, fillPaint)

        strokePaint.alpha = opacity
        strokePaint.shader = null
        strokePaint.color = Color.rgb(if (pressed) 67 else 44, if (pressed) 67 else 44, if (pressed) 67 else 44)
        strokePaint.strokeWidth = max(1f, min(r.width(), r.height()) * 0.014f)
        canvas.drawPath(path, strokePaint)
        clearShaders()
    }

    private fun drawShoulderLabel(
        canvas: Canvas,
        r: RectF,
        label: String,
        opacity: Int,
        sizeFactor: Float
    ) {
        textPaint.alpha = opacity
        textPaint.textSize = r.height() * sizeFactor
        val fm = textPaint.fontMetrics
        val baseline = r.centerY() - (fm.ascent + fm.descent) / 2f
        canvas.drawText(label, r.centerX(), baseline, textPaint)
    }

    private fun drawDpadPiece(
        canvas: Canvas,
        path: Path,
        whole: RectF,
        pressed: Boolean,
        opacity: Int
    ) {
        fillPaint.alpha = opacity
        fillPaint.style = Paint.Style.FILL
        fillPaint.shader = LinearGradient(
            whole.left,
            whole.top,
            whole.right,
            whole.bottom,
            if (pressed) Color.rgb(31, 31, 31) else Color.rgb(16, 16, 16),
            if (pressed) Color.rgb(10, 10, 10) else Color.rgb(0, 0, 0),
            Shader.TileMode.CLAMP
        )
        canvas.drawPath(path, fillPaint)

        strokePaint.alpha = opacity
        strokePaint.shader = null
        strokePaint.color = Color.rgb(if (pressed) 58 else 35, if (pressed) 58 else 35, if (pressed) 58 else 35)
        strokePaint.strokeWidth = max(1f, min(whole.width(), whole.height()) * 0.005f)
        canvas.drawPath(path, strokePaint)
        clearShaders()
    }

    private fun clearShaders() {
        fillPaint.shader = null
        strokePaint.shader = null
    }
}
