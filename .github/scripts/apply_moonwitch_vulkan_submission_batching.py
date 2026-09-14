#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path

TAG = "[moonwitch-vulkan-submission-batching]"


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        print(f"{TAG} {label}: already patched")
        return
    count = text.count(old)
    if count < 1:
        raise RuntimeError(f"{path}: expected one anchor for {label}, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"{TAG} {label}: patched")


root = Path(".")
scheduler_h = root / "src/video_core/renderer_vulkan/vk_scheduler.h"
scheduler_cpp = root / "src/video_core/renderer_vulkan/vk_scheduler.cpp"
master_h = root / "src/video_core/renderer_vulkan/vk_master_semaphore.h"
master_cpp = root / "src/video_core/renderer_vulkan/vk_master_semaphore.cpp"

# Track only real upload-buffer recordings. Ordinary graphics/compute Record() calls must not
# mark the upload command buffer as used.
replace_once(
    scheduler_h,
    '''    void RecordWithUploadBuffer(T&& command) {
        if (chunk->Record(command)) {
            return;
        }
        DispatchWork();
        (void)chunk->Record(command);
    }

    template <typename T>
        requires std::is_invocable_v<T, vk::CommandBuffer>
    void Record(T&& c) {
        this->RecordWithUploadBuffer(
            [command = std::move(c)](vk::CommandBuffer cmdbuf, vk::CommandBuffer) {
                command(cmdbuf);
            });
    }''',
    '''    void RecordWithUploadBuffer(T&& command) {
        upload_work_pending = true;
        if (chunk->Record(command)) {
            return;
        }
        DispatchWork();
        (void)chunk->Record(command);
    }

    template <typename T>
        requires std::is_invocable_v<T, vk::CommandBuffer>
    void Record(T&& c) {
        auto command = [command = std::move(c)](vk::CommandBuffer cmdbuf, vk::CommandBuffer) {
            command(cmdbuf);
        };
        if (chunk->Record(command)) {
            return;
        }
        DispatchWork();
        (void)chunk->Record(command);
    }''',
    "separate upload recording from ordinary recording",
)

replace_once(
    scheduler_h,
    '''    std::unique_ptr<CommandChunk> chunk;
    std::function<void()> on_submit;

    State state;''',
    '''    std::unique_ptr<CommandChunk> chunk;
    std::function<void()> on_submit;
    bool upload_work_pending{};

    State state;''',
    "store upload work state",
)

replace_once(
    master_h,
    '''    VkResult SubmitQueue(vk::CommandBuffer& cmdbuf, vk::CommandBuffer& upload_cmdbuf,
                         VkSemaphore signal_semaphore, VkSemaphore wait_semaphore, u64 host_tick);''',
    '''    VkResult SubmitQueue(vk::CommandBuffer& cmdbuf, vk::CommandBuffer& upload_cmdbuf,
                         VkSemaphore signal_semaphore, VkSemaphore wait_semaphore, u64 host_tick,
                         bool has_upload_work);''',
    "upload-aware public submission",
)

replace_once(
    master_h,
    '''    VkResult SubmitQueueTimeline(vk::CommandBuffer& cmdbuf, vk::CommandBuffer& upload_cmdbuf,
                                 VkSemaphore signal_semaphore, VkSemaphore wait_semaphore,
                                 u64 host_tick);
    VkResult SubmitQueueFence(vk::CommandBuffer& cmdbuf, vk::CommandBuffer& upload_cmdbuf,
                              VkSemaphore signal_semaphore, VkSemaphore wait_semaphore,
                              u64 host_tick);''',
    '''    VkResult SubmitQueueTimeline(vk::CommandBuffer& cmdbuf, vk::CommandBuffer& upload_cmdbuf,
                                 VkSemaphore signal_semaphore, VkSemaphore wait_semaphore,
                                 u64 host_tick, bool has_upload_work);
    VkResult SubmitQueueFence(vk::CommandBuffer& cmdbuf, vk::CommandBuffer& upload_cmdbuf,
                              VkSemaphore signal_semaphore, VkSemaphore wait_semaphore,
                              u64 host_tick, bool has_upload_work);''',
    "upload-aware private submission paths",
)

replace_once(
    master_cpp,
    '''VkResult MasterSemaphore::SubmitQueue(vk::CommandBuffer& cmdbuf, vk::CommandBuffer& upload_cmdbuf,
                                      VkSemaphore signal_semaphore, VkSemaphore wait_semaphore,
                                      u64 host_tick) {
    if (semaphore) {
        return SubmitQueueTimeline(cmdbuf, upload_cmdbuf, signal_semaphore, wait_semaphore,
                                   host_tick);
    } else {
        return SubmitQueueFence(cmdbuf, upload_cmdbuf, signal_semaphore, wait_semaphore, host_tick);
    }
}''',
    '''VkResult MasterSemaphore::SubmitQueue(vk::CommandBuffer& cmdbuf, vk::CommandBuffer& upload_cmdbuf,
                                      VkSemaphore signal_semaphore, VkSemaphore wait_semaphore,
                                      u64 host_tick, bool has_upload_work) {
    if (semaphore) {
        return SubmitQueueTimeline(cmdbuf, upload_cmdbuf, signal_semaphore, wait_semaphore,
                                   host_tick, has_upload_work);
    } else {
        return SubmitQueueFence(cmdbuf, upload_cmdbuf, signal_semaphore, wait_semaphore,
                                host_tick, has_upload_work);
    }
}''',
    "propagate upload state",
)

replace_once(
    master_cpp,
    '''VkResult MasterSemaphore::SubmitQueueTimeline(vk::CommandBuffer& cmdbuf,
                                              vk::CommandBuffer& upload_cmdbuf,
                                              VkSemaphore signal_semaphore,
                                              VkSemaphore wait_semaphore, u64 host_tick) {''',
    '''VkResult MasterSemaphore::SubmitQueueTimeline(vk::CommandBuffer& cmdbuf,
                                              vk::CommandBuffer& upload_cmdbuf,
                                              VkSemaphore signal_semaphore,
                                              VkSemaphore wait_semaphore, u64 host_tick,
                                              bool has_upload_work) {''',
    "timeline upload state",
)

replace_once(
    master_cpp,
    '''VkResult MasterSemaphore::SubmitQueueFence(vk::CommandBuffer& cmdbuf,
                                           vk::CommandBuffer& upload_cmdbuf,
                                           VkSemaphore signal_semaphore, VkSemaphore wait_semaphore,
                                           u64 host_tick) {''',
    '''VkResult MasterSemaphore::SubmitQueueFence(vk::CommandBuffer& cmdbuf,
                                           vk::CommandBuffer& upload_cmdbuf,
                                           VkSemaphore signal_semaphore, VkSemaphore wait_semaphore,
                                           u64 host_tick, bool has_upload_work) {''',
    "fence upload state",
)

# Synchronization2: submit the upload command buffer only when it actually contains upload work.
replace_once(
    master_cpp,
    '''        const std::array<VkCommandBufferSubmitInfo, 2> cmdbuffer_infos{{
            {
                .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_SUBMIT_INFO,
                .pNext = nullptr,
                .commandBuffer = *upload_cmdbuf,
                .deviceMask = 0,
            },
            {
                .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_SUBMIT_INFO,
                .pNext = nullptr,
                .commandBuffer = *cmdbuf,
                .deviceMask = 0,
            },
        }};''',
    '''        const std::array<VkCommandBufferSubmitInfo, 2> cmdbuffer_infos{{
            {
                .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_SUBMIT_INFO,
                .pNext = nullptr,
                .commandBuffer = *upload_cmdbuf,
                .deviceMask = 0,
            },
            {
                .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_SUBMIT_INFO,
                .pNext = nullptr,
                .commandBuffer = *cmdbuf,
                .deviceMask = 0,
            },
        }};''',
    "prepare compact synchronization2 submission",
)

replace_once(
    master_cpp,
    '''            .commandBufferInfoCount = static_cast<u32>(cmdbuffer_infos.size()),
            .pCommandBufferInfos = cmdbuffer_infos.data(),''',
    '''            .commandBufferInfoCount = has_upload_work ? 2u : 1u,
            .pCommandBufferInfos = has_upload_work ? cmdbuffer_infos.data() + 0 : cmdbuffer_infos.data() + 1,''',
    "compact synchronization2 count",
)

# Legacy submit path: same optimization, selecting the graphics command buffer when there is no upload.
replace_once(
    master_cpp,
    '''    const std::array cmdbuffers{*upload_cmdbuf, *cmdbuf};''',
    '''    const std::array cmdbuffers{*upload_cmdbuf, *cmdbuf};''',
    "prepare compact legacy submission",
)

replace_once(
    master_cpp,
    '''        .commandBufferCount = static_cast<u32>(cmdbuffers.size()),
        .pCommandBuffers = cmdbuffers.data(),''',
    '''        .commandBufferCount = has_upload_work ? 2u : 1u,
        .pCommandBuffers = has_upload_work ? cmdbuffers.data() : cmdbuffers.data() + 1,''',
    "compact legacy count",
)

# Fence + synchronization2 has the same two-command-buffer layout as the timeline path. Replace only
# the second occurrence (the first one was already handled above) by anchoring the following fence code.
fence_anchor = '''VkResult MasterSemaphore::SubmitQueueFence'''
text = master_cpp.read_text(encoding="utf-8")
marker = "const VkSubmitInfo2 submit_info2{"
start = text.index(fence_anchor)
idx = text.index(marker, start)
segment = text[idx:]
old = '''            .commandBufferInfoCount = static_cast<u32>(cmdbuffer_infos.size()),
            .pCommandBufferInfos = cmdbuffer_infos.data(),'''
if old not in segment:
    raise RuntimeError(f"{master_cpp}: fence synchronization2 count anchor not found")
segment = segment.replace(old, '''            .commandBufferInfoCount = has_upload_work ? 2u : 1u,
            .pCommandBufferInfos = has_upload_work ? cmdbuffer_infos.data() : cmdbuffer_infos.data() + 1,''', 1)
master_cpp.write_text(text[:idx] + segment, encoding="utf-8")
print(f"{TAG} fence synchronization2 count: patched")

# Submission callback: snapshot upload state before recording the final submit command and do not
# submit the upload command buffer when it was unused. The empty upload command buffer is still ended
# so it remains valid for command-pool recycling.
replace_once(
    scheduler_cpp,
    '''    const u64 signal_value = master_semaphore->NextTick();
    RecordWithUploadBuffer([signal_semaphore, wait_semaphore, signal_value,
                            this](vk::CommandBuffer cmdbuf, vk::CommandBuffer upload_cmdbuf) {''',
    '''    const u64 signal_value = master_semaphore->NextTick();
    const bool has_upload_work = upload_work_pending;
    upload_work_pending = false;
    auto submit_command = [signal_semaphore, wait_semaphore, signal_value, has_upload_work,
                           this](vk::CommandBuffer cmdbuf, vk::CommandBuffer upload_cmdbuf) {''',
    "snapshot upload state",
)

replace_once(
    scheduler_cpp,
    '''        upload_cmdbuf.PipelineBarrier(VK_PIPELINE_STAGE_TRANSFER_BIT, VK_PIPELINE_STAGE_ALL_COMMANDS_BIT, 0, WRITE_BARRIER);
        upload_cmdbuf.End();
        cmdbuf.End();''',
    '''        if (has_upload_work) {
            upload_cmdbuf.PipelineBarrier(VK_PIPELINE_STAGE_TRANSFER_BIT,
                                          VK_PIPELINE_STAGE_ALL_COMMANDS_BIT, 0, WRITE_BARRIER);
        }
        upload_cmdbuf.End();
        cmdbuf.End();''',
    "guard upload barrier",
)

replace_once(
    scheduler_cpp,
    '''        switch (const VkResult result = master_semaphore->SubmitQueue(
                    cmdbuf, upload_cmdbuf, signal_semaphore, wait_semaphore, signal_value)) {''',
    '''        switch (const VkResult result = master_semaphore->SubmitQueue(
                    cmdbuf, upload_cmdbuf, signal_semaphore, wait_semaphore, signal_value,
                    has_upload_work)) {''',
    "pass upload state to queue",
)

replace_once(
    scheduler_cpp,
    '''    });
    chunk->MarkSubmit();
    DispatchWork();''',
    '''    };
    if (chunk->Record(submit_command)) {
        // The submit command was appended to the current chunk.
    } else {
        DispatchWork();
        (void)chunk->Record(submit_command);
    }
    chunk->MarkSubmit();
    DispatchWork();''',
    "record final submission without marking upload work",
)

print(f"{TAG} complete")
