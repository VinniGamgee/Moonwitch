#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path


def replace_once(path: Path, old: str, new: str, marker: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if marker in text:
        print(f"[moonwitch-shader-cache-import] {label}: already patched")
        return
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one anchor for {label}, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"[moonwitch-shader-cache-import] {label}: patched")


root = Path(".")
pipeline_cache = root / "src/video_core/renderer_vulkan/vk_pipeline_cache.cpp"


replace_once(
    pipeline_cache,
    "#include <memory>\n",
    "#include <memory>\n"
    "#include <filesystem>\n"
    "#include <limits>\n"
    "#include <optional>\n"
    "#include <string>\n"
    "#include <string_view>\n"
    "#include <type_traits>\n"
    "#include <system_error>\n",
    "#include <string_view>",
    "include importer support types",
)


anchor = """Shader::Profile ShaderProfileForPrecisionMode(const Shader::Profile& base_profile,
                                               u64 mode) {
    Shader::Profile shader_profile{base_profile};
    shader_profile.moonwitch_shader_precision_mode =
        static_cast<u32>(std::min<u64>(mode, 2));
    return shader_profile;
}
"""

implementation = r'''

// Moonwitch external shader-cache importer. CACHE_VERSION 18 used the same serialized
// environments as version 19, but its pipeline keys did not contain the live precision mode.
constexpr u32 LEGACY_TRANSFERABLE_CACHE_VERSION = 18;
constexpr std::array<char, 8> TRANSFERABLE_CACHE_MAGIC_NUMBER{
    'y', 'u', 'z', 'u', 'c', 'a', 'c', 'h'};
constexpr u32 MAX_PIPELINE_ENVIRONMENTS = 6;
constexpr u64 MAX_SERIALIZED_SHADER_CODE_SIZE = 16ULL * 1024 * 1024;
constexpr u64 MAX_SERIALIZED_MAP_ENTRIES = 1U << 20;

struct LegacyComputePipelineCacheKeyV18 {
    u64 unique_hash;
    u32 shared_memory_size;
    std::array<u32, 3> workgroup_size;
};

struct LegacyGraphicsPipelineCacheKeyV18 {
    std::array<u64, 6> unique_hashes;
    FixedPipelineState state;
};

static_assert(std::is_trivially_copyable_v<LegacyComputePipelineCacheKeyV18>);
static_assert(std::is_trivially_copyable_v<LegacyGraphicsPipelineCacheKeyV18>);
static_assert(sizeof(ComputePipelineCacheKey) ==
              sizeof(LegacyComputePipelineCacheKeyV18) + sizeof(u64));
static_assert(sizeof(GraphicsPipelineCacheKey) ==
              sizeof(LegacyGraphicsPipelineCacheKeyV18) + sizeof(u64));

std::filesystem::path NextCacheBackupPath(const std::filesystem::path& filename,
                                          std::string_view suffix) {
    for (u32 index = 0; index < 1000; ++index) {
        auto candidate{filename};
        candidate += suffix;
        if (index != 0) {
            candidate += "." + std::to_string(index);
        }
        std::error_code error;
        if (!std::filesystem::exists(candidate, error)) {
            return candidate;
        }
    }
    auto fallback{filename};
    fallback += ".moonwitch-cache-backup";
    return fallback;
}

bool QuarantineCacheFile(const std::filesystem::path& filename, std::string_view suffix,
                         std::string_view reason) {
    std::error_code error;
    if (!std::filesystem::exists(filename, error)) {
        return true;
    }
    const auto backup{NextCacheBackupPath(filename, suffix)};
    if (!Common::FS::RenameFile(filename, backup)) {
        LOG_ERROR(Common_Filesystem,
                  "Moonwitch could not preserve incompatible cache {} ({})",
                  Common::FS::PathToUTF8String(filename), reason);
        return false;
    }
    LOG_WARNING(Common_Filesystem,
                "Moonwitch preserved incompatible cache as {} ({})",
                Common::FS::PathToUTF8String(backup), reason);
    return true;
}

template <typename T>
bool ReadCacheValue(std::ifstream& file, T& value) {
    static_assert(std::is_trivially_copyable_v<T>);
    file.read(reinterpret_cast<char*>(&value), sizeof(value));
    return static_cast<bool>(file);
}

bool SkipCacheBytes(std::ifstream& file, std::ifstream::pos_type end, u64 bytes) {
    const auto current{file.tellg()};
    if (current == std::ifstream::pos_type{-1} || current > end) {
        return false;
    }
    const auto remaining{end - current};
    if (remaining < 0 || bytes > static_cast<u64>(remaining) ||
        bytes > static_cast<u64>((std::numeric_limits<std::streamoff>::max)())) {
        return false;
    }
    file.seekg(static_cast<std::streamoff>(bytes), std::ios::cur);
    return static_cast<bool>(file);
}

bool SkipCacheTable(std::ifstream& file, std::ifstream::pos_type end, u64 count,
                    u64 element_size) {
    if (count > MAX_SERIALIZED_MAP_ENTRIES ||
        (element_size != 0 && count > (std::numeric_limits<u64>::max)() / element_size)) {
        return false;
    }
    return SkipCacheBytes(file, end, count * element_size);
}

std::optional<Shader::Stage> SkipSerializedEnvironment(std::ifstream& file,
                                                       std::ifstream::pos_type end) {
    u64 code_size{};
    u64 num_texture_types{};
    u64 num_texture_pixel_formats{};
    u64 num_cbuf_values{};
    u64 num_cbuf_replacement_values{};
    u32 ignored{};
    Shader::Stage stage{};

    if (!ReadCacheValue(file, code_size) || !ReadCacheValue(file, num_texture_types) ||
        !ReadCacheValue(file, num_texture_pixel_formats) ||
        !ReadCacheValue(file, num_cbuf_values) ||
        !ReadCacheValue(file, num_cbuf_replacement_values) ||
        !ReadCacheValue(file, ignored) || // local memory size
        !ReadCacheValue(file, ignored) || // texture-bound buffer
        !ReadCacheValue(file, ignored) || // start address
        !ReadCacheValue(file, ignored) || // cached low address
        !ReadCacheValue(file, ignored) || // cached high address
        !ReadCacheValue(file, ignored) || // viewport transform state
        !ReadCacheValue(file, stage)) {
        return std::nullopt;
    }

    if (code_size == 0 || code_size > MAX_SERIALIZED_SHADER_CODE_SIZE ||
        code_size % sizeof(u64) != 0 || !SkipCacheBytes(file, end, code_size) ||
        !SkipCacheTable(file, end, num_texture_types,
                        sizeof(u32) + sizeof(Shader::TextureType)) ||
        !SkipCacheTable(file, end, num_texture_pixel_formats,
                        sizeof(u32) + sizeof(Shader::TexturePixelFormat)) ||
        !SkipCacheTable(file, end, num_cbuf_values, sizeof(u64) + sizeof(u32)) ||
        !SkipCacheTable(file, end, num_cbuf_replacement_values,
                        sizeof(u64) + sizeof(Shader::ReplaceConstant))) {
        return std::nullopt;
    }

    switch (stage) {
    case Shader::Stage::Compute:
        if (!SkipCacheBytes(file, end, sizeof(std::array<u32, 3>) + sizeof(u32))) {
            return std::nullopt;
        }
        break;
    case Shader::Stage::VertexB:
    case Shader::Stage::TessellationControl:
    case Shader::Stage::TessellationEval:
    case Shader::Stage::Fragment:
    case Shader::Stage::VertexA:
        if (!SkipCacheBytes(file, end, sizeof(Shader::ProgramHeader))) {
            return std::nullopt;
        }
        break;
    case Shader::Stage::Geometry:
        if (!SkipCacheBytes(file, end,
                            sizeof(Shader::ProgramHeader) + sizeof(std::array<u32, 8>))) {
            return std::nullopt;
        }
        break;
    default:
        return std::nullopt;
    }
    return stage;
}

bool CopyCacheBytes(std::ifstream& input, std::ofstream& output, u64 bytes) {
    std::array<char, 64 * 1024> buffer{};
    while (bytes != 0) {
        const auto chunk{static_cast<std::streamsize>(
            std::min<u64>(bytes, static_cast<u64>(buffer.size())))};
        input.read(buffer.data(), chunk);
        if (!input) {
            return false;
        }
        output.write(buffer.data(), chunk);
        if (!output) {
            return false;
        }
        bytes -= static_cast<u64>(chunk);
    }
    return true;
}

bool MigrateTransferableCacheV18(const std::filesystem::path& filename,
                                 u64 shader_precision_mode) {
    std::ifstream input(filename, std::ios::binary | std::ios::ate);
    if (!input.is_open()) {
        return false;
    }
    const auto end{input.tellg()};
    input.seekg(0, std::ios::beg);

    std::array<char, 8> magic{};
    u32 version{};
    input.read(magic.data(), magic.size());
    if (!input || !ReadCacheValue(input, version) ||
        magic != TRANSFERABLE_CACHE_MAGIC_NUMBER ||
        version != LEGACY_TRANSFERABLE_CACHE_VERSION) {
        return false;
    }

    auto temporary{filename};
    temporary += ".moonwitch-import.tmp";
    std::error_code error;
    if (std::filesystem::exists(temporary, error)) {
        Common::FS::RemoveFile(temporary);
    }
    std::ofstream output(temporary, std::ios::binary | std::ios::trunc);
    if (!output.is_open()) {
        return false;
    }
    output.write(TRANSFERABLE_CACHE_MAGIC_NUMBER.data(),
                 TRANSFERABLE_CACHE_MAGIC_NUMBER.size());
    output.write(reinterpret_cast<const char*>(&CACHE_VERSION), sizeof(CACHE_VERSION));

    size_t migrated_pipelines{};
    bool valid{static_cast<bool>(output)};
    while (valid && input.tellg() != end) {
        const auto record_start{input.tellg()};
        if (record_start == std::ifstream::pos_type{-1} || record_start > end) {
            valid = false;
            break;
        }

        u32 num_envs{};
        if (!ReadCacheValue(input, num_envs) || num_envs == 0 ||
            num_envs > MAX_PIPELINE_ENVIRONMENTS) {
            valid = false;
            break;
        }

        bool is_compute{};
        for (u32 index = 0; index < num_envs; ++index) {
            const auto stage{SkipSerializedEnvironment(input, end)};
            if (!stage) {
                valid = false;
                break;
            }
            const bool environment_is_compute{*stage == Shader::Stage::Compute};
            if (index == 0) {
                is_compute = environment_is_compute;
            } else if (is_compute != environment_is_compute) {
                valid = false;
                break;
            }
        }
        if (!valid || (is_compute && num_envs != 1)) {
            valid = false;
            break;
        }

        const auto key_start{input.tellg()};
        if (key_start == std::ifstream::pos_type{-1} || key_start < record_start) {
            valid = false;
            break;
        }

        if (is_compute) {
            LegacyComputePipelineCacheKeyV18 legacy_key{};
            if (!ReadCacheValue(input, legacy_key)) {
                valid = false;
                break;
            }
            const auto record_end{input.tellg()};
            const ComputePipelineCacheKey current_key{
                .unique_hash = legacy_key.unique_hash,
                .moonwitch_shader_precision_mode = shader_precision_mode,
                .shared_memory_size = legacy_key.shared_memory_size,
                .workgroup_size = legacy_key.workgroup_size,
            };
            input.seekg(record_start);
            valid = CopyCacheBytes(input, output, static_cast<u64>(key_start - record_start));
            output.write(reinterpret_cast<const char*>(&current_key), sizeof(current_key));
            valid = valid && static_cast<bool>(output);
            input.seekg(record_end);
        } else {
            LegacyGraphicsPipelineCacheKeyV18 legacy_key{};
            if (!ReadCacheValue(input, legacy_key)) {
                valid = false;
                break;
            }
            const auto record_end{input.tellg()};
            const GraphicsPipelineCacheKey current_key{
                .unique_hashes = legacy_key.unique_hashes,
                .moonwitch_shader_precision_mode = shader_precision_mode,
                .state = legacy_key.state,
            };
            input.seekg(record_start);
            valid = CopyCacheBytes(input, output, static_cast<u64>(key_start - record_start));
            output.write(reinterpret_cast<const char*>(&current_key), sizeof(current_key));
            valid = valid && static_cast<bool>(output);
            input.seekg(record_end);
        }
        valid = valid && static_cast<bool>(input) && input.tellg() <= end;
        ++migrated_pipelines;
    }

    output.flush();
    valid = valid && static_cast<bool>(output) && input.tellg() == end;
    output.close();
    input.close();
    if (!valid) {
        Common::FS::RemoveFile(temporary);
        LOG_ERROR(Common_Filesystem,
                  "Moonwitch rejected malformed external shader cache {}",
                  Common::FS::PathToUTF8String(filename));
        return false;
    }

    const auto backup{NextCacheBackupPath(filename, ".v18.bak")};
    if (!Common::FS::RenameFile(filename, backup)) {
        Common::FS::RemoveFile(temporary);
        return false;
    }
    if (!Common::FS::RenameFile(temporary, filename)) {
        Common::FS::RenameFile(backup, filename);
        Common::FS::RemoveFile(temporary);
        return false;
    }

    LOG_INFO(Common_Filesystem,
             "Moonwitch imported {} external shader pipelines from cache v18 to v19 "
             "using precision mode {}; original preserved as {}",
             migrated_pipelines, shader_precision_mode,
             Common::FS::PathToUTF8String(backup));
    return true;
}

bool PrepareTransferablePipelineCache(const std::filesystem::path& filename) {
    std::ifstream file(filename, std::ios::binary);
    if (!file.is_open()) {
        return true;
    }
    std::array<char, 8> magic{};
    u32 version{};
    file.read(magic.data(), magic.size());
    const bool header_valid{static_cast<bool>(file) && ReadCacheValue(file, version)};
    file.close();

    if (!header_valid || magic != TRANSFERABLE_CACHE_MAGIC_NUMBER) {
        return QuarantineCacheFile(filename, ".invalid.bak",
                                   "invalid transferable-cache header");
    }
    if (version == CACHE_VERSION) {
        return true;
    }
    if (version == LEGACY_TRANSFERABLE_CACHE_VERSION && CACHE_VERSION == 19) {
        if (MigrateTransferableCacheV18(filename, CurrentShaderPrecisionMode())) {
            return true;
        }
        return QuarantineCacheFile(filename, ".v18.migration-failed.bak",
                                   "malformed or unsupported v18 transferable cache");
    }

    const std::string suffix{".v" + std::to_string(version) + ".unsupported.bak"};
    return QuarantineCacheFile(filename, suffix, "unsupported transferable-cache version");
}
'''

replace_once(
    pipeline_cache,
    anchor,
    anchor + implementation,
    "MigrateTransferableCacheV18",
    "add validated v18-to-v19 importer",
)


replace_once(
    pipeline_cache,
    '    pipeline_cache_filename = base_dir / "vulkan.bin";\n\n'
    "    if (use_vulkan_pipeline_cache) {\n",
    '    pipeline_cache_filename = base_dir / "vulkan.bin";\n'
    "    if (!PrepareTransferablePipelineCache(pipeline_cache_filename)) {\n"
    "        // Preserve the user's file if storage permissions prevent a safe backup.\n"
    "        pipeline_cache_filename.clear();\n"
    "    }\n\n"
    "    if (use_vulkan_pipeline_cache) {\n",
    "if (!PrepareTransferablePipelineCache(pipeline_cache_filename))",
    "run importer before disk-cache loading",
)


old_driver_rejection = '''        if (magic_number != VULKAN_CACHE_MAGIC_NUMBER || cache_version != expected_cache_version) {
            file.close();
            if (Common::FS::RemoveFile(filename)) {
                if (magic_number != VULKAN_CACHE_MAGIC_NUMBER) {
                    LOG_ERROR(Common_Filesystem, "Invalid Vulkan driver pipeline cache file");
                }
                if (cache_version != expected_cache_version) {
                    LOG_INFO(Common_Filesystem, "Deleting old Vulkan driver pipeline cache");
                }
            } else {
                LOG_ERROR(Common_Filesystem,
                          "Invalid Vulkan pipeline cache file and failed to delete it in \\"{}\\"",
                          Common::FS::PathToUTF8String(filename));
            }
            return create_pipeline_cache(0, nullptr);
        }
'''

new_driver_rejection = '''        if (magic_number != VULKAN_CACHE_MAGIC_NUMBER || cache_version != expected_cache_version) {
            file.close();
            QuarantineCacheFile(filename, ".driver-incompatible.bak",
                                magic_number != VULKAN_CACHE_MAGIC_NUMBER
                                    ? "invalid Vulkan driver-cache header"
                                    : "unsupported Vulkan driver-cache version");
            return create_pipeline_cache(0, nullptr);
        }
'''

replace_once(
    pipeline_cache,
    old_driver_rejection,
    new_driver_rejection,
    'QuarantineCacheFile(filename, ".driver-incompatible.bak"',
    "preserve rejected Vulkan driver cache",
)


old_driver_catch = '''    } catch (const std::ios_base::failure& e) {
        LOG_ERROR(Common_Filesystem, "{}", e.what());
        if (!Common::FS::RemoveFile(filename)) {
            LOG_ERROR(Common_Filesystem, "Failed to delete Vulkan driver pipeline cache file {}",
                      Common::FS::PathToUTF8String(filename));
        }

        return create_pipeline_cache(0, nullptr);
    }
}
'''

new_driver_catch = '''    } catch (const std::ios_base::failure& e) {
        LOG_ERROR(Common_Filesystem, "{}", e.what());
        QuarantineCacheFile(filename, ".driver-corrupt.bak",
                            "truncated or corrupt Vulkan driver cache");
        return create_pipeline_cache(0, nullptr);
    } catch (const vk::Exception& e) {
        LOG_WARNING(Common_Filesystem,
                    "Vulkan driver rejected external pipeline cache {}: {}",
                    Common::FS::PathToUTF8String(filename), e.what());
        QuarantineCacheFile(filename, ".driver-rejected.bak",
                            "GPU or driver rejected Vulkan pipeline data");
        return create_pipeline_cache(0, nullptr);
    }
}
'''

replace_once(
    pipeline_cache,
    old_driver_catch,
    new_driver_catch,
    "GPU or driver rejected Vulkan pipeline data",
    "recover from GPU-specific driver-cache rejection",
)


print("Applied Moonwitch external shader-cache import and preservation.")
