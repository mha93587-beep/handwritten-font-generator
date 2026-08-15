import os
import ssl
import logging
from urllib.parse import urlparse, parse_qs
from datetime import datetime
import config

logger = logging.getLogger(__name__)

def parse_database_url(url: str):
    """Parse postgresql:// connection URL into connection parameters dictionary."""
    parsed = urlparse(url)
    user = parsed.username
    password = parsed.password
    host = parsed.hostname
    port = parsed.port or 5432
    database = parsed.path.lstrip("/")
    
    query = parse_qs(parsed.query)
    ssl_context = None
    if "sslmode" in query and query["sslmode"][0] in ("require", "verify-ca", "verify-full"):
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
    return {
        "user": user,
        "password": password,
        "host": host,
        "port": port,
        "database": database,
        "ssl_context": ssl_context
    }

def get_connection():
    """Create and return a database connection (pg8000 or sqlite3 fallback)."""
    db_url = config.DATABASE_URL
    if db_url and db_url.startswith("postgres"):
        try:
            import pg8000.dbapi
            params = parse_database_url(db_url)
            conn = pg8000.dbapi.connect(
                user=params["user"],
                password=params["password"],
                host=params["host"],
                port=params["port"],
                database=params["database"],
                ssl_context=params["ssl_context"]
            )
            return conn, "postgres"
        except Exception as e:
            logger.warning(f"PostgreSQL connection failed ({e}), falling back to SQLite.")
            
    # SQLite fallback
    import sqlite3
    db_file = config.BASE_DIR / "bot_database.sqlite3"
    conn = sqlite3.connect(str(db_file), check_same_thread=False)
    return conn, "sqlite"

def init_db():
    """Initialize database tables if they do not exist."""
    try:
        conn, db_type = get_connection()
        cursor = conn.cursor()
        
        if db_type == "postgres":
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    chat_id BIGINT PRIMARY KEY,
                    username VARCHAR(255),
                    first_name VARCHAR(255),
                    last_name VARCHAR(255),
                    total_fonts INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS font_generations (
                    id SERIAL PRIMARY KEY,
                    chat_id BIGINT,
                    font_name VARCHAR(255),
                    glyphs_count INTEGER DEFAULT 0,
                    processing_time_sec FLOAT DEFAULT 0.0,
                    status VARCHAR(50) DEFAULT 'success',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS broadcasts (
                    id SERIAL PRIMARY KEY,
                    message TEXT,
                    sent_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
        else:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    chat_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    total_fonts INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_seen DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS font_generations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER,
                    font_name TEXT,
                    glyphs_count INTEGER DEFAULT 0,
                    processing_time_sec REAL DEFAULT 0.0,
                    status TEXT DEFAULT 'success',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS broadcasts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message TEXT,
                    sent_count INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
        conn.commit()
        cursor.close()
        conn.close()
        logger.info(f"Database initialized successfully using {db_type}.")
        return True
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        return False

def upsert_user(chat_id: int, username: str = None, first_name: str = None, last_name: str = None):
    """Add a new user or update their last_seen timestamp."""
    try:
        conn, db_type = get_connection()
        cursor = conn.cursor()
        now = datetime.utcnow()
        
        if db_type == "postgres":
            cursor.execute("""
                INSERT INTO users (chat_id, username, first_name, last_name, total_fonts, created_at, last_seen)
                VALUES (%s, %s, %s, %s, 0, %s, %s)
                ON CONFLICT (chat_id) DO UPDATE SET
                    username = EXCLUDED.username,
                    first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name,
                    last_seen = EXCLUDED.last_seen;
            """, (chat_id, username, first_name, last_name, now, now))
        else:
            cursor.execute("""
                INSERT INTO users (chat_id, username, first_name, last_name, total_fonts, created_at, last_seen)
                VALUES (?, ?, ?, ?, 0, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET
                    username = excluded.username,
                    first_name = excluded.first_name,
                    last_name = excluded.last_name,
                    last_seen = excluded.last_seen;
            """, (chat_id, username, first_name, last_name, now, now))
            
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        logger.error(f"Error upserting user {chat_id}: {e}")

def increment_user_font_count(chat_id: int):
    """Increment the total fonts generated by the user."""
    try:
        conn, db_type = get_connection()
        cursor = conn.cursor()
        if db_type == "postgres":
            cursor.execute("UPDATE users SET total_fonts = total_fonts + 1 WHERE chat_id = %s", (chat_id,))
        else:
            cursor.execute("UPDATE users SET total_fonts = total_fonts + 1 WHERE chat_id = ?", (chat_id,))
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        logger.error(f"Error incrementing font count for {chat_id}: {e}")

def log_font_generation(chat_id: int, font_name: str, glyphs_count: int, processing_time: float, status: str = "success"):
    """Record a font generation transaction."""
    try:
        conn, db_type = get_connection()
        cursor = conn.cursor()
        now = datetime.utcnow()
        if db_type == "postgres":
            cursor.execute("""
                INSERT INTO font_generations (chat_id, font_name, glyphs_count, processing_time_sec, status, created_at)
                VALUES (%s, %s, %s, %s, %s, %s);
            """, (chat_id, font_name, glyphs_count, processing_time, status, now))
        else:
            cursor.execute("""
                INSERT INTO font_generations (chat_id, font_name, glyphs_count, processing_time_sec, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?);
            """, (chat_id, font_name, glyphs_count, processing_time, status, now))
        conn.commit()
        cursor.close()
        conn.close()
        increment_user_font_count(chat_id)
    except Exception as e:
        logger.error(f"Error logging font generation: {e}")

def get_user_stats(chat_id: int):
    """Retrieve stats for a specific user."""
    try:
        conn, db_type = get_connection()
        cursor = conn.cursor()
        if db_type == "postgres":
            cursor.execute("SELECT total_fonts, created_at FROM users WHERE chat_id = %s", (chat_id,))
        else:
            cursor.execute("SELECT total_fonts, created_at FROM users WHERE chat_id = ?", (chat_id,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        if row:
            return {"total_fonts": row[0], "created_at": row[1]}
        return {"total_fonts": 0, "created_at": "N/A"}
    except Exception as e:
        logger.error(f"Error getting user stats: {e}")
        return {"total_fonts": 0, "created_at": "N/A"}

def get_global_stats():
    """Retrieve global statistics for admin and dashboard."""
    try:
        conn, db_type = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0] or 0
        cursor.execute("SELECT COUNT(*), COALESCE(SUM(glyphs_count), 0) FROM font_generations WHERE status = 'success'")
        font_row = cursor.fetchone()
        total_fonts = font_row[0] or 0
        total_glyphs = font_row[1] or 0
        cursor.close()
        conn.close()
        return {
            "total_users": total_users,
            "total_fonts": total_fonts,
            "total_glyphs": total_glyphs,
            "db_type": db_type
        }
    except Exception as e:
        logger.error(f"Error getting global stats: {e}")
        return {"total_users": 0, "total_fonts": 0, "total_glyphs": 0, "db_type": "offline"}

def get_all_user_ids():
    """Retrieve all user chat_ids for broadcast."""
    try:
        conn, db_type = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT chat_id FROM users")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return [r[0] for r in rows]
    except Exception as e:
        logger.error(f"Error getting user IDs: {e}")
        return []

def get_recent_generations(limit: int = 15):
    """Retrieve list of recent font generations for dashboard display."""
    try:
        conn, db_type = get_connection()
        cursor = conn.cursor()
        if db_type == "postgres":
            cursor.execute("""
                SELECT g.id, g.chat_id, u.username, g.font_name, g.glyphs_count, g.processing_time_sec, g.status, g.created_at
                FROM font_generations g
                LEFT JOIN users u ON g.chat_id = u.chat_id
                ORDER BY g.id DESC
                LIMIT %s;
            """, (limit,))
        else:
            cursor.execute("""
                SELECT g.id, g.chat_id, u.username, g.font_name, g.glyphs_count, g.processing_time_sec, g.status, g.created_at
                FROM font_generations g
                LEFT JOIN users u ON g.chat_id = u.chat_id
                ORDER BY g.id DESC
                LIMIT ?;
            """, (limit,))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows
    except Exception as e:
        logger.error(f"Error getting recent generations: {e}")
        return []
