#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path


TAG = "[moonwitch-core-director-core]"


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
header = root / "src/common/moonwitch_core_director.h"
source = root / "src/common/moonwitch_core_director.cpp"
common_cmake = root / "src/common/CMakeLists.txt"
settings_h = root / "src/common/settings.h"
cpu_manager = root / "src/core/cpu_manager.cpp"
gpu_thread = root / "src/video_core/gpu_thread.cpp"
vk_scheduler = root / "src/video_core/renderer_vulkan/vk_scheduler.cpp"
perf_stats = root / "src/core/perf_stats.cpp"
core_cpp = root / "src/core/core.cpp"


create_file(
    header,
    '''// SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#include "common/common_types.h"

namespace Common::MoonwitchCoreDirector {

enum class ThreadRole : u32 {
    CPUCore,
    GPU,
    VulkanWorker,
};

struct Telemetry {
    bool enabled{};
    bool snapdragon_detected{};
    bool topology_available{};
    u32 registered_threads{};
    u32 applied_threads{};
    u32 failed_threads{};
    u32 allowed_core_count{};
    u32 performance_core_count{};
    u64 performance_core_mask{};
    u32 prime_core{};
    u64 apply_events{};
    u64 drift_repairs{};
    u64 restore_events{};
};

// Captures the thread's original affinity and applies the Snapdragon performance mask live.
void RegisterCurrentThread(ThreadRole role);

// Enables or disables hard affinity. Disable always restores every captured original mask.
void SetEnabled(bool enabled);

// Re-verifies affinity periodically because some vendor kernels overwrite userspace masks.
void Maintain();

Telemetry GetTelemetry();

// Restores every tracked thread and forgets the topology at the end of a game session.
void EndSession();

} // namespace Common::MoonwitchCoreDirector
''',
    "namespace Common::MoonwitchCoreDirector",
    "declare Snapdragon affinity director",
)


create_file(
    source,
    '''// SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
// SPDX-License-Identifier: GPL-3.0-or-later

#include "common/moonwitch_core_director.h"

#ifdef __ANDROID__

#include <algorithm>
#include <array>
#include <cerrno>
#include <chrono>
#include <cctype>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <mutex>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

#include <sched.h>
#include <sys/system_properties.h>
#include <unistd.h>

#include "common/logging.h"

namespace Common::MoonwitchCoreDirector {
namespace {

constexpr u32 MINIMUM_PERFORMANCE_CORES = 4;
constexpr u32 MINIMUM_CLUSTER_DROP_PERCENT = 12;
constexpr auto VERIFY_INTERVAL = std::chrono::milliseconds{500};

struct CpuInfo {
    s64 weight{};
    u64 midr{};
    s32 cpu{};
};

struct CriticalThread {
    pid_t tid{};
    ThreadRole role{};
    cpu_set_t original_mask{};
    cpu_set_t requested_mask{};
    bool original_captured{};
    bool affinity_modified{};
    bool applied{};
    int last_error{};
};

struct ControllerState {
    std::mutex mutex;
    std::vector<CriticalThread> threads;
    bool enabled{};
    bool topology_initialized{};
    bool snapdragon_detected{};
    bool topology_available{};
    cpu_set_t allowed_mask{};
    cpu_set_t performance_mask{};
    u32 allowed_core_count{};
    u32 performance_core_count{};
    u64 performance_mask_bits{};
    u32 prime_core{};
    u64 apply_events{};
    u64 drift_repairs{};
    u64 restore_events{};
    std::chrono::steady_clock::time_point next_verify{};
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

std::string ReadProperty(const char* key) {
    std::array<char, PROP_VALUE_MAX> value{};
    const int length = __system_property_get(key, value.data());
    return length > 0 ? std::string{value.data(), static_cast<std::size_t>(length)} : std::string{};
}

std::string Lower(std::string value) {
    std::transform(value.begin(), value.end(), value.begin(), [](unsigned char character) {
        return static_cast<char>(std::tolower(character));
    });
    return value;
}

bool Contains(std::string_view value, std::string_view needle) {
    return value.find(needle) != std::string_view::npos;
}

bool StartsWithSocCode(std::string_view model, std::string_view prefix) {
    if (!model.starts_with(prefix)) {
        return false;
    }
    return model.size() > prefix.size() &&
           std::isdigit(static_cast<unsigned char>(model[prefix.size()])) != 0;
}

bool DetectSnapdragon(std::string& model) {
    const std::string manufacturer = Lower(ReadProperty("ro.soc.manufacturer"));
    const std::string hardware = Lower(ReadProperty("ro.hardware"));
    const std::string board_platform = Lower(ReadProperty("ro.board.platform"));
    model = ReadProperty("ro.soc.model");
    const std::string lower_model = Lower(model);

    const bool qualcomm_vendor = Contains(manufacturer, "qualcomm") ||
                                 Contains(manufacturer, "qti") || Contains(hardware, "qcom") ||
                                 Contains(board_platform, "qcom");
    const bool snapdragon_code = StartsWithSocCode(lower_model, "sm") ||
                                 StartsWithSocCode(lower_model, "sdm") ||
                                 StartsWithSocCode(lower_model, "msm") ||
                                 StartsWithSocCode(lower_model, "apq") ||
                                 StartsWithSocCode(lower_model, "qcs") ||
                                 StartsWithSocCode(lower_model, "qcm");
    return qualcomm_vendor || snapdragon_code;
}

s64 ReadCpuScalar(s32 cpu, const char* node) {
    s64 value{};
    std::ifstream file{"/sys/devices/system/cpu/cpu" + std::to_string(cpu) + "/" + node};
    if (!file || !(file >> value) || value <= 0) {
        return 0;
    }
    return value;
}

u64 ReadCpuMidr(s32 cpu) {
    u64 value{};
    std::ifstream file{"/sys/devices/system/cpu/cpu" + std::to_string(cpu) +
                       "/regs/identification/midr_el1"};
    if (!file || !(file >> std::hex >> value)) {
        return 0;
    }
    return value;
}

std::vector<CpuInfo> CollectMetric(const cpu_set_t& allowed, const char* node) {
    std::vector<CpuInfo> cores;
    for (s32 cpu = 0; cpu < CPU_SETSIZE; ++cpu) {
        if (!CPU_ISSET(cpu, &allowed)) {
            continue;
        }
        const s64 weight = ReadCpuScalar(cpu, node);
        if (weight <= 0) {
            return {};
        }
        cores.push_back(CpuInfo{.weight = weight, .midr = ReadCpuMidr(cpu), .cpu = cpu});
    }
    return cores;
}

bool WeightsUniform(const std::vector<CpuInfo>& cores) {
    return !cores.empty() &&
           std::all_of(cores.begin(), cores.end(), [&](const CpuInfo& core) {
               return core.weight == cores.front().weight;
           });
}

bool MidrsDistinct(const std::vector<CpuInfo>& cores) {
    return !cores.empty() &&
           std::none_of(cores.begin(), cores.end(),
                        [](const CpuInfo& core) { return core.midr == 0; }) &&
           std::any_of(cores.begin(), cores.end(), [&](const CpuInfo& core) {
               return core.midr != cores.front().midr;
           });
}

bool MasksEqual(const cpu_set_t& lhs, const cpu_set_t& rhs) {
    return std::memcmp(&lhs, &rhs, sizeof(cpu_set_t)) == 0;
}

cpu_set_t Intersect(const cpu_set_t& lhs, const cpu_set_t& rhs) {
    cpu_set_t result;
    CPU_ZERO(&result);
    for (s32 cpu = 0; cpu < CPU_SETSIZE; ++cpu) {
        if (CPU_ISSET(cpu, &lhs) && CPU_ISSET(cpu, &rhs)) {
            CPU_SET(cpu, &result);
        }
    }
    return result;
}

void ResetTopologyLocked(ControllerState& state) {
    state.topology_initialized = false;
    state.snapdragon_detected = false;
    state.topology_available = false;
    CPU_ZERO(&state.allowed_mask);
    CPU_ZERO(&state.performance_mask);
    state.allowed_core_count = 0;
    state.performance_core_count = 0;
    state.performance_mask_bits = 0;
    state.prime_core = 0;
}

void InitializeTopologyLocked(ControllerState& state) {
    if (state.topology_initialized) {
        return;
    }
    state.topology_initialized = true;

    std::string model;
    state.snapdragon_detected = DetectSnapdragon(model);
    if (!state.snapdragon_detected) {
        LOG_WARNING(Common, "Moonwitch Core Director disabled affinity: Snapdragon SoC not detected");
        return;
    }

    if (sched_getaffinity(getpid(), sizeof(state.allowed_mask), &state.allowed_mask) != 0) {
        LOG_WARNING(Common, "Moonwitch Core Director could not read process affinity: {}",
                    std::strerror(errno));
        return;
    }
    state.allowed_core_count = static_cast<u32>(CPU_COUNT(&state.allowed_mask));
    if (state.allowed_core_count == 0) {
        return;
    }

    std::vector<CpuInfo> cores;
    std::vector<CpuInfo> uniform_cores;
    const std::array<const char*, 3> metric_nodes{
        "cpu_capacity",
        "cpufreq/cpuinfo_max_freq",
        "cpufreq/scaling_max_freq",
    };
    for (const char* node : metric_nodes) {
        auto candidate = CollectMetric(state.allowed_mask, node);
        if (candidate.size() != state.allowed_core_count) {
            continue;
        }
        if (WeightsUniform(candidate)) {
            if (uniform_cores.empty()) {
                uniform_cores = std::move(candidate);
            }
        } else {
            cores = std::move(candidate);
            break;
        }
    }

    bool used_cpu_id_fallback = false;
    if (cores.size() != state.allowed_core_count && uniform_cores.size() == state.allowed_core_count) {
        cores = std::move(uniform_cores);
        if (MidrsDistinct(cores)) {
            used_cpu_id_fallback = true;
            for (auto& core : cores) {
                core.weight = static_cast<s64>(core.cpu + 1);
            }
        }
    } else if (cores.size() != state.allowed_core_count) {
        used_cpu_id_fallback = true;
        cores.clear();
        for (s32 cpu = 0; cpu < CPU_SETSIZE; ++cpu) {
            if (CPU_ISSET(cpu, &state.allowed_mask)) {
                cores.push_back(CpuInfo{
                    .weight = static_cast<s64>(cpu + 1),
                    .midr = ReadCpuMidr(cpu),
                    .cpu = cpu,
                });
            }
        }
    }

    std::sort(cores.begin(), cores.end(), [](const CpuInfo& lhs, const CpuInfo& rhs) {
        if (lhs.weight != rhs.weight) {
            return lhs.weight > rhs.weight;
        }
        return lhs.cpu > rhs.cpu;
    });
    if (cores.empty()) {
        return;
    }

    const std::size_t minimum = std::min<std::size_t>(MINIMUM_PERFORMANCE_CORES, cores.size());
    std::size_t selected = cores.size();
    if (used_cpu_id_fallback) {
        selected = std::min(cores.size(),
                            std::max<std::size_t>(minimum, (cores.size() + 1) / 2));
    } else {
        u32 best_drop = 0;
        std::size_t best_split = cores.size();
        for (std::size_t split = minimum; split < cores.size(); ++split) {
            const s64 faster = cores[split - 1].weight;
            const s64 slower = cores[split].weight;
            if (faster <= slower || faster <= 0) {
                continue;
            }
            const u32 drop = static_cast<u32>((faster - slower) * 100 / faster);
            if (drop > best_drop) {
                best_drop = drop;
                best_split = split;
            }
        }
        if (best_drop >= MINIMUM_CLUSTER_DROP_PERCENT) {
            selected = best_split;
        }
    }

    CPU_ZERO(&state.performance_mask);
    for (std::size_t index = 0; index < selected; ++index) {
        const s32 cpu = cores[index].cpu;
        CPU_SET(cpu, &state.performance_mask);
        if (cpu < 64) {
            state.performance_mask_bits |= u64{1} << cpu;
        }
    }
    state.performance_core_count = static_cast<u32>(CPU_COUNT(&state.performance_mask));
    state.prime_core = static_cast<u32>(cores.front().cpu);
    state.topology_available = state.performance_core_count > 0;

    LOG_INFO(Common,
             "Moonwitch Core Director detected Snapdragon {}: performance CPUs 0x{:x}, {}/{} cores, prime CPU {}{}",
             model.empty() ? "(unknown model)" : model, state.performance_mask_bits,
             state.performance_core_count, state.allowed_core_count, state.prime_core,
             used_cpu_id_fallback ? " (CPU-ID fallback)" : "");
}

bool CaptureOriginal(CriticalThread& thread) {
    CPU_ZERO(&thread.original_mask);
    if (sched_getaffinity(thread.tid, sizeof(thread.original_mask), &thread.original_mask) != 0) {
        thread.last_error = errno;
        return false;
    }
    thread.original_captured = true;
    return true;
}

bool VerifyMask(CriticalThread& thread) {
    cpu_set_t observed;
    CPU_ZERO(&observed);
    if (sched_getaffinity(thread.tid, sizeof(observed), &observed) != 0) {
        thread.last_error = errno;
        thread.applied = false;
        return false;
    }
    thread.applied = MasksEqual(observed, thread.requested_mask);
    if (!thread.applied) {
        thread.last_error = ERANGE;
    }
    return thread.applied;
}

bool ApplyLocked(ControllerState& state, CriticalThread& thread) {
    if (!state.snapdragon_detected || !state.topology_available) {
        thread.applied = false;
        thread.last_error = ENOTSUP;
        return false;
    }
    if (!thread.original_captured && !CaptureOriginal(thread)) {
        thread.applied = false;
        return false;
    }

    thread.requested_mask = Intersect(thread.original_mask, state.performance_mask);
    if (CPU_COUNT(&thread.requested_mask) == 0) {
        thread.applied = false;
        thread.last_error = EINVAL;
        return false;
    }
    if (sched_setaffinity(thread.tid, sizeof(thread.requested_mask), &thread.requested_mask) != 0) {
        thread.applied = false;
        thread.last_error = errno;
        return false;
    }
    thread.affinity_modified = true;
    ++state.apply_events;
    return VerifyMask(thread);
}

bool RestoreLocked(ControllerState& state, CriticalThread& thread) {
    if (!thread.original_captured || !thread.affinity_modified) {
        thread.applied = false;
        return true;
    }
    if (sched_setaffinity(thread.tid, sizeof(thread.original_mask), &thread.original_mask) != 0) {
        thread.last_error = errno;
        LOG_WARNING(Common, "Moonwitch Core Director could not restore {} thread {}: {}",
                    RoleName(thread.role), thread.tid, std::strerror(thread.last_error));
        return false;
    }
    cpu_set_t observed;
    CPU_ZERO(&observed);
    if (sched_getaffinity(thread.tid, sizeof(observed), &observed) != 0 ||
        !MasksEqual(observed, thread.original_mask)) {
        thread.last_error = errno == 0 ? ERANGE : errno;
        return false;
    }
    thread.affinity_modified = false;
    thread.applied = false;
    ++state.restore_events;
    return true;
}

void Unregister(pid_t tid) {
    ControllerState& state = State();
    std::scoped_lock lock{state.mutex};
    const auto it = std::find_if(state.threads.begin(), state.threads.end(),
                                 [tid](const CriticalThread& thread) { return thread.tid == tid; });
    if (it == state.threads.end()) {
        return;
    }
    RestoreLocked(state, *it);
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

    InitializeTopologyLocked(state);
    CriticalThread thread{.tid = tid, .role = role};
    CaptureOriginal(thread);
    if (state.enabled) {
        ApplyLocked(state, thread);
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
    state.next_verify = {};
    if (enabled) {
        ResetTopologyLocked(state);
        InitializeTopologyLocked(state);
        state.apply_events = 0;
        state.drift_repairs = 0;
        state.restore_events = 0;
        u32 successes = 0;
        for (auto& thread : state.threads) {
            if (ApplyLocked(state, thread)) {
                ++successes;
            }
        }
        LOG_INFO(Common, "Moonwitch Core Director enabled: {}/{} critical threads hard-pinned",
                 successes, state.threads.size());
        return;
    }

    for (auto& thread : state.threads) {
        RestoreLocked(state, thread);
    }
    LOG_INFO(Common, "Moonwitch Core Director disabled; original affinity masks restored");
}

void Maintain() {
    ControllerState& state = State();
    std::scoped_lock lock{state.mutex};
    if (!state.enabled || !state.snapdragon_detected || !state.topology_available) {
        return;
    }
    const auto now = std::chrono::steady_clock::now();
    if (now < state.next_verify) {
        return;
    }
    state.next_verify = now + VERIFY_INTERVAL;

    for (auto& thread : state.threads) {
        if (!thread.original_captured) {
            continue;
        }
        cpu_set_t observed;
        CPU_ZERO(&observed);
        const bool readable =
            sched_getaffinity(thread.tid, sizeof(observed), &observed) == 0;
        if (readable && MasksEqual(observed, thread.requested_mask)) {
            thread.applied = true;
            continue;
        }
        thread.applied = false;
        if (ApplyLocked(state, thread)) {
            ++state.drift_repairs;
        }
    }
}

Telemetry GetTelemetry() {
    ControllerState& state = State();
    std::scoped_lock lock{state.mutex};
    const u32 registered = static_cast<u32>(state.threads.size());
    const u32 applied = static_cast<u32>(std::count_if(
        state.threads.begin(), state.threads.end(),
        [](const CriticalThread& thread) { return thread.applied; }));
    return Telemetry{
        .enabled = state.enabled,
        .snapdragon_detected = state.snapdragon_detected,
        .topology_available = state.topology_available,
        .registered_threads = registered,
        .applied_threads = applied,
        .failed_threads = state.enabled ? registered - applied : 0,
        .allowed_core_count = state.allowed_core_count,
        .performance_core_count = state.performance_core_count,
        .performance_core_mask = state.performance_mask_bits,
        .prime_core = state.prime_core,
        .apply_events = state.apply_events,
        .drift_repairs = state.drift_repairs,
        .restore_events = state.restore_events,
    };
}

void EndSession() {
    ControllerState& state = State();
    std::scoped_lock lock{state.mutex};
    for (auto& thread : state.threads) {
        RestoreLocked(state, thread);
    }
    state.threads.clear();
    state.next_verify = {};
    ResetTopologyLocked(state);
    LOG_INFO(Common, "Moonwitch Core Director session ended; tracked affinity masks restored");
}

} // namespace Common::MoonwitchCoreDirector

#else

namespace Common::MoonwitchCoreDirector {

void RegisterCurrentThread(ThreadRole) {}
void SetEnabled(bool) {}
void Maintain() {}
Telemetry GetTelemetry() {
    return {};
}
void EndSession() {}

} // namespace Common::MoonwitchCoreDirector

#endif
''',
    "namespace Common::MoonwitchCoreDirector",
    "implement Snapdragon affinity director",
)


replace_once(
    common_cmake,
    "    moonwitch_unleashed.cpp\n    moonwitch_unleashed.h\n",
    "    moonwitch_unleashed.cpp\n    moonwitch_unleashed.h\n"
    "    moonwitch_core_director.cpp\n    moonwitch_core_director.h\n",
    "moonwitch_core_director.cpp",
    "compile Core Director",
)

replace_once(
    settings_h,
    '    SwitchableSetting<bool> moonwitch_unleashed{\n'
    '        linkage, false, "moonwitch_unleashed", Category::Core,\n'
    '        Specialization::Default, true, true};\n',
    '    SwitchableSetting<bool> moonwitch_unleashed{\n'
    '        linkage, false, "moonwitch_unleashed", Category::Core,\n'
    '        Specialization::Default, true, true};\n'
    '    SwitchableSetting<bool> moonwitch_core_director{\n'
    '        linkage, false, "moonwitch_core_director", Category::Core,\n'
    '        Specialization::Default, true, true};\n',
    "moonwitch_core_director{",
    "register runtime and per-game setting",
)

replace_once(
    cpu_manager,
    '#include "common/moonwitch_unleashed.h"\n',
    '#include "common/moonwitch_unleashed.h"\n#include "common/moonwitch_core_director.h"\n',
    '#include "common/moonwitch_core_director.h"',
    "include Core Director in CPU manager",
)

replace_once(
    cpu_manager,
    "    Common::MoonwitchUnleashed::RegisterCurrentThread(\n"
    "        Common::MoonwitchUnleashed::ThreadRole::CPUCore);\n",
    "    Common::MoonwitchUnleashed::RegisterCurrentThread(\n"
    "        Common::MoonwitchUnleashed::ThreadRole::CPUCore);\n"
    "    Common::MoonwitchCoreDirector::RegisterCurrentThread(\n"
    "        Common::MoonwitchCoreDirector::ThreadRole::CPUCore);\n",
    "MoonwitchCoreDirector::ThreadRole::CPUCore",
    "register CPU cores",
)

replace_once(
    gpu_thread,
    '#include "common/moonwitch_unleashed.h"\n',
    '#include "common/moonwitch_unleashed.h"\n#include "common/moonwitch_core_director.h"\n',
    '#include "common/moonwitch_core_director.h"',
    "include Core Director in GPU thread",
)

replace_once(
    gpu_thread,
    "        Common::MoonwitchUnleashed::RegisterCurrentThread(\n"
    "            Common::MoonwitchUnleashed::ThreadRole::GPU);\n",
    "        Common::MoonwitchUnleashed::RegisterCurrentThread(\n"
    "            Common::MoonwitchUnleashed::ThreadRole::GPU);\n"
    "        Common::MoonwitchCoreDirector::RegisterCurrentThread(\n"
    "            Common::MoonwitchCoreDirector::ThreadRole::GPU);\n",
    "MoonwitchCoreDirector::ThreadRole::GPU",
    "register GPU thread",
)

replace_once(
    vk_scheduler,
    '#include "common/moonwitch_unleashed.h"\n',
    '#include "common/moonwitch_unleashed.h"\n#include "common/moonwitch_core_director.h"\n',
    '#include "common/moonwitch_core_director.h"',
    "include Core Director in Vulkan scheduler",
)

replace_once(
    vk_scheduler,
    "    Common::MoonwitchUnleashed::RegisterCurrentThread(\n"
    "        Common::MoonwitchUnleashed::ThreadRole::VulkanWorker);\n",
    "    Common::MoonwitchUnleashed::RegisterCurrentThread(\n"
    "        Common::MoonwitchUnleashed::ThreadRole::VulkanWorker);\n"
    "    Common::MoonwitchCoreDirector::RegisterCurrentThread(\n"
    "        Common::MoonwitchCoreDirector::ThreadRole::VulkanWorker);\n",
    "MoonwitchCoreDirector::ThreadRole::VulkanWorker",
    "register Vulkan worker",
)

replace_once(
    perf_stats,
    '#include "common/moonwitch_unleashed.h"\n',
    '#include "common/moonwitch_unleashed.h"\n#include "common/moonwitch_core_director.h"\n',
    '#include "common/moonwitch_core_director.h"',
    "include Core Director in performance stats",
)

replace_once(
    perf_stats,
    "    Common::MoonwitchUnleashed::ReportFrameWorkDuration(\n"
    "        frame_work_ns, Common::ADPF::GetTargetWorkDuration());\n",
    "    Common::MoonwitchUnleashed::ReportFrameWorkDuration(\n"
    "        frame_work_ns, Common::ADPF::GetTargetWorkDuration());\n"
    "    Common::MoonwitchCoreDirector::Maintain();\n",
    "MoonwitchCoreDirector::Maintain();",
    "verify hard affinity during frame processing",
)

replace_once(
    core_cpp,
    '#include "common/moonwitch_unleashed.h"\n',
    '#include "common/moonwitch_unleashed.h"\n#include "common/moonwitch_core_director.h"\n',
    '#include "common/moonwitch_core_director.h"',
    "include Core Director in shutdown",
)

replace_once(
    core_cpp,
    "        Common::MoonwitchUnleashed::EndSession();\n",
    "        Common::MoonwitchCoreDirector::EndSession();\n"
    "        Common::MoonwitchUnleashed::EndSession();\n",
    "MoonwitchCoreDirector::EndSession();",
    "restore affinity during game shutdown",
)

print("Applied Moonwitch Core Director native Snapdragon affinity controller.")
