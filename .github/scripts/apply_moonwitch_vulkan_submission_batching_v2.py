#!/usr/bin/env python3
from pathlib import Path

TAG='[moonwitch-vulkan-submission-batching]'

def once(p, old, new, marker):
    s=p.read_text()
    if marker in s:
        return
    if s.count(old)!=1:
        raise RuntimeError(f'{p}: anchor count for {marker!r} is {s.count(old)}')
    p.write_text(s.replace(old,new,1))

def many(p, old, new, expected):
    s=p.read_text()
    n=s.count(old)
    if n!=expected:
        raise RuntimeError(f'{p}: expected {expected} anchors, found {n}')
    p.write_text(s.replace(old,new))

r=Path('.')
sh=r/'src/video_core/renderer_vulkan/vk_scheduler.h'
sc=r/'src/video_core/renderer_vulkan/vk_scheduler.cpp'
mh=r/'src/video_core/renderer_vulkan/vk_master_semaphore.h'
mc=r/'src/video_core/renderer_vulkan/vk_master_semaphore.cpp'

once(sh, '''    void RecordWithUploadBuffer(T&& command) {\n        if (chunk->Record(command)) {''', '''    void RecordWithUploadBuffer(T&& command) {\n        upload_work_pending = true;\n        if (chunk->Record(command)) {''', 'upload_work_pending = true;')

once(sh, '''    void Record(T&& c) {\n        this->RecordWithUploadBuffer(\n            [command = std::move(c)](vk::CommandBuffer cmdbuf, vk::CommandBuffer) {\n                command(cmdbuf);\n            });\n    }''', '''    void Record(T&& c) {\n        auto command = [command = std::move(c)](vk::CommandBuffer cmdbuf, vk::CommandBuffer) {\n            command(cmdbuf);\n        };\n        if (chunk->Record(command)) {\n            return;\n        }\n        DispatchWork();\n        (void)chunk->Record(command);\n    }''', 'auto command = [command = std::move(c)]')

once(sh, '    std::function<void()> on_submit;\n\n    State state;', '    std::function<void()> on_submit;\n    bool upload_work_pending{};\n\n    State state;', 'bool upload_work_pending{};')

once(mh, '''    VkResult SubmitQueue(vk::CommandBuffer& cmdbuf, vk::CommandBuffer& upload_cmdbuf,\n                         VkSemaphore signal_semaphore, VkSemaphore wait_semaphore, u64 host_tick);''', '''    VkResult SubmitQueue(vk::CommandBuffer& cmdbuf, vk::CommandBuffer& upload_cmdbuf,\n                         VkSemaphore signal_semaphore, VkSemaphore wait_semaphore, u64 host_tick,\n                         bool has_upload_work);''', 'bool has_upload_work);')

once(mh, '''                                 VkSemaphore signal_semaphore, VkSemaphore wait_semaphore,\n                                 u64 host_tick);''', '''                                 VkSemaphore signal_semaphore, VkSemaphore wait_semaphore,\n                                 u64 host_tick, bool has_upload_work);''', 'u64 host_tick, bool has_upload_work);')

once(mh, '''                              VkSemaphore signal_semaphore, VkSemaphore wait_semaphore,\n                              u64 host_tick);''', '''                              VkSemaphore signal_semaphore, VkSemaphore wait_semaphore,\n                              u64 host_tick, bool has_upload_work);''', 'u64 host_tick, bool has_upload_work);')

once(mc, '''                                      VkSemaphore signal_semaphore, VkSemaphore wait_semaphore,\n                                      u64 host_tick) {\n    if (semaphore) {\n        return SubmitQueueTimeline(cmdbuf, upload_cmdbuf, signal_semaphore, wait_semaphore,\n                                   host_tick);\n    } else {\n        return SubmitQueueFence(cmdbuf, upload_cmdbuf, signal_semaphore, wait_semaphore, host_tick);\n    }\n}''', '''                                      VkSemaphore signal_semaphore, VkSemaphore wait_semaphore,\n                                      u64 host_tick, bool has_upload_work) {\n    if (semaphore) {\n        return SubmitQueueTimeline(cmdbuf, upload_cmdbuf, signal_semaphore, wait_semaphore,\n                                   host_tick, has_upload_work);\n    } else {\n        return SubmitQueueFence(cmdbuf, upload_cmdbuf, signal_semaphore, wait_semaphore,\n                                host_tick, has_upload_work);\n    }\n}''', 'host_tick, bool has_upload_work)')

once(mc, 'u64 host_tick) {\n    const VkSemaphore timeline_semaphore', 'u64 host_tick, bool has_upload_work) {\n    const VkSemaphore timeline_semaphore', 'bool has_upload_work) {\n    const VkSemaphore timeline_semaphore')

# The same command-buffer construction exists once in each submit path.
old='''        const std::array<VkCommandBufferSubmitInfo, 2> cmdbuffer_infos{{\n            {\n                .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_SUBMIT_INFO,\n                .pNext = nullptr,\n                .commandBuffer = *upload_cmdbuf,\n                .deviceMask = 0,\n            },\n            {\n                .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_SUBMIT_INFO,\n                .pNext = nullptr,\n                .commandBuffer = *cmdbuf,\n                .deviceMask = 0,\n            },\n        }};'''
new='''        const std::array<VkCommandBufferSubmitInfo, 2> cmdbuffer_infos{{\n            {\n                .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_SUBMIT_INFO,\n                .pNext = nullptr,\n                .commandBuffer = has_upload_work ? *upload_cmdbuf : *cmdbuf,\n                .deviceMask = 0,\n            },\n            {\n                .sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_SUBMIT_INFO,\n                .pNext = nullptr,\n                .commandBuffer = *cmdbuf,\n                .deviceMask = 0,\n            },\n        }};'''
many(mc,old,new,2)
many(mc,'            .commandBufferInfoCount = static_cast<u32>(cmdbuffer_infos.size()),','            .commandBufferInfoCount = has_upload_work ? 2u : 1u,',2)

old2='''    const std::array cmdbuffers{*upload_cmdbuf, *cmdbuf};\n\n    const u32 num_wait_semaphores = wait_semaphore ? 1 : 0;'''
new2='''    const std::array cmdbuffers{has_upload_work ? *upload_cmdbuf : *cmdbuf, *cmdbuf};\n\n    const u32 num_wait_semaphores = wait_semaphore ? 1 : 0;'''
many(mc,old2,new2,2)
many(mc,'        .commandBufferCount = static_cast<u32>(cmdbuffers.size()),','        .commandBufferCount = has_upload_work ? 2u : 1u,',2)

once(mc, 'u64 host_tick) {\n    if (device.HasSynchronization2())', 'u64 host_tick, bool has_upload_work) {\n    if (device.HasSynchronization2())', 'u64 host_tick, bool has_upload_work) {\n    if (device.HasSynchronization2())')

once(sc, '''    const u64 signal_value = master_semaphore->NextTick();\n    RecordWithUploadBuffer([signal_semaphore, wait_semaphore, signal_value,\n                            this](vk::CommandBuffer cmdbuf, vk::CommandBuffer upload_cmdbuf) {''', '''    const u64 signal_value = master_semaphore->NextTick();\n    const bool has_upload_work = upload_work_pending;\n    upload_work_pending = false;\n    Record([signal_semaphore, wait_semaphore, signal_value, has_upload_work,\n            this](vk::CommandBuffer cmdbuf) {''', 'const bool has_upload_work = upload_work_pending')

once(sc, '''        upload_cmdbuf.PipelineBarrier(VK_PIPELINE_STAGE_TRANSFER_BIT, VK_PIPELINE_STAGE_ALL_COMMANDS_BIT, 0, WRITE_BARRIER);\n        upload_cmdbuf.End();\n        cmdbuf.End();''', '''        if (has_upload_work) {\n            current_upload_cmdbuf.PipelineBarrier(VK_PIPELINE_STAGE_TRANSFER_BIT,\n                                                  VK_PIPELINE_STAGE_ALL_COMMANDS_BIT, 0,\n                                                  WRITE_BARRIER);\n            current_upload_cmdbuf.End();\n        }\n        cmdbuf.End();''', 'current_upload_cmdbuf.PipelineBarrier')

once(sc, '''        switch (const VkResult result = master_semaphore->SubmitQueue(\n                    cmdbuf, upload_cmdbuf, signal_semaphore, wait_semaphore, signal_value)) {''', '''        switch (const VkResult result = master_semaphore->SubmitQueue(\n                    cmdbuf, current_upload_cmdbuf, signal_semaphore, wait_semaphore, signal_value,\n                    has_upload_work)) {''', 'has_upload_work))')

print(TAG, 'complete')
