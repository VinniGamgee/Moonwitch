// SPDX-FileCopyrightText: 2026 Moonwitch Project
// SPDX-License-Identifier: GPL-3.0-or-later

package org.yuzu.yuzu_emu.ui.splash

import android.animation.ValueAnimator
import android.content.Context
import android.content.Intent
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.LinearGradient
import android.graphics.Paint
import android.graphics.Path
import android.graphics.RectF
import android.graphics.Shader
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.view.View
import android.view.animation.DecelerateInterpolator
import androidx.appcompat.app.AppCompatActivity
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import androidx.core.view.WindowCompat
import kotlin.math.min
import org.yuzu.yuzu_emu.R
import org.yuzu.yuzu_emu.ui.main.MainActivity
import org.yuzu.yuzu_emu.utils.DirectoryInitialization

/**
 * Moonwitch-owned startup screen.
 *
 * Android 12+ always draws a system splash before the first Activity. The manifest theme
 * makes that system layer blank; this Activity owns the visible branding so Android never
 * gets a chance to square/crop the Moonwitch logo.
 */
class MoonwitchSplashActivity : AppCompatActivity() {
    private val handler = Handler(Looper.getMainLooper())
    private lateinit var splashView: MoonwitchSplashView
    private var animationFinished = false
    private var launchedMain = false

    override fun onCreate(savedInstanceState: Bundle?) {
        installSplashScreen()
        super.onCreate(savedInstanceState)

        WindowCompat.setDecorFitsSystemWindows(window, false)
        window.statusBarColor = Color.TRANSPARENT
        window.navigationBarColor = Color.TRANSPARENT

        splashView = MoonwitchSplashView(this)
        setContentView(splashView)

        splashView.startAnimation {
            animationFinished = true
            continueWhenReady()
        }
    }

    private fun continueWhenReady() {
        if (launchedMain || !animationFinished) return

        if (!DirectoryInitialization.areDirectoriesReady) {
            handler.postDelayed(::continueWhenReady, 40L)
            return
        }

        launchedMain = true

        // Never forward the launcher Intent itself. Launcher/Game Booster flags such as
        // NEW_TASK/RESET_TASK_IF_NEEDED can reset the task when the splash finishes.
        // MainActivity must receive a clean in-app Intent.
        val destination = Intent(this, MainActivity::class.java)

        startActivity(destination)
        overridePendingTransition(0, 0)
        finish()
    }

    override fun onDestroy() {
        handler.removeCallbacksAndMessages(null)
        if (::splashView.isInitialized) splashView.cancelAnimation()
        super.onDestroy()
    }
}

/**
 * Draws the Moonwitch mark piece-by-piece.
 *
 * Everything is vector geometry drawn directly to Canvas:
 * - no bitmap rectangle
 * - no ImageView crop
 * - no adaptive-icon mask
 * - transparent outside the circular logo
 */
private class MoonwitchSplashView(context: Context) : View(context) {
    private val density = resources.displayMetrics.density
    private val backgroundColor = context.getColor(R.color.ic_launcher_background)

    private val fillPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.FILL
    }
    private val strokePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        style = Paint.Style.STROKE
        strokeCap = Paint.Cap.ROUND
        strokeJoin = Paint.Join.ROUND
    }

    private var progress = 0f
    private var animator: ValueAnimator? = null

    private val moonPath = Path().apply {
        moveTo(59f, 26f)
        cubicTo(41f, 26f, 27f, 40f, 27f, 58f)
        cubicTo(27f, 76f, 42f, 89f, 60f, 87f)
        cubicTo(72f, 86f, 82f, 79f, 88f, 68f)
        cubicTo(82f, 73f, 75f, 76f, 67f, 76f)
        cubicTo(54f, 76f, 44f, 66f, 44f, 53f)
        cubicTo(44f, 41f, 50f, 31f, 59f, 26f)
        close()
    }

    private val dpadPath = Path().apply {
        moveTo(17f, 69f)
        lineTo(23f, 69f)
        lineTo(23f, 63f)
        lineTo(31f, 63f)
        lineTo(31f, 69f)
        lineTo(37f, 69f)
        lineTo(37f, 77f)
        lineTo(31f, 77f)
        lineTo(31f, 83f)
        lineTo(23f, 83f)
        lineTo(23f, 77f)
        lineTo(17f, 77f)
        close()
    }

    private val dpadInnerPath = Path().apply {
        moveTo(24.5f, 66f)
        lineTo(29.5f, 66f)
        lineTo(29.5f, 71f)
        lineTo(34.5f, 71f)
        lineTo(34.5f, 75f)
        lineTo(29.5f, 75f)
        lineTo(29.5f, 80f)
        lineTo(24.5f, 80f)
        lineTo(24.5f, 75f)
        lineTo(19.5f, 75f)
        lineTo(19.5f, 71f)
        lineTo(24.5f, 71f)
        close()
    }

    private val sparklePath = Path().apply {
        moveTo(68f, 45f)
        lineTo(71.5f, 50.5f)
        lineTo(77f, 54f)
        lineTo(71.5f, 57.5f)
        lineTo(68f, 63f)
        lineTo(64.5f, 57.5f)
        lineTo(59f, 54f)
        lineTo(64.5f, 50.5f)
        close()
    }

    fun startAnimation(onFinished: () -> Unit) {
        animator?.cancel()
        animator = ValueAnimator.ofFloat(0f, 1f).apply {
            duration = 1150L
            interpolator = DecelerateInterpolator(1.4f)
            addUpdateListener {
                progress = it.animatedValue as Float
                invalidate()
            }
            doOnEndCompat(onFinished)
            start()
        }
    }

    fun cancelAnimation() {
        animator?.cancel()
        animator = null
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        canvas.drawColor(backgroundColor)

        val maxByDp = 156f * density
        val iconSize = min(maxByDp, min(width, height) * 0.42f)
        val left = (width - iconSize) / 2f
        val top = (height - iconSize) / 2f

        canvas.save()
        canvas.translate(left, top)
        val scale = iconSize / 108f
        canvas.scale(scale, scale)

        drawLogo(canvas)

        canvas.restore()
    }

    private fun drawLogo(canvas: Canvas) {
        val ring = phase(0.00f, 0.30f)
        val moon = phase(0.15f, 0.56f)
        val dpad = phase(0.34f, 0.69f)
        val redButton = phase(0.47f, 0.68f)
        val blueButton = phase(0.53f, 0.74f)
        val greenButton = phase(0.59f, 0.80f)
        val yellowButton = phase(0.65f, 0.86f)
        val sparkle = phase(0.76f, 1.00f)

        // Circular body only. There is intentionally no square backing layer.
        fillPaint.shader = null
        fillPaint.color = Color.rgb(9, 10, 18)
        fillPaint.alpha = (255f * phase(0f, 0.18f)).toInt()
        canvas.drawCircle(54f, 54f, 50f, fillPaint)

        // Ring grows from the top in two directions.
        strokePaint.strokeWidth = 4.5f
        strokePaint.alpha = (255f * ring).toInt()
        val ringBounds = RectF(5f, 5f, 103f, 103f)

        strokePaint.color = Color.rgb(225, 59, 255)
        canvas.drawArc(ringBounds, -90f, -180f * ring, false, strokePaint)

        strokePaint.color = Color.rgb(49, 215, 255)
        canvas.drawArc(ringBounds, -90f, 180f * ring, false, strokePaint)

        // Crescent scales into place.
        canvas.save()
        canvas.scale(lerp(0.72f, 1f, easeOutBack(moon)), lerp(0.72f, 1f, easeOutBack(moon)), 58f, 57f)
        fillPaint.alpha = (255f * moon).toInt()
        fillPaint.shader = LinearGradient(
            28f, 82f, 80f, 29f,
            intArrayOf(
                Color.rgb(241, 60, 255),
                Color.rgb(140, 103, 255),
                Color.rgb(53, 216, 255)
            ),
            floatArrayOf(0f, 0.48f, 1f),
            Shader.TileMode.CLAMP
        )
        canvas.drawPath(moonPath, fillPaint)
        fillPaint.shader = null
        canvas.restore()

        // D-pad enters from the left.
        canvas.save()
        canvas.translate(-18f * (1f - smooth(dpad)), 0f)
        fillPaint.alpha = (255f * dpad).toInt()
        fillPaint.color = Color.rgb(41, 41, 68)
        canvas.drawPath(dpadPath, fillPaint)
        fillPaint.color = Color.rgb(53, 54, 83)
        canvas.drawPath(dpadInnerPath, fillPaint)
        canvas.restore()

        drawPopButton(canvas, 78f, 31f, Color.rgb(197, 45, 75), redButton)
        drawPopButton(canvas, 69f, 40f, Color.rgb(23, 102, 202), blueButton)
        drawPopButton(canvas, 87f, 40f, Color.rgb(20, 122, 104), greenButton)
        drawPopButton(canvas, 78f, 49f, Color.rgb(168, 139, 36), yellowButton)

        // Final sparkle locks the whole mark together.
        canvas.save()
        val sparkleScale = lerp(0.25f, 1f, easeOutBack(sparkle))
        canvas.scale(sparkleScale, sparkleScale, 68f, 54f)
        fillPaint.alpha = (255f * sparkle).toInt()
        fillPaint.shader = LinearGradient(
            60f, 61f, 76f, 47f,
            Color.rgb(225, 59, 255),
            Color.rgb(67, 217, 255),
            Shader.TileMode.CLAMP
        )
        canvas.drawPath(sparklePath, fillPaint)
        fillPaint.shader = null
        canvas.restore()
    }

    private fun drawPopButton(canvas: Canvas, x: Float, y: Float, color: Int, amount: Float) {
        if (amount <= 0f) return
        val scale = easeOutBack(amount).coerceAtLeast(0f)
        fillPaint.shader = null
        fillPaint.color = color
        fillPaint.alpha = (255f * amount.coerceIn(0f, 1f)).toInt()
        canvas.drawCircle(x, y, 5f * scale, fillPaint)
    }

    private fun phase(start: Float, end: Float): Float {
        return ((progress - start) / (end - start)).coerceIn(0f, 1f)
    }

    private fun smooth(value: Float): Float {
        val t = value.coerceIn(0f, 1f)
        return t * t * (3f - 2f * t)
    }

    private fun easeOutBack(value: Float): Float {
        val t = value.coerceIn(0f, 1f) - 1f
        val c1 = 1.70158f
        val c3 = c1 + 1f
        return 1f + c3 * t * t * t + c1 * t * t
    }

    private fun lerp(from: Float, to: Float, amount: Float): Float {
        return from + (to - from) * amount
    }

    /**
     * Small local helper so the patch doesn't depend on animation-ktx extension imports.
     */
    private fun ValueAnimator.doOnEndCompat(block: () -> Unit) {
        addListener(object : android.animation.AnimatorListenerAdapter() {
            override fun onAnimationEnd(animation: android.animation.Animator) {
                block()
            }
        })
    }
}
