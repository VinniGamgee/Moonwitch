# Moonwitch Turnip P5

Purpose-built Turnip experiments for **Poco F5 / Snapdragon 7+ Gen 2 / Adreno 725 / HyperOS 3**, with Moonwitch + Zelda TOTK as the primary workload.

## P5-T1

The first build is intentionally conservative so the phone test has a clean answer.

Base target:
- Mesa 26.3.0-devel commit `62ac221a33` (the commit advertised by the supplied MrPurple T30 binary)
- Android NDK r28b
- API 35
- KGSL / Freedreno Turnip only
- existing `cmdbuf_start_a725_quirk` is a mandatory source guard

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

That separation is deliberate: the Apex V2 package fixed visible Zelda rendering issues on the test device but also produced a map-related 0 FPS/device-loss style failure. P5-T1 keeps the known-fast T30 lineage as close as practical while adding only the two Zelda-facing correctness switches.

## Test protocol

Use Moonwitch's per-game driver selection for TOTK. For the first A/B test:

1. Disable UltraCam and other DynamicFPS/frame-skip mods.
2. Keep the same Moonwitch build, game update, graphics settings, save and cooler setup.
3. Compare T30 vs P5-T1 in the same areas.
4. Test grass, map open/close loops, horse + fast camera rotation, sky islands, Depths and Ultrahand.
5. Record FPS range, frametime feel, black squares/flicker, grass loss and any 0 FPS/crash.
6. Run at least 20–30 minutes before calling the driver stable.

CI also keeps an unstripped debug `.so` as a separate artifact so address-based crashes can be symbolized later.
