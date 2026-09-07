// SPDX-FileCopyrightText: 2026 Moonwitch Project
// SPDX-License-Identifier: GPL-3.0-or-later

package org.yuzu.yuzu_emu.ui.splash

import android.animation.Animator
import android.animation.AnimatorListenerAdapter
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
 * Moonwitch-owned startup animation.
 *
 * Android's mandatory splash is kept blank. The visible logo is drawn here directly on
 * Canvas, so there is no bitmap rectangle or adaptive-icon mask that can turn it square.
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
        if (launchedMain || !animationFinished || isFinishing || isDestroyed) return

        if (!DirectoryInitialization.areDirectoriesReady) {
            handler.postDelayed(::continueWhenReady, 40L)
            return
        }

        launchedMain = true
        val destination = Intent(intent).apply {
            setClass(this@MoonwitchSplashActivity, MainActivity::class.java)
            removeCategory(Intent.CATEGORY_LAUNCHER)
        }

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

private class MoonwitchSplashView(context: Context) : View(context) {
    private val density = resources.displayMetrics.density
    private val backgroundColor = context.getColor(R.color.eden_background)

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
    private var completion: (() -> Unit)? = null

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
        cancelAnimation()
        completion = onFinished
        animator = ValueAnimator.ofFloat(0f, 1f).apply {
            duration = 1200L
            interpolator = DecelerateInterpolator(1.35f)
            addUpdateListener {
                progress = it.animatedValue as Float
                invalidate()
            }
            addListener(object : AnimatorListenerAdapter() {
                private var cancelled = false

                override fun onAnimationCancel(animation: Animator) {
                    cancelled = true
                }

                override fun onAnimationEnd(animation: Animator) {
                    val callback = completion
                    completion = null
                    if (!cancelled) callback?.invoke()
                }
            })
            start()
        }
    }

    fun cancelAnimation() {
        completion = null
        animator?.cancel()
        animator = null
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        canvas.drawColor(backgroundColor)

        val maxSize = 164f * density
        val iconSize = min(maxSize, min(width, height) * 0.44f)
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
        val body = phase(0.00f, 0.16f)
        val ring = phase(0.00f, 0.31f)
        val moon = phase(0.14f, 0.56f)
        val dpad = phase(0.34f, 0.70f)
        val red = phase(0.46f, 0.67f)
        val blue = phase(0.52f, 0.73f)
        val green = phase(0.58f, 0.79f)
        val yellow = phase(0.64f, 0.85f)
        val sparkle = phase(0.75f, 1.00f)

        // Circular body only — there is deliberately no square backing layer.
        fillPaint.shader = null
        fillPaint.color = Color.rgb(9, 10, 18)
        fillPaint.alpha = (255f * body).toInt()
        canvas.drawCircle(54f, 54f, 50f, fillPaint)

        // The border assembles from the top in opposite directions.
        strokePaint.strokeWidth = 4.5f
        strokePaint.alpha = (255f * ring).toInt()
        val bounds = RectF(5f, 5f, 103f, 103f)

        strokePaint.color = Color.rgb(225, 59, 255)
        canvas.drawArc(bounds, -90f, -180f * ring, false, strokePaint)
        strokePaint.color = Color.rgb(49, 215, 255)
        canvas.drawArc(bounds, -90f, 180f * ring, false, strokePaint)

        // Crescent grows into the center.
        canvas.save()
        val moonScale = lerp(0.72f, 1f, easeOutBack(moon))
        canvas.scale(moonScale, moonScale, 58f, 57f)
        fillPaint.alpha = (255f * moon).toInt()
        fillPaint.shader = LinearGradient(
            28f,
            82f,
            80f,
            29f,
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

        // D-pad slides in from the left.
        canvas.save()
        canvas.translate(-18f * (1f - smooth(dpad)), 0f)
        fillPaint.alpha = (255f * dpad).toInt()
        fillPaint.color = Color.rgb(41, 41, 68)
        canvas.drawPath(dpadPath, fillPaint)
        fillPaint.color = Color.rgb(53, 54, 83)
        canvas.drawPath(dpadInnerPath, fillPaint)
        canvas.restore()

        // Switch-style action buttons pop in one after another.
        drawPopButton(canvas, 78f, 31f, Color.rgb(197, 45, 75), red)
        drawPopButton(canvas, 69f, 40f, Color.rgb(23, 102, 202), blue)
        drawPopButton(canvas, 87f, 40f, Color.rgb(20, 122, 104), green)
        drawPopButton(canvas, 78f, 49f, Color.rgb(168, 139, 36), yellow)

        // Final sparkle locks the complete Moonwitch mark together.
        canvas.save()
        val sparkleScale = lerp(0.25f, 1f, easeOutBack(sparkle))
        canvas.scale(sparkleScale, sparkleScale, 68f, 54f)
        fillPaint.alpha = (255f * sparkle).toInt()
        fillPaint.shader = LinearGradient(
            60f,
            61f,
            76f,
            47f,
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
        val visibleAmount = amount.coerceIn(0f, 1f)
        val scale = easeOutBack(visibleAmount).coerceAtLeast(0f)
        fillPaint.shader = null
        fillPaint.color = color
        fillPaint.alpha = (255f * visibleAmount).toInt()
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
}
