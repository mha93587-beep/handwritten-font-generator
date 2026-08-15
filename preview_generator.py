import os
import logging
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import config

logger = logging.getLogger(__name__)

def get_system_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Load bundled DejaVuSans TrueType font for UI headers and labels."""
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

def generate_font_preview(ttf_path: str, output_image_path: str, font_display_name: str = "My Custom Font") -> str:
    """
    Render a crisp specimen card using the generated custom TTF font.
    """
    w, h = 1300, 850
    card = Image.new("RGB", (w, h), "#0F172A")
    draw = ImageDraw.Draw(card)

    # Main Card
    draw.rounded_rectangle([30, 30, w - 30, h - 30], radius=16, fill="#1E293B", outline="#334155", width=2)

    # UI Fonts
    f_ui_badge = get_system_font(14, bold=True)
    f_ui_label = get_system_font(14, bold=True)
    f_ui_footer = get_system_font(13, bold=False)

    # Custom Handwritten Fonts
    try:
        f_title = ImageFont.truetype(ttf_path, 44)
        f_pangram = ImageFont.truetype(ttf_path, 34)
        f_upper = ImageFont.truetype(ttf_path, 28)
        f_lower = ImageFont.truetype(ttf_path, 28)
        f_digits = ImageFont.truetype(ttf_path, 28)
        f_symbols = ImageFont.truetype(ttf_path, 24)
    except Exception as e:
        logger.warning(f"Error loading custom font for preview ({e}), falling back to system font.")
        f_title = get_system_font(44, bold=True)
        f_pangram = get_system_font(34, bold=False)
        f_upper = f_lower = f_digits = f_symbols = get_system_font(28, bold=False)

    # Top Header
    draw.text((60, 60), "HANDWRITTEN FONT SPECIMEN", fill="#38BDF8", font=f_ui_badge)
    draw.text((60, 90), font_display_name, fill="#F8FAFC", font=f_title)
    draw.line([60, 155, w - 60, 155], fill="#334155", width=1)

    # Pangram Sentence
    draw.text((60, 175), "PANGRAM SENTENCE (34pt):", fill="#94A3B8", font=f_ui_label)
    draw.text((60, 205), "The quick brown fox jumps over the lazy dog.", fill="#F1F5F9", font=f_pangram)

    # Uppercase Alphabet
    draw.text((60, 280), "UPPERCASE ALPHABET (A-Z):", fill="#94A3B8", font=f_ui_label)
    draw.text((60, 310), "A B C D E F G H I J K L M N O P Q R S T U V W X Y Z", fill="#E2E8F0", font=f_upper)

    # Lowercase Alphabet
    draw.text((60, 385), "LOWERCASE ALPHABET (a-z):", fill="#94A3B8", font=f_ui_label)
    draw.text((60, 415), "a b c d e f g h i j k l m n o p q r s t u v w x y z", fill="#E2E8F0", font=f_lower)

    # Numerals
    draw.text((60, 490), "NUMERALS & DIGITS (0-9):", fill="#94A3B8", font=f_ui_label)
    draw.text((60, 520), "0 1 2 3 4 5 6 7 8 9", fill="#38BDF8", font=f_digits)

    # Symbols & Punctuation
    draw.text((60, 595), "SYMBOLS & PUNCTUATION:", fill="#94A3B8", font=f_ui_label)
    draw.text((60, 625), ". , ; : ! ? \" ' - + = / % & ( ) [ ]", fill="#CBD5E1", font=f_symbols)

    # Footer
    draw.line([60, 750, w - 60, 750], fill="#334155", width=1)
    draw.text((60, 770), "Generated with Handwritten Font Generator Bot • Install .ttf on Windows, Mac, Android, iOS, Canva, Photoshop", fill="#64748B", font=f_ui_footer)

    card.save(output_image_path, "PNG")
    return output_image_path
