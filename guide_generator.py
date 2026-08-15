import os
import logging
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import config

logger = logging.getLogger(__name__)

def get_unicode_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Load DejaVuSans TrueType font for crystal clear Unicode character rendering."""
    font_file = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    local_path = config.STATIC_DIR / font_file
    if local_path.exists():
        try:
            return ImageFont.truetype(str(local_path), size)
        except Exception:
            pass

    sys_paths = [
        f"/usr/share/fonts/truetype/dejavu/{font_file}",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        "/system/fonts/Roboto-Regular.ttf"
    ]
    for sp in sys_paths:
        if Path(sp).exists():
            try:
                return ImageFont.truetype(sp, size)
            except Exception:
                pass

    return ImageFont.load_default()

def generate_guide_image(output_path: str = "static/writing_guide.png") -> str:
    """
    Generate the official 12-row visual writing guide template.
    Structure: Uppercase (1-4) -> Lowercase (5-8) -> Numbers (9) -> Symbols (10-12).
    """
    width = 1200
    row_height = 80
    header_height = 140
    footer_height = 100
    rows = config.DEFAULT_GRID_ROWS
    total_height = header_height + (len(rows) * row_height) + footer_height

    img = Image.new("RGB", (width, total_height), "#FAFAFA")
    draw = ImageDraw.Draw(img)

    f_title = get_unicode_font(32, bold=True)
    f_sub = get_unicode_font(18, bold=False)
    f_badge = get_unicode_font(14, bold=True)
    f_char = get_unicode_font(34, bold=True)
    f_row_lbl = get_unicode_font(15, bold=True)
    f_footer = get_unicode_font(15, bold=False)

    # Header Card
    draw.rectangle([0, 0, width, header_height - 15], fill="#0F172A")
    draw.text((40, 24), "✍️ OFFICIAL HANDWRITING GUIDE (12 ROWS)", fill="#38BDF8", font=f_title)
    draw.text((40, 72), "Write on a plain white paper in this exact 12-row sequence. Click a top-down photo & send!", fill="#94A3B8", font=f_sub)

    y = header_height

    for i, row_chars in enumerate(rows):
        row_num = i + 1
        is_even = (i % 2 == 0)
        row_bg = "#FFFFFF" if is_even else "#F1F5F9"

        # Section labeling
        if row_num <= 4:
            section_color = "#3B82F6"
            section_tag = "UPPERCASE (A-Z)"
        elif row_num <= 8:
            section_color = "#10B981"
            section_tag = "LOWERCASE (a-z)"
        elif row_num == 9:
            section_color = "#F59E0B"
            section_tag = "NUMBERS (1-9, 0)"
        else:
            section_color = "#8B5CF6"
            section_tag = "SYMBOLS"

        draw.rectangle([40, y, width - 40, y + row_height - 10], fill=row_bg, outline="#E2E8F0", width=1)
        draw.rounded_rectangle([45, y + 8, 160, y + row_height - 18], radius=6, fill=section_color)
        draw.text((55, y + 16), f"Row {row_num:02d}", fill="#FFFFFF", font=f_row_lbl)
        draw.text((55, y + 36), section_tag[:12], fill="#FFFFFF", font=get_unicode_font(10, bold=True))

        # Characters spacing
        usable_w = width - 240
        num_chars = len(row_chars)
        char_step = usable_w / max(num_chars, 1)

        for j, char in enumerate(row_chars):
            cx = 200 + int(j * char_step + char_step / 2)
            cy = y + (row_height - 10) // 2
            draw.text((cx - 10, cy - 20), char, fill="#1E293B", font=f_char)

        y += row_height

    # Footer
    draw.rectangle([0, y + 10, width, total_height], fill="#0F172A")
    draw.text((40, y + 35), "💡 Tip: Keep small gaps between letters • Take photo in good light without shadows • Send to @HandwrittenTextGeneratorbot", fill="#38BDF8", font=f_footer)

    img.save(output_path, "PNG")
    logger.info(f"Generated official writing guide at {output_path}")
    return output_path

if __name__ == "__main__":
    generate_guide_image(str(config.STATIC_DIR / "writing_guide.png"))
    generate_guide_image(str(config.STATIC_DIR / "test_guide.png"))
    print("Writing guide generated successfully!")
