import os
import sys
import time
import threading
import logging
import config
import database

from aiohttp import web
from bot import run_bot_polling
from web_server import start_server

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("MainRunner")

def main():
    print("=" * 60)
    print("🚀 STARTING HANDWRITTEN FONT GENERATOR SYSTEM")
    print("=" * 60)

    # 1. Initialize Database
    database.init_db()
    stats = database.get_global_stats()
    print(f"✅ Neon PostgreSQL Database Connected! (Engine: {stats['db_type']})")

    # 2. Start Telegram Bot in Background Thread
    if config.TELEGRAM_BOT_TOKEN:
        print("🤖 Starting Telegram Bot background polling...")
        bot_thread = threading.Thread(target=run_bot_polling, daemon=True, name="TelegramBotWorker")
        bot_thread.start()
        print(f"✅ Telegram Bot @HandwrittenTextGeneratorbot is ACTIVE & LISTENING 24/7!")
    else:
        print("⚠️ Warning: TELEGRAM_BOT_TOKEN not configured in .env")

    # 3. Start Local Web Server
    port = int(os.getenv("PORT", 8501))
    print(f"🌐 Starting Local Web Dashboard on http://0.0.0.0:{port} (http://localhost:{port})")
    print("=" * 60)

    app = start_server()
    web.run_app(app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()
