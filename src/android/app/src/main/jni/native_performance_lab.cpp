// SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
// SPDX-License-Identifier: GPL-3.0-or-later

#include <chrono>
#include <jni.h>

#include "common/adaptive_frame_pacing.h"
#include "common/adpf.h"
#include "common/smart_adaptive_frame_skip.h"
#include "native.h"

extern "C" {

jdoubleArray Java_org_yuzu_yuzu_1emu_utils_PerformanceLabNative_getRecentFrameTimeStats(
    JNIEnv* env, jobject /*instance*/) {
    constexpr jsize StatCount = 33;
    jdoubleArray j_stats = env->NewDoubleArray(StatCount);
    if (j_stats == nullptr || !EmulationSession::GetInstance().IsRunning()) {
        return j_stats;
    }

    const auto stats =
        EmulationSession::GetInstance().System().GetPerfStats().GetRecentFrameTimeStats();
    const auto adpf = Common::ADPF::GetTelemetry();
    const auto pacing = Common::AdaptiveFramePacing::GetTelemetry();
    const auto frame_skip = Common::SmartAdaptiveFrameSkip::GetTelemetry();
    const double target_ms =
        std::chrono::duration<double, std::milli>(adpf.target_work_duration).count();
    const double actual_ms =
        std::chrono::duration<double, std::milli>(adpf.last_actual_work_duration).count();

    const double values[StatCount] = {
        stats.mean_ms,
        stats.median_ms,
        stats.p95_ms,
        stats.p99_ms,
        stats.max_ms,
        static_cast<double>(stats.sample_count),
        static_cast<double>(stats.total_system_frames),
        adpf.available ? 1.0 : 0.0,
        adpf.render_active ? 1.0 : 0.0,
        adpf.background_active ? 1.0 : 0.0,
        static_cast<double>(adpf.render_thread_count),
        static_cast<double>(adpf.background_thread_count),
        static_cast<double>(adpf.successful_reports),
        target_ms,
        actual_ms,
        pacing.active ? 1.0 : 0.0,
        pacing.target_fps,
        pacing.producer_fps,
        static_cast<double>(pacing.paced_frames),
        static_cast<double>(pacing.resyncs),
        pacing.last_delay_ms,
        frame_skip.enabled ? 1.0 : 0.0,
        frame_skip.eligible ? 1.0 : 0.0,
        frame_skip.pressure_active ? 1.0 : 0.0,
        static_cast<double>(frame_skip.rendered_frames),
        static_cast<double>(frame_skip.skipped_frames),
        static_cast<double>(frame_skip.pressure_score),
        static_cast<double>(frame_skip.cooldown_frames),
        frame_skip.target_fps,
        frame_skip.estimated_composite_ms,
        static_cast<double>(frame_skip.gpu_backlog),
        static_cast<double>(frame_skip.presentation_backlog),
        static_cast<double>(frame_skip.presentation_capacity),
    };
    env->SetDoubleArrayRegion(j_stats, 0, StatCount, values);
    return j_stats;
}

} // extern "C"
