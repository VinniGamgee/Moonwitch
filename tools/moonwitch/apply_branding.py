from pathlib import Path

ROOT = Path.cwd()

# Android identity: change the installable package immediately while preserving the
# internal org.yuzu.yuzu_emu namespace/JNI symbols for the first bring-up.
gradle = ROOT / "src/android/app/build.gradle.kts"
s = gradle.read_text(encoding="utf-8")
s = s.replace('applicationId = "dev.eden.eden_emulator"', 'applicationId = "dev.moonwitch.emulator"')
s = s.replace('applicationId = "dev.legacy.eden_emulator"', 'applicationId = "dev.moonwitch.emulator.legacy"')
s = s.replace('return "4.7.4"', 'return "0.1.0-alpha"')
s = s.replace('STORM EDEN', 'Moonwitch')
gradle.write_text(s, encoding="utf-8")

# Native/app branding and update target.
cmake = ROOT / "CMakeLists.txt"
s = cmake.read_text(encoding="utf-8")
s = s.replace('set(BUILD_AUTO_UPDATE_REPO "ReiKatari/STORM_EDEN")', 'set(BUILD_AUTO_UPDATE_REPO "VinniGamgee/Moonwitch")')
s = s.replace('set(REPO_NAME "STORM EDEN")', 'set(REPO_NAME "MOONWITCH")')
s = s.replace('set(BUILD_VERSION "4.7.4")', 'set(BUILD_VERSION "0.1.0-alpha")')
s = s.replace('set(BUILD_TAG "v4.7.4")', 'set(BUILD_TAG "v0.1.0-alpha")')
s = s.replace('set(BUILD_ID "4.7.4")', 'set(BUILD_ID "0.1.0-alpha")')
cmake.write_text(s, encoding="utf-8")

# Replace visible Storm branding across Android UI resources/source without
# rewriting Java/Kotlin package declarations or JNI symbols.
text_exts = {".kt", ".java", ".xml", ".cpp", ".h", ".hpp", ".kts", ".properties", ".txt", ".md", ".json"}
android_root = ROOT / "src/android"
for p in android_root.rglob("*"):
    if not p.is_file() or p.suffix.lower() not in text_exts:
        continue
    try:
        text = p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        continue
    new = text.replace("STORM EDEN", "Moonwitch").replace("Storm Eden", "Moonwitch")
    if new != text:
        p.write_text(new, encoding="utf-8")

# Add targeted Vulkan diagnostics for the intermittent Android initialization
# failure observed with multiViewport/maxViewports capability reporting.
vk = ROOT / "src/video_core/vulkan_common/vulkan_device.cpp"
s = vk.read_text(encoding="utf-8")
needle = '    const VkPhysicalDeviceLimits& limits{properties.properties.limits};\n'
insert = '''    const VkPhysicalDeviceLimits& limits{properties.properties.limits};\n#if defined(__ANDROID__)\n    LOG_WARNING(Render_Vulkan,\n                "[Moonwitch] Android Vulkan snapshot: multiViewport={}, maxViewports={}, apiVersion={}, vendorID={:#x}, deviceID={:#x}",\n                features.features.multiViewport, limits.maxViewports, properties.properties.apiVersion,\n                properties.properties.vendorID, properties.properties.deviceID);\n#endif\n'''
if needle not in s:
    raise SystemExit("Vulkan limits anchor not found")
s = s.replace(needle, insert, 1)
vk.write_text(s, encoding="utf-8")

# Project provenance/roadmap. Keep upstream licensing intact.
(ROOT / "MOONWITCH.md").write_text('''# Moonwitch\n\nMoonwitch is an Android-focused Nintendo Switch emulator fork derived from STORM EDEN / Eden.\n\nInitial base: STORM EDEN 4.7.4, commit `6da6709e28e240a17df138b3bee57f93aa75526d`.\n\n## Initial goals\n\n- Independent Android application identity (`dev.moonwitch.emulator`).\n- Original Moonwitch branding and UI direction.\n- Diagnose and fix intermittent Android Vulkan initialization failures.\n- Investigate The Legend of Zelda: Tears of the Kingdom foliage/instancing corruption.\n- Investigate UltraCam / TOTK Optimizer compatibility crashes.\n- Preserve upstream improvements while keeping Moonwitch-specific Android fixes isolated and reviewable.\n\n## License\n\nMoonwitch retains the licenses and copyright notices of the upstream source files. The project is distributed under the applicable GPL terms of its upstream components.\n''', encoding="utf-8")

print("Moonwitch 0.1.0-alpha branding and diagnostics applied")
