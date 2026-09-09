#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LAB="$ROOT/turnip-p5"
WORK="$LAB/work"
OUT="$LAB/out"
MESA="$WORK/mesa"

# T30 binary identifies itself as Mesa 26.3.0-devel (git-62ac221a33), Android
# NDK r28b, API/Android 35.  P5-T1 pins those pieces to keep the first A/B
# comparison as close to the known-fast T30 as practical.
MESA_COMMIT="62ac221a33"
NDK_NAME="android-ndk-r28b"
NDK_URL="https://dl.google.com/android/repository/${NDK_NAME}-linux.zip"
ANDROID_API="35"
DRIVER_NAME="vulkan.moonwitch_p5.so"
PACKAGE_NAME="Moonwitch-Turnip-P5-T1.zip"

rm -rf "$WORK" "$OUT"
mkdir -p "$WORK" "$OUT"

printf '[p5-t1] Fetching NDK r28b...\n'
curl -fL --retry 3 --retry-delay 2 "$NDK_URL" -o "$WORK/ndk.zip"
unzip -q "$WORK/ndk.zip" -d "$WORK"
NDK="$WORK/$NDK_NAME/toolchains/llvm/prebuilt/linux-x86_64/bin"

printf '[p5-t1] Fetching exact T30 Mesa base %s...\n' "$MESA_COMMIT"
git init -q "$MESA"
git -C "$MESA" remote add origin https://gitlab.freedesktop.org/mesa/mesa.git
git -C "$MESA" fetch --depth=1 origin "$MESA_COMMIT"
git -C "$MESA" checkout -q --detach FETCH_HEAD
BASE_FULL="$(git -C "$MESA" rev-parse HEAD)"
printf '[p5-t1] Mesa base: %s\n' "$BASE_FULL"

# Mesa/Android stub compatibility fixes used only when the checked-out source
# still has the older forms. They are build-environment fixes, not performance
# or rendering changes.
sed -i 's/typedef const native_handle_t\* buffer_handle_t;/typedef void\* buffer_handle_t;/g' \
  "$MESA/include/android_stub/cutils/native_handle.h" 2>/dev/null || true
sed -i 's/, hnd->handle/, (void *)hnd->handle/g' \
  "$MESA/src/util/u_gralloc/u_gralloc_fallback.c" 2>/dev/null || true
sed -i -E 's/([a-z_]+)->handle->/((const native_handle_t *)\1->handle)->/g' \
  "$MESA/src/vulkan/runtime/vk_android.c" 2>/dev/null || true

python3 "$LAB/apply_t1_totk_fixes.py" "$MESA"

# Preserve the patched source diff in CI output/manifest.  This is deliberately
# expected to contain only compatibility scaffolding plus the two P5-T1 toggles.
git -C "$MESA" diff -- src/freedreno/vulkan/tu_device.cc | tee "$OUT/P5-T1-TOTK.patch"

cat > "$MESA/android-aarch64.txt" <<EOF
[binaries]
ar = '$NDK/llvm-ar'
c = ['ccache', '$NDK/aarch64-linux-android${ANDROID_API}-clang']
cpp = ['ccache', '$NDK/aarch64-linux-android${ANDROID_API}-clang++', '-fno-exceptions', '-fno-unwind-tables', '-fno-asynchronous-unwind-tables', '--start-no-unused-arguments', '-static-libstdc++', '--end-no-unused-arguments']
c_ld = '$NDK/ld.lld'
cpp_ld = '$NDK/ld.lld'
strip = '$NDK/llvm-strip'
pkg-config = ['env', 'PKG_CONFIG_LIBDIR=$WORK/pkg-config', '/usr/bin/pkg-config']

[host_machine]
system = 'android'
cpu_family = 'aarch64'
cpu = 'armv8'
endian = 'little'
EOF

cat > "$MESA/native.txt" <<EOF
[build_machine]
c = ['ccache', 'clang']
cpp = ['ccache', 'clang++']
ar = 'llvm-ar'
strip = 'llvm-strip'
c_ld = 'ld.lld'
cpp_ld = 'ld.lld'
system = 'linux'
cpu_family = 'x86_64'
cpu = 'x86_64'
endian = 'little'
EOF

export CC=clang
export CXX=clang++
export AR=llvm-ar
export RANLIB=llvm-ranlib
export STRIP=llvm-strip
export PATH="$NDK:$PATH"

# T1 intentionally avoids Apex's GCM/cache/suballocator/scheduling deltas and
# avoids speculative CPU-specific flags. Meson's release profile supplies O3;
# this lets the first phone test answer one question: do the Zelda correctness
# switches fix graphics while keeping a T30-like base stable?
printf '[p5-t1] Configuring Mesa...\n'
cd "$MESA"
meson setup build-android-aarch64 \
  --cross-file android-aarch64.txt \
  --native-file native.txt \
  --prefix "$WORK/install" \
  -Dbuildtype=release \
  -Db_ndebug=true \
  -Dstrip=false \
  -Dplatforms=android \
  -Dplatform-sdk-version="$ANDROID_API" \
  -Dandroid-stub=true \
  -Dvideo-codecs= \
  -Dgallium-drivers= \
  -Dvulkan-drivers=freedreno \
  -Dvulkan-beta=true \
  -Dfreedreno-kmds=kgsl \
  -Degl=disabled \
  -Dandroid-libbacktrace=disabled

printf '[p5-t1] Building Turnip...\n'
ninja -C build-android-aarch64 install

SRC_SO="$WORK/install/lib/libvulkan_freedreno.so"
if [[ ! -f "$SRC_SO" ]]; then
  echo '[p5-t1] ERROR: libvulkan_freedreno.so was not produced.' >&2
  exit 1
fi

# Keep an unstripped twin for address-to-symbol crash analysis, but install a
# stripped phone package. This gives us proper post-mortem tools without paying
# the debug-size cost on-device.
cp "$SRC_SO" "$OUT/vulkan.moonwitch_p5.debug.so"
cp "$SRC_SO" "$OUT/$DRIVER_NAME"
"$NDK/llvm-strip" --strip-unneeded "$OUT/$DRIVER_NAME"
patchelf --set-soname "$DRIVER_NAME" "$OUT/$DRIVER_NAME"

# Binary guards.
file "$OUT/$DRIVER_NAME"
readelf -h "$OUT/$DRIVER_NAME" | grep -q 'AArch64'
readelf -d "$OUT/$DRIVER_NAME" | grep -q "$DRIVER_NAME"
strings -a "$OUT/$DRIVER_NAME" | grep -q 'tu_dont_care_as_load'
strings -a "$OUT/$DRIVER_NAME" | grep -q 'tu_allow_oob_indirect_ubo_loads'
strings -a "$OUT/$DRIVER_NAME" | grep -q 'cmdbuf_start_a725_quirk'

VERSION="$(cat "$MESA/VERSION" | tr -d '\n')"
SO_SHA="$(sha256sum "$OUT/$DRIVER_NAME" | awk '{print $1}')"
DEBUG_SHA="$(sha256sum "$OUT/vulkan.moonwitch_p5.debug.so" | awk '{print $1}')"

cat > "$OUT/meta.json" <<EOF
{
  "schemaVersion": 1,
  "name": "Moonwitch Turnip P5-T1 · Poco F5 / A725 / TOTK",
  "description": "P5-T1 baseline: T30 Mesa base ${MESA_COMMIT}, NDK r28b/API 35, A725 quirk retained, dedicated TOTK GMEM DONT_CARE-as-LOAD + OOB indirect UBO correctness defaults. No Apex GCM/cache/suballocator/scheduling bundle yet.",
  "author": "Moonwitch",
  "packageVersion": "P5-T1",
  "vendor": "Mesa / Moonwitch P5",
  "driverVersion": "${VERSION}-P5-T1-${MESA_COMMIT}",
  "minApi": 35,
  "libraryName": "${DRIVER_NAME}"
}
EOF

cat > "$OUT/BUILD-MANIFEST.txt" <<EOF
Moonwitch Turnip P5-T1
======================
Target phone: Poco F5
SoC/GPU: Snapdragon 7+ Gen 2 / Adreno 725
OS target: HyperOS 3 / Android API 35
Primary workload: Moonwitch + Zelda TOTK
Mesa base requested: ${MESA_COMMIT}
Mesa base resolved: ${BASE_FULL}
Mesa VERSION: ${VERSION}
Android NDK: r28b
Optimization policy: Meson release/O3, no custom ThinLTO/CPU tuning in T1
A725 source guard: cmdbuf_start_a725_quirk required
TOTK correctness defaults:
  tu_dont_care_as_load=true
  tu_allow_oob_indirect_ubo_loads=true
Explicitly NOT imported in T1:
  Apex GCM changes
  Apex 4GB shader-cache policy
  Apex 512KB suballocator policy
  Apex Cortex-X3 scheduling tuning
  speculative fence/synchronization relaxations
Installable SO SHA256: ${SO_SHA}
Debug SO SHA256: ${DEBUG_SHA}
EOF

(
  cd "$OUT"
  zip -q "$PACKAGE_NAME" "$DRIVER_NAME" meta.json
)

ZIP_SHA="$(sha256sum "$OUT/$PACKAGE_NAME" | awk '{print $1}')"
printf '\nPackage SHA256: %s\n' "$ZIP_SHA" >> "$OUT/BUILD-MANIFEST.txt"

printf '[p5-t1] SUCCESS: %s\n' "$OUT/$PACKAGE_NAME"
cat "$OUT/BUILD-MANIFEST.txt"
