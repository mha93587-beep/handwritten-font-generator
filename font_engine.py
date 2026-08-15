import os
import sys
import math
import logging
from collections import deque
from typing import Dict, List, Tuple, Optional
from PIL import Image, ImageOps, ImageFilter

import config
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen

logger = logging.getLogger(__name__)

# Character metrics categorization
DESCENDER_CHARS = set("gjpqy,;")
CENTERED_CHARS = set("-=+*~÷×")
HIGH_CHARS = set("'^\"°`")
LOW_CHARS = set("._")

def ramer_douglas_peucker(points: List[Tuple[float, float]], epsilon: float) -> List[Tuple[float, float]]:
    """Simplify polygon curves using the Ramer-Douglas-Peucker algorithm."""
    if len(points) < 3:
        return points

    start_x, start_y = points[0]
    end_x, end_y = points[-1]

    dmax = 0.0
    index = 0
    dx = end_x - start_x
    dy = end_y - start_y
    line_len_sq = dx * dx + dy * dy

    for i in range(1, len(points) - 1):
        px, py = points[i]
        if line_len_sq == 0:
            dist = math.hypot(px - start_x, py - start_y)
        else:
            t = max(0.0, min(1.0, ((px - start_x) * dx + (py - start_y) * dy) / line_len_sq))
            proj_x = start_x + t * dx
            proj_y = start_y + t * dy
            dist = math.hypot(px - proj_x, py - proj_y)

        if dist > dmax:
            index = i
            dmax = dist

    if dmax > epsilon:
        rec1 = ramer_douglas_peucker(points[:index + 1], epsilon)
        rec2 = ramer_douglas_peucker(points[index:], epsilon)
        return rec1[:-1] + rec2
    else:
        return [points[0], points[-1]]

def trace_component_contours(grid: List[List[int]], w: int, h: int, epsilon: float = 1.0) -> List[List[Tuple[float, float]]]:
    """
    Extract clean vector contour loops from binary ink grid (1=ink, 0=background).
    """
    pw, ph = w + 4, h + 4
    pgrid = [[0] * pw for _ in range(ph)]
    for y in range(h):
        for x in range(w):
            pgrid[y + 2][x + 2] = grid[y][x]

    nbrs = [(-1, 0), (-1, 1), (0, 1), (1, 1), (1, 0), (1, -1), (0, -1), (-1, -1)]
    visited = set()
    contours = []

    for y in range(1, ph - 1):
        for x in range(1, pw - 1):
            if pgrid[y][x] == 1:
                has_bg = any(pgrid[y + dy][x + dx] == 0 for dy, dx in nbrs)
                if not has_bg or (x, y) in visited:
                    continue

                contour = []
                cx, cy = x, y
                start_dir = 0
                max_steps = pw * ph * 2
                step = 0

                while step < max_steps:
                    contour.append((cx - 2.0, cy - 2.0))
                    visited.add((cx, cy))

                    found = False
                    for i in range(8):
                        d = (start_dir + i) % 8
                        ny = cy + nbrs[d][0]
                        nx = cx + nbrs[d][1]
                        if 0 <= ny < ph and 0 <= nx < pw and pgrid[ny][nx] == 1:
                            cx, cy = nx, ny
                            start_dir = (d + 5) % 8
                            found = True
                            break

                    if not found or (cx == x and cy == y and len(contour) > 2):
                        break
                    step += 1

                if len(contour) >= 5:
                    simp = ramer_douglas_peucker(contour, epsilon)
                    if len(simp) >= 3:
                        bx0 = min(p[0] for p in simp)
                        bx1 = max(p[0] for p in simp)
                        by0 = min(p[1] for p in simp)
                        by1 = max(p[1] for p in simp)
                        if (bx1 - bx0 >= 3 or by1 - by0 >= 3):
                            contours.append(simp)

    return contours

def process_and_vectorize_glyph(img: Image.Image, epsilon: float = 1.0) -> Tuple[List[List[Tuple[float, float]]], int, int]:
    """
    Extract filtered binary grid, enhance stroke thickness for 100% rich opacity,
    and trace vector contours for a glyph crop.
    Returns (contours, width, height).
    """
    gray = img.convert("L")
    gray = ImageOps.autocontrast(gray, cutoff=2)

    # Thicken thin ballpoint/pen strokes with Morphological Dilation so font has 100% solid opacity
    inv = ImageOps.invert(gray)
    inv_dilated = inv.filter(ImageFilter.MaxFilter(size=3))
    gray = ImageOps.invert(inv_dilated)

    w, h = gray.size
    px = gray.load()

    # Estimate background level
    border_vals = [px[x, 0] for x in range(cw)] if False else [px[x, 0] for x in range(w)] + [px[x, h - 1] for x in range(w)] + [px[0, y] for y in range(h)] + [px[w - 1, y] for y in range(h)]
    bg_val = sum(border_vals) / max(len(border_vals), 1)
    thresh = bg_val - 22

    grid = [[0] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            if px[x, y] < thresh:
                grid[y][x] = 1

    # Filter horizontal ruling lines
    for y in range(h):
        run = 0
        for x in range(w):
            if grid[y][x] == 1:
                run += 1
            else:
                if run > w * 0.70:
                    for rx in range(x - run, x):
                        v_span = sum(1 for vy in range(max(0, y - 3), min(h, y + 4)) if grid[vy][rx] == 1)
                        if v_span <= 3:
                            grid[y][rx] = 0
                run = 0
        if run > w * 0.70:
            for rx in range(w - run, w):
                v_span = sum(1 for vy in range(max(0, y - 3), min(h, y + 4)) if grid[vy][rx] == 1)
                if v_span <= 3:
                    grid[y][rx] = 0

    visited = [[False] * w for _ in range(h)]
    comps = []

    for y in range(h):
        for x in range(w):
            if grid[y][x] == 1 and not visited[y][x]:
                q = deque([(x, y)])
                visited[y][x] = True
                pts = []
                touches_border = False
                while q:
                    cx, cy = q.popleft()
                    pts.append((cx, cy))
                    if cx == 0 or cx == w - 1 or cy == 0 or cy == h - 1:
                        touches_border = True
                    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        nx, ny = cx + dx, cy + dy
                        if 0 <= nx < w and 0 <= ny < h and grid[ny][nx] == 1 and not visited[ny][nx]:
                            visited[ny][nx] = True
                            q.append((nx, ny))
                comps.append((pts, touches_border))

    comps.sort(key=lambda c: len(c[0]), reverse=True)

    clean_grid = [[0] * w for _ in range(h)]
    if comps:
        main_pts, _ = comps[0]
        # Ensure main component is substantial (at least 12 pixels)
        if len(main_pts) >= 12:
            for x, y in main_pts:
                clean_grid[y][x] = 1

            main_min_x = min(p[0] for p in main_pts)
            main_max_x = max(p[0] for p in main_pts)
            for pts, touches_b in comps[1:]:
                if len(pts) >= 5:
                    c_min_x = min(p[0] for p in pts)
                    c_max_x = max(p[0] for p in pts)
                    if (min(main_max_x, c_max_x) - max(main_min_x, c_min_x)) >= -12 and not (touches_b and len(pts) < 15):
                        for x, y in pts:
                            clean_grid[y][x] = 1

    contours = trace_component_contours(clean_grid, w, h, epsilon=epsilon)
    return contours, w, h

def build_glyph_for_char(
    char: str,
    glyph_img: Optional[Image.Image],
    glyph_set: dict,
    units_per_em: int = 1000,
    ascent: int = 800,
    descent: int = -200
) -> Tuple[any, int]:
    """
    Vectorize character crop and compile into FontTools TrueType Glyph with safe coordinate clamping.
    """
    pen = TTGlyphPen(glyph_set)

    if glyph_img is None or char == " ":
        pen.glyph()
        advance_width = int(units_per_em * 0.35)
        return pen.glyph(), advance_width

    contours, crop_w, crop_h = process_and_vectorize_glyph(glyph_img, epsilon=1.0)

    if not contours:
        advance_width = int(units_per_em * 0.35)
        return pen.glyph(), advance_width

    # Find tight bounding box of all contours
    all_x = [p[0] for c in contours for p in c]
    all_y = [p[1] for c in contours for p in c]
    min_x, max_x = min(all_x), max(all_x)
    min_y, max_y = min(all_y), max(all_y)
    glyph_w = max_x - min_x + 1
    glyph_h = max_y - min_y + 1

    # Filter out tiny noise
    if glyph_h < 6 or glyph_w < 3:
        advance_width = int(units_per_em * 0.35)
        return pen.glyph(), advance_width

    target_cap_height = ascent * 0.85
    target_x_height = ascent * 0.55

    if char.isupper() or char.isdigit():
        scale = target_cap_height / max(glyph_h, 1)
    elif char in DESCENDER_CHARS:
        scale = (target_x_height * 1.45) / max(glyph_h, 1)
    elif char in CENTERED_CHARS:
        scale = target_x_height / max(glyph_h, 1)
    elif char.islower():
        scale = target_x_height / max(glyph_h, 1)
    else:
        scale = target_cap_height / max(glyph_h, 1)

    # Strictly limit scale so raster overflow never happens
    scale = min(scale, 20.0)

    max_height = (ascent - descent) * 0.85
    if glyph_h * scale > max_height:
        scale = max_height / glyph_h

    scaled_w = glyph_w * scale
    scaled_h = glyph_h * scale

    if char in DESCENDER_CHARS:
        y_offset = -int(scaled_h * 0.35)
    elif char in CENTERED_CHARS:
        y_offset = int((ascent * 0.45) - (scaled_h / 2.0))
    elif char in HIGH_CHARS:
        y_offset = int(ascent * 0.7)
    elif char in LOW_CHARS:
        y_offset = 0
    else:
        y_offset = 0

    left_side_bearing = int(units_per_em * 0.06)
    advance_width = int(scaled_w + left_side_bearing * 2)
    advance_width = max(int(units_per_em * 0.20), min(int(units_per_em * 1.2), advance_width))

    for contour in contours:
        if len(contour) < 3:
            continue

        p0 = contour[0]
        x0 = int(max(-300, min(1500, left_side_bearing + (p0[0] - min_x) * scale)))
        y0 = int(max(-400, min(1200, y_offset + (glyph_h - (p0[1] - min_y)) * scale)))
        pen.moveTo((x0, y0))

        for pt in contour[1:]:
            x = int(max(-300, min(1500, left_side_bearing + (pt[0] - min_x) * scale)))
            y = int(max(-400, min(1200, y_offset + (glyph_h - (pt[1] - min_y)) * scale)))
            pen.lineTo((x, y))

        pen.closePath()

    return pen.glyph(), advance_width

def create_notdef_glyph(glyph_set: dict, units_per_em: int = 1000, ascent: int = 800) -> Tuple[any, int]:
    """Create .notdef rectangle fallback glyph."""
    pen = TTGlyphPen(glyph_set)
    w = int(units_per_em * 0.45)
    h = int(ascent * 0.8)
    lsb = int(units_per_em * 0.05)
    thick = int(units_per_em * 0.04)

    pen.moveTo((lsb, 0))
    pen.lineTo((lsb + w, 0))
    pen.lineTo((lsb + w, h))
    pen.lineTo((lsb, h))
    pen.closePath()

    pen.moveTo((lsb + thick, thick))
    pen.lineTo((lsb + thick, h - thick))
    pen.lineTo((lsb + w - thick, h - thick))
    pen.lineTo((lsb + w - thick, thick))
    pen.closePath()

    return pen.glyph(), lsb * 2 + w

def compile_ttf_font(
    char_glyph_map: Dict[str, Image.Image],
    output_path: str,
    font_name: str = "MyHandwriting",
    family_name: str = "MyHandwriting"
) -> str:
    """
    Compile character crops dictionary into TrueType TTF font.
    """
    fb = FontBuilder(config.UNITS_PER_EM, isTTF=True)

    glyph_order = [".notdef", "space"]
    char_to_glyph_name = {}
    glyph_table = {}
    hmtx_table = {}
    cmap_table = {}

    glyph_set = {}

    notdef_glyph, notdef_advance = create_notdef_glyph(glyph_set, config.UNITS_PER_EM, config.ASCENT)
    glyph_table[".notdef"] = notdef_glyph
    hmtx_table[".notdef"] = (notdef_advance, int(config.UNITS_PER_EM * 0.05))

    space_glyph, space_advance = build_glyph_for_char(" ", None, glyph_set, config.UNITS_PER_EM, config.ASCENT, config.DESCENT)
    glyph_table["space"] = space_glyph
    hmtx_table["space"] = (space_advance, 0)
    cmap_table[32] = "space"

    for char, img in char_glyph_map.items():
        if char == " ":
            continue

        if char.isalnum():
            gname = f"uni{ord(char):04X}"
        else:
            gname = f"u{ord(char):04X}"

        glyph_order.append(gname)
        char_to_glyph_name[char] = gname
        cmap_table[ord(char)] = gname

        glyph, adv_width = build_glyph_for_char(char, img, glyph_set, config.UNITS_PER_EM, config.ASCENT, config.DESCENT)
        glyph_table[gname] = glyph
        hmtx_table[gname] = (adv_width, int(config.UNITS_PER_EM * 0.06))

    fb.setupGlyphOrder(glyph_order)
    fb.setupCharacterMap(cmap_table)
    fb.setupGlyf(glyph_table)
    fb.setupHorizontalMetrics(hmtx_table)
    fb.setupHorizontalHeader(ascent=config.ASCENT, descent=config.DESCENT)

    name_strings = {
        "familyName": family_name,
        "styleName": "Regular",
        "uniqueFontIdentifier": f"1.000;AGY;{font_name}",
        "fullName": font_name,
        "version": "Version 1.000",
        "psName": font_name.replace(" ", "-"),
        "designer": "AI Handwritten Font Generator",
    }
    fb.setupNameTable(name_strings)
    fb.setupOS2(
        sTypoAscender=config.ASCENT,
        sTypoDescender=config.DESCENT,
        usWinAscent=config.ASCENT,
        usWinDescent=abs(config.DESCENT),
        sxHeight=config.X_HEIGHT,
        sCapHeight=config.CAP_HEIGHT
    )
    fb.setupPost()
    fb.setupHead(unitsPerEm=config.UNITS_PER_EM)

    fb.save(output_path)
    logger.info(f"Successfully saved TrueType font to {output_path}")
    return output_path
