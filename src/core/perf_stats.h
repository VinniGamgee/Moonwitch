// SPDX-FileCopyrightText: 2017 Citra Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

#pragma once

#include <array>
#include <atomic>
#include <chrono>
#include <cstddef>
#include <mutex>
#include "common/common_types.h"

namespace Core {

struct PerfStatsResults {
    /// System FPS (LCD VBlanks) in Hz
    double system_fps;
    /// Average game FPS (GPU frame renders) in Hz
    double average_game_fps;
    /// Walltime per system frame, in seconds, excluding any waits
    double frametime;
    /// Ratio of walltime / emulated time elapsed
    double emulation_speed;
};

/// Rolling frame-time statistics used by Moonwitch's Performance Lab.
/// Values are measured from individual system frames and reported in milliseconds.
struct RecentFrameTimeStats {
    double mean_ms{};
    double median_ms{};
    double p95_ms{};
    double p99_ms{};
    double max_ms{};
    u32 sample_count{};
    u64 total_system_frames{};
};

/**
 * Class to manage and query performance/timing statistics. All public functions of this class are
 * thread-safe unless stated otherwise.
 */
class PerfStats {
public:
    explicit PerfStats(u64 title_id_);
    ~PerfStats();

    using Clock = std::chrono::steady_clock;

    void BeginSystemFrame();
    void EndSystemFrame();
    void EndGameFrame();

    PerfStatsResults GetAndResetStats(std::chrono::microseconds current_system_time_us);

    /**
     * Returns the arithmetic mean of all frametime values stored in the performance history.
     */
    double GetMeanFrametime() const;

    /**
     * Returns rolling statistics from the most recent individual system-frame measurements.
     * This does not reset the normal frontend performance counters.
     */
    RecentFrameTimeStats GetRecentFrameTimeStats() const;

    /**
     * Gets the ratio between walltime and the emulated time of the previous system frame. This is
     * useful for scaling inputs or outputs moving between the two time domains.
     */
    double GetLastFrameTimeScale() const;

private:
    static constexpr std::size_t RecentFrameWindow = 600;

    mutable std::mutex object_mutex;

    /// Title ID for the game that is running. 0 if there is no game running yet
    u64 title_id{0};
    /// Current index for writing to the perf_history array
    std::size_t current_index{0};
    /// Stores an hour of historical frametime data useful for processing and tracking performance
    /// regressions with code changes.
    std::array<double, 216000> perf_history{};

    /// Rolling individual-frame history used for short, responsive Performance Lab statistics.
    std::array<double, RecentFrameWindow> recent_frame_history{};
    std::size_t recent_frame_index{0};
    std::size_t recent_frame_count{0};
    u64 lifetime_system_frames{0};

    /// Point when the cumulative counters were reset
    Clock::time_point reset_point = Clock::now();
    /// System time when the cumulative counters were reset
    std::chrono::microseconds reset_point_system_us{0};

    /// Cumulative duration (excluding v-sync/frame-limiting) of frames since last reset
    Clock::duration accumulated_frametime = Clock::duration::zero();
    /// Cumulative number of system frames (LCD VBlanks) presented since last reset
    u32 system_frames = 0;
    /// Cumulative number of game frames (GSP frame submissions) since last reset
    std::atomic<u32> game_frames = 0;

    /// Point when the previous system frame ended
    Clock::time_point previous_frame_end = reset_point;
    /// Point when the current system frame began
    Clock::time_point frame_begin = reset_point;
    /// Total visible duration (including frame-limiting, etc.) of the previous system frame
    Clock::duration previous_frame_length = Clock::duration::zero();
    /// Previously computed fps
    double previous_fps = 0;
};

class SpeedLimiter {
public:
    using Clock = std::chrono::steady_clock;

    void DoSpeedLimiting(std::chrono::microseconds current_system_time_us);

private:
    /// Emulated system time (in microseconds) at the last limiter invocation
    std::chrono::microseconds previous_system_time_us{0};
    /// Walltime at the last limiter invocation
    Clock::time_point previous_walltime = Clock::now();

    /// Accumulated difference between walltime and emulated time
    std::chrono::microseconds speed_limiting_delta_err{0};
};

} // namespace Core
