// SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
// SPDX-License-Identifier: GPL-3.0-or-later

#include <algorithm>
#include <tuple>
#include <vector>

#include "common/moonwitch_cas_settings.h"
#include "video_core/host_shaders/vulkan_fidelityfx_cas_frag_spv.h"
#include "video_core/host_shaders/vulkan_fidelityfx_fsr_vert_spv.h"
#include "video_core/renderer_vulkan/present/cas.h"
#include "video_core/renderer_vulkan/present/util.h"
#include "video_core/renderer_vulkan/vk_scheduler.h"
#include "video_core/vulkan_common/vulkan_device.h"

namespace Vulkan {

struct CasPushConstants {
    float sharpness;
};

CAS::CAS(const Device& device, MemoryAllocator& allocator, size_t image_count, VkExtent2D extent)
    : m_extent{extent}, m_image_count{static_cast<u32>(image_count)} {
    CreateImages(device, allocator);
    CreateRenderPasses(device);
    CreateSampler(device);
    CreateShaders(device);
    CreateDescriptorPool(device);
    CreateDescriptorSetLayout(device);
    CreateDescriptorSets(device);
    CreatePipelineLayout(device);
    CreatePipeline(device);
}

CAS::~CAS() = default;

void CAS::CreateImages(const Device& device, MemoryAllocator& allocator) {
    m_images.resize(m_image_count);
    for (auto& image : m_images) {
        image.image = CreateWrappedImage(allocator, m_extent, VK_FORMAT_R16G16B16A16_SFLOAT);
        image.image_view =
            CreateWrappedImageView(device, image.image, VK_FORMAT_R16G16B16A16_SFLOAT);
    }
}

void CAS::CreateRenderPasses(const Device& device) {
    m_renderpass = CreateWrappedRenderPass(device, VK_FORMAT_R16G16B16A16_SFLOAT);
    for (auto& image : m_images) {
        image.framebuffer =
            CreateWrappedFramebuffer(device, m_renderpass, image.image_view, m_extent);
    }
}

void CAS::CreateSampler(const Device& device) {
    m_sampler = CreateNearestNeighborSampler(device);
}

void CAS::CreateShaders(const Device& device) {
    m_vertex_shader = CreateWrappedShaderModule(device, VULKAN_FIDELITYFX_FSR_VERT_SPV);
    m_fragment_shader = CreateWrappedShaderModule(device, VULKAN_FIDELITYFX_CAS_FRAG_SPV);
}

void CAS::CreateDescriptorPool(const Device& device) {
    m_descriptor_pool = CreateWrappedDescriptorPool(device, m_image_count, m_image_count);
}

void CAS::CreateDescriptorSetLayout(const Device& device) {
    m_descriptor_set_layout =
        CreateWrappedDescriptorSetLayout(device, {VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER});
}

void CAS::CreateDescriptorSets(const Device& device) {
    (void)device;
    const VkDescriptorSetLayout layout = *m_descriptor_set_layout;
    for (auto& image : m_images) {
        image.descriptor_sets = CreateWrappedDescriptorSets(m_descriptor_pool, {layout});
    }
}

void CAS::CreatePipelineLayout(const Device& device) {
    const VkPushConstantRange range{
        .stageFlags = VK_SHADER_STAGE_FRAGMENT_BIT,
        .offset = 0,
        .size = sizeof(CasPushConstants),
    };
    const VkPipelineLayoutCreateInfo ci{
        .sType = VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO,
        .pNext = nullptr,
        .flags = 0,
        .setLayoutCount = 1,
        .pSetLayouts = m_descriptor_set_layout.address(),
        .pushConstantRangeCount = 1,
        .pPushConstantRanges = &range,
    };
    m_pipeline_layout = device.GetLogical().CreatePipelineLayout(ci);
}

void CAS::CreatePipeline(const Device& device) {
    m_pipeline = CreateWrappedPipeline(device, m_renderpass, m_pipeline_layout,
                                       std::tie(m_vertex_shader, m_fragment_shader));
}

void CAS::UpdateDescriptorSet(const Device& device, VkImageView source_image_view,
                              size_t image_index) {
    auto& image = m_images[image_index];
    std::vector<VkDescriptorImageInfo> image_infos;
    image_infos.reserve(1);
    std::vector<VkWriteDescriptorSet> updates{CreateWriteDescriptorSet(
        image_infos, *m_sampler, source_image_view, image.descriptor_sets[0], 0)};
    device.GetLogical().UpdateDescriptorSets(updates, {});
}

void CAS::UploadImages(const Device& device, Scheduler& scheduler) {
    if (m_images_ready) {
        return;
    }
    scheduler.Record([&](vk::CommandBuffer cmdbuf) {
        for (auto& image : m_images) {
            ClearColorImage(cmdbuf, *image.image);
        }
    });
    scheduler.Finish();
    m_images_ready = true;
}

VkImageView CAS::Draw(const Device& device, Scheduler& scheduler, size_t image_index,
                      VkImageView source_image_view) {
    auto& image = m_images[image_index];
    const float sharpness = std::clamp(static_cast<float>(Settings::GetCasSharpness()) / 100.0f,
                                       0.0f, 1.0f);
    const CasPushConstants push_constants{.sharpness = sharpness};

    UploadImages(device, scheduler);
    UpdateDescriptorSet(device, source_image_view, image_index);

    const VkImage output_image = *image.image;
    const VkFramebuffer framebuffer = *image.framebuffer;
    const VkRenderPass renderpass = *m_renderpass;
    const VkPipeline pipeline = *m_pipeline;
    const VkPipelineLayout layout = *m_pipeline_layout;
    const VkDescriptorSet descriptor_set = image.descriptor_sets[0];
    const VkExtent2D extent = m_extent;

    scheduler.RequestOutsideRenderPassOperationContext();
    scheduler.Record([=](vk::CommandBuffer cmdbuf) {
        TransitionImageLayout(cmdbuf, output_image, VK_IMAGE_LAYOUT_GENERAL);
        BeginRenderPass(cmdbuf, renderpass, framebuffer, extent);
        cmdbuf.BindPipeline(VK_PIPELINE_BIND_POINT_GRAPHICS, pipeline);
        cmdbuf.BindDescriptorSets(VK_PIPELINE_BIND_POINT_GRAPHICS, layout, 0, descriptor_set, {});
        cmdbuf.PushConstants(layout, VK_SHADER_STAGE_FRAGMENT_BIT, push_constants);
        cmdbuf.Draw(3, 1, 0, 0);
        cmdbuf.EndRenderPass();
        TransitionImageLayout(cmdbuf, output_image, VK_IMAGE_LAYOUT_GENERAL);
    });

    return *image.image_view;
}

bool CAS::NeedsRecreation(VkExtent2D extent) const {
    return extent.width != m_extent.width || extent.height != m_extent.height;
}

} // namespace Vulkan
