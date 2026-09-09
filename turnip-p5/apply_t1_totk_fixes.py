#!/usr/bin/env python3
"""Apply the deliberately small P5-T1 TOTK correctness delta.

P5-T1 is an A/B baseline. It intentionally does NOT import Apex's broader
GCM/cache/suballocator/scheduling changes. The public Mesa snapshot used for
T1 has already moved these settings away from the old DRI_CONF_* declarations
that earlier versions of this script expected, so patch the two real runtime
consumers instead of relying on brittle config-macro spelling.
"""

from pathlib import Path
import sys


def replace_exact_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        print(f"[p5-t1] {label}: already applied")
        return

    count = text.count(old)
    if count != 1:
        raise SystemExit(
            f"[p5-t1] {label}: expected exactly one runtime source pattern, found {count}"
        )

    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"[p5-t1] {label}: forced at runtime")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply_t1_totk_fixes.py <mesa-source-dir>")

    root = Path(sys.argv[1]).resolve()
    device = root / "src/freedreno/vulkan/tu_device.cc"
    render_pass = root / "src/freedreno/vulkan/tu_pass.cc"

    for path in (device, render_pass):
        if not path.is_file():
            raise SystemExit(f"[p5-t1] missing {path}")

    # 1) Zelda/GMEM correctness: the 2026-08-17 Mesa snapshot consumes the
    # option directly in attachment_set_ops(). P5-T1 is a dedicated per-game
    # TOTK driver, so normalize guest DONT_CARE load ops unconditionally.
    # This replaces only the public option-gated block; no GMEM scheduling,
    # barriers, resolves or cache policy are changed.
    replace_exact_once(
        render_pass,
        """   if (unlikely(device->instance->drirc.debug.dont_care_as_load)) {\n"
        "      if (load_op == VK_ATTACHMENT_LOAD_OP_DONT_CARE)\n"
        "         load_op = VK_ATTACHMENT_LOAD_OP_LOAD;\n"
        "      if (stencil_load_op == VK_ATTACHMENT_LOAD_OP_DONT_CARE)\n"
        "         stencil_load_op = VK_ATTACHMENT_LOAD_OP_LOAD;\n"
        "   }\n""",
        """   /* Moonwitch P5-T1: dedicated TOTK GMEM correctness path. */\n"
        "   if (load_op == VK_ATTACHMENT_LOAD_OP_DONT_CARE)\n"
        "      load_op = VK_ATTACHMENT_LOAD_OP_LOAD;\n"
        "   if (stencil_load_op == VK_ATTACHMENT_LOAD_OP_DONT_CARE)\n"
        "      stencil_load_op = VK_ATTACHMENT_LOAD_OP_LOAD;\n""",
        "GMEM DONT_CARE-as-LOAD",
    )

    # 2) Zelda shader correctness: the same snapshot copies the modern drirc
    # field into the IR3 compiler options. Force only this compiler option for
    # the dedicated P5-T1 package.
    replace_exact_once(
        device,
        """   device->compiler_options.allow_oob_indirect_ubo_loads =\n"
        "      device->instance->drirc.misc.allow_oob_indirect_ubo_loads;\n""",
        """   /* Moonwitch P5-T1: dedicated TOTK indirect-UBO correctness path. */\n"
        "   device->compiler_options.allow_oob_indirect_ubo_loads = true;\n""",
        "OOB indirect UBO loads",
    )

    # Hard guard: keep the real A725 command-buffer workaround from the base.
    a725_found = any(
        "cmdbuf_start_a725_quirk" in p.read_text(encoding="utf-8", errors="ignore")
        for pattern in ("*.c", "*.cc", "*.h")
        for p in (root / "src/freedreno").rglob(pattern)
    )
    if not a725_found:
        raise SystemExit(
            "[p5-t1] A725 quirk guard failed: cmdbuf_start_a725_quirk not found"
        )

    final_device = device.read_text(encoding="utf-8")
    final_pass = render_pass.read_text(encoding="utf-8")
    guards = (
        (
            "Moonwitch P5-T1: dedicated TOTK GMEM correctness path.",
            final_pass,
        ),
        (
            "Moonwitch P5-T1: dedicated TOTK indirect-UBO correctness path.",
            final_device,
        ),
        ("device->compiler_options.allow_oob_indirect_ubo_loads = true;", final_device),
    )
    for marker, text in guards:
        if marker not in text:
            raise SystemExit(f"[p5-t1] final guard failed: {marker}")

    if "unlikely(device->instance->drirc.debug.dont_care_as_load)" in final_pass:
        raise SystemExit("[p5-t1] final guard failed: GMEM workaround is still option-gated")

    print(
        "[p5-t1] PASS: A725 base retained; the two TOTK correctness paths are forced at their runtime consumers."
    )


if __name__ == "__main__":
    main()
