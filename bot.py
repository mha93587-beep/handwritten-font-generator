import os
import time
import logging
import telebot
from telebot import types
from pathlib import Path
import config
import database
from segmenter import segment_handwriting_sheet, segment_with_gemini_ai
from font_engine import compile_ttf_font
from preview_generator import generate_font_preview
from guide_generator import generate_guide_image

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Initialize Bot
bot = telebot.TeleBot(config.TELEGRAM_BOT_TOKEN, parse_mode="HTML")

def get_main_keyboard(chat_id=None):
    """Create the clean interactive main menu inline keyboard."""
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_guide = types.InlineKeyboardButton("📖 12-Row Guide", callback_data="btn_guide")
    btn_sample = types.InlineKeyboardButton("🖼️ Sample Photo", callback_data="btn_sample")
    btn_setname = types.InlineKeyboardButton("✏️ Set Font Name", callback_data="btn_setname")
    btn_stats = types.InlineKeyboardButton("📊 My Stats", callback_data="btn_stats")
    btn_install = types.InlineKeyboardButton("💡 How to Install", callback_data="btn_install")

    markup.add(btn_guide, btn_sample)
    markup.add(btn_setname, btn_stats)
    markup.add(btn_install)

    if chat_id and config.is_admin(chat_id):
        btn_admin = types.InlineKeyboardButton("👑 Admin Panel", callback_data="btn_admin")
        markup.add(btn_admin)

    return markup

@bot.message_handler(commands=['start', 'help'])
def handle_start(message: types.Message):
    """Handle /start and /help commands with sample image and clean UI."""
    chat_id = message.chat.id
    first_name = message.from_user.first_name or "User"
    username = message.from_user.username or ""
    last_name = message.from_user.last_name or ""

    # Save/Update user in Neon DB
    database.upsert_user(chat_id, username, first_name, last_name)

    is_owner = config.is_admin(chat_id)
    owner_tag = " • 👑 <b>Admin</b>" if is_owner else ""

    welcome_caption = f"""✍️ <b>Handwritten Font Generator</b>{owner_tag}

नमस्ते <b>{first_name}</b>! अपने हाथ की लिखावट को असली <b>.ttf फॉन्ट</b> में बदलें।

📝 <b>बनाने का तरीका:</b>
1️⃣ ऊपर दिए गए फोटो की तरह सादे कागज पर 12 लाइनों में लिखें।
2️⃣ कागज की सीधी (Top-Down) फोटो यहाँ भेजें।
3️⃣ बोट तुरंत आपका <b>.ttf फ़ॉन्ट</b> बनाकर भेज देगा!

<i>✨ किसी प्रिंटर की कोई जरूरत नहीं है!</i>"""

    sample_path = config.STATIC_DIR / "official_sample_sheet.jpg"
    if not sample_path.exists():
        sample_path = config.ASSETS_DIR / "Picsart_26-08-15_06-22-04-501.jpg"

    if sample_path.exists():
        with open(sample_path, "rb") as f:
            bot.send_photo(
                chat_id,
                f,
                caption=welcome_caption,
                reply_markup=get_main_keyboard(chat_id),
                parse_mode="HTML"
            )
    else:
        bot.send_message(
            chat_id,
            welcome_caption,
            reply_markup=get_main_keyboard(chat_id),
            parse_mode="HTML"
        )

@bot.message_handler(commands=['guide'])
def handle_guide_command(message: types.Message):
    """Send the detailed writing guide."""
    send_writing_guide(message.chat.id)

@bot.message_handler(commands=['sample'])
def handle_sample_command(message: types.Message):
    """Send the reference sample photo."""
    send_sample_photo(message.chat.id)

@bot.message_handler(commands=['stats'])
def handle_stats_command(message: types.Message):
    """Show user and global stats."""
    chat_id = message.chat.id
    user_stats = database.get_user_stats(chat_id)
    global_stats = database.get_global_stats()

    stats_msg = f"""
📊 <b>आपकी स्टैटिस्टिक्स (Font Stats):</b>
• आपने कुल फॉन्ट बनाए: <b>{user_stats['total_fonts']}</b>
• सदस्य बने: <b>{str(user_stats['created_at'])[:10]}</b>

🌐 <b>ग्लोबल आंकड़े:</b>
• कुल यूज़र्स: <b>{global_stats['total_users']}</b>
• कुल जनरेट किए गए फॉन्ट्स: <b>{global_stats['total_fonts']}</b>
• डेटाबेस स्टेटस: <b>🟢 {global_stats['db_type'].upper()}</b>
"""
    bot.send_message(chat_id, stats_msg)

@bot.message_handler(commands=['setname'])
def handle_setname(message: types.Message):
    """Allow user to specify custom font family name."""
    chat_id = message.chat.id
    args = message.text.split(maxsplit=1)
    if len(args) > 1:
        custom_name = args[1].strip()
        # Clean name
        clean_name = "".join(c for c in custom_name if c.isalnum() or c in (" ", "_", "-")).strip()
        if clean_name:
            user_font_names[chat_id] = clean_name
            bot.send_message(chat_id, f"✅ आपका फॉन्ट नाम सेट हो गया: <b>{clean_name}</b>\nअब आप अपनी हैंडराइटिंग की फोटो भेजें!")
            return
    bot.send_message(chat_id, "ℹ️ फॉन्ट नाम सेट करने के लिए इस तरह लिखें:\n<code>/setname MyHandwriting</code> या <code>/setname RohitFont</code>")

@bot.message_handler(commands=['admin'])
def handle_admin_command(message: types.Message):
    """Admin dashboard command."""
    chat_id = message.chat.id
    if not config.is_admin(chat_id):
        bot.send_message(chat_id, "⛔ आप इस कमांड के लिए अधिकृत नहीं हैं।")
        return

    global_stats = database.get_global_stats()
    admin_msg = f"""
👑 <b>ADMIN & OWNER DASHBOARD:</b>

👥 Total Users: <b>{global_stats['total_users']}</b>
🎨 Fonts Created: <b>{global_stats['total_fonts']}</b>
🔤 Total Glyphs Vectorized: <b>{global_stats['total_glyphs']}</b>
💾 Database Engine: <b>{global_stats['db_type'].upper()}</b>
🔑 Admin Chat ID: <code>{chat_id}</code>

<b>Available Admin Commands:</b>
• <code>/broadcast &lt;message&gt;</code> - Send message to all users
• <code>/users</code> - View recent registered users list
• <code>/stats</code> - View global system stats
"""
    bot.send_message(chat_id, admin_msg)

@bot.message_handler(commands=['users'])
def handle_users_command(message: types.Message):
    """Admin command to list users."""
    chat_id = message.chat.id
    if not config.is_admin(chat_id):
        bot.send_message(chat_id, "⛔ आप इस कमांड के लिए अधिकृत नहीं हैं।")
        return

    user_ids = database.get_all_user_ids()
    users_text = f"👥 <b>Total Registered Users: {len(user_ids)}</b>\n\n"
    for idx, uid in enumerate(user_ids[:30], 1):
        users_text += f"{idx}. <code>{uid}</code>\n"
    if len(user_ids) > 30:
        users_text += f"\n<i>...and {len(user_ids) - 30} more users.</i>"

    bot.send_message(chat_id, users_text)

@bot.message_handler(commands=['broadcast'])
def handle_broadcast(message: types.Message):
    """Admin broadcast command."""
    chat_id = message.chat.id
    if not config.is_admin(chat_id):
        bot.send_message(chat_id, "⛔ आप इस कमांड के लिए अधिकृत नहीं हैं।")
        return

    text_parts = message.text.split(maxsplit=1)
    if len(text_parts) < 2:
        bot.send_message(chat_id, "⚠️ उपयोग: <code>/broadcast आपका संदेश</code>")
        return

    broadcast_msg = text_parts[1]
    user_ids = database.get_all_user_ids()
    sent_count = 0
    failed_count = 0

    status_msg = bot.send_message(chat_id, f"📢 ब्रॉडकास्ट शुरू हो रहा है... ({len(user_ids)} यूज़र्स को)")

    for uid in user_ids:
        try:
            bot.send_message(uid, f"📢 <b>Announcement / सूचना:</b>\n\n{broadcast_msg}")
            sent_count += 1
            time.sleep(0.05)
        except Exception:
            failed_count += 1

    bot.edit_message_text(
        f"✅ ब्रॉडकास्ट पूरा हुआ!\n• सफलतापूर्वक भेजा गया: {sent_count}\n• विफल: {failed_count}",
        chat_id,
        status_msg.message_id
    )

def send_writing_guide(chat_id: int):
    """Send the clean visual writing guide."""
    guide_img_path = config.STATIC_DIR / "writing_guide.png"
    if not guide_img_path.exists():
        generate_guide_image(str(guide_img_path))

    caption = """📖 <b>12-Row Writing Guide</b>

1. साफ <b>सादा सफेद कागज</b> लें (बिना लाइन वाला)।
2. गहरे काले या नीले पेन से 12 लाइनों में लिखें:
   • <b>1-4:</b> बड़े अक्षर (A - Z)
   • <b>5-8:</b> छोटे अक्षर (a - z)
   • <b>9:</b> अंक (1 2 3 4 5 6 7 8 9 0)
   • <b>10-12:</b> सिम्बल्स (. , ; : ! ? " ' - + = / % & ( ) [ ])
3. अक्षरों में हल्का गैप रखें और ऊपर से सीधी फोटो भेजें! 📸"""
    try:
        with open(guide_img_path, "rb") as photo:
            bot.send_photo(chat_id, photo, caption=caption, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error sending guide photo: {e}")
        bot.send_message(chat_id, caption, parse_mode="HTML")

def send_sample_photo(chat_id: int):
    """Send the real handwritten sample image as clean reference."""
    sample_path = config.STATIC_DIR / "official_sample_sheet.jpg"
    if not sample_path.exists():
        sample_path = config.ASSETS_DIR / "Picsart_26-08-15_06-22-04-501.jpg"
    if sample_path.exists():
        with open(sample_path, "rb") as f:
            bot.send_photo(
                chat_id,
                f,
                caption="📝 <b>हैंडराइटिंग सैंपल शीट</b>\nसादे सफेद कागज पर इसी तरह 12 लाइनों में लिखकर फ़ोटो भेजें!",
                parse_mode="HTML"
            )
    else:
        bot.send_message(chat_id, "⚠️ सैंपल फ़ोटो उपलब्ध नहीं है। कृपया /guide देखें।")

def send_install_instructions(chat_id: int):
    """Send concise font installation guide."""
    msg = """💡 <b>फ़ॉन्ट (.ttf) कैसे इस्तेमाल करें:</b>

💻 <b>Windows / Mac:</b> फ़ाइल खोलकर <b>Install</b> पर क्लिक करें।
📱 <b>Canva / Pixellab / CapCut:</b> Text टूल में जाकर .ttf फ़ाइल अपलोड करें।"""
    bot.send_message(chat_id, msg)

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call: types.CallbackQuery):
    """Handle inline button clicks."""
    chat_id = call.message.chat.id
    if call.data == "btn_guide":
        send_writing_guide(chat_id)
    elif call.data == "btn_sample":
        send_sample_photo(chat_id)
    elif call.data == "btn_stats":
        handle_stats_command(call.message)
    elif call.data == "btn_install":
        send_install_instructions(chat_id)
    elif call.data == "btn_setname":
        bot.send_message(chat_id, "✏️ फॉन्ट का नया नाम रखने के लिए लिखें:\n<code>/setname MyAwesomeFont</code>")
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass

@bot.message_handler(content_types=['photo', 'document'])
def handle_photo_upload(message: types.Message):
    """Process incoming handwritten image and generate TTF font."""
    chat_id = message.chat.id
    start_time = time.time()

    # Get user font name
    font_name = user_font_names.get(chat_id, f"HandwrittenFont_{chat_id % 10000:04d}")

    # Send initial processing message
    status_msg = bot.send_message(
        chat_id,
        "📥 <b>फोटो प्राप्त हुई!</b>\n⏳ <i>Step 1/4: इमेज स्कैन व लाइन डिटेक्शन जारी है...</i>"
    )

    try:
        # Determine file_id
        if message.photo:
            # Highest resolution photo
            file_id = message.photo[-1].file_id
        elif message.document and message.document.mime_type.startswith("image/"):
            file_id = message.document.file_id
        else:
            bot.edit_message_text(
                "❌ कृपया एक इमेज (फोटो) फाइल भेजें (JPG / PNG)।",
                chat_id,
                status_msg.message_id
            )
            return

        # Download file
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        temp_img_path = config.TEMP_DIR / f"upload_{chat_id}_{int(time.time())}.jpg"
        with open(temp_img_path, "wb") as f:
            f.write(downloaded_file)

        # Step 2: Segment characters
        bot.edit_message_text(
            "✂️ <b>Step 2/4: अक्षरों को स्कैन व वेक्टर कंटूर में बदला जा रहा है...</b>",
            chat_id,
            status_msg.message_id
        )

        char_map = None
        # Try Gemini Vision AI if API key is provided
        if config.GEMINI_API_KEY:
            try:
                char_map = segment_with_gemini_ai(str(temp_img_path))
            except Exception as e:
                logger.warning(f"Gemini segmentation fallback: {e}")

        # If Gemini not configured or returned empty, use computer vision segmenter
        if not char_map or len(char_map) < 5:
            char_map = segment_handwriting_sheet(str(temp_img_path))

        if not char_map or len(char_map) == 0:
            bot.edit_message_text(
                "❌ <b>कोई अक्षर डिटेक्ट नहीं हो सका!</b>\n\nकृपया सुनिश्चित करें कि कागज पर अक्षर साफ और अच्छी रोशनी में लिखे हों। /guide देखकर दोबारा कोशिश करें।",
                chat_id,
                status_msg.message_id
            )
            return

        # Step 3: Compile TTF Font
        bot.edit_message_text(
            f"🛠️ <b>Step 3/4: {len(char_map)} अक्षरों के साथ TrueType (.ttf) फॉन्ट बनाया जा रहा है...</b>",
            chat_id,
            status_msg.message_id
        )

        output_ttf_path = config.OUTPUT_DIR / f"{font_name}.ttf"
        compile_ttf_font(char_map, str(output_ttf_path), font_name=font_name, family_name=font_name)

        # Step 4: Generate Preview Specimen Card
        bot.edit_message_text(
            "🎨 <b>Step 4/4: फॉन्ट प्रीव्यू कार्ड तैयार किया जा रहा है...</b>",
            chat_id,
            status_msg.message_id
        )

        output_preview_path = config.OUTPUT_DIR / f"{font_name}_preview.png"
        generate_font_preview(str(output_ttf_path), str(output_preview_path), font_display_name=font_name)

        elapsed_time = round(time.time() - start_time, 2)

        # Log to Database
        database.log_font_generation(
            chat_id=chat_id,
            font_name=font_name,
            glyphs_count=len(char_map),
            processing_time=elapsed_time,
            status="success"
        )

        # Send Preview Photo
        with open(output_preview_path, "rb") as preview_file:
            bot.send_photo(
                chat_id,
                preview_file,
                caption=f"🎉 <b>आपका फ़ॉन्ट तैयार है!</b>\n\n🔤 <b>Font:</b> <code>{font_name}</code>\n📊 <b>Glyphs:</b> <code>{len(char_map)}</code>\n⚡ <b>Speed:</b> <code>{elapsed_time}s</code>",
                parse_mode="HTML"
            )

        # Send .ttf Font Document
        with open(output_ttf_path, "rb") as ttf_file:
            bot.send_document(
                chat_id,
                ttf_file,
                caption=f"📥 <b>{font_name}.ttf</b> — इसे Canva, Photoshop, Windows या Android में इनस्टॉल करें!",
                parse_mode="HTML"
            )

        # Delete processing message
        try:
            bot.delete_message(chat_id, status_msg.message_id)
        except Exception:
            pass

        # Clean temp upload
        if temp_img_path.exists():
            temp_img_path.unlink()

        # Notify Admin
        if config.ADMIN_CHAT_ID and config.ADMIN_CHAT_ID != chat_id:
            try:
                bot.send_message(
                    config.ADMIN_CHAT_ID,
                    f"🔔 <b>New Font Generated!</b>\n• User Chat ID: <code>{chat_id}</code>\n• Font Name: <b>{font_name}</b>\n• Glyphs: <b>{len(char_map)}</b>\n• Time: <b>{elapsed_time}s</b>"
                )
            except Exception:
                pass

    except Exception as e:
        logger.error(f"Error processing image: {e}", exc_info=True)
        bot.edit_message_text(
            f"❌ <b>फ़ॉन्ट बनाने में समस्या आई:</b>\n<code>{str(e)[:200]}</code>\n\nकृपया साफ़ फ़ोटो के साथ दोबारा प्रयास करें या /guide देखें।",
            chat_id,
            status_msg.message_id
        )

def run_bot_polling():
    """Start Telegram bot with resilient infinite polling."""
    logger.info("Starting Telegram Bot Polling...")
    database.init_db()
    # Generate guide asset if missing
    guide_path = config.STATIC_DIR / "writing_guide.png"
    if not guide_path.exists():
        generate_guide_image(str(guide_path))

    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            logger.error(f"Bot polling exception: {e}. Retrying in 5 seconds...")
            time.sleep(5)

if __name__ == "__main__":
    run_bot_polling()
