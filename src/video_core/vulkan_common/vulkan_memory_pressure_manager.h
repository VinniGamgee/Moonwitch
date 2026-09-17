// SPDX-FileCopyrightText: Copyright 2026 Moonwitch Contributors
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#include <array>
#include <mutex>

#include "common/common_types.h"
#include "video_core/vulkan_common/vma.h"

namespace Vulkan {

/// Tracks Vulkan/VMA heap pressure and adapts allocation strategy before the
/// allocator reaches a hard budget failure. This intentionally never changes
/// render resolution or resource lifetime.
class MemoryPressureManager {
public:
    enum class State {
        Normal,
        Elevated,
        Critical,
    };

    MemoryPressureManager(VmaAllocator allocator,
                          const VkPhysicalDeviceMemoryProperties& properties);

    MemoryPressureManager(const MemoryPressureManager&) = delete;
    MemoryPressureManager& operator=(const MemoryPressureManager&) = delete;

    /// Samples heap budgets at a bounded cadence. Cheap no-op between samples.
    void Refresh();

    [[nodiscard]] State GetState() const;

    /// Returns VMA allocation strategy flags appropriate for current pressure.
    [[nodiscard]] VmaAllocationCreateFlags AllocationFlags() const;

    [[nodiscard]] u64 AllocationCount() const;
    [[nodiscard]] VkDeviceSize PeakUsage() const;

private:
    void SampleLocked();

    VmaAllocator allocator{};
    VkPhysicalDeviceMemoryProperties properties{};

    mutable std::mutex mutex;
    State state{State::Normal};
    u32 allocations_since_sample{};
    u64 allocation_count{};
    VkDeviceSize peak_usage{};
};

} // namespace Vulkan
