// SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
// SPDX-License-Identifier: GPL-3.0-or-later

package org.yuzu.yuzu_emu.utils

import android.content.Context
import android.os.Build
import androidx.annotation.StringRes
import java.io.File
import java.util.Locale
import org.yuzu.yuzu_emu.R
import org.yuzu.yuzu_emu.features.settings.model.BooleanSetting
import org.yuzu.yuzu_emu.features.settings.model.IntSetting
import org.yuzu.yuzu_emu.features.settings.model.StringSetting
import org.yuzu.yuzu_emu.features.settings.utils.SettingsFile
import org.yuzu.yuzu_emu.model.Game

/**
 * Applies small, auditable per-game profiles for hardware that has been explicitly validated.
 *
 * This intentionally avoids broad "optimization" guesses. Unsupported devices only receive an
 * informational result and their configuration is never changed.
 */
object DeviceProfileManager {
    private const val TOTK_TITLE_ID = "0100F2C0115B6000"
    private const val POCO_F5_TOTK_PIPELINE_WORKERS = 4
    private const val POCO_F5_TOTK_EDS_LEVEL = 1
    private val pocoF5Models = setOf("23049PCD8G", "23049PCD8I")

    data class Preview(
        val deviceName: String,
        val socName: String,
        val recommendation: Recommendation?
    )

    data class Recommendation(
        @StringRes val profileNameId: Int,
        @StringRes val changesId: Int,
        @StringRes val driverNameId: Int,
        val integerSettings: Map<IntSetting, Int>,
        val booleanSettings: Map<BooleanSetting, Boolean>,
        val driverIntegerSettings: Map<IntSetting, Int> = emptyMap(),
        val driverBooleanSettings: Map<BooleanSetting, Boolean> = emptyMap()
    )

    data class ApplyResult(
        val applied: Boolean,
        val driverOutcome: DriverOutcome
    )

    fun currentDeviceName(): String = deviceName(isPocoF5())

    enum class DriverOutcome {
        SELECTED,
        ALREADY_SELECTED,
        NOT_INSTALLED,
        BUSY,
        FAILED
    }

    fun preview(game: Game): Preview {
        val isPocoF5 = isPocoF5()
        return Preview(
            deviceName = deviceName(isPocoF5),
            socName = socName(),
            recommendation = if (isPocoF5) recommendationFor(game) else null
        )
    }

    fun cardDetails(context: Context, game: Game): String {
        val preview = preview(game)
        val profile = preview.recommendation
        return if (profile == null) {
            context.getString(
                R.string.device_profile_card_unavailable,
                preview.deviceName
            )
        } else {
            context.getString(
                R.string.device_profile_card_detected,
                preview.deviceName,
                context.getString(profile.profileNameId)
            )
        }
    }

    fun isRecommendedDriverInstalled(): Boolean = findRecommendedDriver() != null

    fun driverName(context: Context, recommendation: Recommendation): String =
        context.getString(recommendation.driverNameId)

    fun apply(
        context: Context,
        game: Game,
        recommendation: Recommendation
    ): ApplyResult {
        if (NativeConfig.isPerGameConfigLoaded()) {
            return ApplyResult(applied = false, driverOutcome = DriverOutcome.BUSY)
        }

        val recommendedDriver = findRecommendedDriver()
        var driverChanged = false
        var pipelineBehaviorChanged = false
        var driverOutcome = DriverOutcome.NOT_INSTALLED
        var applied = false

        try {
            SettingsFile.loadCustomConfig(game)

            val integerSettingsToApply = LinkedHashMap(recommendation.integerSettings)
            val booleanSettingsToApply = LinkedHashMap(recommendation.booleanSettings)
            if (recommendedDriver != null) {
                integerSettingsToApply.putAll(recommendation.driverIntegerSettings)
                booleanSettingsToApply.putAll(recommendation.driverBooleanSettings)
            }

            val targetDynamicState = integerSettingsToApply[IntSetting.RENDERER_DYNA_STATE]
            if (targetDynamicState != null) {
                val needsGlobal = NativeConfig.usingGlobal(IntSetting.RENDERER_DYNA_STATE.key)
                pipelineBehaviorChanged =
                    IntSetting.RENDERER_DYNA_STATE.getInt(needsGlobal) != targetDynamicState
            }

            val targetVertexInputDynamicState =
                booleanSettingsToApply[BooleanSetting.RENDERER_VERTEX_INPUT_DYNAMIC_STATE]
            if (targetVertexInputDynamicState != null) {
                val needsGlobal = NativeConfig.usingGlobal(
                    BooleanSetting.RENDERER_VERTEX_INPUT_DYNAMIC_STATE.key
                )
                pipelineBehaviorChanged = pipelineBehaviorChanged ||
                    BooleanSetting.RENDERER_VERTEX_INPUT_DYNAMIC_STATE.getBoolean(needsGlobal) !=
                    targetVertexInputDynamicState
            }

            integerSettingsToApply.forEach { (setting, value) ->
                setting.setInt(value)
            }
            booleanSettingsToApply.forEach { (setting, value) ->
                setting.setBoolean(value)
            }

            if (recommendedDriver != null) {
                val currentPath = StringSetting.DRIVER_PATH.getString()
                val recommendedPath = recommendedDriver.first
                driverChanged = currentPath != recommendedPath
                StringSetting.DRIVER_PATH.setString(recommendedPath)
                driverOutcome = if (driverChanged) {
                    DriverOutcome.SELECTED
                } else {
                    DriverOutcome.ALREADY_SELECTED
                }
            }

            NativeConfig.savePerGameConfig()
            applied = true
        } catch (exception: Exception) {
            Log.error(
                "[DeviceProfileManager] Failed to apply profile for ${game.programIdHex}: " +
                    exception.message
            )
            driverOutcome = DriverOutcome.FAILED
        } finally {
            if (NativeConfig.isPerGameConfigLoaded()) {
                NativeConfig.unloadPerGameConfig()
            }
            runCatching { NativeConfig.reloadGlobalConfig() }
        }

        if (applied && (driverChanged || pipelineBehaviorChanged)) {
            wipeShaderCache(context, game)
        }

        return ApplyResult(applied, driverOutcome)
    }

    private fun recommendationFor(game: Game): Recommendation =
        if (game.programIdHex.uppercase(Locale.ROOT) == TOTK_TITLE_ID) {
            Recommendation(
                profileNameId = R.string.device_profile_poco_f5_totk,
                changesId = R.string.device_profile_changes_poco_f5_totk,
                driverNameId = R.string.device_profile_driver_t30,
                integerSettings = linkedMapOf(
                    IntSetting.RENDERER_BACKEND to 1, // Vulkan
                    IntSetting.CPU_BACKEND to 1, // NCE
                    IntSetting.CPU_ACCURACY to 0, // Auto
                    IntSetting.RENDERER_RESOLUTION to 2, // 0.75x
                    IntSetting.RENDERER_SCALING_FILTER to 6, // FSR
                    IntSetting.FSR_SHARPENING_SLIDER to 25,
                    IntSetting.RENDERER_ANTI_ALIASING to 0, // None
                    IntSetting.RENDERER_VSYNC to 2, // FIFO
                    IntSetting.RENDERER_ACCURACY to 0, // Low
                    IntSetting.DMA_ACCURACY to 0, // Default
                    IntSetting.GPU_FENCE_BEHAVIOR to 0, // Default
                    IntSetting.RENDERER_VRAM_USAGE_MODE to 0, // Conservative
                    IntSetting.RENDERER_ASTC_DECODE_METHOD to 1, // GPU
                    IntSetting.RENDERER_NVDEC_EMULATION to 2, // GPU
                    IntSetting.ANDROID_PIPELINE_WORKERS to POCO_F5_TOTK_PIPELINE_WORKERS,
                    IntSetting.RENDERER_DYNA_STATE to 0 // Safe fallback when T30 is unavailable
                ),
                booleanSettings = baseBooleanSettings() + mapOf(
                    BooleanSetting.RENDERER_FRAME_GEN to false,
                    BooleanSetting.RENDERER_VERTEX_INPUT_DYNAMIC_STATE to false
                ),
                driverIntegerSettings = linkedMapOf(
                    IntSetting.RENDERER_DYNA_STATE to POCO_F5_TOTK_EDS_LEVEL
                ),
                driverBooleanSettings = linkedMapOf(
                    BooleanSetting.RENDERER_VERTEX_INPUT_DYNAMIC_STATE to true
                )
            )
        } else {
            Recommendation(
                profileNameId = R.string.device_profile_poco_f5_balanced,
                changesId = R.string.device_profile_changes_poco_f5_balanced,
                driverNameId = R.string.device_profile_driver_t30,
                integerSettings = linkedMapOf(
                    IntSetting.RENDERER_BACKEND to 1, // Vulkan
                    IntSetting.CPU_BACKEND to 1, // NCE
                    IntSetting.CPU_ACCURACY to 0, // Auto
                    IntSetting.RENDERER_RESOLUTION to 3, // 1x
                    IntSetting.RENDERER_ANTI_ALIASING to 0, // None
                    IntSetting.RENDERER_VSYNC to 2, // FIFO
                    IntSetting.RENDERER_ACCURACY to 0, // Low
                    IntSetting.DMA_ACCURACY to 0, // Default
                    IntSetting.GPU_FENCE_BEHAVIOR to 0, // Default
                    IntSetting.RENDERER_VRAM_USAGE_MODE to 0, // Conservative
                    IntSetting.RENDERER_ASTC_DECODE_METHOD to 1, // GPU
                    IntSetting.RENDERER_NVDEC_EMULATION to 2 // GPU
                ),
                booleanSettings = baseBooleanSettings()
            )
        }

    private fun baseBooleanSettings(): Map<BooleanSetting, Boolean> = linkedMapOf(
        BooleanSetting.FASTMEM to true,
        BooleanSetting.FASTMEM_EXCLUSIVES to true,
        BooleanSetting.USE_DOCKED_MODE to false,
        BooleanSetting.RENDERER_USE_DISK_SHADER_CACHE to true,
        BooleanSetting.RENDERER_USE_VULKAN_DRIVER_PIPELINE_CACHE to true,
        BooleanSetting.RENDERER_FORCE_MAX_CLOCK to true,
        BooleanSetting.RENDERER_ASYNCHRONOUS_GPU_EMULATION to true,
        BooleanSetting.RENDERER_ASYNC_PRESENTATION to true,
        BooleanSetting.RENDERER_ASYNCHRONOUS_SHADERS to false,
        BooleanSetting.RENDERER_REACTIVE_FLUSHING to false,
        BooleanSetting.USE_OPTIMIZED_VERTEX_BUFFERS to true,
        BooleanSetting.RENDERER_PATCH_OLD_QCOM_DRIVERS to false
    )

    private fun findRecommendedDriver(): Pair<String, GpuDriverMetadata>? =
        GpuDriverHelper.getDrivers().firstOrNull { (path, metadata) ->
            val identity = buildString {
                append(path)
                append(' ')
                append(metadata.name.orEmpty())
                append(' ')
                append(metadata.version.orEmpty())
                append(' ')
                append(metadata.author.orEmpty())
            }.lowercase(Locale.ROOT)

            identity.contains("t30") && identity.contains("purple")
        }

    private fun wipeShaderCache(context: Context, game: Game) {
        val externalFilesDir = context.getExternalFilesDir(null) ?: return
        File(
            externalFilesDir,
            "shader/${game.settingsName.lowercase(Locale.ROOT)}"
        ).deleteRecursively()
    }

    private fun isPocoF5(): Boolean {
        val model = Build.MODEL.uppercase(Locale.ROOT)
        val device = Build.DEVICE.lowercase(Locale.ROOT)
        return model in pocoF5Models || device == "marble"
    }

    private fun deviceName(isPocoF5: Boolean): String {
        val model = Build.MODEL.ifBlank { Build.DEVICE }
        if (isPocoF5) {
            return when (model.uppercase(Locale.ROOT)) {
                "23049RAD8C" -> "Redmi Note 12 Turbo ($model)"
                else -> "POCO F5 ($model)"
            }
        }

        val manufacturer = Build.MANUFACTURER
            .ifBlank { "Android" }
            .replaceFirstChar { if (it.isLowerCase()) it.titlecase(Locale.ROOT) else it.toString() }
        return if (model.startsWith(manufacturer, ignoreCase = true)) {
            model
        } else {
            "$manufacturer $model"
        }
    }

    private fun socName(): String {
        val soc = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            Build.SOC_MODEL
        } else {
            Build.HARDWARE
        }
        return soc.ifBlank { Build.HARDWARE.ifBlank { "Unknown" } }
    }
}
