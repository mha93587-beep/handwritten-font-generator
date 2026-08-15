import os
import sys
from pathlib import Path

extra_paths = [
    "/usr/lib/python3/dist-packages",
    "/data/data/com.termux/files/usr/lib/python3.13/site-packages",
    "/data/data/com.termux/files/usr/lib/python3.14/site-packages"
]
for p in extra_paths:
    if os.path.exists(p) and p not in sys.path:
        sys.path.insert(0, p)

import math
import logging
from collections import deque
from typing import Dict, List, Tuple, Optional
from PIL import Image, ImageOps, ImageFilter

import config

logger = logging.getLogger(__name__)

# The 12 Official Standard Rows and their expected characters
OFFICIAL_ROW_DEFINITIONS = [
    # (row_name, expected_chars, is_symbols)
    ("R01_A-G", ["A", "B", "C", "D", "E", "F", "G"], False),
    ("R02_H-N", ["H", "I", "J", "K", "L", "M", "N"], False),
    ("R03_O-U", ["O", "P", "Q", "R", "S", "T", "U"], False),
    ("R04_V-Z", ["V", "W", "X", "Y", "Z"], False),
    ("R05_a-g", ["a", "b", "c", "d", "e", "f", "g"], False),
    ("R06_h-n", ["h", "i", "j", "k", "l", "m", "n"], False),
    ("R07_o-v", ["o", "p", "q", "r", "s", "t", "u", "v"], False),
    ("R08_w-z", ["w", "x", "y", "z"], False),
    ("R09_0-9", ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"], False),
    ("R10_sym1", [".", ",", ";", ":", "!", "?", "\"", "\x27", "-"], True),
    ("R11_sym2", ["+", "=", "/", "%", "&", "(", ")"], True),
    ("R12_sym3", ["[", "]"], True)
]

def segment_handwriting_sheet(image_path: str) -> Dict[str, Image.Image]:
    """
    Precision 12-Row Handwriting Segmentation Engine.
    Isolates row bands, filters margin noise, merges in-row multi-part glyphs,
    and maps seamlessly to the official 12-row sequence.
    """
    img = Image.open(image_path)
    img = ImageOps.exif_transpose(img)
    w, h = img.size

    gray = img.convert("L")
    blur = gray.filter(ImageFilter.GaussianBlur(radius=18))
    gray_px = list(gray.get_flattened_data() if hasattr(gray, "get_flattened_data") else gray.getdata())
    blur_px = list(blur.get_flattened_data() if hasattr(blur, "get_flattened_data") else blur.getdata())

    # Adaptive binarization
    grid = [[0] * w for _ in range(h)]
    for y in range(h):
        row_offset = y * w
        for x in range(w):
            if gray_px[row_offset + x] < blur_px[row_offset + x] - 12:
                grid[y][x] = 1

    visited = [[False] * w for _ in range(h)]
    blobs = []

    # Connected Component Labeling
    for y in range(int(h * 0.01), int(h * 0.99)):
        for x in range(int(w * 0.01), int(w * 0.99)):
            if grid[y][x] == 1 and not visited[y][x]:
                q = deque([(x, y)])
                visited[y][x] = True
                min_x, max_x = x, x
                min_y, max_y = y, y
                pixel_count = 0

                while q:
                    cx, cy = q.popleft()
                    pixel_count += 1
                    if cx < min_x: min_x = cx
                    if cx > max_x: max_x = cx
                    if cy < min_y: min_y = cy
                    if cy > max_y: max_y = cy

                    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1), (-1, 1), (1, -1)]:
                        nx, ny = cx + dx, cy + dy
                        if 0 <= nx < w and 0 <= ny < h:
                            if grid[ny][nx] == 1 and not visited[ny][nx]:
                                visited[ny][nx] = True
                                q.append((nx, ny))

                bw = max_x - min_x + 1
                bh = max_y - min_y + 1

                # Discard specks & extreme border streaks
                if pixel_count >= 8 and (bw >= 3 or bh >= 4) and bw < w * 0.6:
                    blobs.append({
                        "box": [min_x, min_y, max_x, max_y],
                        "xc": (min_x + max_x) / 2,
                        "yc": (min_y + max_y) / 2,
                        "w": bw,
                        "h": bh,
                        "pixels": pixel_count
                    })

    # Prepare binary mask image for high-precision bounding box cropping
    clean_img = Image.new("L", (w, h), 255)
    c_px = clean_img.load()
    for y in range(h):
        for x in range(w):
            if grid[y][x] == 1:
                c_px[x, y] = 0

    # Calculate 12 proportional row bands
    # Approximate proportional boundaries for standard A4 / camera sheets
    proportions = [
        (0.00, 0.082),   # R01: A-G
        (0.082, 0.158),  # R02: H-N
        (0.158, 0.233),  # R03: O-U
        (0.233, 0.312),  # R04: V-Z
        (0.312, 0.395),  # R05: a-g
        (0.395, 0.478),  # R06: h-n
        (0.478, 0.562),  # R07: o-v
        (0.562, 0.648),  # R08: w-z
        (0.648, 0.742),  # R09: 1-9, 0
        (0.742, 0.835),  # R10: . , ; : ! ? " ' -
        (0.835, 0.920),  # R11: + = / % & ( )
        (0.920, 1.000)   # R12: [ ]
    ]

    char_map = {}

    for (r_name, expected_chars, is_symbols), (p_min, p_max) in zip(OFFICIAL_ROW_DEFINITIONS, proportions):
        y0 = int(p_min * h)
        y1 = int(p_max * h)

        # Isolate blobs inside this row
        row_blobs = [b for b in blobs if y0 <= b["yc"] < y1]

        # Filter margin dust
        row_blobs = [b for b in row_blobs if not ((b["xc"] < 45 or b["xc"] > w - 45) and b["pixels"] < 100)]

        # Merge in-row multi-part components
        row_blobs.sort(key=lambda b: (b["xc"], b["yc"]))
        merged_row = []
        used = set()

        for i, b1 in enumerate(row_blobs):
            if i in used:
                continue
            cur_box = list(b1["box"])
            cur_yc = [b1["yc"]]
            cur_xc = [b1["xc"]]
            total_p = b1["pixels"]
            used.add(i)

            for j in range(i + 1, len(row_blobs)):
                if j in used:
                    continue
                b2 = row_blobs[j]
                h_overlap = (min(cur_box[2], b2["box"][2]) - max(cur_box[0], b2["box"][0]))
                h_dist = abs((cur_box[0] + cur_box[2]) / 2 - b2["xc"])
                v_dist = abs(b1["yc"] - b2["yc"])

                # Merge parts of same letter inside row
                if (h_overlap > -8 or h_dist < 26) and v_dist < 45:
                    cur_box[0] = min(cur_box[0], b2["box"][0])
                    cur_box[1] = min(cur_box[1], b2["box"][1])
                    cur_box[2] = max(cur_box[2], b2["box"][2])
                    cur_box[3] = max(cur_box[3], b2["box"][3])
                    cur_yc.append(b2["yc"])
                    cur_xc.append(b2["xc"])
                    total_p += b2["pixels"]
                    used.add(j)

            merged_row.append({
                "box": tuple(cur_box),
                "yc": sum(cur_yc) / len(cur_yc),
                "xc": sum(cur_xc) / len(cur_xc),
                "w": cur_box[2] - cur_box[0] + 1,
                "h": cur_box[3] - cur_box[1] + 1,
                "pixels": total_p
            })

        # Discard tiny noise specks in letter rows
        if not is_symbols:
            merged_row = [c for c in merged_row if c["pixels"] >= 90 and c["h"] >= 26]

        # Sort strictly left to right
        merged_row.sort(key=lambda c: c["xc"])

        # Map to expected characters
        for idx, ch in enumerate(expected_chars):
            if idx < len(merged_row):
                b = merged_row[idx]
                bx0, by0, bx1, by1 = b["box"]
                char_map[ch] = clean_img.crop((max(0, bx0 - 4), max(0, by0 - 4), min(w, bx1 + 5), min(h, by1 + 5)))

    # Fallbacks for any missing characters
    if "0" not in char_map and "O" in char_map:
        char_map["0"] = char_map["O"]
    if "1" not in char_map and "I" in char_map:
        char_map["1"] = char_map["I"]

    for ch in list("abcdefghijklmnopqrstuvwxyz"):
        if ch not in char_map and ch.upper() in char_map:
            char_map[ch] = char_map[ch.upper()]
    for ch in list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
        if ch not in char_map and ch.lower() in char_map:
            char_map[ch] = char_map[ch.lower()]

    logger.info(f"Segmented {len(char_map)} character crops for 12-row official template.")
    return char_map

def segment_with_gemini_ai(image_path: str, api_key: Optional[str] = None) -> Dict[str, Image.Image]:
    """Autonomous fallback for AI segmentation."""
    return segment_handwriting_sheet(image_path)
