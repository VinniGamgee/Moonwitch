// SPDX-FileCopyrightText: Copyright 2026 Moonwitch Contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#include "video_core/vulkan_common/vulkan_memory_pressure_manager.h"

#include <algorithm>
#include <limits>

namespace Vulkan {
namespace {

constexpr u32 kSampleEveryAllocations = 32;
constexpr double kElevatedThreshold = 0.82;
constexpr double kCriticalThreshold = 0.92;
constexpr double kRecoveryThreshold = 0.74;

} // namespace

MemoryPressureManager::MemoryPressureManager(
    VmaAllocator allocator_, const VkPhysicalDeviceMemoryProperties& properties_)
    : allocator{allocator_}, properties{properties_} {}

void MemoryPressureManager::Refresh() {
    std::scoped_lock lock{mutex};
    ++allocation_count;
    if (++allocations_since_sample < kSampleEveryAllocations) {
        return;
    }
    allocations_since_sample = 0;
    SampleLocked();
}

void MemoryPressureManager::SampleLocked() {
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

    // Hysteresis prevents the allocator from bouncing between strategies when
    // usage hovers around a threshold.
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

MemoryPressureManager::State MemoryPressureManager::GetState() const {
    std::scoped_lock lock{mutex};
    return state;
}

VmaAllocationCreateFlags MemoryPressureManager::AllocationFlags() const {
    std::scoped_lock lock{mutex};
    if (state == State::Critical) {
        return VMA_ALLOCATION_CREATE_STRATEGY_MIN_MEMORY_BIT;
    }
    return VMA_ALLOCATION_CREATE_STRATEGY_MIN_TIME_BIT;
}

u64 MemoryPressureManager::AllocationCount() const {
    std::scoped_lock lock{mutex};
    return allocation_count;
}

VkDeviceSize MemoryPressureManager::PeakUsage() const {
    std::scoped_lock lock{mutex};
    return peak_usage;
}

} // namespace Vulkan
