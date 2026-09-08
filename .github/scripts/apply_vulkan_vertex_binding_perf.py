#!/usr/bin/env python3
from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match in {path}, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_in_function(path: Path, start_marker: str, end_marker: str,
                        old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    start = text.find(start_marker)
    if start < 0:
        raise SystemExit(f"{label}: function start not found in {path}")
    end = text.find(end_marker, start + len(start_marker))
    if end < 0:
        raise SystemExit(f"{label}: function end marker not found in {path}")
    region = text[start:end]
    if new in region:
        return
    count = region.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match in function, found {count}")
    patched = region.replace(old, new, 1)
    path.write_text(text[:start] + patched + text[end:], encoding="utf-8")


root = Path(__file__).resolve().parents[2]
buffer_h = root / "src/video_core/renderer_vulkan/vk_buffer_cache.h"
buffer_cpp = root / "src/video_core/renderer_vulkan/vk_buffer_cache.cpp"
graphics_h = root / "src/video_core/renderer_vulkan/vk_graphics_pipeline.h"
texture_h = root / "src/video_core/texture_cache/texture_cache.h"
texture_base_h = root / "src/video_core/texture_cache/texture_cache_base.h"

replace_once(
    buffer_h,
    "    void BindVertexBuffers(VideoCommon::HostBindings<Buffer>& bindings);\n\n"
    "    void BindTransformFeedbackBuffer(u32 index, VkBuffer buffer, u32 offset, u32 size);",
    "    void BindVertexBuffers(VideoCommon::HostBindings<Buffer>& bindings);\n\n"
    "    void SetVertexInputDynamicState(bool is_active) {\n"
    "        vertex_input_dynamic_state_active = is_active;\n"
    "    }\n\n"
    "    void BindTransformFeedbackBuffer(u32 index, VkBuffer buffer, u32 offset, u32 size);",
    "vertex-input setter",
)

replace_once(
    buffer_h,
    "    bool limit_dynamic_storage_buffers = false;\n"
    "    u32 max_dynamic_storage_buffers = (std::numeric_limits<u32>::max)();\n"
    "};",
    "    bool limit_dynamic_storage_buffers = false;\n"
    "    u32 max_dynamic_storage_buffers = (std::numeric_limits<u32>::max)();\n\n"
    "    bool vertex_input_dynamic_state_active = false;\n"
    "};",
    "vertex-input state flag",
)

replace_in_function(
    buffer_cpp,
    "void BufferCacheRuntime::BindVertexBuffer(",
    "void BufferCacheRuntime::BindVertexBuffers(",
    "    if (device.IsExtExtendedDynamicStateSupported()) {",
    "    if (device.IsExtExtendedDynamicStateSupported() && !vertex_input_dynamic_state_active) {",
    "single vertex-buffer bind",
)

replace_in_function(
    buffer_cpp,
    "void BufferCacheRuntime::BindVertexBuffers(",
    "void BufferCacheRuntime::BindTransformFeedbackBuffer(",
    "    if (device.IsExtExtendedDynamicStateSupported()) {",
    "    if (device.IsExtExtendedDynamicStateSupported() && !vertex_input_dynamic_state_active) {",
    "multi vertex-buffer bind",
)

replace_once(
    graphics_h,
    "    bool Configure(bool is_indexed) {\n"
    "        return configure_func(this, is_indexed);\n"
    "    }",
    "    bool Configure(bool is_indexed) {\n"
    "        buffer_cache.runtime.SetVertexInputDynamicState(HasDynamicVertexInput());\n"
    "        return configure_func(this, is_indexed);\n"
    "    }",
    "graphics pipeline dynamic vertex-input wiring",
)

# Texture-cache hot maps. Keep std::unordered_map entries that require stable iterators and
# keep ankerl available for the two small join-cache sets; only migrate lookup-heavy maps.
replace_once(
    texture_base_h,
    "#include <ankerl/unordered_dense.h>\n#include <vector>",
    "#include <ankerl/unordered_dense.h>\n#include \"common/container/unordered_map.h\"\n#include <vector>",
    "texture-cache flat-map include",
)
replace_once(
    texture_h,
    "#include <ankerl/unordered_dense.h>\n#include <boost/container/small_vector.hpp>",
    "#include <ankerl/unordered_dense.h>\n#include \"common/container/unordered_map.h\"\n#include <boost/container/small_vector.hpp>",
    "texture-cache impl flat-map include",
)

map_replacements = [
    (
        "using TextureCacheGPUMap = ankerl::unordered_dense::map<u64, std::vector<ImageId>, Common::IdentityHash<u64>>;",
        "using TextureCacheGPUMap = ::Common::unordered_map<u64, std::vector<ImageId>, Common::IdentityHash<u64>>;",
        "texture GPU page map",
    ),
    (
        "    ankerl::unordered_dense::map<u32, SamplerId> sampler_ids;",
        "    ::Common::unordered_map<u32, SamplerId> sampler_ids;",
        "sampler id map",
    ),
    (
        "    ankerl::unordered_dense::map<u32, ImageViewId> image_view_ids;",
        "    ::Common::unordered_map<u32, ImageViewId> image_view_ids;",
        "image-view id map",
    ),
    (
        "    ankerl::unordered_dense::map<RenderTargets, FramebufferId> framebuffers;",
        "    ::Common::unordered_map<RenderTargets, FramebufferId> framebuffers;",
        "framebuffer lookup map",
    ),
    (
        "    ankerl::unordered_dense::map<u64, std::vector<ImageMapId>, Common::IdentityHash<u64>> page_table;",
        "    ::Common::unordered_map<u64, std::vector<ImageMapId>, Common::IdentityHash<u64>> page_table;",
        "texture CPU page table",
    ),
    (
        "    ankerl::unordered_dense::map<ImageId, boost::container::small_vector<ImageViewId, 16>> sparse_views;",
        "    ::Common::unordered_map<ImageId, boost::container::small_vector<ImageViewId, 16>> sparse_views;",
        "sparse image-view map",
    ),
    (
        "    ankerl::unordered_dense::map<GPUVAddr, ImageAllocId> image_allocs_table;",
        "    ::Common::unordered_map<GPUVAddr, ImageAllocId> image_allocs_table;",
        "image allocation lookup map",
    ),
    (
        "    ankerl::unordered_dense::map<ImageId, size_t> join_alias_indices;",
        "    ::Common::unordered_map<ImageId, size_t> join_alias_indices;",
        "join alias index map",
    ),
]
for old, new, label in map_replacements:
    replace_once(texture_base_h, old, new, label)

replace_once(
    texture_h,
    "        [image_id](u64 page, ankerl::unordered_dense::map<u64, std::vector<ImageId>, Common::IdentityHash<u64>>& selected_page_table) {",
    "        [image_id](u64 page, ::Common::unordered_map<u64, std::vector<ImageId>, Common::IdentityHash<u64>>& selected_page_table) {",
    "texture page-table unregister callback",
)

print("Applied Vulkan vertex binding and texture-cache flat-map optimizations.")
