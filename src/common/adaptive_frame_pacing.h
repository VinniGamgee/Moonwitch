// SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <thread>

namespace Common::AdaptiveFramePacing {

struct Telemetry {
    bool active{};
    double target_fps{};
    double producer_fps{};
    std::uint64_t paced_frames{};
    std::uint64_t resyncs{};
    double last_delay_ms{};
};

namespace Detail {

inline std::atomic_bool g_active{false};
inline std::atomic<std::int64_t> g_target_millifps{0};
inline std::atomic<std::int64_t> g_producer_millifps{0};
inline std::atomic<std::uint64_t> g_paced_frames{0};
inline std::atomic<std::uint64_t> g_resyncs{0};
inline std::atomic<std::int64_t> g_last_delay_ns{0};

inline void Publish(bool active, double target_fps, double producer_fps,
                    std::chrono::nanoseconds delay) {
    g_active.store(active, std::memory_order_relaxed);
    g_target_millifps.store(static_cast<std::int64_t>(std::llround(target_fps * 1000.0)),
                            std::memory_order_relaxed);
    g_producer_millifps.store(static_cast<std::int64_t>(std::llround(producer_fps * 1000.0)),
                              std::memory_order_relaxed);
    g_last_delay_ns.store(delay.count(), std::memory_order_relaxed);
}

} // namespace Detail

inline Telemetry GetTelemetry() {
    return Telemetry{
        .active = Detail::g_active.load(std::memory_order_relaxed),
        .target_fps = static_cast<double>(
                          Detail::g_target_millifps.load(std::memory_order_relaxed)) /
                      1000.0,
        .producer_fps = static_cast<double>(
                            Detail::g_producer_millifps.load(std::memory_order_relaxed)) /
                        1000.0,
        .paced_frames = Detail::g_paced_frames.load(std::memory_order_relaxed),
        .resyncs = Detail::g_resyncs.load(std::memory_order_relaxed),
        .last_delay_ms = static_cast<double>(
                            Detail::g_last_delay_ns.load(std::memory_order_relaxed)) /
                        1'000'000.0,
    };
}

/**
 * Deadline-based frame pacer for Android's modern Vulkan presentation path.
 *
 * The controller deliberately never waits for a frame that has already missed its deadline. Late
 * frames resynchronize the phase immediately, preventing the classic "catch-up burst" where a
 * limiter releases several frames back-to-back after a stutter. Auto mode learns the unpaced
 * producer cadence and chooses the next standard ceiling (30/60/90/120 Hz), so a 23 FPS workload
 * is never capped to 20 FPS and retains headroom to recover.
 */
class Controller {
public:
    using Clock = std::chrono::steady_clock;

    void Pace(bool enabled, bool automatic, double requested_fps, bool async_presentation) {
        const auto now = Clock::now();
        ObserveProducer(now, async_presentation);

        if (!enabled) {
            ResetDeadlines();
            Detail::Publish(false, 0.0, ProducerFps(), std::chrono::nanoseconds::zero());
            return;
        }

        const double target_fps = automatic ? AutoTarget(async_presentation) : requested_fps;
        if (target_fps <= 0.0) {
            // Auto mode is still warming up. Do not impose a guessed limit.
            ResetDeadlines();
            Detail::Publish(false, 0.0, ProducerFps(), std::chrono::nanoseconds::zero());
            return;
        }

        const auto interval = std::chrono::duration_cast<Clock::duration>(
            std::chrono::duration<double>(1.0 / target_fps));

        if (current_target_fps != target_fps || next_deadline.time_since_epoch().count() == 0) {
            current_target_fps = target_fps;
            next_deadline = now + interval;
            last_applied_delay = Clock::duration::zero();
            Detail::Publish(true, target_fps, ProducerFps(), std::chrono::nanoseconds::zero());
            return;
        }

        if (now >= next_deadline) {
            // A late frame must never be delayed further. Drop accumulated timing debt and start a
            // new phase from this frame so a shader/CPU hitch cannot cause a presentation burst.
            next_deadline = now + interval;
            last_applied_delay = Clock::duration::zero();
            Detail::g_resyncs.fetch_add(1, std::memory_order_relaxed);
            Detail::Publish(true, target_fps, ProducerFps(), std::chrono::nanoseconds::zero());
            return;
        }

        const auto deadline = next_deadline;
        std::this_thread::sleep_until(deadline);
        const auto after_sleep = Clock::now();
        last_applied_delay = after_sleep - now;
        Detail::g_paced_frames.fetch_add(1, std::memory_order_relaxed);

        // Advance from the ideal deadline rather than from the wake-up timestamp. Small scheduler
        // overshoots therefore do not become permanent phase drift.
        next_deadline = deadline + interval;
        Detail::Publish(
            true, target_fps, ProducerFps(),
            std::chrono::duration_cast<std::chrono::nanoseconds>(last_applied_delay));
    }

    void Reset() {
        last_observation = {};
        ema_producer_ns = 0.0;
        producer_samples = 0;
        auto_target_fps = 0.0;
        pending_lower_target = 0.0;
        lower_target_samples = 0;
        ResetDeadlines();
        Detail::Publish(false, 0.0, 0.0, std::chrono::nanoseconds::zero());
    }

private:
    void ObserveProducer(Clock::time_point now, bool async_presentation) {
        if (last_observation.time_since_epoch().count() == 0) {
            last_observation = now;
            return;
        }

        auto observed = now - last_observation;
        last_observation = now;

        // With synchronous presentation the interval includes the delay that this controller added
        // to the previous frame. Remove only our own wait so Auto learns the producer rather than
        // learning its own cap. The asynchronous present thread consumes an already-queued stream,
        // so its inter-present interval is not a reliable producer signal.
        if (!async_presentation && observed > last_applied_delay) {
            observed -= last_applied_delay;
        }
        last_applied_delay = Clock::duration::zero();

        if (async_presentation) {
            return;
        }

        const double ns = static_cast<double>(
            std::chrono::duration_cast<std::chrono::nanoseconds>(observed).count());
        // Ignore impossible/noisy samples and long pauses, menus or surface transitions.
        if (ns < 2'000'000.0 || ns > 250'000'000.0) {
            return;
        }

        constexpr double alpha = 0.12;
        ema_producer_ns = producer_samples == 0 ? ns : ema_producer_ns + alpha * (ns - ema_producer_ns);
        ++producer_samples;
    }

    [[nodiscard]] double ProducerFps() const {
        if (ema_producer_ns <= 0.0) {
            return 0.0;
        }
        return 1'000'000'000.0 / ema_producer_ns;
    }

    [[nodiscard]] static double CeilingFor(double producer_fps) {
        // Small tolerance keeps a nominal 30/60/90 FPS source in its matching bucket while still
        // moving up immediately when the producer is genuinely faster than that ceiling.
        if (producer_fps <= 31.5) {
            return 30.0;
        }
        if (producer_fps <= 63.0) {
            return 60.0;
        }
        if (producer_fps <= 94.5) {
            return 90.0;
        }
        return 120.0;
    }

    double AutoTarget(bool async_presentation) {
        if (async_presentation) {
            // The consumer thread can drain queued frames in bursts, which would poison cadence
            // detection. 60 Hz is a safe ceiling: workloads below it are never delayed when late.
            auto_target_fps = 60.0;
            return auto_target_fps;
        }

        constexpr std::uint32_t warmup_samples = 8;
        if (producer_samples < warmup_samples) {
            return 0.0;
        }

        const double desired = CeilingFor(ProducerFps());
        if (auto_target_fps == 0.0) {
            auto_target_fps = desired;
            return auto_target_fps;
        }

        if (desired > auto_target_fps) {
            // Removing a restriction is safe, so allow recovery almost immediately.
            auto_target_fps = desired;
            pending_lower_target = 0.0;
            lower_target_samples = 0;
            return auto_target_fps;
        }

        if (desired < auto_target_fps) {
            if (pending_lower_target != desired) {
                pending_lower_target = desired;
                lower_target_samples = 1;
            } else {
                ++lower_target_samples;
            }
            // A lower ceiling is only accepted after sustained evidence. During this period slow
            // frames simply miss the higher-frequency deadline and are never blocked.
            constexpr std::uint32_t downshift_samples = 24;
            if (lower_target_samples >= downshift_samples) {
                auto_target_fps = desired;
                pending_lower_target = 0.0;
                lower_target_samples = 0;
            }
        } else {
            pending_lower_target = 0.0;
            lower_target_samples = 0;
        }
        return auto_target_fps;
    }

    void ResetDeadlines() {
        next_deadline = {};
        current_target_fps = 0.0;
        last_applied_delay = Clock::duration::zero();
    }

    Clock::time_point last_observation{};
    Clock::time_point next_deadline{};
    Clock::duration last_applied_delay{};
    double ema_producer_ns{};
    double current_target_fps{};
    double auto_target_fps{};
    double pending_lower_target{};
    std::uint32_t producer_samples{};
    std::uint32_t lower_target_samples{};
};

} // namespace Common::AdaptiveFramePacing
