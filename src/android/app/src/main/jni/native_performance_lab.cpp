// SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
// SPDX-License-Identifier: GPL-3.0-or-later

#include <jni.h>

#include "native.h"

extern "C" {

jdoubleArray Java_org_yuzu_yuzu_1emu_utils_PerformanceLabNative_getRecentFrameTimeStats(
    JNIEnv* env, jobject /*instance*/) {
    constexpr jsize StatCount = 7;
    jdoubleArray j_stats = env->NewDoubleArray(StatCount);
    if (j_stats == nullptr || !EmulationSession::GetInstance().IsRunning()) {
        return j_stats;
    }

    const auto stats =
        EmulationSession::GetInstance().System().GetPerfStats().GetRecentFrameTimeStats();
    const double values[StatCount] = {
        stats.mean_ms,
        stats.median_ms,
        stats.p95_ms,
        stats.p99_ms,
        stats.max_ms,
        static_cast<double>(stats.sample_count),
        static_cast<double>(stats.total_system_frames),
    };
    env->SetDoubleArrayRegion(j_stats, 0, StatCount, values);
    return j_stats;
}

} // extern "C"
