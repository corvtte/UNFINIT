import os
import sqlite3
import asyncio
from typing import Any, List, Tuple, Optional
from pathlib import Path
from core.logger import get_logger

logger = get_logger("database")
BASE_DIR = Path(__file__).resolve().parent.parent

def fix_mojibake(text: str, default: str = "فروشگاه دوره‌های آموزشی UNFINIT") -> str:
    """
    Repairs Mojibake Persian/Arabic UTF-8 strings mistakenly decoded as Latin-1 / Windows-1252.
    """
    if not text or not isinstance(text, str) or not str(text).strip():
        return default
    if any(ch in text for ch in ("Ù", "Ø", "â", "Ã")):
        try:
            repaired = text.encode("latin1").decode("utf-8")
            if repaired and not any(ch in repaired for ch in ("Ù", "Ø", "â", "Ã")):
                return repaired
        except Exception:
            pass
        return default
    return text

def get_db_path() -> Path:
    env_p = os.getenv("SQLITE_DB_PATH", "").strip()
    if env_p:
        p = Path(env_p)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p
    try:
        from core.config import config
        if hasattr(config, "DB_PATH") and config.DB_PATH:
            config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            return config.DB_PATH
    except Exception:
        pass
    return BASE_DIR / "store_database.db"

def get_db_connection() -> sqlite3.Connection:
    db_file = get_db_path()
    conn = sqlite3.connect(str(db_file), timeout=20, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

async def execute_query(sql: str, params: Tuple = ()) -> Any:
    def _run():
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute(sql, params)
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()
    return await asyncio.to_thread(_run)

async def fetch_one(sql: str, params: Tuple = ()) -> Optional[dict]:
    def _run():
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute(sql, params)
            row = cur.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()
    return await asyncio.to_thread(_run)

async def fetch_all(sql: str, params: Tuple = ()) -> List[dict]:
    def _run():
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute(sql, params)
            rows = cur.fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
    return await asyncio.to_thread(_run)

async def get_system_setting(key: str, default: str = "") -> str:
    row = await fetch_one("SELECT value FROM system_settings WHERE key = ?", (key,))
    if row and "value" in row:
        return str(row["value"])
    return default

def sync_settings_to_json_and_env() -> None:
    import json
    import os
    from core.config import config
    if os.getenv("TESTING") == "true" or os.getenv("PYTEST_CURRENT_TEST"):
        return
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT key, value FROM system_settings")
        settings_dict = {row[0]: row[1] for row in cur.fetchall()}
    finally:
        conn.close()

    crucial_keys = {
        "TELEGRAM_BOT_TOKEN": config.TELEGRAM_BOT_TOKEN,
        "TELEGRAM_OWNER_ID": str(config.TELEGRAM_OWNER_ID),
        "BALE_BOT_TOKEN": config.BALE_BOT_TOKEN,
        "BALE_OWNER_ID": str(config.BALE_OWNER_ID),
        "BALE_PAYMENT_TOKEN": config.BALE_PAYMENT_TOKEN,
        "RUBIKA_BOT_TOKEN": config.RUBIKA_BOT_TOKEN,
        "RUBIKA_OWNER_ID": str(config.RUBIKA_OWNER_ID),
        "FORCE_JOIN_CHANNEL_TELEGRAM": config.FORCE_JOIN_CHANNEL_TELEGRAM,
        "FORCE_JOIN_CHANNEL_BALE": config.FORCE_JOIN_CHANNEL_BALE,
        "CARD_NUMBER": config.CARD_NUMBER,
        "CARD_HOLDER": config.CARD_HOLDER,
        "ADMIN_PANEL_PASSWORD": config.ADMIN_PANEL_PASSWORD,
        "NARA_API_KEY": config.NARA_API_KEY,
        "NARA_MODEL": config.NARA_MODEL,
        "NARA_BASE_URL": config.NARA_BASE_URL,
        "GEMINI_API_KEY": config.GEMINI_API_KEY,
        "GEMINI_MODEL": config.GEMINI_MODEL,
        "DEFAULT_ARTIST": config.DEFAULT_ARTIST
    }
    SENSITIVE_KEYS = {
        "TELEGRAM_BOT_TOKEN", "BALE_BOT_TOKEN", "RUBIKA_BOT_TOKEN",
        "BALE_PAYMENT_TOKEN", "bale_payment_token",
        "NARA_API_KEY", "nara_api_key",
        "GEMINI_API_KEY", "gemini_api_key",
        "ADMIN_PANEL_PASSWORD", "admin_password"
    }

    disk_safe_dict = {}
    for k, v in settings_dict.items():
        if k in SENSITIVE_KEYS:
            disk_safe_dict[k] = ""  # Security: Never leak secrets to disk JSON
        else:
            disk_safe_dict[k] = v

    for k, v in crucial_keys.items():
        if k not in disk_safe_dict:
            if k in SENSITIVE_KEYS:
                disk_safe_dict[k] = ""
            else:
                disk_safe_dict[k] = v

    try:
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(config.SETTINGS_JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(disk_safe_dict, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"[settings_sync] Error saving {config.SETTINGS_JSON_FILE}: {e}")

    try:
        env_path = config.BASE_DIR / ".env"
        if env_path.exists():
            env_lines = []
            existing_keys = set()
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    stripped = line.strip()
                    if "=" in stripped and not stripped.startswith("#"):
                        ek = stripped.split("=", 1)[0].strip()
                        existing_keys.add(ek)
                        if ek in settings_dict:
                            env_lines.append(f"{ek}={settings_dict[ek]}\n")
                            continue
                    env_lines.append(line)
            for k, v in settings_dict.items():
                if k not in existing_keys:
                    env_lines.append(f"{k}={v}\n")
            with open(env_path, "w", encoding="utf-8") as f:
                f.writelines(env_lines)
    except Exception as e:
        logger.debug(f"[settings_sync] Optional .env sync notice: {e}")

async def set_system_setting(key: str, value: str) -> None:
    await execute_query(
        "INSERT INTO system_settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, str(value))
    )
    await asyncio.to_thread(sync_settings_to_json_and_env)


def db_save_media_session(drop_id: str, data: dict) -> None:
    import json
    from datetime import datetime
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        clean_v = {ck: cv for ck, cv in data.items() if ck != "raw_message"}
        data_json = json.dumps(clean_v, ensure_ascii=False)
        cur.execute(
            """INSERT INTO media_sessions (drop_id, data_json, created_at, updated_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(drop_id) DO UPDATE SET data_json = excluded.data_json, updated_at = excluded.updated_at""",
            (drop_id, data_json, now_str, now_str)
        )
        conn.commit()
    finally:
        conn.close()


def db_get_media_session(drop_id: str) -> Optional[dict]:
    import json
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT data_json FROM media_sessions WHERE drop_id = ?", (drop_id,))
        row = cur.fetchone()
        if row and row["data_json"]:
            return json.loads(row["data_json"])
        return None
    finally:
        conn.close()


def db_get_all_media_sessions() -> dict:
    import json
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT drop_id, data_json FROM media_sessions ORDER BY updated_at DESC")
        rows = cur.fetchall()
        res = {}
        for r in rows:
            try:
                res[r["drop_id"]] = json.loads(r["data_json"])
            except Exception:
                pass
        return res
    finally:
        conn.close()


def db_delete_media_session(drop_id: str) -> bool:
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM media_sessions WHERE drop_id = ?", (drop_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def db_save_user_action(user_key: str, action: str, drop_id: str, extra: dict = None) -> None:
    import json
    from datetime import datetime
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        extra_json = json.dumps(extra or {}, ensure_ascii=False)
        cur.execute(
            """INSERT INTO user_actions (user_key, action, drop_id, extra_json, updated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(user_key) DO UPDATE SET action = excluded.action, drop_id = excluded.drop_id,
               extra_json = excluded.extra_json, updated_at = excluded.updated_at""",
            (user_key, action, drop_id, extra_json, now_str)
        )
        conn.commit()
    finally:
        conn.close()


def db_get_user_action(user_key: str) -> Optional[dict]:
    import json
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT action, drop_id, extra_json FROM user_actions WHERE user_key = ?", (user_key,))
        row = cur.fetchone()
        if row:
            extra = json.loads(row["extra_json"]) if row["extra_json"] else {}
            return {"action": row["action"], "drop_id": row["drop_id"], "extra": extra}
        return None
    finally:
        conn.close()


def db_clear_user_action(user_key: str) -> bool:
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM user_actions WHERE user_key = ?", (user_key,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def db_get_all_user_actions() -> dict:
    import json
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT user_key, action, drop_id, extra_json FROM user_actions")
        rows = cur.fetchall()
        res = {}
        for r in rows:
            try:
                extra = json.loads(r["extra_json"]) if r["extra_json"] else {}
                res[r["user_key"]] = {"action": r["action"], "drop_id": r["drop_id"], "extra": extra}
            except Exception:
                pass
        return res
    finally:
        conn.close()


async def init_db():
    def _init():
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
        CREATE TABLE IF NOT EXISTS system_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS media_sessions (
            drop_id TEXT PRIMARY KEY,
            data_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """)

        # Purge dead Windows sessions (C:\, c:\, D:\, d:\, \Users\, /Users/Sajjad)
        cur.execute("""
        DELETE FROM media_sessions
        WHERE data_json LIKE '%C:\\%'
           OR data_json LIKE '%c:\\%'
           OR data_json LIKE '%D:\\%'
           OR data_json LIKE '%d:\\%'
           OR data_json LIKE '%\\Users\\%'
           OR data_json LIKE '%/Users/Sajjad%'
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS user_actions (
            user_key TEXT PRIMARY KEY,
            action TEXT NOT NULL,
            drop_id TEXT NOT NULL,
            extra_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            price INTEGER NOT NULL DEFAULT 0,
            description TEXT NOT NULL DEFAULT '',
            photo_file_id TEXT,
            photo_url TEXT DEFAULT '',
            digital_file_id TEXT,
            download_link TEXT DEFAULT '',
            digital_file_type TEXT NOT NULL DEFAULT 'audio',
            active INTEGER NOT NULL DEFAULT 1,
            allow_card INTEGER NOT NULL DEFAULT 1,
            allow_bale INTEGER NOT NULL DEFAULT 1,
            payment_type TEXT NOT NULL DEFAULT 'paid',
            created_at TEXT NOT NULL
        )
        """)

        cur.execute("PRAGMA table_info(products)")
        existing_cols = {row[1] for row in cur.fetchall()}
        if "download_link" not in existing_cols:
            cur.execute("ALTER TABLE products ADD COLUMN download_link TEXT DEFAULT ''")
        if "photo_url" not in existing_cols:
            cur.execute("ALTER TABLE products ADD COLUMN photo_url TEXT DEFAULT ''")
        if "allow_card" not in existing_cols:
            cur.execute("ALTER TABLE products ADD COLUMN allow_card INTEGER DEFAULT 1")
        if "allow_bale" not in existing_cols:
            cur.execute("ALTER TABLE products ADD COLUMN allow_bale INTEGER DEFAULT 1")
        if "bale_photo_file_id" not in existing_cols:
            cur.execute("ALTER TABLE products ADD COLUMN bale_photo_file_id TEXT DEFAULT ''")

        # Auto-clean legacy filler text and redundant titles from download_link in products
        try:
            cur.execute("SELECT product_id, name, download_link FROM products WHERE download_link IS NOT NULL AND download_link != ''")
            rows_to_clean = cur.fetchall()
            if rows_to_clean:
                from services.store_service import clean_course_access_input
                for r_pid, r_name, r_link in rows_to_clean:
                    clean_l = clean_course_access_input(r_link, r_name)
                    if clean_l and clean_l != r_link:
                        cur.execute("UPDATE products SET download_link = ? WHERE product_id = ?", (clean_l, r_pid))
        except Exception:
            pass

        cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT UNIQUE NOT NULL,
            user_id TEXT NOT NULL,
            username TEXT NOT NULL DEFAULT '',
            customer_name TEXT NOT NULL DEFAULT '',
            phone TEXT NOT NULL DEFAULT '',
            product_id TEXT NOT NULL,
            product_name TEXT NOT NULL,
            total INTEGER NOT NULL DEFAULT 0,
            wallet_used INTEGER NOT NULL DEFAULT 0,
            receipt_file_id TEXT,
            receipt_text TEXT DEFAULT '',
            payment_method TEXT DEFAULT 'telegram',
            status TEXT NOT NULL DEFAULT 'pending',
            platform TEXT NOT NULL DEFAULT 'telegram',
            created_at TEXT NOT NULL
        )
        """)

        cur.execute("PRAGMA table_info(orders)")
        existing_order_cols = {row[1] for row in cur.fetchall()}
        if "payment_method" not in existing_order_cols:
            cur.execute("ALTER TABLE orders ADD COLUMN payment_method TEXT DEFAULT 'telegram'")
        if "receipt_text" not in existing_order_cols:
            cur.execute("ALTER TABLE orders ADD COLUMN receipt_text TEXT DEFAULT ''")
        if "invoice_id" not in existing_order_cols:
            cur.execute("ALTER TABLE orders ADD COLUMN invoice_id TEXT DEFAULT ''")

        cur.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT UNIQUE NOT NULL,
            customer_name TEXT NOT NULL DEFAULT '',
            phone TEXT NOT NULL DEFAULT '',
            terms_accepted INTEGER NOT NULL DEFAULT 0,
            wallet_balance INTEGER NOT NULL DEFAULT 0,
            platform TEXT NOT NULL DEFAULT 'telegram',
            created_at TEXT NOT NULL
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS support_tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id TEXT UNIQUE NOT NULL,
            user_id TEXT NOT NULL,
            username TEXT NOT NULL DEFAULT '',
            message_text TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',
            platform TEXT NOT NULL DEFAULT 'telegram',
            created_at TEXT NOT NULL
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS keyword_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT NOT NULL DEFAULT 'INSTAGRAM',
            keyword TEXT NOT NULL,
            matching_mode TEXT NOT NULL DEFAULT 'CONTAINS',
            response_type TEXT NOT NULL DEFAULT 'TEXT',
            response_text TEXT NOT NULL DEFAULT '',
            media_id TEXT,
            enabled INTEGER NOT NULL DEFAULT 1,
            priority INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """)

        cur.execute("SELECT COUNT(*) FROM keyword_rules")
        if cur.fetchone()[0] == 0:
            kw_seed = [
                ("INSTAGRAM", "قوانین", "CONTAINS", "TEXT", "سلام دوست عزیز! دوره جامع کشف قوانین زندگی به شما کمک میکند قوانین فرکانس و مدارهای کیهانی را درک کرده و اتفاقات دلخواهتان را رقم بزنید. جهت ثبت نام یا دریافت تخفیف به کانال تلگرام ما بپیوندید.", None, 1, 10, "2026-08-24", "2026-08-24"),
                ("INSTAGRAM", "ثروت", "CONTAINS", "TEXT", "سلام! دوره روانشناسی ثروت ۱ باورهای مخرب مالی شما را شناسایی و مدار مالی شما را متحول میکند.", None, 1, 10, "2026-08-24", "2026-08-24"),
                ("INSTAGRAM", "هدیه", "CONTAINS", "TEXT", "سلام و درود! فایل صوتی هدیه ویژه شما با موضوع قانون جذب و باورها آماده است.", None, 1, 10, "2026-08-24", "2026-08-24"),
            ]
            cur.executemany("INSERT INTO keyword_rules (platform, keyword, matching_mode, response_type, response_text, media_id, enabled, priority, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", kw_seed)
            conn.commit()

        # 1. First priority: Load settings from data/settings.json
        from core.config import config
        import json
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)

        if config.SETTINGS_JSON_FILE.exists():
            try:
                # Read existing database settings first to protect non-empty live tokens
                cur.execute("SELECT key, value FROM system_settings")
                db_settings = {row[0]: str(row[1]).strip() for row in cur.fetchall()}

                with open(config.SETTINGS_JSON_FILE, "r", encoding="utf-8") as f:
                    saved_settings = json.load(f)

                loaded_count = 0
                for k, v in saved_settings.items():
                    if v is None:
                        continue
                    v_str = str(v).strip()
                    if k in ("STORE_NAME", "WELCOME_TEXT") or any(ch in v_str for ch in ("Ù", "Ø", "â", "Ã")):
                        v_str = fix_mojibake(v_str, default="فروشگاه دوره‌های آموزشی UNFINIT" if k == "STORE_NAME" else "به فروشگاه دوره‌های آموزشی و دانلودی UNFINIT خوش آمدید.")
                    existing_val = db_settings.get(k, "")

                    # PROTECTION: If existing database setting has a valid value and incoming value is empty,
                    # DO NOT overwrite the valid database value with empty string!
                    if not v_str and existing_val:
                        v_str = existing_val
                    else:
                        cur.execute(
                            "INSERT INTO system_settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                            (k, v_str)
                        )
                        loaded_count += 1

                    if hasattr(config, k) and v_str:
                        try:
                            if k in ("NARA_MODEL", "nara_model") and v_str == "mistral-large":
                                v_str = "mimo-v2.5-free"
                            # CRITICAL: Environment variable absolute priority!
                            # If key exists in os.environ with a non-empty value, do not override config attribute
                            if os.environ.get(k):
                                continue
                            if isinstance(getattr(config, k), int):
                                setattr(config, k, int(v_str or 0))
                            else:
                                setattr(config, k, v_str)
                        except Exception:
                            pass
                conn.commit()
                logger.info(f"[init_db] Successfully loaded {loaded_count} system settings from {config.SETTINGS_JSON_FILE} with empty-overwrite protection")
            except Exception as ex:
                logger.error(f"[init_db] Error reading settings from {config.SETTINGS_JSON_FILE}: {ex}")
        else:
            # Export initial settings to data/settings.json
            try:
                sync_settings_to_json_and_env()
            except Exception:
                pass

        # Load admin_password, Nara, Gemini, and Default Artist settings from DB if configured (only if not set in os.environ)
        cur.execute("SELECT key, value FROM system_settings WHERE key IN ('admin_password', 'nara_api_key', 'nara_model', 'nara_base_url', 'gemini_api_key', 'GEMINI_API_KEY', 'gemini_model', 'GEMINI_MODEL', 'DEFAULT_ARTIST', 'default_artist')")
        for s_row in cur.fetchall():
            k, v = s_row[0], s_row[1]
            if k == 'admin_password' and v:
                if not os.environ.get("ADMIN_PANEL_PASSWORD"):
                    config.ADMIN_PANEL_PASSWORD = str(v).strip()
            elif k == 'nara_api_key' and v:
                if not os.environ.get("NARA_API_KEY"):
                    config.NARA_API_KEY = str(v).strip()
            elif k == 'nara_model' and v:
                if not os.environ.get("NARA_MODEL"):
                    m_val = str(v).strip()
                    if m_val == "mistral-large":
                        m_val = "mimo-v2.5-free"
                    config.NARA_MODEL = m_val
            elif k == 'nara_base_url' and v:
                if not os.environ.get("NARA_BASE_URL"):
                    config.NARA_BASE_URL = str(v).strip()
            elif k in ('gemini_api_key', 'GEMINI_API_KEY') and v:
                if not os.environ.get("GEMINI_API_KEY"):
                    config.GEMINI_API_KEY = str(v).strip()
            elif k in ('gemini_model', 'GEMINI_MODEL') and v:
                if not os.environ.get("GEMINI_MODEL"):
                    config.GEMINI_MODEL = str(v).strip()
            elif k in ('DEFAULT_ARTIST', 'default_artist') and v:
                if not os.environ.get("DEFAULT_ARTIST"):
                    config.DEFAULT_ARTIST = str(v).strip()

        # 2. First priority: Load courses from data/courses.json
        courses_file = config.COURSES_JSON_FILE if config.COURSES_JSON_FILE.exists() else (config.DATA_DIR / "courses_backup.json")
        cur.execute("SELECT COUNT(*) FROM products")
        count = cur.fetchone()[0]

        if count == 0:
            if courses_file.exists():
                try:
                    with open(courses_file, "r", encoding="utf-8") as f:
                        b_items = json.load(f)
                    for item in b_items:
                        if not bool(item.get("active", 1)):
                            continue
                        cur.execute(
                            """INSERT INTO products (
                                product_id, name, price, description, download_link, photo_url,
                                allow_card, allow_bale, payment_type, created_at, active
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                            (
                                item.get("product_id"), item.get("name"), int(item.get("price", 0)),
                                item.get("description", ""), item.get("download_link", ""), item.get("photo_url", ""),
                                int(item.get("allow_card", 1)), int(item.get("allow_bale", 1)),
                                item.get("payment_type", "paid"), item.get("created_at", "2026-08-22"),
                                int(item.get("active", 1))
                            )
                        )
                    conn.commit()
                    logger.info(f"[init_db] Restored {len(b_items)} courses from disk JSON {courses_file}")
                except Exception as ex:
                    logger.error(f"[init_db] Error restoring courses from {courses_file}: {ex}")
            else:
                seed = [
                    ("prod_01", "دوره جامع کشف قوانین زندگی", 8800000, "دوره بی‌نظیر کشف قوانین بدون تغییر جهان هستی برای درک مدارها، فرکانس‌ها و ساخت اتفاقات دلخواه زندگی.", "", "", 1, 1, "paid", "2026-08-22", 1),
                    ("prod_02", "دوره روانشناسی ثروت ۱", 8900000, "شناسایی و تغییر ترمزها و باورهای مخرب مالی و دستیابی به استقلال و آزادی مالی پایدار.", "", "", 1, 1, "paid", "2026-08-22", 1),
                    ("prod_03", "دوره جامع عزت‌نفس و خودباوری", 3500000, "ساخت بنیادهای محکم شخصیتی، رهایی از گفتگوهای منفی ذهنی، احساس لیاقت و شجاعت فردی.", "", "", 1, 1, "paid", "2026-08-22", 1),
                ]
                cur.executemany(
                    """INSERT INTO products (
                        product_id, name, price, description, download_link, photo_url,
                        allow_card, allow_bale, payment_type, created_at, active
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    seed
                )
                conn.commit()
                # Create initial courses.json
                try:
                    init_data = [{
                        "product_id": s[0], "name": s[1], "price": s[2], "description": s[3],
                        "download_link": s[4], "photo_url": s[5], "allow_card": s[6], "allow_bale": s[7],
                        "payment_type": s[8], "created_at": s[9], "active": s[10]
                    } for s in seed]
                    with open(config.COURSES_JSON_FILE, "w", encoding="utf-8") as f:
                        json.dump(init_data, f, ensure_ascii=False, indent=2)
                except Exception:
                    pass
        elif not config.COURSES_JSON_FILE.exists():
            # Sync existing DB to courses.json
            try:
                cur.execute("SELECT product_id, name, price, description, download_link, photo_url, allow_card, allow_bale, payment_type, created_at, active FROM products")
                existing = [{
                    "product_id": r[0], "name": r[1], "price": r[2], "description": r[3],
                    "download_link": r[4], "photo_url": r[5], "allow_card": r[6], "allow_bale": r[7],
                    "payment_type": r[8], "created_at": r[9], "active": r[10]
                } for r in cur.fetchall()]
                with open(config.COURSES_JSON_FILE, "w", encoding="utf-8") as f:
                    json.dump(existing, f, ensure_ascii=False, indent=2)
            except Exception:
                pass

        # Permanent cleanup of legacy ghost sessions, extra courses, and fake test tokens
        try:
            cur.execute("""
            DELETE FROM media_sessions
            WHERE drop_id LIKE 'test_%'
               OR drop_id LIKE 'cleanup_%'
               OR drop_id LIKE 'unique_test_%'
               OR drop_id IN (
                   '2fca0108', '0f911a3c', '634565a0', '4ee8ea80',
                   '4c050e8b', '1e832d9d', 'eec9b85a', 'test_drop_v24_9',
                   'drop_test_persistence', '2f555dc7', 'bfb26c62', 'c98a561f'
               )
            """)

            cur.execute("""
            DELETE FROM products
            WHERE product_id NOT IN ('prod_01', 'prod_02', 'prod_03')
            """)

            cur.execute("""
            UPDATE system_settings SET value = ''
            WHERE key = 'bale_payment_token' AND value LIKE '%secret_123456%'
            """)

            cur.execute("""
            UPDATE system_settings SET value = ''
            WHERE key = 'tg_fjoin_channel' AND value LIKE '%unfinit%'
            """)

            cur.execute("""
            UPDATE system_settings SET value = 'فروشگاه دوره‌های آموزشی UNFINIT'
            WHERE key = 'STORE_NAME' OR value LIKE '%Ù%' OR value LIKE '%Ø%'
            """)
            cur.execute("""
            UPDATE system_settings SET value = 'mimo-v2.5-free'
            WHERE key = 'nara_model' AND value = 'mistral-large'
            """)
            config.STORE_NAME = fix_mojibake(config.STORE_NAME)
            config.WELCOME_TEXT = fix_mojibake(config.WELCOME_TEXT, default="به فروشگاه دوره‌های آموزشی و دانلودی UNFINIT خوش آمدید.")

            env_bale_pay = os.getenv("BALE_PAYMENT_TOKEN", "").strip()
            if env_bale_pay:
                cur.execute(
                    "INSERT INTO system_settings (key, value) VALUES ('bale_payment_token', ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                    (env_bale_pay,)
                )
                config.BALE_PAYMENT_TOKEN = env_bale_pay

            conn.commit()
            logger.info("[init_db] Cleaned up legacy test sessions, extra courses, and fake tokens successfully.")
        except Exception as ex_clean:
            logger.error(f"[init_db] Error during cleanup: {ex_clean}")

        conn.close()

    await asyncio.to_thread(_init)
