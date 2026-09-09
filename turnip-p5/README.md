# Moonwitch Turnip P5

Purpose-built Turnip experiments for **Poco F5 / Snapdragon 7+ Gen 2 / Adreno 725 / HyperOS 3**, with Moonwitch + Zelda TOTK as the primary workload.

## P5-T1

The first build is intentionally conservative so the phone test has a clean answer.

### Source provenance

The supplied MrPurple T30 binary identifies itself as `PurpleVK 26.3.0-devel (git-62ac221a33)`, but `62ac221a33` is not present in public upstream Mesa history. CI verified this by searching the August window and then deepening the public `main` history by 12,000 commits. It therefore must be treated as a MrPurple fork/private-tree identifier, not as an upstream Mesa commit.

T30 was published on 2026-08-17 at 12:38 UTC. The closest independently logged public Mesa snapshot before that publication is:

- Mesa commit `dddaef6f8c970770cc60f6bab6ab5392f54e7679`
- snapshot time/release window: 2026-08-17 before T30 publication
- Vulkan 1.4.359

P5-T1 uses that reproducible public snapshot while keeping `62ac221a33` in the build manifest strictly as the T30 binary reference. We do **not** claim P5-T1 is the exact T30 source.

### Build target

- Poco F5 / SM7475 / Adreno 725 only as the development target
- Android NDK r28b
- API 35 / HyperOS 3 target
- KGSL / Freedreno Turnip
- `cmdbuf_start_a725_quirk` is mandatory; CI fails if the selected Mesa source or debug binary loses it

T1 changes exactly two Turnip correctness defaults for this **dedicated per-game TOTK driver**:

- `tu_dont_care_as_load = true`
- `tu_allow_oob_indirect_ubo_loads = true`

Not imported yet:

- Apex GCM bundle
- Apex 4 GB shader-cache policy
- Apex 512 KB suballocator policy
- Apex Cortex-X3 scheduling tuning
- speculative fence/barrier relaxations
- custom CPU microarchitecture flags

That separation is deliberate: Apex V2 fixed visible Zelda rendering issues on the test device but also produced a map-related 0 FPS/device-loss style failure. P5-T1 first tests whether the Zelda-facing correctness switches can be retained on a public Mesa baseline very close in time to T30 without importing Apex's broader riskier tuning bundle.

## Test protocol

Use Moonwitch's per-game driver selection for TOTK. For the first A/B test:

1. Disable UltraCam and other DynamicFPS/frame-skip mods.
2. Keep the same Moonwitch build, game update, graphics settings, save and cooler setup.
3. Compare T30 vs P5-T1 in the same areas.
4. Test grass, map open/close loops, horse + fast camera rotation, sky islands, Depths and Ultrahand.
5. Record FPS range, frametime feel, black squares/flicker, grass loss and any 0 FPS/crash.
6. Run at least 20–30 minutes before calling the driver stable.

CI also keeps an unstripped debug `.so` as a separate artifact so address-based crashes can be symbolized later.
