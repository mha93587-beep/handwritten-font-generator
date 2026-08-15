import os
import time
import base64
import threading
import logging
from pathlib import Path
import streamlit as st
from PIL import Image

import config
import database
from segmenter import segment_handwriting_sheet, segment_with_gemini_ai
from font_engine import compile_ttf_font
from preview_generator import generate_font_preview
from guide_generator import generate_guide_image

# Configure Streamlit page
st.set_page_config(
    page_title="AI Handwritten Font Generator & Bot",
    page_icon="✍️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for state-of-the-art UI
st.markdown("""
<style>
    /* Dark aesthetic styling */
    .main-header {
        font-size: 2.2rem;
        font-weight: 800;
        background: linear-gradient(135deg, #38BDF8, #818CF8);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        color: #94A3B8;
        font-size: 1rem;
        margin-bottom: 1.5rem;
    }
    .status-badge {
        display: inline-flex;
        align-items: center;
        padding: 6px 14px;
        background-color: #064E3B;
        color: #34D399;
        border-radius: 9999px;
        font-weight: 600;
        font-size: 0.85rem;
        border: 1px solid #059669;
    }
    .stat-card {
        background: #1E293B;
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
    }
    .stat-val {
        font-size: 1.8rem;
        font-weight: 700;
        color: #F8FAFC;
    }
    .stat-lbl {
        color: #94A3B8;
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
</style>
""", unsafe_allow_html=True)

# ----------------- BACKGROUND TELEGRAM BOT THREAD -----------------
@st.cache_resource
def start_bot_background():
    """Start Telegram bot in background thread only once per Streamlit instance."""
    if not config.TELEGRAM_BOT_TOKEN:
        return False, "TELEGRAM_BOT_TOKEN not configured"

    try:
        from bot import run_bot_polling
        bot_thread = threading.Thread(target=run_bot_polling, daemon=True, name="TelegramBotWorker")
        bot_thread.start()
        return True, "Running"
    except Exception as e:
        return False, str(e)

# Start background bot
bot_active, bot_status_msg = start_bot_background()

# Initialize Database
database.init_db()

# ----------------- SIDEBAR -----------------
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/calligraphy.png", width=64)
    st.markdown("### ✍️ Font Generator Bot")
    
    if bot_active:
        st.markdown('<div class="status-badge">🟢 Telegram Bot: Active</div>', unsafe_allow_html=True)
    else:
        st.error(f"🔴 Bot Error: {bot_status_msg}")

    st.markdown("---")
    st.markdown("#### ⚙️ System Status")
    stats = database.get_global_stats()
    st.markdown(f"**Database:** `{stats['db_type'].upper()}`")
    st.markdown(f"**Admin Chat ID:** `{config.ADMIN_CHAT_ID or 'Not Set'}`")
    st.markdown(f"**Gemini AI:** `{'Enabled' if config.GEMINI_API_KEY else 'Auto (Local CV)'}`")
    
    st.markdown("---")
    st.markdown("#### 📱 Telegram Channel & Bot")
    st.info("You can send handwritten paper photos directly to your Telegram bot 24/7!")
    
    st.markdown("---")
    st.caption("Handwritten Font Generator v1.0 • Antigravity AI")

# ----------------- MAIN UI -----------------
st.markdown('<div class="main-header">✍️ Handwritten Font Generator & Telegram Bot</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Convert photos of plain handwritten paper into real installable TrueType (.ttf) fonts automatically!</div>', unsafe_allow_html=True)

# Top KPI Summary Cards
kpi1, kpi2, kpi3, kpi4 = st.columns(4)
with kpi1:
    st.markdown(f'<div class="stat-card"><div class="stat-val">{stats["total_users"]}</div><div class="stat-lbl">Total Users</div></div>', unsafe_allow_html=True)
with kpi2:
    st.markdown(f'<div class="stat-card"><div class="stat-val">{stats["total_fonts"]}</div><div class="stat-lbl">Fonts Generated</div></div>', unsafe_allow_html=True)
with kpi3:
    st.markdown(f'<div class="stat-card"><div class="stat-val">{stats["total_glyphs"]}</div><div class="stat-lbl">Glyphs Vectorized</div></div>', unsafe_allow_html=True)
with kpi4:
    st.markdown(f'<div class="stat-card"><div class="stat-val">24/7</div><div class="stat-lbl">Streamlit & Bot Cloud</div></div>', unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# Tabs
tab_create, tab_guide, tab_stats, tab_install = st.tabs([
    "✨ Web Font Generator",
    "📖 Writing Guide & Template",
    "📊 Analytics & DB Logs",
    "💡 How to Install Fonts"
])

# ----------------- TAB 1: WEB GENERATOR -----------------
with tab_create:
    st.markdown("### 🎨 Create Font from Handwritten Sheet")
    st.write("Upload a clear photo of your handwriting written on a plain white paper or ruled notebook.")

    col_input, col_preview = st.columns([1, 1])

    with col_input:
        uploaded_file = st.file_uploader("Upload Handwriting Photo (JPG / PNG)", type=["jpg", "jpeg", "png"])
        font_family_name = st.text_input("Font Family Name", value="MyHandwriting").strip() or "MyHandwriting"
        
        # Clean font name
        font_family_name = "".join(c for c in font_family_name if c.isalnum() or c in (" ", "_", "-")).strip()

        use_sample = st.checkbox("Or test with provided sample image (`IMG_20260814_185829.jpg`)", value=False)

        generate_btn = st.button("🚀 Vectorize & Generate TTF Font", type="primary", use_container_width=True)

    img_to_process = None
    if uploaded_file is not None:
        img_to_process = Image.open(uploaded_file)
        with col_preview:
            st.image(img_to_process, caption="Uploaded Handwriting Sheet", use_container_width=True)
    elif use_sample:
        sample_path = config.ASSETS_DIR / "IMG_20260814_185829.jpg"
        if sample_path.exists():
            img_to_process = Image.open(sample_path)
            with col_preview:
                st.image(img_to_process, caption="Sample Reference Sheet", use_container_width=True)

    if generate_btn and img_to_process:
        start_time = time.time()
        with st.spinner("⏳ Analyzing sheet, segmenting characters and tracing vector outlines..."):
            temp_path = config.TEMP_DIR / f"web_upload_{int(time.time())}.jpg"
            img_to_process.save(temp_path, "JPEG")

            # Extract character glyphs
            char_map = None
            if config.GEMINI_API_KEY:
                try:
                    char_map = segment_with_gemini_ai(str(temp_path))
                except Exception as e:
                    st.warning(f"Gemini fallback: {e}")

            if not char_map or len(char_map) < 5:
                char_map = segment_handwriting_sheet(str(temp_path))

            if not char_map:
                st.error("❌ No characters could be extracted. Please check the image lighting and layout.")
            else:
                st.success(f"✅ Successfully extracted {len(char_map)} character glyphs!")
                
                # Compile TrueType font
                out_ttf = config.OUTPUT_DIR / f"{font_family_name}.ttf"
                compile_ttf_font(char_map, str(out_ttf), font_name=font_family_name, family_name=font_family_name)

                # Generate Preview Card
                out_preview = config.OUTPUT_DIR / f"{font_family_name}_preview.png"
                generate_font_preview(str(out_ttf), str(out_preview), font_display_name=font_family_name)

                elapsed = round(time.time() - start_time, 2)
                
                # Record to Database
                database.log_font_generation(
                    chat_id=0,
                    font_name=font_family_name,
                    glyphs_count=len(char_map),
                    processing_time=elapsed,
                    status="success"
                )

                st.markdown("---")
                st.markdown("### 🎉 Generated Font Results")

                res_col1, res_col2 = st.columns([1.2, 1])
                with res_col1:
                    st.image(str(out_preview), caption="Font Specimen Preview Card", use_container_width=True)

                with res_col2:
                    st.markdown(f"**Font Name:** `{font_family_name}`")
                    st.markdown(f"**Total Glyphs:** `{len(char_map)}`")
                    st.markdown(f"**Generation Time:** `{elapsed}s`")

                    with open(out_ttf, "rb") as f:
                        ttf_bytes = f.read()

                    st.download_button(
                        label="📥 Download TrueType Font (.ttf)",
                        data=ttf_bytes,
                        file_name=f"{font_family_name}.ttf",
                        mime="font/ttf",
                        type="primary",
                        use_container_width=True
                    )

                # Live Interactive Web Sandbox
                st.markdown("### 🔤 Interactive Live Font Sandbox")
                st.write("Type anything below to test your new custom handwritten font in real-time right in your browser!")

                b64_font = base64.b64encode(ttf_bytes).decode("utf-8")
                test_text = st.text_area("Live Test Text", value="Hello World! This is my real handwritten font created with Telegram Bot!")

                st.markdown(f"""
                <style>
                @font-face {{
                    font-family: 'LiveUserFont_{int(time.time())}';
                    src: url(data:font/ttf;base64,{b64_font}) format('truetype');
                }}
                .font-sandbox {{
                    font-family: 'LiveUserFont_{int(time.time())}', sans-serif;
                    font-size: 32px;
                    line-height: 1.6;
                    padding: 24px;
                    background: #1E293B;
                    border: 2px solid #38BDF8;
                    border-radius: 12px;
                    color: #F8FAFC;
                    min-height: 120px;
                    white-space: pre-wrap;
                }}
                </style>
                <div class="font-sandbox">{test_text}</div>
                """, unsafe_allow_html=True)

# ----------------- TAB 2: WRITING GUIDE -----------------
with tab_guide:
    st.markdown("### 📖 How to Write Your Characters (Step-by-Step)")
    st.write("Follow these easy instructions to get the highest quality font without needing any printer or pre-printed form!")

    guide_path = config.STATIC_DIR / "writing_guide.png"
    if not guide_path.exists():
        generate_guide_image(str(guide_path))

    g_col1, g_col2 = st.columns([1, 1])
    with g_col1:
        st.markdown("#### 📐 Visual Instruction Sheet")
        st.image(str(guide_path), use_container_width=True)

    with g_col2:
        st.markdown("#### 📸 Official Sample Sheet (from User)")
        sample_path = config.STATIC_DIR / "official_sample_sheet.jpg"
        if not sample_path.exists():
            sample_path = config.ASSETS_DIR / "Picsart_26-08-15_06-22-04-501.jpg"
        if sample_path.exists():
            st.image(str(sample_path), caption="Actual Handwritten Reference Sheet (12 Rows)", use_container_width=True)

        st.markdown("""
        #### 💡 Pro Tips for Best Results:
        1. **Paper:** Any standard plain white blank paper.
        2. **Pen:** Use dark black or blue gel/ballpoint pen with solid strokes.
        3. **Rows:** Write in 12 structured lines (Uppercase -> Lowercase -> Numbers -> Symbols).
        4. **Lighting:** Avoid heavy shadows or angle distortion. Take photo from directly above.
        """)

# ----------------- TAB 3: ANALYTICS & LOGS -----------------
with tab_stats:
    st.markdown("### 📊 Database & Font Generations Log")
    recent_logs = database.get_recent_generations(limit=25)
    
    if recent_logs:
        st.dataframe(
            recent_logs,
            column_names=["ID", "Chat ID", "Username", "Font Name", "Glyphs", "Time (sec)", "Status", "Timestamp"],
            use_container_width=True
        )
    else:
        st.info("No font generation logs found in database yet.")

# ----------------- TAB 4: INSTALLATION GUIDE -----------------
with tab_install:
    st.markdown("### 💡 How to Install and Use .ttf Fonts")
    
    col_w, col_m, col_p = st.columns(3)
    
    with col_w:
        st.markdown("#### 💻 Windows PC")
        st.markdown("""
        1. Download the `.ttf` file.
        2. Right-click the file and choose **Install** (or *Install for all users*).
        3. Open Microsoft Word, PowerPoint, or Photoshop.
        4. Select your custom font from the dropdown list!
        """)

    with col_m:
        st.markdown("#### 🍎 Mac OS")
        st.markdown("""
        1. Double-click the downloaded `.ttf` file.
        2. In the Font Book preview window, click **Install Font**.
        3. It is now instantly available across all Mac applications.
        """)

    with col_p:
        st.markdown("#### 📱 Android & Mobile")
        st.markdown("""
        1. **Canva / CapCut / Pixellab:** In the Text Editor, choose *Fonts* -> *Upload Font* and pick your `.ttf` file.
        2. **System-wide Font:** Use apps like *zFont 3* to apply across supported Android devices.
        """)
