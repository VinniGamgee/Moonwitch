// SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
// SPDX-License-Identifier: GPL-3.0-or-later

#define VK_USE_PLATFORM_ANDROID_KHR 1

#include <android/api-level.h>
#include <android/native_window.h>
#include <android/native_window_jni.h>
#include <android/log.h>
#include <dlfcn.h>
#include <jni.h>
#include <pthread.h>
#include <stdint.h>
#include <vulkan/vulkan.h>

namespace {
constexpr const char* TAG = "MoonwitchKenjiBridge";
pthread_t g_rendering_thread{};
bool g_initial_orientation_flipped = true;

using SetBuffersTransformFn = int (*)(ANativeWindow*, int32_t);

int64_t CreateAndroidSurface(int64_t native_window, int64_t instance) {
    if (native_window <= 0 || instance == 0) {
        return 0;
    }

    const auto vk_instance = reinterpret_cast<VkInstance>(instance);
    const auto create_android_surface = reinterpret_cast<PFN_vkCreateAndroidSurfaceKHR>(
        vkGetInstanceProcAddr(vk_instance, "vkCreateAndroidSurfaceKHR"));
    if (create_android_surface == nullptr) {
        __android_log_print(ANDROID_LOG_ERROR, TAG, "vkCreateAndroidSurfaceKHR is unavailable");
        return 0;
    }

    VkAndroidSurfaceCreateInfoKHR info{};
    info.sType = VK_STRUCTURE_TYPE_ANDROID_SURFACE_CREATE_INFO_KHR;
    info.window = reinterpret_cast<ANativeWindow*>(native_window);

    VkSurfaceKHR surface = VK_NULL_HANDLE;
    const VkResult result = create_android_surface(vk_instance, &info, nullptr, &surface);
    if (result != VK_SUCCESS) {
        __android_log_print(ANDROID_LOG_ERROR, TAG, "vkCreateAndroidSurfaceKHR failed: %d", result);
        return 0;
    }
    return reinterpret_cast<int64_t>(surface);
}

void ApplySurfaceTransform(ANativeWindow* window, int transform) {
    if (window == nullptr || android_get_device_api_level() < 26) {
        return;
    }

    void* libandroid = dlopen("libandroid.so", RTLD_NOW | RTLD_LOCAL);
    if (libandroid == nullptr) {
        return;
    }
    const auto set_transform = reinterpret_cast<SetBuffersTransformFn>(
        dlsym(libandroid, "ANativeWindow_setBuffersTransform"));
    if (set_transform == nullptr) {
        dlclose(libandroid);
        return;
    }

    // Kenji passes VkSurfaceTransformFlagBitsKHR shifted left by one.
    transform >>= 1;
    int32_t native_transform = ANATIVEWINDOW_TRANSFORM_IDENTITY;
    switch (transform) {
    case VK_SURFACE_TRANSFORM_IDENTITY_BIT_KHR:
        native_transform = ANATIVEWINDOW_TRANSFORM_IDENTITY;
        break;
    case VK_SURFACE_TRANSFORM_ROTATE_90_BIT_KHR:
        native_transform = ANATIVEWINDOW_TRANSFORM_ROTATE_90;
        break;
    case VK_SURFACE_TRANSFORM_ROTATE_180_BIT_KHR:
        native_transform = g_initial_orientation_flipped
            ? ANATIVEWINDOW_TRANSFORM_IDENTITY
            : ANATIVEWINDOW_TRANSFORM_ROTATE_180;
        break;
    case VK_SURFACE_TRANSFORM_ROTATE_270_BIT_KHR:
        native_transform = ANATIVEWINDOW_TRANSFORM_ROTATE_270;
        break;
    case VK_SURFACE_TRANSFORM_HORIZONTAL_MIRROR_BIT_KHR:
        native_transform = ANATIVEWINDOW_TRANSFORM_MIRROR_HORIZONTAL;
        break;
    case VK_SURFACE_TRANSFORM_HORIZONTAL_MIRROR_ROTATE_90_BIT_KHR:
        native_transform = ANATIVEWINDOW_TRANSFORM_MIRROR_HORIZONTAL |
                           ANATIVEWINDOW_TRANSFORM_ROTATE_90;
        break;
    case VK_SURFACE_TRANSFORM_HORIZONTAL_MIRROR_ROTATE_180_BIT_KHR:
        native_transform = ANATIVEWINDOW_TRANSFORM_MIRROR_VERTICAL;
        break;
    case VK_SURFACE_TRANSFORM_HORIZONTAL_MIRROR_ROTATE_270_BIT_KHR:
        native_transform = ANATIVEWINDOW_TRANSFORM_MIRROR_VERTICAL |
                           ANATIVEWINDOW_TRANSFORM_ROTATE_90;
        break;
    default:
        native_transform = ANATIVEWINDOW_TRANSFORM_IDENTITY;
        break;
    }

    set_transform(window, native_transform);
    dlclose(libandroid);
}
} // namespace

extern "C" JNIEXPORT jlong JNICALL
Java_org_kenjinx_android_NativeHelpers_getNativeWindow(JNIEnv* env, jobject, jobject surface) {
    if (surface == nullptr) {
        return -1;
    }
    ANativeWindow* window = ANativeWindow_fromSurface(env, surface);
    return window == nullptr ? -1 : reinterpret_cast<jlong>(window);
}

extern "C" JNIEXPORT void JNICALL
Java_org_kenjinx_android_NativeHelpers_releaseNativeWindow(JNIEnv*, jobject, jlong window) {
    if (window > 0) {
        ANativeWindow_release(reinterpret_cast<ANativeWindow*>(window));
    }
}

extern "C" JNIEXPORT jlong JNICALL
Java_org_kenjinx_android_NativeHelpers_getCreateSurfacePtr(JNIEnv*, jobject) {
    return reinterpret_cast<jlong>(&CreateAndroidSurface);
}

extern "C" JNIEXPORT jstring JNICALL
Java_org_kenjinx_android_NativeHelpers_getStringJava(JNIEnv* env, jobject, jlong ptr) {
    if (ptr == 0) {
        return nullptr;
    }
    return env->NewStringUTF(reinterpret_cast<const char*>(ptr));
}

extern "C" JNIEXPORT void JNICALL
Java_org_kenjinx_android_NativeHelpers_setIsInitialOrientationFlipped(
    JNIEnv*, jobject, jboolean flipped) {
    g_initial_orientation_flipped = flipped == JNI_TRUE;
}

// These symbols are imported directly by LibKenjinx NativeAOT.
extern "C" void setRenderingThread() {
    g_rendering_thread = pthread_self();
}

extern "C" void debug_break(int) {
    // Matches Kenji's release behavior: diagnostic hook only.
}

extern "C" void setCurrentTransform(int64_t native_window, int transform) {
    ApplySurfaceTransform(reinterpret_cast<ANativeWindow*>(native_window), transform);
}
