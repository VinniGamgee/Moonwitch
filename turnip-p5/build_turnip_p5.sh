#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LAB="$ROOT/turnip-p5"
WORK="$LAB/work"
OUT="$LAB/out"
MESA="$WORK/mesa"

# The supplied MrPurple T30 binary identifies itself as:
#   PurpleVK 26.3.0-devel (git-62ac221a33)
# That SHA is not present in upstream Mesa history, even after deepening the
# public main branch by 12k commits, so it is a fork/private-tree identifier.
# T30 was published at 2026-08-17 12:38 UTC. The closest independently logged
# public Mesa snapshot before that release is dd daef6... (07:44 UTC), still
# Vulkan 1.4.359. P5-T1 uses that reproducible source base and records the
# private T30 SHA separately instead of pretending it is upstream.
T30_PRIVATE_SHA="62ac221a33"
MESA_COMMIT="dddaef6f8c970770cc60f6bab6ab5392f54e7679"
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

printf '[p5-t1] Fetching reproducible public Mesa base %s...\n' "$MESA_COMMIT"
git clone \
  --filter=blob:none \
  --no-checkout \
  --shallow-since=2026-08-16 \
  --branch main \
  https://gitlab.freedesktop.org/mesa/mesa.git \
  "$MESA"

if ! git -C "$MESA" cat-file -e "${MESA_COMMIT}^{commit}" 2>/dev/null; then
  echo '[p5-t1] Public base not in shallow window; deepening Mesa history...'
  git -C "$MESA" fetch --filter=blob:none --deepen=2000 origin main
fi

if ! git -C "$MESA" cat-file -e "${MESA_COMMIT}^{commit}" 2>/dev/null; then
  echo "[p5-t1] ERROR: public Mesa base ${MESA_COMMIT} is unavailable." >&2
  exit 2
fi

git -C "$MESA" checkout -q --detach "$MESA_COMMIT"
BASE_FULL="$(git -C "$MESA" rev-parse HEAD)"
BASE_DATE="$(git -C "$MESA" show -s --format=%ci HEAD)"
if [[ "$BASE_FULL" != "$MESA_COMMIT" ]]; then
  echo "[p5-t1] ERROR: checked out ${BASE_FULL}, expected ${MESA_COMMIT}." >&2
  exit 2
fi
printf '[p5-t1] Public Mesa base: %s (%s)\n' "$BASE_FULL" "$BASE_DATE"
printf '[p5-t1] T30 fork/private reference: %s\n' "$T30_PRIVATE_SHA"

# A725 is non-negotiable for this project. Upstream Mesa has a dedicated
# command-buffer-start workaround for A725; fail rather than silently build a
# generic A7xx path if that support is missing from the selected snapshot.
if ! grep -Rqs --include='*.c' --include='*.cc' --include='*.h' --include='*.py' \
  'cmdbuf_start_a725_quirk' "$MESA/src/freedreno"; then
  echo '[p5-t1] ERROR: public base does not contain cmdbuf_start_a725_quirk.' >&2
  exit 3
fi

# Android/NDK compatibility edits only. These are conditional build scaffolding,
# not renderer/performance changes.
sed -i 's/typedef const native_handle_t\* buffer_handle_t;/typedef void\* buffer_handle_t;/g' \
  "$MESA/include/android_stub/cutils/native_handle.h" 2>/dev/null || true
sed -i 's/, hnd->handle/, (void *)hnd->handle/g' \
  "$MESA/src/util/u_gralloc/u_gralloc_fallback.c" 2>/dev/null || true
sed -i -E 's/([a-z_]+)->handle->/((const native_handle_t *)\1->handle)->/g' \
  "$MESA/src/vulkan/runtime/vk_android.c" 2>/dev/null || true

# T1 intentionally imports only the two Zelda-facing correctness switches.
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

# P5-T1 is the clean A/B baseline: release/O3 only. No Apex GCM, giant cache,
# suballocator, scheduler, fence or CPU-microarchitecture bundle yet.
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

# Keep an unstripped twin for address-to-symbol crash analysis. The phone gets
# a stripped package. Validate the A725 path before stripping local symbols.
cp "$SRC_SO" "$OUT/vulkan.moonwitch_p5.debug.so"
if ! strings -a "$OUT/vulkan.moonwitch_p5.debug.so" | grep -q 'cmdbuf_start_a725_quirk'; then
  echo '[p5-t1] ERROR: A725 quirk did not survive into the debug binary.' >&2
  exit 5
fi

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
  "description": "P5-T1: closest reproducible public Mesa snapshot before MrPurple T30 release, NDK r28b/API 35, A725 path required, Zelda GMEM DONT_CARE-as-LOAD + OOB indirect UBO correctness defaults. T30 fork SHA ${T30_PRIVATE_SHA} tracked for reference; no Apex tuning bundle.",
  "author": "Moonwitch",
  "packageVersion": "P5-T1",
  "vendor": "Mesa / Moonwitch P5",
  "driverVersion": "${VERSION}-P5-T1-${MESA_COMMIT:0:10}",
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
MrPurple T30 binary reference: ${T30_PRIVATE_SHA} (fork/private-tree SHA; not upstream Mesa)
Public reconstruction base: ${BASE_FULL}
Public base date: ${BASE_DATE}
Why this base: closest independently logged public Mesa snapshot before T30's 2026-08-17 12:38 UTC release
Mesa VERSION: ${VERSION}
Android NDK: r28b
Optimization policy: Meson release/O3; no extra CPU/GCM/cache tuning in T1
A725 guard: cmdbuf_start_a725_quirk required in source and debug binary
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
