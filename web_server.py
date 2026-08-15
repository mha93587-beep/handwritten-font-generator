import os
import time
import base64
import asyncio
import logging
from pathlib import Path
import config
import database

from aiohttp import web
from PIL import Image
from segmenter import segment_handwriting_sheet, segment_with_gemini_ai
from font_engine import compile_ttf_font
from preview_generator import generate_font_preview
from guide_generator import generate_guide_image

logger = logging.getLogger(__name__)

# Initialize DB and Guide Image
database.init_db()
guide_file = config.STATIC_DIR / "writing_guide.png"
if not guide_file.exists():
    generate_guide_image(str(guide_file))

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Handwritten Font Generator & Telegram Bot</title>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #0B0F19;
            --surface: #131B2E;
            --surface-card: #1E293B;
            --border: #334155;
            --primary: #38BDF8;
            --primary-hover: #0EA5E9;
            --accent: #818CF8;
            --success: #34D399;
            --text: #F8FAFC;
            --text-muted: #94A3B8;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Plus Jakarta Sans', sans-serif; }
        body { background: var(--bg); color: var(--text); padding-bottom: 60px; min-height: 100vh; }
        
        .navbar {
            display: flex; align-items: center; justify-content: space-between;
            padding: 18px 40px; background: var(--surface); border-bottom: 1px solid var(--border);
        }
        .brand { display: flex; align-items: center; gap: 12px; font-size: 1.25rem; font-weight: 800; color: var(--text); }
        .brand span { background: linear-gradient(135deg, var(--primary), var(--accent)); -webkit-background-clip: text; -webkit-fill-color: transparent; -webkit-text-fill-color: transparent; }
        .status-badge {
            display: flex; align-items: center; gap: 8px; padding: 6px 14px;
            background: #064E3B; color: var(--success); border-radius: 9999px; font-size: 0.85rem; font-weight: 600; border: 1px solid #059669;
        }
        .status-dot { width: 8px; height: 8px; background: var(--success); border-radius: 50%; animation: pulse 2s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.4; } }
        
        .container { max-width: 1200px; margin: 0 auto; padding: 30px 20px; }
        
        /* Stats Grid */
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 30px; }
        .stat-card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 20px; text-align: center; }
        .stat-val { font-size: 1.8rem; font-weight: 800; color: var(--text); }
        .stat-lbl { font-size: 0.8rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; margin-top: 4px; }
        
        /* Tabs */
        .tab-nav { display: flex; gap: 10px; border-bottom: 1px solid var(--border); margin-bottom: 24px; }
        .tab-btn {
            background: none; border: none; padding: 12px 20px; font-size: 0.95rem; font-weight: 600;
            color: var(--text-muted); cursor: pointer; border-bottom: 2px solid transparent; transition: all 0.2s;
        }
        .tab-btn.active { color: var(--primary); border-bottom-color: var(--primary); }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        
        /* Generator Layout */
        .gen-layout { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
        @media (max-width: 860px) { .gen-layout { grid-template-columns: 1fr; } }
        
        .card { background: var(--surface); border: 1px solid var(--border); border-radius: 16px; padding: 24px; }
        .card h2 { font-size: 1.25rem; font-weight: 700; margin-bottom: 16px; color: var(--text); }
        
        .form-group { margin-bottom: 18px; }
        .form-group label { display: block; font-size: 0.85rem; font-weight: 600; color: var(--text-muted); margin-bottom: 8px; }
        .form-control {
            width: 100%; padding: 12px 16px; background: var(--surface-card); border: 1px solid var(--border);
            border-radius: 8px; color: var(--text); font-size: 0.95rem; outline: none;
        }
        .form-control:focus { border-color: var(--primary); }
        
        .file-dropzone {
            border: 2px dashed var(--border); border-radius: 12px; padding: 30px; text-align: center;
            background: var(--surface-card); cursor: pointer; transition: all 0.2s;
        }
        .file-dropzone:hover { border-color: var(--primary); }
        
        .btn {
            display: inline-flex; align-items: center; justify-content: center; gap: 8px;
            padding: 12px 24px; border-radius: 8px; font-weight: 600; font-size: 0.95rem; cursor: pointer;
            border: none; transition: all 0.2s; text-decoration: none; width: 100%;
        }
        .btn-primary { background: var(--primary); color: #000; }
        .btn-primary:hover { background: var(--primary-hover); }
        .btn-secondary { background: var(--surface-card); color: var(--text); border: 1px solid var(--border); }
        
        .sandbox-box {
            margin-top: 24px; background: var(--surface-card); border: 2px solid var(--primary);
            border-radius: 12px; padding: 24px; font-size: 28px; line-height: 1.5; min-height: 120px;
            white-space: pre-wrap; color: #FFF; outline: none;
        }
        
        .guide-img { width: 100%; border-radius: 12px; border: 1px solid var(--border); margin-top: 12px; }
        
        .telegram-box {
            background: linear-gradient(135deg, #1E3A8A, #1E293B); border: 1px solid #3B82F6;
            border-radius: 16px; padding: 24px; margin-top: 24px; display: flex; align-items: center; justify-content: space-between;
        }
    </style>
</head>
<body>
    <div class="navbar">
        <div class="brand">✍️ <span>Handwritten Font Generator</span></div>
        <div class="status-badge"><div class="status-dot"></div> Telegram Bot: Live & Polling</div>
    </div>
    
    <div class="container">
        <!-- Stats KPI Cards -->
        <div class="stats-grid">
            <div class="stat-card"><div class="stat-val" id="stat-users">__TOTAL_USERS__</div><div class="stat-lbl">Total Users</div></div>
            <div class="stat-card"><div class="stat-val" id="stat-fonts">__TOTAL_FONTS__</div><div class="stat-lbl">Fonts Created</div></div>
            <div class="stat-card"><div class="stat-val">100%</div><div class="stat-lbl">Vector Precision</div></div>
            <div class="stat-card"><div class="stat-val">24/7</div><div class="stat-lbl">Cloud Bot Service</div></div>
        </div>
        
        <!-- Tab Navigation -->
        <div class="tab-nav">
            <button class="tab-btn active" onclick="switchTab('tab-gen')">✨ Web Font Generator</button>
            <button class="tab-btn" onclick="switchTab('tab-guide')">📖 Writing Guide</button>
            <button class="tab-btn" onclick="switchTab('tab-bot')">🤖 Telegram Bot</button>
            <button class="tab-btn" onclick="switchTab('tab-install')">💡 Install Guide</button>
        </div>
        
        <!-- TAB 1: GENERATOR -->
        <div id="tab-gen" class="tab-content active">
            <div class="gen-layout">
                <!-- Left form -->
                <div class="card">
                    <h2>📸 Upload Handwriting Sheet</h2>
                    <form id="gen-form">
                        <div class="form-group">
                            <label>Font Family Name</label>
                            <input type="text" id="font-name" class="form-control" value="MyHandwriting" required>
                        </div>
                        
                        <div class="form-group">
                            <label>Handwritten Sheet Photo (JPG / PNG)</label>
                            <div class="file-dropzone" onclick="document.getElementById('file-input').click()">
                                <p id="file-label">📁 Click here to select photo of your handwritten paper</p>
                                <input type="file" id="file-input" style="display:none;" accept="image/*">
                            </div>
                        </div>
                        
                        <div class="form-group">
                            <label><input type="checkbox" id="use-sample"> Or test with pre-loaded official 12-row sample sheet (Picsart_26-08-15_06-22-04-501.jpg)</label>
                        </div>
                        
                        <button type="submit" class="btn btn-primary" id="btn-submit">🚀 Vectorize & Generate TTF Font</button>
                    </form>
                    
                    <div id="progress-box" style="display:none; margin-top: 16px; padding: 12px; background: #064E3B; border-radius: 8px; color: #34D399; font-size: 0.9rem;">
                        ⏳ Processing handwriting... Scanning lines and compiling TrueType font...
                    </div>
                </div>
                
                <!-- Right Preview & Sandbox -->
                <div class="card">
                    <h2>🔤 Real-Time Interactive Sandbox</h2>
                    <p style="color: var(--text-muted); font-size: 0.9rem; margin-bottom: 12px;">Type anywhere below to test the custom handwritten font live:</p>
                    <div id="sandbox" class="sandbox-box" contenteditable="true">The quick brown fox jumps over the lazy dog! 0123456789 @#₹</div>
                    
                    <div id="result-actions" style="margin-top: 20px; display: none;">
                        <a id="download-btn" class="btn btn-primary" href="#" download>📥 Download TrueType (.ttf) File</a>
                        <img id="preview-img" style="width: 100%; border-radius: 8px; margin-top: 14px; border: 1px solid var(--border);" src="">
                    </div>
                </div>
            </div>
        </div>
        
        <!-- TAB 2: WRITING GUIDE -->
        <div id="tab-guide" class="tab-content">
            <div class="card">
                <h2>📖 How to Write on Plain White Paper</h2>
                <p style="color: var(--text-muted); margin-bottom: 16px;">No printer or special forms needed! Just write in 12 neat rows on any white paper (Uppercase ➔ Lowercase ➔ Numbers ➔ Symbols):</p>
                <img class="guide-img" src="/static/writing_guide.png" alt="Official Writing Guide">
            </div>
        </div>
        
        <!-- TAB 3: TELEGRAM BOT -->
        <div id="tab-bot" class="tab-content">
            <div class="telegram-box">
                <div>
                    <h2 style="color: #FFF; margin-bottom: 6px;">🤖 Telegram Bot is LIVE!</h2>
                    <p style="color: #93C5FD; font-size: 0.95rem;">Send your handwritten photo to <b>@HandwrittenTextGeneratorbot</b> directly on Telegram!</p>
                </div>
                <div>
                    <a href="https://t.me/HandwrittenTextGeneratorbot" target="_blank" class="btn btn-primary" style="width: auto; padding: 12px 28px;">Open Bot in Telegram ✈️</a>
                </div>
            </div>
        </div>
        
        <!-- TAB 4: INSTALL GUIDE -->
        <div id="tab-install" class="tab-content">
            <div class="stats-grid">
                <div class="card">
                    <h2>💻 Windows PC</h2>
                    <p style="color: var(--text-muted); font-size: 0.9rem; line-height: 1.6;">1. Download the <b>.ttf</b> file.<br>2. Right-click and choose <b>Install</b>.<br>3. Open MS Word, Photoshop, or Premiere and select your font!</p>
                </div>
                <div class="card">
                    <h2>🍎 Mac OS</h2>
                    <p style="color: var(--text-muted); font-size: 0.9rem; line-height: 1.6;">1. Double-click the downloaded <b>.ttf</b> file.<br>2. In the Font Book window, click <b>Install Font</b>.<br>3. Immediately available across all Mac apps.</p>
                </div>
                <div class="card">
                    <h2>📱 Android & Canva</h2>
                    <p style="color: var(--text-muted); font-size: 0.9rem; line-height: 1.6;">1. In <b>Canva / Pixellab / CapCut</b>, open Text tool.<br>2. Click <b>Upload Font</b> and pick the .ttf file.<br>3. Use zFont 3 for system-wide font styling.</p>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        function switchTab(tabId) {
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
            document.getElementById(tabId).classList.add('active');
            event.target.classList.add('active');
        }
        
        const fileInput = document.getElementById('file-input');
        fileInput.addEventListener('change', () => {
            if (fileInput.files.length > 0) {
                document.getElementById('file-label').innerText = 'Selected: ' + fileInput.files[0].name;
            }
        });
        
        document.getElementById('gen-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const fontName = document.getElementById('font-name').value.trim() || 'MyHandwriting';
            const useSample = document.getElementById('use-sample').checked;
            const file = fileInput.files[0];
            
            if (!file && !useSample) {
                alert('Please select an image file or check the sample box!');
                return;
            }
            
            const pBox = document.getElementById('progress-box');
            pBox.style.display = 'block';
            
            const formData = new FormData();
            formData.append('font_name', fontName);
            formData.append('use_sample', useSample ? 'true' : 'false');
            if (file) {
                formData.append('image', file);
            }
            
            try {
                const res = await fetch('/api/generate', { method: 'POST', body: formData });
                const data = await res.json();
                pBox.style.display = 'none';
                
                if (data.success) {
                    // Update Font-Face in browser
                    const newStyle = document.createElement('style');
                    newStyle.appendChild(document.createTextNode(`
                        @font-face {
                            font-family: '${fontName}_${Date.now()}';
                            src: url(data:font/ttf;base64,${data.font_base64}) format('truetype');
                        }
                    `));
                    document.head.appendChild(newStyle);
                    
                    const sandbox = document.getElementById('sandbox');
                    sandbox.style.fontFamily = `'${fontName}_${Date.now()}', sans-serif`;
                    
                    const dlBtn = document.getElementById('download-btn');
                    dlBtn.href = data.download_url;
                    dlBtn.download = `${fontName}.ttf`;
                    
                    const prevImg = document.getElementById('preview-img');
                    prevImg.src = data.preview_url + '?t=' + Date.now();
                    
                    document.getElementById('result-actions').style.display = 'block';
                    alert(`✅ Font "${fontName}" generated successfully with ${data.glyphs_count} glyphs!`);
                } else {
                    alert('Error generating font: ' + data.error);
                }
            } catch (err) {
                pBox.style.display = 'none';
                alert('Failed to connect to server: ' + err);
            }
        });
    </script>
</body>
</html>
"""

async def handle_index(request):
    """Serve Dashboard HTML."""
    stats = database.get_global_stats()
    html = HTML_TEMPLATE.replace("__TOTAL_USERS__", str(stats.get("total_users", 1)))
    html = html.replace("__TOTAL_FONTS__", str(stats.get("total_fonts", 0)))
    return web.Response(text=html, content_type="text/html")

async def handle_api_generate(request):
    """API endpoint to generate TTF font from uploaded image."""
    try:
        reader = await request.multipart()
        font_name = "MyHandwriting"
        use_sample = False
        image_bytes = None

        while True:
            field = await reader.next()
            if field is None:
                break
            if field.name == "font_name":
                font_name = (await field.read(decode=True)).decode("utf-8").strip() or "MyHandwriting"
            elif field.name == "use_sample":
                val = (await field.read(decode=True)).decode("utf-8").strip()
                use_sample = (val.lower() == "true")
            elif field.name == "image":
                image_bytes = await field.read(decode=False)

        font_name = "".join(c for c in font_name if c.isalnum() or c in (" ", "_", "-")).strip()

        temp_img_path = config.TEMP_DIR / f"api_upload_{int(time.time())}.jpg"
        if use_sample or not image_bytes:
            sample_src = config.STATIC_DIR / "official_sample_sheet.jpg"
            if not sample_src.exists():
                sample_src = config.ASSETS_DIR / "Picsart_26-08-15_06-22-04-501.jpg"
            if sample_src.exists():
                with open(sample_src, "rb") as sf:
                    with open(temp_img_path, "wb") as tf:
                        tf.write(sf.read())
            else:
                return web.json_response({"success": False, "error": "Sample image not found on server"})
        else:
            with open(temp_img_path, "wb") as f:
                f.write(image_bytes)

        # Run segmentation
        char_map = segment_handwriting_sheet(str(temp_img_path))
        if not char_map:
            return web.json_response({"success": False, "error": "No characters detected on sheet."})

        # Compile TTF
        out_ttf = config.OUTPUT_DIR / f"{font_name}.ttf"
        compile_ttf_font(char_map, str(out_ttf), font_name=font_name, family_name=font_name)

        # Generate Preview Card
        out_prev = config.OUTPUT_DIR / f"{font_name}_preview.png"
        generate_font_preview(str(out_ttf), str(out_prev), font_display_name=font_name)

        with open(out_ttf, "rb") as f:
            ttf_b64 = base64.b64encode(f.read()).decode("utf-8")

        database.log_font_generation(0, font_name, len(char_map), 1.5, "success")

        if temp_img_path.exists():
            temp_img_path.unlink()

        return web.json_response({
            "success": True,
            "font_name": font_name,
            "glyphs_count": len(char_map),
            "font_base64": ttf_b64,
            "download_url": f"/download/{font_name}.ttf",
            "preview_url": f"/output/{font_name}_preview.png"
        })

    except Exception as e:
        logger.error(f"API generate error: {e}", exc_info=True)
        return web.json_response({"success": False, "error": str(e)})

async def handle_download(request):
    """Serve font file download."""
    filename = request.match_info.get("filename")
    file_path = config.OUTPUT_DIR / filename
    if file_path.exists():
        return web.FileResponse(file_path)
    return web.Response(status=404, text="File not found")

def start_server(host="0.0.0.0", port=8501):
    """Create and start the aiohttp web application."""
    app = web.Application()
    app.router.add_get("/", handle_index)
    app.router.add_post("/api/generate", handle_api_generate)
    app.router.add_get("/download/{filename}", handle_download)
    app.router.add_static("/static/", path=str(config.STATIC_DIR), name="static")
    app.router.add_static("/output/", path=str(config.OUTPUT_DIR), name="output")
    return app

if __name__ == "__main__":
    app = start_server()
    web.run_app(app, host="0.0.0.0", port=8501)
