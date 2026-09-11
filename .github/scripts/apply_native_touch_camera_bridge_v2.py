#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def write(rel, text):
    (ROOT / rel).write_text(text, encoding="utf-8")


def replace_once(rel, old, new, label):
    text = read(rel)
    if new in text:
        return
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match in {rel}, found {count}")
    write(rel, text.replace(old, new, 1))


def patch_native_cpp():
    rel = "src/android/app/src/main/jni/native_input.cpp"
    text = read(rel)

    include_anchor = "#include <cmath>\n"
    include_block = '''#include <algorithm>\n#include <array>\n#include <cmath>\n#include <cstring>\n#include <optional>\n#include <vector>\n'''
    if "#include <optional>" not in text:
        if include_anchor not in text:
            raise RuntimeError("native_input.cpp: v1 cmath include not found")
        text = text.replace(include_anchor, include_block, 1)

    header_anchor = '#include "hid_core/frontend/emulated_devices.h"\n'
    core_headers = '''#include "core/hle/kernel/k_memory_block.h"\n#include "core/hle/kernel/k_process.h"\n#include "core/hle/kernel/k_process_page_table.h"\n#include "core/hle/kernel/svc_types.h"\n#include "core/memory.h"\n#include "hid_core/frontend/emulated_devices.h"\n'''
    if '#include "core/hle/kernel/k_memory_block.h"' not in text:
        if header_anchor not in text:
            raise RuntimeError("native_input.cpp: v1 emulated_devices include not found")
        text = text.replace(header_anchor, core_headers, 1)

    begin_marker = "// MOONWITCH_NATIVE_TOUCH_CAMERA_BEGIN\n"
    end_marker = "// MOONWITCH_NATIVE_TOUCH_CAMERA_END\n"
    start = text.find(begin_marker)
    end = text.find(end_marker)
    if start < 0 or end < 0 or end <= start:
        raise RuntimeError("native_input.cpp: native camera markers missing")
    end += len(end_marker)

    block = r'''// MOONWITCH_NATIVE_TOUCH_CAMERA_BEGIN
// Host-side TouchLook source. Android supplies only MotionEvent deltas. The global HID mouse
// remains available for games that consume mouse natively. A guest adapter may additionally
// expose the Moonwitch bridge packet below; this is still a relative pointer stream and never
// passes through Npad, VirtualGamepad, an analog center, radius, deadzone, or stick magnitude.
static bool moonwitch_native_touch_camera_active = false;

namespace {
constexpr u64 MOONWITCH_TOUCH_BRIDGE_MAGIC_A = 0x3245474449524254ULL; // "TBRIDGE2"
constexpr u64 MOONWITCH_TOUCH_BRIDGE_MAGIC_B = 0x324D41434354574DULL; // "MWTCCAM2"
constexpr u32 MOONWITCH_TOUCH_BRIDGE_VERSION = 2;
constexpr std::size_t MOONWITCH_TOUCH_BRIDGE_SCAN_CHUNK = 256 * 1024;

#pragma pack(push, 1)
struct MoonwitchTouchBridgePacket {
    u64 magic_a;
    u64 magic_b;
    u32 version;
    u32 sequence;
    f32 total_x;
    f32 total_y;
    u32 enabled;
    u32 reserved;
};
#pragma pack(pop)
static_assert(sizeof(MoonwitchTouchBridgePacket) == 40);

std::optional<Common::ProcessAddress> moonwitch_touch_bridge_address;
f32 moonwitch_touch_bridge_total_x = 0.0f;
f32 moonwitch_touch_bridge_total_y = 0.0f;
u32 moonwitch_touch_bridge_sequence = 0;

bool MoonwitchTouchBridgeMatches(Core::Memory::Memory& memory, Common::ProcessAddress address) {
    MoonwitchTouchBridgePacket packet{};
    if (!memory.ReadBlock(address, &packet, sizeof(packet))) {
        return false;
    }
    return packet.magic_a == MOONWITCH_TOUCH_BRIDGE_MAGIC_A &&
           packet.magic_b == MOONWITCH_TOUCH_BRIDGE_MAGIC_B &&
           packet.version == MOONWITCH_TOUCH_BRIDGE_VERSION;
}

std::optional<Common::ProcessAddress> MoonwitchFindTouchBridge(Core::System& system) {
    auto* process = system.ApplicationProcess();
    if (process == nullptr) {
        return std::nullopt;
    }

    auto& page_table = process->GetPageTable();
    auto& memory = system.ApplicationMemory();
    const u64 aslr_start = GetInteger(page_table.GetAliasCodeRegionStart());
    const u64 aslr_end = aslr_start + page_table.GetAliasCodeRegionSize();

    const std::array<u8, 16> needle{
        0x54, 0x42, 0x52, 0x49, 0x44, 0x47, 0x45, 0x32,
        0x4D, 0x57, 0x54, 0x43, 0x43, 0x41, 0x4D, 0x32,
    };
    std::vector<u8> buffer(MOONWITCH_TOUCH_BRIDGE_SCAN_CHUNK);
    Kernel::Svc::PageInfo page_info{};

    u64 query_address = aslr_start;
    while (query_address < aslr_end) {
        Kernel::KMemoryInfo info{};
        const auto result = page_table.QueryInfo(&info, &page_info,
                                                  Kernel::KProcessAddress{query_address});
        if (result.IsFailure()) {
            break;
        }

        const u64 region_start = std::max<u64>(query_address, info.GetAddress());
        const u64 region_end = std::min<u64>(aslr_end, info.GetEndAddress());
        const auto state = info.GetState();
        const bool module_data = state == Kernel::KMemoryState::CodeData ||
                                 state == Kernel::KMemoryState::AliasCodeData;

        if (module_data && region_end > region_start) {
            for (u64 cursor = region_start; cursor < region_end;) {
                const std::size_t amount = static_cast<std::size_t>(
                    std::min<u64>(MOONWITCH_TOUCH_BRIDGE_SCAN_CHUNK, region_end - cursor));
                if (amount >= needle.size() &&
                    memory.ReadBlock(Common::ProcessAddress{cursor}, buffer.data(), amount)) {
                    const auto first = buffer.begin();
                    const auto last = first + static_cast<std::ptrdiff_t>(amount);
                    const auto hit = std::search(first, last, needle.begin(), needle.end());
                    if (hit != last) {
                        const u64 offset = static_cast<u64>(std::distance(first, hit));
                        const Common::ProcessAddress candidate{cursor + offset};
                        if (MoonwitchTouchBridgeMatches(memory, candidate)) {
                            return candidate;
                        }
                    }
                }
                cursor += amount;
            }
        }

        const u64 next = info.GetEndAddress();
        if (next <= query_address) {
            break;
        }
        query_address = next;
    }

    return std::nullopt;
}

void MoonwitchPublishTouchBridge(bool enabled, f32 delta_x, f32 delta_y) {
    if (!EmulationSession::GetInstance().IsRunning()) {
        moonwitch_touch_bridge_address.reset();
        return;
    }

    auto& system = EmulationSession::GetInstance().System();
    auto& memory = system.ApplicationMemory();

    moonwitch_touch_bridge_total_x += delta_x;
    moonwitch_touch_bridge_total_y += delta_y;
    ++moonwitch_touch_bridge_sequence;

    if (moonwitch_touch_bridge_address &&
        !MoonwitchTouchBridgeMatches(memory, *moonwitch_touch_bridge_address)) {
        moonwitch_touch_bridge_address.reset();
    }
    if (!moonwitch_touch_bridge_address) {
        moonwitch_touch_bridge_address = MoonwitchFindTouchBridge(system);
    }
    if (!moonwitch_touch_bridge_address) {
        return;
    }

    const MoonwitchTouchBridgePacket packet{
        .magic_a = MOONWITCH_TOUCH_BRIDGE_MAGIC_A,
        .magic_b = MOONWITCH_TOUCH_BRIDGE_MAGIC_B,
        .version = MOONWITCH_TOUCH_BRIDGE_VERSION,
        .sequence = moonwitch_touch_bridge_sequence,
        .total_x = moonwitch_touch_bridge_total_x,
        .total_y = moonwitch_touch_bridge_total_y,
        .enabled = enabled ? 1u : 0u,
        .reserved = 0u,
    };
    memory.WriteBlock(*moonwitch_touch_bridge_address, &packet, sizeof(packet));
}
} // namespace

void Java_org_yuzu_yuzu_1emu_features_input_NativeInput_onNativeTouchCameraBegin(
    JNIEnv* env, jobject j_obj) {
    moonwitch_native_touch_camera_active = EmulationSession::GetInstance().IsRunning();
    if (!moonwitch_native_touch_camera_active) {
        return;
    }
    auto* devices = EmulationSession::GetInstance().System().HIDCore().GetEmulatedDevices();
    devices->ConsumeMouseRelativeDelta();
    MoonwitchPublishTouchBridge(true, 0.0f, 0.0f);
}

void Java_org_yuzu_yuzu_1emu_features_input_NativeInput_onNativeTouchCameraDelta(
    JNIEnv* env, jobject j_obj, jfloat j_delta_x, jfloat j_delta_y) {
    if (!moonwitch_native_touch_camera_active || !EmulationSession::GetInstance().IsRunning()) {
        return;
    }

    // Preserve the Android delta as floating point for guest adapters. HID mouse additionally
    // receives the nearest integer because the Switch HID mouse ABI stores signed integer deltas.
    MoonwitchPublishTouchBridge(true, static_cast<f32>(j_delta_x), static_cast<f32>(j_delta_y));

    const auto delta_x = static_cast<s32>(std::lround(j_delta_x));
    const auto delta_y = static_cast<s32>(std::lround(j_delta_y));
    if (delta_x == 0 && delta_y == 0) {
        return;
    }

    auto* devices = EmulationSession::GetInstance().System().HIDCore().GetEmulatedDevices();
    devices->AddMouseRelativeDelta(delta_x, delta_y);
}

void Java_org_yuzu_yuzu_1emu_features_input_NativeInput_onNativeTouchCameraEnd(
    JNIEnv* env, jobject j_obj) {
    moonwitch_native_touch_camera_active = false;
    if (!EmulationSession::GetInstance().IsRunning()) {
        moonwitch_touch_bridge_address.reset();
        return;
    }
    MoonwitchPublishTouchBridge(false, 0.0f, 0.0f);
    auto* devices = EmulationSession::GetInstance().System().HIDCore().GetEmulatedDevices();
    devices->ConsumeMouseRelativeDelta();
}
// MOONWITCH_NATIVE_TOUCH_CAMERA_END
'''

    text = text[:start] + block + text[end:]
    write(rel, text)


def validate():
    rel = "src/android/app/src/main/jni/native_input.cpp"
    text = read(rel)
    start = text.index("// MOONWITCH_NATIVE_TOUCH_CAMERA_BEGIN")
    end = text.index("// MOONWITCH_NATIVE_TOUCH_CAMERA_END")
    segment = text[start:end]

    required = [
        "MOONWITCH_TOUCH_BRIDGE_MAGIC_A",
        "MoonwitchFindTouchBridge",
        "MoonwitchPublishTouchBridge",
        "GetAliasCodeRegionStart",
        "ApplicationMemory().WriteBlock",
        "AddMouseRelativeDelta",
    ]
    for token in required:
        if token not in segment:
            raise RuntimeError(f"native bridge v2 missing required token: {token}")

    forbidden = [
        "VirtualGamepad",
        "Npad",
        "RightStick",
        "SetStickPosition",
        "AnalogStick",
    ]
    for token in forbidden:
        if token in segment:
            raise RuntimeError(f"native bridge v2 accidentally contains gamepad token: {token}")


if __name__ == "__main__":
    patch_native_cpp()
    validate()
    print("Moonwitch native TouchLook bridge v2 applied: relative touch -> HID + guest memory adapter")
