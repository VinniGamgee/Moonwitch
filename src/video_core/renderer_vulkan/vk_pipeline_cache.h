// SPDX-FileCopyrightText: Copyright 2026 Eden Emulator Project
// SPDX-License-Identifier: GPL-3.0-or-later

// SPDX-FileCopyrightText: Copyright 2019 yuzu Emulator Project
// SPDX-License-Identifier: GPL-2.0-or-later

#pragma once

#include <array>
#include <atomic>
#include <chrono>
#include <cstddef>
#include <filesystem>
#include <memory>
#include <type_traits>
#include <vector>

#include "common/common_types.h"
#include "common/container/unordered_map.h"
#include "common/thread_worker.h"
#include "shader_recompiler/frontend/ir/basic_block.h"
#include "shader_recompiler/frontend/ir/value.h"
#include "shader_recompiler/frontend/maxwell/control_flow.h"
#include "shader_recompiler/host_translate_info.h"
#include "shader_recompiler/object_pool.h"
#include "shader_recompiler/profile.h"
#include "video_core/engines/maxwell_3d.h"
#include "video_core/host1x/gpu_device_memory_manager.h"
#include "video_core/renderer_vulkan/fixed_pipeline_state.h"
#include "video_core/renderer_vulkan/vk_buffer_cache.h"
#include "video_core/renderer_vulkan/vk_compute_pipeline.h"
#include "video_core/renderer_vulkan/vk_graphics_pipeline.h"
#include "video_core/renderer_vulkan/vk_texture_cache.h"
#include "video_core/shader_cache.h"

namespace Core {
class System;
}

namespace Shader::IR {
struct Program;
}

namespace VideoCore {
class ShaderNotify;
}

namespace Vulkan {

using Maxwell = Tegra::Engines::Maxwell3D::Regs;

struct ComputePipelineCacheKey {
    u64 unique_hash;
    u32 shared_memory_size;
    std::array<u32, 3> workgroup_size;

    size_t Hash() const noexcept;

    bool operator==(const ComputePipelineCacheKey& rhs) const noexcept;

    bool operator!=(const ComputePipelineCacheKey& rhs) const noexcept {
        return !operator==(rhs);
    }
};
static_assert(std::has_unique_object_representations_v<ComputePipelineCacheKey>);
static_assert(std::is_trivially_copyable_v<ComputePipelineCacheKey>);
static_assert(std::is_trivially_constructible_v<ComputePipelineCacheKey>);

} // namespace Vulkan

namespace std {

template <>
struct hash<Vulkan::ComputePipelineCacheKey> {
    size_t operator()(const Vulkan::ComputePipelineCacheKey& k) const noexcept {
        return k.Hash();
    }
};

} // namespace std

namespace Vulkan {

class ComputePipeline;
class DescriptorPool;
class Device;
class PipelineStatistics;
class RenderPassCache;
class Scheduler;

using VideoCommon::ShaderInfo;

struct ShaderPools {
    void ReleaseContents() {
        flow_block.ReleaseContents();
        block.ReleaseContents();
        inst.ReleaseContents();
    }

    Shader::ObjectPool<Shader::IR::Inst> inst{8192};
    Shader::ObjectPool<Shader::IR::Block> block{32};
    Shader::ObjectPool<Shader::Maxwell::Flow::Block> flow_block{32};
};

struct PipelineBuildMetricsSnapshot {
    u64 cache_hits{};
    u64 cache_misses{};
    u64 frontend_compiles{};
    u64 builds_queued{};
    u64 builds_completed{};
    u64 frontend_compile_ns{};
    u64 queue_wait_ns{};
    u64 driver_build_ns{};
};

// Low-overhead counters used to validate the Smart Shader Pipeline scheduler without exposing a
// user-facing setting or adding work to the renderer's per-draw fast path.
class PipelineBuildMonitor {
public:
    void RecordCacheHit() noexcept {
        cache_hits.fetch_add(1, std::memory_order_relaxed);
    }

    void RecordCacheMiss() noexcept {
        cache_misses.fetch_add(1, std::memory_order_relaxed);
    }

    void RecordFrontendCompile(std::chrono::nanoseconds duration) noexcept {
        frontend_compiles.fetch_add(1, std::memory_order_relaxed);
        frontend_compile_ns.fetch_add(PositiveNanoseconds(duration), std::memory_order_relaxed);
    }

    void RecordBuildQueued() noexcept {
        builds_queued.fetch_add(1, std::memory_order_relaxed);
    }

    void RecordBuildComplete(std::chrono::nanoseconds queue_wait,
                             std::chrono::nanoseconds driver_build) noexcept {
        queue_wait_ns.fetch_add(PositiveNanoseconds(queue_wait), std::memory_order_relaxed);
        driver_build_ns.fetch_add(PositiveNanoseconds(driver_build), std::memory_order_relaxed);
        builds_completed.fetch_add(1, std::memory_order_release);
    }

    [[nodiscard]] PipelineBuildMetricsSnapshot Snapshot() const noexcept {
        return {
            .cache_hits = cache_hits.load(std::memory_order_relaxed),
            .cache_misses = cache_misses.load(std::memory_order_relaxed),
            .frontend_compiles = frontend_compiles.load(std::memory_order_relaxed),
            .builds_queued = builds_queued.load(std::memory_order_relaxed),
            .builds_completed = builds_completed.load(std::memory_order_acquire),
            .frontend_compile_ns = frontend_compile_ns.load(std::memory_order_relaxed),
            .queue_wait_ns = queue_wait_ns.load(std::memory_order_relaxed),
            .driver_build_ns = driver_build_ns.load(std::memory_order_relaxed),
        };
    }

private:
    static u64 PositiveNanoseconds(std::chrono::nanoseconds duration) noexcept {
        return duration.count() > 0 ? static_cast<u64>(duration.count()) : 0;
    }

    std::atomic<u64> cache_hits{};
    std::atomic<u64> cache_misses{};
    std::atomic<u64> frontend_compiles{};
    std::atomic<u64> builds_queued{};
    std::atomic<u64> builds_completed{};
    std::atomic<u64> frontend_compile_ns{};
    std::atomic<u64> queue_wait_ns{};
    std::atomic<u64> driver_build_ns{};
};

class PipelineCache : public VideoCommon::ShaderCache {
public:
    explicit PipelineCache(Tegra::MaxwellDeviceMemoryManager& device_memory_, const Device& device,
                           Scheduler& scheduler, DescriptorPool& descriptor_pool,
                           GuestDescriptorQueue& guest_descriptor_queue,
                           DescriptorBufferRing& descriptor_buffer_ring,
                           RenderPassCache& render_pass_cache, BufferCache& buffer_cache,
                           TextureCache& texture_cache, VideoCore::ShaderNotify& shader_notify_);
    ~PipelineCache();

    [[nodiscard]] GraphicsPipeline* CurrentGraphicsPipeline();

    [[nodiscard]] ComputePipeline* CurrentComputePipeline();

    void LoadDiskResources(u64 title_id, std::stop_token stop_loading,
                           const VideoCore::DiskResourceLoadCallback& callback);

private:
    [[nodiscard]] GraphicsPipeline* CurrentGraphicsPipelineSlowPath();

    [[nodiscard]] GraphicsPipeline* BuiltPipeline(GraphicsPipeline* pipeline) const noexcept;

    std::unique_ptr<GraphicsPipeline> CreateGraphicsPipeline();

    std::unique_ptr<GraphicsPipeline> CreateGraphicsPipeline(
        ShaderPools& pools, const GraphicsPipelineCacheKey& key,
        std::span<Shader::Environment* const> envs, PipelineStatistics* statistics,
        bool build_in_parallel);

    std::unique_ptr<ComputePipeline> CreateComputePipeline(const ComputePipelineCacheKey& key,
                                                           const ShaderInfo* shader);

    std::unique_ptr<ComputePipeline> CreateComputePipeline(ShaderPools& pools,
                                                           const ComputePipelineCacheKey& key,
                                                           Shader::Environment& env,
                                                           PipelineStatistics* statistics,
                                                           bool build_in_parallel);

    void SerializeVulkanPipelineCache(const std::filesystem::path& filename,
                                      const vk::PipelineCache& pipeline_cache, u32 cache_version);

    vk::PipelineCache LoadVulkanPipelineCache(const std::filesystem::path& filename,
                                              u32 expected_cache_version);

    void QueueVulkanPipelineCacheFlush();

    void RecordPipelineCacheResult(bool hit);

    void ReportPipelineBuildMetrics();

    const Device& device;
    Scheduler& scheduler;
    DescriptorPool& descriptor_pool;
    GuestDescriptorQueue& guest_descriptor_queue;
    DescriptorBufferRing& descriptor_buffer_ring;
    RenderPassCache& render_pass_cache;
    BufferCache& buffer_cache;
    TextureCache& texture_cache;
    VideoCore::ShaderNotify& shader_notify;
    bool use_asynchronous_shaders{};
    bool use_vulkan_pipeline_cache{};

    GraphicsPipelineCacheKey graphics_key{};
    GraphicsPipeline* current_pipeline{};
    ComputePipeline* current_compute_pipeline{};

    ::Common::unordered_map<ComputePipelineCacheKey, std::unique_ptr<ComputePipeline>> compute_cache;
    ::Common::unordered_map<GraphicsPipelineCacheKey, std::unique_ptr<GraphicsPipeline>> graphics_cache;

    ShaderPools main_pools;

    Shader::Profile profile;
    Shader::HostTranslateInfo host_info;

    std::filesystem::path pipeline_cache_filename;

    std::filesystem::path vulkan_pipeline_cache_filename;
    vk::PipelineCache vulkan_pipeline_cache;
    size_t pipelines_since_flush{};
    std::chrono::steady_clock::time_point last_flush{};
    std::atomic<size_t> last_cache_size{};
    std::atomic_bool flush_in_flight{};

    PipelineBuildMonitor pipeline_build_monitor;
    u64 next_pipeline_metrics_report{64};
    Common::ThreadWorker workers;
    Common::ThreadWorker serialization_thread;
    DynamicFeatures dynamic_features;
};

} // namespace Vulkan
