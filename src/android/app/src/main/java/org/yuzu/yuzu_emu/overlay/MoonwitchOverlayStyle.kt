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
 * The supplied black background is only a presentation backdrop. The actual controls are rendered
 * as soft translucent glass so the game remains visible underneath them, even when overlay opacity
 * is set to 100%.
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

        // Outer analog ring: translucent glass, never an opaque black disc.
        fillPaint.alpha = alpha
        fillPaint.style = Paint.Style.FILL
        fillPaint.shader = RadialGradient(
            cx,
            cy,
            outerRadius,
            intArrayOf(
                Color.argb(if (pressed) 22 else 12, 210, 210, 210),
                Color.argb(if (pressed) 28 else 16, 150, 150, 150),
                Color.argb(if (pressed) 52 else 34, 235, 235, 235)
            ),
            floatArrayOf(0f, 0.72f, 1f),
            Shader.TileMode.CLAMP
        )
        canvas.drawCircle(cx, cy, outerRadius, fillPaint)

        strokePaint.alpha = alpha
        strokePaint.shader = null
        strokePaint.color = Color.argb(if (pressed) 105 else 76, 235, 235, 235)
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
            Color.argb(if (pressed) 88 else 66, 245, 245, 245),
            Color.argb(if (pressed) 52 else 38, 125, 125, 125),
            Shader.TileMode.CLAMP
        )
        canvas.drawCircle(knobX, knobY, knobRadius, fillPaint)

        strokePaint.color = Color.argb(if (pressed) 126 else 92, 245, 245, 245)
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
                Color.argb(if (pressed) 64 else 42, 235, 235, 235),
                Color.argb(if (pressed) 38 else 22, 145, 145, 145),
                Color.argb(if (pressed) 82 else 54, 245, 245, 245)
            ),
            floatArrayOf(0f, 0.62f, 1f),
            Shader.TileMode.CLAMP
        )
        canvas.drawCircle(cx, cy, radius, fillPaint)

        strokePaint.alpha = opacity
        strokePaint.shader = null
        strokePaint.color = Color.argb(if (pressed) 135 else 94, 245, 245, 245)
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
                Color.argb(if (pressed) 82 else 52, 245, 245, 245),
                Color.argb(if (pressed) 34 else 18, 130, 130, 130),
                Color.argb(if (pressed) 68 else 42, 225, 225, 225)
            ),
            floatArrayOf(0f, 0.58f, 1f),
            Shader.TileMode.CLAMP
        )
        canvas.drawPath(path, fillPaint)

        strokePaint.alpha = opacity
        strokePaint.shader = null
        strokePaint.color = Color.argb(if (pressed) 136 else 92, 245, 245, 245)
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
            Color.argb(if (pressed) 72 else 44, 238, 238, 238),
            Color.argb(if (pressed) 34 else 20, 130, 130, 130),
            Shader.TileMode.CLAMP
        )
        canvas.drawPath(path, fillPaint)

        strokePaint.alpha = opacity
        strokePaint.shader = null
        strokePaint.color = Color.argb(if (pressed) 126 else 82, 245, 245, 245)
        strokePaint.strokeWidth = max(1f, min(whole.width(), whole.height()) * 0.005f)
        canvas.drawPath(path, strokePaint)
        clearShaders()
    }

    private fun clearShaders() {
        fillPaint.shader = null
        strokePaint.shader = null
    }
}
