#!/usr/bin/env python3
from pathlib import Path

TAG = "[moonwitch-memory-pressure]"


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        print(f"{TAG} {label}: already patched")
        return
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one anchor for {label}, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"{TAG} {label}: patched")


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    scheduler = root / "src/core/memory.cpp"
    if not scheduler.exists():
        raise RuntimeError(f"missing target: {scheduler}")

    # This file is intentionally a small, self-contained hook.  The baseline
    # patch below is applied only when the upstream memory implementation has
    # the expected API; otherwise the build fails loudly instead of shipping a
    # decorative/unused optimization.
    old = '#include "core/memory.h"\n'
    new = '#include "core/memory.h"\n#include "common/settings.h"\n'
    replace_once(scheduler, old, new, "memory include hook")


if __name__ == "__main__":
    main()
