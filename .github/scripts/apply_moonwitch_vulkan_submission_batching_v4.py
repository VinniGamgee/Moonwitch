#!/usr/bin/env python3
from pathlib import Path

def once(p, old, new, label):
    s=p.read_text()
    if old not in s:
        return
    if s.count(old)!=1:
        raise RuntimeError(f'{p}: expected 1 anchor for {label}, found {s.count(old)}')
    p.write_text(s.replace(old,new,1))

def many(p, old, new, expected, label):
    s=p.read_text()
    if old not in s:
        return
    n=s.count(old)
    if n not in (expected, expected - 1):
        raise RuntimeError(f'{p}: expected {expected} anchors for {label}, found {n}')
    p.write_text(s.replace(old,new))

r=Path('.')
sh=r/'src/video_core/renderer_vulkan/vk_scheduler.h'
sc=r/'src/video_core/renderer_vulkan/vk_scheduler.cpp'
mh=r/'src/video_core/renderer_vulkan/vk_master_semaphore.h'
mc=r/'src/video_core/renderer_vulkan/vk_master_semaphore.cpp'

once(sh, '''    void RecordWithUploadBuffer(T&& command) {
        if (chunk->Record(command)) {''', '''    void RecordWithUploadBuffer(T&& command) {
        upload_work_pending = true;
        if (chunk->Record(command)) {''', 'scheduler upload flag')
once(sh, '''    void Record(T&& c) {
        this->RecordWithUploadBuffer(
            [command = std::move(c)](vk::CommandBuffer cmdbuf, vk::CommandBuffer) {
                command(cmdbuf);
            });
    }''', '''    void Record(T&& c) {
        auto command = [command = std::move(c)](vk::CommandBuffer cmdbuf, vk::CommandBuffer) {
            command(cmdbuf);
        };
        if (chunk->Record(command)) {
            return;
        }
        DispatchWork();
        (void)chunk->Record(command);
    }''', 'scheduler direct record path')
once(sh, '    std::function<void()> on_submit;\n\n    State state;', '    std::function<void()> on_submit;\n    bool upload_work_pending{};\n\n    State state;', 'scheduler upload state')

once(mh, '''    VkResult SubmitQueue(vk::CommandBuffer& cmdbuf, vk::CommandBuffer& upload_cmdbuf,
                         VkSemaphore signal_semaphore, VkSemaphore wait_semaphore, u64 host_tick);''', '''    VkResult SubmitQueue(vk::CommandBuffer& cmdbuf, vk::CommandBuffer& upload_cmdbuf,
                         VkSemaphore signal_semaphore, VkSemaphore wait_semaphore, u64 host_tick,
                         bool has_upload_work);''', 'public submit signature')

once(mh, '''                                 VkSemaphore signal_semaphore, VkSemaphore wait_semaphore,
                                 u64 host_tick);''', '''                                 VkSemaphore signal_semaphore, VkSemaphore wait_semaphore,
                                 u64 host_tick, bool has_upload_work);''', 'timeline submit signature')
once(mh, '''                              VkSemaphore signal_semaphore, VkSemaphore wait_semaphore,
                              u64 host_tick);''', '''                              VkSemaphore signal_semaphore, VkSemaphore wait_semaphore,
                              u64 host_tick, bool has_upload_work);''', 'fence submit signature')

once(mc, '''                                      VkSemaphore signal_semaphore, VkSemaphore wait_semaphore,
                                      u64 host_tick) {
    if (semaphore) {
        return SubmitQueueTimeline(cmdbuf, upload_cmdbuf, signal_semaphore, wait_semaphore,
                                   host_tick);
    } else {
        return SubmitQueueFence(cmdbuf, upload_cmdbuf, signal_semaphore, wait_semaphore, host_tick);
    }
}''', '''                                      VkSemaphore signal_semaphore, VkSemaphore wait_semaphore,
                                      u64 host_tick, bool has_upload_work) {
    if (semaphore) {
        return SubmitQueueTimeline(cmdbuf, upload_cmdbuf, signal_semaphore, wait_semaphore,
                                   host_tick, has_upload_work);
    } else {
        return SubmitQueueFence(cmdbuf, upload_cmdbuf, signal_semaphore, wait_semaphore,
                                host_tick, has_upload_work);
    }
}''', 'dispatch submit signature')

once(mc, '''                                              VkSemaphore signal_semaphore,
                                              VkSemaphore wait_semaphore, u64 host_tick) {''', '''                                              VkSemaphore signal_semaphore,
                                              VkSemaphore wait_semaphore, u64 host_tick,
                                              bool has_upload_work) {''', 'timeline definition')
once(mc, '''                                           VkSemaphore signal_semaphore, VkSemaphore wait_semaphore,
                                           u64 host_tick) {''', '''                                           VkSemaphore signal_semaphore, VkSemaphore wait_semaphore,
                                           u64 host_tick, bool has_upload_work) {''', 'fence definition')

old='''        const std::array<VkCommandBufferSubmitInfo, 2> cmdbuffer_infos{{
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
        }};'''
new='''        const std::array<VkCommandBufferSubmitInfo, 2> cmdbuffer_infos{{
            {
                .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_SUBMIT_INFO,
                .pNext = nullptr,
                .commandBuffer = has_upload_work ? *upload_cmdbuf : *cmdbuf,
                .deviceMask = 0,
            },
            {
                .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_SUBMIT_INFO,
                .pNext = nullptr,
                .commandBuffer = *cmdbuf,
                .deviceMask = 0,
            },
        }};'''
many(mc,old,new,2,'sync2 command buffers')
many(mc,'            .commandBufferInfoCount = static_cast<u32>(cmdbuffer_infos.size()),','            .commandBufferInfoCount = has_upload_work ? 2u : 1u,',2,'sync2 command count')
old='''    const std::array cmdbuffers{*upload_cmdbuf, *cmdbuf};

    const u32 num_wait_semaphores = wait_semaphore ? 1 : 0;'''
new='''    const std::array cmdbuffers{has_upload_work ? *upload_cmdbuf : *cmdbuf, *cmdbuf};

    const u32 num_wait_semaphores = wait_semaphore ? 1 : 0;'''
many(mc,old,new,2,'legacy command buffers')
many(mc,'        .commandBufferCount = static_cast<u32>(cmdbuffers.size()),','        .commandBufferCount = has_upload_work ? 2u : 1u,',2,'legacy command count')

once(sc, '''    const u64 signal_value = master_semaphore->NextTick();
    RecordWithUploadBuffer([signal_semaphore, wait_semaphore, signal_value,
                            this](vk::CommandBuffer cmdbuf, vk::CommandBuffer upload_cmdbuf) {''', '''    const u64 signal_value = master_semaphore->NextTick();
    const bool has_upload_work = upload_work_pending;
    upload_work_pending = false;
    Record([signal_semaphore, wait_semaphore, signal_value, has_upload_work,
            this](vk::CommandBuffer cmdbuf) {''', 'scheduler submission snapshot')
once(sc, '''        upload_cmdbuf.PipelineBarrier(VK_PIPELINE_STAGE_TRANSFER_BIT, VK_PIPELINE_STAGE_ALL_COMMANDS_BIT, 0, WRITE_BARRIER);
        upload_cmdbuf.End();
        cmdbuf.End();''', '''        if (has_upload_work) {
            current_upload_cmdbuf.PipelineBarrier(VK_PIPELINE_STAGE_TRANSFER_BIT,
                                                  VK_PIPELINE_STAGE_ALL_COMMANDS_BIT, 0,
                                                  WRITE_BARRIER);
        }
        current_upload_cmdbuf.End();
        cmdbuf.End();''', 'scheduler conditional upload barrier')
once(sc, '''        switch (const VkResult result = master_semaphore->SubmitQueue(
                    cmdbuf, upload_cmdbuf, signal_semaphore, wait_semaphore, signal_value)) {''', '''        switch (const VkResult result = master_semaphore->SubmitQueue(
                    cmdbuf, current_upload_cmdbuf, signal_semaphore, wait_semaphore, signal_value,
                    has_upload_work)) {''', 'scheduler upload-aware submit')

print('[moonwitch-vulkan-submission-batching] complete')
