#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path


TAG = "[moonwitch-unleashed-core]"


def replace_once(path: Path, old: str, new: str, marker: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if marker in text:
        print(f"{TAG} {label}: already patched")
        return
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one anchor for {label}, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"{TAG} {label}: patched")


def create_file(path: Path, content: str, marker: str, label: str) -> None:
    if path.exists():
        text = path.read_text(encoding="utf-8")
        if marker in text:
            print(f"{TAG} {label}: already patched")
            return
        raise RuntimeError(f"{path}: refusing to replace an unrelated existing file")
    path.write_text(content, encoding="utf-8")
    print(f"{TAG} {label}: created")


root = Path(".")
header = root / "src/common/moonwitch_unleashed.h"
source = root / "src/common/moonwitch_unleashed.cpp"
common_cmake = root / "src/common/CMakeLists.txt"
settings_h = root / "src/common/settings.h"
cpu_manager = root / "src/core/cpu_manager.cpp"
gpu_thread = root / "src/video_core/gpu_thread.cpp"
vk_scheduler = root / "src/video_core/renderer_vulkan/vk_scheduler.cpp"
perf_stats = root / "src/core/perf_stats.cpp"
core_cpp = root / "src/core/core.cpp"
adpf_h = root / "src/common/adpf.h"
adpf_cpp = root / "src/common/adpf.cpp"


create_file(
    header,
    '''// SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#include <chrono>
#include <cstddef>
#include "common/common_types.h"

namespace Common::MoonwitchUnleashed {

enum class ThreadRole : u32 {
    CPUCore,
    GPU,
    VulkanWorker,
};

struct FrameStats {
    double median_ms{};
    double p95_ms{};
    double p99_ms{};
    u32 sample_count{};
};

struct Telemetry {
    bool enabled{};
    bool kernel_supported{};
    bool boost_active{};
    u32 registered_threads{};
    u32 applied_threads{};
    u32 failed_threads{};
    u32 requested_util_min_percent{};
    u64 deadline_misses{};
    u64 boost_events{};
    FrameStats baseline{};
    FrameStats active{};
};

// Registers only the latency-critical emulation threads selected by Moonwitch. The original
// per-thread clamp is captured before any change and restored on thread exit or session shutdown.
void RegisterCurrentThread(ThreadRole role);

// Applies or restores the scheduler floor immediately for every registered critical thread.
void SetEnabled(bool enabled);

// Drives the short 90% burst after repeated deadline misses and records before/after samples.
void ReportFrameWorkDuration(std::chrono::nanoseconds actual,
                             std::chrono::nanoseconds target);

Telemetry GetTelemetry();

// Restores all captured scheduler values without changing the saved setting for the next session.
void EndSession();

} // namespace Common::MoonwitchUnleashed
''',
    "namespace Common::MoonwitchUnleashed",
    "declare scheduler controller",
)


create_file(
    source,
    '''// SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
// SPDX-License-Identifier: GPL-3.0-or-later

#include "common/moonwitch_unleashed.h"

#ifdef __ANDROID__

#include <algorithm>
#include <array>
#include <cerrno>
#include <chrono>
#include <cstring>
#include <mutex>
#include <vector>

#include <sys/syscall.h>
#include <unistd.h>

#include "common/logging.h"

namespace Common::MoonwitchUnleashed {
namespace {

constexpr u32 UTIL_SCALE = 1024;
constexpr u32 BASE_UTIL_MIN = 768;  // 75%
constexpr u32 BURST_UTIL_MIN = 922; // 90%, rounded from 921.6
constexpr u32 DEADLINE_MISS_PERCENT = 105;
constexpr u32 MISSES_BEFORE_BURST = 3;
constexpr auto BURST_DURATION = std::chrono::seconds{2};
constexpr std::size_t FRAME_WINDOW = 600;

constexpr u64 SCHED_FLAG_KEEP_POLICY_VALUE = 0x08;
constexpr u64 SCHED_FLAG_KEEP_PARAMS_VALUE = 0x10;
constexpr u64 SCHED_FLAG_UTIL_CLAMP_MIN_VALUE = 0x20;

#if defined(SYS_sched_getattr) && defined(SYS_sched_setattr)
constexpr bool HAS_UCLAMP_SYSCALLS = true;
#else
constexpr bool HAS_UCLAMP_SYSCALLS = false;
#endif

struct SchedAttr {
    u32 size{};
    u32 sched_policy{};
    u64 sched_flags{};
    s32 sched_nice{};
    u32 sched_priority{};
    u64 sched_runtime{};
    u64 sched_deadline{};
    u64 sched_period{};
    u32 sched_util_min{};
    u32 sched_util_max{};
};

struct FrameWindow {
    std::array<double, FRAME_WINDOW> values{};
    std::size_t index{};
    std::size_t count{};

    void Push(double value) {
        values[index] = value;
        index = (index + 1) % values.size();
        count = std::min(count + 1, values.size());
    }
};

struct CriticalThread {
    pid_t tid{};
    ThreadRole role{};
    bool original_captured{};
    bool applied{};
    u32 original_util_min{};
    u32 current_util_min{};
    int last_error{};
};

struct ControllerState {
    std::mutex mutex;
    std::vector<CriticalThread> threads;
    bool enabled{};
    bool boost_active{};
    u32 requested_util_min{};
    u32 consecutive_misses{};
    std::chrono::steady_clock::time_point boost_until{};
    u64 deadline_misses{};
    u64 boost_events{};
    FrameWindow disabled_history;
    FrameWindow baseline;
    FrameWindow active;
};

ControllerState& State() {
    static ControllerState* const state = new ControllerState();
    return *state;
}

const char* RoleName(ThreadRole role) {
    switch (role) {
    case ThreadRole::CPUCore:
        return "CPUCore";
    case ThreadRole::GPU:
        return "GPU";
    case ThreadRole::VulkanWorker:
        return "VulkanWorker";
    }
    return "Unknown";
}

bool ReadAttr(pid_t tid, SchedAttr& attr, int& error) {
    if constexpr (!HAS_UCLAMP_SYSCALLS) {
        error = ENOSYS;
        return false;
    }
#if defined(SYS_sched_getattr) && defined(SYS_sched_setattr)
    attr = {};
    attr.size = sizeof(attr);
    if (syscall(SYS_sched_getattr, tid, &attr, sizeof(attr), 0) != 0) {
        error = errno;
        return false;
    }
    return true;
#else
    (void)tid;
    (void)attr;
    error = ENOSYS;
    return false;
#endif
}

bool WriteClamp(pid_t tid, u32 requested, u32& observed, int& error) {
    SchedAttr attr{};
    if (!ReadAttr(tid, attr, error)) {
        return false;
    }

    const u32 effective = std::min(requested, attr.sched_util_max);
    attr.sched_flags = SCHED_FLAG_KEEP_POLICY_VALUE | SCHED_FLAG_KEEP_PARAMS_VALUE |
                       SCHED_FLAG_UTIL_CLAMP_MIN_VALUE;
    attr.sched_util_min = effective;

#if defined(SYS_sched_getattr) && defined(SYS_sched_setattr)
    if (syscall(SYS_sched_setattr, tid, &attr, 0) != 0) {
        error = errno;
        if (error != EINVAL) {
            return false;
        }

        // Some Android kernels expose utilization clamping but reject KEEP_* flags. Re-submit the
        // exact attributes returned by sched_getattr while changing only the requested minimum.
        attr.sched_flags = SCHED_FLAG_UTIL_CLAMP_MIN_VALUE;
        if (syscall(SYS_sched_setattr, tid, &attr, 0) != 0) {
            error = errno;
            return false;
        }
    }

    SchedAttr verify{};
    if (!ReadAttr(tid, verify, error)) {
        return false;
    }
    observed = verify.sched_util_min;
    if (observed != effective) {
        error = ERANGE;
        return false;
    }
    error = 0;
    return true;
#else
    (void)effective;
    error = ENOSYS;
    return false;
#endif
}

bool CaptureOriginal(CriticalThread& thread) {
    SchedAttr attr{};
    if (!ReadAttr(thread.tid, attr, thread.last_error)) {
        return false;
    }
    thread.original_util_min = attr.sched_util_min;
    thread.current_util_min = attr.sched_util_min;
    thread.original_captured = true;
    return true;
}

bool Apply(CriticalThread& thread, u32 requested) {
    if (!thread.original_captured && !CaptureOriginal(thread)) {
        thread.applied = false;
        return false;
    }
    u32 observed{};
    if (!WriteClamp(thread.tid, requested, observed, thread.last_error)) {
        thread.applied = false;
        return false;
    }
    thread.current_util_min = observed;
    thread.applied = observed >= requested;
    return thread.applied;
}

void Restore(CriticalThread& thread) {
    if (!thread.original_captured) {
        thread.applied = false;
        return;
    }
    u32 observed{};
    if (!WriteClamp(thread.tid, thread.original_util_min, observed, thread.last_error)) {
        LOG_WARNING(Common, "Moonwitch Unleashed could not restore {} thread {}: {}",
                    RoleName(thread.role), thread.tid, std::strerror(thread.last_error));
        return;
    }
    thread.current_util_min = observed;
    thread.applied = false;
}

void ApplyAllLocked(ControllerState& state, u32 requested) {
    state.requested_util_min = requested;
    u32 successes = 0;
    for (auto& thread : state.threads) {
        if (Apply(thread, requested)) {
            ++successes;
        }
    }
    LOG_INFO(Common, "Moonwitch Unleashed requested uclamp.min {}%: {}/{} critical threads verified",
             (requested * 100 + UTIL_SCALE / 2) / UTIL_SCALE, successes, state.threads.size());
}

FrameStats Summarize(const FrameWindow& window) {
    if (window.count == 0) {
        return {};
    }
    std::array<double, FRAME_WINDOW> sorted{};
    std::copy_n(window.values.begin(), window.count, sorted.begin());
    std::sort(sorted.begin(), sorted.begin() + window.count);
    const auto percentile = [&](std::size_t value) {
        const std::size_t rank = std::max<std::size_t>(1, (window.count * value + 99) / 100);
        return sorted[std::min(rank - 1, window.count - 1)];
    };
    return FrameStats{
        .median_ms = percentile(50),
        .p95_ms = percentile(95),
        .p99_ms = percentile(99),
        .sample_count = static_cast<u32>(window.count),
    };
}

void Unregister(pid_t tid) {
    ControllerState& state = State();
    std::scoped_lock lock{state.mutex};
    const auto it = std::find_if(state.threads.begin(), state.threads.end(),
                                 [tid](const CriticalThread& thread) { return thread.tid == tid; });
    if (it == state.threads.end()) {
        return;
    }
    Restore(*it);
    state.threads.erase(it);
}

struct ThreadRegistration {
    bool registered{};
    ~ThreadRegistration() {
        if (registered) {
            Unregister(gettid());
        }
    }
};

thread_local ThreadRegistration t_registration;

} // Anonymous namespace

void RegisterCurrentThread(ThreadRole role) {
    const pid_t tid = gettid();
    ControllerState& state = State();
    std::scoped_lock lock{state.mutex};
    if (std::any_of(state.threads.begin(), state.threads.end(),
                    [tid](const CriticalThread& thread) { return thread.tid == tid; })) {
        return;
    }

    CriticalThread thread{.tid = tid, .role = role};
    CaptureOriginal(thread);
    if (state.enabled) {
        Apply(thread, state.requested_util_min == 0 ? BASE_UTIL_MIN : state.requested_util_min);
    }
    state.threads.push_back(thread);
    t_registration.registered = true;
}

void SetEnabled(bool enabled) {
    ControllerState& state = State();
    std::scoped_lock lock{state.mutex};
    if (state.enabled == enabled) {
        return;
    }

    state.enabled = enabled;
    state.boost_active = false;
    state.consecutive_misses = 0;
    state.boost_until = {};
    if (enabled) {
        state.baseline = state.disabled_history;
        state.active = {};
        state.deadline_misses = 0;
        state.boost_events = 0;
        ApplyAllLocked(state, BASE_UTIL_MIN);
    } else {
        for (auto& thread : state.threads) {
            Restore(thread);
        }
        state.requested_util_min = 0;
        LOG_INFO(Common, "Moonwitch Unleashed disabled; original scheduler clamps restored");
    }
}

void ReportFrameWorkDuration(std::chrono::nanoseconds actual,
                             std::chrono::nanoseconds target) {
    if (actual.count() <= 0) {
        return;
    }

    ControllerState& state = State();
    std::scoped_lock lock{state.mutex};
    const double actual_ms = std::chrono::duration<double, std::milli>(actual).count();
    if (!state.enabled) {
        state.disabled_history.Push(actual_ms);
        return;
    }

    state.active.Push(actual_ms);
    if (target.count() <= 0) {
        return;
    }

    const auto now = std::chrono::steady_clock::now();
    const bool missed = actual.count() * 100 > target.count() * DEADLINE_MISS_PERCENT;
    if (missed) {
        ++state.deadline_misses;
        ++state.consecutive_misses;
        if (state.consecutive_misses >= MISSES_BEFORE_BURST) {
            state.consecutive_misses = 0;
            state.boost_until = now + BURST_DURATION;
            if (!state.boost_active) {
                state.boost_active = true;
                ++state.boost_events;
                ApplyAllLocked(state, BURST_UTIL_MIN);
            }
        }
    } else {
        state.consecutive_misses = 0;
    }

    if (state.boost_active && now >= state.boost_until) {
        state.boost_active = false;
        ApplyAllLocked(state, BASE_UTIL_MIN);
    }
}

Telemetry GetTelemetry() {
    ControllerState& state = State();
    std::scoped_lock lock{state.mutex};

    const u32 registered = static_cast<u32>(state.threads.size());
    const u32 applied = static_cast<u32>(std::count_if(
        state.threads.begin(), state.threads.end(),
        [](const CriticalThread& thread) { return thread.applied; }));
    const bool any_supported = std::any_of(
        state.threads.begin(), state.threads.end(),
        [](const CriticalThread& thread) { return thread.original_captured; });

    return Telemetry{
        .enabled = state.enabled,
        .kernel_supported = HAS_UCLAMP_SYSCALLS && (registered == 0 || any_supported),
        .boost_active = state.boost_active,
        .registered_threads = registered,
        .applied_threads = applied,
        .failed_threads = state.enabled ? registered - applied : 0,
        .requested_util_min_percent =
            (state.requested_util_min * 100 + UTIL_SCALE / 2) / UTIL_SCALE,
        .deadline_misses = state.deadline_misses,
        .boost_events = state.boost_events,
        .baseline = Summarize(state.baseline),
        .active = Summarize(state.active),
    };
}

void EndSession() {
    ControllerState& state = State();
    std::scoped_lock lock{state.mutex};
    for (auto& thread : state.threads) {
        Restore(thread);
    }
    state.threads.clear();
    state.boost_active = false;
    state.consecutive_misses = 0;
    state.boost_until = {};
    state.requested_util_min = state.enabled ? BASE_UTIL_MIN : 0;
    LOG_INFO(Common, "Moonwitch Unleashed session ended; all tracked clamps restored");
}

} // namespace Common::MoonwitchUnleashed

#else

namespace Common::MoonwitchUnleashed {

void RegisterCurrentThread(ThreadRole) {}
void SetEnabled(bool) {}
void ReportFrameWorkDuration(std::chrono::nanoseconds, std::chrono::nanoseconds) {}
Telemetry GetTelemetry() {
    return {};
}
void EndSession() {}

} // namespace Common::MoonwitchUnleashed

#endif
''',
    "Moonwitch Unleashed requested uclamp.min",
    "implement verified uclamp controller",
)


replace_once(
    adpf_h,
    "void SetTargetWorkDuration(std::chrono::nanoseconds target);\n",
    "void SetTargetWorkDuration(std::chrono::nanoseconds target);\n"
    "std::chrono::nanoseconds GetTargetWorkDuration();\n",
    "GetTargetWorkDuration();",
    "expose lock-free ADPF target",
)

replace_once(
    adpf_cpp,
    """    if (state.handle != nullptr) {
        api.update_target(state.handle, target.count());
    }
}

void ReportActualWorkDuration(std::chrono::nanoseconds actual_duration) {
""",
    """    if (state.handle != nullptr) {
        api.update_target(state.handle, target.count());
    }
}

std::chrono::nanoseconds GetTargetWorkDuration() {
    return std::chrono::nanoseconds{g_target_ns.load(std::memory_order_relaxed)};
}

void ReportActualWorkDuration(std::chrono::nanoseconds actual_duration) {
""",
    "return std::chrono::nanoseconds{g_target_ns.load(std::memory_order_relaxed)};",
    "implement lock-free ADPF target read",
)

replace_once(
    adpf_cpp,
    "void SetTargetWorkDuration(std::chrono::nanoseconds) {}\n\n"
    "void ReportActualWorkDuration(std::chrono::nanoseconds) {}\n",
    "void SetTargetWorkDuration(std::chrono::nanoseconds) {}\n\n"
    "std::chrono::nanoseconds GetTargetWorkDuration() {\n"
    "    return {};\n"
    "}\n\n"
    "void ReportActualWorkDuration(std::chrono::nanoseconds) {}\n",
    "std::chrono::nanoseconds GetTargetWorkDuration() {\n    return {};\n}",
    "add non-Android ADPF target stub",
)

replace_once(
    common_cmake,
    "    adpf.cpp\n    adpf.h\n",
    "    adpf.cpp\n    adpf.h\n    moonwitch_unleashed.cpp\n    moonwitch_unleashed.h\n",
    "moonwitch_unleashed.cpp",
    "compile scheduler controller",
)

replace_once(
    settings_h,
    '    SwitchableSetting<bool> use_multi_core{linkage, true, "use_multi_core", Category::Core};\n',
    '    SwitchableSetting<bool> use_multi_core{linkage, true, "use_multi_core", Category::Core};\n'
    '    SwitchableSetting<bool> moonwitch_unleashed{\n'
    '        linkage, false, "moonwitch_unleashed", Category::Core,\n'
    '        Specialization::Default, true, true};\n',
    "moonwitch_unleashed{",
    "register runtime and per-game setting",
)

replace_once(
    cpu_manager,
    '#include "common/thread.h"\n',
    '#include "common/thread.h"\n#include "common/moonwitch_unleashed.h"\n',
    '#include "common/moonwitch_unleashed.h"',
    "include controller in CPU manager",
)

replace_once(
    cpu_manager,
    "    Common::SetCurrentThreadToPerformanceCores();\n    auto& data = core_data[core];\n",
    "    Common::SetCurrentThreadToPerformanceCores();\n"
    "    Common::MoonwitchUnleashed::RegisterCurrentThread(\n"
    "        Common::MoonwitchUnleashed::ThreadRole::CPUCore);\n"
    "    auto& data = core_data[core];\n",
    "ThreadRole::CPUCore",
    "register CPU cores",
)

replace_once(
    gpu_thread,
    '#include "common/thread.h"\n',
    '#include "common/thread.h"\n#include "common/moonwitch_unleashed.h"\n',
    '#include "common/moonwitch_unleashed.h"',
    "include controller in GPU thread",
)

replace_once(
    gpu_thread,
    "        Common::SetCurrentThreadToPerformanceCores();\n        system.RegisterHostThread();\n",
    "        Common::SetCurrentThreadToPerformanceCores();\n"
    "        Common::MoonwitchUnleashed::RegisterCurrentThread(\n"
    "            Common::MoonwitchUnleashed::ThreadRole::GPU);\n"
    "        system.RegisterHostThread();\n",
    "ThreadRole::GPU",
    "register GPU thread",
)

replace_once(
    vk_scheduler,
    '#include "common/thread.h"\n',
    '#include "common/thread.h"\n#include "common/moonwitch_unleashed.h"\n',
    '#include "common/moonwitch_unleashed.h"',
    "include controller in Vulkan scheduler",
)

replace_once(
    vk_scheduler,
    "    Common::SetCurrentThreadToPerformanceCores();\n\n    const auto TryPopQueue",
    "    Common::SetCurrentThreadToPerformanceCores();\n"
    "    Common::MoonwitchUnleashed::RegisterCurrentThread(\n"
    "        Common::MoonwitchUnleashed::ThreadRole::VulkanWorker);\n\n"
    "    const auto TryPopQueue",
    "ThreadRole::VulkanWorker",
    "register Vulkan worker",
)

replace_once(
    perf_stats,
    '#include "common/fs/path_util.h"\n',
    '#include "common/fs/path_util.h"\n#include "common/moonwitch_unleashed.h"\n',
    '#include "common/moonwitch_unleashed.h"',
    "include controller in performance stats",
)

replace_once(
    perf_stats,
    "    Common::ADPF::ReportActualWorkDuration(\n"
    "        std::chrono::duration_cast<std::chrono::nanoseconds>(frame_time));\n",
    "    const auto frame_work_ns =\n"
    "        std::chrono::duration_cast<std::chrono::nanoseconds>(frame_time);\n"
    "    Common::ADPF::ReportActualWorkDuration(frame_work_ns);\n"
    "    Common::MoonwitchUnleashed::ReportFrameWorkDuration(\n"
    "        frame_work_ns, Common::ADPF::GetTargetWorkDuration());\n",
    "MoonwitchUnleashed::ReportFrameWorkDuration",
    "feed deadline controller and comparison samples",
)

replace_once(
    core_cpp,
    '#include "common/logging.h"\n',
    '#include "common/logging.h"\n#include "common/moonwitch_unleashed.h"\n',
    '#include "common/moonwitch_unleashed.h"',
    "include controller in core shutdown",
)

replace_once(
    core_cpp,
    "        SetShuttingDown(true);\n        Common::ADPF::Shutdown();\n",
    "        SetShuttingDown(true);\n"
    "        Common::MoonwitchUnleashed::EndSession();\n"
    "        Common::ADPF::Shutdown();\n",
    "MoonwitchUnleashed::EndSession();",
    "restore clamps during game shutdown",
)

print("Applied Moonwitch Unleashed native scheduler controller.")
