// SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstddef>
#include <cstdint>

namespace Common::SmartAdaptiveFrameSkip {

struct Telemetry {
    bool enabled{};
    bool eligible{};
    bool pressure_active{};
    std::uint64_t rendered_frames{};
    std::uint64_t skipped_frames{};
    std::uint32_t pressure_score{};
    std::uint32_t cooldown_frames{};
    double target_fps{};
    double estimated_composite_ms{};
    std::uint64_t gpu_backlog{};
    std::uint64_t presentation_backlog{};
    std::uint64_t presentation_capacity{};
};

struct Signals {
    bool enabled{};
    bool eligible{};
    bool force_render{};
    bool pacing_active{};
    double target_fps{};
    std::uint64_t pacing_resyncs{};
    std::uint64_t gpu_backlog{};
    std::size_t presentation_backlog{};
    std::size_t presentation_capacity{};
};

namespace Detail {

inline std::atomic_bool g_enabled{false};
inline std::atomic_bool g_eligible{false};
inline std::atomic_bool g_pressure_active{false};
inline std::atomic<std::uint64_t> g_rendered_frames{0};
inline std::atomic<std::uint64_t> g_skipped_frames{0};
inline std::atomic<std::uint32_t> g_pressure_score{0};
inline std::atomic<std::uint32_t> g_cooldown_frames{0};
inline std::atomic<std::int64_t> g_target_millifps{0};
inline std::atomic<std::int64_t> g_estimated_composite_ns{0};
inline std::atomic<std::uint64_t> g_gpu_backlog{0};
inline std::atomic<std::uint64_t> g_presentation_backlog{0};
inline std::atomic<std::uint64_t> g_presentation_capacity{0};

inline void Publish(const Telemetry& telemetry) {
    g_enabled.store(telemetry.enabled, std::memory_order_relaxed);
    g_eligible.store(telemetry.eligible, std::memory_order_relaxed);
    g_pressure_active.store(telemetry.pressure_active, std::memory_order_relaxed);
    g_rendered_frames.store(telemetry.rendered_frames, std::memory_order_relaxed);
    g_skipped_frames.store(telemetry.skipped_frames, std::memory_order_relaxed);
    g_pressure_score.store(telemetry.pressure_score, std::memory_order_relaxed);
    g_cooldown_frames.store(telemetry.cooldown_frames, std::memory_order_relaxed);
    g_target_millifps.store(
        static_cast<std::int64_t>(std::llround(telemetry.target_fps * 1000.0)),
        std::memory_order_relaxed);
    g_estimated_composite_ns.store(static_cast<std::int64_t>(
                                       std::llround(telemetry.estimated_composite_ms * 1'000'000.0)),
                                   std::memory_order_relaxed);
    g_gpu_backlog.store(telemetry.gpu_backlog, std::memory_order_relaxed);
    g_presentation_backlog.store(telemetry.presentation_backlog, std::memory_order_relaxed);
    g_presentation_capacity.store(telemetry.presentation_capacity, std::memory_order_relaxed);
}

} // namespace Detail

inline Telemetry GetTelemetry() {
    return Telemetry{
        .enabled = Detail::g_enabled.load(std::memory_order_relaxed),
        .eligible = Detail::g_eligible.load(std::memory_order_relaxed),
        .pressure_active = Detail::g_pressure_active.load(std::memory_order_relaxed),
        .rendered_frames = Detail::g_rendered_frames.load(std::memory_order_relaxed),
        .skipped_frames = Detail::g_skipped_frames.load(std::memory_order_relaxed),
        .pressure_score = Detail::g_pressure_score.load(std::memory_order_relaxed),
        .cooldown_frames = Detail::g_cooldown_frames.load(std::memory_order_relaxed),
        .target_fps = static_cast<double>(
                          Detail::g_target_millifps.load(std::memory_order_relaxed)) /
                      1000.0,
        .estimated_composite_ms = static_cast<double>(
                                      Detail::g_estimated_composite_ns.load(
                                          std::memory_order_relaxed)) /
                                  1'000'000.0,
        .gpu_backlog = Detail::g_gpu_backlog.load(std::memory_order_relaxed),
        .presentation_backlog =
            Detail::g_presentation_backlog.load(std::memory_order_relaxed),
        .presentation_capacity =
            Detail::g_presentation_capacity.load(std::memory_order_relaxed),
    };
}

/**
 * Conservative controller that abandons only the final host composition of a guest frame.
 *
 * A skip is allowed only after sustained deadline pressure and evidence that composition is worth
 * avoiding (measured compositor cost or a real GPU/presentation queue backlog). Guest GPU commands,
 * CPU emulation, audio, input, timers and rasterizer maintenance remain outside this controller and
 * must still advance when the caller accepts a skip.
 */
class Controller {
public:
    using Clock = std::chrono::steady_clock;

    Controller() {
        ResetSession();
    }

    ~Controller() {
        Detail::Publish({});
    }

    [[nodiscard]] bool ShouldSkip(const Signals& signals, Clock::time_point now = Clock::now()) {
        latest_signals = signals;
        skip_pending = false;

        if (!signals.enabled) {
            if (session_enabled) {
                ResetSession();
            }
            Publish(false, false);
            return false;
        }

        if (!session_enabled) {
            ResetSession();
            session_enabled = true;
        }

        if (!signals.eligible) {
            ResetPressure(signals.pacing_resyncs);
            Publish(true, false);
            return false;
        }

        const double target_fps = signals.pacing_active ? signals.target_fps : 0.0;
        const double budget_ms = target_fps >= 15.0 ? 1000.0 / target_fps : 0.0;
        const double arrival_ms = ObserveArrival(now);
        const bool pacing_late = ObservePacingResync(signals.pacing_resyncs);

        if (budget_ms <= 0.0) {
            pressure_score = 0;
            pressure_active = false;
            Publish(true, true);
            return false;
        }

        // Surface changes, pauses and loading transitions must not manufacture pressure.
        const double pause_threshold_ms = (std::max)(250.0, budget_ms * 4.0);
        const bool long_pause = arrival_ms > pause_threshold_ms;
        const bool arrival_late = arrival_ms > budget_ms * 1.12 && !long_pause;

        const bool gpu_queue_high = signals.gpu_backlog >= 3;
        const bool present_queue_high =
            signals.presentation_capacity >= 2 &&
            signals.presentation_backlog + 1 >= signals.presentation_capacity;
        const bool queue_pressure = gpu_queue_high || present_queue_high;

        const double minimum_useful_work_ms = std::clamp(budget_ms * 0.10, 1.0, 3.0);
        const bool composition_worth_skipping =
            work_samples >= WarmupSamples && estimated_composite_ms >= minimum_useful_work_ms;
        const bool late = pacing_late || arrival_late;

        if (long_pause) {
            pressure_score = 0;
            pressure_active = false;
        } else if (late) {
            pressure_score = (std::min)(MaxPressure,
                                        pressure_score +
                                            (queue_pressure || composition_worth_skipping ? 2U : 1U));
        } else if (queue_pressure) {
            pressure_score = (std::min)(MaxPressure, pressure_score + 1U);
        } else {
            pressure_score = pressure_score > 1 ? pressure_score - 2 : 0;
        }

        // Separate enter/exit thresholds prevent a single good/bad frame from flipping the system.
        if (pressure_score >= EnterPressure) {
            pressure_active = true;
        } else if (pressure_score <= ExitPressure) {
            pressure_active = false;
        }

        const bool warm = work_samples >= WarmupSamples;
        const bool cooldown_complete = frames_since_skip >= MinRenderedFramesBetweenSkips;
        const bool useful = queue_pressure || composition_worth_skipping;
        const bool should_skip = !signals.force_render && warm && cooldown_complete &&
                                 pressure_active && useful;

        skip_pending = should_skip;
        Publish(true, true);
        return should_skip;
    }

    void OnRendered(Clock::duration elapsed, double pacing_delay_ms, bool sample_cost = true) {
        if (!session_enabled || !latest_signals.eligible) {
            Publish(session_enabled, latest_signals.eligible);
            return;
        }

        ++rendered_frames;
        ++frames_since_skip;
        skip_pending = false;

        double measured_ms =
            std::chrono::duration<double, std::milli>(elapsed).count() - pacing_delay_ms;
        measured_ms = (std::max)(0.0, measured_ms);

        if (sample_cost && measured_ms >= 0.05 && measured_ms <= 250.0) {
            // Cap isolated stalls before the EMA so a shader hitch cannot arm skipping by itself.
            const double target_fps = latest_signals.target_fps;
            const double budget_ms = target_fps >= 15.0 ? 1000.0 / target_fps : 33.333;
            measured_ms = (std::min)(measured_ms, budget_ms * 2.0);
            constexpr double alpha = 0.15;
            estimated_composite_ms = work_samples == 0
                                         ? measured_ms
                                         : estimated_composite_ms +
                                               alpha * (measured_ms - estimated_composite_ms);
            ++work_samples;
        }

        Publish(session_enabled, latest_signals.eligible);
    }

    void OnSkipped() {
        if (!skip_pending) {
            return;
        }
        ++skipped_frames;
        frames_since_skip = 0;
        pressure_score = pressure_score > 3 ? pressure_score - 3 : 0;
        if (pressure_score <= ExitPressure) {
            pressure_active = false;
        }
        skip_pending = false;
        Publish(session_enabled, latest_signals.eligible);
    }

    void Reset() {
        ResetSession();
        Detail::Publish({});
    }

private:
    static constexpr std::uint32_t WarmupSamples = 24;
    static constexpr std::uint32_t MinRenderedFramesBetweenSkips = 5;
    static constexpr std::uint32_t EnterPressure = 6;
    static constexpr std::uint32_t ExitPressure = 2;
    static constexpr std::uint32_t MaxPressure = 10;

    double ObserveArrival(Clock::time_point now) {
        if (last_arrival.time_since_epoch().count() == 0) {
            last_arrival = now;
            return 0.0;
        }
        const double elapsed_ms =
            std::chrono::duration<double, std::milli>(now - last_arrival).count();
        last_arrival = now;
        return elapsed_ms;
    }

    bool ObservePacingResync(std::uint64_t resyncs) {
        if (!has_resync_baseline) {
            last_pacing_resyncs = resyncs;
            has_resync_baseline = true;
            return false;
        }
        const bool advanced = resyncs > last_pacing_resyncs;
        last_pacing_resyncs = resyncs;
        return advanced;
    }

    void ResetPressure(std::uint64_t pacing_resyncs) {
        pressure_score = 0;
        pressure_active = false;
        work_samples = 0;
        estimated_composite_ms = 0.0;
        frames_since_skip = MinRenderedFramesBetweenSkips;
        last_arrival = {};
        last_pacing_resyncs = pacing_resyncs;
        has_resync_baseline = true;
        skip_pending = false;
    }

    void ResetSession() {
        session_enabled = false;
        latest_signals = {};
        rendered_frames = 0;
        skipped_frames = 0;
        work_samples = 0;
        estimated_composite_ms = 0.0;
        has_resync_baseline = false;
        ResetPressure(0);
        has_resync_baseline = false;
    }

    void Publish(bool enabled, bool eligible) const {
        const std::uint32_t cooldown =
            frames_since_skip >= MinRenderedFramesBetweenSkips
                ? 0
                : MinRenderedFramesBetweenSkips - frames_since_skip;
        Detail::Publish(Telemetry{
            .enabled = enabled,
            .eligible = eligible,
            .pressure_active = pressure_active,
            .rendered_frames = rendered_frames,
            .skipped_frames = skipped_frames,
            .pressure_score = pressure_score,
            .cooldown_frames = cooldown,
            .target_fps = latest_signals.pacing_active ? latest_signals.target_fps : 0.0,
            .estimated_composite_ms = estimated_composite_ms,
            .gpu_backlog = latest_signals.gpu_backlog,
            .presentation_backlog = latest_signals.presentation_backlog,
            .presentation_capacity = latest_signals.presentation_capacity,
        });
    }

    Signals latest_signals{};
    Clock::time_point last_arrival{};
    std::uint64_t last_pacing_resyncs{};
    std::uint64_t rendered_frames{};
    std::uint64_t skipped_frames{};
    std::uint32_t work_samples{};
    std::uint32_t frames_since_skip{MinRenderedFramesBetweenSkips};
    std::uint32_t pressure_score{};
    double estimated_composite_ms{};
    bool session_enabled{};
    bool has_resync_baseline{};
    bool pressure_active{};
    bool skip_pending{};
};

} // namespace Common::SmartAdaptiveFrameSkip
