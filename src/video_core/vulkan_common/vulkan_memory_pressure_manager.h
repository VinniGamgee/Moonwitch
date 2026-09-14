// SPDX-FileCopyrightText: Copyright 2026 Moonwitch Contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#include <algorithm>
#include <mutex>
#include <vector>

#include "common/common_types.h"
#include "video_core/vulkan_common/vma.h"

namespace Vulkan {

/// Tracks Vulkan/VMA heap pressure and adapts allocation strategy before the
/// allocator reaches a hard budget failure. This never changes render
/// resolution or resource lifetime.
class MemoryPressureManager {
public:
    enum class State {
        Normal,
        Elevated,
        Critical,
    };

    MemoryPressureManager(VmaAllocator allocator_,
                          const VkPhysicalDeviceMemoryProperties& properties_)
        : allocator{allocator_}, properties{properties_} {}

    MemoryPressureManager(const MemoryPressureManager&) = delete;
    MemoryPressureManager& operator=(const MemoryPressureManager&) = delete;

    void Refresh() {
        std::scoped_lock lock{mutex};
        ++allocation_count;
        if (++allocations_since_sample < kSampleEveryAllocations) {
            return;
        }
        allocations_since_sample = 0;
        SampleLocked();
    }

    [[nodiscard]] State GetState() const {
        std::scoped_lock lock{mutex};
        return state;
    }

    [[nodiscard]] VmaAllocationCreateFlags AllocationFlags() const {
        std::scoped_lock lock{mutex};
        if (state == State::Critical) {
            return VMA_ALLOCATION_CREATE_STRATEGY_MIN_MEMORY_BIT;
        }
        return VMA_ALLOCATION_CREATE_STRATEGY_MIN_TIME_BIT;
    }

    [[nodiscard]] u64 AllocationCount() const {
        std::scoped_lock lock{mutex};
        return allocation_count;
    }

    [[nodiscard]] VkDeviceSize PeakUsage() const {
        std::scoped_lock lock{mutex};
        return peak_usage;
    }

private:
    static constexpr u32 kSampleEveryAllocations = 32;
    static constexpr double kElevatedThreshold = 0.82;
    static constexpr double kCriticalThreshold = 0.92;
    static constexpr double kRecoveryThreshold = 0.74;

    void SampleLocked() {
        std::vector<VmaBudget> budgets(properties.memoryHeapCount);
        vmaGetHeapBudgets(allocator, budgets.data());

        double worst_ratio = 0.0;
        VkDeviceSize current_usage = 0;
        for (u32 i = 0; i < properties.memoryHeapCount; ++i) {
            const VkDeviceSize usage = budgets[i].usage;
            VkDeviceSize budget = budgets[i].budget;
            if (budget == 0) {
                budget = properties.memoryHeaps[i].size;
            }
            if (budget == 0) {
                continue;
            }
            current_usage = std::max(current_usage, usage);
            worst_ratio = std::max(worst_ratio,
                                   static_cast<double>(usage) / static_cast<double>(budget));
        }

        peak_usage = std::max(peak_usage, current_usage);

        switch (state) {
        case State::Normal:
            if (worst_ratio >= kCriticalThreshold) {
                state = State::Critical;
            } else if (worst_ratio >= kElevatedThreshold) {
                state = State::Elevated;
            }
            break;
        case State::Elevated:
            if (worst_ratio >= kCriticalThreshold) {
                state = State::Critical;
            } else if (worst_ratio < kRecoveryThreshold) {
                state = State::Normal;
            }
            break;
        case State::Critical:
            if (worst_ratio < kRecoveryThreshold) {
                state = State::Normal;
            } else if (worst_ratio < kElevatedThreshold) {
                state = State::Elevated;
            }
            break;
        }
    }

    VmaAllocator allocator{};
    VkPhysicalDeviceMemoryProperties properties{};
    mutable std::mutex mutex;
    State state{State::Normal};
    u32 allocations_since_sample{};
    u64 allocation_count{};
    VkDeviceSize peak_usage{};
};

} // namespace Vulkan
