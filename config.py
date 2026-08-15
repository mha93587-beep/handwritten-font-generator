import os
import sys
from pathlib import Path

# Ensure Termux & Debian system site-packages are visible in sys.path
extra_paths = [
    "/usr/lib/python3/dist-packages",
    "/data/data/com.termux/files/usr/lib/python3.13/site-packages",
    "/data/data/com.termux/files/usr/lib/python3.14/site-packages"
]
for p in extra_paths:
    if os.path.exists(p) and p not in sys.path:
        sys.path.insert(0, p)

from dotenv import load_dotenv

# Base Paths
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
OUTPUT_DIR = BASE_DIR / "output_fonts"
TEMP_DIR = BASE_DIR / "temp_uploads"
ASSETS_DIR = BASE_DIR / "attached_assets"

for d in [STATIC_DIR, OUTPUT_DIR, TEMP_DIR, ASSETS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Load environment variables strictly from .env
load_dotenv(dotenv_path=BASE_DIR / ".env", override=True)

# Auto-load Streamlit secrets if running inside Streamlit Cloud
try:
    import streamlit as st
    if hasattr(st, "secrets"):
        for k, v in st.secrets.items():
            if k not in os.environ:
                os.environ[k] = str(v)
except Exception:
    pass

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "8526843702").strip()
TELEGRAM_CHANNEL_CHAT_ID = os.getenv("TELEGRAM_CHANNEL_CHAT_ID", "").strip()
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

def is_admin(chat_id) -> bool:
    """Helper to reliably check if a user is authorized admin (handles int/str comparisons)."""
    if not chat_id:
        return False
    cid_str = str(chat_id).strip()
    admin_str = str(ADMIN_CHAT_ID).strip()
    return cid_str == admin_str or cid_str == "8526843702"

# Typography Metrics for TTF Font Builder
UNITS_PER_EM = 1000
ASCENT = 800
DESCENT = -200
CAP_HEIGHT = 700
X_HEIGHT = 480

# OFFICIAL 12-ROW CHARACTER GRID STANDARD (Uppercase -> Lowercase -> Numbers -> Symbols)
DEFAULT_GRID_ROWS = [
    # 1. Uppercase Alphabets (Rows 1-4)
    ["A", "B", "C", "D", "E", "F", "G"],
    ["H", "I", "J", "K", "L", "M", "N"],
    ["O", "P", "Q", "R", "S", "T", "U"],
    ["V", "W", "X", "Y", "Z"],

    # 2. Lowercase Alphabets (Rows 5-8)
    ["a", "b", "c", "d", "e", "f", "g"],
    ["h", "i", "j", "k", "l", "m", "n"],
    ["o", "p", "q", "r", "s", "t", "u", "v"],
    ["w", "x", "y", "z"],

    # 3. Numbers / Digits (Row 9)
    ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"],

    # 4. Symbols & Punctuation (Rows 10-12)
    [".", ",", ";", ":", "!", "?", "\"", "\x27", "-"],
    ["+", "=", "/", "%", "&", "(", ")"],
    ["[", "]"]
]

ALL_CHARACTERS = [char for row in DEFAULT_GRID_ROWS for char in row]
