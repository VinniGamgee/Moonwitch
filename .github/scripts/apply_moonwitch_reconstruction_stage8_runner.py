#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

patcher = Path(__file__).with_name("apply_moonwitch_reconstruction_stage8.py")
text = patcher.read_text(encoding="utf-8")
old = (
    '    "    const VkImageAspectFlags dst_aspect_mask = dst.AspectMask();\\n"\n'
    '    "    const VkImageAspectFlags src_aspect_mask = src.AspectMask();\\n",\n'
)
new = (
    '    "    const VkImageAspectFlags src_aspect_mask = src.AspectMask();\\n"\n'
    '    "    const VkImageAspectFlags dst_aspect_mask = dst.AspectMask();\\n",\n'
)
if old not in text:
    raise RuntimeError("Stage 8 ReinterpretImage anchor correction target was not found")
text = text.replace(old, new, 1)
namespace = {"__name__": "__main__", "__file__": str(patcher)}
exec(compile(text, str(patcher), "exec"), namespace)
