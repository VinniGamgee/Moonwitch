#!/usr/bin/env python3
"""Apply the deliberately small P5-T1 TOTK correctness delta.

P5-T1 is an A/B baseline.  It intentionally does NOT import Apex's broader
GCM/cache/suballocator/scheduling changes.  This package is meant to be picked
as a per-game driver for TOTK, so the two known Zelda workarounds are made the
Turnip defaults inside this dedicated build.
"""

from pathlib import Path
import sys


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        print(f"[p5-t1] {label}: already enabled")
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(
            f"[p5-t1] {label}: expected exactly one source default {old!r}, found {count}"
        )
    print(f"[p5-t1] {label}: enabling")
    return text.replace(old, new, 1)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply_t1_totk_fixes.py <mesa-source-dir>")

    root = Path(sys.argv[1]).resolve()
    device = root / "src/freedreno/vulkan/tu_device.cc"
    if not device.is_file():
        raise SystemExit(f"[p5-t1] missing {device}")

    text = device.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "DRI_CONF_TU_DONT_CARE_AS_LOAD(false)",
        "DRI_CONF_TU_DONT_CARE_AS_LOAD(true)",
        "GMEM DONT_CARE-as-LOAD",
    )
    text = replace_once(
        text,
        "DRI_CONF_TU_ALLOW_OOB_INDIRECT_UBO_LOADS(false)",
        "DRI_CONF_TU_ALLOW_OOB_INDIRECT_UBO_LOADS(true)",
        "OOB indirect UBO loads",
    )
    device.write_text(text, encoding="utf-8")

    # Hard guards: P5-T1 must keep the A725 command-buffer quirk from the base
    # and must contain both correctness switches in their enabled form.
    if not any(
        "cmdbuf_start_a725_quirk" in p.read_text(encoding="utf-8", errors="ignore")
        for p in (root / "src/freedreno").rglob("*.[ch]")
    ) and not any(
        "cmdbuf_start_a725_quirk" in p.read_text(encoding="utf-8", errors="ignore")
        for p in (root / "src/freedreno").rglob("*.cc")
    ):
        raise SystemExit("[p5-t1] A725 quirk guard failed: cmdbuf_start_a725_quirk not found")

    final = device.read_text(encoding="utf-8")
    required = (
        "DRI_CONF_TU_DONT_CARE_AS_LOAD(true)",
        "DRI_CONF_TU_ALLOW_OOB_INDIRECT_UBO_LOADS(true)",
    )
    for marker in required:
        if marker not in final:
            raise SystemExit(f"[p5-t1] final guard failed: {marker}")

    print("[p5-t1] PASS: A725 base retained; only the two dedicated TOTK correctness defaults were changed.")


if __name__ == "__main__":
    main()
