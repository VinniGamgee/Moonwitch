// SPDX-FileCopyrightText: Copyright 2026 Eden Emulator Project
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#include <chrono>
#include <cstddef>
#include <cstdint>

namespace Common::ADPF {

enum class Session {
    Render,
    Background,
};

struct Telemetry {
    bool available{};
    bool render_active{};
    bool background_active{};
    std::size_t render_thread_count{};
    std::size_t background_thread_count{};
    std::uint64_t successful_reports{};
    std::chrono::nanoseconds target_work_duration{};
    std::chrono::nanoseconds last_actual_work_duration{};
};

bool IsSessionSupported(Session session);

bool AddCurrentThread(Session session);
void RemoveCurrentThread();

void SetTargetWorkDuration(std::chrono::nanoseconds target);

// Report the measured work duration of a completed emulation/system frame. This is the preferred
// path for ADPF because the caller can exclude sleeps and frame-limiter waits from the sample.
void ReportActualWorkDuration(std::chrono::nanoseconds actual);

// Legacy/convenience path for callers that only have frame boundaries available.
void ReportFrameInterval();

Telemetry GetTelemetry();

void Shutdown();

} // namespace Common::ADPF
