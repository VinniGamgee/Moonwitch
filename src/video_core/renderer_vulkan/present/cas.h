// SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
// SPDX-License-Identifier: GPL-3.0-or-later

#pragma once

#include <cstddef>
#include <vector>

#include "common/common_types.h"
#include "video_core/vulkan_common/vulkan_memory_allocator.h"
#include "video_core/vulkan_common/vulkan_wrapper.h"

namespace Vulkan {

class Device;
class Scheduler;

class CAS final {
public:
    explicit CAS(const Device& device, MemoryAllocator& allocator, size_t image_count, VkExtent2D extent);
    ~CAS();

    VkImageView Draw(const Device& device, Scheduler& scheduler, size_t image_index,
                     VkImageView source_image_view);
    [[nodiscard]] bool NeedsRecreation(VkExtent2D extent) const;

private:
    void CreateImages(const Device& device, MemoryAllocator& allocator);
    void CreateRenderPasses(const Device& device);
    void CreateSampler(const Device& device);
    void CreateShaders(const Device& device);
    void CreateDescriptorPool(const Device& device);
    void CreateDescriptorSetLayout(const Device& device);
    void CreateDescriptorSets(const Device& device);
    void CreatePipelineLayout(const Device& device);
    void CreatePipeline(const Device& device);
    void UpdateDescriptorSet(const Device& device, VkImageView source_image_view, size_t image_index);
    void UploadImages(const Device& device, Scheduler& scheduler);

    struct Image {
        vk::DescriptorSets descriptor_sets{};
        vk::Framebuffer framebuffer{};
        vk::Image image{};
        vk::ImageView image_view{};
    };

    std::vector<Image> m_images{};
    VkExtent2D m_extent{};
    u32 m_image_count{};
    vk::ShaderModule m_vertex_shader{};
    vk::ShaderModule m_fragment_shader{};
    vk::DescriptorPool m_descriptor_pool{};
    vk::DescriptorSetLayout m_descriptor_set_layout{};
    vk::PipelineLayout m_pipeline_layout{};
    vk::Pipeline m_pipeline{};
    vk::RenderPass m_renderpass{};
    vk::Sampler m_sampler{};
    bool m_images_ready{};
};

} // namespace Vulkan
