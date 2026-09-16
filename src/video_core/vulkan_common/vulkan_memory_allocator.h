// SPDX-FileCopyrightText: Copyright 2025 Eden Emulator Project
// SPDX-License-Identifier: GPL-3.0-or-later

// SPDX-FileCopyrightText: Copyright 2019 yuzu Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

#pragma once

#include <memory>
#include <span>
#include <vector>

#include "common/common_types.h"
#include "video_core/vulkan_common/vulkan_device.h"
#include "video_core/vulkan_common/vulkan_memory_pressure_manager.h"
#include "video_core/vulkan_common/vulkan_wrapper.h"
#include "video_core/vulkan_common/vma.h"

namespace Vulkan {

class Device;

enum class MemoryUsage {
    DeviceLocal,
    Upload,
    Download,
    Stream,
};

template<typename F>
void ForEachDeviceLocalHostVisibleHeap(const Device &device, F &&f) {
    auto memory_props = device.GetPhysical().GetMemoryProperties().memoryProperties;
    for (size_t i = 0; i < memory_props.memoryTypeCount; i++) {
        auto &memory_type = memory_props.memoryTypes[i];
        if ((memory_type.propertyFlags & VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT) &&
            (memory_type.propertyFlags & VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT)) {
            f(memory_type.heapIndex, memory_props.memoryHeaps[memory_type.heapIndex]);
        }
    }
}

class MemoryCommit {
public:
    MemoryCommit() noexcept = default;
    MemoryCommit(VmaAllocator allocator, VmaAllocation allocation,
                 const VmaAllocationInfo &info) noexcept;
    ~MemoryCommit();
    MemoryCommit(const MemoryCommit &) = delete;
    MemoryCommit &operator=(const MemoryCommit &) = delete;
    MemoryCommit(MemoryCommit &&) noexcept;
    MemoryCommit &operator=(MemoryCommit &&) noexcept;

    [[nodiscard]] std::span<u8> Map();
    [[nodiscard]] std::span<const u8> Map() const;
    void Unmap();
    explicit operator bool() const noexcept { return allocation != nullptr; }
    VkDeviceMemory Memory() const noexcept { return memory; }
    VkDeviceSize Offset() const noexcept { return offset; }
    VkDeviceSize Size() const noexcept { return size; }
    VmaAllocation Allocation() const noexcept { return allocation; }

private:
    void Release();
    VmaAllocator allocator{};
    VmaAllocation allocation{};
    VkDeviceMemory memory{};
    VkDeviceSize offset{};
    VkDeviceSize size{};
    void *mapped_ptr{};
};

class MemoryAllocator {
public:
    explicit MemoryAllocator(const Device &device_);
    ~MemoryAllocator();

    MemoryAllocator &operator=(const MemoryAllocator &) = delete;
    MemoryAllocator(const MemoryAllocator &) = delete;

    vk::Image CreateImage(const VkImageCreateInfo &ci) const;
    vk::Buffer CreateBuffer(const VkBufferCreateInfo &ci, MemoryUsage usage) const;

    MemoryCommit Commit(const VkMemoryRequirements &requirements, MemoryUsage usage);
    MemoryCommit Commit(const vk::Buffer &buffer, MemoryUsage usage);

private:
    static bool IsAutoUsage(VmaMemoryUsage u) noexcept {
        switch (u) {
            case VMA_MEMORY_USAGE_AUTO:
            case VMA_MEMORY_USAGE_AUTO_PREFER_DEVICE:
            case VMA_MEMORY_USAGE_AUTO_PREFER_HOST:
                return true;
            default:
                return false;
        }
    }

    const Device &device;
    VmaAllocator allocator;
    const VkPhysicalDeviceMemoryProperties properties;
    VkDeviceSize buffer_image_granularity;
    u32 valid_memory_types{~0u};
    mutable MemoryPressureManager pressure_manager;
};

} // namespace Vulkan
