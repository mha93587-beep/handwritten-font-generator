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

# User custom font names cache {chat_id: font_name}
user_font_names = {}

def get_main_keyboard():
    """Create the interactive main menu inline keyboard."""
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_guide = types.InlineKeyboardButton("📖 Writing Guide (लिखने का तरीका)", callback_data="btn_guide")
    btn_sample = types.InlineKeyboardButton("🖼️ Sample Photo (उदाहरण)", callback_data="btn_sample")
    btn_setname = types.InlineKeyboardButton("✏️ Set Font Name (नाम बदलें)", callback_data="btn_setname")
    btn_stats = types.InlineKeyboardButton("📊 My Stats (मेरी स्टैट्स)", callback_data="btn_stats")
    btn_install = types.InlineKeyboardButton("💡 How to Install (उपयोग विधि)", callback_data="btn_install")
    btn_admin = types.InlineKeyboardButton("⚡ Admin Panel", callback_data="btn_admin")
    
    markup.add(btn_guide, btn_sample)
    markup.add(btn_setname, btn_stats)
    markup.add(btn_install)
    return markup

@bot.message_handler(commands=['start', 'help'])
def handle_start(message: types.Message):
    """Handle /start and /help commands."""
    chat_id = message.chat.id
    first_name = message.from_user.first_name or "User"
    username = message.from_user.username or ""
    last_name = message.from_user.last_name or ""

    # Save/Update user in Neon DB
    database.upsert_user(chat_id, username, first_name, last_name)

    welcome_text = f"""
👋 <b>नमस्ते {first_name}! Handwritten Font Generator Bot में आपका स्वागत है! ✍️</b>

यह बोट आपके हाथों से लिखे गए अक्षरों को एक <b>असली TrueType Font (.ttf)</b> फाइल में बदल देगा!

🚀 <b>कैसे इस्तेमाल करें:</b>
1️⃣ एक सादा सफेद कागज (Plain White Paper) लें।
2️⃣ काले या नीले पेन से हमारे गाइड के अनुसार सभी अक्षर लिखें।
3️⃣ उस कागज की सीधी, साफ फ़ोटो खींचकर यहाँ भेजें।
4️⃣ बोट तुरंत आपका <b>.ttf फॉन्ट</b> बनाकर आपको भेज देगा!

<i>✨ किसी प्रिंटर या स्पेशल फॉर्म की कोई जरूरत नहीं है!</i>

नीचे दिए गए बटनों से गाइड देखें या सीधे फोटो अपलोड करें:
"""
    bot.send_message(chat_id, welcome_text, reply_markup=get_main_keyboard())

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
    if config.ADMIN_CHAT_ID and chat_id != config.ADMIN_CHAT_ID:
        bot.send_message(chat_id, "⛔ आप इस कमांड के लिए अधिकृत नहीं हैं।")
        return

    global_stats = database.get_global_stats()
    admin_msg = f"""
⚡ <b>ADMIN DASHBOARD:</b>

👥 Total Users: <b>{global_stats['total_users']}</b>
🎨 Fonts Created: <b>{global_stats['total_fonts']}</b>
🔤 Total Glyphs Extracted: <b>{global_stats['total_glyphs']}</b>
💾 Database Engine: <b>{global_stats['db_type']}</b>

<b>Admin Commands:</b>
• <code>/broadcast &lt;message&gt;</code> - Send message to all users
• <code>/users</code> - List recent user IDs
• <code>/stats</code> - View system stats
"""
    bot.send_message(chat_id, admin_msg)

@bot.message_handler(commands=['broadcast'])
def handle_broadcast(message: types.Message):
    """Admin broadcast command."""
    chat_id = message.chat.id
    if config.ADMIN_CHAT_ID and chat_id != config.ADMIN_CHAT_ID:
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
    """Send the generated writing guide image and instructions."""
    guide_img_path = config.STATIC_DIR / "writing_guide.png"
    if not guide_img_path.exists():
        generate_guide_image(str(guide_img_path))

    caption = """
📖 <b>कागज पर लिखने का नया 12-Row फॉर्मेट (Writing Guide):</b>

1. एक साफ <b>सादा सफेद कागज (Plain White Paper)</b> लें।
2. डार्क काले या नीले पेन से अक्षर लिखें।
3. नीचे दी गई <b>12 पंक्तियों (Rows)</b> के सही क्रम में लिखें:
   • <b>पंक्ति 1-4:</b> बड़े अक्षर (A, B, C, D... Z)
   • <b>पंक्ति 5-8:</b> छोटे अक्षर (a, b, c, d... z)
   • <b>पंक्ति 9:</b> अंक (1 2 3 4 5 6 7 8 9 0)
   • <b>पंक्ति 10-12:</b> सिम्बल्स (. , ; : ! ? " ' - + = / % & ( ) [ ])
4. अक्षरों के बीच थोड़ा स्पेस रखें ताकि वे आपस में न जुड़ें।
5. अच्छी रोशनी में ऊपर से सीधी (Top-Down) फोटो खींचकर भेजें! 📸
"""
    try:
        with open(guide_img_path, "rb") as photo:
            bot.send_photo(chat_id, photo, caption=caption, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error sending guide photo: {e}")
        bot.send_message(chat_id, caption, parse_mode="HTML")

def send_sample_photo(chat_id: int):
    """Send the real handwritten sample image as reference."""
    sample_path = config.STATIC_DIR / "official_sample_sheet.jpg"
    if not sample_path.exists():
        sample_path = config.ASSETS_DIR / "Picsart_26-08-15_06-22-04-501.jpg"
    if sample_path.exists():
        with open(sample_path, "rb") as f:
            bot.send_photo(
                chat_id,
                f,
                caption="📝 <b>यह देखिए रियल उदाहरण (Official 12-Row Sample Sheet):</b>\nआप भी इसी तरह सादे सफेद कागज पर 12 पंक्तियों में लिखकर फ़ोटो भेज सकते हैं!",
                parse_mode="HTML"
            )
    else:
        bot.send_message(chat_id, "⚠️ सैंपल फ़ोटो उपलब्ध नहीं है। कृपया /guide देखें।")

def send_install_instructions(chat_id: int):
    """Send font installation guide."""
    msg = """
💡 <b>फॉन्ट (.ttf) का उपयोग और इनस्टॉल कैसे करें:</b>

💻 <b>Windows PC में:</b>
1. .ttf फाइल डाउनलोड करें।
2. फाइल पर Right Click करें और <b>'Install'</b> पर क्लिक करें।
3. MS Word, Photoshop, Premiere आदि में फॉन्ट चुनकर टाइप करें!

🍎 <b>Mac OS में:</b>
1. .ttf फाइल खोलें और <b>'Install Font'</b> पर क्लिक करें।

📱 <b>Android / iPhone (Mobile) में:</b>
• <b>Canva / Pixellab / InShot / CapCut:</b> Text टूल में जाकर 'Upload Font' चुनें और .ttf फाइल सेलेक्ट करें।
• <b>zFont 3:</b> पूरे सिस्टम का फॉन्ट बदलने के लिए zFont ऐप का इस्तेमाल कर सकते हैं।
"""
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
                caption=f"🎉 <b>बधाई हो! आपका फॉन्ट तैयार है!</b>\n\n📝 फॉन्ट का नाम: <b>{font_name}</b>\n🔤 कुल अक्षर: <b>{len(char_map)}</b>\n⚡ प्रोसेसिंग समय: <b>{elapsed_time}s</b>",
                parse_mode="HTML"
            )

        # Send .ttf Font Document
        with open(output_ttf_path, "rb") as ttf_file:
            bot.send_document(
                chat_id,
                ttf_file,
                caption=f"📥 <b>{font_name}.ttf</b> फ़ाइल को डाउनलोड करके अपने PC या Mobile में इनस्टॉल करें!\n\n💡 इनस्टॉल करने की जानकारी के लिए /help या बटन दबाएं।",
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
