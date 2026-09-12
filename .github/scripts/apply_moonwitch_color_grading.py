#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path
from textwrap import dedent


def replace_once(path: Path, old: str, new: str, marker: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if marker in text:
        print(f"[moonwitch-color-grading] {label}: already patched")
        return
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one anchor for {label}, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"[moonwitch-color-grading] {label}: patched")


def write_new(path: Path, content: str, marker: str, label: str) -> None:
    rendered = dedent(content).lstrip()
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if marker in existing:
            print(f"[moonwitch-color-grading] {label}: already present")
            return
        raise RuntimeError(f"{path}: refusing to overwrite an unrelated existing file")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered, encoding="utf-8")
    print(f"[moonwitch-color-grading] {label}: created")


root = Path(".")
settings_h = root / "src/common/settings.h"
int_setting = root / (
    "src/android/app/src/main/java/org/yuzu/yuzu_emu/features/settings/model/IntSetting.kt"
)
settings_item = root / (
    "src/android/app/src/main/java/org/yuzu/yuzu_emu/features/settings/model/view/SettingsItem.kt"
)
presenter = root / (
    "src/android/app/src/main/java/org/yuzu/yuzu_emu/features/settings/ui/"
    "SettingsFragmentPresenter.kt"
)
emulation_fragment = root / (
    "src/android/app/src/main/java/org/yuzu/yuzu_emu/fragments/EmulationFragment.kt"
)
arrays_xml = root / "src/android/app/src/main/res/values/arrays.xml"
strings_xml = root / "src/android/app/src/main/res/values/strings.xml"
strings_pt_xml = root / "src/android/app/src/main/res/values-pt-rBR/strings.xml"
video_cmake = root / "src/video_core/CMakeLists.txt"
shader_cmake = root / "src/video_core/host_shaders/CMakeLists.txt"
layer_cpp = root / "src/video_core/renderer_vulkan/present/layer.cpp"
layer_h = root / "src/video_core/renderer_vulkan/present/layer.h"


replace_once(
    settings_h,
    '    SwitchableSetting<bool> frame_gen{linkage, false, "frame_gen", Category::Renderer,\n',
    '    // Moonwitch Color Grading is independent from the window scaling filter. Mode 0 keeps\n'
    '    // the pass disabled, so the default path has no additional GPU work.\n'
    '    SwitchableSetting<int, true> moonwitch_color_grading_mode{\n'
    '        linkage, 0, 0, 8, "moonwitch_color_grading_mode", Category::Renderer,\n'
    '        Specialization::Default, true, true};\n'
    '    SwitchableSetting<int, true> moonwitch_color_grading_strength{\n'
    '        linkage, 100, 0, 100, "moonwitch_color_grading_strength", Category::Renderer,\n'
    '        Specialization::Scalar | Specialization::Percentage, true, true};\n\n'
    '    SwitchableSetting<bool> frame_gen{linkage, false, "frame_gen", Category::Renderer,\n',
    "moonwitch_color_grading_mode",
    "register renderer settings",
)

replace_once(
    int_setting,
    '    RENDERER_ANTI_ALIASING("anti_aliasing"),\n',
    '    RENDERER_ANTI_ALIASING("anti_aliasing"),\n'
    '    MOONWITCH_COLOR_GRADING_MODE("moonwitch_color_grading_mode"),\n'
    '    MOONWITCH_COLOR_GRADING_STRENGTH("moonwitch_color_grading_strength"),\n',
    "MOONWITCH_COLOR_GRADING_MODE",
    "expose Android settings",
)

replace_once(
    settings_item,
    """            put(
                SingleChoiceSetting(
                    IntSetting.RENDERER_ANTI_ALIASING,
                    titleId = R.string.renderer_anti_aliasing,
                    choicesId = R.array.rendererAntiAliasingNames,
                    valuesId = R.array.rendererAntiAliasingValues
                )
            )
            put(
                SwitchSetting(
                    BooleanSetting.RENDERER_FRAME_GEN,
""",
    """            put(
                SingleChoiceSetting(
                    IntSetting.RENDERER_ANTI_ALIASING,
                    titleId = R.string.renderer_anti_aliasing,
                    choicesId = R.array.rendererAntiAliasingNames,
                    valuesId = R.array.rendererAntiAliasingValues
                )
            )
            put(
                SingleChoiceSetting(
                    IntSetting.MOONWITCH_COLOR_GRADING_MODE,
                    titleId = R.string.mw_color_grading_title,
                    descriptionId = R.string.mw_color_grading_description,
                    choicesId = R.array.moonwitchColorGradingNames,
                    valuesId = R.array.moonwitchColorGradingValues
                )
            )
            put(
                SliderSetting(
                    IntSetting.MOONWITCH_COLOR_GRADING_STRENGTH,
                    titleId = R.string.mw_color_grading_strength,
                    descriptionId = R.string.mw_color_grading_strength_description,
                    min = 0,
                    max = 100,
                    units = "%"
                )
            )
            put(
                SwitchSetting(
                    BooleanSetting.RENDERER_FRAME_GEN,
""",
    "MOONWITCH_COLOR_GRADING_MODE",
    "register settings UI items",
)

replace_once(
    presenter,
    '            add(IntSetting.RENDERER_ANTI_ALIASING.key)\n\n'
    '            add(HeaderSetting(R.string.mw_reconstruction_and_detail))\n',
    '            add(IntSetting.RENDERER_ANTI_ALIASING.key)\n\n'
    '            add(HeaderSetting(R.string.mw_color_grading_header))\n'
    '            add(IntSetting.MOONWITCH_COLOR_GRADING_MODE.key)\n'
    '            add(IntSetting.MOONWITCH_COLOR_GRADING_STRENGTH.key)\n\n'
    '            add(HeaderSetting(R.string.mw_reconstruction_and_detail))\n',
    "mw_color_grading_header",
    "show color grading controls",
)

replace_once(
    arrays_xml,
    '    <string-array name="statsPosition">\n',
    """    <string-array name="moonwitchColorGradingNames">
        <item>@string/mw_color_grading_original</item>
        <item>@string/mw_color_grading_vivid</item>
        <item>@string/mw_color_grading_dark</item>
        <item>@string/mw_color_grading_cinematic</item>
        <item>@string/mw_color_grading_warm</item>
        <item>@string/mw_color_grading_cool</item>
        <item>@string/mw_color_grading_moonlight</item>
        <item>@string/mw_color_grading_monochrome</item>
        <item>@string/mw_color_grading_hdr_plus</item>
    </string-array>

    <integer-array name="moonwitchColorGradingValues">
        <item>0</item>
        <item>1</item>
        <item>2</item>
        <item>3</item>
        <item>4</item>
        <item>5</item>
        <item>6</item>
        <item>7</item>
        <item>8</item>
    </integer-array>

    <string-array name="statsPosition">
""",
    "moonwitchColorGradingNames",
    "add preset arrays",
)

replace_once(
    strings_xml,
    '    <!-- Screen Layouts -->\n',
    """    <!-- Moonwitch Color Grading -->
    <string name="mw_color_grading_header">Image style</string>
    <string name="mw_color_grading_title">Moonwitch color style</string>
    <string name="mw_color_grading_description">Independent post-processing applied to the game image without replacing the scaling or anti-aliasing filters. Original disables the pass.</string>
    <string name="mw_color_grading_strength">Color style intensity</string>
    <string name="mw_color_grading_strength_description">Controls how strongly the selected style is blended with the original image.</string>
    <string name="mw_color_grading_original">Original (off)</string>
    <string name="mw_color_grading_vivid">Vivid</string>
    <string name="mw_color_grading_dark">Dark</string>
    <string name="mw_color_grading_cinematic">Cinematic</string>
    <string name="mw_color_grading_warm">Warm</string>
    <string name="mw_color_grading_cool">Cool</string>
    <string name="mw_color_grading_moonlight">Moonlight</string>
    <string name="mw_color_grading_monochrome">Monochrome</string>
    <string name="mw_color_grading_hdr_plus">HDR+</string>

    <!-- Screen Layouts -->
""",
    "mw_color_grading_title",
    "add English strings",
)

replace_once(
    strings_pt_xml,
    '    <!-- Screen Layouts -->\n',
    """    <!-- Moonwitch Color Grading -->
    <string name="mw_color_grading_header">Estilo de imagem</string>
    <string name="mw_color_grading_title">Estilo de cor Moonwitch</string>
    <string name="mw_color_grading_description">Pós-processamento independente aplicado à imagem do jogo sem substituir os filtros de escala ou anti-aliasing. Original desativa o passe.</string>
    <string name="mw_color_grading_strength">Intensidade do estilo</string>
    <string name="mw_color_grading_strength_description">Controla o quanto o estilo selecionado é misturado com a imagem original.</string>
    <string name="mw_color_grading_original">Original (desligado)</string>
    <string name="mw_color_grading_vivid">Vívido</string>
    <string name="mw_color_grading_dark">Escuro</string>
    <string name="mw_color_grading_cinematic">Cinemático</string>
    <string name="mw_color_grading_warm">Quente</string>
    <string name="mw_color_grading_cool">Frio</string>
    <string name="mw_color_grading_moonlight">Luar</string>
    <string name="mw_color_grading_monochrome">Monocromático</string>
    <string name="mw_color_grading_hdr_plus">HDR+</string>

    <!-- Screen Layouts -->
""",
    "mw_color_grading_title",
    "add Brazilian Portuguese strings",
)

replace_once(
    video_cmake,
    "    renderer_vulkan/present/cas.cpp\n    renderer_vulkan/present/cas.h\n",
    "    renderer_vulkan/present/cas.cpp\n"
    "    renderer_vulkan/present/cas.h\n"
    "    renderer_vulkan/present/color_grading.cpp\n"
    "    renderer_vulkan/present/color_grading.h\n",
    "renderer_vulkan/present/color_grading.cpp",
    "register renderer sources",
)

replace_once(
    shader_cmake,
    "    ${CMAKE_CURRENT_SOURCE_DIR}/vulkan_present.frag\n",
    "    ${CMAKE_CURRENT_SOURCE_DIR}/moonwitch_color_grading.frag\n"
    "    ${CMAKE_CURRENT_SOURCE_DIR}/vulkan_present.frag\n",
    "moonwitch_color_grading.frag",
    "register host shader",
)

replace_once(
    emulation_fragment,
    """            quickSettings.addIntSetting(
                R.string.renderer_anti_aliasing,
                container,
                IntSetting.RENDERER_ANTI_ALIASING,
                R.array.rendererAntiAliasingNames,
                R.array.rendererAntiAliasingValues
            )
""",
    """            quickSettings.addIntSetting(
                R.string.renderer_anti_aliasing,
                container,
                IntSetting.RENDERER_ANTI_ALIASING,
                R.array.rendererAntiAliasingNames,
                R.array.rendererAntiAliasingValues
            )

            quickSettings.addDivider(container)

            quickSettings.addIntSetting(
                R.string.mw_color_grading_title,
                container,
                IntSetting.MOONWITCH_COLOR_GRADING_MODE,
                R.array.moonwitchColorGradingNames,
                R.array.moonwitchColorGradingValues
            )

            quickSettings.addSliderSetting(
                R.string.mw_color_grading_strength,
                container,
                IntSetting.MOONWITCH_COLOR_GRADING_STRENGTH,
                minValue = 0,
                maxValue = 100,
                units = "%"
            )
""",
    "IntSetting.MOONWITCH_COLOR_GRADING_MODE",
    "add live Quick Settings controls",
)

replace_once(
    layer_h,
    '#include "video_core/renderer_vulkan/present/cas.h"\n',
    '#include "video_core/renderer_vulkan/present/cas.h"\n'
    '#include "video_core/renderer_vulkan/present/color_grading.h"\n',
    'present/color_grading.h',
    "include color grading pass",
)

replace_once(
    layer_h,
    "    std::optional<CAS> cas_pass{};\n",
    "    std::optional<CAS> cas_pass{};\n"
    "    std::optional<MoonwitchColorGrading> color_grading_pass{};\n",
    "color_grading_pass",
    "store color grading pass",
)

replace_once(
    layer_cpp,
    '#include "video_core/renderer_vulkan/present/cas.h"\n',
    '#include "video_core/renderer_vulkan/present/cas.h"\n'
    '#include "video_core/renderer_vulkan/present/color_grading.h"\n',
    'present/color_grading.h',
    "include renderer implementation",
)

replace_once(
    layer_cpp,
    """        source_image_view = cas_pass->Draw(device, scheduler, image_index, source_image_view);
    }

    SetMatrixData(device, *out_push_constants, layout);
""",
    """        source_image_view = cas_pass->Draw(device, scheduler, image_index, source_image_view);
    }

    if (Settings::values.moonwitch_color_grading_mode.GetValue() != 0) {
        const VkExtent2D color_grading_extent =
            std::holds_alternative<std::monostate>(sr_filter) ? render_extent
                                                              : output_size_extent;
        if (!color_grading_pass || color_grading_pass->NeedsRecreation(color_grading_extent)) {
            color_grading_pass.emplace(device, memory_allocator, image_count,
                                       color_grading_extent);
        }
        source_image_view = color_grading_pass->Draw(device, scheduler, image_index,
                                                     source_image_view);
    }

    SetMatrixData(device, *out_push_constants, layout);
""",
    "moonwitch_color_grading_mode.GetValue()",
    "insert independent post-processing pass",
)

write_new(
    root / "src/video_core/renderer_vulkan/present/color_grading.h",
    r'''
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

        class MoonwitchColorGrading final {
        public:
            explicit MoonwitchColorGrading(const Device& device, MemoryAllocator& allocator,
                                           size_t image_count, VkExtent2D extent);
            ~MoonwitchColorGrading();

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
            void UpdateDescriptorSet(const Device& device, VkImageView source_image_view,
                                     size_t image_index);
            void UploadImages(const Device& device, Scheduler& scheduler);

            struct Image {
                vk::DescriptorSets descriptor_sets{};
                vk::Framebuffer framebuffer{};
                vk::Image image{};
                vk::ImageView image_view{};
            };

            std::vector<Image> images{};
            VkExtent2D extent{};
            u32 image_count{};
            vk::ShaderModule vertex_shader{};
            vk::ShaderModule fragment_shader{};
            vk::DescriptorPool descriptor_pool{};
            vk::DescriptorSetLayout descriptor_set_layout{};
            vk::PipelineLayout pipeline_layout{};
            vk::Pipeline pipeline{};
            vk::RenderPass renderpass{};
            vk::Sampler sampler{};
            bool images_ready{};
        };

        } // namespace Vulkan
    ''',
    "class MoonwitchColorGrading final",
    "create renderer header",
)

write_new(
    root / "src/video_core/renderer_vulkan/present/color_grading.cpp",
    r'''
        // SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
        // SPDX-License-Identifier: GPL-3.0-or-later

        #include <algorithm>
        #include <tuple>
        #include <vector>

        #include "common/settings.h"
        #include "video_core/host_shaders/moonwitch_color_grading_frag_spv.h"
        #include "video_core/host_shaders/vulkan_fidelityfx_fsr_vert_spv.h"
        #include "video_core/renderer_vulkan/present/color_grading.h"
        #include "video_core/renderer_vulkan/present/util.h"
        #include "video_core/renderer_vulkan/vk_scheduler.h"
        #include "video_core/vulkan_common/vulkan_device.h"

        namespace Vulkan {

        struct ColorGradingPushConstants {
            s32 mode;
            f32 strength;
        };

        MoonwitchColorGrading::MoonwitchColorGrading(const Device& device,
                                                     MemoryAllocator& allocator,
                                                     size_t image_count_, VkExtent2D extent_)
            : extent{extent_}, image_count{static_cast<u32>(image_count_)} {
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

        MoonwitchColorGrading::~MoonwitchColorGrading() = default;

        void MoonwitchColorGrading::CreateImages(const Device& device,
                                                 MemoryAllocator& allocator) {
            images.resize(image_count);
            for (auto& image : images) {
                image.image =
                    CreateWrappedImage(allocator, extent, VK_FORMAT_R16G16B16A16_SFLOAT);
                image.image_view = CreateWrappedImageView(device, image.image,
                                                          VK_FORMAT_R16G16B16A16_SFLOAT);
            }
        }

        void MoonwitchColorGrading::CreateRenderPasses(const Device& device) {
            renderpass = CreateWrappedRenderPass(device, VK_FORMAT_R16G16B16A16_SFLOAT);
            for (auto& image : images) {
                image.framebuffer =
                    CreateWrappedFramebuffer(device, renderpass, image.image_view, extent);
            }
        }

        void MoonwitchColorGrading::CreateSampler(const Device& device) {
            sampler = CreateNearestNeighborSampler(device);
        }

        void MoonwitchColorGrading::CreateShaders(const Device& device) {
            vertex_shader =
                CreateWrappedShaderModule(device, VULKAN_FIDELITYFX_FSR_VERT_SPV);
            fragment_shader =
                CreateWrappedShaderModule(device, MOONWITCH_COLOR_GRADING_FRAG_SPV);
        }

        void MoonwitchColorGrading::CreateDescriptorPool(const Device& device) {
            descriptor_pool = CreateWrappedDescriptorPool(device, image_count, image_count);
        }

        void MoonwitchColorGrading::CreateDescriptorSetLayout(const Device& device) {
            descriptor_set_layout = CreateWrappedDescriptorSetLayout(
                device, {VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER});
        }

        void MoonwitchColorGrading::CreateDescriptorSets(const Device& device) {
            (void)device;
            const VkDescriptorSetLayout layout = *descriptor_set_layout;
            for (auto& image : images) {
                image.descriptor_sets = CreateWrappedDescriptorSets(descriptor_pool, {layout});
            }
        }

        void MoonwitchColorGrading::CreatePipelineLayout(const Device& device) {
            const VkPushConstantRange range{
                .stageFlags = VK_SHADER_STAGE_FRAGMENT_BIT,
                .offset = 0,
                .size = sizeof(ColorGradingPushConstants),
            };
            const VkPipelineLayoutCreateInfo ci{
                .sType = VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO,
                .pNext = nullptr,
                .flags = 0,
                .setLayoutCount = 1,
                .pSetLayouts = descriptor_set_layout.address(),
                .pushConstantRangeCount = 1,
                .pPushConstantRanges = &range,
            };
            pipeline_layout = device.GetLogical().CreatePipelineLayout(ci);
        }

        void MoonwitchColorGrading::CreatePipeline(const Device& device) {
            pipeline = CreateWrappedPipeline(device, renderpass, pipeline_layout,
                                             std::tie(vertex_shader, fragment_shader));
        }

        void MoonwitchColorGrading::UpdateDescriptorSet(const Device& device,
                                                        VkImageView source_image_view,
                                                        size_t image_index) {
            auto& image = images[image_index];
            std::vector<VkDescriptorImageInfo> image_infos;
            image_infos.reserve(1);
            std::vector<VkWriteDescriptorSet> updates{CreateWriteDescriptorSet(
                image_infos, *sampler, source_image_view, image.descriptor_sets[0], 0)};
            device.GetLogical().UpdateDescriptorSets(updates, {});
        }

        void MoonwitchColorGrading::UploadImages(const Device& device, Scheduler& scheduler) {
            if (images_ready) {
                return;
            }
            scheduler.Record([&](vk::CommandBuffer cmdbuf) {
                for (auto& image : images) {
                    ClearColorImage(cmdbuf, *image.image);
                }
            });
            scheduler.Finish();
            images_ready = true;
        }

        VkImageView MoonwitchColorGrading::Draw(const Device& device, Scheduler& scheduler,
                                                size_t image_index,
                                                VkImageView source_image_view) {
            auto& image = images[image_index];
            const s32 mode = std::clamp(
                Settings::values.moonwitch_color_grading_mode.GetValue(), 0, 8);
            const f32 strength = std::clamp(
                static_cast<f32>(Settings::values.moonwitch_color_grading_strength.GetValue()) /
                    100.0f,
                0.0f, 1.0f);
            const ColorGradingPushConstants push_constants{
                .mode = mode,
                .strength = strength,
            };

            UploadImages(device, scheduler);
            UpdateDescriptorSet(device, source_image_view, image_index);

            const VkImage output_image = *image.image;
            const VkFramebuffer framebuffer = *image.framebuffer;
            const VkRenderPass current_renderpass = *renderpass;
            const VkPipeline current_pipeline = *pipeline;
            const VkPipelineLayout current_layout = *pipeline_layout;
            const VkDescriptorSet descriptor_set = image.descriptor_sets[0];
            const VkExtent2D current_extent = extent;

            scheduler.RequestOutsideRenderPassOperationContext();
            scheduler.Record([=](vk::CommandBuffer cmdbuf) {
                TransitionImageLayout(cmdbuf, output_image, VK_IMAGE_LAYOUT_GENERAL);
                BeginRenderPass(cmdbuf, current_renderpass, framebuffer, current_extent);
                cmdbuf.BindPipeline(VK_PIPELINE_BIND_POINT_GRAPHICS, current_pipeline);
                cmdbuf.BindDescriptorSets(VK_PIPELINE_BIND_POINT_GRAPHICS, current_layout, 0,
                                          descriptor_set, {});
                cmdbuf.PushConstants(current_layout, VK_SHADER_STAGE_FRAGMENT_BIT,
                                     push_constants);
                cmdbuf.Draw(3, 1, 0, 0);
                cmdbuf.EndRenderPass();
                TransitionImageLayout(cmdbuf, output_image, VK_IMAGE_LAYOUT_GENERAL);
            });

            return *image.image_view;
        }

        bool MoonwitchColorGrading::NeedsRecreation(VkExtent2D new_extent) const {
            return new_extent.width != extent.width || new_extent.height != extent.height;
        }

        } // namespace Vulkan
    ''',
    "MoonwitchColorGrading::MoonwitchColorGrading",
    "create renderer implementation",
)

write_new(
    root / "src/video_core/host_shaders/moonwitch_color_grading.frag",
    r'''
        // SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
        // SPDX-License-Identifier: GPL-3.0-or-later

        #version 450

        layout(location = 0) in vec2 texcoord;
        layout(location = 0) out vec4 frag_color;

        layout(binding = 0) uniform sampler2D color_texture;

        layout(push_constant) uniform ColorGradingPushConstants {
            int mode;
            float strength;
        } grading;

        const vec3 LUMA = vec3(0.2126, 0.7152, 0.0722);

        vec3 change_saturation(vec3 color, float saturation) {
            float luminance = dot(color, LUMA);
            return mix(vec3(luminance), color, saturation);
        }

        vec3 change_contrast(vec3 color, float contrast) {
            return (color - vec3(0.5)) * contrast + vec3(0.5);
        }

        vec3 apply_grade(vec3 source, int mode) {
            float luminance = dot(source, LUMA);
            vec3 result = source;

            if (mode == 1) {
                // Vivid: stronger separation and color without crushing highlights.
                result = change_contrast(source, 1.08);
                result = change_saturation(result, 1.20);
                result *= vec3(1.025, 1.015, 0.985);
            } else if (mode == 2) {
                // Dark: deeper midtones, slightly cooler shadows.
                result = mix(source, source * source, 0.22);
                result = change_contrast(result, 1.10);
                result = change_saturation(result, 0.95);
                result *= vec3(0.95, 0.975, 1.01);
            } else if (mode == 3) {
                // Cinematic: restrained saturation with teal shadows and warm highlights.
                result = change_contrast(source, 1.10);
                result = change_saturation(result, 0.92);
                float shadows = 1.0 - smoothstep(0.12, 0.62, luminance);
                float highlights = smoothstep(0.42, 0.95, luminance);
                result += shadows * vec3(-0.022, 0.006, 0.025);
                result += highlights * vec3(0.026, 0.010, -0.018);
            } else if (mode == 4) {
                // Warm: golden highlights while retaining neutral blacks.
                float highlights = smoothstep(0.18, 0.92, luminance);
                result = change_saturation(source, 1.05);
                result *= mix(vec3(1.015, 1.0, 0.98), vec3(1.075, 1.025, 0.91), highlights);
            } else if (mode == 5) {
                // Cool: blue/cyan bias with a small contrast lift.
                result = change_contrast(source, 1.04);
                result = change_saturation(result, 1.03);
                result *= vec3(0.94, 1.005, 1.075);
            } else if (mode == 6) {
                // Moonlight: dark fantasy grade with blue shadows and muted warm channels.
                float shadows = 1.0 - smoothstep(0.16, 0.72, luminance);
                result = mix(source, source * source, 0.16);
                result = change_contrast(result, 1.08);
                result = change_saturation(result, 0.94);
                result *= vec3(0.89, 0.96, 1.09);
                result += shadows * vec3(-0.018, 0.008, 0.035);
            } else if (mode == 7) {
                // Monochrome: neutral luminance with a little extra definition.
                result = change_contrast(vec3(luminance), 1.07);
            } else if (mode == 8) {
                // HDR+: SDR-safe tone shaping that reveals shadow and highlight detail.
                float mapped_luminance = luminance +
                    0.72 * luminance * (1.0 - luminance) * (0.52 - luminance);
                float luminance_gain = mapped_luminance / max(luminance, 0.0001);
                result = source * luminance_gain;
                result = change_contrast(result, 1.04);
                result = change_saturation(result, 1.10);
                float highlights = smoothstep(0.62, 1.0, luminance);
                result = mix(result, result / (0.92 + 0.08 * result), 0.28 * highlights);
            }

            return clamp(result, 0.0, 1.0);
        }

        void main() {
            vec4 source = texture(color_texture, texcoord);
            vec3 graded = apply_grade(source.rgb, grading.mode);
            float amount = clamp(grading.strength, 0.0, 1.0);
            frag_color = vec4(mix(source.rgb, graded, amount), source.a);
        }
    ''',
    "ColorGradingPushConstants",
    "create color grading shader",
)

print(
    "Applied Moonwitch Color Grading: nine presets, HDR+ and live Quick Settings controls."
)
