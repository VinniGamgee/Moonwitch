#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path

path = Path("src/video_core/texture_cache/texture_cache.h")
text = path.read_text(encoding="utf-8")

old = '''    } else {\n        RefreshContents(image, image_id);\n        if (!image.aliased_images.empty()) {\n            SynchronizeAliases(image_id);\n        }\n    }\n'''

new = '''    } else {\n        // Moonwitch graphics research experiment #2:\n        // Ryujinx flushes newer incompatible texture overlaps before synchronizing\n        // the texture being used. Yuzu tracks incompatible overlaps, but normally\n        // only synchronizes compatible aliases here. For this experiment, if a\n        // newer GPU-owned incompatible overlap exists, flush the shared guest\n        // memory region first and force this image to reload from that memory.\n        bool has_newer_incompatible_overlap = false;\n        for (const ImageId overlap_id : image.overlapping_images) {\n            const ImageBase& overlap = slot_images[overlap_id];\n            if (overlap.modification_tick > image.modification_tick &&\n                overlap.IsSafeGpuCopy()) {\n                has_newer_incompatible_overlap = true;\n                break;\n            }\n        }\n        if (has_newer_incompatible_overlap) {\n            DownloadMemory(image.cpu_addr, image.guest_size_bytes);\n            image.flags |= ImageFlagBits::CpuModified;\n        }\n\n        RefreshContents(image, image_id);\n        if (!image.aliased_images.empty()) {\n            SynchronizeAliases(image_id);\n        }\n    }\n'''

if old not in text:
    raise SystemExit("Expected TextureCache PrepareImage fragment not found; aborting research patch")

text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")
print("Applied graphics research experiment #2: synchronize newer incompatible overlaps before image use.")
