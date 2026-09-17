// SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
// SPDX-License-Identifier: GPL-3.0-or-later

// SPDX-FileCopyrightText: Copyright yuzu/Citra Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

import com.android.build.gradle.api.ApplicationVariant
import kotlin.collections.setOf
import org.jlleitschuh.gradle.ktlint.reporter.ReporterType
import com.github.triplet.gradle.androidpublisher.ReleaseStatus
import org.gradle.api.tasks.Copy

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("kotlin-parcelize")
    kotlin("plugin.serialization") version "1.9.20"
    id("androidx.navigation.safeargs.kotlin")
    id("org.jlleitschuh.gradle.ktlint") version "11.4.0"
    id("com.github.triplet.play") version "3.8.6"
    id("idea")
}

val autoVersion = (((System.currentTimeMillis() / 1000) - 1451606400) / 10).toInt()

val moonwitchDir = project(":Moonwitch").projectDir

@Suppress("UnstableApiUsage")
android {
    namespace = "org.yuzu.yuzu_emu"

    compileSdkVersion = "android-36"
    ndkVersion = "28.2.13676358"

    val isNightly =
        providers.gradleProperty("nightly").orNull?.toBooleanStrictOrNull() ?: false

    buildFeatures {
        viewBinding = true
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    packaging {
        jniLibs.useLegacyPackaging = true
    }

    androidResources {
        generateLocaleConfig = true
    }

    defaultConfig {
        applicationId = "com.moonwitch.emulator"
        minSdk = 24
        targetSdk = 36
        versionName = getGitVersion()
        versionCode = autoVersion

        externalNativeBuild {
            cmake {
                val extraCMakeArgs =
                    (project.findProperty("YUZU_ANDROID_ARGS") as String?)?.split("\\s+".toRegex())
                        ?: emptyList()

                arguments.addAll(
                    listOf(
                        "-DENABLE_QT=0",
                        "-DENABLE_WEB_SERVICE=1",
                        "-DANDROID_ARM_NEON=true",
                        "-DYUZU_USE_CPM=ON",
                        "-DCPMUTIL_FORCE_BUNDLED=ON",
                        "-DYUZU_USE_BUNDLED_FFMPEG=ON",
                        "-DCMAKE_EXPORT_COMPILE_COMMANDS=ON",
                        "-DBUILD_TESTING=OFF",
                        "-DYUZU_TESTS=OFF",
                        "-DDYNARMIC_TESTS=OFF",
                        *extraCMakeArgs.toTypedArray()
                    )
                )

                if (isNightly) {
                    arguments.addAll(
                        listOf(
                            "-DENABLE_UPDATE_CHECKER=ON",
                            "-DNIGHTLY_BUILD=ON",
                        )
                    )
                }

                abiFilters("arm64-v8a")
            }
        }
    }

    val keystoreFile = System.getenv("ANDROID_KEYSTORE_FILE")
    signingConfigs {
        if (keystoreFile != null) {
            create("release") {
                storeFile = file(keystoreFile)
                storePassword = System.getenv("ANDROID_KEYSTORE_PASS")
                keyAlias = System.getenv("ANDROID_KEY_ALIAS")
                keyPassword = System.getenv("ANDROID_KEYSTORE_PASS")
            }
        }
        create("default") {
            storeFile = file("$projectDir/debug.keystore")
            storePassword = "android"
            keyAlias = "androiddebugkey"
            keyPassword = "android"
        }
    }

    buildTypes {
        release {
            signingConfig = if (keystoreFile != null) {
                signingConfigs.getByName("release")
            } else {
                signingConfigs.getByName("default")
            }

            if (isNightly) {
                applicationIdSuffix = ".nightly"
                manifestPlaceholders += mapOf("appNameSuffix" to " Nightly")
            } else {
                manifestPlaceholders += mapOf("appNameSuffix" to "")
            }

            isMinifyEnabled = true
            isDebuggable = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }

        register("relWithDebInfo") {
            isDefault = true
            signingConfig = signingConfigs.getByName("default")
            isDebuggable = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
            manifestPlaceholders += mapOf("appNameSuffix" to " Debug Release")
            versionNameSuffix = "-relWithDebInfo"
            applicationIdSuffix = ".relWithDebInfo"
            isJniDebuggable = true
        }

        debug {
            signingConfig = signingConfigs.getByName("default")
            isDebuggable = true
            isJniDebuggable = true
            versionNameSuffix = "-debug"
            applicationIdSuffix = ".debug"
            manifestPlaceholders += mapOf("appNameSuffix" to " Debug")
        }
    }

    flavorDimensions.add("version")
    productFlavors {
        create("mainline") {
            dimension = "version"
            isDefault = true
            minSdk = 33
            manifestPlaceholders += mapOf("appNameBase" to "Moonwitch")
            resValue("string", "app_name_suffixed", "Moonwitch")
            ndk { abiFilters += listOf("arm64-v8a") }
        }

        create("genshinSpoof") {
            dimension = "version"
            minSdk = 35
            manifestPlaceholders += mapOf("appNameBase" to "Moonwitch Optimized")
            resValue("string", "app_name_suffixed", "Moonwitch Optimized")
            applicationId = "com.miHoYo.Yuanshen"
            externalNativeBuild { cmake { arguments.add("-DGENSHIN_SPOOF=ON") } }
            ndk { abiFilters += listOf("arm64-v8a") }
        }

        create("legacy") {
            dimension = "version"
            minSdk = 29
            manifestPlaceholders += mapOf("appNameBase" to "Moonwitch Legacy")
            resValue("string", "app_name_suffixed", "Moonwitch Legacy")
            applicationId = "com.moonwitch.emulator.legacy"
            externalNativeBuild { cmake { arguments.add("-DYUZU_LEGACY=ON") } }
            sourceSets {
                getByName("legacy") { res.srcDirs("src/main/legacy") }
            }
            ndk { abiFilters += listOf("arm64-v8a") }
        }

        create("chromeOS") {
            dimension = "version"
            manifestPlaceholders += mapOf("appNameBase" to "Moonwitch ChromeOS")
            resValue("string", "app_name_suffixed", "Moonwitch ChromeOS")
            ndk { abiFilters += listOf("x86_64") }
            externalNativeBuild { cmake { abiFilters("x86_64") } }
        }
    }

    externalNativeBuild {
        cmake {
            version = "3.31.6"
            path = file("${moonwitchDir}/CMakeLists.txt")
        }
    }

    productFlavors.all {
        val currentName = manifestPlaceholders["appNameBase"] as? String ?: "Moonwitch"
        val suffix = if (isNightly) " Nightly" else ""
        resValue("string", "app_name_suffixed", "$currentName$suffix")
        resValue("string", "app_name", "Moonwitch$suffix")
    }
}

idea {
    module {
        excludeDirs.add(file("${moonwitchDir}/build"))
        excludeDirs.add(file("${moonwitchDir}/.cache"))
    }
}

tasks.register<Delete>("ktlintReset", fun Delete.() {
    delete(File(layout.buildDirectory.toString() + File.separator + "intermediates/ktLint"))
})

val showFormatHelp = {
    logger.lifecycle(
        "If this check fails, please try running \"gradlew ktlintFormat\" for automatic " +
                "codestyle fixes"
    )
}
tasks.getByPath("ktlintKotlinScriptCheck").doFirst { showFormatHelp.invoke() }
tasks.getByPath("ktlintMainSourceSetCheck").doFirst { showFormatHelp.invoke() }
tasks.getByPath("loadKtlintReporters").dependsOn("ktlintReset")

ktlint {
    version.set("0.47.1")
    android.set(true)
    ignoreFailures.set(false)
    disabledRules.set(setOf("no-wildcard-imports", "package-name", "import-ordering"))
    reporters { reporter(ReporterType.CHECKSTYLE) }
}

play {
    val keyPath = System.getenv("SERVICE_ACCOUNT_KEY_PATH")
    if (keyPath != null) serviceAccountCredentials.set(File(keyPath))
    track.set(System.getenv("STORE_TRACK") ?: "internal")
    releaseStatus.set(ReleaseStatus.COMPLETED)
}

dependencies {
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("androidx.recyclerview:recyclerview:1.4.0")
    implementation("androidx.constraintlayout:constraintlayout:2.2.1")
    implementation("androidx.fragment:fragment-ktx:1.8.6")
    implementation("androidx.documentfile:documentfile:1.0.1")
    implementation("com.google.android.material:material:1.12.0")
    implementation("androidx.preference:preference-ktx:1.2.1")
    implementation("androidx.lifecycle:lifecycle-viewmodel-ktx:2.8.7")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("io.coil-kt:coil:2.2.2")
    implementation("androidx.core:core-splashscreen:1.0.1")
    implementation("com.fasterxml.jackson.module:jackson-module-kotlin:2.17.2")
    implementation("androidx.window:window:1.3.0")
    implementation("androidx.swiperefreshlayout:swiperefreshlayout:1.1.0")
    implementation("org.commonmark:commonmark:0.22.0")
    implementation("androidx.navigation:navigation-fragment-ktx:2.8.9")
    implementation("androidx.navigation:navigation-ui-ktx:2.8.9")
    implementation("info.debatty:java-string-similarity:2.0.0")
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.6.3")
    implementation("androidx.compose.ui:ui-graphics-android:1.7.8")
    implementation("androidx.compose.ui:ui-text-android:1.7.8")
    implementation("net.swiftzer.semver:semver:2.0.0")
}

fun runGitCommand(command: List<String>): String {
    return try {
        ProcessBuilder(command)
            .directory(project.rootDir)
            .redirectOutput(ProcessBuilder.Redirect.PIPE)
            .redirectError(ProcessBuilder.Redirect.PIPE)
            .start()
            .inputStream.bufferedReader()
            .use { it.readText() }
            .trim()
    } catch (e: Exception) {
        logger.error("Cannot find git")
        ""
    }
}

fun getGitVersion(): String {
    val gitVersion = runGitCommand(listOf("git", "describe", "--always", "--long"))
        .replace(Regex("(-0)?-[^-]+$"), "")
    val versionName = if (System.getenv("GITHUB_ACTIONS") != null) {
        System.getenv("GIT_TAG_NAME") ?: gitVersion
    } else {
        gitVersion
    }
    return versionName.ifEmpty { "0.0" }
}

afterEvaluate {
    val artifactsDir = layout.projectDirectory.dir("${moonwitchDir}/artifacts")
    val outputsDir = layout.buildDirectory.dir("outputs").get()

    android.applicationVariants.forEach { variant ->
        val variantName = variant.name
        val variantTask = variantName.replaceFirstChar { it.uppercaseChar() }
        val flavor = variant.flavorName
        val type = variant.buildType.name
        val baseName = "app-$flavor-$type"
        val apkFile = outputsDir.file("apk/$flavor/$type/$baseName.apk")
        val aabFile = outputsDir.file("bundle/$variantName/$baseName.aab")
        val taskName = "copy${variantTask}Outputs"

        tasks.register<Copy>(taskName) {
            group = "publishing"
            description = "Copy APK and AAB for $variantName to $artifactsDir"
            from(apkFile)
            from(aabFile)
            into(artifactsDir)
            dependsOn("assemble${variantTask}")
            dependsOn("bundle${variantTask}")
        }
    }
}
