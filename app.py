import os
import sys
import re
import asyncio
import threading
import subprocess
from typing import Any, Optional, Dict, List
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from core.config import config
from core.logger import get_logger
from core.database import init_db
from task_store import ensure_storage_dirs

logger = get_logger("main_app")
ensure_storage_dirs()
config.TEMP_DIR.mkdir(parents=True, exist_ok=True)
config.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
config.BANNERS_DIR.mkdir(parents=True, exist_ok=True)
config.DATA_DIR.mkdir(parents=True, exist_ok=True)

import json
import urllib.parse
import uuid
from services.web_panel import (
    render_dashboard_html,
    render_storefront_html,
    get_system_health,
    handle_api_dispatch_url,
    handle_store_buy_bale,
    handle_store_buy_card,
    handle_store_get_orders,
    handle_store_approve_order,
    handle_store_reject_order,
    handle_store_delete_order,
    handle_store_cleanup_rejected_orders,
    handle_store_get_order_status
)
from services.store_service import StoreService
from services.session_manager import session_manager
from core.database import get_system_setting, set_system_setting, get_db_connection, fix_mojibake

def get_valid_admin_passwords() -> set:
    """Retrieves all valid admin passwords from environment, config, and database."""
    valid = set()
    if getattr(config, "ADMIN_PANEL_PASSWORD", None):
        p = str(config.ADMIN_PANEL_PASSWORD).strip()
        if p:
            valid.add(p)
    if os.environ.get("ADMIN_PANEL_PASSWORD"):
        p = str(os.environ.get("ADMIN_PANEL_PASSWORD")).strip()
        if p:
            valid.add(p)
    try:
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT value FROM system_settings WHERE key = 'admin_password'")
            row = cur.fetchone()
            if row and row[0]:
                p = str(row[0]).strip()
                if p:
                    valid.add(p)
        finally:
            conn.close()
    except Exception:
        pass
    return valid

def verify_admin_password(pwd: Any) -> bool:
    """Strictly validates provided password against non-empty registered admin passwords."""
    if not pwd or not isinstance(pwd, str):
        return False
    pwd_clean = pwd.strip()
    if not pwd_clean:
        return False
    valid = get_valid_admin_passwords()
    if not valid:
        return False
    return pwd_clean in valid

def mask_secret(val: Any, prefix_len: int = 4, suffix_len: int = 4) -> str:
    """Masks sensitive secret tokens/keys for UI display (e.g. hf_1234••••••••5678)."""
    s = str(val or "").strip()
    if not s or s.lower() in ("0", "none", "null", "false"):
        return ""
    if len(s) <= 8:
        return "••••••••"
    return f"{s[:prefix_len]}••••••••{s[-suffix_len:]}"

def is_masked_or_empty(val: Any) -> bool:
    """Detects if an incoming setting value is untouched/masked or empty."""
    if val is None:
        return True
    s = str(val).strip()
    if not s:
        return True
    return "••••" in s or "****" in s

def _clean_val(val: Any) -> str:
    s = str(val or "").strip()
    if s in ("0", "none", "null"):
        return ""
    return s

def _first_valid(*vals) -> str:
    for v in vals:
        s = _clean_val(v)
        if s and s.lower() not in ("0", "none", "null", "false"):
            return s
    return ""

async def get_all_settings_async() -> dict:
    # Direct priority: os.environ (HF Space Secrets) -> config -> SQLite database
    tg_tok = _first_valid(os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("BOT_TOKEN"), config.TELEGRAM_BOT_TOKEN, await get_system_setting("TELEGRAM_BOT_TOKEN", ""))
    bale_tok = _first_valid(os.environ.get("BALE_BOT_TOKEN"), config.BALE_BOT_TOKEN, await get_system_setting("BALE_BOT_TOKEN", ""))
    bale_pay = _first_valid(os.environ.get("BALE_PAYMENT_TOKEN"), config.BALE_PAYMENT_TOKEN, await get_system_setting("bale_payment_token", ""))
    rubika_tok = _first_valid(os.environ.get("RUBIKA_BOT_TOKEN"), config.RUBIKA_BOT_TOKEN, await get_system_setting("RUBIKA_BOT_TOKEN", ""))
    nara_key = _first_valid(os.environ.get("NARA_API_KEY"), config.NARA_API_KEY, await get_system_setting("nara_api_key", ""))
    gemini_key = _first_valid(os.environ.get("GEMINI_API_KEY"), config.GEMINI_API_KEY, await get_system_setting("gemini_api_key", ""))
    hf_tok = _first_valid(os.environ.get("HF_TOKEN"), getattr(config, "HF_TOKEN", ""), await get_system_setting("HF_TOKEN", ""))
    hf_sp = _first_valid(os.environ.get("HF_SPACE_ID"), getattr(config, "HF_SPACE_ID", ""), await get_system_setting("HF_SPACE_ID", ""), "Foadian/UNFINIT")
    card_num = _first_valid(os.environ.get("CARD_NUMBER"), config.CARD_NUMBER, await get_system_setting("CARD_NUMBER", ""))
    card_holder = _first_valid(os.environ.get("CARD_HOLDER"), config.CARD_HOLDER, await get_system_setting("CARD_HOLDER", ""))
    zarin_mid = _first_valid(os.environ.get("ZARINPAL_MERCHANT_ID"), getattr(config, "ZARINPAL_MERCHANT_ID", ""), await get_system_setting("zarinpal_merchant_id", ""))
    cd_note = await get_system_setting("COURSE_DELIVERY_NOTE", getattr(config, "COURSE_DELIVERY_NOTE", "امیدوارم این دوره، براتون سرشار از آگاهی، رشد و نتایج ارزشمند باشه. ✨"))

    return {
        "STORE_NAME": fix_mojibake(await get_system_setting("STORE_NAME", config.STORE_NAME)),
        "WELCOME_TEXT": fix_mojibake(await get_system_setting("WELCOME_TEXT", config.WELCOME_TEXT), default=config.WELCOME_TEXT),
        "TELEGRAM_BOT_TOKEN": mask_secret(tg_tok),
        "TELEGRAM_OWNER_ID": _first_valid(os.environ.get("TELEGRAM_OWNER_ID"), str(config.TELEGRAM_OWNER_ID), await get_system_setting("TELEGRAM_OWNER_ID", "")),
        "BALE_BOT_TOKEN": mask_secret(bale_tok),
        "BALE_OWNER_ID": _first_valid(os.environ.get("BALE_OWNER_ID"), str(config.BALE_OWNER_ID), await get_system_setting("BALE_OWNER_ID", "")),
        "BALE_PAYMENT_TOKEN": mask_secret(bale_pay),
        "RUBIKA_BOT_TOKEN": mask_secret(rubika_tok),
        "RUBIKA_OWNER_ID": _first_valid(os.environ.get("RUBIKA_OWNER_ID"), str(config.RUBIKA_OWNER_ID), await get_system_setting("RUBIKA_OWNER_ID", "")),
        "FORCE_JOIN_CHANNEL_TELEGRAM": await get_system_setting("tg_fjoin_channel", config.FORCE_JOIN_CHANNEL_TELEGRAM),
        "FORCE_JOIN_CHANNEL_BALE": await get_system_setting("bale_fjoin_channel", config.FORCE_JOIN_CHANNEL_BALE),
        "CARD_NUMBER": mask_secret(card_num, 4, 4),
        "CARD_HOLDER": card_holder,
        "DEFAULT_ARTIST": fix_mojibake(await get_system_setting("DEFAULT_ARTIST", config.DEFAULT_ARTIST), default=config.DEFAULT_ARTIST),
        "COURSE_DESC_MAX_LEN": await get_system_setting("COURSE_DESC_MAX_LEN", str(getattr(config, "COURSE_DESC_MAX_LEN", 255))),
        "NARA_API_KEY": mask_secret(nara_key),
        "NARA_MODEL": await get_system_setting("nara_model", config.NARA_MODEL),
        "GEMINI_API_KEY": mask_secret(gemini_key),
        "GEMINI_MODEL": await get_system_setting("gemini_model", config.GEMINI_MODEL),
        "TELEGRAM_FORUM_GROUP_ID": await get_system_setting("tg_forum_group_id", getattr(config, "TELEGRAM_FORUM_GROUP_ID", "")),
        "ADMIN_USER_IDS": await get_system_setting("admin_user_ids", ",".join(getattr(config, "ADMIN_USER_IDS", []))),
        "ZARINPAL_MERCHANT_ID": mask_secret(zarin_mid),
        "ZARINPAL_SANDBOX": str(await get_system_setting("zarinpal_sandbox", str(getattr(config, "ZARINPAL_SANDBOX", False)))).lower(),
        "MAX_SAFE_BALE_SIZE_MB": str(await get_system_setting("max_safe_bale_size_mb", str(getattr(config, "MAX_SAFE_BALE_SIZE_MB", 49.99)))),
        "HF_TOKEN": mask_secret(hf_tok),
        "HF_SPACE_ID": str(hf_sp or "Foadian/UNFINIT").strip(),
        "COURSE_DELIVERY_NOTE": fix_mojibake(cd_note, default="امیدوارم این دوره، براتون سرشار از آگاهی، رشد و نتایج ارزشمند باشه. ✨"),
    }

def get_all_settings() -> dict:
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(get_all_settings_async())
    finally:
        loop.close()

_get_all_settings = get_all_settings


class WebhookAndHealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path in ("/store", "/store/"):
            try:
                html = render_storefront_html()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(html.encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(f"Error rendering storefront: {e}".encode("utf-8"))
            return
        elif path == "/api/store/orders":
            try:
                res = handle_store_get_orders()
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode("utf-8"))
            return
        elif path == "/api/store/order_status":
            try:
                query_params = urllib.parse.parse_qs(parsed.query)
                ord_id = (query_params.get("order_id", [""])[0]).strip()
                phone = (query_params.get("phone", [""])[0]).strip()
                q = ord_id or phone
                res = handle_store_get_order_status(q)
                self.send_response(200 if res.get("ok") else 400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
        elif path == "/api/analytics":
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                data = loop.run_until_complete(StoreService.get_sales_analytics())
                loop.close()
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": True, "analytics": data}, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode("utf-8"))
            return
        elif path == "/api/coupons":
            try:
                from core.database import db_get_all_coupons
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                coupons = loop.run_until_complete(db_get_all_coupons())
                loop.close()
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": True, "coupons": coupons}, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode("utf-8"))
            return
        elif path in ("/", "/dashboard"):
            try:
                html = render_dashboard_html()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(html.encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(f"Error rendering dashboard: {e}".encode("utf-8"))
        elif path == "/api/status":
            health = get_system_health()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(health, ensure_ascii=False).encode("utf-8"))
        elif path == "/api/products":
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                prods = loop.run_until_complete(StoreService.get_products(is_free_only=False))
                loop.close()
                res = [{"id": p.product_id, "name": p.name, "price": p.price, "desc": p.description} for p in prods]
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": True, "products": res}, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
        elif path == "/api/logs":
            from core.logger import get_recent_logs
            logs = get_recent_logs(200)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True, "logs": logs}, ensure_ascii=False).encode("utf-8"))
        elif path == "/api/logs/download":
            log_path = BASE_DIR / "unfinit_server_log.txt"
            content = b""
            if log_path.exists():
                try:
                    with open(log_path, "rb") as f:
                        content = f.read()
                except Exception as e:
                    content = f"Error reading log file: {e}".encode("utf-8")
            else:
                from core.logger import get_recent_logs
                logs = get_recent_logs(500)
                content = "\n".join(logs).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Disposition", 'attachment; filename="unfinit_server_log.txt"')
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return
        elif path == "/api/courses":
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                prods = loop.run_until_complete(StoreService.get_all_products())
                loop.close()
                res_prods = [{
                    "product_id": p.product_id,
                    "name": p.name,
                    "price": p.price,
                    "description": p.description,
                    "download_link": p.download_link,
                    "photo_url": p.photo_url,
                    "active": p.active,
                    "allow_card": p.allow_card,
                    "allow_bale": p.allow_bale
                } for p in prods]
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": True, "courses": res_prods}, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode("utf-8"))
        elif path.startswith("/dl/"):
            drop_id = path[4:].strip()
            session = session_manager.get_session(drop_id)
            if not session:
                self.send_response(404)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(f"نشست فایل رسانه با شناسه {drop_id} یافت نشد یا منقضی شده است.".encode("utf-8"))
                return

            local_path = session.get("working_path") or session.get("compressed_path") or session.get("local_path")
            if not local_path or not Path(local_path).exists():
                from services.web_panel import ensure_session_file_on_disk, _run_sync
                p_disk = _run_sync(ensure_session_file_on_disk(drop_id))
                if p_disk and p_disk.exists():
                    local_path = str(p_disk)
                else:
                    self.send_response(404)
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                    self.end_headers()
                    self.wfile.write("فایل باینری روی دیسک سرور یافت نشد و امکان دانلود خودکار از مبدا میسر نگردید.".encode("utf-8"))
                    return

            p = Path(local_path)
            file_size = p.stat().st_size
            send_name = session.get("audio_filename") or p.name
            safe_ascii_name = urllib.parse.quote(send_name)

            content_type = "application/octet-stream"
            suf = p.suffix.lower()
            if suf == ".mp3":
                content_type = "audio/mpeg"
            elif suf in (".m4a", ".aac"):
                content_type = "audio/mp4"
            elif suf in (".mp4", ".mkv", ".mov"):
                content_type = "video/mp4"

            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{safe_ascii_name}")
            self.send_header("Content-Length", str(file_size))
            self.end_headers()

            try:
                with open(p, "rb") as f:
                    while chunk := f.read(64 * 1024):
                        self.wfile.write(chunk)
            except Exception:
                pass
            return
        elif path.startswith("/uploads/"):
            rel_sub = path[len("/uploads/"):].strip()
            clean_sub = Path(rel_sub)
            if ".." in clean_sub.parts:
                self.send_response(403)
                self.end_headers()
                return

            if rel_sub.startswith("banners/"):
                b_name = Path(rel_sub[len("banners/"):].strip()).name
                file_path = config.BANNERS_DIR / b_name
            else:
                file_path = (config.UPLOADS_DIR / clean_sub).resolve()
                try:
                    file_path.relative_to(config.UPLOADS_DIR.resolve())
                except ValueError:
                    self.send_response(403)
                    self.end_headers()
                    return

            if not file_path.exists() or not file_path.is_file():
                self.send_response(404)
                self.end_headers()
                return

            mime = "image/jpeg"
            suf = file_path.suffix.lower()
            if suf == ".png": mime = "image/png"
            elif suf == ".webp": mime = "image/webp"
            elif suf == ".gif": mime = "image/gif"
            elif suf == ".svg": mime = "image/svg+xml"
            elif suf == ".mp3": mime = "audio/mpeg"
            elif suf == ".mp4": mime = "video/mp4"

            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(file_path.stat().st_size))
            self.send_header("Cache-Control", "public, max-age=86400")
            self.end_headers()
            try:
                with open(file_path, "rb") as f:
                    while chunk := f.read(64 * 1024):
                        self.wfile.write(chunk)
            except Exception:
                pass
            return
        elif path.startswith("/api/studio/specs"):
            # Support both /api/studio/specs/<drop_id> and /api/studio/specs?drop_id=<drop_id>
            drop_id = ""
            if path.startswith("/api/studio/specs/"):
                drop_id = path[len("/api/studio/specs/"):].strip()
            if not drop_id:
                query_params = urllib.parse.parse_qs(parsed.query)
                drop_id = (query_params.get("drop_id", [""])[0]).strip()

            from services.web_panel import handle_studio_specs
            specs_data = handle_studio_specs(drop_id)
            self.send_response(200 if specs_data.get("ok") else 400)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(specs_data, ensure_ascii=False).encode("utf-8"))
            return
        elif path.startswith("/api/studio/cover/"):
            drop_id = path[len("/api/studio/cover/"):].strip()
            from services.web_panel import get_studio_cover_bytes
            cov_bytes, mime = get_studio_cover_bytes(drop_id)
            if cov_bytes:
                self.send_response(200)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(len(cov_bytes)))
                self.send_header("Cache-Control", "public, max-age=3600")
                self.end_headers()
                self.wfile.write(cov_bytes)
            else:
                self.send_response(404)
                self.end_headers()
            return
        elif path == "/api/studio/table_html":
            from services.web_panel import handle_studio_table_html
            query_params = urllib.parse.parse_qs(parsed.query)
            sort_by = (query_params.get("sort", ["newest"])[0]).strip()
            table_data = handle_studio_table_html(sort_by=sort_by)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(table_data, ensure_ascii=False).encode("utf-8"))
            return
        elif path == "/api/settings":
            query_params = urllib.parse.parse_qs(parsed.query)
            pwd = (query_params.get("password", [""])[0]).strip()

            if not verify_admin_password(pwd):
                self.send_response(401)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": "رمز عبور مدیریت سیستم نادرست است یا سکرت ADMIN_PANEL_PASSWORD تنظیم نشده است."}, ensure_ascii=False).encode("utf-8"))
                return

            try:
                settings_data = get_all_settings()
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": True, "settings": settings_data}, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode("utf-8"))
        elif path == "/api/settings/export":
            query_params = urllib.parse.parse_qs(parsed.query)
            pwd = (query_params.get("password", [""])[0]).strip()
            if not verify_admin_password(pwd):
                self.send_response(401)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": "رمز عبور مدیریت سیستم نادرست است یا سکرت ADMIN_PANEL_PASSWORD تنظیم نشده است."}, ensure_ascii=False).encode("utf-8"))
                return

            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                async def _export_settings():
                    conn = get_db_connection()
                    try:
                        cur = conn.cursor()
                        cur.execute("SELECT key, value FROM system_settings")
                        db_dict = {row[0]: row[1] for row in cur.fetchall()}
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
                        "COURSE_DESC_MAX_LEN": str(getattr(config, "COURSE_DESC_MAX_LEN", 255)),
                        "NARA_API_KEY": config.NARA_API_KEY,
                        "NARA_MODEL": config.NARA_MODEL,
                        "NARA_BASE_URL": config.NARA_BASE_URL,
                        "GEMINI_API_KEY": config.GEMINI_API_KEY,
                        "GEMINI_MODEL": config.GEMINI_MODEL,
                        "TELEGRAM_FORUM_GROUP_ID": getattr(config, "TELEGRAM_FORUM_GROUP_ID", ""),
                        "ADMIN_USER_IDS": ",".join(getattr(config, "ADMIN_USER_IDS", [])),
                        "ZARINPAL_MERCHANT_ID": getattr(config, "ZARINPAL_MERCHANT_ID", ""),
                        "ZARINPAL_SANDBOX": str(getattr(config, "ZARINPAL_SANDBOX", False)),
                        "MAX_SAFE_BALE_SIZE_MB": str(getattr(config, "MAX_SAFE_BALE_SIZE_MB", 49.99))
                    }
                    SENSITIVE_KEYS = {
                        "TELEGRAM_BOT_TOKEN", "BALE_BOT_TOKEN", "RUBIKA_BOT_TOKEN",
                        "BALE_PAYMENT_TOKEN", "bale_payment_token",
                        "NARA_API_KEY", "nara_api_key",
                        "GEMINI_API_KEY", "gemini_api_key",
                        "ADMIN_PANEL_PASSWORD", "admin_password"
                    }
                    for k, v in crucial_keys.items():
                        if k not in db_dict:
                            db_dict[k] = v
                    for k in SENSITIVE_KEYS:
                        db_dict[k] = ""  # Security: Never leak secrets in downloadable export
                    return db_dict

                export_data = loop.run_until_complete(_export_settings())
                loop.close()

                export_bytes = json.dumps(export_data, ensure_ascii=False, indent=2).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Disposition", 'attachment; filename="settings_backup.json"')
                self.send_header("Content-Length", str(len(export_bytes)))
                self.end_headers()
                self.wfile.write(export_bytes)
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode("utf-8"))
            return
        elif path == "/api/payment/zarinpal/callback":
            query_params = urllib.parse.parse_qs(parsed.query)
            order_id = (query_params.get("order_id", [""])[0]).strip()
            authority = (query_params.get("Authority", [""])[0]).strip()
            status = (query_params.get("Status", [""])[0]).strip()

            if status != "OK" or not authority:
                self.send_response(302)
                self.send_header("Location", f"/store?payment=failed&order_id={urllib.parse.quote(order_id)}")
                self.end_headers()
                return

            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                res = loop.run_until_complete(StoreService.verify_zarinpal_payment(order_id, authority))
                loop.close()

                if res.get("ok"):
                    dl = urllib.parse.quote(str(res.get("download_link") or ""))
                    ref_id = urllib.parse.quote(str(res.get("ref_id") or ""))
                    self.send_response(302)
                    self.send_header("Location", f"/store?payment=success&order_id={urllib.parse.quote(order_id)}&ref_id={ref_id}&dl={dl}")
                    self.end_headers()
                else:
                    err = urllib.parse.quote(str(res.get("error") or "Verification failed"))
                    self.send_response(302)
                    self.send_header("Location", f"/store?payment=failed&order_id={urllib.parse.quote(order_id)}&error={err}")
                    self.end_headers()
            except Exception as e:
                self.send_response(302)
                self.send_header("Location", f"/store?payment=failed&order_id={urllib.parse.quote(order_id)}&error={urllib.parse.quote(str(e))}")
                self.end_headers()
            return
        else:
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(f"UNFINIT Production Multi-Platform Engine (Telegram, Bale, Rubika) {config.ENGINE_VERSION} is LIVE!\n".encode("utf-8"))

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length > 0 else b"{}"

        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception:
            payload = {}

        if path == "/api/store/buy_bale":
            try:
                res = handle_store_buy_bale(payload)
                self.send_response(200 if res.get("ok") else 400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode("utf-8"))
            return
        elif path == "/api/store/buy_card":
            try:
                res = handle_store_buy_card(payload)
                self.send_response(200 if res.get("ok") else 400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode("utf-8"))
            return
        elif path == "/api/store/orders/approve":
            try:
                ord_id = (payload.get("order_id") or "").strip()
                res = handle_store_approve_order(ord_id)
                self.send_response(200 if res.get("ok") else 400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode("utf-8"))
            return
        elif path == "/api/store/orders/reject":
            try:
                ord_id = (payload.get("order_id") or "").strip()
                reason = (payload.get("reason") or "").strip()
                res = handle_store_reject_order(ord_id, reason)
                self.send_response(200 if res.get("ok") else 400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode("utf-8"))
            return
        elif path == "/api/store/orders/delete":
            try:
                ord_id = (payload.get("order_id") or "").strip()
                res = handle_store_delete_order(ord_id)
                self.send_response(200 if res.get("ok") else 400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode("utf-8"))
            return
        elif path == "/api/store/orders/cleanup_rejected":
            try:
                res = handle_store_cleanup_rejected_orders()
                self.send_response(200 if res.get("ok") else 400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode("utf-8"))
            return
        elif path in ("/api/coupons/validate", "/api/store/coupon/validate"):
            try:
                code = (payload.get("code") or payload.get("coupon_code") or "").strip()
                amt = int(payload.get("amount") or payload.get("order_amount") or 0)
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                res = loop.run_until_complete(StoreService.validate_coupon(code, amt))
                loop.close()
                self.send_response(200 if res.get("ok") else 400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode("utf-8"))
            return
        elif path == "/api/coupons/create":
            try:
                from core.database import db_create_coupon
                code = (payload.get("code") or "").strip()
                dtype = payload.get("discount_type", "percent")
                dval = int(payload.get("discount_value", 0) or 0)
                max_u = int(payload.get("max_uses", 0) or 0)
                min_amt = int(payload.get("min_order_amount", 0) or 0)
                exp_d = (payload.get("expire_date") or "").strip()
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                ok = loop.run_until_complete(db_create_coupon(code, dtype, dval, max_u, min_amt, exp_d))
                loop.close()
                self.send_response(200 if ok else 400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": ok}, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode("utf-8"))
            return
        elif path == "/api/dispatch_url":
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                res = loop.run_until_complete(handle_api_dispatch_url(payload))
                loop.close()
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode("utf-8"))
        elif path == "/api/studio/upload":
            try:
                from services.web_panel import handle_studio_upload
                res = handle_studio_upload(payload)
                self.send_response(200 if res.get("ok") else 400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode("utf-8"))
        elif path in ("/api/studio/edit_tags", "/api/studio/tags"):
            try:
                from services.web_panel import handle_studio_edit_tags
                res = handle_studio_edit_tags(payload)
                self.send_response(200 if res.get("ok") else 400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode("utf-8"))
        elif path == "/api/studio/batch_edit":
            try:
                from services.web_panel import handle_studio_batch_edit
                res = handle_studio_batch_edit(payload)
                self.send_response(200 if res.get("ok") else 400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode("utf-8"))
        elif path == "/api/studio/dispatch":
            try:
                from services.web_panel import handle_studio_dispatch
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                res = loop.run_until_complete(handle_studio_dispatch(payload))
                loop.close()
                self.send_response(200 if res.get("ok") else 400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode("utf-8"))
        elif path == "/api/studio/cut":
            try:
                from services.web_panel import handle_studio_cut
                res = handle_studio_cut(payload)
                self.send_response(200 if res.get("ok") else 400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode("utf-8"))
        elif path == "/api/studio/delete":
            try:
                from services.web_panel import handle_studio_delete
                res = handle_studio_delete(payload)
                self.send_response(200 if res.get("ok") else 400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode("utf-8"))
        elif path == "/api/studio/delete_batch":
            try:
                from services.web_panel import handle_studio_delete_batch
                res = handle_studio_delete_batch(payload)
                self.send_response(200 if res.get("ok") else 400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode("utf-8"))
        elif path == "/api/studio/cleanup":
            try:
                from services.web_panel import handle_studio_cleanup
                res = handle_studio_cleanup()
                self.send_response(200 if res.get("ok") else 400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode("utf-8"))
        elif path in ("/api/courses/add", "/api/products"):
            try:
                name = payload.get("name", "").strip()
                price = int(payload.get("price", 0))
                desc = payload.get("description", "").strip()
                dl_link = payload.get("download_link", "").strip()
                photo_url = payload.get("photo_url", "").strip()
                allow_card = bool(payload.get("allow_card", True))
                allow_bale = bool(payload.get("allow_bale", True))
                if not name:
                    raise ValueError("نام دوره الزامی است.")
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                p_obj = loop.run_until_complete(StoreService.add_product(
                    name=name, price=price, description=desc,
                    download_link=dl_link, photo_url=photo_url,
                    allow_card=allow_card, allow_bale=allow_bale
                ))
                loop.close()
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": True, "product_id": p_obj.product_id}, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode("utf-8"))
        elif path == "/api/payment/zarinpal/request":
            course_id = (payload.get("course_id") or "").strip()
            name = (payload.get("customer_name") or "").strip()
            phone = (payload.get("phone") or "").strip()
            email = (payload.get("email") or "").strip()
            host = self.headers.get("Host", "localhost:7860")
            scheme = "https" if ("huggingface.co" in host or "hf.space" in host) else "http"
            callback_url = f"{scheme}://{host}/api/payment/zarinpal/callback"

            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                res = loop.run_until_complete(StoreService.request_zarinpal_payment(
                    course_id=course_id,
                    customer_name=name,
                    phone=phone,
                    email=email,
                    callback_url=callback_url
                ))
                loop.close()

                self.send_response(200 if res.get("ok") else 400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(res, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False).encode("utf-8"))
            return
        elif path == "/api/upload/banner":
            try:
                fname = payload.get("filename", "banner.jpg").strip()
                prod_id = payload.get("prod_id", "").strip()
                data_b64 = payload.get("data", "").strip()
                if not data_b64:
                    raise ValueError("داده تصویر ارسال نشده است.")

                if "," in data_b64:
                    data_b64 = data_b64.split(",", 1)[1]

                import base64
                import io
                import re
                from PIL import Image

                img_bytes = base64.b64decode(data_b64)

                # Process image with Pillow: RGBA transparency compositing, 16:9 HD 1280px, JPEG quality 90-92, max 1024KB
                with Image.open(io.BytesIO(img_bytes)) as img:
                    # Clean transparency compositing if image has alpha channel
                    if img.mode in ("RGBA", "LA") or ("transparency" in img.info):
                        bg = Image.new("RGB", img.size, (24, 24, 27))
                        alpha_mask = img.convert("RGBA").split()[3]
                        bg.paste(img.convert("RGBA"), mask=alpha_mask)
                        img = bg
                    elif img.mode != "RGB":
                        img = img.convert("RGB")

                    # 16:9 HD max width 1280px
                    max_w = 1280
                    if img.width > max_w:
                        new_h = int(img.height * (max_w / img.width))
                        img = img.resize((max_w, new_h), Image.Resampling.LANCZOS)

                    q = 92
                    buf = io.BytesIO()
                    img.save(buf, format="JPEG", quality=q, optimize=True)
                    while buf.tell() > 1024 * 1024 and q > 50:
                        q -= 5
                        buf = io.BytesIO()
                        img.save(buf, format="JPEG", quality=q, optimize=True)

                    final_bytes = buf.getvalue()

                safe_prod = re.sub(r'[^a-zA-Z0-9_-]', '', prod_id) if prod_id else "course"
                h_hash = uuid.uuid4().hex[:8]
                safe_name = f"banner_{safe_prod}_{h_hash}.jpg"

                config.BANNERS_DIR.mkdir(parents=True, exist_ok=True)
                dest_path = config.BANNERS_DIR / safe_name
                with open(dest_path, "wb") as f:
                    f.write(final_bytes)

                rel_url = f"/uploads/banners/{safe_name}"
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": True, "url": rel_url}, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self.send_response(400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode("utf-8"))
        elif path == "/api/login":
            pwd = (payload.get("password") or "").strip()
            if verify_admin_password(pwd):
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": True, "token": "authenticated"}, ensure_ascii=False).encode("utf-8"))
            else:
                self.send_response(401)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": "رمز عبور مدیریت نادرست است یا سکرت ADMIN_PANEL_PASSWORD تنظیم نشده است."}, ensure_ascii=False).encode("utf-8"))
        elif path == "/api/hermes/chat":
            msg = (payload.get("message") or "").strip()
            history = payload.get("history") or []
            model = (payload.get("model") or "").strip() or None
            if not msg:
                self.send_response(400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": "پیام ارسال نشده است."}, ensure_ascii=False).encode("utf-8"))
                return
            try:
                from services.hermes_agent import hermes_agent
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                reply_data = loop.run_until_complete(hermes_agent.chat(msg, history, model=model))
                loop.close()
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps(reply_data, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False).encode("utf-8"))
        elif path == "/api/settings":
            try:
                pwd = (payload.get("password") or "").strip()
                if not verify_admin_password(pwd):
                    self.send_response(401)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(json.dumps({"ok": False, "error": "رمز عبور مدیریت سیستم نادرست است یا سکرت ADMIN_PANEL_PASSWORD تنظیم نشده است."}, ensure_ascii=False).encode("utf-8"))
                    return

                new_settings = payload.get("settings", {})
                new_pwd = str(new_settings.get("NEW_ADMIN_PASSWORD") or "").strip()

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                secrets_to_cloud = {}
                CLOUD_SECRET_MAPPING = {
                    "TELEGRAM_BOT_TOKEN": "TELEGRAM_BOT_TOKEN",
                    "TELEGRAM_OWNER_ID": "TELEGRAM_OWNER_ID",
                    "BALE_BOT_TOKEN": "BALE_BOT_TOKEN",
                    "BALE_OWNER_ID": "BALE_OWNER_ID",
                    "BALE_PAYMENT_TOKEN": "BALE_PAYMENT_TOKEN",
                    "RUBIKA_BOT_TOKEN": "RUBIKA_BOT_TOKEN",
                    "RUBIKA_OWNER_ID": "RUBIKA_OWNER_ID",
                    "CARD_NUMBER": "CARD_NUMBER",
                    "CARD_HOLDER": "CARD_HOLDER",
                    "NARA_API_KEY": "NARA_API_KEY",
                    "GEMINI_API_KEY": "GEMINI_API_KEY",
                    "ZARINPAL_MERCHANT_ID": "ZARINPAL_MERCHANT_ID",
                    "HF_TOKEN": "HF_TOKEN",
                    "HF_SPACE_ID": "HF_SPACE_ID",
                }

                async def _save_all():
                    mapping = {
                        "STORE_NAME": "STORE_NAME",
                        "WELCOME_TEXT": "WELCOME_TEXT",
                        "TELEGRAM_BOT_TOKEN": "TELEGRAM_BOT_TOKEN",
                        "TELEGRAM_OWNER_ID": "TELEGRAM_OWNER_ID",
                        "BALE_BOT_TOKEN": "BALE_BOT_TOKEN",
                        "BALE_OWNER_ID": "BALE_OWNER_ID",
                        "BALE_PAYMENT_TOKEN": "bale_payment_token",
                        "RUBIKA_BOT_TOKEN": "RUBIKA_BOT_TOKEN",
                        "RUBIKA_OWNER_ID": "RUBIKA_OWNER_ID",
                        "FORCE_JOIN_CHANNEL_TELEGRAM": "tg_fjoin_channel",
                        "FORCE_JOIN_CHANNEL_BALE": "bale_fjoin_channel",
                        "CARD_NUMBER": "CARD_NUMBER",
                        "CARD_HOLDER": "CARD_HOLDER",
                        "DEFAULT_ARTIST": "DEFAULT_ARTIST",
                        "COURSE_DESC_MAX_LEN": "COURSE_DESC_MAX_LEN",
                        "NARA_API_KEY": "nara_api_key",
                        "NARA_MODEL": "nara_model",
                        "GEMINI_API_KEY": "gemini_api_key",
                        "GEMINI_MODEL": "gemini_model",
                        "TELEGRAM_FORUM_GROUP_ID": "tg_forum_group_id",
                        "ADMIN_USER_IDS": "admin_user_ids",
                        "ZARINPAL_MERCHANT_ID": "zarinpal_merchant_id",
                        "ZARINPAL_SANDBOX": "zarinpal_sandbox",
                        "MAX_SAFE_BALE_SIZE_MB": "max_safe_bale_size_mb",
                        "HF_TOKEN": "HF_TOKEN",
                        "HF_SPACE_ID": "HF_SPACE_ID",
                        "COURSE_DELIVERY_NOTE": "COURSE_DELIVERY_NOTE",
                    }
                    SENSITIVE_KEYS = {
                        "TELEGRAM_BOT_TOKEN", "BALE_BOT_TOKEN", "RUBIKA_BOT_TOKEN",
                        "BALE_PAYMENT_TOKEN", "NARA_API_KEY", "GEMINI_API_KEY",
                        "HF_TOKEN", "CARD_NUMBER", "CARD_HOLDER"
                    }
                    for k, val in new_settings.items():
                        if k in mapping and val is not None:
                            val_str = str(val).strip()
                            if k in SENSITIVE_KEYS and is_masked_or_empty(val_str):
                                continue
                            if k in ("STORE_NAME", "WELCOME_TEXT"):
                                val_str = fix_mojibake(val_str, default=config.STORE_NAME if k == "STORE_NAME" else config.WELCOME_TEXT)
                            if k in ("FORCE_JOIN_CHANNEL_TELEGRAM", "FORCE_JOIN_CHANNEL_BALE") and val_str:
                                if not val_str.startswith("@") and not val_str.lstrip("-").isdigit():
                                    val_str = f"@{val_str}"
                            await set_system_setting(mapping[k], val_str)
                            if hasattr(config, k):
                                try:
                                    if isinstance(getattr(config, k), int):
                                        setattr(config, k, int(val_str or 0))
                                    else:
                                        setattr(config, k, val_str)
                                except Exception:
                                    pass
                            if k == "STORE_NAME":
                                config.STORE_NAME = val_str
                            elif k == "WELCOME_TEXT":
                                config.WELCOME_TEXT = val_str
                            elif k == "BALE_PAYMENT_TOKEN":
                                config.BALE_PAYMENT_TOKEN = val_str
                            elif k == "NARA_API_KEY":
                                config.NARA_API_KEY = val_str
                            elif k == "NARA_MODEL":
                                config.NARA_MODEL = val_str
                            elif k == "GEMINI_API_KEY":
                                config.GEMINI_API_KEY = val_str
                            elif k == "GEMINI_MODEL":
                                config.GEMINI_MODEL = val_str
                            elif k == "COURSE_DESC_MAX_LEN":
                                config.COURSE_DESC_MAX_LEN = int(val_str or 255)
                            elif k == "TELEGRAM_FORUM_GROUP_ID":
                                config.TELEGRAM_FORUM_GROUP_ID = val_str
                            elif k == "ADMIN_USER_IDS":
                                config.ADMIN_USER_IDS = [x.strip() for x in val_str.split(",") if x.strip()]
                            elif k == "ZARINPAL_MERCHANT_ID":
                                config.ZARINPAL_MERCHANT_ID = val_str
                            elif k == "ZARINPAL_SANDBOX":
                                config.ZARINPAL_SANDBOX = val_str.lower() in ("true", "1", "yes")
                            elif k == "MAX_SAFE_BALE_SIZE_MB":
                                try:
                                    config.MAX_SAFE_BALE_SIZE_MB = float(val_str or 49.99)
                                    config.MAX_SAFE_BALE_SIZE_BYTES = int(config.MAX_SAFE_BALE_SIZE_MB * 1024 * 1024)
                                except Exception:
                                    pass
                            elif k == "HF_TOKEN":
                                config.HF_TOKEN = val_str
                                os.environ["HF_TOKEN"] = val_str
                            elif k == "HF_SPACE_ID":
                                config.HF_SPACE_ID = val_str
                                os.environ["HF_SPACE_ID"] = val_str
                            elif k == "COURSE_DELIVERY_NOTE":
                                config.COURSE_DELIVERY_NOTE = val_str

                            # Track cloud secrets to sync
                            if k in CLOUD_SECRET_MAPPING and val_str and not is_masked_or_empty(val_str):
                                secrets_to_cloud[CLOUD_SECRET_MAPPING[k]] = val_str

                    # Check for changing admin password
                    new_pwd = str(new_settings.get("NEW_ADMIN_PASSWORD") or "").strip()
                    if new_pwd and not is_masked_or_empty(new_pwd):
                        await set_system_setting("admin_password", new_pwd)
                        config.ADMIN_PANEL_PASSWORD = new_pwd
                        secrets_to_cloud["ADMIN_PANEL_PASSWORD"] = new_pwd

                loop.run_until_complete(_save_all())
                loop.close()

                # Trigger background sync to Hugging Face Space Secrets and local .env
                if secrets_to_cloud:
                    def _sync_worker(secrets_dict):
                        # Hugging Face Space Secrets
                        hf_token = new_settings.get("HF_TOKEN") or getattr(config, "HF_TOKEN", None) or os.environ.get("HF_TOKEN")
                        if hf_token and is_masked_or_empty(hf_token):
                            hf_token = getattr(config, "HF_TOKEN", None) or os.environ.get("HF_TOKEN")
                        space_id = new_settings.get("HF_SPACE_ID") or getattr(config, "HF_SPACE_ID", None) or os.environ.get("HF_SPACE_ID") or "Foadian/UNFINIT"
                        if space_id and is_masked_or_empty(space_id):
                            space_id = getattr(config, "HF_SPACE_ID", None) or os.environ.get("HF_SPACE_ID") or "Foadian/UNFINIT"
                        if hf_token and space_id:
                            try:
                                from huggingface_hub import HfApi
                                api = HfApi(token=hf_token)
                                for sk, sv in secrets_dict.items():
                                    if sv and str(sv).strip():
                                        api.add_space_secret(repo_id=space_id, key=sk.strip(), value=str(sv).strip())
                                logger.info(f"[cloud_secrets] Synced {len(secrets_dict)} secrets to Hugging Face Space ({space_id})")
                            except Exception as ex:
                                logger.warning(f"[cloud_secrets] Failed to sync to Hugging Face: {ex}")

                        # Local .env file sync
                        env_file = config.BASE_DIR / ".env"
                        if env_file.exists():
                            try:
                                with open(env_file, "r", encoding="utf-8") as f:
                                    lines = f.readlines()
                                existing = set()
                                new_lines = []
                                for line in lines:
                                    s = line.strip()
                                    if s and not s.startswith("#") and "=" in s:
                                        ek, _ = s.split("=", 1)
                                        ek = ek.strip()
                                        existing.add(ek)
                                        if ek in secrets_dict and secrets_dict[ek]:
                                            new_lines.append(f"{ek}={secrets_dict[ek]}\n")
                                        else:
                                            new_lines.append(line)
                                    else:
                                        new_lines.append(line)
                                for ek, ev in secrets_dict.items():
                                    if ek not in existing and ev:
                                        new_lines.append(f"{ek}={ev}\n")
                                with open(env_file, "w", encoding="utf-8") as f:
                                    f.writelines(new_lines)
                                logger.info("[local_secrets] Synced secrets to .env file")
                            except Exception as ex:
                                logger.warning(f"[local_secrets] Failed to sync .env: {ex}")

                    threading.Thread(target=_sync_worker, args=(secrets_to_cloud,), daemon=True).start()

                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": True, "message": "تنظیمات با موفقیت در دیتابیس پایدار و سکرت‌های ابری هاگینگ‌فیس ذخیره و همگام‌سازی شدند."}, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False).encode("utf-8"))
        elif path == "/api/settings/import":
            try:
                pwd = (payload.get("password") or "").strip()
                if not verify_admin_password(pwd):
                    self.send_response(401)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(json.dumps({"ok": False, "error": "رمز عبور مدیریت سیستم نادرست است یا سکرت ADMIN_PANEL_PASSWORD تنظیم نشده است."}, ensure_ascii=False).encode("utf-8"))
                    return

                imported = payload.get("settings") if isinstance(payload.get("settings"), dict) else payload
                if not isinstance(imported, dict) or not imported:
                    raise ValueError("فایل یا داده معتبری از تنظیمات ارسال نشده است.")

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                async def _import_all():
                    mapping = {
                        "TELEGRAM_BOT_TOKEN": "TELEGRAM_BOT_TOKEN",
                        "TELEGRAM_OWNER_ID": "TELEGRAM_OWNER_ID",
                        "BALE_BOT_TOKEN": "BALE_BOT_TOKEN",
                        "BALE_OWNER_ID": "BALE_OWNER_ID",
                        "BALE_PAYMENT_TOKEN": "bale_payment_token",
                        "bale_payment_token": "bale_payment_token",
                        "RUBIKA_BOT_TOKEN": "RUBIKA_BOT_TOKEN",
                        "RUBIKA_OWNER_ID": "RUBIKA_OWNER_ID",
                        "FORCE_JOIN_CHANNEL_TELEGRAM": "tg_fjoin_channel",
                        "tg_fjoin_channel": "tg_fjoin_channel",
                        "FORCE_JOIN_CHANNEL_BALE": "bale_fjoin_channel",
                        "bale_fjoin_channel": "bale_fjoin_channel",
                        "CARD_NUMBER": "CARD_NUMBER",
                        "CARD_HOLDER": "CARD_HOLDER",
                        "COURSE_DESC_MAX_LEN": "COURSE_DESC_MAX_LEN",
                        "NARA_API_KEY": "nara_api_key",
                        "nara_api_key": "nara_api_key",
                        "NARA_MODEL": "nara_model",
                        "nara_model": "nara_model",
                        "NARA_BASE_URL": "nara_base_url",
                        "nara_base_url": "nara_base_url",
                        "GEMINI_API_KEY": "gemini_api_key",
                        "gemini_api_key": "gemini_api_key",
                        "GEMINI_MODEL": "gemini_model",
                        "gemini_model": "gemini_model"
                    }
                    SENSITIVE_KEYS = {
                        "TELEGRAM_BOT_TOKEN", "BALE_BOT_TOKEN", "RUBIKA_BOT_TOKEN",
                        "BALE_PAYMENT_TOKEN", "NARA_API_KEY", "GEMINI_API_KEY",
                        "HF_TOKEN", "CARD_NUMBER", "CARD_HOLDER"
                    }
                    count = 0
                    for k, val in imported.items():
                        if k in ("password", "token") or val is None:
                            continue
                        val_str = str(val).strip()
                        if (k.upper() in SENSITIVE_KEYS or k in SENSITIVE_KEYS) and is_masked_or_empty(val_str):
                            continue
                        db_key = mapping.get(k, k)
                        await set_system_setting(db_key, val_str)
                        count += 1
                        cfg_attr = k.upper()
                        if hasattr(config, cfg_attr):
                            try:
                                if isinstance(getattr(config, cfg_attr), int):
                                    setattr(config, cfg_attr, int(val_str or 0))
                                else:
                                    setattr(config, cfg_attr, val_str)
                            except Exception:
                                pass
                        if cfg_attr == "BALE_PAYMENT_TOKEN":
                            config.BALE_PAYMENT_TOKEN = val_str
                        elif cfg_attr == "NARA_API_KEY":
                            config.NARA_API_KEY = val_str
                        elif cfg_attr == "NARA_MODEL":
                            config.NARA_MODEL = val_str
                        elif cfg_attr == "GEMINI_API_KEY":
                            config.GEMINI_API_KEY = val_str
                        elif cfg_attr == "GEMINI_MODEL":
                            config.GEMINI_MODEL = val_str
                        elif cfg_attr == "COURSE_DESC_MAX_LEN":
                            config.COURSE_DESC_MAX_LEN = int(val_str or 255)
                    return count

                saved_count = loop.run_until_complete(_import_all())
                loop.close()

                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": True, "count": saved_count, "message": f"{saved_count} تنظیم با موفقیت بازیابی شد."}, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self.send_response(400)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False).encode("utf-8"))
        elif path == "/api/courses/update":
            try:
                p_id = payload.get("product_id")
                if not p_id:
                    raise ValueError("شناسه دوره الزامی است.")
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                for field in ("name", "price", "description", "download_link", "photo_url", "allow_card", "allow_bale"):
                    if field in payload:
                        if field == "price":
                            val = int(payload[field])
                        elif field in ("allow_card", "allow_bale"):
                            val = 1 if payload[field] else 0
                        else:
                            val = str(payload[field])
                        loop.run_until_complete(StoreService.update_product_field(p_id, field, val))
                loop.close()
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": True}, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode("utf-8"))
        elif path in ("/api/courses/toggle", "/api/products/toggle_active"):
            try:
                p_id = (payload.get("product_id") or payload.get("id") or "").strip()
                if not p_id:
                    raise ValueError("شناسه دوره الزامی است.")
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                prod = loop.run_until_complete(StoreService.get_product(p_id))
                if not prod:
                    raise ValueError("دوره یافت نشد.")
                new_state = 0 if prod.active else 1
                loop.run_until_complete(StoreService.update_product_field(p_id, "active", new_state))
                loop.close()
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": True, "active": bool(new_state)}, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode("utf-8"))
        elif path in ("/api/courses/delete", "/api/products/delete"):
            try:
                p_id = (payload.get("product_id") or payload.get("id") or "").strip()
                if not p_id:
                    raise ValueError("شناسه دوره الزامی است.")
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(StoreService.delete_product(p_id))
                loop.close()
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": True}, ensure_ascii=False).encode("utf-8"))
            except Exception as e:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode("utf-8"))
        elif path == "/api/payment/zarinpal/callback":
            query_params = urllib.parse.parse_qs(parsed.query)
            order_id = (query_params.get("order_id", [""])[0]).strip()
            authority = (query_params.get("Authority", [""])[0]).strip()
            status = (query_params.get("Status", [""])[0]).strip()

            if status != "OK" or not authority:
                self.send_response(302)
                self.send_header("Location", f"/store?payment=failed&order_id={urllib.parse.quote(order_id)}")
                self.end_headers()
                return

            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                res = loop.run_until_complete(StoreService.verify_zarinpal_payment(order_id, authority))
                loop.close()

                if res.get("ok"):
                    dl = urllib.parse.quote(str(res.get("download_link") or ""))
                    ref_id = urllib.parse.quote(str(res.get("ref_id") or ""))
                    self.send_response(302)
                    self.send_header("Location", f"/store?payment=success&order_id={urllib.parse.quote(order_id)}&ref_id={ref_id}&dl={dl}")
                    self.end_headers()
                else:
                    err = urllib.parse.quote(str(res.get("error") or "Verification failed"))
                    self.send_response(302)
                    self.send_header("Location", f"/store?payment=failed&order_id={urllib.parse.quote(order_id)}&error={err}")
                    self.end_headers()
            except Exception as e:
                self.send_response(302)
                self.send_header("Location", f"/store?payment=failed&order_id={urllib.parse.quote(order_id)}&error={urllib.parse.quote(str(e))}")
                self.end_headers()
            return
        else:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"OK"}')

    def log_message(self, format, *args):
        return

def run_web_server():
    try:
        server = ThreadingHTTPServer(("0.0.0.0", config.PORT), WebhookAndHealthHandler)
        logger.info(f"Web health & webhook server running on port {config.PORT}")
        server.serve_forever()
    except Exception as e:
        logger.error(f"Web server error: {e}")

def start_rubika_worker_process():
    worker_script = BASE_DIR / "rubika_worker.py"
    if worker_script.exists():
        try:
            logger.info("Starting Rubika Task Worker supervisor process...")
            env = {**os.environ, "PYTHONUNBUFFERED": "1"}
            subprocess.Popen([sys.executable, "-u", str(worker_script)], cwd=str(BASE_DIR), env=env)
            logger.info("Rubika Task Worker supervisor process started successfully!")
        except Exception as e:
            logger.error(f"Could not start Rubika worker process: {e}")

async def main():
    logger.info(f"Initializing UNFINIT Multi-Platform Engine {config.ENGINE_VERSION}...")
    
    # 1. Start HTTP Health & Webhook Server
    threading.Thread(target=run_web_server, daemon=True).start()

    # 2. Start Rubika Background Worker Subprocess
    threading.Thread(target=start_rubika_worker_process, daemon=True).start()

    # 3. Initialize Database
    try:
        await init_db()
    except Exception as e:
        logger.error(f"Database init error: {e}")

    # 4. Instantiate Platform Adapters safely
    tg_adapter = None
    bale_adapter = None
    rubika_adapter = None
    instagram_adapter = None

    try:
        from platforms.telegram_adapter import TelegramAdapter
        tg_adapter = TelegramAdapter()
    except Exception as e:
        logger.error(f"Telegram adapter initialization error: {e}")

    try:
        from platforms.bale_adapter import BaleAdapter, run_bale_polling_engine
        bale_adapter = BaleAdapter()
    except Exception as e:
        logger.error(f"Bale adapter initialization error: {e}")

    try:
        from platforms.rubika_adapter import RubikaAdapter, run_rubika_polling_engine
        rubika_adapter = RubikaAdapter()
    except Exception as e:
        logger.error(f"Rubika adapter initialization error: {e}")

    try:
        from platforms.instagram_adapter import InstagramAdapter
        instagram_adapter = InstagramAdapter()
    except Exception as e:
        logger.error(f"Instagram adapter initialization error: {e}")

    try:
        from services.web_panel import set_active_adapters
        set_active_adapters(tg=tg_adapter, bale=bale_adapter, rubika=rubika_adapter)
    except Exception as e:
        logger.warning(f"Could not wire active adapters to web_panel: {e}")

    if tg_adapter:
        tg_adapter.bale_adapter = bale_adapter
        tg_adapter.rubika_adapter = rubika_adapter
        try:
            tg_adapter.register_handlers()
        except Exception as e:
            logger.error(f"Telegram handlers registration error: {e}")

    # 5. Start Bale Polling (if configured)
    if bale_adapter and config.BALE_BOT_TOKEN:
        def run_bale_thread():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(run_bale_polling_engine(telegram_adapter_instance=tg_adapter, rubika_adapter_instance=rubika_adapter))
        threading.Thread(target=run_bale_thread, daemon=True).start()
        logger.info("Bale polling listener engine started.")

    # 6. Start Rubika Bot API Polling (if configured)
    if rubika_adapter and config.RUBIKA_BOT_TOKEN:
        def run_rubika_thread():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(run_rubika_polling_engine(telegram_adapter_instance=tg_adapter, bale_adapter_instance=bale_adapter))
        threading.Thread(target=run_rubika_thread, daemon=True).start()
        logger.info("Rubika Bot API polling listener engine started.")

    # 7. Instagram Listener loop disabled temporarily as per user request to clean up server logs
    # if instagram_adapter and (instagram_adapter.has_session() or (config.INSTAGRAM_USERNAME and config.INSTAGRAM_PASSWORD)):
    #     def run_ig_thread():
    #         loop = asyncio.new_event_loop()
    #         asyncio.set_event_loop(loop)
    #         loop.run_until_complete(run_instagram_listener_engine(telegram_adapter_instance=tg_adapter))
    #     threading.Thread(target=run_ig_thread, daemon=True).start()
    #     logger.info("Instagram listener engine started.")

    # 8. Start Telegram MTProto Client
    if tg_adapter and config.TELEGRAM_BOT_TOKEN and config.API_ID:
        async def start_telegram_with_retry():
            from pyrogram.errors import FloodWait
            while True:
                try:
                    logger.info("Starting Telegram MTProto Client...")
                    await tg_adapter.app.start()
                    logger.info("Telegram MTProto Client is ONLINE and listening!")
                    break
                except FloodWait as fw:
                    wait_sec = int(fw.value)
                    logger.warning(f"Telegram MTProto FloodWait: waiting {wait_sec}s before auto-reconnecting...")
                    await asyncio.sleep(wait_sec + 2)
                except Exception as e:
                    err_str = str(e)
                    if "FLOOD_WAIT" in err_str:
                        m = re.search(r"(\d+)\s*seconds", err_str)
                        wait_sec = int(m.group(1)) if m else 60
                        logger.warning(f"Telegram MTProto FloodWait: waiting {wait_sec}s before auto-reconnecting...")
                        await asyncio.sleep(wait_sec + 2)
                    else:
                        err_str_lower = err_str.lower()
                        if "auth_key_duplicated" in err_str_lower or getattr(e, "ID", None) == "AUTH_KEY_DUPLICATED" or getattr(e, "CODE", None) == 406 or "406" in err_str:
                            session_file = config.DATA_DIR / "unfinit_store_session.session"
                            try:
                                session_file.unlink(missing_ok=True)
                                logger.warning(f"[TG] AUTH_KEY_DUPLICATED: deleted stale session file '{session_file}'. Reconnecting in 2s...")
                            except Exception as del_err:
                                logger.warning(f"[TG] Could not delete session file: {del_err}")
                            await asyncio.sleep(2)
                            # loop continues → fresh session will be created
                        else:
                            logger.error(f"Telegram client start error: {e}")
                            break

        asyncio.create_task(start_telegram_with_retry())

    logger.info(f"UNFINIT Engine {config.ENGINE_VERSION} is fully operational across Telegram, Bale & Rubika!")

    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
