// SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#include <optional>
#include <vector>

#include "common/math_util.h"
#include "video_core/vulkan_common/vulkan_memory_allocator.h"
#include "video_core/vulkan_common/vulkan_wrapper.h"

namespace Vulkan {

class Device;
class Scheduler;

class NIS {
public:
    NIS(const Device& device, MemoryAllocator& memory_allocator, Scheduler& scheduler,
        size_t image_count, VkExtent2D output_extent);

    NIS(const NIS&) = delete;
    NIS& operator=(const NIS&) = delete;
    NIS(NIS&&) noexcept = default;
    NIS& operator=(NIS&&) noexcept = delete;

    [[nodiscard]] std::optional<VkImageView> Draw(
        const Device& device, Scheduler& scheduler, size_t image_index, VkImage source_image,
        VkImageView source_image_view, VkExtent2D input_image_extent,
        const Common::Rectangle<f32>& crop_rect);

private:
    void CreateOutputImages(const Device& device);
    void CreateCoefficientImages(const Device& device, Scheduler& scheduler);
    void CreateConfigBuffers();
    void CreateDescriptors(const Device& device);
    void CreatePipeline(const Device& device);
    void UpdateFixedDescriptors(const Device& device);
    void UpdateInputDescriptor(const Device& device, size_t image_index,
                               VkImageView source_image_view);

    MemoryAllocator& memory_allocator;
    const size_t image_count;
    const VkExtent2D output_extent;

    std::vector<vk::Image> output_images;
    std::vector<vk::ImageView> output_image_views;
    std::vector<vk::Buffer> config_buffers;
    std::vector<bool> output_initialized;

    vk::Image scaler_coeff_image;
    vk::Image usm_coeff_image;
    vk::ImageView scaler_coeff_view;
    vk::ImageView usm_coeff_view;
    vk::Sampler sampler;

    vk::DescriptorPool descriptor_pool;
    vk::DescriptorSetLayout descriptor_set_layout;
    vk::DescriptorSets descriptor_sets;
    vk::PipelineLayout pipeline_layout;
    vk::ShaderModule shader;
    vk::Pipeline pipeline;
};

} // namespace Vulkan
