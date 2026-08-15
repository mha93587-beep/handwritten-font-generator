import os
import sys
import time
from pathlib import Path
import config
import database
from segmenter import segment_handwriting_sheet
from font_engine import compile_ttf_font
from preview_generator import generate_font_preview
from guide_generator import generate_guide_image

print("=" * 60)
print("🚀 RUNNING FULL SYSTEM TEST SUITE")
print("=" * 60)

# Test 1: Configuration & .env loading
print("\n[TEST 1] Testing Configuration & Secrets Loading...")
assert config.TELEGRAM_BOT_TOKEN, "ERROR: TELEGRAM_BOT_TOKEN not loaded from .env!"
assert config.DATABASE_URL, "ERROR: DATABASE_URL not loaded from .env!"
print(f"✅ TELEGRAM_BOT_TOKEN loaded: {config.TELEGRAM_BOT_TOKEN[:10]}... (hidden)")
print(f"✅ ADMIN_CHAT_ID: {config.ADMIN_CHAT_ID}")
print(f"✅ DATABASE_URL loaded: {config.DATABASE_URL[:30]}... (hidden)")

# Test 2: Database Connectivity
print("\n[TEST 2] Testing Neon PostgreSQL Database Connection...")
try:
    db_ok = database.init_db()
    assert db_ok, "Database init failed"
    # Test user upsert
    database.upsert_user(99999999, "test_user", "Test", "User")
    stats = database.get_global_stats()
    print(f"✅ Database connected successfully! Engine: {stats['db_type']}")
    print(f"✅ Global Stats: Users={stats['total_users']}, Fonts={stats['total_fonts']}")
except Exception as e:
    print(f"❌ Database test failed: {e}")
    sys.exit(1)

# Test 3: Visual Guide Generation
print("\n[TEST 3] Testing Visual Guide Generation...")
guide_path = config.STATIC_DIR / "test_guide.png"
res_guide = generate_guide_image(str(guide_path))
assert Path(res_guide).exists(), "Guide image not created"
print(f"✅ Writing guide image generated: {res_guide} (Size: {Path(res_guide).stat().st_size} bytes)")

# Test 4: Handwriting Image Segmentation on new official 12-row sheet
print("\n[TEST 4] Testing Handwriting Segmentation on official 12-row asset (Picsart_26-08-15_06-22-04-501.jpg)...")
sample_img = config.STATIC_DIR / "official_sample_sheet.jpg"
if not sample_img.exists():
    sample_img = config.ASSETS_DIR / "Picsart_26-08-15_06-22-04-501.jpg"
assert sample_img.exists(), f"Sample image not found at {sample_img}"

t0 = time.time()
char_map = segment_handwriting_sheet(str(sample_img))
t_seg = time.time() - t0
print(f"✅ Segmented {len(char_map)} character glyphs in {t_seg:.2f}s!")
sample_extracted = list(char_map.keys())[:15]
print(f"   Extracted sample characters: {sample_extracted}")

# Test 5: TrueType TTF Font Compilation
print("\n[TEST 5] Testing TrueType Font (.ttf) Vectorization & Compilation...")
test_ttf_path = config.OUTPUT_DIR / "TestHandwriting.ttf"
t0 = time.time()
compile_ttf_font(char_map, str(test_ttf_path), font_name="TestHandwriting", family_name="TestHandwriting")
t_font = time.time() - t0
assert test_ttf_path.exists(), "TTF font file was not generated"
ttf_size = test_ttf_path.stat().st_size
print(f"✅ Successfully compiled TrueType font: {test_ttf_path}")
print(f"   TTF File Size: {ttf_size} bytes | Generation Time: {t_font:.2f}s")

# Test 6: Specimen Preview Card Generation
print("\n[TEST 6] Testing Font Preview Card Generation...")
test_preview_path = config.OUTPUT_DIR / "TestHandwriting_preview.png"
res_prev = generate_font_preview(str(test_ttf_path), str(test_preview_path), font_display_name="Test Handwritten Font")
assert Path(res_prev).exists(), "Preview card not created"
print(f"✅ Specimen preview card generated: {res_prev} (Size: {Path(res_prev).stat().st_size} bytes)")

# Test 7: Telegram Bot API Connection
print("\n[TEST 7] Testing Telegram Bot API Connectivity...")
try:
    import telebot
    bot = telebot.TeleBot(config.TELEGRAM_BOT_TOKEN)
    me = bot.get_me()
    print(f"✅ Telegram Bot API connected successfully!")
    print(f"   Bot Username: @{me.username}")
    print(f"   Bot First Name: {me.first_name}")
    print(f"   Bot ID: {me.id}")
except Exception as e:
    print(f"❌ Telegram Bot API test failed: {e}")
    sys.exit(1)

print("\n" + "=" * 60)
print("🎉 ALL TESTS PASSED SUCCESSFULLY (100% OPERATIONAL)!")
print("=" * 60)
