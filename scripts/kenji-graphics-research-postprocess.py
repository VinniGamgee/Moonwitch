#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path

path = Path("src/video_core/texture_cache/texture_cache.h")
text = path.read_text(encoding="utf-8")

old = '''        const bool must_download = IsDownloadable(image) && False(image.flags & ImageFlagBits::BadOverlap);\n        if ((!aggressive_mode && True(image.flags & ImageFlagBits::CostlyLoad)) || (!high_priority_mode && must_download)) {\n            return false;\n        }\n'''

new = '''        const bool is_bad_overlap = True(image.flags & ImageFlagBits::BadOverlap);\n        const bool is_gpu_modified = True(image.flags & ImageFlagBits::GpuModified);\n\n        // Moonwitch graphics research experiment #1:\n        // Ryujinx keeps explicit synchronization/dependency state for incompatible\n        // texture overlaps. Yuzu's GC historically treated BadOverlap images as\n        // non-downloadable and could evict a GPU-modified resource without preserving\n        // its contents. Keep such resources resident until we can establish a safe\n        // synchronization path instead of silently discarding GPU-owned data.\n        if (is_bad_overlap && is_gpu_modified) {\n            return false;\n        }\n\n        const bool must_download = IsDownloadable(image);\n        if ((!aggressive_mode && True(image.flags & ImageFlagBits::CostlyLoad)) || (!high_priority_mode && must_download)) {\n            return false;\n        }\n'''

if old not in text:
    raise SystemExit("Expected TextureCache GC fragment not found; aborting research patch")

text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")
print("Applied graphics research experiment #1: retain GPU-modified BadOverlap images.")
