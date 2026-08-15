# ✍️ Handwritten Font Generator Telegram Bot & Web App

A complete, AI-powered system that transforms photos of plain handwritten paper into installable TrueType (`.ttf`) fonts. Includes a Telegram Bot and a Streamlit Web Dashboard ready to host for free on **Streamlit Community Cloud**.

---

## 🌟 Key Features

- **No Printer or Form Needed**: Users can simply write on any plain white blank sheet or lined notebook.
- **Automated TrueType Vectorization**: Automatically extracts character bounding boxes, computes vector bezier contours, aligns baselines/descenders, and compiles real `.ttf` font files with standard Unicode mappings (`cmap`, `glyf`, `hmtx`, `OS/2`).
- **Interactive Font Specimen Preview**: Generates high-res image previews of the font displaying pangrams, uppercase/lowercase alphabets, and numbers.
- **Neon PostgreSQL Database**: Automatically stores user profiles, stats, generation logs, and broadcast history.
- **Dual Mode (Telegram Bot + Streamlit Cloud App)**: Runs 24/7 on Streamlit Free Cloud with an interactive live typing sandbox in the browser alongside background Telegram polling.
- **Gemini Vision AI Support**: Optional Gemini Vision integration for advanced OCR/bounding box parsing.

---

## 📋 Official Character Layout Reference (12 Rows)

Users write the following characters in order on their plain white sheet:

```text
Row 01: A B C D E F G
Row 02: H I J K L M N
Row 03: O P Q R S T U
Row 04: V W X Y Z
Row 05: a b c d e f g
Row 06: h i j k l m n
Row 07: o p q r s t u v
Row 08: w x y z
Row 09: 1 2 3 4 5 6 7 8 9 0
Row 10: . , ; : ! ? " ' -
Row 11: + = / % & ( )
Row 12: [ ]
```

---

## 🚀 How to Host on Streamlit Community Cloud (Free 24/7)

1. Push this repository to GitHub.
2. Go to [share.streamlit.io](https://share.streamlit.io/) and click **New App**.
3. Select your repository, branch, and set Main file path: `app.py`.
4. Under **Advanced Settings** -> **Secrets**, paste your environment variables:
   ```toml
   TELEGRAM_BOT_TOKEN = "your_telegram_bot_token_here"
   ADMIN_CHAT_ID = "your_admin_chat_id_here"
   DATABASE_URL = "your_neon_postgres_url_here"
   GEMINI_API_KEY = "optional_gemini_api_key_here"
   ```
5. Click **Deploy**! Streamlit Cloud will run the web app and start the Telegram Bot in the background automatically!

---

## 💻 How to Run Locally

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run Streamlit App + Telegram Bot
streamlit run app.py

# Or run Telegram Bot standalone:
python bot.py
```

---

## 🤖 Telegram Bot Commands

- `/start` - Welcome message and interactive menu.
- `/guide` - View visual writing guide and instructions.
- `/sample` - View reference handwritten sheet photo.
- `/setname <FontName>` - Set custom name for your font (e.g. `/setname RohitFont`).
- `/stats` - View your font generation statistics.
- `/admin` - Admin control panel (Authorized admin only).
- `/broadcast <message>` - Send announcement to all bot users.
