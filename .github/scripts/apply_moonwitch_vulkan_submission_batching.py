#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path

TAG = "[moonwitch-vulkan-submission-batching]"


def replace_once(path: Path, old: str, new: str, marker: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if marker in text:
        print(f"{TAG} {label}: already patched")
        return
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one anchor for {label}, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"{TAG} {label}: patched")

root = Path(".")
scheduler_h = root / "src/video_core/renderer_vulkan/vk_scheduler.h"
scheduler_cpp = root / "src/video_core/renderer_vulkan/vk_scheduler.cpp"
master_h = root / "src/video_core/renderer_vulkan/vk_master_semaphore.h"
master_cpp = root / "src/video_core/renderer_vulkan/vk_master_semaphore.cpp"

replace_once(
    scheduler_h,
    '''    template <typename T>\n        requires std::is_invocable_v<T, vk::CommandBuffer, vk::CommandBuffer>\n    void RecordWithUploadBuffer(T&& command) {\n        if (chunk->Record(command)) {\n            return;\n        }\n        DispatchWork();\n        (void)chunk->Record(command);\n    }\n\n    template <typename T>\n        requires std::is_invocable_v<T, vk::CommandBuffer>\n    void Record(T&& c) {\n        this->RecordWithUploadBuffer(\n            [command = std::move(c)](vk::CommandBuffer cmdbuf, vk::CommandBuffer) {\n                command(cmdbuf);\n            });\n    }''',
    '''    template <typename T>\n        requires std::is_invocable_v<T, vk::CommandBuffer, vk::CommandBuffer>\n    void RecordWithUploadBuffer(T&& command) {\n        upload_work_pending = true;\n        if (chunk->Record(command)) {\n            return;\n        }\n        DispatchWork();\n        (void)chunk->Record(command);\n    }\n\n    template <typename T>\n        requires std::is_invocable_v<T, vk::CommandBuffer>\n    void Record(T&& c) {\n        auto command = [command = std::move(c)](vk::CommandBuffer cmdbuf, vk::CommandBuffer) {\n            command(cmdbuf);\n        };\n        if (chunk->Record(command)) {\n            return;\n        }\n        DispatchWork();\n        (void)chunk->Record(command);\n    }''',
    "upload_work_pending = true;",
    "track upload-only recording",
)

replace_once(
    scheduler_h,
    "    std::function<void()> on_submit;\n\n    State state;",
    "    std::function<void()> on_submit;\n    bool upload_work_pending{};\n\n    State state;",
    "bool upload_work_pending{};",
    "store upload submission state",
)

replace_once(
    master_h,
    '''    VkResult SubmitQueue(vk::CommandBuffer& cmdbuf, vk::CommandBuffer& upload_cmdbuf,\n                         VkSemaphore signal_semaphore, VkSemaphore wait_semaphore, u64 host_tick);''',
    '''    VkResult SubmitQueue(vk::CommandBuffer& cmdbuf, vk::CommandBuffer& upload_cmdbuf,\n                         VkSemaphore signal_semaphore, VkSemaphore wait_semaphore, u64 host_tick,\n                         bool has_upload_work);''',
    "bool has_upload_work);",
    "expose upload-aware queue submission",
)

replace_once(
    master_h,
    '''    VkResult SubmitQueueTimeline(vk::CommandBuffer& cmdbuf, vk::CommandBuffer& upload_cmdbuf,\n                                 VkSemaphore signal_semaphore, VkSemaphore wait_semaphore,\n                                 u64 host_tick);\n    VkResult SubmitQueueFence(vk::CommandBuffer& cmdbuf, vk::CommandBuffer& upload_cmdbuf,\n                              VkSemaphore signal_semaphore, VkSemaphore wait_semaphore,\n                              u64 host_tick);''',
    '''    VkResult SubmitQueueTimeline(vk::CommandBuffer& cmdbuf, vk::CommandBuffer& upload_cmdbuf,\n                                 VkSemaphore signal_semaphore, VkSemaphore wait_semaphore,\n                                 u64 host_tick, bool has_upload_work);\n    VkResult SubmitQueueFence(vk::CommandBuffer& cmdbuf, vk::CommandBuffer& upload_cmdbuf,\n                              VkSemaphore signal_semaphore, VkSemaphore wait_semaphore,\n                              u64 host_tick, bool has_upload_work);''',
    "u64 host_tick, bool has_upload_work);",
    "propagate upload state",
)

replace_once(
    master_cpp,
    '''VkResult MasterSemaphore::SubmitQueue(vk::CommandBuffer& cmdbuf, vk::CommandBuffer& upload_cmdbuf,\n                                      VkSemaphore signal_semaphore, VkSemaphore wait_semaphore,\n                                      u64 host_tick) {\n    if (semaphore) {\n        return SubmitQueueTimeline(cmdbuf, upload_cmdbuf, signal_semaphore, wait_semaphore,\n                                   host_tick);\n    } else {\n        return SubmitQueueFence(cmdbuf, upload_cmdbuf, signal_semaphore, wait_semaphore, host_tick);\n    }\n}''',
    '''VkResult MasterSemaphore::SubmitQueue(vk::CommandBuffer& cmdbuf, vk::CommandBuffer& upload_cmdbuf,\n                                      VkSemaphore signal_semaphore, VkSemaphore wait_semaphore,\n                                      u64 host_tick, bool has_upload_work) {\n    if (semaphore) {\n        return SubmitQueueTimeline(cmdbuf, upload_cmdbuf, signal_semaphore, wait_semaphore,\n                                   host_tick, has_upload_work);\n    } else {\n        return SubmitQueueFence(cmdbuf, upload_cmdbuf, signal_semaphore, wait_semaphore,\n                                host_tick, has_upload_work);\n    }\n}''',
    "host_tick, bool has_upload_work)",
    "make queue submission upload-aware",
)

replace_once(
    master_cpp,
    '''VkResult MasterSemaphore::SubmitQueueTimeline(vk::CommandBuffer& cmdbuf,\n                                              vk::CommandBuffer& upload_cmdbuf,\n                                              VkSemaphore signal_semaphore,\n                                              VkSemaphore wait_semaphore, u64 host_tick) {''',
    '''VkResult MasterSemaphore::SubmitQueueTimeline(vk::CommandBuffer& cmdbuf,\n                                              vk::CommandBuffer& upload_cmdbuf,\n                                              VkSemaphore signal_semaphore,\n                                              VkSemaphore wait_semaphore, u64 host_tick,\n                                              bool has_upload_work) {''',
    "bool has_upload_work) {",
    "upload-aware timeline submit",
)

replace_once(
    master_cpp,
    '''VkResult MasterSemaphore::SubmitQueueFence(vk::CommandBuffer& cmdbuf,\n                                           vk::CommandBuffer& upload_cmdbuf,\n                                           VkSemaphore signal_semaphore, VkSemaphore wait_semaphore,\n                                           u64 host_tick) {''',
    '''VkResult MasterSemaphore::SubmitQueueFence(vk::CommandBuffer& cmdbuf,\n                                           vk::CommandBuffer& upload_cmdbuf,\n                                           VkSemaphore signal_semaphore, VkSemaphore wait_semaphore,\n                                           u64 host_tick, bool has_upload_work) {''',
    "u64 host_tick, bool has_upload_work) {",
    "upload-aware fence submit",
)

# Both submission paths currently submit upload + graphics unconditionally. Make the command-buffer
# array/count depend on whether this flush actually recorded upload work. This keeps the dependency
# order identical while removing an otherwise-empty upload command buffer from normal graphics-only flushes.
replace_once(
    master_cpp,
    '''        const std::array<VkCommandBufferSubmitInfo, 2> cmdbuffer_infos{{\n            {\n                .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_SUBMIT_INFO,\n                .pNext = nullptr,\n                .commandBuffer = *upload_cmdbuf,\n                .deviceMask = 0,\n            },\n            {\n                .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_SUBMIT_INFO,\n                .pNext = nullptr,\n                .commandBuffer = *cmdbuf,\n                .deviceMask = 0,\n            },\n        }};''',
    '''        const std::array<VkCommandBufferSubmitInfo, 2> cmdbuffer_infos{{\n            {\n                .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_SUBMIT_INFO,\n                .pNext = nullptr,\n                .commandBuffer = has_upload_work ? *upload_cmdbuf : *cmdbuf,\n                .deviceMask = 0,\n            },\n            {\n                .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_SUBMIT_INFO,\n                .pNext = nullptr,\n                .commandBuffer = *cmdbuf,\n                .deviceMask = 0,\n            },\n        }};''',
    "commandBuffer = has_upload_work ? *upload_cmdbuf : *cmdbuf",
    "compact synchronization2 command list",
)

replace_once(
    master_cpp,
    "            .commandBufferInfoCount = static_cast<u32>(cmdbuffer_infos.size()),\n            .pCommandBufferInfos = cmdbuffer_infos.data(),",
    "            .commandBufferInfoCount = has_upload_work ? 2u : 1u,\n            .pCommandBufferInfos = cmdbuffer_infos.data(),",
    "commandBufferInfoCount = has_upload_work ? 2u : 1u",
    "compact synchronization2 count",
)

replace_once(
    master_cpp,
    '''    const std::array cmdbuffers{*upload_cmdbuf, *cmdbuf};\n\n    const u32 num_wait_semaphores = wait_semaphore ? 1 : 0;''',
    '''    const std::array cmdbuffers{has_upload_work ? *upload_cmdbuf : *cmdbuf, *cmdbuf};\n\n    const u32 num_wait_semaphores = wait_semaphore ? 1 : 0;''',
    "const std::array cmdbuffers{has_upload_work ? *upload_cmdbuf : *cmdbuf",
    "compact legacy command list",
)

replace_once(
    master_cpp,
    "        .commandBufferCount = static_cast<u32>(cmdbuffers.size()),\n        .pCommandBuffers = cmdbuffers.data(),",
    "        .commandBufferCount = has_upload_work ? 2u : 1u,\n        .pCommandBuffers = cmdbuffers.data(),",
    "commandBufferCount = has_upload_work ? 2u : 1u",
    "compact legacy count",
)

replace_once(
    scheduler_cpp,
    '''    const u64 signal_value = master_semaphore->NextTick();\n    RecordWithUploadBuffer([signal_semaphore, wait_semaphore, signal_value,\n                            this](vk::CommandBuffer cmdbuf, vk::CommandBuffer upload_cmdbuf) {''',
    '''    const u64 signal_value = master_semaphore->NextTick();\n    const bool has_upload_work = upload_work_pending;\n    upload_work_pending = false;\n    Record([signal_semaphore, wait_semaphore, signal_value, has_upload_work,\n            this](vk::CommandBuffer cmdbuf) {''',
    "const bool has_upload_work = upload_work_pending;",
    "snapshot upload work before submission",
)

replace_once(
    scheduler_cpp,
    '''        upload_cmdbuf.PipelineBarrier(VK_PIPELINE_STAGE_TRANSFER_BIT, VK_PIPELINE_STAGE_ALL_COMMANDS_BIT, 0, WRITE_BARRIER);\n        upload_cmdbuf.End();\n        cmdbuf.End();''',
    '''        if (has_upload_work) {\n            current_upload_cmdbuf.PipelineBarrier(VK_PIPELINE_STAGE_TRANSFER_BIT,\n                                                  VK_PIPELINE_STAGE_ALL_COMMANDS_BIT, 0,\n                                                  WRITE_BARRIER);\n            current_upload_cmdbuf.End();\n        }\n        cmdbuf.End();''',
    "if (has_upload_work) {\n            current_upload_cmdbuf.PipelineBarrier",
    "emit upload barrier only when uploads exist",
)

replace_once(
    scheduler_cpp,
    '''        switch (const VkResult result = master_semaphore->SubmitQueue(\n                    cmdbuf, upload_cmdbuf, signal_semaphore, wait_semaphore, signal_value)) {''',
    '''        switch (const VkResult result = master_semaphore->SubmitQueue(\n                    cmdbuf, current_upload_cmdbuf, signal_semaphore, wait_semaphore, signal_value,\n                    has_upload_work)) {''',
    "signal_value,\n                    has_upload_work))",
    "pass upload state to queue",
)

print(f"{TAG} complete")
