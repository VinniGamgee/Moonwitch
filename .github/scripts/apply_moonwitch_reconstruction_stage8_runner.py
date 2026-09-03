#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

patcher = Path(__file__).with_name("apply_moonwitch_reconstruction_stage8.py")
text = patcher.read_text(encoding="utf-8")

# Keep the Stage 8 patcher source untouched, but correct anchors/types before executing it.
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

# SGSR2SceneHistoryMatch is nested in TextureCacheRuntime. In an out-of-class member
# definition the return type appears before the qualified function name, so the nested
# type must be explicitly qualified or Clang treats it as undeclared.
old_return = (
    "std::optional<SGSR2SceneHistoryMatch>\n"
    "TextureCacheRuntime::SGSR2FindSceneHistory(VkImage displayed_color_image) {"
)
new_return = (
    "std::optional<TextureCacheRuntime::SGSR2SceneHistoryMatch>\n"
    "TextureCacheRuntime::SGSR2FindSceneHistory(VkImage displayed_color_image) {"
)
if old_return not in text:
    raise RuntimeError("Stage 8 SGSR2 scene-history return type correction target was not found")
text = text.replace(old_return, new_return, 1)

namespace = {"__name__": "__main__", "__file__": str(patcher)}
exec(compile(text, str(patcher), "exec"), namespace)
