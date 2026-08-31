#!/usr/bin/env python3
from pathlib import Path
import subprocess

BASE = "138bab71ce8abef39a05371d7e0253eacaeec509"
SOURCE = Path("src/video_core/renderer_vulkan/vk_rasterizer.cpp")
WORKFLOW = Path(".github/workflows/build-android-baseline.yml")
SELF = Path(".github/scripts/apply_totk_foliage_sync.py")

text = SOURCE.read_text()

anchor_setup = '''    if (!pipeline->Configure(*kepler_compute, *gpu_memory, scheduler, buffer_cache,\n                             texture_cache)) {\n        return;\n    }\n\n    const auto& qmd{kepler_compute->launch_description};\n'''
replacement_setup = '''    if (!pipeline->Configure(*kepler_compute, *gpu_memory, scheduler, buffer_cache,\n                             texture_cache)) {\n        return;\n    }\n\n    // Moonwitch: Tears of the Kingdom can lose compute-produced foliage data on Android\n    // while the guest-side objects remain alive. Keep this workaround title-specific so\n    // other games retain the normal, cheaper synchronization path.\n#ifdef __ANDROID__\n    static constexpr u64 TOTK_PROGRAM_ID = 0x0100F2C0115B6000ULL;\n    const bool apply_totk_compute_visibility_workaround = program_id == TOTK_PROGRAM_ID;\n#else\n    const bool apply_totk_compute_visibility_workaround = false;\n#endif\n    const auto record_totk_compute_visibility_barrier =\n        [this, apply_totk_compute_visibility_workaround] {\n            if (!apply_totk_compute_visibility_workaround) {\n                return;\n            }\n            scheduler.Record([](vk::CommandBuffer cmdbuf) {\n                static constexpr VkMemoryBarrier visibility_barrier{\n                    .sType = VK_STRUCTURE_TYPE_MEMORY_BARRIER,\n                    .pNext = nullptr,\n                    .srcAccessMask = VK_ACCESS_SHADER_WRITE_BIT | VK_ACCESS_MEMORY_WRITE_BIT,\n                    .dstAccessMask = VK_ACCESS_INDIRECT_COMMAND_READ_BIT |\n                                     VK_ACCESS_INDEX_READ_BIT |\n                                     VK_ACCESS_VERTEX_ATTRIBUTE_READ_BIT |\n                                     VK_ACCESS_UNIFORM_READ_BIT | VK_ACCESS_SHADER_READ_BIT |\n                                     VK_ACCESS_MEMORY_READ_BIT,\n                };\n                static constexpr VkPipelineStageFlags destination_stages =\n                    VK_PIPELINE_STAGE_DRAW_INDIRECT_BIT | VK_PIPELINE_STAGE_VERTEX_INPUT_BIT |\n                    VK_PIPELINE_STAGE_VERTEX_SHADER_BIT |\n                    VK_PIPELINE_STAGE_TESSELLATION_CONTROL_SHADER_BIT |\n                    VK_PIPELINE_STAGE_TESSELLATION_EVALUATION_SHADER_BIT |\n                    VK_PIPELINE_STAGE_GEOMETRY_SHADER_BIT |\n                    VK_PIPELINE_STAGE_FRAGMENT_SHADER_BIT |\n                    VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT;\n                cmdbuf.PipelineBarrier(VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT, destination_stages,\n                                       0, visibility_barrier);\n            });\n        };\n\n    const auto& qmd{kepler_compute->launch_description};\n'''
if text.count(anchor_setup) != 1:
    raise RuntimeError(f"setup anchor count={text.count(anchor_setup)}")
text = text.replace(anchor_setup, replacement_setup, 1)

anchor_indirect = '''        scheduler.Record([pipeline, indirect_buffer = buffer->Handle(),\n                          indirect_offset = offset](vk::CommandBuffer cmdbuf) {\n            if (!pipeline->IsBound()) {\n                return;\n            }\n            cmdbuf.DispatchIndirect(indirect_buffer, indirect_offset);\n        });\n        return;\n'''
replacement_indirect = '''        scheduler.Record([pipeline, indirect_buffer = buffer->Handle(),\n                          indirect_offset = offset](vk::CommandBuffer cmdbuf) {\n            if (!pipeline->IsBound()) {\n                return;\n            }\n            cmdbuf.DispatchIndirect(indirect_buffer, indirect_offset);\n        });\n        record_totk_compute_visibility_barrier();\n        return;\n'''
if text.count(anchor_indirect) != 1:
    raise RuntimeError(f"indirect anchor count={text.count(anchor_indirect)}")
text = text.replace(anchor_indirect, replacement_indirect, 1)

anchor_direct = '''    scheduler.Record([pipeline, dim](vk::CommandBuffer cmdbuf) {\n        if (!pipeline->IsBound()) {\n            return;\n        }\n        cmdbuf.Dispatch(dim[0], dim[1], dim[2]);\n    });\n\n    // Log compute dispatch\n'''
replacement_direct = '''    scheduler.Record([pipeline, dim](vk::CommandBuffer cmdbuf) {\n        if (!pipeline->IsBound()) {\n            return;\n        }\n        cmdbuf.Dispatch(dim[0], dim[1], dim[2]);\n    });\n    record_totk_compute_visibility_barrier();\n\n    // Log compute dispatch\n'''
if text.count(anchor_direct) != 1:
    raise RuntimeError(f"direct anchor count={text.count(anchor_direct)}")
text = text.replace(anchor_direct, replacement_direct, 1)
SOURCE.write_text(text)

normal_workflow = '''name: Moonwitch V1.2 Performance Preview\n\non:\n  workflow_dispatch:\n  push:\n    branches:\n      - perf/moonwitch-v1.2\n\njobs:\n  build:\n    runs-on: ubuntu-latest\n    timeout-minutes: 120\n    steps:\n      - name: Checkout\n        uses: actions/checkout@v4\n        with:\n          submodules: recursive\n          fetch-depth: 1\n\n      - name: Java 17\n        uses: actions/setup-java@v4\n        with:\n          distribution: temurin\n          java-version: '17'\n\n      - name: Dependencies\n        shell: bash\n        run: |\n          sudo apt-get update\n          sudo apt-get install -y glslang-tools spirv-tools\n          yes | "$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager" --licenses >/dev/null || true\n          "$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager" "platforms;android-36" "build-tools;36.0.0" "ndk;28.2.13676358" "cmake;3.31.6"\n\n      - name: Build\n        shell: bash\n        env:\n          CCACHE: 'false'\n        run: |\n          chmod +x .ci/android/build.sh src/android/gradlew\n          .ci/android/build.sh -t standard -b Release\n\n      - name: Upload APK\n        uses: actions/upload-artifact@v4\n        with:\n          name: MOONWITCH-V1-2-PERF-PREVIEW\n          path: artifacts/*.apk\n          if-no-files-found: error\n          retention-days: 7\n'''
WORKFLOW.write_text(normal_workflow)
SELF.unlink()

subprocess.run(["git", "config", "user.name", "Moonwitch CI"], check=True)
subprocess.run(["git", "config", "user.email", "moonwitch-ci@users.noreply.github.com"], check=True)
subprocess.run(["git", "add", "-A"], check=True)
subprocess.run(["git", "reset", "--soft", BASE], check=True)
subprocess.run(["git", "commit", "-m", "[skip ci] renderer(vulkan): add TOTK compute visibility workaround"], check=True)
subprocess.run(["git", "push", "--force", "origin", "HEAD:perf/moonwitch-v1.2"], check=True)
