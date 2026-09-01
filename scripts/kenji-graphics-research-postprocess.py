#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright 2026 Moonwitch Project
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path

path = Path("src/video_core/texture_cache/texture_cache.h")
text = path.read_text(encoding="utf-8")

old = '''    } else {\n        RefreshContents(image, image_id);\n        if (!image.aliased_images.empty()) {\n            SynchronizeAliases(image_id);\n        }\n    }\n'''

new = '''    } else {\n        // Moonwitch graphics research experiment #3:\n        // Ryujinx synchronizes incompatible overlaps before texture reads, but does\n        // so through resource/subresource dependency tracking. EXP2 approximated\n        // that too broadly and could overwrite resources while they were still being\n        // rendered. Narrow the experiment to sampled/read-only image preparation,\n        // synchronize only the newest GPU-owned incompatible overlap, and advance\n        // this image's modification tick after the reload so the same dependency is\n        // not flushed again every draw.\n        if (!is_modification && !image.overlapping_images.empty()) {\n            ImageId newest_overlap_id{};\n            u64 newest_overlap_tick = image.modification_tick;\n            for (const ImageId overlap_id : image.overlapping_images) {\n                const ImageBase& overlap = slot_images[overlap_id];\n                if (overlap.modification_tick > newest_overlap_tick &&\n                    IsDownloadable(overlap)) {\n                    newest_overlap_id = overlap_id;\n                    newest_overlap_tick = overlap.modification_tick;\n                }\n            }\n\n            if (newest_overlap_id) {\n                Image& overlap = slot_images[newest_overlap_id];\n                auto map = runtime.DownloadStagingBuffer(overlap.unswizzled_size_bytes);\n                const auto copies = FixSmallVectorADL(FullDownloadCopies(overlap.info));\n                overlap.DownloadMemory(map, copies);\n                runtime.Finish();\n                SwizzleImage(*gpu_memory, overlap.gpu_addr, overlap.info, copies,\n                             map.mapped_span, swizzle_data_buffer);\n\n                image.flags |= ImageFlagBits::CpuModified;\n                RefreshContents(image, image_id);\n                image.modification_tick = newest_overlap_tick;\n            } else {\n                RefreshContents(image, image_id);\n            }\n        } else {\n            RefreshContents(image, image_id);\n        }\n\n        if (!image.aliased_images.empty()) {\n            SynchronizeAliases(image_id);\n        }\n    }\n'''

if old not in text:
    raise SystemExit("Expected TextureCache PrepareImage fragment not found; aborting research patch")

text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")
print("Applied graphics research experiment #3: sampled-image incompatible-overlap synchronization.")
