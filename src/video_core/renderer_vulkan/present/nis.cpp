// SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
// SPDX-License-Identifier: GPL-3.0-or-later

#include <algorithm>
#include <array>
#include <cmath>
#include <cstring>
#include <cstdint>
#include <span>
#include <vector>

#include "common/settings.h"
#include "video_core/host_shaders/nvidia_nis_comp_spv.h"
#include "video_core/renderer_vulkan/present/NIS_Config.h"
#include "video_core/renderer_vulkan/present/nis.h"
#include "video_core/renderer_vulkan/present/util.h"
#include "video_core/renderer_vulkan/vk_scheduler.h"
#include "video_core/renderer_vulkan/vk_shader_util.h"
#include "video_core/vulkan_common/vulkan_device.h"

namespace Vulkan {

namespace {

constexpr VkFormat NIS_OUTPUT_FORMAT = VK_FORMAT_R16G16B16A16_SFLOAT;
constexpr VkFormat NIS_COEFFICIENT_FORMAT = VK_FORMAT_R16G16B16A16_SFLOAT;
constexpr VkExtent2D NIS_COEFFICIENT_EXTENT{2, 64};
constexpr u32 NIS_BLOCK_WIDTH = 32;
constexpr u32 NIS_BLOCK_HEIGHT = 24;

u32 ClampViewportOrigin(float normalized, u32 extent) {
    if (extent == 0) {
        return 0;
    }
    const float pixel = std::floor(std::clamp(normalized, 0.0f, 1.0f) *
                                   static_cast<float>(extent));
    return static_cast<u32>(std::clamp(pixel, 0.0f, static_cast<float>(extent - 1)));
}

u32 ClampViewportEnd(float normalized, u32 extent) {
    const float pixel = std::ceil(std::clamp(normalized, 0.0f, 1.0f) *
                                  static_cast<float>(extent));
    return static_cast<u32>(std::clamp(pixel, 1.0f, static_cast<float>(extent)));
}

} // Anonymous namespace

NIS::NIS(const Device& device, MemoryAllocator& memory_allocator_, Scheduler& scheduler,
         size_t image_count_, VkExtent2D output_extent_)
    : memory_allocator{memory_allocator_}, image_count{image_count_}, output_extent{output_extent_} {
    CreateOutputImages(device);
    CreateCoefficientImages(device, scheduler);
    CreateConfigBuffers();
    CreateDescriptors(device);
    CreatePipeline(device);
    UpdateFixedDescriptors(device);
}

void NIS::CreateOutputImages(const Device& device) {
    output_images.resize(image_count);
    output_image_views.resize(image_count);
    output_initialized.resize(image_count, false);

    for (size_t i = 0; i < image_count; ++i) {
        output_images[i] =
            CreateWrappedImage(memory_allocator, output_extent, NIS_OUTPUT_FORMAT);
        output_image_views[i] =
            CreateWrappedImageView(device, output_images[i], NIS_OUTPUT_FORMAT);
    }
}

void NIS::CreateCoefficientImages(const Device& device, Scheduler& scheduler) {
    static_assert(sizeof(coef_scale_fp16) == 64 * 8 * sizeof(std::uint16_t));
    static_assert(sizeof(coef_usm_fp16) == 64 * 8 * sizeof(std::uint16_t));

    scaler_coeff_image =
        CreateWrappedImage(memory_allocator, NIS_COEFFICIENT_EXTENT, NIS_COEFFICIENT_FORMAT);
    usm_coeff_image =
        CreateWrappedImage(memory_allocator, NIS_COEFFICIENT_EXTENT, NIS_COEFFICIENT_FORMAT);
    scaler_coeff_view =
        CreateWrappedImageView(device, scaler_coeff_image, NIS_COEFFICIENT_FORMAT);
    usm_coeff_view = CreateWrappedImageView(device, usm_coeff_image, NIS_COEFFICIENT_FORMAT);

    const auto scaler_bytes = std::span<const u8>{
        reinterpret_cast<const u8*>(coef_scale_fp16), sizeof(coef_scale_fp16)};
    const auto usm_bytes = std::span<const u8>{
        reinterpret_cast<const u8*>(coef_usm_fp16), sizeof(coef_usm_fp16)};

    UploadImage(device, memory_allocator, scheduler, scaler_coeff_image, NIS_COEFFICIENT_EXTENT,
                NIS_COEFFICIENT_FORMAT, scaler_bytes);
    UploadImage(device, memory_allocator, scheduler, usm_coeff_image, NIS_COEFFICIENT_EXTENT,
                NIS_COEFFICIENT_FORMAT, usm_bytes);

    sampler = CreateBilinearSampler(device);
}

void NIS::CreateConfigBuffers() {
    config_buffers.reserve(image_count);
    for (size_t i = 0; i < image_count; ++i) {
        const VkBufferCreateInfo buffer_ci{
            .sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO,
            .pNext = nullptr,
            .flags = 0,
            .size = sizeof(NISConfig),
            .usage = VK_BUFFER_USAGE_UNIFORM_BUFFER_BIT,
            .sharingMode = VK_SHARING_MODE_EXCLUSIVE,
            .queueFamilyIndexCount = 0,
            .pQueueFamilyIndices = nullptr,
        };
        config_buffers.emplace_back(memory_allocator.CreateBuffer(buffer_ci, MemoryUsage::Upload));
    }
}

void NIS::CreateDescriptors(const Device& device) {
    const std::array<VkDescriptorPoolSize, 4> pool_sizes{{
        {VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER, static_cast<u32>(image_count)},
        {VK_DESCRIPTOR_TYPE_SAMPLER, static_cast<u32>(image_count)},
        {VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE, static_cast<u32>(image_count * 3)},
        {VK_DESCRIPTOR_TYPE_STORAGE_IMAGE, static_cast<u32>(image_count)},
    }};
    descriptor_pool = device.GetLogical().CreateDescriptorPool(VkDescriptorPoolCreateInfo{
        .sType = VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO,
        .pNext = nullptr,
        .flags = 0,
        .maxSets = static_cast<u32>(image_count),
        .poolSizeCount = static_cast<u32>(pool_sizes.size()),
        .pPoolSizes = pool_sizes.data(),
    });

    const std::array<VkDescriptorType, 6> descriptor_types{
        VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER,
        VK_DESCRIPTOR_TYPE_SAMPLER,
        VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE,
        VK_DESCRIPTOR_TYPE_STORAGE_IMAGE,
        VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE,
        VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE,
    };
    descriptor_set_layout = CreateWrappedDescriptorSetLayout(
        device, std::span<const VkDescriptorType>{descriptor_types.data(), descriptor_types.size()},
        VK_SHADER_STAGE_COMPUTE_BIT);

    const std::vector<VkDescriptorSetLayout> layouts(image_count, *descriptor_set_layout);
    descriptor_sets = CreateWrappedDescriptorSets(descriptor_pool, layouts);
}

void NIS::CreatePipeline(const Device& device) {
    pipeline_layout = CreateWrappedPipelineLayout(device, descriptor_set_layout);
    shader = BuildShader(device, NVIDIA_NIS_COMP_SPV);
    pipeline = CreateWrappedComputePipeline(device, pipeline_layout, *shader);
}

void NIS::UpdateFixedDescriptors(const Device& device) {
    for (size_t i = 0; i < image_count; ++i) {
        const VkDescriptorBufferInfo config_info{
            .buffer = *config_buffers[i],
            .offset = 0,
            .range = sizeof(NISConfig),
        };
        const VkDescriptorImageInfo sampler_info{
            .sampler = *sampler,
            .imageView = VK_NULL_HANDLE,
            .imageLayout = VK_IMAGE_LAYOUT_UNDEFINED,
        };
        const VkDescriptorImageInfo output_info{
            .sampler = VK_NULL_HANDLE,
            .imageView = *output_image_views[i],
            .imageLayout = VK_IMAGE_LAYOUT_GENERAL,
        };
        const VkDescriptorImageInfo scaler_info{
            .sampler = VK_NULL_HANDLE,
            .imageView = *scaler_coeff_view,
            .imageLayout = VK_IMAGE_LAYOUT_GENERAL,
        };
        const VkDescriptorImageInfo usm_info{
            .sampler = VK_NULL_HANDLE,
            .imageView = *usm_coeff_view,
            .imageLayout = VK_IMAGE_LAYOUT_GENERAL,
        };

        const std::array<VkWriteDescriptorSet, 5> writes{{
            {
                .sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET,
                .pNext = nullptr,
                .dstSet = descriptor_sets[i],
                .dstBinding = 0,
                .dstArrayElement = 0,
                .descriptorCount = 1,
                .descriptorType = VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER,
                .pImageInfo = nullptr,
                .pBufferInfo = &config_info,
                .pTexelBufferView = nullptr,
            },
            {
                .sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET,
                .pNext = nullptr,
                .dstSet = descriptor_sets[i],
                .dstBinding = 1,
                .dstArrayElement = 0,
                .descriptorCount = 1,
                .descriptorType = VK_DESCRIPTOR_TYPE_SAMPLER,
                .pImageInfo = &sampler_info,
                .pBufferInfo = nullptr,
                .pTexelBufferView = nullptr,
            },
            {
                .sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET,
                .pNext = nullptr,
                .dstSet = descriptor_sets[i],
                .dstBinding = 3,
                .dstArrayElement = 0,
                .descriptorCount = 1,
                .descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_IMAGE,
                .pImageInfo = &output_info,
                .pBufferInfo = nullptr,
                .pTexelBufferView = nullptr,
            },
            {
                .sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET,
                .pNext = nullptr,
                .dstSet = descriptor_sets[i],
                .dstBinding = 4,
                .dstArrayElement = 0,
                .descriptorCount = 1,
                .descriptorType = VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE,
                .pImageInfo = &scaler_info,
                .pBufferInfo = nullptr,
                .pTexelBufferView = nullptr,
            },
            {
                .sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET,
                .pNext = nullptr,
                .dstSet = descriptor_sets[i],
                .dstBinding = 5,
                .dstArrayElement = 0,
                .descriptorCount = 1,
                .descriptorType = VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE,
                .pImageInfo = &usm_info,
                .pBufferInfo = nullptr,
                .pTexelBufferView = nullptr,
            },
        }};
        device.GetLogical().UpdateDescriptorSets(writes, {});
    }
}

void NIS::UpdateInputDescriptor(const Device& device, size_t image_index,
                                VkImageView source_image_view) {
    const VkDescriptorImageInfo input_info{
        .sampler = VK_NULL_HANDLE,
        .imageView = source_image_view,
        .imageLayout = VK_IMAGE_LAYOUT_GENERAL,
    };
    const VkWriteDescriptorSet write{
        .sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET,
        .pNext = nullptr,
        .dstSet = descriptor_sets[image_index],
        .dstBinding = 2,
        .dstArrayElement = 0,
        .descriptorCount = 1,
        .descriptorType = VK_DESCRIPTOR_TYPE_SAMPLED_IMAGE,
        .pImageInfo = &input_info,
        .pBufferInfo = nullptr,
        .pTexelBufferView = nullptr,
    };
    device.GetLogical().UpdateDescriptorSets(std::array{write}, {});
}

std::optional<VkImageView> NIS::Draw(
    const Device& device, Scheduler& scheduler, size_t image_index, VkImage source_image,
    VkImageView source_image_view, VkExtent2D input_image_extent,
    const Common::Rectangle<f32>& crop_rect) {
    if (image_index >= image_count || input_image_extent.width == 0 ||
        input_image_extent.height == 0 || output_extent.width == 0 || output_extent.height == 0) {
        return std::nullopt;
    }

    const float left = (std::min)(crop_rect.left, crop_rect.right);
    const float right = (std::max)(crop_rect.left, crop_rect.right);
    const float top = (std::min)(crop_rect.top, crop_rect.bottom);
    const float bottom = (std::max)(crop_rect.top, crop_rect.bottom);

    const u32 input_x = ClampViewportOrigin(left, input_image_extent.width);
    const u32 input_y = ClampViewportOrigin(top, input_image_extent.height);
    const u32 input_end_x = ClampViewportEnd(right, input_image_extent.width);
    const u32 input_end_y = ClampViewportEnd(bottom, input_image_extent.height);
    const u32 input_width = (std::max)(1U, input_end_x - input_x);
    const u32 input_height = (std::max)(1U, input_end_y - input_y);

    NISConfig config{};
    const float sharpness =
        std::clamp(static_cast<float>(Settings::values.nis_sharpening_slider.GetValue()) / 100.0f,
                   0.0f, 1.0f);
    const bool valid_config = NVScalerUpdateConfig(
        config, sharpness, input_x, input_y, input_width, input_height, input_image_extent.width,
        input_image_extent.height, 0, 0, output_extent.width, output_extent.height,
        output_extent.width, output_extent.height, NISHDRMode::None);
    if (!valid_config) {
        // NVIDIA NIS supports source/output scale ratios from 0.5 to 1.0 per axis.
        // Fall back to Moonwitch's normal presentation instead of pretending NIS ran.
        return std::nullopt;
    }

    auto mapped = config_buffers[image_index].Mapped();
    std::memcpy(mapped.data(), &config, sizeof(config));
    config_buffers[image_index].Flush();
    UpdateInputDescriptor(device, image_index, source_image_view);

    const VkImage output_image = *output_images[image_index];
    const VkImageView output_view = *output_image_views[image_index];
    const VkDescriptorSet descriptor_set = descriptor_sets[image_index];
    const VkPipeline compute_pipeline = *pipeline;
    const VkPipelineLayout layout = *pipeline_layout;
    const bool was_initialized = output_initialized[image_index];
    output_initialized[image_index] = true;

    const u32 dispatch_x = (output_extent.width + NIS_BLOCK_WIDTH - 1) / NIS_BLOCK_WIDTH;
    const u32 dispatch_y = (output_extent.height + NIS_BLOCK_HEIGHT - 1) / NIS_BLOCK_HEIGHT;

    scheduler.RequestOutsideRenderPassOperationContext();
    scheduler.Record([=](vk::CommandBuffer cmdbuf) {
        const VkImageMemoryBarrier source_barrier{
            .sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER,
            .pNext = nullptr,
            .srcAccessMask = VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT | VK_ACCESS_SHADER_WRITE_BIT |
                             VK_ACCESS_TRANSFER_WRITE_BIT | VK_ACCESS_MEMORY_WRITE_BIT,
            .dstAccessMask = VK_ACCESS_SHADER_READ_BIT,
            .oldLayout = VK_IMAGE_LAYOUT_GENERAL,
            .newLayout = VK_IMAGE_LAYOUT_GENERAL,
            .srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
            .dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
            .image = source_image,
            .subresourceRange{
                .aspectMask = VK_IMAGE_ASPECT_COLOR_BIT,
                .baseMipLevel = 0,
                .levelCount = 1,
                .baseArrayLayer = 0,
                .layerCount = 1,
            },
        };
        cmdbuf.PipelineBarrier(vk::PIPELINE_STAGE_GRAPHICS_COMPUTE_TRANSFER,
                               VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT, 0, source_barrier);

        const VkImageMemoryBarrier output_write_barrier{
            .sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER,
            .pNext = nullptr,
            .srcAccessMask = was_initialized ? VK_ACCESS_SHADER_READ_BIT : 0U,
            .dstAccessMask = VK_ACCESS_SHADER_WRITE_BIT,
            .oldLayout = was_initialized ? VK_IMAGE_LAYOUT_GENERAL : VK_IMAGE_LAYOUT_UNDEFINED,
            .newLayout = VK_IMAGE_LAYOUT_GENERAL,
            .srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
            .dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
            .image = output_image,
            .subresourceRange{
                .aspectMask = VK_IMAGE_ASPECT_COLOR_BIT,
                .baseMipLevel = 0,
                .levelCount = 1,
                .baseArrayLayer = 0,
                .layerCount = 1,
            },
        };
        cmdbuf.PipelineBarrier(vk::PIPELINE_STAGE_GRAPHICS_COMPUTE,
                               VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT, 0, output_write_barrier);

        cmdbuf.BindPipeline(VK_PIPELINE_BIND_POINT_COMPUTE, compute_pipeline);
        cmdbuf.BindDescriptorSets(VK_PIPELINE_BIND_POINT_COMPUTE, layout, 0, descriptor_set, {});
        cmdbuf.Dispatch(dispatch_x, dispatch_y, 1);

        const VkImageMemoryBarrier output_read_barrier{
            .sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER,
            .pNext = nullptr,
            .srcAccessMask = VK_ACCESS_SHADER_WRITE_BIT,
            .dstAccessMask = VK_ACCESS_SHADER_READ_BIT,
            .oldLayout = VK_IMAGE_LAYOUT_GENERAL,
            .newLayout = VK_IMAGE_LAYOUT_GENERAL,
            .srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
            .dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
            .image = output_image,
            .subresourceRange{
                .aspectMask = VK_IMAGE_ASPECT_COLOR_BIT,
                .baseMipLevel = 0,
                .levelCount = 1,
                .baseArrayLayer = 0,
                .layerCount = 1,
            },
        };
        cmdbuf.PipelineBarrier(VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,
                               vk::PIPELINE_STAGE_GRAPHICS_COMPUTE, 0, output_read_barrier);
    });

    return output_view;
}

} // namespace Vulkan
