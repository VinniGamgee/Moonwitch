#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LAB="$ROOT/turnip-p5"
WORK="$LAB/work"
OUT="$LAB/out"
MESA="$WORK/mesa"

# The user's T30 binary reports:
#   PurpleVK 26.3.0-devel (git-62ac221a33)
#   Android 35 / NDK r28b
# and its ZIP timestamp is 2026-08-16. P5-T1 deliberately stays close to that
# baseline and adds only the two Zelda correctness switches.
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

# A short SHA is an object name, not a remote ref, so `git fetch origin
# 62ac221a33` is invalid on GitLab. Fetch the surrounding Mesa history first,
# then resolve the short SHA locally. Blob filtering keeps this much lighter
# than a full Mesa clone; checkout lazily downloads the required source blobs.
printf '[p5-t1] Resolving exact T30 Mesa base %s from upstream history...\n' "$MESA_COMMIT"
git clone \
  --filter=blob:none \
  --no-checkout \
  --shallow-since=2026-08-01 \
  --branch main \
  https://gitlab.freedesktop.org/mesa/mesa.git \
  "$MESA"

BASE_FULL="$(git -C "$MESA" rev-list --all | grep -E "^${MESA_COMMIT}[0-9a-f]*$" | head -n1 || true)"
if [[ -z "$BASE_FULL" ]]; then
  echo '[p5-t1] Short SHA not found in the August shallow window; deepening history...'
  git -C "$MESA" fetch --filter=blob:none --deepen=12000 origin main
  BASE_FULL="$(git -C "$MESA" rev-list --all | grep -E "^${MESA_COMMIT}[0-9a-f]*$" | head -n1 || true)"
fi

if [[ -z "$BASE_FULL" ]]; then
  echo "[p5-t1] ERROR: Mesa upstream history does not contain ${MESA_COMMIT}." >&2
  echo '[p5-t1] The T30 short SHA may come from a private/fork-only commit; refusing to silently substitute another base.' >&2
  exit 2
fi

if [[ "$BASE_FULL" != ${MESA_COMMIT}* ]]; then
  echo "[p5-t1] ERROR: resolved SHA ${BASE_FULL} does not match requested prefix ${MESA_COMMIT}." >&2
  exit 2
fi

git -C "$MESA" checkout -q --detach "$BASE_FULL"
BASE_DATE="$(git -C "$MESA" show -s --format=%ci HEAD)"
printf '[p5-t1] Mesa base: %s (%s)\n' "$BASE_FULL" "$BASE_DATE"

# The T30 binary contains this A725 path. We require the matching source path
# before touching any Zelda options; no generic A7xx fallback is accepted.
if ! grep -Rqs --include='*.c' --include='*.cc' --include='*.h' \
  'cmdbuf_start_a725_quirk' "$MESA/src/freedreno"; then
  echo '[p5-t1] ERROR: exact base does not contain cmdbuf_start_a725_quirk.' >&2
  exit 3
fi

# Android/NDK compatibility edits only. These are not renderer/performance
# changes and are conditional so the script works if upstream already fixed
# the forms.
sed -i 's/typedef const native_handle_t\* buffer_handle_t;/typedef void\* buffer_handle_t;/g' \
  "$MESA/include/android_stub/cutils/native_handle.h" 2>/dev/null || true
sed -i 's/, hnd->handle/, (void *)hnd->handle/g' \
  "$MESA/src/util/u_gralloc/u_gralloc_fallback.c" 2>/dev/null || true
sed -i -E 's/([a-z_]+)->handle->/((const native_handle_t *)\1->handle)->/g' \
  "$MESA/src/vulkan/runtime/vk_android.c" 2>/dev/null || true

python3 "$LAB/apply_t1_totk_fixes.py" "$MESA"
git -C "$MESA" diff -- src/freedreno/vulkan/tu_device.cc | tee "$OUT/P5-T1-TOTK.patch"

cat > "$MESA/android-aarch64.txt" <<EOF
[binaries]
ar = '$NDK/llvm-ar'
c = ['ccache', '$NDK/aarch64-linux-android${ANDROID_API}-clang']
cpp = ['ccache', '$NDK/aarch64-linux-android${ANDROID_API}-clang++', '-fno-exceptions', '-fno-unwind-tables', '-fno-asynchronous-unwind-tables', '--start-no-unused-arguments', '-static-libstdc++', '--end-no-unused-arguments']
c_ld = '$NDK/ld.lld'
cpp_ld = '$NDK/ld.lld'
strip = '$NDK/llvm-strip'
pkg-config = '/usr/bin/pkg-config'

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

# No Apex GCM/cache/suballocator/scheduling bundle in T1. Release/O3 only;
# this isolates the correctness delta for the first phone A/B test.
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
  find "$WORK/install" -maxdepth 4 -type f -name '*vulkan*' -print || true
  exit 4
fi

# Keep the unstripped twin for crash address -> symbol analysis. The phone gets
# a stripped copy only. The A725 symbol guard runs against the debug twin,
# because stripping is allowed to remove local function names.
cp "$SRC_SO" "$OUT/vulkan.moonwitch_p5.debug.so"
strings -a "$OUT/vulkan.moonwitch_p5.debug.so" | grep -q 'cmdbuf_start_a725_quirk'

cp "$SRC_SO" "$OUT/$DRIVER_NAME"
patchelf --set-soname "$DRIVER_NAME" "$OUT/$DRIVER_NAME"
"$NDK/llvm-strip" --strip-unneeded "$OUT/$DRIVER_NAME"

file "$OUT/$DRIVER_NAME"
readelf -h "$OUT/$DRIVER_NAME" | grep -q 'AArch64'
readelf -d "$OUT/$DRIVER_NAME" | grep -q "$DRIVER_NAME"
strings -a "$OUT/$DRIVER_NAME" | grep -q 'tu_dont_care_as_load'
strings -a "$OUT/$DRIVER_NAME" | grep -q 'tu_allow_oob_indirect_ubo_loads'

VERSION="$(tr -d '\n' < "$MESA/VERSION")"
SO_SHA="$(sha256sum "$OUT/$DRIVER_NAME" | awk '{print $1}')"
DEBUG_SHA="$(sha256sum "$OUT/vulkan.moonwitch_p5.debug.so" | awk '{print $1}')"

cat > "$OUT/meta.json" <<EOF
{
  "schemaVersion": 1,
  "name": "Moonwitch Turnip P5-T1 · Poco F5 / A725 / TOTK",
  "description": "P5-T1 baseline: exact T30 Mesa git ${MESA_COMMIT}, NDK r28b/API 35, A725 quirk retained, Zelda GMEM DONT_CARE-as-LOAD + OOB indirect UBO correctness defaults. No Apex GCM/cache/suballocator/scheduling bundle.",
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
Mesa commit date: ${BASE_DATE}
Mesa VERSION: ${VERSION}
Android NDK: r28b
Optimization policy: Meson release/O3; no extra CPU/GCM/cache tuning in T1
A725 guard: cmdbuf_start_a725_quirk present in exact base and debug binary
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
