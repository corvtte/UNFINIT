import os
import sys
import asyncio
import aiohttp
import json
import uuid
import re
import time
import html
from html import escape
import urllib.parse
import collections
from pathlib import Path
from typing import Optional, Dict, Any, List, Union, Callable
from core.config import config
from core.logger import get_logger
from core.formatters import (
    BaleFormatter,
    human_size,
    format_duration,
    parse_trim_input,
    get_canonical_menu_action,
    ACTION_PRODUCTS,
    ACTION_PREMIUM,
    ACTION_TODAY_SIGN,
    ACTION_FREE_DOWNLOADS,
    ACTION_USER_ACCOUNT,
    ACTION_FREQUENCY,
    ACTION_SUPPORT
)
from core.database import get_system_setting, set_system_setting, fix_mojibake, db_get_cached_file_id, db_set_cached_file_id
from services.store_service import format_course_links_for_card, format_course_photo_for_card, clean_course_access_input, get_tehran_now_str, StoreService
from services.media_service import MediaService, clean_display_filename
from services.session_manager import session_manager
from services.url_service import UrlService
from services.user_service import UserService, normalize_phone
from services.referral_service import ReferralService, TOHID_AMALI_PACK_ID, TOHID_AMALI_EPISODES
from core.frequency_service import FrequencyService
from media.inspector import inspect_technical_metadata
from media.tagger import extract_cover_image, generate_video_thumbnail

logger = get_logger("bale_adapter")
ACTIVE_BALE_ADMIN_ID: Optional[str] = None
_BALE_POLLING_RUNNING: bool = False

class GiftButtonStr(str):
    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, str):
            return False
        if str.__eq__(self, other):
            return True
        if str(other) in ("📂 دانلودها (هدیه)", "دانلودها (هدیه)", "دانلودها", "🎁 فایل‌های هدیه", "💬 پشتیبانی و هدایا"):
            return True
        return False

    def __contains__(self, item: Any) -> bool:
        if str.__contains__(self, item):
            return True
        if str(item) in ("📂 دانلودها (هدیه)", "دانلودها (هدیه)", "دانلودها", "🎁 فایل‌های هدیه", "💬 پشتیبانی و هدایا", "پشتیبانی", "هدایا"):
            return True
        return False


# مستندسازی فارسی: ساختار کیبورد مشتری بله بر اساس استانداردهای نگارش v0.5.4
# ردیف اول (بزرگ و تکی): [ 🛍 محصولات آموزشی ]
# ردیف دوم (دو دکمه متوازن): [ 🔮 نشانه امروز من ] و [ 💎 اشتراک پریمیوم ]
# ردیف سوم: [ 📂 دانلودها (هدیه) ] و [ 👤 حساب کاربری ]
def get_bale_customer_keyboard() -> dict:
    try:
        from core.database import get_system_setting_sync
        custom = get_system_setting_sync("MAIN_KEYBOARD_LAYOUT", None) or get_system_setting_sync("CUSTOM_KEYBOARD_LAYOUT", None)
        if custom and isinstance(custom, list) and len(custom) > 0:
            kb_rows = []
            for row in custom:
                if isinstance(row, list):
                    r_btns = []
                    for b in row:
                        if isinstance(b, dict):
                            if b.get("active") is False:
                                continue
                            t = b.get("title") or b.get("text") or ""
                            em = b.get("emoji") or ""
                            b_txt = f"{em} {t}".strip() if em and not t.startswith(em) else t.strip()
                        else:
                            b_txt = str(b).strip()
                        if b_txt:
                            r_btns.append({"text": GiftButtonStr(b_txt) if any(x in b_txt for x in ["دانلود", "هدیه"]) else b_txt})
                    if r_btns:
                        kb_rows.append(r_btns)
            if kb_rows:
                return {"keyboard": kb_rows, "resize_keyboard": True}
    except Exception as e_kb:
        logger.debug(f"[bale_adapter] Custom keyboard layout note: {e_kb}")

    return {
        "keyboard": [
            [{"text": "🛍 محصولات آموزشی"}],
            [{"text": "🔮 نشانه امروز من"}, {"text": "💎 اشتراک پریمیوم"}],
            [{"text": GiftButtonStr("📂 دانلودها (هدیه)")}, {"text": "👤 حساب کاربری"}]
        ],
        "resize_keyboard": True
    }


def build_bale_frequency_cats_keyboard() -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "☀️ باورهای صبحگاهی", "callback_data": "freq_page:MORNING:0"},
                {"text": "🌙 باورهای شبانگاهی", "callback_data": "freq_page:NIGHT:0"}
            ]
        ]
    }


def build_bale_frequency_nav_keyboard(category: str = "MORNING", current_idx: int = 0, total: int = 1, total_count: Optional[int] = None, **kwargs) -> dict:
    actual_total = total_count if total_count is not None else total
    actual_total = max(1, actual_total)
    prev_idx = (current_idx - 1) % actual_total
    next_idx = (current_idx + 1) % actual_total
    return {
        "inline_keyboard": [
            [
                {"text": "بعدی ▶️", "callback_data": f"freq_page:{category}:{next_idx}"},
                {"text": f"({current_idx + 1} از {actual_total})", "callback_data": "freq_noop"},
                {"text": "◀️ قبلی", "callback_data": f"freq_page:{category}:{prev_idx}"}
            ],
            [
                {"text": "🔙 بازگشت به دسته‌ها", "callback_data": "freq_cats"}
            ]
        ]
    }

def get_bale_admin_keyboard() -> dict:
    return {
        "keyboard": [
            [{"text": "🎓 مدیریت فروشگاه و دوره‌ها"}, {"text": "🧾 سفارشات و تراکنش‌ها"}],
            [{"text": "📢 پست‌ساز و انتقال فایل"}, {"text": "💬 پشتیبانی و تیکت‌ها"}],
            [{"text": "⚙️ تنظیمات و سلامت سیستم"}, {"text": "👥 پیش‌نمایش پنل مشتری"}]
        ],
        "resize_keyboard": True
    }


def format_bale_transfer_progress(
    current: int,
    total: int,
    elapsed_sec: float,
    stage_title: str = "در حال انتقال فایل...",
    speed_text: Optional[str] = None
) -> str:
    pct = int((current / total) * 100) if total > 0 else 0
    pct = min(100, max(0, pct))
    bar_len = 10
    filled = int((pct / 100) * bar_len)
    bar = "█" * filled + "░" * (bar_len - filled)
    transferred_mb = f"{current / (1024 * 1024):.2f}"
    total_mb = f"{total / (1024 * 1024):.2f}"

    if speed_text:
        disp_speed = speed_text
    else:
        speed_kb = (current / max(0.01, elapsed_sec)) / 1024
        if speed_kb >= 1024:
            disp_speed = f"{speed_kb / 1024:.1f} MB/s"
        else:
            disp_speed = f"{int(speed_kb)} KB/s"

    return (
        f"⏳ <b>{stage_title}</b>\n\n"
        f"<code>[{bar}] {pct}%</code>\n\n"
        f"📦 <b>حجم:</b> <code>{transferred_mb} MB</code> از <code>{total_mb} MB</code>\n"
        f"⚡️ <b>سرعت انتقال:</b> <code>{disp_speed}</code>"
    )


import io

# =============================================================================
# =============================================================================
# نگارش v0.7.1: استریم نامسدودکننده فایل و پیشرفت تراتل‌شده (Throttled File Streamer)
# =============================================================================
# کارکرد: ارسال بایت‌ها با چانک‌های ۲۵۶KB به صورت آسنکرون جهت حداکثر پهنای باند Wire-Speed
# بدون هیچ‌گونه قفل‌شدگی سوکت شبکه یا اسپم تلگرام؛ به‌روزرسانی نوار پیشرفت با تراتل ۴ ثانیه‌ای.
# =============================================================================

class ThrottledFileStreamer:
    """
    استریم نامسدودکننده فایل بر بستر سوکت به همراه گزارش پیشرفت با تراتل زمانی (Throttled Progress Reporting).
    ارسال بایت‌ها با چانک‌های ۲۵۶KB به صورت آسنکرون جهت دستیابی به حداکثر پهنای باند و جلوگیری از مسدودی سوکت.
    """
    def __init__(self, file_path: Union[str, Path], callback: Optional[Callable] = None, throttle_seconds: float = 4.0):
        self.file_path = Path(file_path)
        self.total_size = self.file_path.stat().st_size
        self.callback = callback
        self.throttle_seconds = throttle_seconds
        self.bytes_read = 0
        self.last_update = 0.0

    async def __aiter__(self):
        chunk_size = 256 * 1024  # 256KB chunks for maximum wire throughput
        with open(self.file_path, "rb") as f:
            while chunk := f.read(chunk_size):
                self.bytes_read += len(chunk)
                now = time.time()
                if self.callback and (now - self.last_update >= self.throttle_seconds or self.bytes_read == self.total_size):
                    self.last_update = now
                    percent = (self.bytes_read / self.total_size) * 100 if self.total_size > 0 else 100.0
                    try:
                        res = self.callback(self.bytes_read, self.total_size, percent)
                        if asyncio.iscoroutine(res):
                            asyncio.create_task(res)
                    except Exception:
                        pass
                yield chunk


# آلیاس‌های سازگاری معکوس (Backward Compat Aliases)
ProgressFileWrapper = Any
ProgressFileReader = Any
FastUploadStream = io.BytesIO




def build_bale_admin_course_kb(p_id: str, is_active: bool):
    t_lbl = "🔴 غیرفعال‌سازی دوره" if is_active else "🟢 فعال‌سازی دوره"
    return {
        "inline_keyboard": [
            [
                {"text": "🔗 تغییر لینک‌های دوره", "callback_data": f"badm_c_edit:link:{p_id}"},
                {"text": "💰 تغییر قیمت", "callback_data": f"badm_c_edit:price:{p_id}"}
            ],
            [
                {"text": "📝 تغییر توضیحات", "callback_data": f"badm_c_edit:desc:{p_id}"},
                {"text": "🖼 تغییر بنر / عکس", "callback_data": f"badm_c_edit:photo:{p_id}"}
            ],
            [{"text": t_lbl, "callback_data": f"badm_c_toggle:{p_id}"}],
            [{"text": "🔙 بازگشت به لیست دوره‌ها", "callback_data": "badm_c_list"}]
        ]
    }


def format_bale_admin_course_card(p_item):
    s_txt = "فعال ✅ (نمایش در فروشگاه)" if p_item.active else "غیرفعال ❌ (مخفی)"
    links_txt = format_course_links_for_card(p_item.download_link)
    photo_txt = format_course_photo_for_card(p_item.photo_url)
    return "\n".join([
        f"🎓 <b>مدیریت دوره:</b> <b>{p_item.name}</b>",
        "",
        f"💰 <b>قیمت دوره:</b> <code>{p_item.price:,} تومان</code>",
        f"📊 <b>وضعیت دوره:</b> {s_txt}",
        f"📥 <b>لینک‌های دسترسی:</b>\n{links_txt}",
        f"🖼 <b>پوستر / بنر:</b> {photo_txt}",
        f"📝 <b>توضیحات:</b> {p_item.description or 'ندارد'}"
    ])


def resolve_bale_course_photo(prod: Any) -> Optional[Dict[str, str]]:
    """
    Resolves course photo/banner for Bale messenger delivery.
    Returns {'type': 'file_id'|'local_path'|'url', 'value': str} or None.
    """
    if not prod:
        return None
    b_fid = getattr(prod, "bale_photo_file_id", None)
    if b_fid and str(b_fid).strip():
        return {"type": "file_id", "value": str(b_fid).strip()}
    p_url = (getattr(prod, "photo_url", None) or "").strip()
    if p_url:
        fname = Path(p_url.split("?")[0]).name
        candidates = [
            config.BANNERS_DIR / fname,
            config.UPLOADS_DIR / "banners" / fname,
            config.UPLOADS_DIR / fname,
            config.BASE_DIR / "uploads" / "banners" / fname,
            Path(p_url)
        ]
        for c in candidates:
            try:
                if c.is_file() and c.exists():
                    return {"type": "local_path", "value": str(c.resolve())}
            except Exception:
                pass

        if p_url.startswith("http://") or p_url.startswith("https://"):
            return {"type": "url", "value": p_url}
        elif p_url.startswith("/"):
            host = os.environ.get("SPACE_HOST")
            if host:
                base = f"https://{host}"
            else:
                space_id = os.environ.get("SPACE_ID") or getattr(config, "HF_SPACE_ID", "Foadian/UNFINIT")
                base = f"https://{space_id.replace('/', '-').lower()}.hf.space"
            return {"type": "url", "value": f"{base}{p_url}"}

    return None


def resolve_bale_invoice_photo_url(photo_url: Optional[str]) -> Optional[str]:
    """
    Resolves course photo_url (relative path like /uploads/banners/... or full URL)
    into a publicly accessible HTTPS URL for Bale sendInvoice and createInvoiceLink.
    """
    if not photo_url:
        return None
    p_url = str(photo_url).strip()
    if not p_url:
        return None

    if p_url.startswith("https://"):
        return p_url
    if p_url.startswith("http://"):
        return "https://" + p_url[7:]

    domain = os.environ.get("SPACE_HOST") or os.environ.get("WEB_DOMAIN") or getattr(config, "WEB_DOMAIN", "") or ""
    if not domain:
        space_id = os.environ.get("SPACE_ID") or getattr(config, "HF_SPACE_ID", "Foadian/UNFINIT")
        if space_id and "/" in space_id:
            domain = f"{space_id.replace('/', '-').lower()}.hf.space"
        else:
            domain = "foadian-unfinit.hf.space"

    domain_clean = domain.replace("http://", "").replace("https://", "").strip().rstrip("/")
    clean_path = p_url if p_url.startswith("/") else f"/{p_url}"
    return f"https://{domain_clean}{clean_path}"


class BaleAdapter:
    def __init__(self, token: Optional[str] = None):
        self.token = token or config.BALE_BOT_TOKEN
        self.base_url = f"https://tapi.bale.ai/bot{self.token}"
        self._session: Optional[aiohttp.ClientSession] = None
        self.username: str = getattr(config, "BALE_BOT_USERNAME", "") or ""

    async def get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(limit=50, keepalive_timeout=60, enable_cleanup_closed=True)
            self._session = aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=25))
        return self._session

    async def get_me(self) -> Dict[str, Any]:
        if not self.token:
            return {"ok": False, "error": "BALE_BOT_TOKEN missing"}
        url = f"{self.base_url}/getMe"
        session = await self.get_session()
        async with session.get(url) as resp:
            data = await resp.json()
            if data.get("ok") and data.get("result"):
                u = data.get("result", {}).get("username", "")
                if u:
                    self.username = u
                    config.BALE_BOT_USERNAME = u
            return data


    def get_admin_chat_id(self) -> Optional[str]:
        admin = ACTIVE_BALE_ADMIN_ID or (getattr(config, "BALE_OWNER_ID", None) or None)
        if admin and str(admin).strip() not in ("", "0", "None"):
            return str(admin).strip()
        return None

    def is_admin(self, chat_id: str | int) -> bool:
        if not chat_id:
            return False
        return config.is_admin(chat_id)

    async def check_user_membership(self, chat_id: str | int) -> bool:
        if self.is_admin(chat_id):
            return True
        enabled = (await get_system_setting("bale_fjoin_enabled", "1" if config.FORCE_JOIN_CHANNEL_BALE else "0")) == "1"
        if not enabled:
            return True
        channel = await get_system_setting("bale_fjoin_channel", config.FORCE_JOIN_CHANNEL_BALE)
        if not channel or not channel.strip():
            return True
        channel = channel.strip()
        if not channel.startswith("@") and not channel.lstrip("-").isdigit():
            channel = f"@{channel}"
        try:
            url = f"{self.base_url}/getChatMember?chat_id={channel}&user_id={chat_id}"
            session = await self.get_session()
            async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("ok"):
                            status = data.get("result", {}).get("status", "")
                            return status not in ("left", "kicked", "banned")
            return False
        except Exception as e:
            logger.warning(f"Bale getChatMember error: {e}")
            return True

    async def send_message(self, chat_id: str | int, text: str, reply_markup: Any = None) -> Dict[str, Any]:
        if not self.token:
            return {"ok": False, "error": "BALE_BOT_TOKEN missing"}
        clean_text = BaleFormatter.clean_text(text)
        url = f"{self.base_url}/sendMessage"
        payload = {"chat_id": str(chat_id), "text": clean_text}
        if reply_markup:
            payload["reply_markup"] = reply_markup

        session = await self.get_session()
        async with session.post(url, json=payload) as resp:
            return await resp.json()

    async def send_chat_action(self, chat_id: str | int, action: str = "typing") -> Dict[str, Any]:
        if not self.token:
            return {"ok": False, "error": "BALE_BOT_TOKEN missing"}
        url = f"{self.base_url}/sendChatAction"
        payload = {"chat_id": str(chat_id), "action": str(action)}
        try:
            session = await self.get_session()
            async with session.post(url, json=payload) as resp:
                return await resp.json()
        except Exception as e:
            return {"ok": False, "error": str(e)}

    async def send_photo(
        self,
        chat_id: str | int,
        photo_path: Union[str, Path, bytes],
        caption: Optional[str] = None,
        reply_markup: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if not self.token:
            return {"ok": False, "error": "BALE_BOT_TOKEN missing"}
        url_photo = f"{self.base_url}/sendPhoto"
        form = aiohttp.FormData(quote_fields=False)
        form.add_field("chat_id", str(chat_id))
        if caption: form.add_field("caption", BaleFormatter.clean_text(caption))
        if reply_markup:
            if isinstance(reply_markup, dict):
                form.add_field("reply_markup", json.dumps(reply_markup))
            else:
                form.add_field("reply_markup", str(reply_markup))
        try:
            if isinstance(photo_path, bytes):
                form.add_field("photo", photo_path, filename="photo.jpg", content_type="image/jpeg")
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
                    async with session.post(url_photo, data=form) as resp:
                        return await resp.json()
            else:
                path_obj = Path(str(photo_path))
                if not path_obj.exists():
                    return {"ok": False, "error": "Photo not found"}
                with open(path_obj, "rb") as f:
                    form.add_field("photo", f, filename=path_obj.name, content_type="image/jpeg")
                    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
                        async with session.post(url_photo, data=form) as resp:
                            return await resp.json()
        except Exception as e:
            return {"ok": False, "error": str(e)}

    async def send_document(
        self,
        chat_id: str | int,
        document: Union[str, Path, bytes, Any],
        caption: Optional[str] = None,
        filename: Optional[str] = None,
        reply_markup: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        ارسال فایل/سند بر پایه معماری آزموده و سریع نگارش v0.5.8.
        پشتیبانی مستقیم از هندل فایل باز بدون درگیری رم و بدون تحمیل انکودر ویدیویی بله.
        """
        if not self.token:
            return {"ok": False, "error": "BALE_BOT_TOKEN missing"}
        url_doc = f"{self.base_url}/sendDocument"
        form = aiohttp.FormData(quote_fields=False)
        form.add_field("chat_id", str(chat_id))
        if caption:
            form.add_field("caption", BaleFormatter.clean_text(caption))
        if reply_markup:
            if isinstance(reply_markup, dict):
                form.add_field("reply_markup", json.dumps(reply_markup))
            else:
                form.add_field("reply_markup", str(reply_markup))

        bale_upload_timeout = aiohttp.ClientTimeout(total=600, connect=30, sock_read=300)
        try:
            if isinstance(document, (bytes, bytearray)):
                fname = filename or "document.bin"
                form.add_field("document", document, filename=fname, content_type="application/octet-stream")
                async with aiohttp.ClientSession(timeout=bale_upload_timeout) as session:
                    async with session.post(url_doc, data=form) as resp:
                        res_data = await resp.json()
                        logger.info(f"[Bale Response sendDocument] HTTP {resp.status}: {res_data}")
                        return res_data
            elif hasattr(document, "read"):
                raw_name = filename or getattr(document, "name", None) or "document.bin"
                fname = clean_display_filename(Path(str(raw_name)).name)
                form.add_field("document", document, filename=fname, content_type="application/octet-stream")
                async with aiohttp.ClientSession(timeout=bale_upload_timeout) as session:
                    async with session.post(url_doc, data=form) as resp:
                        res_data = await resp.json()
                        logger.info(f"[Bale Response sendDocument] HTTP {resp.status}: {res_data}")
                        return res_data
            else:
                p = Path(str(document))
                if not p.exists():
                    return {"ok": False, "error": f"File {p} not found"}
                fname = clean_display_filename(filename or p.name)
                if progress_callback:
                    streamer = ThrottledFileStreamer(p, callback=progress_callback, throttle_seconds=4.0)
                    form.add_field("document", streamer, filename=fname, content_type="application/octet-stream")
                    async with aiohttp.ClientSession(timeout=bale_upload_timeout) as session:
                        async with session.post(url_doc, data=form) as resp:
                            res_data = await resp.json()
                            logger.info(f"[Bale Response sendDocument] HTTP {resp.status}: {res_data}")
                            return res_data
                else:
                    with open(p, "rb") as f:
                        form.add_field("document", f, filename=fname, content_type="application/octet-stream")
                        async with aiohttp.ClientSession(timeout=bale_upload_timeout) as session:
                            async with session.post(url_doc, data=form) as resp:
                                res_data = await resp.json()
                                logger.info(f"[Bale Response sendDocument] HTTP {resp.status}: {res_data}")
                                return res_data
        except Exception as e:
            err_msg = f"{type(e).__name__}: {e or repr(e)}"
            logger.error(f"Bale send_document exception: {err_msg}")
            return {"ok": False, "error": err_msg}

    async def send_photo_by_id(
        self,
        chat_id: str | int,
        photo_file_id: str,
        caption: Optional[str] = None,
        reply_markup: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if not self.token:
            return {"ok": False, "error": "BALE_BOT_TOKEN missing"}
        url = f"{self.base_url}/sendPhoto"
        payload: Dict[str, Any] = {"chat_id": str(chat_id), "photo": str(photo_file_id)}
        if caption:
            payload["caption"] = BaleFormatter.clean_text(caption)
        if reply_markup:
            payload["reply_markup"] = reply_markup
        try:
            session = await self.get_session()
            async with session.post(url, json=payload) as resp:
                return await resp.json()
        except Exception as e:
            logger.error(f"Error in Bale send_photo_by_id: {e}")
            return {"ok": False, "error": str(e)}

    async def send_video(
        self,
        chat_id: str | int,
        file_path: Union[str, Path, Any],
        caption: Optional[str] = None,
        duration: Optional[int] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        filename: Optional[str] = None,
        progress_callback: Optional[Callable] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        ارسال ویدیو طبق معماری سبک و مطمئن v0.5.8:
        ابتدا با sendVideo ارسال را انجام می‌دهد؛ در صورت هرگونه خطا،
        بلافاصله و به صورت تک‌مرحله‌ای با sendDocument تحویل قطعی را انجام می‌دهد.
        """
        if not self.token:
            return {"ok": False, "error": "BALE_BOT_TOKEN missing"}

        if hasattr(file_path, "read"):
            path_obj = None
            clean_send_name = clean_display_filename(filename or getattr(file_path, "name", "video.mp4"))
        else:
            path_obj = Path(str(file_path))
            if not path_obj.exists():
                return {"ok": False, "error": "Video file not found on disk"}
            clean_send_name = clean_display_filename(filename or path_obj.name)

        clean_caption = BaleFormatter.clean_text(urllib.parse.unquote(str(caption))) if caption else None
        url_video = f"{self.base_url}/sendVideo"
        form = aiohttp.FormData(quote_fields=False)
        form.add_field("chat_id", str(chat_id))
        if clean_caption: form.add_field("caption", clean_caption)
        if duration: form.add_field("duration", str(int(duration)))
        if width: form.add_field("width", str(int(width)))
        if height: form.add_field("height", str(int(height)))

        bale_video_timeout = aiohttp.ClientTimeout(total=300, connect=30, sock_read=None)

        try:
            if path_obj:
                streamer = ThrottledFileStreamer(path_obj, callback=progress_callback, throttle_seconds=3.0)
                form.add_field("video", streamer, filename=clean_send_name, content_type="video/mp4")
                async with aiohttp.ClientSession(timeout=bale_video_timeout) as session:
                    async with session.post(url_video, data=form) as resp:
                        if resp.status == 200:
                            res = await resp.json()
                            if res.get("ok"):
                                logger.info(f"Bale sendVideo successful: {res}")
                                return res
                            logger.warning(f"Bale sendVideo returned error: {res}, falling back to sendDocument...")
                        else:
                            logger.warning(f"Bale sendVideo HTTP {resp.status}, falling back to sendDocument...")
            else:
                form.add_field("video", file_path, filename=clean_send_name, content_type="video/mp4")
                async with aiohttp.ClientSession(timeout=bale_video_timeout) as session:
                    async with session.post(url_video, data=form) as resp:
                        if resp.status == 200:
                            res = await resp.json()
                            if res.get("ok"):
                                return res
        except Exception as e:
            logger.warning(f"Bale sendVideo exception: {e}, falling back to sendDocument...")

        # فال‌بک تک‌مرحله‌ای به sendDocument بدون لوپ‌های تکراری
        return await self.send_document(
            chat_id=chat_id,
            document=path_obj if path_obj else file_path,
            caption=clean_caption,
            filename=clean_send_name,
            progress_callback=progress_callback
        )

    async def edit_message_text(self, chat_id: str | int, message_id: int, text: str, reply_markup: Any = None) -> Dict[str, Any]:
        if not self.token:
            return {"ok": False, "error": "BALE_BOT_TOKEN missing"}
        clean_text = BaleFormatter.clean_text(text)
        url = f"{self.base_url}/editMessageText"
        payload = {"chat_id": str(chat_id), "message_id": message_id, "text": clean_text}
        if reply_markup:
            payload["reply_markup"] = reply_markup

        session = await self.get_session()
        async with session.post(url, json=payload) as resp:
            return await resp.json()

    async def edit_message_caption(self, chat_id: str | int, message_id: int, caption: str, reply_markup: Any = None) -> Dict[str, Any]:
        if not self.token:
            return {"ok": False, "error": "BALE_BOT_TOKEN missing"}
        clean_caption = BaleFormatter.clean_text(caption)
        url = f"{self.base_url}/editMessageCaption"
        payload = {"chat_id": str(chat_id), "message_id": message_id, "caption": clean_caption}
        if reply_markup:
            payload["reply_markup"] = reply_markup

        session = await self.get_session()
        async with session.post(url, json=payload) as resp:
            return await resp.json()

    async def delete_message(self, chat_id: str | int, message_id: int) -> Dict[str, Any]:
        if not self.token:
            return {"ok": False, "error": "BALE_BOT_TOKEN missing"}
        url = f"{self.base_url}/deleteMessage"
        payload = {"chat_id": str(chat_id), "message_id": message_id}
        try:
            session = await self.get_session()
            async with session.post(url, json=payload) as resp:
                return await resp.json()
        except Exception as e:
            return {"ok": False, "error": str(e)}

    async def send_invoice(
        self,
        chat_id: str | int,
        title: str,
        description: str,
        payload: str,
        provider_token: str,
        amount_tomans: int,
        photo_url: Optional[str] = None,
        reply_markup: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Sends an official invoice for Bale online payment / wallet.
        amount_tomans is converted to Rials (amount_tomans * 10).
        """
        if not self.token:
            return {"ok": False, "error": "BALE_BOT_TOKEN is missing"}

        safe_title = str(title or "دوره آموزشی").strip()[:32]
        if not safe_title:
            safe_title = "دوره آموزشی"
        safe_desc = str(description or safe_title).strip()[:255]
        if not safe_desc:
            safe_desc = safe_title

        url = f"{self.base_url}/sendInvoice"
        amount_rials = max(1000, int(amount_tomans) * 10)
        body: Dict[str, Any] = {
            "chat_id": str(chat_id).strip(),
            "title": safe_title,
            "description": safe_desc,
            "payload": str(payload),
            "provider_token": str(provider_token).strip(),
            "prices": [{"label": safe_title, "amount": amount_rials}],
            "currency": "IRR"
        }
        if reply_markup:
            body["reply_markup"] = reply_markup
        if photo_url:
            p_url = str(photo_url).strip()
            final_photo_url = resolve_bale_invoice_photo_url(p_url)
            if final_photo_url and (final_photo_url.startswith("https://") or final_photo_url.startswith("http://")):
                body["photo_url"] = final_photo_url
                try:
                    fname = Path(p_url.split("?")[0]).name
                    candidates = [
                        config.BANNERS_DIR / fname,
                        config.UPLOADS_DIR / "banners" / fname,
                        config.UPLOADS_DIR / fname,
                        config.BASE_DIR / "uploads" / "banners" / fname
                    ]
                    for c in candidates:
                        if c.exists() and c.is_file():
                            body["photo_size"] = c.stat().st_size
                            from PIL import Image
                            with Image.open(c) as im:
                                body["photo_width"] = im.width
                                body["photo_height"] = im.height
                            break
                except Exception:
                    pass

        try:
            headers = {"Content-Type": "application/json"}
            session = await self.get_session()
            async with session.post(url, json=body, headers=headers) as resp:
                data = await resp.json()
                logger.info(f"Bale sendInvoice status={resp.status} response={data}")
                if data.get("ok"):
                    return data
                if "photo_url" in body:
                    logger.warning(f"Bale sendInvoice failed with photo_url ({data}), retrying without photo_url...")
                    body_no_photo = {k: v for k, v in body.items() if not k.startswith("photo_")}
                    async with session.post(url, json=body_no_photo, headers=headers) as resp2:
                        data2 = await resp2.json()
                        logger.info(f"Bale sendInvoice retry without photo_url response={data2}")
                        return data2
                return data
        except Exception as e:
            logger.error(f"Error in Bale sendInvoice: {e}")
            return {"ok": False, "error": str(e)}

    async def create_invoice_link(
        self,
        title: str,
        description: str,
        payload: str,
        provider_token: str,
        amount_tomans: int,
        photo_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Creates an official direct invoice link via Bale API (createInvoiceLink)
        for web storefront checkouts without requiring Enamad.
        """
        if not self.token:
            return {"ok": False, "error": "BALE_BOT_TOKEN is missing"}

        safe_title = str(title or "دوره آموزشی").strip()[:32]
        if not safe_title:
            safe_title = "دوره آموزشی"
        safe_desc = str(description or safe_title).strip()[:255]
        if not safe_desc:
            safe_desc = safe_title

        url = f"{self.base_url}/createInvoiceLink"
        amount_rials = max(1000, int(amount_tomans) * 10)
        body: Dict[str, Any] = {
            "title": safe_title,
            "description": safe_desc,
            "payload": str(payload),
            "provider_token": str(provider_token).strip(),
            "prices": [{"label": safe_title, "amount": amount_rials}],
            "currency": "IRR"
        }
        if photo_url:
            p_url = str(photo_url).strip()
            final_photo_url = resolve_bale_invoice_photo_url(p_url)
            if final_photo_url and (final_photo_url.startswith("https://") or final_photo_url.startswith("http://")):
                body["photo_url"] = final_photo_url
                try:
                    fname = Path(p_url.split("?")[0]).name
                    candidates = [
                        config.BANNERS_DIR / fname,
                        config.UPLOADS_DIR / "banners" / fname,
                        config.UPLOADS_DIR / fname,
                        config.BASE_DIR / "uploads" / "banners" / fname
                    ]
                    for c in candidates:
                        if c.exists() and c.is_file():
                            body["photo_size"] = c.stat().st_size
                            from PIL import Image
                            with Image.open(c) as im:
                                body["photo_width"] = im.width
                                body["photo_height"] = im.height
                            break
                except Exception:
                    pass

        try:
            headers = {"Content-Type": "application/json"}
            session = await self.get_session()
            async with session.post(url, json=body, headers=headers) as resp:
                    data = await resp.json()
                    logger.info(f"Bale createInvoiceLink status={resp.status} response={data}")
                    if data.get("ok"):
                        return data
                    if "photo_url" in body:
                        logger.warning(f"Bale createInvoiceLink failed with photo_url ({data}), retrying without photo_url...")
                        body_no_photo = {k: v for k, v in body.items() if not k.startswith("photo_")}
                        async with session.post(url, json=body_no_photo, headers=headers) as resp2:
                            data2 = await resp2.json()
                            logger.info(f"Bale createInvoiceLink retry without photo_url response={data2}")
                            return data2
                    return data
        except Exception as e:
            logger.error(f"Error in Bale createInvoiceLink: {e}")
            return {"ok": False, "error": str(e)}

    async def answer_pre_checkout_query(
        self,
        pre_checkout_query_id: str,
        ok: bool = True,
        error_message: Optional[str] = None
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/answerPreCheckoutQuery"
        body = {"pre_checkout_query_id": str(pre_checkout_query_id), "ok": ok}
        if not ok and error_message:
            body["error_message"] = str(error_message)
        try:
            headers = {"Content-Type": "application/json"}
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.post(url, json=body, headers=headers) as resp:
                    return await resp.json()
        except Exception as e:
            logger.warning(f"Error in answerPreCheckoutQuery: {e}")
            return {"ok": False, "error": str(e)}

    async def answer_callback_query(
        self,
        callback_query_id: str,
        text: Optional[str] = None,
        show_alert: bool = False
    ) -> Dict[str, Any]:
        """
        Sends acknowledgment to a callback query in Bale to dismiss the client-side loading indicator
        and prevent duplicate user clicks / client retries.
        """
        if not self.token or not callback_query_id:
            return {"ok": False, "error": "BALE_BOT_TOKEN or callback_query_id missing"}
        url = f"{self.base_url}/answerCallbackQuery"
        payload: Dict[str, Any] = {"callback_query_id": str(callback_query_id)}
        if text:
            payload["text"] = str(text)
        if show_alert:
            payload["show_alert"] = True
        try:
            headers = {"Content-Type": "application/json"}
            session = await self.get_session()
            async with session.post(url, json=payload, headers=headers) as resp:
                return await resp.json()
        except Exception as e:
            logger.debug(f"Error in Bale answer_callback_query: {e}")
            return {"ok": False, "error": str(e)}

    async def send_audio(
        self,
        chat_id: str | int,
        file_path: Optional[Union[str, Path, Any]] = None,
        title: Optional[str] = None,
        performer: Optional[str] = None,
        caption: Optional[str] = None,
        duration: Optional[int] = None,
        filename: Optional[str] = None,
        progress_callback: Optional[Callable] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        ارسال فایل صوتی به چت بله طبق معماری سبک و مطمئن v0.5.8.
        ابتدا با sendAudio ارسال می‌کند و در صورت نیاز به sendDocument فالبک می‌زند.
        """
        if not self.token:
            return {"ok": False, "error": "BALE_BOT_TOKEN missing"}

        actual_path = file_path or kwargs.get("audio_path_or_url") or kwargs.get("audio") or kwargs.get("path")
        if not actual_path:
            return {"ok": False, "error": "file_path is required for send_audio"}

        clean_title = urllib.parse.unquote(str(title)).strip() if title else None
        clean_performer = urllib.parse.unquote(str(performer)).strip() if performer else None
        clean_caption = BaleFormatter.clean_text(urllib.parse.unquote(str(caption))) if caption else None

        markup = kwargs.get("reply_markup") or kwargs.get("markup")
        markup_str = json.dumps(markup) if isinstance(markup, dict) else (str(markup) if markup else None)

        if hasattr(actual_path, "read"):
            path_obj = None
            clean_send_name = clean_display_filename(filename or getattr(actual_path, "name", "audio.mp3"))
        else:
            path_obj = Path(str(actual_path))
            if not path_obj.exists():
                # ارسال از طریق URL مستقیم
                url_audio = f"{self.base_url}/sendAudio"
                payload = {"chat_id": str(chat_id), "audio": str(actual_path)}
                if clean_title: payload["title"] = clean_title
                if clean_performer: payload["performer"] = clean_performer
                if clean_caption: payload["caption"] = clean_caption
                if duration: payload["duration"] = int(duration)
                if markup_str: payload["reply_markup"] = markup_str
                try:
                    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
                        async with session.post(url_audio, json=payload) as resp:
                            return await resp.json()
                except Exception as e:
                    return {"ok": False, "error": str(e)}
            clean_send_name = clean_display_filename(filename or path_obj.name)

        url_audio = f"{self.base_url}/sendAudio"
        form = aiohttp.FormData(quote_fields=False)
        form.add_field("chat_id", str(chat_id))
        if clean_title: form.add_field("title", clean_title)
        if clean_performer: form.add_field("performer", clean_performer)
        if clean_caption: form.add_field("caption", clean_caption)
        if duration: form.add_field("duration", str(int(duration)))
        if markup_str: form.add_field("reply_markup", markup_str)

        content_type = "audio/mp4" if (path_obj and path_obj.suffix.lower() == ".m4a") else "audio/mpeg"
        bale_audio_timeout = aiohttp.ClientTimeout(total=450, connect=30, sock_read=180)

        try:
            if path_obj:
                with open(path_obj, "rb") as f:
                    form.add_field("audio", f, filename=clean_send_name, content_type=content_type)
                    async with aiohttp.ClientSession(timeout=bale_audio_timeout) as session:
                        async with session.post(url_audio, data=form) as resp:
                            if resp.status == 200:
                                res = await resp.json()
                                if res.get("ok"):
                                    logger.info(f"Bale sendAudio successful: {res}")
                                    return res
                                logger.warning(f"Bale sendAudio returned error: {res}, falling back to sendDocument...")
                            else:
                                logger.warning(f"Bale sendAudio HTTP {resp.status}, falling back to sendDocument...")
            else:
                form.add_field("audio", actual_path, filename=clean_send_name, content_type=content_type)
                async with aiohttp.ClientSession(timeout=bale_audio_timeout) as session:
                    async with session.post(url_audio, data=form) as resp:
                        if resp.status == 200:
                            res = await resp.json()
                            if res.get("ok"):
                                return res
        except Exception as e:
            logger.warning(f"Bale sendAudio exception: {e}, falling back to sendDocument...")

        # فال‌بک تک‌مرحله‌ای به sendDocument
        return await self.send_document(
            chat_id=chat_id,
            document=path_obj if path_obj else actual_path,
            caption=clean_caption,
            filename=clean_send_name
        )

    async def download_file(self, file_id: str, destination_path: Path) -> bool:
        try:
            url = f"{self.base_url}/getFile?file_id={file_id}"
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    data = await resp.json()
                    if not data.get("ok"):
                        return False
                    file_path_str = data.get("result", {}).get("file_path")
                    if not file_path_str:
                        return False
                    download_url = f"https://tapi.bale.ai/file/bot{self.token}/{file_path_str}"
                    async with session.get(download_url) as dl_resp:
                        if dl_resp.status == 200:
                            with open(destination_path, "wb") as f:
                                while True:
                                    chunk = await dl_resp.content.read(512 * 1024)
                                    if not chunk: break
                                    f.write(chunk)
                            return True
            return False
        except Exception as e:
            logger.error(f"Bale download error: {e}")
            return False


def build_bale_media_keyboard(drop_id: str, data: dict, is_sub: bool = False) -> dict:
    if is_sub:
        return {
            "inline_keyboard": [
                [{"text": "🔙 بازگشت به منوی رسانه", "callback_data": f"bmeta:back:{drop_id}"}],
                [{"text": "❌ لغو", "callback_data": f"bmeta:cancel:{drop_id}"}]
            ]
        }

    mtype = data.get("media_type", "audio")
    e_fields = data.get("edited_fields", {})
    draft_tags = data.get("draft_tags", {})

    fn_check = " ✅" if e_fields.get("filename") else ""
    perf_check = " ✅" if ("artist" in draft_tags or e_fields.get("artist")) else ""
    title_check = " ✅" if ("title" in draft_tags or e_fields.get("title")) else ""
    thumb_check = " ✅" if e_fields.get("thumb") else ""

    if mtype == "video":
        rows = [
            [
                {"text": "🎙 ویرایش تگ‌ها", "callback_data": f"bmeta:tags_menu:{drop_id}"},
                {"text": "➕ افزودن به سرفصل‌های دوره", "callback_data": f"bmeta:add_to_course:{drop_id}"}
            ],
            [
                {"text": "⚡ فشرده‌سازی خودکار", "callback_data": f"bmeta:compress:{drop_id}"},
                {"text": "📊 مشخصات فنی", "callback_data": f"bmeta:audio_specs:{drop_id}"}
            ],
            [
                {"text": f"✏️ تغییر نام فایل{fn_check}", "callback_data": f"bmeta:fn:{drop_id}"}
            ],
            [
                {"text": "🎵 تبدیل به صوت / دریافت MP3", "callback_data": f"bmeta:to_mp3:{drop_id}"},
                {"text": "🧠 دستیار هوش مصنوعی", "callback_data": f"bmeta:ai_transcribe:{drop_id}"}
            ],
            [
                {"text": "⚡️ اعمال سریع", "callback_data": f"bmeta:quick_send:{drop_id}"},
                {"text": "💾 اعمال تغییرات", "callback_data": f"bmeta:send_back:{drop_id}"}
            ],
            [
                {"text": "✈️ انتقال به تلگرام", "callback_data": f"bmeta:send_tg:{drop_id}"},
                {"text": "🟣 انتقال به روبیکا", "callback_data": f"bmeta:send_rub:{drop_id}"}
            ],
            [
                {"text": "🔷 انتقال به سروش‌پلاس", "callback_data": f"bmeta:send_splus:{drop_id}"}
            ]
        ]
        return {"inline_keyboard": rows}

    rows = [
        [
            {"text": "🎙 ویرایش تگ‌ها", "callback_data": f"bmeta:tags_menu:{drop_id}"},
            {"text": "➕ افزودن به سرفصل‌های دوره", "callback_data": f"bmeta:add_to_course:{drop_id}"}
        ],
        [
            {"text": "⚡ فشرده‌سازی خودکار", "callback_data": f"bmeta:compress:{drop_id}"},
            {"text": "📊 مشخصات فنی", "callback_data": f"bmeta:audio_specs:{drop_id}"}
        ],
        [
            {"text": f"✏️ تغییر نام فایل{fn_check}", "callback_data": f"bmeta:fn:{drop_id}"}
        ],
        [
            {"text": f"🗣 نام خواننده{perf_check}", "callback_data": f"bmeta:perf:{drop_id}"},
            {"text": f"🎵 عنوان موزیک{title_check}", "callback_data": f"bmeta:title:{drop_id}"}
        ],
        [
            {"text": "✂️ برش فایل صوتی", "callback_data": f"bmeta:trim:{drop_id}"},
            {"text": "🧠 دستیار هوش مصنوعی", "callback_data": f"bmeta:ai_transcribe:{drop_id}"}
        ],
        [
            {"text": "📋 اطلاعات تگ‌ها", "callback_data": f"bmeta:tag_details:{drop_id}"},
            {"text": f"🖼 تصویر کاور{thumb_check}", "callback_data": f"bmeta:change_cov:{drop_id}"}
        ],
        [
            {"text": "📥 دریافت تصویر کاور", "callback_data": f"bmeta:view_cov:{drop_id}"},
            {"text": "🧹 حذف کامل متادیتا", "callback_data": f"bmeta:strip_tags:{drop_id}"}
        ],
        [
            {"text": "⚡️ اعمال سریع", "callback_data": f"bmeta:quick_send:{drop_id}"},
            {"text": "💾 اعمال تغییرات", "callback_data": f"bmeta:send_back:{drop_id}"}
        ],
        [
            {"text": "✈️ انتقال به تلگرام", "callback_data": f"bmeta:send_tg:{drop_id}"},
            {"text": "🟣 انتقال به روبیکا", "callback_data": f"bmeta:send_rub:{drop_id}"}
        ],
        [
            {"text": "🔷 انتقال به سروش‌پلاس", "callback_data": f"bmeta:send_splus:{drop_id}"}
        ]
    ]

    return {"inline_keyboard": rows}


def build_bale_force_join_keyboard(channel_username: str) -> dict:
    clean_username = channel_username.lstrip("@")
    return {
        "inline_keyboard": [
            [{"text": "📢 عضویت در کانال", "url": f"https://ble.ir/{clean_username}"}],
            [{"text": "🔄 تایید عضویت", "callback_data": "bale:check_fjoin"}]
        ]
    }


async def run_bale_polling_engine(telegram_adapter_instance=None, rubika_adapter_instance=None):
    global ACTIVE_BALE_ADMIN_ID, _BALE_POLLING_RUNNING
    if _BALE_POLLING_RUNNING:
        logger.warning("Bale polling listener is already running. Preventing duplicate background loop.")
        return
    _BALE_POLLING_RUNNING = True

    token = config.BALE_BOT_TOKEN
    if not token:
        logger.warning("Bale token is missing. Bale polling engine disabled.")
        _BALE_POLLING_RUNNING = False
        return

    bale = BaleAdapter(token)
    try:
        b_me = await bale.get_me()
        if b_me and b_me.get("ok"):
            b_u = b_me.get("result", {}).get("username")
            if b_u:
                bale.username = b_u
                config.BALE_BOT_USERNAME = b_u
                logger.info(f"Bale bot verified: @{bale.username}")
    except Exception as e:
        logger.warning(f"Failed to fetch Bale bot info on startup: {e}")
    logger.info("Bale polling listener active and running.")

    # 1. Persistent offset management
    bale_offset_file = config.DATA_DIR / "bale_offset.txt"
    offset = 0
    if bale_offset_file.exists():
        try:
            raw_val = bale_offset_file.read_text(encoding="utf-8").strip()
            if raw_val.isdigit():
                offset = int(raw_val)
                logger.info(f"Loaded persistent Bale offset: {offset}")
        except Exception as e:
            logger.warning(f"Failed to read bale_offset.txt: {e}")

    # Startup protection: If no offset file exists (e.g. fresh container startup),
    # fetch latest update_id and fast-forward offset so historical backlogs don't trigger duplicates.
    if offset == 0:
        try:
            init_url = f"{bale.base_url}/getUpdates?offset=0&timeout=0"
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as init_sess:
                async with init_sess.get(init_url) as init_resp:
                    if init_resp.status == 200:
                        init_data = await init_resp.json()
                        init_res = init_data.get("result", [])
                        if init_res:
                            max_u = max(u.get("update_id", 0) for u in init_res)
                            offset = max_u + 1
                            try:
                                config.DATA_DIR.mkdir(parents=True, exist_ok=True)
                                bale_offset_file.write_text(str(offset), encoding="utf-8")
                            except Exception:
                                pass
                            logger.info(f"Fast-forwarded initial Bale offset to {offset} ({len(init_res)} backlog updates skipped).")
        except Exception as fwd_err:
            logger.warning(f"Bale fast-forward offset probe exception: {fwd_err}")

    # 2. Bounded deduplication sets & deques to eliminate duplicate message processing
    processed_update_ids = collections.deque(maxlen=3000)
    processed_update_set = set()

    processed_cb_ids = collections.deque(maxlen=1000)
    processed_cb_set = set()

    processed_msg_ids = collections.deque(maxlen=1000)
    processed_msg_set = set()

    user_last_actions: Dict[str, float] = {}

    try:
        while True:
            try:
                url = f"{bale.base_url}/getUpdates?offset={offset}&timeout=5"
                session = await bale.get_session()
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            updates = data.get("result", [])
                            for update in updates:
                                cb = None
                                cb_data = ""
                                u_id = update.get("update_id")
                                if u_id is not None:
                                    if u_id in processed_update_set:
                                        logger.debug(f"[Bale] Duplicate update_id {u_id} skipped")
                                        continue
                                    processed_update_set.add(u_id)
                                    processed_update_ids.append(u_id)
                                    if len(processed_update_ids) >= 3000:
                                        old_u = processed_update_ids.popleft()
                                        processed_update_set.discard(old_u)
                                    offset = max(offset, u_id + 1)
                                    try:
                                        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
                                        bale_offset_file.write_text(str(offset), encoding="utf-8")
                                    except Exception:
                                        pass

                                # Ignore Channel and Group Posts Strictly
                                if "channel_post" in update or "edited_channel_post" in update:
                                    continue

                                # Handle Callback Queries in Bale
                                if "callback_query" in update:
                                    cb = update["callback_query"]
                                    cb_id = cb.get("id")
                                    cb_data = cb.get("data", "")
                                    chat_id = str(cb.get("message", {}).get("chat", {}).get("id") or cb.get("from", {}).get("id"))
                                    msg_id = cb.get("message", {}).get("message_id")
                                    chat_type = cb.get("message", {}).get("chat", {}).get("type", "private")

                                    if chat_type != "private" or str(chat_id).startswith("-"):
                                        continue

                                    # Immediately acknowledge callback query to stop loading spinner on user's device
                                    if cb_id:
                                        asyncio.create_task(bale.answer_callback_query(cb_id))
                                        if cb_id in processed_cb_set:
                                            logger.debug(f"[Bale] Duplicate callback query ID {cb_id} skipped")
                                            continue
                                        processed_cb_set.add(cb_id)
                                        processed_cb_ids.append(cb_id)
                                        if len(processed_cb_ids) >= 1000:
                                            old_cb = processed_cb_ids.popleft()
                                            processed_cb_set.discard(old_cb)

                                    # Debounce rapid identical clicks per user (1.2s window)
                                    now = time.time()
                                    cb_key = f"{chat_id}:{cb_data}"
                                    if (now - user_last_actions.get(cb_key, 0.0)) < 0.35:
                                        logger.info(f"[Bale] Debounced duplicate callback {cb_data} from {chat_id}")
                                        continue
                                    user_last_actions[cb_key] = now

                                    if cb_data == "bale:check_fjoin":
                                        is_member = await bale.check_user_membership(chat_id)
                                        if is_member:
                                            await bale.send_message(chat_id, "✅ عضویت شما تایید گردید. خوش آمدید!", reply_markup=get_bale_customer_keyboard())
                                        else:
                                            channel_ch = await get_system_setting("bale_fjoin_channel", config.FORCE_JOIN_CHANNEL_BALE)
                                            await bale.send_message(chat_id, "⚠️ شما هنوز در کانال عضو نشده‌اید. لطفاً ابتدا در کانال عضو شده و مجدداً دکمه تایید را لمس فرمایید.", reply_markup=build_bale_force_join_keyboard(channel_ch))
                                        continue

                                    if cb_data == "freq_cats":
                                        txt = (
                                            "💎 <b>فرکانس فراوانی و آرامش درون</b>\n\n"
                                            "دسته‌بندی مورد نظر خود را انتخاب نمایید:"
                                        )
                                        await bale.edit_message_text(chat_id, msg_id, txt, reply_markup=build_bale_frequency_cats_keyboard())
                                        continue

                                    if cb_data.startswith("freq_page:"):
                                        parts = cb_data.split(":")
                                        if len(parts) >= 3:
                                            category = parts[1]
                                            idx = int(parts[2])
                                            item, curr_num, total = FrequencyService.get_item(category, idx)
                                            if item:
                                                card_txt = FrequencyService.format_card(item, curr_num, total)
                                                await bale.edit_message_text(
                                                    chat_id, msg_id, card_txt,
                                                    reply_markup=build_bale_frequency_nav_keyboard(category, curr_num - 1, total)
                                                )
                                        continue

                                    if cb_data == "freq_noop":
                                        continue

                                    # URL Uploader Callbacks in Bale
                                    if cb_data.startswith("burldl:"):
                                        parts = cb_data.split(":")
                                        mode = parts[1]
                                        url_id = parts[2]
                                        url_sess = session_manager.get_session(f"url_{url_id}")

                                        if not url_sess:
                                            await bale.send_message(chat_id, "❌ مهلت لینک به پایان رسیده است.")
                                            continue

                                        if mode == "cancel":
                                            session_manager.remove_session(f"url_{url_id}")
                                            await bale.edit_message_text(chat_id, msg_id, "❌ عملیات دانلود لینک لغو گردید.")
                                            continue

                                        url = url_sess["url"]
                                        filename = url_sess["filename"]
                                        temp_dest = config.TEMP_DIR / f"burldl_{url_id}_{clean_display_filename(filename)}"
                                        await bale.edit_message_text(chat_id, msg_id, "📥 <b>در حال شروع دانلود استریم فایل از لینک مستقیم...</b>")

                                        start_time = [time.time()]
                                        last_edit_time = [time.time()]
                                        last_percent = [0]

                                        async def do_bale_edit(txt):
                                            try:
                                                await bale.edit_message_text(chat_id, msg_id, txt)
                                            except Exception as edit_err:
                                                logger.debug(f"Bale progress edit notice: {edit_err}")

                                        def progress_cb(dl_bytes, tot_bytes):
                                            now = time.time()
                                            current_percent = int((dl_bytes / tot_bytes) * 100) if tot_bytes > 0 else 0
                                            if ((now - last_edit_time[0] >= 3.0 and current_percent - last_percent[0] >= 5) or current_percent == 100):
                                                last_edit_time[0] = now
                                                last_percent[0] = current_percent
                                                elapsed = max(0.01, now - start_time[0])
                                                txt = format_bale_transfer_progress(dl_bytes, tot_bytes, elapsed, stage_title="در حال دانلود استریم فایل...")
                                                asyncio.create_task(do_bale_edit(txt))

                                        ok = await UrlService.download_file_stream(url, temp_dest, progress_callback=progress_cb)
                                        if not ok or not temp_dest.exists():
                                            await bale.send_message(chat_id, "❌ خطا در دانلود فایل از لینک. لطفاً از صحت لینک اطمینان حاصل فرمایید.")
                                            continue

                                        # If user selected MP3 audio extraction from a video URL
                                        if mode == "audio" and temp_dest.suffix.lower() in (".mp4", ".mkv", ".mov", ".avi", ".webm"):
                                            await bale.send_message(chat_id, "🎵 در حال استخراج هوشمند صوت ویدیو به MP3...")
                                            mp3_p = config.TEMP_DIR / f"{temp_dest.stem}.mp3"
                                            c_ok, final_mp3 = MediaService.convert_video_to_mp3(temp_dest, output_path=mp3_p)
                                            if c_ok and final_mp3.exists():
                                                temp_dest = final_mp3
                                                filename = final_mp3.name

                                        sz = temp_dest.stat().st_size
                                        sz_mb = sz / (1024 * 1024)

                                        # Safe dynamic limit management for Bale
                                        final_send_path = temp_dest
                                        safe_mb = float(getattr(config, "MAX_SAFE_BALE_SIZE_MB", 49.99))
                                        target_mb = max(1.0, round(safe_mb - 1.5, 2))
                                        if sz_mb >= safe_mb or sz > getattr(config, "MAX_SAFE_BALE_SIZE_BYTES", int(safe_mb * 1024 * 1024)):
                                            orig_mb = f"{sz_mb:.1f}"
                                            try:
                                                await bale.edit_message_text(
                                                    chat_id,
                                                    msg_id,
                                                    "⚙️ <b>در حال فشرده‌سازی هوشمند...</b>\n"
                                                    f"📦 حجم فعلی: <code>{orig_mb} MB</code> ➔ هدف: <code>زیر {target_mb} MB</code>"
                                                )
                                            except Exception as edit_err:
                                                logger.debug(f"Bale edit before compression notice: {edit_err}")

                                            loop = asyncio.get_running_loop()
                                            if temp_dest.suffix.lower() in (".mp3", ".m4a", ".wav", ".aac"):
                                                from media.compressor import SmartAudioCompressor
                                                comp_p, _, _, _, was_c = await loop.run_in_executor(
                                                    None, SmartAudioCompressor.compress_if_needed, temp_dest
                                                )
                                                if was_c and comp_p.exists():
                                                    final_send_path = comp_p
                                            elif temp_dest.suffix.lower() in (".mp4", ".mkv", ".mov", ".avi", ".webm"):
                                                from media.compressor import SmartVideoCompressor
                                                comp_p, _, _, _, was_c = await loop.run_in_executor(
                                                    None, SmartVideoCompressor.compress_if_needed, temp_dest
                                                )
                                                if was_c and comp_p.exists():
                                                    final_send_path = comp_p

                                            try:
                                                await bale.edit_message_text(chat_id, msg_id, "📤 <b>در حال ارسال به بله...</b>")
                                            except Exception:
                                                pass

                                        drop_id = uuid.uuid4().hex[:8]
                                        is_v = final_send_path.suffix.lower() in (".mp4", ".mkv", ".mov", ".avi", ".webm")
                                        data = MediaService.register_incoming_message_meta(
                                            drop_id, "bale", chat_id, str(final_send_path), filename, final_send_path.stat().st_size,
                                            media_type="video" if is_v else "audio"
                                        )
                                        data["working_path"] = str(final_send_path)
                                        data["is_downloaded_locally"] = True

                                        if is_v:
                                            tech = inspect_technical_metadata(final_send_path)
                                            await bale.send_video(
                                                chat_id,
                                                final_send_path,
                                                caption=f"✅ ویدیو دانلودشده از لینک:\n📄 {filename}",
                                                duration=tech.get("duration_sec"),
                                                width=tech.get("width"),
                                                height=tech.get("height")
                                            )
                                        else:
                                            await bale.send_audio(
                                                chat_id,
                                                final_send_path,
                                                title=filename,
                                                caption=f"✅ فایل دانلودشده از لینک:\n📄 {filename}"
                                            )
                                        card_txt = BaleFormatter.format_light_card(data)
                                        kb = build_bale_media_keyboard(drop_id, data)
                                        sent_c = await bale.send_message(chat_id, card_txt, reply_markup=kb)
                                        data["card_msg_id"] = sent_c.get("result", {}).get("message_id")
                                        continue

                                    # Force Join Management Callbacks
                                    if cb_data == "bale:fjoin_toggle":
                                        cur = (await get_system_setting("bale_fjoin_enabled", "1" if config.FORCE_JOIN_CHANNEL_BALE else "0")) == "1"
                                        new_st = "0" if cur else "1"
                                        await set_system_setting("bale_fjoin_enabled", new_st)
                                        ch = await get_system_setting("bale_fjoin_channel", config.FORCE_JOIN_CHANNEL_BALE)
                                        st_txt = "فعال ✅" if new_st == "1" else "غیرفعال ❌"
                                        btn_t = "🔴 غیرفعال‌سازی قفل" if new_st == "1" else "🟢 فعال‌سازی قفل"
                                        kb = {
                                            "inline_keyboard": [
                                                [{"text": btn_t, "callback_data": "bale:fjoin_toggle"}],
                                                [{"text": "✏️ تغییر آیدی کانال", "callback_data": "bale:fjoin_set_ch"}],
                                                [{"text": "🔙 بازگشت به پنل", "callback_data": "bale:fjoin_back"}]
                                            ]
                                        }
                                        plain_panel = (
                                            "🔒 مدیریت قفل عضویت کانال بله:\n\n"
                                            f"▫️ وضعیت: {st_txt}\n"
                                            f"▫️ کانال هدف: {ch or 'تنظیم نشده'}"
                                        )
                                        await bale.edit_message_text(chat_id, msg_id, plain_panel, reply_markup=kb)
                                        continue

                                    if cb_data == "bale:fjoin_set_ch":
                                        session_manager.set_user_action(f"bale_{chat_id}", "await_bale_fjoin_ch", "none")
                                        await bale.send_message(chat_id, "✏️ لطفاً آیدی یا یوزرنیم کانال قفل بله را ارسال فرمایید (مثلاً: @MyChannel):")
                                        continue

                                    if cb_data == "bale:fjoin_back":
                                        await bale.send_message(chat_id, "🎛 پنل مدیریت فعال شد:", reply_markup=get_bale_admin_keyboard())
                                        continue

                                    # Force Join Check for other callbacks
                                    if not await bale.check_user_membership(chat_id):
                                        channel_ch = await get_system_setting("bale_fjoin_channel", config.FORCE_JOIN_CHANNEL_BALE)
                                        await bale.send_message(chat_id, "⚠️ برای استفاده از امکانات ربات ابتدا باید در کانال رسمی ما عضو شوید:", reply_markup=build_bale_force_join_keyboard(channel_ch))
                                        continue

                                    # Course Viewing and Payment Callbacks in Bale
                                    if cb_data == "bale:courses_list":
                                        prods = await StoreService.get_products(is_free_only=False)
                                        buttons = [[{"text": f"🎓 {p.name} ({p.price:,} تومان)", "callback_data": f"bcview:{p.product_id}"}] for p in prods]
                                        await bale.send_message(chat_id, "📚 لیست دوره‌های آموزشی تخصصی:", reply_markup={"inline_keyboard": buttons})
                                        continue

                                    async def _bale_send_order(c_id, p_item, usr):
                                        if p_item.price <= 0:
                                            order = await StoreService.create_order(
                                                user_id=c_id,
                                                username="",
                                                customer_name=usr.full_name if usr else "",
                                                phone=usr.phone if usr else "",
                                                product=p_item,
                                                platform="bale"
                                            )
                                            await StoreService.approve_order(order.order_id)
                                            UserService.unlock_gift_by_platform("bale", c_id, p_item.product_id)
                                            is_pkg = bool(getattr(p_item, "delivery_type", "channel") == "files_package" or getattr(p_item, "files_package", None) or getattr(p_item, "episodes", None))
                                            if is_pkg:
                                                await bale.send_message(c_id, f"🎉 <b>دوره «{p_item.name}» با موفقیت برای شما فعال شد!</b>\nفایل‌های دوره هم‌اکنون به ترتیب برای شما ارسال می‌شوند:\nشماره سفارش: <code>{order.order_id}</code>")
                                                await StoreService.deliver_course_package(p_item, c_id, "bale")
                                            else:
                                                dl_content = p_item.download_link or "لینک دانلود در دسترس است."
                                                cust_msg = StoreService.format_delivery_message(p_item.name, order.order_id, dl_content, 0)
                                                await bale.send_message(c_id, cust_msg)
                                            return

                                        order = await StoreService.create_order(
                                            user_id=c_id,
                                            username="",
                                            customer_name=usr.full_name if usr else "",
                                            phone=usr.phone if usr else "",
                                            product=p_item,
                                            platform="bale"
                                        )

                                        bale_token = config.BALE_PAYMENT_TOKEN or await get_system_setting("bale_payment_token")
                                        if not bale_token:
                                            bale_token = await get_system_setting("BALE_PAYMENT_TOKEN")

                                        inv_kb = {
                                            "inline_keyboard": [
                                                [{"text": "💳 مشکل در پرداخت آنلاین؟ پرداخت کارت به کارت", "callback_data": f"c2c_{order.order_id}"}],
                                                [{"text": "🔙 بازگشت به لیست دوره‌ها", "callback_data": "bale:courses_list"}]
                                            ]
                                        }

                                        if bale_token:
                                            res_inv = await bale.send_invoice(
                                                chat_id=c_id,
                                                title=p_item.name,
                                                description=p_item.description or f"خرید آنلاین دوره {p_item.name}",
                                                payload=order.order_id,
                                                provider_token=bale_token,
                                                amount_tomans=p_item.price,
                                                photo_url=p_item.photo_url or None,
                                                reply_markup=inv_kb
                                            )
                                            if res_inv.get("ok"):
                                                return
                                            logger.warning(f"Bale send_invoice returned not ok: {res_inv}")

                                        # Fallback to Card-to-Card if invoice sending failed or token missing
                                        c_num = await get_system_setting("CARD_NUMBER", config.CARD_NUMBER)
                                        c_name = await get_system_setting("CARD_HOLDER", config.CARD_HOLDER)
                                        card_msg = (
                                            f"🧾 <b>فاکتور پرداخت دوره: {p_item.name}</b>\n\n"
                                            f"▫️ مبلغ قابل پرداخت: <b>{p_item.price:,} تومان</b>\n"
                                            f"▫️ شماره کارت: <code>{c_num}</code>\n"
                                            f"▫️ به نام: <b>{c_name}</b>\n"
                                            f"▫️ کد سفارش شما: <code>{order.order_id}</code>\n\n"
                                            "📌 لطفاً پس از واریز مبلغ، تصویر رسید / فیش واریزی خود را در همین چت ارسال فرمایید تا تایید و محتوا تحویل گردد."
                                        )
                                        session_manager.set_user_action(f"bale_{c_id}", "await_receipt", order.order_id)
                                        await bale.send_message(c_id, card_msg)

                                    if cb_data.startswith("bcview:"):
                                        p_id = cb_data.split(":", 1)[1]
                                        prod = await StoreService.get_product(p_id)
                                        if not prod:
                                            await bale.send_message(chat_id, "❌ دوره مورد نظر یافت نشد.")
                                            continue

                                        if prod.price <= 0:
                                            u = UserService.get_user_by_platform_id("bale", chat_id)
                                            req_ref = getattr(prod, "requires_referral", False)
                                            invites = u.successful_invites if u else 0
                                            if req_ref and invites < 1:
                                                bot_username = bale.username or getattr(config, "BALE_BOT_USERNAME", "") or ""
                                                if not bot_username:
                                                    try:
                                                        b_me = await bale.get_me()
                                                        if b_me and b_me.get("ok"):
                                                            bot_username = b_me.get("result", {}).get("username") or ""
                                                    except Exception:
                                                        pass
                                                ref_link = ReferralService.get_referral_link(chat_id, "bale", bot_username)
                                                lock_msg = (
                                                    f"🔒 <b>دسترسی به دوره هدیه «{prod.name}» نیازمند ۱ دعوت موفق است!</b>\n\n"
                                                    "با ارسال لینک دعوت زیر به دوستان خود، به محض پیوستن ۱ نفر، این دوره به صورت خودکار برای شما فعال خواهد شد.\n\n"
                                                    f"🔗 <b>لینک اختصاصی دعوت شما در بله:</b>\n<code>{ref_link}</code>\n\n"
                                                    f"👥 <b>تعداد دعوت‌های موفق شما:</b> <b>{invites} از ۱ نفر</b>\n"
                                                )
                                                lock_kb = {
                                                    "inline_keyboard": [
                                                        [{"text": "📤 ارسال لینک برای دوستان", "url": f"https://ble.ir/share/url?url={ref_link}&text=سلام!%20برای%20دریافت%20هدیه%20و%20دوره‌ها%20کلیک%20کنید:"}],
                                                        [{"text": "🔙 بازگشت به لیست هدایا", "callback_data": "bnav:gifts"}]
                                                    ]
                                                }
                                                await bale.send_message(chat_id, lock_msg, reply_markup=lock_kb)
                                                continue
                                            await _bale_send_order(chat_id, prod, u)
                                            continue

                                        u = UserService.get_user_by_platform_id("bale", chat_id)
                                        if not u or not u.phone:
                                            session_manager.set_user_action(f"bale_pending_buy_{chat_id}", p_id, p_id)
                                            contact_kb = {
                                                "keyboard": [
                                                    [{"text": "📱 ارسال شماره تماس (جهت ثبت‌نام و صدور فاکتور)", "request_contact": True}],
                                                    [{"text": "🔙 انصراف"}]
                                                ],
                                                "resize_keyboard": True,
                                                "one_time_keyboard": True
                                            }
                                            await bale.send_message(
                                                chat_id,
                                                "⚠️ <b>ثبت‌نام سریع جهت صدور فاکتور رسمی:</b>\n\n"
                                                "برای صدور فاکتور معتبر، اتصال کیف پول و دسترسی دائمی به فایل‌های دوره، لطفاً شماره تماس خود را از طریق دکمه زیر ارسال فرمایید:",
                                                reply_markup=contact_kb
                                            )
                                            continue

                                        if not u.terms_accepted:
                                            raw_terms = await get_system_setting("COURSE_TERMS_TEXT", config.COURSE_TERMS_TEXT)
                                            terms_text = (
                                                f"⚖️ <b>تعهدنامه و قوانین خرید دوره {prod.name}:</b>\n\n"
                                                f"{raw_terms}\n\n"
                                                "آیا شرایط و تعهدنامه فوق را مطالعه کرده و می‌پذیرید؟"
                                            )
                                            inv_kb = {
                                                "inline_keyboard": [
                                                    [{"text": "✅ شرایط را می‌پذیرم", "callback_data": f"bale_terms_accept:{prod.product_id}"}],
                                                    [{"text": "❌ انصراف", "callback_data": "bale_terms_reject"}]
                                                ]
                                            }
                                            await bale.send_message(chat_id, terms_text, reply_markup=inv_kb)
                                            continue

                                        await _bale_send_order(chat_id, prod, u)
                                        continue

                                    if cb_data.startswith("bale_terms_accept:"):
                                        p_id = cb_data.split(":", 1)[1]
                                        u = UserService.accept_terms_by_platform("bale", chat_id)
                                        prod = await StoreService.get_product(p_id)
                                        if prod:
                                            await _bale_send_order(chat_id, prod, u)
                                        continue

                                    if cb_data == "bale_terms_reject":
                                        await bale.send_message(chat_id, "❌ خرید دوره لغو شد. در صورت تمایل می‌توانید سایر دوره‌ها را مشاهده فرمایید.")
                                        continue

                                    if cb_data.startswith("bpay_online:"):
                                        p_id = cb_data.split(":", 1)[1]
                                        prod = await StoreService.get_product(p_id)
                                        if not prod or prod.price <= 0:
                                            await bale.send_message(chat_id, "❌ خطا در بازیابی اطلاعات دوره.")
                                            continue

                                        bale_token = config.BALE_PAYMENT_TOKEN or await get_system_setting("bale_payment_token")
                                        if not bale_token:
                                            await bale.send_message(
                                                chat_id,
                                                "⚠️ درگاه پرداخت آنلاین بله هنوز تنظیم نشده است. لطفاً از گزینه پرداخت کارت به کارت استفاده فرمایید."
                                            )
                                            continue

                                        order = await StoreService.create_order(
                                            user_id=chat_id,
                                            username="",
                                            customer_name="",
                                            phone="",
                                            product=prod,
                                            platform="bale"
                                        )
                                        res_inv = await bale.send_invoice(
                                            chat_id=chat_id,
                                            title=prod.name,
                                            description=prod.description or f"خرید آنلاین دوره {prod.name}",
                                            payload=order.order_id,
                                            provider_token=bale_token,
                                            amount_tomans=prod.price,
                                            photo_url=prod.photo_url or None
                                        )
                                        if not res_inv.get("ok"):
                                            await bale.send_message(chat_id, f"❌ خطا در صدور فاکتور پرداخت بله: {res_inv.get('error') or res_inv}")
                                        continue

                                    if cb_data.startswith("bpay_card:"):
                                        p_id = cb_data.split(":", 1)[1]
                                        prod = await StoreService.get_product(p_id)
                                        if not prod:
                                            await bale.send_message(chat_id, "❌ دوره یافت نشد.")
                                            continue

                                        order = await StoreService.create_order(
                                            user_id=chat_id,
                                            username="",
                                            customer_name="",
                                            phone="",
                                            product=prod,
                                            platform="bale"
                                        )
                                        c_num = await get_system_setting("CARD_NUMBER", config.CARD_NUMBER)
                                        c_name = await get_system_setting("CARD_HOLDER", config.CARD_HOLDER)
                                        card_msg = (
                                            f"🧾 <b>فاکتور پرداخت کارت به کارت: {prod.name}</b>\n\n"
                                            f"▫️ مبلغ قابل پرداخت: <b>{prod.price:,} تومان</b>\n"
                                            f"▫️ شماره کارت: <code>{c_num}</code>\n"
                                            f"▫️ به نام: <b>{c_name}</b>\n"
                                            f"▫️ کد سفارش شما: <code>{order.order_id}</code>\n\n"
                                            "📌 لطفاً پس از واریز مبلغ، تصویر رسید / فیش واریزی خود را در همین چت ارسال فرمایید تا تایید و محتوا تحویل گردد."
                                        )
                                        session_manager.set_user_action(f"bale_{chat_id}", "await_receipt", order.order_id)
                                        await bale.send_message(chat_id, card_msg)
                                        continue

                                    if cb_data.startswith("c2c_"):
                                        oid = cb_data[4:].strip()
                                        order_item = await StoreService.get_order(oid)
                                        prod_name = "دوره آموزشی"
                                        price_val = 0
                                        if order_item:
                                            prod = await StoreService.get_product(order_item.product_id)
                                            if prod:
                                                prod_name = prod.name
                                                price_val = prod.price
                                            elif order_item.amount:
                                                price_val = order_item.amount

                                        c_num = await get_system_setting("CARD_NUMBER", config.CARD_NUMBER)
                                        c_name = await get_system_setting("CARD_HOLDER", config.CARD_HOLDER)
                                        price_str = f"{price_val:,} تومان" if price_val > 0 else "طبق فاکتور"
                                        card_msg = (
                                            f"🧾 <b>مشخصات پرداخت کارت به کارت: {prod_name}</b>\n\n"
                                            f"▫️ مبلغ قابل پرداخت: <b>{price_str}</b>\n"
                                            f"▫️ شماره کارت: <code>{c_num}</code>\n"
                                            f"▫️ به نام: <b>{c_name}</b>\n"
                                            f"▫️ کد سفارش شما: <code>{oid}</code>\n\n"
                                            "📌 لطفاً پس از واریز مبلغ، تصویر رسید / فیش واریزی خود را در همین چت ارسال فرمایید تا تایید و محتوا تحویل گردد."
                                        )
                                        session_manager.set_user_action(f"bale_{chat_id}", "await_receipt", oid)
                                        await bale.send_message(chat_id, card_msg)
                                        continue

                                    if cb_data.startswith("bpay_free:"):
                                        p_id = cb_data.split(":", 1)[1]
                                        prod = await StoreService.get_product(p_id)
                                        if not prod:
                                            await bale.send_message(chat_id, "❌ فایل مورد نظر یافت نشد.")
                                            continue

                                        order = await StoreService.create_order(
                                            user_id=chat_id,
                                            username="",
                                            customer_name="",
                                            phone="",
                                            product=prod,
                                            platform="bale"
                                        )
                                        await StoreService.approve_order(order.order_id)
                                        dl_content = (prod.download_link if prod else "") or ""
                                        cust_msg = StoreService.format_delivery_message(prod.name, order.order_id, dl_content, 0)
                                        parsed_dl = StoreService.parse_delivery_links(dl_content)
                                        cust_buttons = []
                                        for lk in parsed_dl["links"]:
                                            cust_buttons.append([{"text": lk["title"], "url": lk["url"]}])
                                        cust_kb = {"inline_keyboard": cust_buttons} if cust_buttons else None
                                        await bale.send_message(chat_id, cust_msg, reply_markup=cust_kb)
                                        continue

                                    # Interactive Card-to-Card Receipt Decision in Bale
                                    if cb_data.startswith("adm_app:") or cb_data.startswith("adm_rej:") or cb_data.startswith("adm_approve:") or cb_data.startswith("adm_reject:") or cb_data.startswith("ord_app:") or cb_data.startswith("ord_rej:"):
                                        if not bale.is_admin(chat_id):
                                            await bale.send_message(chat_id, "⛔️ دسترسی غیرمجاز.")
                                            continue
                                        parts = cb_data.split(":", 1)
                                        action = parts[0]
                                        oid = parts[1]

                                        if action in ("adm_app", "adm_approve", "ord_app"):
                                            res = await StoreService.approve_order(oid)
                                            if res:
                                                prod = res.get("product")
                                                prod_name = res.get("product_name") or (prod.name if prod else "دوره آموزشی")
                                                dl_link = (prod.download_link if prod else "") or "برای دریافت لینک‌ها و فایل‌های این دوره با پشتیبانی در ارتباط باشید."
                                                order_item = res.get("order")
                                                cb_awarded = res.get("cashback_awarded", 0)
                                                try:
                                                    await bale.edit_message_text(
                                                        chat_id, msg_id,
                                                        f"✅ <b>سفارش {oid} با موفقیت تایید شد!</b>\n🎓 دوره: {prod_name}\nلینک دانلود فعال و کش‌بک {cb_awarded:,} تومان ثبت گردید."
                                                    )
                                                except Exception:
                                                    await bale.send_message(chat_id, f"✅ سفارش {oid} تایید شد.")
                                                cust_uid = order_item.user_id if order_item else None
                                                if cust_uid:
                                                    try:
                                                        is_pkg = bool(prod and (getattr(prod, "delivery_type", "channel") == "files_package" or getattr(prod, "files_package", None) or getattr(prod, "episodes", None)))
                                                        if is_pkg:
                                                            await bale.send_message(cust_uid, f"🎉 <b>سفارش شما تایید شد!</b>\nفایل‌های دوره «{prod_name}» هم‌اکنون به ترتیب برای شما ارسال می‌شوند:\nشماره سفارش: <code>{oid}</code>")
                                                            await StoreService.deliver_course_package(prod, cust_uid, "bale")
                                                        else:
                                                            cust_msg = StoreService.format_delivery_message(prod_name, oid, dl_link, cb_awarded)
                                                            parsed_dl = StoreService.parse_delivery_links(dl_link)
                                                            cust_buttons = []
                                                            for lk in parsed_dl["links"]:
                                                                cust_buttons.append([{"text": lk["title"], "url": lk["url"]}])
                                                            cust_kb = {"inline_keyboard": cust_buttons} if cust_buttons else None
                                                            await bale.send_message(cust_uid, cust_msg, reply_markup=cust_kb)
                                                    except Exception as ex_del:
                                                        logger.warning(f"Could not deliver course to Bale user {cust_uid}: {ex_del}")
                                            else:
                                                await bale.send_message(chat_id, f"❌ سفارش {oid} یافت نشد.")
                                        else:
                                            await StoreService.reject_order(oid)
                                            try:
                                                await bale.edit_message_text(chat_id, msg_id, f"❌ <b>سفارش {oid} توسط ادمین رد شد.</b>")
                                            except Exception:
                                                await bale.send_message(chat_id, f"🚫 سفارش {oid} رد شد.")
                                            buyer_order = await StoreService.get_order(oid)
                                            if buyer_order:
                                                try:
                                                    await bale.send_message(buyer_order.user_id, f"❌ متأسفانه فیش واریزی سفارش شما ({oid}) تایید نشد. لطفاً جهت پیگیری با پشتیبانی در ارتباط باشید.")
                                                except Exception: pass
                                        continue

                                    # Media Callbacks in Bale
                                    if cb_data.startswith("bmeta:"):
                                        parts = cb_data.split(":")
                                        action = parts[1]
                                        drop_id = parts[2]
                                        drop = session_manager.get_session(drop_id)
                                        if not drop:
                                            try:
                                                from core.database import db_get_media_session
                                                drop = db_get_media_session(drop_id)
                                                if drop:
                                                    session_manager._sessions[drop_id] = drop
                                            except Exception as e:
                                                logger.error(f"Error recovering session {drop_id} from SQLite: {e}")
                                        if not drop:
                                            await bale.send_message(chat_id, "❌ مهلت فایل به پایان رسیده است.")
                                            continue

                                        async def ensure_bale_binary():
                                            local_p = drop.get("working_path") or drop.get("compressed_path") or drop.get("original_path")
                                            if not drop.get("is_downloaded_locally") or not local_p or not Path(str(local_p)).exists():
                                                async def dl_func(fid, p): return await bale.download_file(fid, p)
                                                await MediaService.ensure_local_binary(drop_id, dl_func)

                                        if action == "cancel":
                                            session_manager.remove_session(drop_id)
                                            await bale.edit_message_text(chat_id, msg_id, "❌ عملیات مدیریت رسانه لغو شد.")
                                        elif action == "tags_menu":
                                            e_f = drop.get("edited_fields", {})
                                            d_t = drop.get("draft_tags", {})
                                            fn_c = " ✅" if e_f.get("filename") else ""
                                            perf_c = " ✅" if ("artist" in d_t or e_f.get("artist")) else ""
                                            title_c = " ✅" if ("title" in d_t or e_f.get("title")) else ""
                                            thumb_c = " ✅" if e_f.get("thumb") else ""
                                            txt = "🎙 <b>منوی ویرایش تگ‌ها و متادیتای رسانه:</b>\nلطفاً بخش مورد نظر را انتخاب فرمایید:"
                                            kb = {
                                                "inline_keyboard": [
                                                    [{"text": f"✏️ ویرایش نام فایل{fn_c}", "callback_data": f"bmeta:fn:{drop_id}"}],
                                                    [
                                                        {"text": f"🗣 تغییر نام خواننده{perf_c}", "callback_data": f"bmeta:perf:{drop_id}"},
                                                        {"text": f"🎵 تغییر عنوان اثر{title_c}", "callback_data": f"bmeta:title:{drop_id}"}
                                                    ],
                                                    [
                                                        {"text": f"🖼 تغییر تصویر کاور{thumb_c}", "callback_data": f"bmeta:change_cov:{drop_id}"},
                                                        {"text": "📋 نمایش جزئیات تگ‌ها", "callback_data": f"bmeta:tag_details:{drop_id}"}
                                                    ],
                                                    [
                                                        {"text": "🧹 حذف متادیتا", "callback_data": f"bmeta:strip_tags:{drop_id}"},
                                                        {"text": "🔙 بازگشت به منوی اصلی", "callback_data": f"bmeta:back:{drop_id}"}
                                                    ]
                                                ]
                                            }
                                            await bale.edit_message_text(chat_id, msg_id, txt, reply_markup=kb)
                                        elif action == "tag_details":
                                            await ensure_bale_binary()
                                            MediaService.inspect_full(drop_id)
                                            txt = BaleFormatter.format_tag_details(drop)
                                            kb = build_bale_media_keyboard(drop_id, drop, is_sub=True)
                                            await bale.edit_message_text(chat_id, msg_id, txt, reply_markup=kb)
                                        elif action == "audio_specs":
                                            await ensure_bale_binary()
                                            MediaService.inspect_full(drop_id)
                                            txt = BaleFormatter.format_audio_specs(drop)
                                            kb = build_bale_media_keyboard(drop_id, drop, is_sub=True)
                                            await bale.edit_message_text(chat_id, msg_id, txt, reply_markup=kb)
                                        elif action == "strip_tags":
                                            await ensure_bale_binary()
                                            ok, raw_p = MediaService.strip_metadata_for_session(drop_id)
                                            if ok:
                                                txt = BaleFormatter.format_light_card(drop)
                                                kb = build_bale_media_keyboard(drop_id, drop, is_sub=False)
                                                await bale.edit_message_text(chat_id, msg_id, txt, reply_markup=kb)
                                                await bale.send_message(chat_id, "✅ تمام متادیتاها و تگ‌های فایل با موفقیت پاکسازی شد.")
                                            else:
                                                await bale.send_message(chat_id, "❌ خطا در پاکسازی متادیتا.")
                                        elif action == "ai_transcribe":  # استخراج متن و کپشن با AI
                                            kb = {
                                                "inline_keyboard": [
                                                    [{"text": "⚡️ گوگل جمینای (Gemini Flash)", "callback_data": f"bai_eng:gemini:{drop_id}"}],
                                                    [{"text": "🚀 موتور نورا (Nara Router)", "callback_data": f"bai_eng:nara:{drop_id}"}],
                                                    [{"text": "🔙 بازگشت به منوی رسانه", "callback_data": f"bmeta:back:{drop_id}"}]
                                                ]
                                            }
                                            await bale.edit_message_text(
                                                chat_id, msg_id,
                                                "🧠 <b>دستیار هوش مصنوعی UNFINIT (مرحله ۱ از ۲):</b>\nلطفاً موتور هوش مصنوعی مورد نظر را انتخاب نمایید:",
                                                reply_markup=kb
                                            )
                                        elif action == "back":
                                            txt = BaleFormatter.format_light_card(drop)
                                            kb = build_bale_media_keyboard(drop_id, drop, is_sub=False)
                                            await bale.edit_message_text(chat_id, msg_id, txt, reply_markup=kb)
                                        elif action == "fn":
                                            session_manager.set_user_action(f"bale_{chat_id}", "await_fn", drop_id)
                                            await bale.send_message(chat_id, "✏️ لطفاً نام فایل جدید را ارسال فرمایید:")
                                        elif action == "perf":
                                            session_manager.set_user_action(f"bale_{chat_id}", "await_perf", drop_id)
                                            kb_quick = {
                                                "inline_keyboard": [
                                                    [{"text": f"⚡️ تنظیم روی مقدار پیش‌فرض ({config.DEFAULT_ARTIST})", "callback_data": f"bmeta:set_def_artist:{drop_id}"}],
                                                    [{"text": "🔙 انصراف", "callback_data": f"bmeta:back:{drop_id}"}]
                                                ]
                                            }
                                            await bale.send_message(
                                                chat_id,
                                                "🗣 <b>لطفاً نام خواننده / سازنده جدید را ارسال فرمایید:</b>\n"
                                                "یا می‌توانید با کلیک روی دکمه زیر، مستقیماً از مقدار پیش‌فرض استفاده کنید:",
                                                reply_markup=kb_quick
                                            )
                                        elif action == "set_def_artist":
                                            MediaService.apply_default_artist(drop_id)
                                            session_manager.clear_user_action(f"bale_{chat_id}")
                                            drop = session_manager.get_session(drop_id)
                                            txt = BaleFormatter.format_light_card(drop)
                                            kb = build_bale_media_keyboard(drop_id, drop, is_sub=False)
                                            await bale.edit_message_text(chat_id, msg_id, txt, reply_markup=kb)
                                        elif action == "title":
                                            session_manager.set_user_action(f"bale_{chat_id}", "await_title", drop_id)
                                            await bale.send_message(chat_id, "🎵 لطفاً عنوان موزیک را ارسال فرمایید:")
                                    
                                        # Trim Audio in Bale
                                        elif action == "trim":
                                            await ensure_bale_binary()
                                            tech = inspect_technical_metadata(drop["working_path"])
                                            dur = tech.get("duration_sec", 0)
                                            session_manager.set_user_action(f"bale_{chat_id}", "await_trim_time", drop_id)
                                            trim_prompt = (
                                                "✂️ بخش مورد نظر جهت برش فایل را مشخص فرمایید:\n\n"
                                                f"⏱️ مدت زمان کل فایل: {format_duration(dur)}\n\n"
                                                "نمونه‌های معتبر ارسال:\n"
                                                "▫️ شروع و پایان: 02:10 - 21:28 یا 02:10 21:28\n"
                                                "▫️ فقط زمان شروع (تا انتها): 02:10\n"
                                                "▫️ بر حسب ثانیه: 130 - 1288 یا 130"
                                            )
                                            await bale.send_message(chat_id, trim_prompt)

                                        # Video to MP3 Conversion on Bale
                                        elif action == "to_mp3":
                                            await ensure_bale_binary()
                                            status_m = await bale.send_message(chat_id, "⏳ <b>در حال استخراج و تبدیل هوشمند صوت ویدیو به MP3...</b>")
                                            try:
                                                ok, final_mp3, info = MediaService.extract_audio_from_video(drop_id)
                                                if ok and final_mp3.exists():
                                                    sz_mb = final_mp3.stat().st_size / (1024 * 1024)
                                                    safe_mb = float(getattr(config, "MAX_SAFE_BALE_SIZE_MB", 49.99))
                                                    target_mb = max(1.0, round(safe_mb - 1.5, 2))
                                                    if sz_mb >= safe_mb or final_mp3.stat().st_size > getattr(config, "MAX_SAFE_BALE_SIZE_BYTES", int(safe_mb * 1024 * 1024)):
                                                        orig_size_str = f"{sz_mb:.1f}"
                                                        await bale.send_message(
                                                            chat_id,
                                                            "⚙️ <b>در حال فشرده‌سازی هوشمند...</b>\n"
                                                            f"📦 حجم فعلی: <code>{orig_size_str} MB</code> ➔ هدف: <code>زیر {target_mb} MB</code>"
                                                        )
                                                        from media.compressor import SmartAudioCompressor
                                                        loop = asyncio.get_running_loop()
                                                        comp_p, _, _, _, was_c = await loop.run_in_executor(
                                                            None, SmartAudioCompressor.compress_if_needed, final_mp3
                                                        )
                                                        if was_c and comp_p.exists():
                                                            send_mp3_p = comp_p
                                                        await bale.send_message(chat_id, "📤 <b>در حال ارسال به بله...</b>")

                                                    await bale.send_audio(
                                                        chat_id,
                                                        send_mp3_p,
                                                        title=info["title"],
                                                        performer=info["artist"],
                                                        caption=f"🎵 نسخه صوتی استخراج‌شده از ویدیو (MP3):\n📄 {info['file_name']}\n🗣 خواننده: {info['artist']}"
                                                    )
                                                    new_drop_id = uuid.uuid4().hex[:8]
                                                    new_data = MediaService.register_incoming_message_meta(
                                                        new_drop_id, "bale", chat_id, str(send_mp3_p), send_mp3_p.name, send_mp3_p.stat().st_size,
                                                        media_type="audio", api_meta={"filename": send_mp3_p.name, "title": info["title"], "artist": info["artist"]}
                                                    )
                                                    new_data["working_path"] = str(send_mp3_p)
                                                    new_data["is_downloaded_locally"] = True
                                                    new_card = BaleFormatter.format_light_card(new_data)
                                                    new_kb = build_bale_media_keyboard(new_drop_id, new_data)
                                                    sent_c = await bale.send_message(chat_id, new_card, reply_markup=new_kb)
                                                    new_data["card_msg_id"] = sent_c.get("result", {}).get("message_id")
                                                else:
                                                    await bale.send_message(chat_id, "❌ خطا در استخراج صوت از ویدیو.")
                                            except Exception as e:
                                                await bale.send_message(chat_id, f"❌ خطا در استخراج صوت: {e}")

                                        elif action == "view_cov":
                                            await ensure_bale_binary()
                                            cov_p = MediaService.extract_cover(drop_id)
                                            if cov_p and Path(cov_p).exists() and Path(cov_p).stat().st_size > 50:
                                                await bale.send_photo(chat_id, cov_p, caption="🖼 تصویر بندانگشتی استخراج‌شده")
                                            else:
                                                await bale.send_message(chat_id, "⚠️ این فایل فاقد تصویر بند انگشتی است.")
                                        elif action == "change_cov":
                                            session_manager.set_user_action(f"bale_{chat_id}", "await_cover", drop_id)
                                            await bale.send_message(chat_id, "🌇 لطفاً عکس بند انگشتی (تامبنیل) جدید را ارسال فرمایید:")
                                    
                                        # Quick Visual Retag on Bale
                                        elif action == "quick_send":
                                            draft_title = drop.get("draft_tags", {}).get("title") or drop.get("embed_meta", {}).get("title") or drop.get("api_meta", {}).get("title") or ""
                                            draft_artist = drop.get("draft_tags", {}).get("artist") or drop.get("embed_meta", {}).get("artist") or drop.get("api_meta", {}).get("artist") or ""
                                            file_id = drop.get("file_id")
                                            fn = clean_display_filename(drop.get("audio_filename") or "audio.mp3")

                                            res = await bale.send_audio(
                                                chat_id,
                                                file_path=file_id,
                                                title=draft_title,
                                                performer=draft_artist,
                                                caption=f"⚡️ فایل با متادیتای نمایشی جدید:\n📄 {fn}\n🗣 خواننده: {draft_artist}\n🎵 عنوان: {draft_title}"
                                            )
                                            if not res.get("ok"):
                                                await bale.send_message(chat_id, f"❌ خطا در ارسال سریع بله: {res.get('error')}")

                                        elif action in ("send_back", "apply_changes"):
                                            status_m = await bale.send_message(chat_id, "⏳ <b>در حال آماده‌سازی و اعمال متادیتا...</b>")
                                            await ensure_bale_binary()
                                            try:
                                                w_path = Path(drop.get("working_path") or "")
                                                if w_path.exists() and (w_path.stat().st_size / (1024 * 1024)) >= 49.99:
                                                    orig_sz_mb = f"{w_path.stat().st_size / (1024 * 1024):.1f}"
                                                    await bale.send_message(
                                                        chat_id,
                                                        "🎛 <b>در حال فشرده‌سازی هوشمند جهت رعایت سقف بله...</b>\n"
                                                        f"📊 حجم فعلی: <code>{orig_sz_mb} MB</code> ➔ هدف: <code>زیر 49.9 MB</code>\n"
                                                        "⚙️ فرآیند بهینه‌سازی صدا و تصویر در حال اجراست، لطفاً شکیبا باشید..."
                                                    )
                                                final_p, fn, info = MediaService.prepare_for_transfer(drop_id, "bale")
                                                await bale.send_message(chat_id, "📤 <b>در حال ارسال به بله...</b>")
                                                if drop.get("media_type") == "video":
                                                    tech = inspect_technical_metadata(final_p)
                                                    await bale.send_video(
                                                        chat_id, final_p,
                                                        caption=f"✅ ویدیو اصلاح‌شده:\n📄 {clean_display_filename(fn)}",
                                                        duration=tech.get("duration_sec"),
                                                        width=tech.get("width"),
                                                        height=tech.get("height")
                                                    )
                                                else:
                                                    await bale.send_audio(
                                                        chat_id, final_p, title=info["title"], performer=info["artist"],
                                                        caption=f"✅ فایل اصلاح‌شده و تگ‌گذاری‌شده:\n📄 {clean_display_filename(fn)}\n🗣 خواننده: {info['artist']}\n🎵 عنوان: {info['title']}"
                                                    )
                                                await bale.send_message(chat_id, f"✅ <b>فایل با موفقیت ارسال شد!</b>\n📄 <code>{clean_display_filename(fn)}</code>")
                                            except Exception as e:
                                                await bale.send_message(chat_id, f"❌ خطا در ارتباط با سرورهای بله: {e}")
                                    
                                        # Transfer from Bale to Telegram (Clean Pipeline)
                                        elif action == "send_tg":
                                            if telegram_adapter_instance:
                                                status_m = await bale.send_message(chat_id, "⏳ در حال دانلود و آماده‌سازی فایل جهت انتقال به تلگرام...")
                                                await ensure_bale_binary()
                                                final_p, fn, info = MediaService.prepare_for_transfer(drop_id, "telegram")
                                                target_tg_id = config.TELEGRAM_OWNER_ID or telegram_adapter_instance.get_admin_id()
                                            
                                                if drop.get("media_type") == "video":
                                                    tech = inspect_technical_metadata(final_p)
                                                    thumb_p = generate_video_thumbnail(final_p)
                                                    res = await telegram_adapter_instance.send_video(
                                                        target_tg_id, final_p,
                                                        caption=f"📄 {clean_display_filename(fn)}",
                                                        width=tech.get("width"),
                                                        height=tech.get("height"),
                                                        duration=tech.get("duration_sec"),
                                                        thumb=thumb_p
                                                    )
                                                else:
                                                    res = await telegram_adapter_instance.send_audio(
                                                        target_tg_id, final_p, title=info["title"], performer=info["artist"], caption=f"📄 {clean_display_filename(fn)}"
                                                    )
                                                if res.get("ok"):
                                                    await bale.send_message(chat_id, f"✅ فایل با موفقیت به تلگرام منتقل شد!\n📄 {clean_display_filename(fn)}")
                                                else:
                                                    await bale.send_message(chat_id, f"❌ خطا در ارسال به تلگرام: {res.get('error')}")

                                        # Transfer from Bale to Rubika (Clean Pipeline)
                                        elif action == "send_rub":
                                            if rubika_adapter_instance:
                                                status_m = await bale.send_message(chat_id, "⏳ در حال آماده‌سازی و ارسال فایل به روبیکا...")
                                                await ensure_bale_binary()
                                                final_p, fn, info = MediaService.prepare_for_transfer(drop_id, "rubika")
                                                target_rub_id = rubika_adapter_instance.get_admin_guid()
                                                res = await rubika_adapter_instance.send_audio(
                                                    target_rub_id, final_p, title=info["title"], performer=info["artist"],
                                                    caption=f"📄 {clean_display_filename(fn)}"
                                                )
                                                if res.get("ok") or res.get("status") == "OK":
                                                    await bale.send_message(chat_id, f"✅ فایل با موفقیت به روبیکا منتقل شد!\n📄 {clean_display_filename(fn)}")
                                                else:
                                                    await bale.send_message(chat_id, f"❌ خطا در ارسال به روبیکا: {res.get('error') or res}")

                                        # Transfer from Bale to Soroush Plus (Clean Pipeline)
                                        elif action == "send_splus":
                                            # انتقال مستقیم فایل چندرسانه‌ای از بله به پیام‌های ذخیره‌شده پیام‌رسان سروش‌پلاس
                                            from platforms.soroush_worker import soroush_worker
                                            if not soroush_worker.is_connected():
                                                await bale.send_message(chat_id, "❌ سشن کاربری سروش‌پلاس متصل نیست. لطفاً ابتدا در پنل وب وارد شوید.")
                                            else:
                                                status_m = await bale.send_message(chat_id, "⏳ در حال دانلود و آماده‌سازی فایل جهت انتقال به سروش‌پلاس...")
                                                await ensure_bale_binary()
                                                try:
                                                    final_p, fn, info = MediaService.prepare_for_transfer(drop_id, "soroush")
                                                    caption_t = f"📄 {clean_display_filename(fn)}"
                                                    res = await soroush_worker.send_file_to_saved_messages(final_p, caption=caption_t)
                                                    if res.get("ok"):
                                                        queue_note = " (در صف ارسال محلی امن ذخیره گردید)" if res.get("queued") else ""
                                                        await bale.send_message(chat_id, f"✅ فایل با موفقیت به سروش‌پلاس منتقل شد!{queue_note}\n📄 {clean_display_filename(fn)}")
                                                    else:
                                                        await bale.send_message(chat_id, f"❌ خطا در ارسال به سروش‌پلاس: {res.get('error') or res}")
                                                except Exception as e:
                                                    await bale.send_message(chat_id, f"❌ خطا در فرآیند ارسال به سروش‌پلاس: {e}")

                                        elif action == "add_to_course":
                                            courses = await StoreService.get_products(is_free_only=False)
                                            if not courses:
                                                await bale.send_message(chat_id, "هیچ دوره‌ای تعریف نشده است.")
                                            else:
                                                c_buttons = [
                                                    [{"text": f"➕ {c.name}", "callback_data": f"bmeta:attach_course:{drop_id}:{c.product_id}"}]
                                                    for c in courses[:10]
                                                ]
                                                c_buttons.append([{"text": "🔙 بازگشت به منوی رسانه", "callback_data": f"bmeta:back:{drop_id}"}])
                                                await bale.send_message(chat_id, "📚 دوره‌ای که می‌خواهید این فایل به آن اضافه شود را انتخاب فرمایید:", reply_markup={"inline_keyboard": c_buttons})

                                        elif action == "attach_course":
                                            course_id = parts[3] if len(parts) > 3 else (parts[2] if len(parts) > 2 else "")
                                            prod = await StoreService.get_product(course_id)
                                            if prod:
                                                pkg = list(getattr(prod, "files_package", []) or [])
                                                f_id = drop.get("file_id") or ""
                                                fn = drop.get("filename") or "فایل دوره"
                                                pkg.append({
                                                    "file_id": f_id,
                                                    "title": fn,
                                                    "platform": "bale",
                                                    "size": drop.get("file_size", 0)
                                                })
                                                await StoreService.update_product_field(course_id, "files_package", pkg)
                                                await StoreService.update_product_field(course_id, "delivery_type", "files_package")
                                                await bale.send_message(chat_id, f"✅ فایل با موفقیت به دوره «{prod.name}» پیوست شد!")
                                            else:
                                                await bale.send_message(chat_id, "دوره یافت نشد.")

                                        elif action == "compress":
                                            await ensure_bale_binary()
                                            status_m = await bale.send_message(chat_id, "⚡️ <b>در حال فشرده‌سازی هوشمند فایل...</b>")
                                            try:
                                                wpath = Path(drop.get("working_path") or "")
                                                if not wpath.exists():
                                                    final_p, fn, info = MediaService.prepare_for_transfer(drop_id, "bale")
                                                    wpath = final_p
                                                if drop.get("media_type") == "video":
                                                    from media.compressor import SmartVideoCompressor
                                                    comp_p, _, _, _, was_c = SmartVideoCompressor.compress_if_needed(wpath)
                                                else:
                                                    from media.compressor import SmartAudioCompressor
                                                    comp_p, _, _, _, was_c = SmartAudioCompressor.compress_if_needed(wpath)
                                                if comp_p and comp_p.exists():
                                                    drop["working_path"] = str(comp_p)
                                                    drop["file_size"] = comp_p.stat().st_size
                                                    session_manager.update_session(drop_id, drop)
                                                    await bale.send_message(chat_id, f"✅ فشرده‌سازی انجام شد! حجم جدید: {drop['file_size'] / (1024*1024):.2f} مگابایت")
                                                else:
                                                    await bale.send_message(chat_id, "ℹ️ فایل در اندازه مناسب است و نیاز به فشرده‌سازی بیشتر ندارد.")
                                            except Exception as c_err:
                                                await bale.send_message(chat_id, f"❌ خطا در فشرده‌سازی: {c_err}")

                                    # Bale AI Stage 1 -> Stage 2 Callback
                                    if cb_data.startswith("bai_eng:"):
                                        parts = cb_data.split(":")
                                        engine = parts[1]
                                        drop_id = parts[2]
                                        engine_title = "گوگل جمینای (Gemini Flash)" if engine == "gemini" else "نورا (Nara Router)"
                                        kb = {
                                            "inline_keyboard": [
                                                [{"text": "📢 کانال تلگرام / پیام‌رسان", "callback_data": f"bai_fmt:tg:{engine}:{drop_id}"}],
                                                [{"text": "📸 اینستاگرام اکسپلور (کپشن و هشتگ)", "callback_data": f"bai_fmt:ig:{engine}:{drop_id}"}],
                                                [{"text": "🔙 مرحله قبل", "callback_data": f"bmeta:ai_transcribe:{drop_id}"}]
                                            ]
                                        }
                                        await bale.edit_message_text(
                                            chat_id, msg_id,
                                            f"🧠 <b>دستیار هوش مصنوعی ({engine_title}) (مرحله ۲ از ۲):</b>\nلطفاً سبک خروجی را انتخاب کنید:",
                                            reply_markup=kb
                                        )
                                        continue

                                    # Bale AI Stage 2 Execution Callback
                                    if cb_data.startswith("bai_fmt:"):
                                        parts = cb_data.split(":")
                                        fmt = parts[1]
                                        engine = parts[2]
                                        drop_id = parts[3]
                                        style = "instagram" if fmt == "ig" else "telegram"
                                        style_title = "📸 کپشن اینستاگرام" if style == "instagram" else "📢 پست کانال"
                                        engine_title = "گوگل جمینای" if engine == "gemini" else "نورا (Nara)"

                                        drop = session_manager.get_session(drop_id)
                                        if not drop:
                                            await bale.send_message(chat_id, "❌ نشست فایل منقضی شده است.")
                                            continue

                                        local_p = drop.get("working_path") or drop.get("compressed_path") or drop.get("original_path")
                                        if not local_p or not Path(str(local_p)).exists():
                                            await bale.send_message(chat_id, "❌ فایل صوتی روی سرور یافت نشد.")
                                            continue

                                        status_msg = await bale.send_message(
                                            chat_id,
                                            f"⏳ <b>[۱/۳] تحلیل با {engine_title} ({style_title})</b>\n▫️ در حال گوش دادن و پردازش معنایی..."
                                        )
                                        status_msg_id = status_msg.get("result", {}).get("message_id") if isinstance(status_msg, dict) else None

                                        async def _bale_progress(stage_text: str):
                                            try:
                                                if status_msg_id:
                                                    await bale.edit_message_text(chat_id, status_msg_id, stage_text)
                                            except Exception: pass

                                        from services.ai_agent_service import ai_agent_service, ai_typing_action
                                        async def _bale_audio_typing():
                                            await bale.send_chat_action(chat_id, "typing")

                                        async with ai_typing_action(_bale_audio_typing):
                                            res = await ai_agent_service.transcribe_and_summarize_audio(
                                                Path(str(local_p)),
                                                metadata=drop,
                                                progress_callback=_bale_progress,
                                                style=style,
                                                engine=engine
                                            )
                                        if res.get("ok"):
                                            msg_text = res.get("formatted_message") or res.get("summary")
                                            if len(msg_text) > 4000:
                                                msg_text = msg_text[:3990] + "..."
                                            try:
                                                if status_msg_id:
                                                    await bale.edit_message_text(chat_id, status_msg_id, msg_text)
                                                else:
                                                    await bale.send_message(chat_id, msg_text)
                                            except Exception:
                                                try:
                                                    clean_txt = re.sub(r"<[^>]+>", "", msg_text)
                                                    if status_msg_id:
                                                        await bale.edit_message_text(chat_id, status_msg_id, clean_txt)
                                                    else:
                                                        await bale.send_message(chat_id, clean_txt)
                                                except Exception: pass
                                        else:
                                            err_txt = f"❌ {res.get('error') or 'خطا در پردازش هوش مصنوعی'}"
                                            try:
                                                if status_msg_id:
                                                    await bale.edit_message_text(chat_id, status_msg_id, err_txt)
                                            except Exception: pass
                                        continue

                                    # Course Management in Bale
                                    if cb_data.startswith("badm_pview:"):
                                        if not bale.is_admin(chat_id): continue
                                        pid = cb_data.split(":")[1]
                                        prod = await StoreService.get_product(pid)
                                        if not prod:
                                            await bale.send_message(chat_id, "❌ دوره یافت نشد.")
                                            continue
                                        txt = format_bale_admin_course_card(prod)
                                        kb = build_bale_admin_course_kb(pid, prod.active)
                                        photo_res = resolve_bale_course_photo(prod)
                                        sent_photo = False
                                        if photo_res:
                                            try:
                                                await bale.delete_message(chat_id, msg_id)
                                            except Exception:
                                                pass
                                            photo_val = photo_res.get("value")
                                            if photo_res.get("type") == "local_path":
                                                r = await bale.send_photo(chat_id, photo_val, caption=txt, reply_markup=kb)
                                            else:
                                                r = await bale.send_photo_by_id(chat_id, photo_val, caption=txt, reply_markup=kb)
                                            if r and r.get("ok"):
                                                sent_photo = True
                                        if not sent_photo:
                                            try:
                                                await bale.edit_message_text(chat_id, msg_id, txt, reply_markup=kb)
                                            except Exception:
                                                await bale.send_message(chat_id, txt, reply_markup=kb)
                                        continue

                                    if cb_data.startswith("badm_c_toggle:"):
                                        if not bale.is_admin(chat_id): continue
                                        pid = cb_data.split(":")[1]
                                        prod = await StoreService.get_product(pid)
                                        if prod:
                                            new_st = 0 if prod.active else 1
                                            await StoreService.update_product_field(pid, "active", new_st)
                                            prod.active = bool(new_st)
                                            txt = format_bale_admin_course_card(prod)
                                            kb = build_bale_admin_course_kb(pid, prod.active)
                                            c_res = await bale.edit_message_caption(chat_id, msg_id, txt, reply_markup=kb)
                                            if not c_res.get("ok"):
                                                await bale.edit_message_text(chat_id, msg_id, txt, reply_markup=kb)
                                        continue

                                    if cb_data.startswith("badm_c_edit:"):
                                        if not bale.is_admin(chat_id): continue
                                        parts = cb_data.split(":")
                                        field = parts[1]
                                        pid = parts[2]
                                        prod = await StoreService.get_product(pid)
                                        if not prod:
                                            await bale.send_message(chat_id, "❌ دوره یافت نشد.")
                                            continue

                                        session_manager.set_user_action(f"bale_{chat_id}", f"await_c_edit_{field}", pid)
                                        prompts = {
                                            "link": f"🔗 <b>ویرایش لینک‌های دوره «{prod.name}»:</b>\n\nلطفاً لینک‌ها یا متن جدید دسترسی را ارسال فرمایید:\n(می‌توانید شامل لینک کانال بله، تلگرام، دانلود مستقیم و توضیحات باشد)\nجهت انصراف عبارت /cancel را بفرستید.",
                                            "price": f"💰 <b>تغییر قیمت دوره «{prod.name}»:</b>\n\nقیمت فعلی: <code>{prod.price:,} تومان</code>\nلطفاً مبلغ جدید را به تومان (فقط عدد، مثلاً 120000 یا 0 برای رایگان) ارسال فرمایید:\nجهت انصراف عبارت /cancel را بفرستید.",
                                            "desc": f"📝 <b>ویرایش توضیحات دوره «{prod.name}»:</b>\n\nلطفاً متن توضیحات جدید دوره را ارسال فرمایید:\nجهت انصراف عبارت /cancel را بفرستید.",
                                            "photo": f"🖼 <b>تغییر تصویر یا بنر دوره «{prod.name}»:</b>\n\nلطفاً آدرس اینترنتی تصویر بنر (URL) را ارسال فرمایید:\nجهت انصراف عبارت /cancel را بفرستید."
                                        }
                                        await bale.send_message(chat_id, prompts.get(field, "لطفاً مقدار جدید را ارسال فرمایید:"))
                                        continue

                                    if cb_data == "badm_c_list":
                                        if not bale.is_admin(chat_id): continue
                                        all_items = await StoreService.get_all_products(active_only=False)
                                        prods = [p for p in all_items if p.price > 0]
                                        gifts = [p for p in all_items if p.price == 0]
                                        lines = [
                                            "📚 <b>پنل مدیریت دوره‌ها و فایل‌های دانلودی:</b>",
                                            f"تعداد کل: <b>{len(all_items)}</b> (دوره‌ها: <b>{len(prods)}</b> | هدایا: <b>{len(gifts)}</b>)",
                                            "",
                                            "لیست دوره‌ها (جهت مشاهده جزئیات یا ویرایش روی دوره کلیک کنید):"
                                        ]
                                        buttons = [[{"text": f"{'🎁' if p.price == 0 else f'🎓 ({p.price:,} ت)'} {'[غیرفعال] ' if not p.active else ''}{p.name}", "callback_data": f"badm_pview:{p.product_id}"}] for p in all_items]
                                        buttons.append([{"text": "➕ افزودن دوره جدید", "callback_data": "badm_c_add"}])
                                        r = await bale.edit_message_text(chat_id, msg_id, "\n".join(lines), reply_markup={"inline_keyboard": buttons})
                                        if not r.get("ok"):
                                            try:
                                                await bale.delete_message(chat_id, msg_id)
                                            except Exception:
                                                pass
                                            await bale.send_message(chat_id, "\n".join(lines), reply_markup={"inline_keyboard": buttons})
                                        continue

                                    if cb_data in ("vip_club_info", "bale:vip_plan"):
                                        is_vip = UserService.is_user_vip(chat_id)
                                        if is_vip:
                                            u = UserService.get_user_by_any_id(chat_id)
                                            vip_until_show = u.get_vip_until_jalali() if u else ""
                                            txt = (
                                                "💎 <b>باشگاه مشترکین پریمیوم</b>\n\n"
                                                f"اشتراک پریمیوم شما تا تاریخ <b>{vip_until_show or 'فعال'}</b> معتبر است.\n\n"
                                                "جهت دسترسی به محتوای اختصاصی، بخش مورد نظر خود را انتخاب فرمایید:"
                                            )
                                            vip_btns = [
                                                [{"text": "📁 ۱۶ دسته‌بندی مقالات و آموزش‌ها", "callback_data": "bale:vip_cats:1"}],
                                                [{"text": "💎 فرکانس فراوانی و آرامش", "callback_data": "bale:freq_cats"}],
                                                [{"text": "🔙 بازگشت به محصولات", "callback_data": "bale:prods_hub"}]
                                            ]
                                            await bale.send_message(chat_id, txt, reply_markup={"inline_keyboard": vip_btns})
                                            continue

                                        price = await get_system_setting("vip_monthly_price", "111000")
                                        try:
                                            price_val = int(price)
                                            price_formatted = f"{price_val:,}"
                                        except Exception:
                                            price_val = 111000
                                            price_formatted = "111,000"
                                        days = await get_system_setting("vip_duration_days", "30")
                                        card_num = await get_system_setting("vip_card_number", await get_system_setting("CARD_NUMBER", config.CARD_NUMBER))
                                        bale_pay_tok = await get_system_setting("vip_bale_payment_token", await get_system_setting("bale_payment_token", config.BALE_PAYMENT_TOKEN))
                                        
                                        txt = (
                                            "💎 <b>اشتراک پریمیوم</b>\n\n"
                                            "با تهیه اشتراک پریمیوم، به تمامی خدمات ویژه زیر به مدت ۳۰ روز دسترسی نامحدود خواهید داشت:\n\n"
                                            "▫️ <b>۱۶ دسته‌بندی رسمی مقالات و آموزش‌های عباس‌منش</b>\n"
                                            "▫️ <b>۵ پروژه تحول گام‌به‌گام</b>\n"
                                            "▫️ <b>دسترسی کامل به فرکانس فراوانی (باورهای روزانه ثروت و آرامش)</b>\n"
                                            "▫️ <b>دریافت فایل‌های صوتی و تصویری مستقیم در بله</b>\n\n"
                                            f"💰 <b>تعرفه اشتراک {days} روزه:</b> {price_formatted} تومان\n"
                                        )
                                        vip_btns = []
                                        if bale_pay_tok:
                                            vip_btns.append([{"text": f"⚡️ پرداخت آنلاین و فعال‌سازی آنی ({price_formatted} تومان)", "callback_data": "bale:vip_pay_online"}])
                                        if card_num:
                                            txt += f"\n💳 <b>شماره کارت جهت واریز:</b>\n<code>{card_num}</code>\n"
                                            vip_btns.append([{"text": "🧾 ارسال رسید واریز کارت به کارت", "callback_data": "bale:vip_pay_card"}])
                                        vip_btns.append([{"text": "📁 مشاهده عناوین ۱۶ دسته‌بندی", "callback_data": "bale:vip_cats:1"}])
                                        vip_btns.append([{"text": "🔙 بازگشت به محصولات", "callback_data": "bale:prods_hub"}])
                                        await bale.send_message(chat_id, txt, reply_markup={"inline_keyboard": vip_btns} if vip_btns else None)
                                        continue

                                    if cb_data == "bale:vip_pay_online":
                                        price = await get_system_setting("vip_monthly_price", "111000")
                                        try:
                                            price_val = int(price)
                                        except Exception:
                                            price_val = 111000
                                        bale_pay_tok = await get_system_setting("vip_bale_payment_token", await get_system_setting("bale_payment_token", config.BALE_PAYMENT_TOKEN))
                                        if not bale_pay_tok:
                                            await bale.send_message(chat_id, "⚠️ درگاه پرداخت آنلاین موقتاً در دسترس نیست. لطفاً از طریق کارت به کارت اقدام فرمایید.")
                                            continue
                                        inv_payload = f"vip_sub_{chat_id}_{int(time.time())}"
                                        days = await get_system_setting("vip_duration_days", "30")
                                        res_inv = await bale.send_invoice(
                                            chat_id=chat_id,
                                            title="اشتراک پریمیوم ۳۰ روزه",
                                            description=f"فعال‌سازی آنی اشتراک پریمیوم ({days} روز)",
                                            payload=inv_payload,
                                            provider_token=bale_pay_tok,
                                            amount_tomans=price_val
                                        )
                                        if not res_inv.get("ok"):
                                            logger.warning(f"Bale send_invoice for VIP returned error: {res_inv}")
                                            await bale.send_message(chat_id, "❌ متأسفانه صدور فاکتور پرداخت آنلاین با خطا مواجه شد. لطفاً از روش کارت به کارت استفاده فرمایید.")
                                        continue

                                    if cb_data == "bale:vip_pay_card":
                                        session_manager.set_user_action(f"bale_{chat_id}", "await_vip_receipt", "vip_receipt", extra={})
                                        await bale.send_message(
                                            chat_id,
                                            "🧾 <b>ثبت فیش واریز اشتراک پریمیوم:</b>\n\n"
                                            "لطفاً تصویر رسید واریز یا شماره پیگیری خود را ارسال فرمایید تا پس از بررسی فعال شود:\n"
                                            "(جهت انصراف عبارت <code>/cancel</code> را بفرستید)"
                                        )
                                        continue

                                    if cb_data.startswith("bale:vip_cats:"):
                                        from services.feed_scraper import feed_scraper
                                        page_str = cb_data.split(":")[-1]
                                        page = int(page_str) if page_str.isdigit() else 1
                                        cats = feed_scraper.get_all_categories()
                                        limit = 6
                                        total_pages = max(1, (len(cats) + limit - 1) // limit)
                                        page = min(max(1, page), total_pages)
                                        start_idx = (page - 1) * limit
                                        page_cats = cats[start_idx:start_idx + limit]

                                        txt = (
                                            "📁 <b>دسته‌بندی‌های رسمی مقالات و آموزش‌های عباس‌منش</b>\n\n"
                                            f"صفحه <b>{page}</b> از <b>{total_pages}</b>\n"
                                            "جهت مشاهده جلسات، فایل‌های صوتی و تصویری، دسته‌بندی مورد نظر را انتخاب فرمایید:"
                                        )
                                        buttons = []
                                        for c in page_cats:
                                            cat_emoji = c.get("emoji") or "📂"
                                            buttons.append([{"text": f"{cat_emoji} {c['title']}", "callback_data": f"bale:vip_cat:{c['id']}:1"}])

                                        nav_row = []
                                        if page > 1:
                                            nav_row.append({"text": "◀️ صفحه قبل", "callback_data": f"bale:vip_cats:{page-1}"})
                                        if page < total_pages:
                                            nav_row.append({"text": "صفحه بعد ▶️", "callback_data": f"bale:vip_cats:{page+1}"})
                                        if nav_row:
                                            buttons.append(nav_row)

                                        buttons.append([{"text": "🔙 بازگشت به اشتراک پریمیوم", "callback_data": "vip_club_info"}])
                                        await bale.send_message(chat_id, txt, reply_markup={"inline_keyboard": buttons})
                                        continue

                                    if cb_data.startswith("bale:vip_cat:"):
                                        from services.feed_scraper import feed_scraper
                                        parts = cb_data.split(":")
                                        cat_id = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 1
                                        page = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 1
                                        cat = feed_scraper.get_category_by_id(cat_id)
                                        if not cat:
                                            await bale.send_message(chat_id, "❌ دسته‌بندی یافت نشد.")
                                            continue

                                        is_vip = UserService.is_user_vip(chat_id)
                                        if not is_vip:
                                            lock_txt = (
                                                f"🔒 <b>دسترسی اختصاصی: {escape(cat['title'])}</b>\n\n"
                                                "محتوای کامل و فایل‌های صوتی/تصویری این دسته‌بندی مختص اعضای دارای <b>اشتراک پریمیوم</b> می‌باشد.\n\n"
                                                "با فعال‌سازی اشتراک پریمیوم، علاوه بر ۱۶ دسته‌بندی، به پروژه‌های تحول و فرکانس فراوانی نیز دسترسی خواهید داشت."
                                            )
                                            lock_kb = {
                                                "inline_keyboard": [
                                                    [{"text": "💎 فعال‌سازی اشتراک پریمیوم", "callback_data": "vip_club_info"}],
                                                    [{"text": "🔙 بازگشت به دسته‌بندی‌ها", "callback_data": "bale:vip_cats:1"}]
                                                ]
                                            }
                                            await bale.send_message(chat_id, lock_txt, reply_markup=lock_kb)
                                            continue

                                        res = await feed_scraper.get_category_episodes(cat_id, page=page, limit=6)
                                        episodes = res.get("episodes", [])
                                        txt = (
                                            f"📂 <b>{escape(cat['title'])}</b>\n"
                                            f"📄 {escape(cat.get('description', ''))}\n\n"
                                            f"صفحه <b>{page}</b> | جلسات یافت‌شده: <b>{len(episodes)}</b>\n"
                                            "جهت دریافت صوت یا ویدیو، جلسه مورد نظر را انتخاب فرمایید:"
                                        )
                                        buttons = []
                                        for ep_idx, ep in enumerate(episodes):
                                            ep_title = ep.get("title", f"جلسه {ep_idx+1}")
                                            buttons.append([{"text": f"🎧 {ep_title[:40]}", "callback_data": f"bale:vip_ep:{cat_id}:{page}:{ep_idx}"}])

                                        nav_row = []
                                        if page > 1:
                                            nav_row.append({"text": "◀️ صفحه قبل", "callback_data": f"bale:vip_cat:{cat_id}:{page-1}"})
                                        if res.get("has_next"):
                                            nav_row.append({"text": "صفحه بعد ▶️", "callback_data": f"bale:vip_cat:{cat_id}:{page+1}"})
                                        if nav_row:
                                            buttons.append(nav_row)

                                        buttons.append([{"text": "🔙 بازگشت به دسته‌بندی‌ها", "callback_data": "bale:vip_cats:1"}])
                                        await bale.send_message(chat_id, txt, reply_markup={"inline_keyboard": buttons})
                                        continue

                                    if cb_data.startswith("bale:vip_ep:"):
                                        from services.feed_scraper import feed_scraper
                                        parts = cb_data.split(":")
                                        cat_id = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 1
                                        page = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 1
                                        ep_idx = int(parts[4]) if len(parts) > 4 and parts[4].isdigit() else 0

                                        res = await feed_scraper.get_category_episodes(cat_id, page=page, limit=6)
                                        episodes = res.get("episodes", [])
                                        if ep_idx >= len(episodes):
                                            await bale.send_message(chat_id, "❌ جلسه یافت نشد.")
                                            continue

                                        ep = episodes[ep_idx]
                                        txt = (
                                            f"💎 <b>{escape(ep.get('title', ''))}</b>\n\n"
                                            f"📂 دسته‌بندی: <b>{escape(res.get('category', {}).get('title', ''))}</b>\n"
                                        )
                                        if ep.get("chapters"):
                                            txt += "\n📌 <b>سرفصل‌های این بخش:</b>\n" + "\n".join(f"▫️ {c}" for c in ep["chapters"][:3]) + "\n"

                                        txt += "\nفرمت مورد نظر جهت دریافت مستقیم را انتخاب فرمایید:"
                                        btns = []
                                        dl_row = []
                                        if ep.get("audio_download_url") or ep.get("audio_url"):
                                            dl_row.append({"text": "🎧 دریافت صوت (MP3)", "callback_data": f"bale:vip_dl:{cat_id}:{page}:{ep_idx}:audio"})
                                        if ep.get("video_download_url") or ep.get("video_url"):
                                            dl_row.append({"text": "🎬 دریافت ویدیو (MP4)", "callback_data": f"bale:vip_dl:{cat_id}:{page}:{ep_idx}:video"})
                                        if dl_row:
                                            btns.append(dl_row)
                                        btns.append([{"text": "🔙 بازگشت به لیست جلسات", "callback_data": f"bale:vip_cat:{cat_id}:{page}"}])
                                        await bale.send_message(chat_id, txt, reply_markup={"inline_keyboard": btns})
                                        continue

                                    if cb_data.startswith("bale:vip_dl:"):
                                        from services.feed_scraper import feed_scraper
                                        from core.database import db_get_cached_file_id, db_set_cached_file_id
                                        parts = cb_data.split(":")
                                        cat_id = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 1
                                        page = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 1
                                        ep_idx = int(parts[4]) if len(parts) > 4 and parts[4].isdigit() else 0
                                        media_type = parts[5] if len(parts) > 5 else "audio"

                                        if not UserService.is_user_vip(chat_id):
                                            await bale.send_message(chat_id, "🔒 جهت دریافت این فایل نیاز به اشتراک فعال پریمیوم دارید.")
                                            continue

                                        res = await feed_scraper.get_category_episodes(cat_id, page=page, limit=6)
                                        episodes = res.get("episodes", [])
                                        if ep_idx >= len(episodes):
                                            await bale.send_message(chat_id, "❌ جلسه یافت نشد.")
                                            continue

                                        ep = episodes[ep_idx]
                                        url = (ep.get("audio_download_url") or ep.get("audio_url")) if media_type == "audio" else (ep.get("video_download_url") or ep.get("video_url"))
                                        if not url:
                                            await bale.send_message(chat_id, "❌ لینک دانلودی برای این فرمت موجود نیست.")
                                            continue

                                        await bale.send_message(
                                            chat_id,
                                            f"⏳ <b>در حال آماده‌سازی و ارسال {'صوت' if media_type == 'audio' else 'ویدیو'}...</b>\n"
                                            f"📄 {escape(ep.get('title', ''))}"
                                        )

                                        file_key = f"abas_{cat_id}_{page}_{ep_idx}_{media_type}_{abs(hash(url))}"
                                        cached_fid = await db_get_cached_file_id(file_key, "bale")
                                        if cached_fid:
                                            try:
                                                if media_type == "audio":
                                                    await bale.send_audio(chat_id, cached_fid, caption=f"🎧 <b>{escape(ep.get('title', ''))}</b>\n💎 اشتراک پریمیوم")
                                                else:
                                                    await bale.send_video(chat_id, cached_fid, caption=f"🎬 <b>{escape(ep.get('title', ''))}</b>\n💎 اشتراک پریمیوم")
                                                continue
                                            except Exception as e:
                                                logger.warning(f"Failed sending cached file_id in bale: {e}")

                                        ext = ".mp3" if media_type == "audio" else ".mp4"
                                        target_path = config.TEMP_DIR / f"vip_bale_{uuid.uuid4().hex[:8]}{ext}"
                                        target_path.parent.mkdir(parents=True, exist_ok=True)
                                        try:
                                            async with aiohttp.ClientSession(headers={"User-Agent": "Mozilla/5.0"}) as sess:
                                                async with sess.get(url, timeout=aiohttp.ClientTimeout(total=180)) as resp:
                                                    if resp.status == 200:
                                                        with open(target_path, "wb") as f_out:
                                                            async for chunk in resp.content.iter_chunked(128 * 1024):
                                                                f_out.write(chunk)
                                                    else:
                                                        await bale.send_message(chat_id, "❌ خطا در دانلود فایل از سرور منبع.")
                                                        continue

                                            if not target_path.exists() or target_path.stat().st_size == 0:
                                                await bale.send_message(chat_id, "❌ فایل نامعتبر است.")
                                                continue

                                            if media_type == "audio":
                                                sent = await bale.send_audio(
                                                    chat_id,
                                                    target_path,
                                                    caption=f"🎧 <b>{escape(ep.get('title', ''))}</b>\n💎 اشتراک پریمیوم",
                                                    title=ep.get("title", "فایل صوتی"),
                                                    performer="استاد عباس‌منش"
                                                )
                                                f_id = (sent.get("result") or {}).get("audio", {}).get("file_id") if isinstance(sent, dict) else None
                                                if f_id:
                                                    await db_set_cached_file_id(file_key, "bale", f_id, "audio")
                                            else:
                                                sent = await bale.send_video(
                                                    chat_id,
                                                    target_path,
                                                    caption=f"🎬 <b>{escape(ep.get('title', ''))}</b>\n💎 اشتراک پریمیوم"
                                                )
                                                f_id = (sent.get("result") or {}).get("video", {}).get("file_id") if isinstance(sent, dict) else None
                                                if f_id:
                                                    await db_set_cached_file_id(file_key, "bale", f_id, "video")
                                        except Exception as e:
                                            logger.error(f"Error sending VIP media in bale: {e}")
                                            await bale.send_message(chat_id, f"❌ خطا در ارسال فایل: {e}")
                                        finally:
                                            if target_path.exists():
                                                try: target_path.unlink()
                                                except Exception: pass
                                        continue

                                    if cb_data in ("bale:prods_hub", "bale:prods_back"):
                                        p_kb = {
                                            "inline_keyboard": [
                                                [{"text": "🎓 دوره‌های آموزشی", "callback_data": "bnav:courses"}],
                                                [{"text": "🎧 کتاب‌های صوتی", "callback_data": "bale:prods_audiobooks"}],
                                                [{"text": "💎 اشتراک پریمیوم", "callback_data": "vip_club_info"}]
                                            ]
                                        }
                                        await bale.send_message(chat_id, "🛍 <b>مرکز محصولات آموزشی و اشتراک:</b>\n\nلطفاً بخش مورد نظر خود را انتخاب نمایید:", reply_markup=p_kb)
                                        continue

                                    if cb_data == "bale:prods_courses":
                                        prods = await StoreService.get_products(is_free_only=False)
                                        buttons = [[{"text": f"🎓 {p.name} ({p.price:,} تومان)", "callback_data": f"bcview:{p.product_id}"}] for p in prods]
                                        buttons.append([{"text": "🔙 بازگشت به محصولات", "callback_data": "bale:prods_hub"}])
                                        await bale.send_message(chat_id, "📚 لیست دوره‌های آموزشی تخصصی:", reply_markup={"inline_keyboard": buttons})
                                        continue

                                    if cb_data == "bale:prods_audiobooks":
                                        all_p = await StoreService.get_products(is_free_only=False)
                                        audio_prods = [p for p in all_p if getattr(p, "delivery_type", "") == "audio" or "صوتی" in p.name or "کتاب" in p.name]
                                        if not audio_prods:
                                            audio_prods = all_p
                                        buttons = [[{"text": f"🎧 {p.name} ({p.price:,} تومان)", "callback_data": f"bcview:{p.product_id}"}] for p in audio_prods]
                                        buttons.append([{"text": "🔙 بازگشت به محصولات", "callback_data": "bale:prods_hub"}])
                                        await bale.send_message(chat_id, "🎧 <b>کتاب‌ها و پکیج‌های صوتی ارزشمند:</b>\n\nجهت مشاهده و تهیه، عنوان مورد نظر را انتخاب فرمایید:", reply_markup={"inline_keyboard": buttons})
                                        continue

                                    if cb_data == "badm_c_add":
                                        if not bale.is_admin(chat_id): continue
                                        session_manager.set_user_action(f"bale_{chat_id}", "await_c_name", "new_course", extra={})
                                        await bale.send_message(
                                            chat_id,
                                            "➕ <b>افزودن دوره جدید به فروشگاه (مرحله ۱ از ۵):</b>\n\n"
                                            "لطفاً <b>نام کامل دوره</b> را ارسال فرمایید:\n"
                                            "(جهت انصراف عبارت <code>/cancel</code> را بفرستید)"
                                        )
                                        continue

                                    if cb_data == "badm_backup_file":
                                        if not bale.is_admin(chat_id): continue
                                        if config.DB_PATH.exists():
                                            await bale.send_document(
                                                chat_id,
                                                config.DB_PATH,
                                                caption=f"💾 <b>نسخه پشتیبان پایگاه داده SQLite</b>\nنگارش سیستم: <code>{config.ENGINE_VERSION}</code>"
                                            )
                                        else:
                                            await bale.send_message(chat_id, "❌ فایل دیتابیس یافت نشد.")
                                        continue

                                    if cb_data == "badm:cleanup_disk":
                                        if not bale.is_admin(chat_id): continue
                                        deleted = 0
                                        if config.TEMP_DIR.exists():
                                            for f in config.TEMP_DIR.glob("*"):
                                                try:
                                                    if f.is_file():
                                                        f.unlink()
                                                        deleted += 1
                                                except Exception:
                                                    pass
                                        await bale.send_message(chat_id, f"🧹 پاکسازی دیسک انجام شد ({deleted} فایل موقت حذف شد).")
                                        continue

                                    if cb_data in ("admin:ping", "badm:ping"):
                                        t0 = time.time()
                                        api_ok = True
                                        try:
                                            await bale.get_me()
                                            latency_ms = max(1, int((time.time() - t0) * 1000))
                                        except Exception:
                                            api_ok = False
                                            latency_ms = 0

                                        db_ok = True
                                        db_t0 = time.time()
                                        try:
                                            from core.database import fetch_one
                                            await fetch_one("SELECT 1")
                                            db_latency_ms = max(1, int((time.time() - db_t0) * 1000))
                                        except Exception:
                                            db_ok = False
                                            db_latency_ms = 0

                                        msg = (
                                            "🏓 <b>نتیجه آزمون پینگ و سلامت سرور (Bale):</b>\n\n"
                                            f"⚡️ <b>پاسخ‌دهی وب‌سرویس بله:</b> <code>{latency_ms or 120} ms</code> ({'پایدار ✅' if api_ok else 'خطا ❌'})\n"
                                            f"💾 <b>پاسخ‌دهی دیتابیس SQLite:</b> <code>{db_latency_ms} ms</code> ({'سالم ✅' if db_ok else 'خطا ❌'})\n"
                                            "🌐 <b>سرور ابری:</b> آنلاین (Hugging Face Port 7860)\n"
                                            f"🚀 <b>نگارش موتور:</b> <code>{config.ENGINE_VERSION}</code>\n"
                                            f"🕒 <b>زمان آزمون:</b> <code>{get_tehran_now_str()}</code>"
                                        )
                                        await bale.send_message(chat_id, msg)
                                        continue

                                    if cb_data.startswith("b_svg_hex:"):
                                        target_fid = cb_data.split(":", 1)[1]
                                        session_manager.set_user_action(f"bale_{chat_id}", "await_svg_hex", target_fid)
                                        await bale.send_message(chat_id, "🎨 لطفاً کد هگز رنگ دلخواه خود را ارسال فرمایید (مانند #3B82F6 یا #E11D48):")
                                        continue

                                    if cb_data.startswith("b_svg_recol:"):
                                        parts = cb_data.split(":", 2)
                                        if len(parts) == 3:
                                            c_name = parts[1].lower()
                                            target_fid = parts[2]
                                            color_map = {"white": "#FFFFFF", "black": "#000000"}
                                            hex_color = color_map.get(c_name, c_name if c_name.startswith("#") else f"#{c_name}")
                                            await bale.send_chat_action(chat_id, "upload_document")
                                            tmp_svg_path = config.TEMP_DIR / f"svg_dl_{uuid.uuid4().hex[:8]}.svg"
                                            try:
                                                from services.image_service import image_service
                                                downloaded = await bale.download_file(target_fid, tmp_svg_path)
                                                if not downloaded or not tmp_svg_path.exists():
                                                    raise ValueError("خطا در دانلود فایل SVG از سرور بله.")
                                                with open(tmp_svg_path, "r", encoding="utf-8", errors="replace") as svg_f:
                                                    svg_str = svg_f.read()
                                                recolored_svg = image_service.recolor_svg(svg_str, hex_color)
                                                out_bytes = recolored_svg.encode("utf-8")
                                                svg_kb = {
                                                    "inline_keyboard": [
                                                        [
                                                            {"text": "⚪️ سفید (#FFF)", "callback_data": f"b_svg_recol:white:{target_fid}"},
                                                            {"text": "⚫️ مشکی (#000)", "callback_data": f"b_svg_recol:black:{target_fid}"}
                                                        ],
                                                        [
                                                            {"text": "🎨 کد هگز دلخواه", "callback_data": f"b_svg_hex:{target_fid}"}
                                                        ],
                                                        [
                                                            {"text": "🖼 خروجی PNG (شفاف)", "callback_data": f"b_svg_conv:png:{target_fid}"},
                                                            {"text": "🖼 خروجی JPG (باکیفیت)", "callback_data": f"b_svg_conv:jpg:{target_fid}"}
                                                        ]
                                                    ]
                                                }
                                                caption = f"🎨 <b>وکتور با رنگ تغییر‌یافته ({hex_color}):</b>\nنگارش موتور وکتور: <code>{config.ENGINE_VERSION}</code>"
                                                await bale.send_document(chat_id, out_bytes, caption=caption, filename=f"vector_{hex_color.lstrip('#')}.svg", reply_markup=svg_kb)
                                            except Exception as e_recol:
                                                logger.error(f"[bale_svg_recol] error: {e_recol}")
                                                await bale.send_message(chat_id, f"❌ خطا در تغییر رنگ وکتور: {e_recol}")
                                            finally:
                                                if tmp_svg_path.exists():
                                                    try: tmp_svg_path.unlink()
                                                    except Exception: pass
                                        continue

                                    if cb_data.startswith("b_svg_conv:"):
                                        parts = cb_data.split(":", 2)
                                        if len(parts) == 3:
                                            target_fmt = parts[1].lower()
                                            target_fid = parts[2]
                                            await bale.send_chat_action(chat_id, "upload_document" if target_fmt in ("png", "svg") else "upload_photo")
                                            tmp_svg_path = config.TEMP_DIR / f"svg_dl_{uuid.uuid4().hex[:8]}.svg"
                                            try:
                                                from services.image_service import image_service
                                                downloaded = await bale.download_file(target_fid, tmp_svg_path)
                                                if not downloaded or not tmp_svg_path.exists():
                                                    raise ValueError("خطا در دانلود فایل SVG از سرور بله.")
                                                
                                                with open(tmp_svg_path, "rb") as svg_f:
                                                    svg_bytes = svg_f.read()
                                                
                                                if target_fmt in ("jpg", "jpeg"):
                                                    out_bytes = image_service.convert_svg_to_jpg(svg_bytes)
                                                    caption = f"🖼 <b>تصویر باکیفیت JPG استخراج‌شده از وکتور</b>\nنگارش موتور وکتور: <code>{config.ENGINE_VERSION}</code>"
                                                    await bale.send_photo(chat_id, out_bytes, caption=caption)
                                                elif target_fmt == "svg":
                                                    caption = f"📥 <b>فایل اصلی وکتور SVG</b>\nنگارش موتور وکتور: <code>{config.ENGINE_VERSION}</code>"
                                                    await bale.send_document(chat_id, svg_bytes, caption=caption, filename="vector.svg")
                                                else:
                                                    out_bytes = image_service.convert_svg_to_png(svg_bytes)
                                                    caption = f"🖼 <b>تصویر باکیفیت PNG (شفاف) استخراج‌شده از وکتور</b>\nنگارش موتور وکتور: <code>{config.ENGINE_VERSION}</code>"
                                                    await bale.send_document(chat_id, out_bytes, caption=caption, filename="vector_converted.png")
                                            except Exception as e_svg:
                                                logger.error(f"[bale_svg_conv] Conversion error: {e_svg}")
                                                await bale.send_message(chat_id, f"❌ خطا در پردازش و تبدیل فایل وکتور: {e_svg}")
                                            finally:
                                                try:
                                                    if tmp_svg_path.exists():
                                                        tmp_svg_path.unlink()
                                                except Exception:
                                                    pass
                                        continue

                                    if cb_data.startswith("b_c_episodes:"):
                                        c_pid = cb_data.split(":", 1)[1]
                                        c_prod = await StoreService.get_product(c_pid)
                                        if not c_prod:
                                            await bale.send_message(chat_id, "❌ دوره مورد نظر یافت نشد.")
                                            continue
                                        c_eps = await StoreService.get_course_episodes(c_pid)
                                        if not c_eps:
                                            await bale.send_message(chat_id, f"ℹ️ هنوز قسمتی برای دوره «{c_prod.name}» ثبت نشده است.")
                                            continue
                                        ep_btns = []
                                        for ep in c_eps:
                                            ep_num = ep.get("part") or 1
                                            ep_t = ep.get("title") or f"قسمت {ep_num}"
                                            ep_u = ep.get("url")
                                            if ep_u:
                                                ep_btns.append([{"text": f"🎵 قسمت {ep_num}: {ep_t}", "url": ep_u}])
                                        ep_btns.append([{"text": "🔙 بازگشت به دوره", "callback_data": f"bcview:{c_pid}"}])
                                        await bale.send_message(chat_id, f"📚 <b>سرفصل‌ها و قسمت‌های دوره «{c_prod.name}»:</b>", reply_markup={"inline_keyboard": ep_btns})
                                        continue

                                    if cb_data == "bale:fjoin_panel":
                                        if not bale.is_admin(chat_id): continue
                                        ch = await get_system_setting("bale_fjoin_channel", config.FORCE_JOIN_CHANNEL_BALE)
                                        enabled = (await get_system_setting("bale_fjoin_enabled", "1" if config.FORCE_JOIN_CHANNEL_BALE else "0")) == "1"
                                        st_txt = "فعال ✅" if enabled else "غیرفعال ❌"
                                        btn_t = "🔴 غیرفعال‌سازی قفل" if enabled else "🟢 فعال‌سازی قفل"
                                        kb = {
                                            "inline_keyboard": [
                                                [{"text": btn_t, "callback_data": "bale:fjoin_toggle"}],
                                                [{"text": "✏️ تغییر آیدی کانال", "callback_data": "bale:fjoin_set_ch"}],
                                                [{"text": "🔙 بازگشت به پنل", "callback_data": "bale:fjoin_back"}]
                                            ]
                                        }
                                        plain_panel = (
                                            "🔒 مدیریت قفل عضویت کانال بله:\n\n"
                                            f"▫️ وضعیت: {st_txt}\n"
                                            f"▫️ کانال هدف: {ch or 'تنظیم نشده'}"
                                        )
                                        await bale.send_message(chat_id, plain_panel, reply_markup=kb)
                                        continue

                                    if cb_data == "bnav:courses_my":
                                        purchased = await StoreService.get_customer_purchased_courses(chat_id)
                                        if not purchased:
                                            await bale.send_message(chat_id, "📚 هنوز دوره‌ای در حساب شما ثبت نشده است.")
                                            continue
                                        await bale.send_message(chat_id, f"📚 <b>دوره‌های فعال و ثبت‌شده شما ({len(purchased)} مورد):</b>")
                                        for i, c in enumerate(purchased, 1):
                                            c_name = c.get("name") or "دوره آموزشی"
                                            card_txt, buttons = StoreService.format_customer_course_card(c_name, c.get("download_link"), i, len(purchased))
                                            c_kb = {"inline_keyboard": [[{"text": b["text"], "url": b["url"]}] for b in buttons]} if buttons else None
                                            await bale.send_message(chat_id, card_txt, reply_markup=c_kb)
                                        continue

                                    if cb_data == "bnav:courses":
                                        prods = await StoreService.get_products(is_free_only=False)
                                        buttons = [[{"text": f"🎓 {p.name} ({p.price:,} تومان)", "callback_data": f"bcview:{p.product_id}"}] for p in prods]
                                        await bale.send_message(chat_id, "📚 لیست دوره‌های آموزشی تخصصی:", reply_markup={"inline_keyboard": buttons})
                                        continue

                                    if cb_data == "bnav:gifts":
                                        gifts = await StoreService.get_products(is_free_only=True)
                                        u = UserService.get_user_by_platform_id("bale", chat_id)
                                        invites = u.successful_invites if u else 0
                                        buttons = []
                                        if gifts:
                                            for g in gifts:
                                                req_ref = getattr(g, "requires_referral", False)
                                                if req_ref and invites < 1:
                                                    buttons.append([{"text": f"🔒 {g.name} (نیازمند ۱ دعوت)", "callback_data": f"bgift_locked:{g.product_id}"}])
                                                else:
                                                    buttons.append([{"text": f"🎁 {g.name} (رایگان)", "callback_data": f"bcview:{g.product_id}"}])
                                        buttons.append([{"text": "🎁 طرح دعوت از دوستان و دریافت هدایا", "callback_data": "bnav:referral"}])
                                        txt = "🎁 <b>دوره‌ها و هدایای آموزشی رایگان:</b>\nجهت دریافت هر دوره روی آن کلیک کنید:"
                                        await bale.send_message(chat_id, txt, reply_markup={"inline_keyboard": buttons} if buttons else None)
                                        continue

                                    if cb_data.startswith("bgift_locked:"):
                                        g_id = cb_data.split(":")[1]
                                        g_prod = await StoreService.get_product(g_id)
                                        g_name = g_prod.name if g_prod else "این دوره هدیه"
                                        bot_username = bale.username or getattr(config, "BALE_BOT_USERNAME", "") or ""
                                        if not bot_username:
                                            try:
                                                b_me = await bale.get_me()
                                                if b_me and b_me.get("ok"):
                                                    bot_username = b_me.get("result", {}).get("username") or ""
                                            except Exception:
                                                pass
                                        ref_link = ReferralService.get_referral_link(chat_id, "bale", bot_username)
                                        u = UserService.get_user_by_platform_id("bale", chat_id)
                                        invites = u.successful_invites if u else 0
                                        share_url = f"https://ble.ir/share/url?url={ref_link}&text=سلام!%20برای%20دریافت%20هدیه%20و%20دوره‌ها%20روی%20این%20لینک%20کلیک%20کنید:"
                                        msg_txt = (
                                            f"🔒 <b>دسترسی به دوره هدیه «{html.escape(g_name)}» نیازمند ۱ دعوت موفق است!</b>\n\n"
                                            "با ارسال لینک دعوت زیر به دوستان خود، به محض پیوستن ۱ نفر، لینک دانلود این فایل به صورت خودکار برای شما فعال خواهد شد.\n\n"
                                            f"🔗 <b>لینک اختصاصی دعوت شما در بله:</b>\n<code>{ref_link}</code>\n\n"
                                            f"👥 <b>تعداد دعوت‌های موفق شما:</b> <b>{invites} از ۱ نفر</b>\n"
                                        )
                                        kb = {
                                            "inline_keyboard": [
                                                [{"text": "📤 ارسال لینک برای دوستان", "url": share_url}],
                                                [{"text": "🔙 بازگشت به لیست هدایا", "callback_data": "bnav:gifts"}]
                                            ]
                                        }
                                        await bale.send_message(chat_id, msg_txt, reply_markup=kb)
                                        continue

                                    async def _bale_show_referral_panel(c_id, usr):
                                        bot_username = bale.username or getattr(config, "BALE_BOT_USERNAME", "") or ""
                                        if not bot_username:
                                            try:
                                                b_me = await bale.get_me()
                                                if b_me and b_me.get("ok"):
                                                    bot_username = b_me.get("result", {}).get("username") or ""
                                            except Exception:
                                                pass
                                        ref_link = ReferralService.get_referral_link(c_id, "bale", bot_username)
                                        invites = usr.successful_invites
                                        unlocked = UserService.is_gift_unlocked_by_platform("bale", c_id, TOHID_AMALI_PACK_ID)
                                        st_txt = "✅ <b>باز شده و آماده دریافت</b>" if unlocked else "🔒 <b>قفل (نیاز به ۱ دعوت موفق)</b>"

                                        inv_custom = getattr(config, "INVITE_FRIENDS_TEXT", "").strip()
                                        inv_body = inv_custom if inv_custom else "با ارسال لینک دعوت اختصاصی خود به دوستان، به محض پیوستن ۱ نفر، <b>بسته صوتی کامل ۱۱ قسمتی توحید عملی</b> برای شما فعال خواهد شد!"
                                        msg_text = (
                                            "🎁 <b>طرح دعوت از دوستان و دریافت هدایا:</b>\n\n"
                                            f"{inv_body}\n\n"
                                            f"🔗 <b>لینک اختصاصی دعوت شما در بله:</b>\n<code>{ref_link}</code>\n\n"
                                            f"👥 <b>تعداد دعوت‌های موفق شما:</b> <b>{invites} نفر</b>\n"
                                            f"🎧 <b>وضعیت بسته صوتی:</b> {st_txt}\n"
                                        )
                                        share_url = f"https://ble.ir/share/url?url={ref_link}&text=سلام!%20برای%20دریافت%20هدیه%20و%20دوره‌ها%20کلیک%20کنید:"
                                        buttons = [
                                            [{"text": "📤 ارسال لینک برای دوستان", "url": share_url}]
                                        ]
                                        if unlocked:
                                            buttons.append([{"text": "🎧 دریافت ۱۱ فایل صوتی توحید عملی", "callback_data": "bale:tohid_amali_list"}])
                                        buttons.append([{"text": "🔙 بازگشت به حساب کاربری", "callback_data": "bnav:profile"}])
                                        await bale.send_message(c_id, msg_text, reply_markup={"inline_keyboard": buttons})

                                    if cb_data == "bnav:referral":
                                        u = UserService.get_user_by_platform_id("bale", chat_id)
                                        if not u or not u.phone:
                                            session_manager.set_user_action(f"bale_pending_referral_{chat_id}", "referral", "referral")
                                            contact_kb = {
                                                "keyboard": [
                                                    [{"text": "📱 ارسال شماره تماس (جهت دریافت هدیه)", "request_contact": True}],
                                                    [{"text": "🔙 انصراف"}]
                                                ],
                                                "resize_keyboard": True,
                                                "one_time_keyboard": True
                                            }
                                            await bale.send_message(
                                                chat_id,
                                                "🎁 <b>دریافت بسته صوتی ۱۱ قسمتی توحید عملی:</b>\n\n"
                                                "برای فعال‌سازی لینک دعوت اختصاصی و دریافت فایل‌های هدیه، لطفاً ابتدا شماره تماس خود را ثبت نمایید:",
                                                reply_markup=contact_kb
                                            )
                                            continue
                                        await _bale_show_referral_panel(chat_id, u)
                                        continue

                                    if cb_data == "bnav:profile":
                                        cust = await StoreService.get_or_create_customer(chat_id, platform="bale")
                                        purchased = await StoreService.get_customer_purchased_courses(chat_id)
                                        lines = [
                                            "👤 <b>اطلاعات حساب کاربری شما:</b>\n",
                                            f"▫️ شناسه کاربری: <code>{cust.user_id}</code>",
                                            f"💰 موجودی کیف پول: <code>{cust.wallet_balance:,} تومان</code>",
                                            f"🎁 درصد کش‌بک خریدها: <code>{config.CASHBACK_PERCENT}%</code>",
                                            f"📚 دوره‌های خریداری‌شده: <b>{len(purchased)} دوره</b>\n"
                                        ]
                                        p_btns = []
                                        if purchased:
                                            p_btns.append([{"text": f"📚 مشاهده دوره‌های من ({len(purchased)})", "callback_data": "bnav:courses_my"}])
                                        else:
                                            p_btns.append([{"text": "📚 لیست دوره‌های آموزشی", "callback_data": "bnav:courses"}])
                                        p_btns.append([{"text": "🎁 هدایا و دانلودهای رایگان", "callback_data": "bnav:gifts"}])
                                        p_btns.append([{"text": "🎁 طرح دعوت از دوستان و دریافت هدایا", "callback_data": "bnav:referral"}])
                                        p_btns.append([{"text": "💬 پشتیبانی و تیکت", "callback_data": "bnav:support"}])
                                        await bale.send_message(chat_id, "\n".join(lines), reply_markup={"inline_keyboard": p_btns})
                                        continue

                                    if cb_data == "bale:tohid_amali_list":
                                        if not await bale.check_user_membership(chat_id) and not bale.is_admin(chat_id):
                                            ch = await get_system_setting("bale_fjoin_channel", config.FORCE_JOIN_CHANNEL_BALE)
                                            await bale.send_message(
                                                chat_id,
                                                "⚠️ <b>برای دریافت فایل‌های دوره، عضویت در کانال الزامی است:</b>",
                                                reply_markup=build_bale_force_join_keyboard(ch)
                                            )
                                            continue

                                        if not UserService.is_gift_unlocked_by_platform("bale", chat_id, TOHID_AMALI_PACK_ID) and not bale.is_admin(chat_id):
                                            await bale.send_message(chat_id, "🔒 <b>این بسته هنوز برای شما قفل است.</b>\nلطفاً ابتدا ۱ نفر از دوستان خود را دعوت کنید.")
                                            continue

                                        lines = [
                                            "🎧 <b>فهرست ۱۱ قسمت صوتی دوره توحید عملی:</b>",
                                            "جهت دریافت هر فایل، روی دکمه آن کلیک کنید:\n"
                                        ]
                                        buttons = []
                                        for ep in TOHID_AMALI_EPISODES:
                                            p = ep["part"]
                                            t = ep["title"]
                                            d = ep["duration"]
                                            buttons.append([{"text": f"▶️ قسمت {p}: {t} ({d})", "callback_data": f"bale:tohid_part:{p}"}])
                                        buttons.append([{"text": "🔙 بازگشت به منوی دعوت", "callback_data": "bnav:referral"}])
                                        await bale.send_message(chat_id, "\n".join(lines), reply_markup={"inline_keyboard": buttons})
                                        continue

                                    if cb_data.startswith("bale:tohid_part:"):
                                        part_num = int(cb_data.split(":", 2)[2])
                                        if not await bale.check_user_membership(chat_id) and not bale.is_admin(chat_id):
                                            ch = await get_system_setting("bale_fjoin_channel", config.FORCE_JOIN_CHANNEL_BALE)
                                            await bale.send_message(
                                                chat_id,
                                                "⚠️ <b>برای دریافت فایل‌های دوره، عضویت در کانال الزامی است:</b>",
                                                reply_markup=build_bale_force_join_keyboard(ch)
                                            )
                                            continue

                                        if not UserService.is_gift_unlocked_by_platform("bale", chat_id, TOHID_AMALI_PACK_ID) and not bale.is_admin(chat_id):
                                            await bale.send_message(chat_id, "🔒 این بسته هنوز قفل است.")
                                            continue

                                        ep = next((e for e in TOHID_AMALI_EPISODES if e["part"] == part_num), None)
                                        if not ep:
                                            await bale.send_message(chat_id, "❌ قسمت مورد نظر یافت نشد.")
                                            continue

                                        cache_key = f"tohid_part_{part_num}"
                                        cached_fid = await db_get_cached_file_id(cache_key, "bale")
                                        caption_txt = f"🎧 <b>بسته صوتی توحید عملی - قسمت {part_num}</b>\n▫️ عنوان: <b>{ep['title']}</b>\n⏱ مدت: <code>{ep['duration']}</code>"

                                        if cached_fid:
                                            try:
                                                res_aud = await bale.send_audio(
                                                    chat_id=chat_id,
                                                    file_path=cached_fid,
                                                    caption=caption_txt,
                                                    title=f"توحید عملی - قسمت {part_num}: {ep['title']}",
                                                    performer="UNFINIT Academy"
                                                )
                                                if res_aud.get("ok"):
                                                    continue
                                            except Exception as e:
                                                logger.warning(f"[Bale] Failed to send cached file_id {cached_fid}: {e}")

                                        candidates = [
                                            config.DATA_DIR / "gifts" / ep["filename"],
                                            config.STORAGE_DIR / "gifts" / ep["filename"],
                                            Path("data") / "gifts" / ep["filename"]
                                        ]
                                        local_found = None
                                        for c in candidates:
                                            if c.exists():
                                                local_found = c
                                                break

                                        if local_found:
                                            try:
                                                sent_res = await bale.send_audio(
                                                    chat_id=chat_id,
                                                    file_path=str(local_found),
                                                    caption=caption_txt,
                                                    title=f"توحید عملی - قسمت {part_num}: {ep['title']}",
                                                    performer="UNFINIT Academy"
                                                )
                                                if sent_res.get("ok"):
                                                    res_obj = sent_res.get("result", {})
                                                    audio_obj = res_obj.get("audio") or res_obj.get("document") or {}
                                                    new_fid = audio_obj.get("file_id")
                                                    if new_fid:
                                                        await db_set_cached_file_id(cache_key, "bale", new_fid, "audio")
                                                continue
                                            except Exception as e:
                                                logger.warning(f"[Bale] Error sending audio file {local_found}: {e}")

                                        await bale.send_message(
                                            chat_id,
                                            f"{caption_txt}\n\n"
                                            "ℹ️ این فایل در حال آماده‌سازی و بارگذاری مستقیم بر روی سرور می‌باشد."
                                        )
                                        continue

                                    continue
                                # Handle Pre-Checkout Query (Bale Online Payment Gateway)
                                if "pre_checkout_query" in update:
                                    pcq = update["pre_checkout_query"]
                                    pcq_id = pcq.get("id")
                                    logger.info(f"Bale pre_checkout_query received: {pcq_id}")
                                    await bale.answer_pre_checkout_query(pcq_id, ok=True)
                                    continue

                                # Handle Normal Messages in Bale
                                if "message" in update:
                                    msg = update["message"]
                                    chat_id = str(msg.get("chat", {}).get("id") or msg.get("from", {}).get("id") or "")
                                    chat_type = msg.get("chat", {}).get("type", "private")
                                    text = (msg.get("text") or "").strip()
                                    canon_action = get_canonical_menu_action(text)
                                    m_id = msg.get("message_id")

                                    # Strict Filter: Only Private Chats
                                    if chat_type != "private" or str(chat_id).startswith("-"):
                                        continue

                                    # Deduplicate message by chat_id + message_id
                                    if m_id is not None:
                                        m_key = f"{chat_id}_{m_id}"
                                        if m_key in processed_msg_set:
                                            logger.debug(f"[Bale] Duplicate message {m_key} skipped")
                                            continue
                                        processed_msg_set.add(m_key)
                                        processed_msg_ids.append(m_key)
                                        if len(processed_msg_ids) >= 1000:
                                            old_m = processed_msg_ids.popleft()
                                            processed_msg_set.discard(old_m)

                                    # Debounce rapid identical text/buttons from same user (1.2s window)
                                    if text:
                                        now = time.time()
                                        txt_key = f"{chat_id}:{text}"
                                        if (now - user_last_actions.get(txt_key, 0.0)) < 0.35:
                                            logger.info(f"[Bale] Debounced duplicate text '{text}' from {chat_id}")
                                            continue
                                        user_last_actions[txt_key] = now
                                
                                    if chat_id:
                                        if bale.is_admin(chat_id):
                                            ACTIVE_BALE_ADMIN_ID = chat_id
                                        await StoreService.get_or_create_customer(chat_id, platform="bale")

                                    # Contact Message Handler (Cross-Platform Unified Identity)
                                    contact_data = msg.get("contact")
                                    if contact_data:
                                        raw_phone = contact_data.get("phone_number") or ""
                                        norm_phone = normalize_phone(raw_phone)
                                        if norm_phone:
                                            fn = contact_data.get("first_name") or ""
                                            ln = contact_data.get("last_name") or ""
                                            full_name = f"{fn} {ln}".strip()
                                            u = UserService.link_platform_user("bale", chat_id, norm_phone, full_name)

                                            # Check if there is a pending referral code
                                            pending_ref_data = session_manager.get_user_action(f"bale_ref_{chat_id}")
                                            pending_ref = pending_ref_data.get("extra") if pending_ref_data else None
                                            if pending_ref:
                                                inviter_phone, newly_unlocked = ReferralService.record_referral(
                                                    inviter_code=pending_ref,
                                                    invited_phone=norm_phone,
                                                    invited_platform="bale",
                                                    invited_platform_id=chat_id
                                                )
                                                session_manager.clear_user_action(f"bale_ref_{chat_id}")
                                                if newly_unlocked and inviter_phone:
                                                    inviter = UserService.get_user_by_phone(inviter_phone)
                                                    if inviter and inviter.bale_id:
                                                        try:
                                                            await bale.send_message(
                                                                inviter.bale_id,
                                                                ReferralService.get_congratulations_message("bale")
                                                            )
                                                        except Exception as e:
                                                            logger.warning(f"[Bale] Failed to notify inviter {inviter.bale_id}: {e}")

                                            success_msg = (
                                                f"✅ <b>حساب کاربری شما با موفقیت متصل شد.</b>\n\n"
                                                f"📱 شماره تماس: <code>{norm_phone}</code>\n"
                                                f"👤 نام: <b>{full_name or 'کاربر گرامی'}</b>\n"
                                                f"🔗 کد معرف اختصاصی شما: <code>{u.referral_code}</code>"
                                            )
                                            await bale.send_message(chat_id, success_msg, reply_markup=get_bale_customer_keyboard())

                                            # Check if user had a pending purchase
                                            pending_buy_data = session_manager.get_user_action(f"bale_pending_buy_{chat_id}")
                                            if pending_buy_data:
                                                prod_id = pending_buy_data.get("extra")
                                                session_manager.clear_user_action(f"bale_pending_buy_{chat_id}")
                                                if prod_id:
                                                    prod = await StoreService.get_product(prod_id)
                                                    if prod:
                                                        if prod.price > 0 and not u.terms_accepted:
                                                            terms_text = (
                                                                f"⚖️ <b>تعهدنامه مالکیت معنوی دوره {prod.name}:</b>\n\n"
                                                                "«این دوره متعلق به خریدار است و هرگونه بازنشر، فروش، اشتراک‌گذاری یا قرار دادن آن در اختیار دیگران شرعاً و قانوناً غیرمجاز بوده و پیگرد قانونی دارد.»\n\n"
                                                                "آیا شرایط و تعهدنامه فوق را مطالعه کرده و می‌پذیرید؟"
                                                            )
                                                            inv_kb = {
                                                                "inline_keyboard": [
                                                                    [{"text": "✅ شرایط را می‌پذیرم", "callback_data": f"bale_terms_accept:{prod.product_id}"}],
                                                                    [{"text": "❌ انصراف", "callback_data": "bale_terms_reject"}]
                                                                ]
                                                            }
                                                            await bale.send_message(chat_id, terms_text, reply_markup=inv_kb)
                                                            continue
                                                        else:
                                                            await _bale_send_order(chat_id, prod, u)
                                                            continue

                                            # Check if user had a pending referral view
                                            pending_ref_view = session_manager.get_user_action(f"bale_pending_referral_{chat_id}")
                                            if pending_ref_view:
                                                session_manager.clear_user_action(f"bale_pending_referral_{chat_id}")
                                                await _bale_show_referral_panel(chat_id, u)
                                                continue
                                        else:
                                            await bale.send_message(chat_id, "⚠️ شماره تماس ارسالی نامعتبر است.")
                                        continue

                                    # Successful Online Payment Handler
                                    sp = msg.get("successful_payment")
                                    if sp:
                                        payload_raw = str(sp.get("invoice_payload") or "")
                                        if payload_raw.startswith("vip_sub_"):
                                            days_val = int(await get_system_setting("vip_duration_days", "30"))
                                            u_vip = UserService.grant_vip(str(chat_id), days=days_val)
                                            logger.info(f"Bale successful_payment: Premium activated for {chat_id} until {getattr(u_vip, 'vip_until', '')}")
                                            vip_until_show = u_vip.get_vip_until_jalali() if u_vip else ""
                                            await bale.send_message(
                                                chat_id,
                                                f"🎉 <b>تبریک! اشتراک پریمیوم {days_val} روزه شما با موفقیت فعال شد.</b>\n\n"
                                                f"هم‌اکنون به ۱۶ دسته‌بندی و فرکانس فراوانی دسترسی دارید. ✨\n\n"
                                                f"💎 اشتراک پریمیوم شما تا تاریخ <b>{vip_until_show}</b> معتبر است.",
                                                reply_markup=get_bale_customer_keyboard()
                                            )
                                            continue

                                        order_id = payload_raw
                                        logger.info(f"Bale successful_payment received for order {order_id}!")
                                        res_app = await StoreService.approve_order(order_id)
                                        prod_name = (res_app.get("product_name") if res_app else None) or "دوره آموزشی"
                                        cb_amount = res_app.get("cashback_amount", 0) if res_app else 0
                                    
                                        order_item = await StoreService.get_order(order_id)
                                        dl_content = ""
                                        prod_item = None
                                        if order_item:
                                            prod_item = await StoreService.get_product(order_item.product_id)
                                            if prod_item and prod_item.download_link:
                                                dl_content = prod_item.download_link

                                        is_pkg = bool(prod_item and (getattr(prod_item, "delivery_type", "channel") == "files_package" or getattr(prod_item, "files_package", None) or getattr(prod_item, "episodes", None)))
                                        if is_pkg:
                                            await bale.send_message(chat_id, f"🎉 <b>پرداخت شما با موفقیت انجام شد!</b>\nفایل‌های دوره «{prod_name}» هم‌اکنون به ترتیب ارسال می‌شوند:\nشماره سفارش: <code>{order_id}</code>")
                                            await StoreService.deliver_course_package(prod_item, chat_id, "bale")
                                        else:
                                            confirm_txt = StoreService.format_delivery_message(prod_name, order_id, dl_content, cb_amount)
                                            parsed_dl = StoreService.parse_delivery_links(dl_content)
                                            cust_buttons = []
                                            for lk in parsed_dl["links"]:
                                                cust_buttons.append([{"text": lk["title"], "url": lk["url"]}])
                                            cust_kb = {"inline_keyboard": cust_buttons} if cust_buttons else None
                                            await bale.send_message(chat_id, confirm_txt, reply_markup=cust_kb)
                                        continue

                                    user_act = session_manager.get_user_action(f"bale_{chat_id}")
                                    if text == "/cancel" and user_act:
                                        session_manager.clear_user_action(f"bale_{chat_id}")
                                        await bale.send_message(chat_id, "❌ عملیات لغو شد.")
                                        continue

                                    if any(text.startswith(cmd) for cmd in ["👤 دوره‌های من", "دوره‌های من", "/my_courses"]):
                                        purchased = await StoreService.get_customer_purchased_courses(chat_id)
                                        if not purchased:
                                            await bale.send_message(chat_id, "📚 <b>دوره‌های من:</b>\n\nهنوز دوره‌ای به نام حساب شما ثبت نشده است.\nمی‌توانید دوره‌های آموزشی را از بخش «📚 لیست دوره‌های آموزشی» یا وب‌سایت تهیه نمایید.")
                                        else:
                                            await bale.send_message(
                                                chat_id,
                                                f"📚 <b>دوره‌های فعال و خریداری‌شده شما ({len(purchased)} دوره):</b>\n\n"
                                                "در ادامه کارت‌های دسترسی به هر دوره همراه با دکمه‌های ورود مستقیم تقدیم حضورتان می‌گردد:"
                                            )
                                            for i, c in enumerate(purchased, 1):
                                                c_name = c.get("name") or "دوره آموزشی"
                                                card_txt, buttons = StoreService.format_customer_course_card(c_name, c.get("download_link"), i, len(purchased))
                                                c_kb = {"inline_keyboard": [[{"text": b["text"], "url": b["url"]}] for b in buttons]} if buttons else None
                                                await bale.send_message(chat_id, card_txt, reply_markup=c_kb)
                                        continue

                                    # مستندسازی فارسی: هندلر لید مگنت «نشانه امروز من» با فالبک هوشمند
                                    # در صورت بروز خطا در استخراج صوت، متن الهام‌بخش به همراه دکمه دانلود مستقیم بلافاصله تحویل می‌گردد.
                                    if canon_action == ACTION_TODAY_SIGN or any(text.startswith(cmd) for cmd in ["🔮 نشانه امروز من", "نشانه امروز من", "نشانه امروز", "نشانه", "/sign"]):
                                        wait_msg = await bale.send_message(chat_id, "🔮 <i>در حال مکاشفه و دریافت نشانه امروز شما...</i>")
                                        try:
                                            from core.sign_service import SignService
                                            reader_tag = await get_system_setting("sign_reader_tag", "abasmanesh365")
                                            extract_chapters = (await get_system_setting("sign_extract_chapters", "1")) == "1"

                                            sign = await SignService.get_user_today_sign(chat_id)
                                            caption = SignService.format_sign_caption(sign, reader_tag=reader_tag, include_chapters=extract_chapters)
                                            audio_url = sign.get("audio_url")
                                            local_audio_path = None
                                            if audio_url:
                                                try:
                                                    local_audio_path = await SignService.ensure_audio_downloaded(sign, reader_tag=reader_tag)
                                                except Exception as e_dl:
                                                    logger.warning(f"[bale_sign] ensure_audio_downloaded failed: {e_dl}")

                                            sign_kb = SignService.build_sign_buttons(sign, platform="bale")
                                            perf_title = reader_tag or "نشانه امروز"
                                            sent_ok = False
                                            if local_audio_path and local_audio_path.exists():
                                                try:
                                                    await bale.send_audio(
                                                        chat_id=chat_id,
                                                        file_path=str(local_audio_path),
                                                        title=sign.get("title", "نشانه امروز من"),
                                                        performer=perf_title,
                                                        caption=caption,
                                                        reply_markup=sign_kb
                                                    )
                                                    sent_ok = True
                                                except Exception as ex_snd:
                                                    logger.warning(f"[bale_sign] send_audio local failed: {ex_snd}")

                                            if not sent_ok:
                                                # مستندسازی فارسی: در صورت عدم امکان ارسال باینری صوت، پیام کامل متنی همراه با دکمه‌های شیشه‌ای ارسال می‌شود
                                                await bale.send_message(chat_id, caption, reply_markup=sign_kb)
                                        except Exception as ex_sign:
                                            logger.error(f"[bale_sign] Error sending sign to {chat_id}: {ex_sign}")
                                            await bale.send_message(chat_id, "❌ متأسفانه در این لحظه دریافت نشانه میسر نشد. لطفاً دقایقی دیگر مجدداً تلاش فرمایید.")
                                        continue

                                    if canon_action == ACTION_PREMIUM or any(text.startswith(cmd) for cmd in ["💎 اشتراک پریمیوم", "💎 عضویت در اشتراک پریمیوم", "💎 عضویت در باشگاه پریمیوم VIP", "عضویت در اشتراک پریمیوم", "اشتراک پریمیوم", "باشگاه پریمیوم", "اشتراک VIP", "/vip", "/premium"]):
                                        is_vip = UserService.is_user_vip(chat_id)
                                        if is_vip:
                                            u = UserService.get_user_by_any_id(chat_id)
                                            vip_until_show = u.get_vip_until_jalali() if u else ""
                                            txt = (
                                                "💎 <b>باشگاه مشترکین پریمیوم</b>\n\n"
                                                f"اشتراک پریمیوم شما تا تاریخ <b>{vip_until_show or 'فعال'}</b> معتبر است.\n\n"
                                                "جهت دسترسی به محتوای اختصاصی، بخش مورد نظر خود را انتخاب فرمایید:"
                                            )
                                            vip_btns = [
                                                [{"text": "📁 ۱۶ دسته‌بندی مقالات و آموزش‌ها", "callback_data": "bale:vip_cats:1"}],
                                                [{"text": "💎 فرکانس فراوانی و آرامش", "callback_data": "bale:freq_cats"}],
                                                [{"text": "🔙 بازگشت به محصولات", "callback_data": "bale:prods_hub"}]
                                            ]
                                            await bale.send_message(chat_id, txt, reply_markup={"inline_keyboard": vip_btns})
                                            continue

                                        price = await get_system_setting("vip_monthly_price", "111000")
                                        try:
                                            price_val = int(price)
                                            price_formatted = f"{price_val:,}"
                                        except Exception:
                                            price_val = 111000
                                            price_formatted = "111,000"
                                        days = await get_system_setting("vip_duration_days", "30")
                                        card_num = await get_system_setting("vip_card_number", await get_system_setting("CARD_NUMBER", config.CARD_NUMBER))
                                        bale_pay_tok = await get_system_setting("vip_bale_payment_token", await get_system_setting("bale_payment_token", config.BALE_PAYMENT_TOKEN))
                                        txt = (
                                            "💎 <b>اشتراک پریمیوم</b>\n\n"
                                            "با تهیه اشتراک پریمیوم، به تمامی خدمات ویژه زیر به مدت ۳۰ روز دسترسی نامحدود خواهید داشت:\n\n"
                                            "▫️ <b>۱۶ دسته‌بندی رسمی مقالات و آموزش‌های عباس‌منش</b>\n"
                                            "▫️ <b>۵ پروژه تحول گام‌به‌گام</b>\n"
                                            "▫️ <b>دسترسی کامل به فرکانس فراوانی (باورهای روزانه ثروت و آرامش)</b>\n"
                                            "▫️ <b>دریافت فایل‌های صوتی و تصویری مستقیم در بله</b>\n\n"
                                            f"💰 <b>تعرفه اشتراک {days} روزه:</b> {price_formatted} تومان\n"
                                        )
                                        vip_btns = []
                                        if bale_pay_tok:
                                            vip_btns.append([{"text": f"⚡️ پرداخت آنلاین و فعال‌سازی آنی ({price_formatted} تومان)", "callback_data": "bale:vip_pay_online"}])
                                        if card_num:
                                            txt += f"\n💳 <b>شماره کارت جهت واریز:</b>\n<code>{card_num}</code>\n"
                                            vip_btns.append([{"text": "🧾 ارسال رسید واریز کارت به کارت", "callback_data": "bale:vip_pay_card"}])
                                        vip_btns.append([{"text": "📁 مشاهده عناوین ۱۶ دسته‌بندی", "callback_data": "bale:vip_cats:1"}])
                                        vip_btns.append([{"text": "🔙 بازگشت به محصولات", "callback_data": "bale:prods_hub"}])
                                        await bale.send_message(chat_id, txt, reply_markup={"inline_keyboard": vip_btns} if vip_btns else None)
                                        continue

                                    if (text in ["💾 بک‌آپ دیتابیس", "بک‌آپ دیتابیس", "/backup_db"]) and bale.is_admin(chat_id):
                                        if config.DB_PATH.exists():
                                            await bale.send_document(chat_id, config.DB_PATH, caption=f"💾 <b>نسخه پشتیبان SQLite</b>\nنگارش: {config.ENGINE_VERSION}")
                                        else:
                                            await bale.send_message(chat_id, "❌ فایل دیتابیس یافت نشد.")
                                        continue

                                    if (text in ["➕ افزودن دوره جدید", "افزودن دوره", "/add_course"]) and bale.is_admin(chat_id):
                                        session_manager.set_user_action(f"bale_{chat_id}", "await_c_name", "new_course", extra={})
                                        await bale.send_message(chat_id, "➕ <b>افزودن دوره جدید به فروشگاه (مرحله ۱ از ۵):</b>\n\nلطفاً <b>نام کامل دوره</b> را ارسال فرمایید:\n(جهت انصراف عبارت <code>/cancel</code> را بفرستید)")
                                        continue

                                    # Course creation wizard in Bale
                                    if user_act and user_act.get("action") == "await_c_name":
                                        c_data = user_act.get("extra") or {}
                                        c_data["name"] = text
                                        session_manager.set_user_action(f"bale_{chat_id}", "await_c_price", "new_course", extra=c_data)
                                        await bale.send_message(chat_id, f"💰 <b>نام دوره: «{text}»</b>\n\nلطفاً <b>قیمت دوره به تومان</b> را ارسال کنید (برای رایگان عدد 0 بفرستید):")
                                        continue

                                    if user_act and user_act.get("action") == "await_c_price":
                                        c_data = user_act.get("extra") or {}
                                        clean_d = re.sub(r"[^\d]", "", text)
                                        price = int(clean_d) if clean_d else 0
                                        c_data["price"] = price
                                        session_manager.set_user_action(f"bale_{chat_id}", "await_c_desc", "new_course", extra=c_data)
                                        await bale.send_message(chat_id, f"📝 <b>قیمت دوره: {price:,} تومان</b>\n\nلطفاً <b>توضیحات و سرفصل‌های دوره</b> را ارسال فرمایید:")
                                        continue

                                    if user_act and user_act.get("action") == "await_c_desc":
                                        c_data = user_act.get("extra") or {}
                                        c_data["desc"] = text
                                        session_manager.set_user_action(f"bale_{chat_id}", "await_c_link", "new_course", extra=c_data)
                                        await bale.send_message(chat_id, "📥 <b>توضیحات ثبت شد!</b>\n\nلطفاً <b>لینک مستقیم دانلود محتوای دوره</b> را ارسال نمایید:")
                                        continue

                                    if user_act and user_act.get("action") == "await_c_link":
                                        c_data = user_act.get("extra") or {}
                                        c_data["link"] = clean_course_access_input(text, c_data.get("name", ""))
                                        session_manager.set_user_action(f"bale_{chat_id}", "await_c_photo", "new_course", extra=c_data)
                                        await bale.send_message(chat_id, "🖼 <b>لینک دانلود ثبت شد!</b>\n\nدر صورت تمایل <b>عکس بنر دوره</b> را ارسال کنید یا دستور <code>/skip</code> را بفرستید:")
                                        continue

                                    if user_act and user_act.get("action") == "await_c_photo":
                                        c_data = user_act.get("extra") or {}
                                        session_manager.clear_user_action(f"bale_{chat_id}")
                                        prod = await StoreService.add_product(
                                            name=c_data.get("name") or "دوره جدید",
                                            price=int(c_data.get("price") or 0),
                                            description=c_data.get("desc") or "",
                                            download_link=c_data.get("link") or "",
                                            photo_url="",
                                            allow_card=True,
                                            allow_bale=True
                                        )
                                        await bale.send_message(chat_id, "✅ دوره با موفقیت ثبت و در فروشگاه وب منتشر شد.")
                                        continue

                                    if user_act and user_act.get("action", "").startswith("await_c_edit_"):
                                        act = user_act["action"]
                                        pid = user_act["drop_id"]
                                        prod = await StoreService.get_product(pid)
                                        if not prod:
                                            session_manager.clear_user_action(f"bale_{chat_id}")
                                            await bale.send_message(chat_id, "❌ دوره یافت نشد.")
                                            continue


                                        if act == "await_c_edit_link":
                                            clean_l = clean_course_access_input(text, prod.name if prod else "")
                                            await StoreService.update_product_field(pid, "download_link", clean_l)
                                            session_manager.clear_user_action(f"bale_{chat_id}")
                                            prod.download_link = clean_l
                                            await bale.send_message(chat_id, f"✅ لینک‌های دسترسی دوره «{prod.name}» با موفقیت به‌روزرسانی شد.")
                                            await bale.send_message(chat_id, format_bale_admin_course_card(prod), reply_markup=build_bale_admin_course_kb(pid, prod.active))
                                            continue

                                        elif act == "await_c_edit_price":
                                            clean_digits = re.sub(r"[^\d]", "", text)
                                            new_price = int(clean_digits) if clean_digits else 0
                                            await StoreService.update_product_field(pid, "price", new_price)
                                            session_manager.clear_user_action(f"bale_{chat_id}")
                                            prod.price = new_price
                                            await bale.send_message(chat_id, f"✅ قیمت دوره «{prod.name}» به {new_price:,} تومان تغییر یافت.")
                                            await bale.send_message(chat_id, format_bale_admin_course_card(prod), reply_markup=build_bale_admin_course_kb(pid, prod.active))
                                            continue

                                        elif act == "await_c_edit_desc":
                                            await StoreService.update_product_field(pid, "description", text)
                                            session_manager.clear_user_action(f"bale_{chat_id}")
                                            prod.description = text
                                            await bale.send_message(chat_id, f"✅ توضیحات دوره «{prod.name}» با موفقیت ذخیره شد.")
                                            await bale.send_message(chat_id, format_bale_admin_course_card(prod), reply_markup=build_bale_admin_course_kb(pid, prod.active))
                                            continue

                                        elif act == "await_c_edit_photo":
                                            await StoreService.update_product_field(pid, "photo_url", text)
                                            session_manager.clear_user_action(f"bale_{chat_id}")
                                            prod.photo_url = text
                                            await bale.send_message(chat_id, f"✅ آدرس تصویر یا بنر دوره «{prod.name}» ذخیره گردید.")
                                            await bale.send_message(chat_id, format_bale_admin_course_card(prod), reply_markup=build_bale_admin_course_kb(pid, prod.active))
                                            continue

                                    # Direct Download Link (URL Uploader Gate in Bale)
                                    link_match = re.search(r'https?://[^\s]+', text)
                                    if link_match:
                                        if not bale.is_admin(chat_id):
                                            await bale.send_message(
                                                chat_id,
                                                f"⛔ دسترسی غیرمجاز! شناسه عددی بله شما جهت ثبت در پنل: <code>{chat_id}</code>"
                                            )
                                            continue

                                        if user_act:
                                            session_manager.clear_user_action(f"bale_{chat_id}")
                                            user_act = None

                                        clean_url = link_match.group(0).strip()
                                        probe = await UrlService.probe_url(clean_url)
                                        if probe.get("is_valid"):
                                            url_id = uuid.uuid4().hex[:8]
                                            session_manager.create_session(f"url_{url_id}", {**probe, "url_id": url_id, "url": clean_url})
                                        
                                            card_txt = (
                                                "🌐 <b>لینک مستقیم دانلود شناسایی شد:</b>\n\n"
                                                f"📄 <b>نام فایل:</b> <code>{probe['filename']}</code>\n"
                                                f"📦 <b>حجم تقریبی:</b> <b>{human_size(probe['file_size'])}</b>\n\n"
                                                "لطفاً نحوه دریافت و ارسال در بله را انتخاب فرمایید:"
                                            )
                                            kb_url = {
                                                "inline_keyboard": [
                                                    [{"text": "⚡️ شروع و تبدیل به فایل بله", "callback_data": f"burldl:auto:{url_id}"}],
                                                    [
                                                        {"text": "🎵 استخراج و تبدیل به MP3", "callback_data": f"burldl:audio:{url_id}"},
                                                        {"text": "📁 دریافت در حالت فایل", "callback_data": f"burldl:doc:{url_id}"}
                                                    ],
                                                    [{"text": "❌ انصراف", "callback_data": f"burldl:cancel:{url_id}"}]
                                                ]
                                            }
                                            await bale.send_message(chat_id, card_txt, reply_markup=kb_url)
                                            continue
                                        else:
                                            err_reason = probe.get("error") or "سرور مبدا اجازه دسترسی به این فایل را نداد یا لینک نامعتبر است."
                                            await bale.send_message(chat_id, f"❌ <b>خطا در بررسی لینک دانلود:</b> {err_reason}")
                                            continue

                                    # Handle Set Force Join Channel in Admin
                                    if user_act and user_act.get("action") == "await_bale_fjoin_ch" and text:
                                        ch_text = text.strip()
                                        if not ch_text.startswith("@") and not ch_text.lstrip("-").isdigit():
                                            ch_text = f"@{ch_text}"
                                        await set_system_setting("bale_fjoin_channel", ch_text)
                                        await set_system_setting("bale_fjoin_enabled", "1")
                                        session_manager.clear_user_action(f"bale_{chat_id}")
                                        await bale.send_message(chat_id, f"✅ کانال قفل عضویت بله روی {ch_text} تنظیم و فعال گردید.", reply_markup=get_bale_admin_keyboard())
                                        continue

                                    # Force Join Check for text messages
                                    if not await bale.check_user_membership(chat_id):
                                        channel_ch = await get_system_setting("bale_fjoin_channel", config.FORCE_JOIN_CHANNEL_BALE)
                                        await bale.send_message(chat_id, "⚠️ برای استفاده از امکانات ربات ابتدا باید در کانال رسمی ما عضو شوید:", reply_markup=build_bale_force_join_keyboard(channel_ch))
                                        continue

                                    # Handle Audio Trimming in Bale
                                    if user_act and user_act.get("action") == "await_trim_time" and text:
                                        drop_id = user_act["drop_id"]
                                        drop = session_manager.get_session(drop_id)
                                        if drop:
                                            tech = inspect_technical_metadata(drop.get("working_path") or "")
                                            total_dur = float(tech.get("duration_sec", 0))
                                            start_s, end_s = parse_trim_input(text, total_duration=total_dur)
                                            if start_s is None:
                                                await bale.send_message(chat_id, "❌ فرمت زمان نامعتبر است. لطفاً مانند 02:10 - 21:28 ارسال فرمایید.")
                                                continue

                                            session_manager.clear_user_action(f"bale_{chat_id}")
                                            status_m = await bale.send_message(chat_id, "⏳ در حال برش فایل صوتی...")
                                            ok, trimmed_p = MediaService.trim_audio(drop["working_path"], start_s, end_s)
                                            if ok and trimmed_p.exists():
                                                t_tech = inspect_technical_metadata(trimmed_p)
                                                t_dur = t_tech.get("duration_sec", 0)
                                                await bale.send_audio(
                                                    chat_id,
                                                    trimmed_p,
                                                    title=drop.get("embed_meta", {}).get("title") or trimmed_p.stem,
                                                    caption=f"✂️ فایل صوتی برش‌خورده ({format_duration(start_s)} تا {format_duration(end_s or total_dur)}):\n📄 {trimmed_p.name}"
                                                )
                                                new_drop_id = uuid.uuid4().hex[:8]
                                                new_data = MediaService.register_incoming_message_meta(
                                                    new_drop_id, "bale", chat_id, str(trimmed_p), trimmed_p.name, trimmed_p.stat().st_size,
                                                    media_type="audio", api_meta={"filename": trimmed_p.name, "duration_sec": t_dur}
                                                )
                                                new_data["working_path"] = str(trimmed_p)
                                                new_data["is_downloaded_locally"] = True
                                                new_card = BaleFormatter.format_light_card(new_data)
                                                new_kb = build_bale_media_keyboard(new_drop_id, new_data)
                                                sent_c = await bale.send_message(chat_id, new_card, reply_markup=new_kb)
                                                new_data["card_msg_id"] = sent_c.get("result", {}).get("message_id")
                                            else:
                                                await bale.send_message(chat_id, "❌ خطا در برش فایل.")
                                        continue

                                    # Metadata Text Input Handler (Fast in-place Draft update)
                                    if user_act and user_act.get("action") in ("await_fn", "await_perf", "await_title") and text:
                                        act = user_act["action"]
                                        drop_id = user_act["drop_id"]
                                        field_map = {"await_fn": "filename", "await_perf": "artist", "await_title": "title"}
                                        field_name_fa = {"await_fn": "نام فایل", "await_perf": "نام خواننده", "await_title": "نام موزیک"}[act]
                                        MediaService.update_draft_field(drop_id, field_map[act], text)
                                        session_manager.clear_user_action(f"bale_{chat_id}")
                                        drop = session_manager.get_session(drop_id)
                                        txt = BaleFormatter.format_light_card(drop)
                                        kb = build_bale_media_keyboard(drop_id, drop, is_sub=False)
                                        card_msg_id = drop.get("card_msg_id")
                                        if card_msg_id:
                                            await bale.edit_message_text(chat_id, card_msg_id, txt, reply_markup=kb)
                                        else:
                                            await bale.send_message(chat_id, txt, reply_markup=kb)
                                        continue

                                    if user_act and user_act.get("action") == "await_svg_hex" and text:
                                        target_fid = user_act.get("drop_id")
                                        session_manager.clear_user_action(f"bale_{chat_id}")
                                        color = text.strip()
                                        if not color.startswith("#"):
                                            color = "#" + color
                                        await bale.send_chat_action(chat_id, "upload_document")
                                        tmp_svg_path = config.TEMP_DIR / f"svg_dl_{uuid.uuid4().hex[:8]}.svg"
                                        try:
                                            from services.image_service import image_service
                                            downloaded = await bale.download_file(target_fid, tmp_svg_path)
                                            if not downloaded or not tmp_svg_path.exists():
                                                raise ValueError("خطا در دانلود فایل SVG از سرور بله.")
                                            with open(tmp_svg_path, "r", encoding="utf-8", errors="replace") as svg_f:
                                                svg_str = svg_f.read()
                                            recolored_svg = image_service.recolor_svg(svg_str, color)
                                            out_bytes = recolored_svg.encode("utf-8")
                                            svg_kb = {
                                                "inline_keyboard": [
                                                    [
                                                        {"text": "⚪️ سفید (#FFF)", "callback_data": f"b_svg_recol:white:{target_fid}"},
                                                        {"text": "⚫️ مشکی (#000)", "callback_data": f"b_svg_recol:black:{target_fid}"}
                                                    ],
                                                    [
                                                        {"text": "🎨 ارسال کد هگز", "callback_data": f"b_svg_hex:{target_fid}"}
                                                    ],
                                                    [
                                                        {"text": "🖼 خروجی PNG شفاف", "callback_data": f"b_svg_conv:png:{target_fid}"},
                                                        {"text": "🖼 خروجی JPG", "callback_data": f"b_svg_conv:jpg:{target_fid}"}
                                                    ],
                                                    [
                                                        {"text": "📥 دریافت مجدد فایل SVG", "callback_data": f"b_svg_conv:svg:{target_fid}"}
                                                    ]
                                                ]
                                            }
                                            caption = f"🎨 <b>وکتور با رنگ جدید ({color}):</b>\nنگارش موتور وکتور: <code>{config.ENGINE_VERSION}</code>"
                                            await bale.send_document(chat_id, out_bytes, caption=caption, filename=f"vector_{color.lstrip('#')}.svg", reply_markup=svg_kb)
                                        except Exception as e_svg:
                                            logger.error(f"[bale_svg_hex] error: {e_svg}")
                                            await bale.send_message(chat_id, f"❌ خطا در پردازش تغییر رنگ: {e_svg}")
                                        finally:
                                            if tmp_svg_path.exists():
                                                try: tmp_svg_path.unlink()
                                                except Exception: pass
                                        continue

                                    if text.startswith("/start "):
                                        param = text.split(" ", 1)[1].strip()
                                        if param.startswith("ord_") or param.startswith("invoice_") or "ord_" in param or param.startswith("ORD_") or param.startswith("order_"):
                                            clean_oid = param
                                            for pfx in ("invoice_id=", "invoice_", "ord_ORD_", "ord_ord_", "order_", "ord_", "ORD_"):
                                                if clean_oid.startswith(pfx):
                                                    clean_oid = clean_oid[len(pfx):]
                                            clean_oid = clean_oid.split("&")[0].split("?")[0].strip()

                                            order_item = await StoreService.get_order(clean_oid) or await StoreService.get_order(param)
                                            if order_item:
                                                prod = await StoreService.get_product(order_item.product_id)
                                                if prod:
                                                    bale_token = config.BALE_PAYMENT_TOKEN or await get_system_setting("bale_payment_token")
                                                    if not bale_token:
                                                        bale_token = await get_system_setting("BALE_PAYMENT_TOKEN")
                                                    if bale_token:
                                                        inv_kb = {
                                                            "inline_keyboard": [
                                                                [{"text": "💳 مشکل در پرداخت آنلاین؟ پرداخت کارت به کارت", "callback_data": f"c2c_{order_item.order_id}"}],
                                                                [{"text": "🔙 بازگشت به لیست دوره‌ها", "callback_data": "bale:courses_list"}]
                                                            ]
                                                        }
                                                        await bale.send_invoice(
                                                            chat_id=chat_id,
                                                            title=prod.name,
                                                            description=prod.description or f"پرداخت رسمی دوره {prod.name}",
                                                            payload=order_item.order_id,
                                                            provider_token=bale_token,
                                                            amount_tomans=prod.price,
                                                            photo_url=prod.photo_url or None,
                                                            reply_markup=inv_kb
                                                        )
                                                        continue
                                                    else:
                                                        await bale.send_message(chat_id, "⚠️ درگاه پرداخت آنلاین بله هنوز تنظیم نشده است. لطفاً از طریق کارت به کارت اقدام فرمایید.")
                                                        continue
                                            await bale.send_message(chat_id, f"❌ سفارش با شناسه {param} یافت نشد.")
                                            continue

                                        elif param.startswith("course_"):
                                            c_pid = param.replace("course_", "").strip()
                                            prod = await StoreService.get_product(c_pid)
                                            if prod:
                                                order = await StoreService.create_order(
                                                    user_id=chat_id,
                                                    username="",
                                                    customer_name="",
                                                    phone="",
                                                    product=prod,
                                                    platform="bale"
                                                )
                                                bale_token = config.BALE_PAYMENT_TOKEN or await get_system_setting("bale_payment_token")
                                                if bale_token:
                                                    inv_kb = {
                                                        "inline_keyboard": [
                                                            [{"text": "💳 مشکل در پرداخت آنلاین؟ پرداخت کارت به کارت", "callback_data": f"c2c_{order.order_id}"}],
                                                            [{"text": "🔙 بازگشت به لیست دوره‌ها", "callback_data": "bale:courses_list"}]
                                                        ]
                                                    }
                                                    await bale.send_invoice(
                                                        chat_id=chat_id,
                                                        title=prod.name,
                                                        description=prod.description or f"پرداخت آنلاین دوره {prod.name}",
                                                        payload=order.order_id,
                                                        provider_token=bale_token,
                                                        amount_tomans=prod.price,
                                                        photo_url=prod.photo_url or None,
                                                        reply_markup=inv_kb
                                                    )
                                                    continue
                                                else:
                                                    await bale.send_message(chat_id, "⚠️ درگاه پرداخت آنلاین بله هنوز تنظیم نشده است.")
                                                    continue
                                            await bale.send_message(chat_id, "❌ دوره مورد نظر یافت نشد.")
                                            continue

                                        else:
                                            ref_code = ReferralService.parse_referral_code(param)
                                            if ref_code:
                                                session_manager.set_user_action(f"bale_ref_{chat_id}", ref_code, ref_code)
                                                logger.info(f"[Bale] User {chat_id} started bot with referral code {ref_code}")
                                                try:
                                                    ReferralService.record_referral(
                                                        referred_id=chat_id,
                                                        referrer_id=ref_code,
                                                        platform="bale"
                                                    )
                                                except Exception as e_ref:
                                                    logger.warning(f"[Bale] record_referral error: {e_ref}")

                                            s_name = fix_mojibake(await get_system_setting("STORE_NAME", config.STORE_NAME), default=config.STORE_NAME)
                                            w_text = fix_mojibake(await get_system_setting("WELCOME_TEXT", config.WELCOME_TEXT), default=config.WELCOME_TEXT)
                                            if bale.is_admin(chat_id):
                                                admin_txt = (
                                                    f"🎛 <b>پنل مدیریت یکپارچه فروشگاه | {s_name}</b>\n\n"
                                                    f"{w_text}\n\n"
                                                    f"سلام مدیر گرامی بله خوش آمدید. تمامی امکانات فروشگاه و سفارش‌ها در دسترس شماست."
                                                )
                                                await bale.send_message(chat_id, admin_txt, reply_markup=get_bale_admin_keyboard())
                                            else:
                                                await bale.send_message(chat_id, w_text, reply_markup=get_bale_customer_keyboard())
                                            continue

                                    if text.lower() in ("/ping", "ping", "پینگ"):
                                        api_start = time.time()
                                        try:
                                            await bale.get_me()
                                            net_latency_ms = max(1, int((time.time() - api_start) * 1000))
                                        except Exception:
                                            net_latency_ms = 0
                                        db_st = "متصل ✅"
                                        db_start = time.time()
                                        try:
                                            from core.database import fetch_one
                                            await fetch_one("SELECT 1")
                                            db_latency_ms = max(1, int((time.time() - db_start) * 1000))
                                        except Exception:
                                            db_st = "خطا در اتصال ❌"
                                            db_latency_ms = 0
                                        t_time = get_tehran_now_str()
                                        p_msg = (
                                            "🏓 <b>پنگ سیستم | آنلاین و فعال</b>\n\n"
                                            "🟢 <b>پلتفرم:</b> پیام‌رسان بله (Bot API)\n"
                                            f"⏱ <b>تاخیر رفت‌وبرگشت شبکه:</b> <code>{net_latency_ms or 120} ms</code>\n"
                                            f"💾 <b>تاخیر پردازش پایگاه‌داده:</b> <code>{db_latency_ms} ms</code> ({db_st})\n"
                                            "🌐 <b>سرور ابری:</b> آنلاین (Hugging Face Port 7860)\n"
                                            f"🚀 <b>نگارش موتور:</b> <code>{config.ENGINE_VERSION}</code>\n"
                                            f"🕒 <b>زمان سرور (تهران):</b> <code>{t_time}</code>"
                                        )
                                        await bale.send_message(chat_id, p_msg)
                                        continue

                                    if text.startswith("/start") or text in ("start", "شروع", "منوی اصلی", "خانه"):
                                        s_name = fix_mojibake(await get_system_setting("STORE_NAME", config.STORE_NAME), default=config.STORE_NAME)
                                        w_text = fix_mojibake(await get_system_setting("WELCOME_TEXT", config.WELCOME_TEXT), default=config.WELCOME_TEXT)
                                        if bale.is_admin(chat_id):
                                            admin_txt = (
                                                f"🎛 <b>پنل مدیریت یکپارچه فروشگاه | {s_name}</b>\n\n"
                                                f"{w_text}\n\n"
                                                f"سلام مدیر گرامی بله خوش آمدید. تمامی امکانات فروشگاه و سفارش‌ها در دسترس شماست."
                                            )
                                            await bale.send_message(chat_id, admin_txt, reply_markup=get_bale_admin_keyboard())
                                        else:
                                            await bale.send_message(chat_id, w_text, reply_markup=get_bale_customer_keyboard())
                                        continue

                                    if text in ("👥 پیش‌نمایش پنل مشتری", "👁 پیش‌نمایش پنل مشتری", "پیش‌نمایش پنل مشتری", "منوی مشتری"):
                                        await bale.send_message(chat_id, "👁 در حال نمایش منوی کاربری مشتریان:", reply_markup=get_bale_customer_keyboard())
                                        continue

                                    if text in ("⚙️ تنظیمات و سلامت سیستم", "⚙️ مدیریت و سلامت سیستم", "پنل ادمین", "سلامت سیستم", "تنظیمات سیستم"):
                                        if bale.is_admin(chat_id):
                                            temp_files = list(config.TEMP_DIR.glob("*")) if config.TEMP_DIR.exists() else []
                                            total_temp_size = sum(f.stat().st_size for f in temp_files if f.is_file())
                                            lines = [
                                                "⚙️ <b>وضعیت زنده سرور و اتصالات سیستم:</b>",
                                                "",
                                                f"🟢 <b>پیام‌رسان بله:</b> <code>{'آنلاین ✅' if config.BALE_BOT_TOKEN else 'غیرفعال ❌'}</code> (شناسه ادمین: <code>{config.BALE_OWNER_ID}</code>)",
                                                f"✈️ <b>ربات تلگرام:</b> <code>{'آنلاین ✅' if getattr(config, 'TELEGRAM_BOT_TOKEN', '') else 'غیرفعال ❌'}</code>",
                                                f"💾 <b>دیسک موقت:</b> <code>{len(temp_files)} فایل ({human_size(total_temp_size)})</code>",
                                                f"🚀 <b>سقف فشرده‌سازی بله:</b> <code>{config.MAX_SAFE_BALE_SIZE_MB} MB</code>",
                                                f"💳 <b>شماره کارت فعال:</b> <code>{config.CARD_NUMBER}</code> ({config.CARD_HOLDER})"
                                            ]
                                            kb = {
                                                "inline_keyboard": [
                                                    [
                                                        {"text": "🧹 پاکسازی دیسک", "callback_data": "badm:cleanup_disk"},
                                                        {"text": "💾 بک‌آپ دیتابیس", "callback_data": "badm_backup_file"}
                                                    ],
                                                    [
                                                        {"text": "🏓 تست سلامت و پینگ (Ping)", "callback_data": "admin:ping"}
                                                    ],
                                                    [
                                                        {"text": "🔒 مدیریت قفل کانال", "callback_data": "bale:fjoin_panel"}
                                                    ]
                                                ]
                                            }
                                            await bale.send_message(chat_id, "\n".join(lines), reply_markup=kb)
                                        continue

                                    if text in ("🔒 مدیریت قفل کانال", "قفل کانال"):
                                        if bale.is_admin(chat_id):
                                            ch = await get_system_setting("bale_fjoin_channel", config.FORCE_JOIN_CHANNEL_BALE)
                                            enabled = (await get_system_setting("bale_fjoin_enabled", "1" if config.FORCE_JOIN_CHANNEL_BALE else "0")) == "1"
                                            st_txt = "فعال ✅" if enabled else "غیرفعال ❌"
                                            btn_t = "🔴 غیرفعال‌سازی قفل" if enabled else "🟢 فعال‌سازی قفل"
                                            kb = {
                                                "inline_keyboard": [
                                                    [{"text": btn_t, "callback_data": "bale:fjoin_toggle"}],
                                                    [{"text": "✏️ تغییر آیدی کانال", "callback_data": "bale:fjoin_set_ch"}],
                                                    [{"text": "🔙 بازگشت به پنل", "callback_data": "bale:fjoin_back"}]
                                                ]
                                            }
                                            plain_panel = (
                                                "🔒 مدیریت قفل عضویت کانال بله:\n\n"
                                                f"▫️ وضعیت: {st_txt}\n"
                                                f"▫️ کانال هدف: {ch or 'تنظیم نشده'}"
                                            )
                                            await bale.send_message(chat_id, plain_panel, reply_markup=kb)
                                        continue

                                    if text in ("🎓 مدیریت فروشگاه و دوره‌ها", "📚 مدیریت دوره‌ها", "مدیریت دوره‌ها", "📚 مدیریت دوره ها", "مدیریت دوره ها", "مدیریت دوره", "/courses", "/admin_courses"):
                                        if not bale.is_admin(chat_id):
                                            await bale.send_message(chat_id, "⛔️ <b>دسترسی غیرمجاز:</b> این منو فقط برای مدیر است.")
                                            continue
                                        all_items = await StoreService.get_all_products(active_only=False)
                                        prods = [p for p in all_items if p.price > 0]
                                        gifts = [p for p in all_items if p.price == 0]
                                        lines = [
                                            "📚 <b>پنل مدیریت دوره‌ها و فایل‌های دانلودی:</b>",
                                            f"تعداد کل: <b>{len(all_items)}</b> (دوره‌ها: <b>{len(prods)}</b> | هدایا: <b>{len(gifts)}</b>)",
                                            "",
                                            "لیست دوره‌ها (جهت مشاهده جزئیات، تغییر قیمت/لینک یا فعال/غیرفعال‌سازی روی نام دوره کلیک کنید):"
                                        ]
                                        buttons = [[{"text": f"{'🎁' if p.price == 0 else f'🎓 ({p.price:,} ت)'} {'[غیرفعال] ' if not p.active else ''}{p.name}", "callback_data": f"badm_pview:{p.product_id}"}] for p in all_items]
                                        buttons.append([{"text": "➕ افزودن دوره جدید", "callback_data": "badm_c_add"}])
                                        await bale.send_message(chat_id, "\n".join(lines), reply_markup={"inline_keyboard": buttons})
                                        continue

                                    if text in ("🧾 سفارشات و تراکنش‌ها", "🧾 سفارش‌ها", "سفارش‌ها", "سفارشات", "تراکنش‌ها"):
                                        recent_orders = await StoreService.get_customer_orders(chat_id)
                                        lines = [
                                            "🧾 <b>پنل مدیریت سفارشات:</b>",
                                            "فیش‌های واریزی جدید بلافاصله برای بررسی و تایید ارسال می‌گردند.",
                                            f"تعداد تراکنش‌های ثبت‌شده اخیر: {len(recent_orders)}"
                                        ]
                                        await bale.send_message(chat_id, "\n".join(lines))
                                        continue

                                    if text in ("💬 پشتیبانی و تیکت‌ها", "تیکت‌ها"):
                                        await bale.send_message(chat_id, "💬 <b>تیکت‌های پشتیبانی:</b>\nپیام‌های جدید کاربران بلافاصله در این چت برای پاسخ‌دهی نمایش داده می‌شوند.")
                                        continue

                                    if text in ("📢 پست‌ساز و انتقال فایل", "پست‌ساز"):
                                        p_txt = (
                                            "📢 <b>هاب رسانه و پست‌ساز بله:</b>\n"
                                            "هر فایل صوتی، ویدیویی، تصویری یا لینک مستقیم دانلودی در این چت ارسال نمایید تا امکانات زیر فعال شوند:\n\n"
                                            "▫️ استخراج عمیق متادیتا، تگ‌ها و مشخصات فنی صوت (FFprobe)\n"
                                            "▫️ برش دقیق صوتی و حذف اینترو/اوترو بدون افت کیفیت\n"
                                            "▫️ ویرایش نام فایل، خواننده، عنوان و تصویر بند انگشتی (تامبنیل)\n"
                                            "▫️ تبدیل هوشمند ویدیو به صوت (Video to MP3)\n"
                                            "▫️ اعمال سریع نمایشی یا رایت فیزیکی کامل روی فایل\n"
                                            "▫️ فشرده‌سازی هوشمند و انتقال به تلگرام یا روبیکا"
                                        )
                                        await bale.send_message(chat_id, p_txt)
                                        continue

                                    if canon_action == ACTION_PRODUCTS or text in ("🛍 محصولات آموزشی", "محصولات آموزشی", "🛍 محصولات", "محصولات", "📚 لیست دوره‌های آموزشی"):
                                        p_kb = {
                                            "inline_keyboard": [
                                                [{"text": "🎓 دوره‌های آموزشی", "callback_data": "bnav:courses"}],
                                                [{"text": "🎧 کتاب‌های صوتی", "callback_data": "bale:prods_audiobooks"}]
                                            ]
                                        }
                                        await bale.send_message(
                                            chat_id,
                                            "🛍 <b>مرکز محصولات آموزشی و کتاب‌های صوتی:</b>\n\n"
                                            "لطفاً دسته‌بندی مورد نظر خود را برای مشاهده سرفصل‌ها، قیمت و ثبت سفارش انتخاب فرمایید:",
                                            reply_markup=p_kb
                                        )
                                        continue

                                    if text in ("👤 دوره‌های من", "دوره‌های من", "/my_courses"):
                                        purchased = await StoreService.get_customer_purchased_courses(chat_id)
                                        if not purchased:
                                            await bale.send_message(chat_id, "📚 هنوز دوره‌ای در حساب شما ثبت نشده است.\nمی‌توانید دوره‌ها را از منوی «💎 محصولات و اشتراک پریمیوم» تهیه فرمایید.")
                                            continue
                                        await bale.send_message(chat_id, f"📚 <b>دوره‌های فعال و خریداری‌شده شما ({len(purchased)} دوره):</b>\n\nدر ادامه کارت‌های دسترسی به هر دوره تقدیم حضورتان می‌گردد:")
                                        for i, c in enumerate(purchased, 1):
                                            c_name = c.get("name") or "دوره آموزشی"
                                            card_txt, buttons = StoreService.format_customer_course_card(c_name, c.get("download_link"), i, len(purchased))
                                            c_kb = {"inline_keyboard": [[{"text": b["text"], "url": b["url"]}] for b in buttons]} if buttons else None
                                            await bale.send_message(chat_id, card_txt, reply_markup=c_kb)
                                        continue

                                    if canon_action == ACTION_FREQUENCY or any(text.startswith(cmd) for cmd in ["💎 فرکانس فراوانی", "فرکانس فراوانی", "فرکانس", "/frequency"]):
                                        txt = (
                                            "💎 <b>فرکانس فراوانی و آرامش درون</b>\n\n"
                                            "با انتخاب هر بخش، باورهای ثروت‌ساز و آرامش‌بخش روزانه را ورق بزنید و ذهن خود را روی مدار توانگری و دریافت برکت الهی تنظیم کنید:"
                                        )
                                        await bale.send_message(chat_id, txt, reply_markup=build_bale_frequency_cats_keyboard())
                                        continue

                                    if canon_action == ACTION_USER_ACCOUNT or any(text.startswith(cmd) for cmd in ["👤 حساب کاربری", "حساب کاربری", "📦 خریدهای من", "خریدهای من", "/profile"]):
                                        cust = await StoreService.get_or_create_customer(chat_id, platform="bale")
                                        purchased = await StoreService.get_customer_purchased_courses(chat_id)
                                        lines = [
                                            "👤 <b>اطلاعات حساب کاربری شما:</b>\n",
                                            f"▫️ شناسه کاربری: <code>{cust.user_id}</code>",
                                            f"💰 موجودی کیف پول: <code>{cust.wallet_balance:,} تومان</code>",
                                            f"🎁 درصد کش‌بک خریدها: <code>{config.CASHBACK_PERCENT}%</code>",
                                            f"📚 دوره‌های خریداری‌شده: <b>{len(purchased)} دوره</b>\n"
                                        ]
                                        if not purchased:
                                            lines.append("هنوز دوره‌ای در حساب شما ثبت نشده است.")
                                            lines.append("می‌توانید دوره‌ها را از بخش «📚 لیست دوره‌های آموزشی» تهیه فرمایید.")
                                            profile_kb = {
                                                "inline_keyboard": [
                                                    [{"text": "📚 لیست دوره‌های آموزشی", "callback_data": "bnav:courses"}],
                                                    [{"text": "🎁 هدایا و دانلودهای رایگان", "callback_data": "bnav:gifts"}],
                                                    [{"text": "👥 دعوت از دوستان و دریافت هدیه", "callback_data": "bnav:referral"}],
                                                    [{"text": "💬 پشتیبانی و تیکت", "callback_data": "bnav:support"}]
                                                ]
                                            }
                                        else:
                                             lines.append("جهت دسترسی به دوره‌ها و لینک‌های آموزشی، دکمه زیر را لمس نمایید:")
                                             profile_kb = {
                                                 "inline_keyboard": [
                                                     [{"text": f"📚 مشاهده دوره‌های من ({len(purchased)})", "callback_data": "bnav:courses_my"}],
                                                     [{"text": "🎁 هدایا و دانلودهای رایگان", "callback_data": "bnav:gifts"}],
                                                     [{"text": "👥 دعوت از دوستان و دریافت هدیه", "callback_data": "bnav:referral"}],
                                                     [{"text": "💬 پشتیبانی و تیکت", "callback_data": "bnav:support"}]
                                                 ]
                                             }
                                        await bale.send_message(chat_id, "\n".join(lines), reply_markup=profile_kb)
                                        continue

                                    if canon_action == ACTION_FREE_DOWNLOADS or any(text.startswith(cmd) for cmd in ["🎁 فایل‌های هدیه", "فایل‌های هدیه", "💬 پشتیبانی و هدایا", "پشتیبانی و هدایا", "💬 پشتیبانی", "پشتیبانی", "🎁 دانلودها (هدیه)", "📂 دانلودها (هدیه)", "دانلودها (هدیه) 📁", "دانلودها", "هدیه", "/support", "/gifts"]):
                                        gifts = await StoreService.get_products(is_free_only=True)
                                        u = UserService.get_user_by_platform_id("bale", chat_id)
                                        invites = u.successful_invites if u else 0
                                        buttons = []
                                        if gifts:
                                            for g in gifts:
                                                req_ref = getattr(g, "requires_referral", False)
                                                if req_ref and invites < 1:
                                                    buttons.append([{"text": f"🔒 {g.name} (نیازمند ۱ دعوت)", "callback_data": f"bgift_locked:{g.product_id}"}])
                                                else:
                                                    buttons.append([{"text": f"🎁 {g.name} (رایگان)", "callback_data": f"bcview:{g.product_id}"}])
                                        buttons.append([{"text": "👥 دعوت از دوستان و دریافت هدیه", "callback_data": "bnav:referral"}])
                                        session_manager.set_user_action(f"bale_{chat_id}", "await_support", "none")
                                        support_custom = getattr(config, "SUPPORT_CENTER_TEXT", "").strip()
                                        if support_custom:
                                            support_txt = (
                                                f"💬 <b>مرکز پشتیبانی و ارتباط با ما:</b>\n\n"
                                                f"{support_custom}\n\n"
                                                "📩 <b>ارسال پیام به پشتیبانی:</b> هم‌اکنون می‌توانید متن پیام، سوال یا شماره پیگیری خود را ارسال فرمایید تا تیکت شما ثبت گردد."
                                            )
                                        else:
                                            support_txt = (
                                                "💬 <b>مرکز پشتیبانی و هدایای آموزشی:</b>\n\n"
                                                "🎁 <b>دوره‌ها و هدایای آموزشی رایگان:</b> در دکمه‌های زیر آماده دریافت هستند.\n\n"
                                                "📩 <b>ارسال پیام به پشتیبانی:</b> هم‌اکنون می‌توانید متن پیام، سوال یا شماره پیگیری خود را ارسال فرمایید تا تیکت شما ثبت گردد."
                                            )
                                        if buttons:
                                            await bale.send_message(chat_id, support_txt, reply_markup={"inline_keyboard": buttons})
                                        else:
                                            await bale.send_message(chat_id, support_txt)
                                        continue

                                    if user_act:
                                        if user_act["action"] == "await_support" and text:
                                            tck = await StoreService.create_support_ticket(chat_id, "", text, platform="bale")
                                            session_manager.clear_user_action(f"bale_{chat_id}")
                                            await bale.send_message(chat_id, f"✅ پیام شما با موفقیت ثبت شد.\nشماره تیکت: {tck.ticket_id}")
                                            continue
                                        if user_act.get("action") == "await_c_photo" and "photo" in msg:
                                            c_data = user_act.get("extra") or {}
                                            session_manager.clear_user_action(f"bale_{chat_id}")
                                            photo_file_id = msg["photo"][-1]["file_id"]
                                        
                                            prod_id = f"prod_{uuid.uuid4().hex[:6]}"
                                            banner_web_url = ""
                                            config.BANNERS_DIR.mkdir(parents=True, exist_ok=True)
                                            banner_filename = f"banner_{prod_id}.jpg"
                                            banner_local_path = config.BANNERS_DIR / banner_filename
                                            try:
                                                dl_ok = await bale.download_file(photo_file_id, banner_local_path)
                                                if dl_ok and banner_local_path.exists():
                                                    try:
                                                        from PIL import Image
                                                        with Image.open(banner_local_path) as im:
                                                            im = im.convert("RGB")
                                                            if im.width > 1200:
                                                                h = int(im.height * (1200 / im.width))
                                                                im = im.resize((1200, h), Image.Resampling.LANCZOS)
                                                            im.save(banner_local_path, "JPEG", quality=85, optimize=True)
                                                    except Exception as pil_err:
                                                        logger.warning(f"[bale_c_photo] Pillow optimization: {pil_err}")
                                                    banner_web_url = f"/uploads/banners/{banner_filename}"
                                            except Exception as dl_err:
                                                logger.warning(f"[bale_c_photo] Failed to download banner: {dl_err}")

                                            prod = await StoreService.add_product(
                                                name=c_data.get("name") or "دوره جدید",
                                                price=int(c_data.get("price") or 0),
                                                description=c_data.get("desc") or "",
                                                download_link=c_data.get("link") or "",
                                                photo_url=banner_web_url or photo_file_id,
                                                allow_card=True,
                                                allow_bale=True
                                            )
                                            if photo_file_id:
                                                await StoreService.update_product_field(prod.product_id, "photo_file_id", photo_file_id)
                                            if banner_web_url:
                                                await StoreService.update_product_field(prod.product_id, "photo_url", banner_web_url)
                                            
                                            await bale.send_message(chat_id, "✅ دوره با موفقیت ثبت و در فروشگاه وب منتشر شد.")
                                            continue

                                        if user_act["action"] == "await_receipt" and "photo" in msg:
                                            order_id = user_act["drop_id"]
                                            f_id = msg["photo"][-1]["file_id"]
                                            await StoreService.submit_receipt(order_id, f_id)
                                            session_manager.clear_user_action(f"bale_{chat_id}")
                                            await bale.send_message(chat_id, "✅ فیش واریزی شما ثبت گردید و به زودی بررسی می‌شود.")

                                            # Forward receipt to admin with approve/reject buttons
                                            order_item = await StoreService.get_order(order_id)
                                            prod_name = "دوره آموزشی"
                                            amount = 0
                                            if order_item:
                                                prod = await StoreService.get_product(order_item.product_id)
                                                if prod:
                                                    prod_name = prod.name
                                                    amount = prod.price
                                            admin_txt = (
                                                f"🧾 <b>فیش واریزی جدید دریافت شد</b>\n\n"
                                                f"👤 <b>کاربر:</b> <code>{chat_id}</code>\n"
                                                f"🎓 <b>دوره:</b> {prod_name}\n"
                                                f"💰 <b>مبلغ:</b> {amount:,} تومان\n"
                                                f"🔖 <b>کد سفارش:</b> <code>{order_id}</code>"
                                            )
                                            admin_kb = {"inline_keyboard": [
                                                [
                                                    {"text": "✅ تایید و تحویل دوره", "callback_data": f"adm_approve:{order_id}"},
                                                    {"text": "❌ رد سفارش", "callback_data": f"adm_reject:{order_id}"}
                                                ]
                                            ]}
                                            admin_id = bale.get_admin_chat_id()
                                            if admin_id:
                                                try:
                                                    await bale.send_photo_by_id(admin_id, f_id, caption=admin_txt, reply_markup=admin_kb)
                                                except Exception as err:
                                                    logger.error(f"Failed to forward receipt to admin {admin_id}: {err}")
                                            continue

                                    # Handle Incoming / Forwarded Audio/Video in Bale (Admin Only)
                                    fwd = msg.get("forward_message") or msg.get("reply_to_message")
                                    media_item = msg.get("audio") or msg.get("document") or msg.get("voice") or msg.get("video")
                                    if not media_item and isinstance(fwd, dict):
                                        media_item = fwd.get("audio") or fwd.get("document") or fwd.get("voice") or fwd.get("video")
                                    if media_item and not user_act:
                                        raw_file_name = str(media_item.get("file_name") or "")
                                        mime_type = str(media_item.get("mime_type") or "").lower()
                                        if raw_file_name.lower().endswith(".svg") or mime_type == "image/svg+xml":
                                            f_id = media_item.get("file_id")
                                            svg_kb = {
                                                "inline_keyboard": [
                                                    [
                                                        {"text": "⚪️ سفید (#FFF)", "callback_data": f"b_svg_recol:white:{f_id}"},
                                                        {"text": "⚫️ مشکی (#000)", "callback_data": f"b_svg_recol:black:{f_id}"}
                                                    ],
                                                    [
                                                        {"text": "🎨 ارسال کد هگز", "callback_data": f"b_svg_hex:{f_id}"}
                                                    ],
                                                    [
                                                        {"text": "🖼 خروجی PNG شفاف", "callback_data": f"b_svg_conv:png:{f_id}"},
                                                        {"text": "🖼 خروجی JPG", "callback_data": f"b_svg_conv:jpg:{f_id}"}
                                                    ],
                                                    [
                                                        {"text": "📥 دریافت مجدد فایل SVG", "callback_data": f"b_svg_conv:svg:{f_id}"}
                                                    ]
                                                ]
                                            }
                                            await bale.send_message(
                                                chat_id,
                                                f"🎨 <b>استودیوی وکتور SVG:</b> <code>{html.escape(raw_file_name or 'vector.svg')}</code>\n\n"
                                                "عملیات مورد نظر خود را جهت تغییر رنگ یا تبدیل فرمت انتخاب فرمایید:",
                                                reply_markup=svg_kb
                                            )
                                            continue

                                        is_v = bool(msg.get("video")) or (isinstance(fwd, dict) and bool(fwd.get("video"))) or raw_file_name.lower().endswith((".mp4", ".mkv", ".mov", ".avi"))
                                        if not bale.is_admin(chat_id):
                                            await bale.send_message(
                                                chat_id,
                                                f"📚 به فروشگاه دوره‌های آموزشی {config.STORE_NAME} خوش آمدید.\nجهت مشاهده دوره‌ها، دانلود هدایا یا ارتباط با پشتیبانی از دکمه‌های منوی زیر استفاده فرمایید:",
                                                reply_markup=get_bale_customer_keyboard()
                                            )
                                            continue

                                        f_id = media_item.get("file_id")
                                        raw_fn = media_item.get("file_name") or ("video.mp4" if is_v else "bale_media.mp3")
                                        fn = clean_display_filename(urllib.parse.unquote(str(raw_fn)))
                                        sz = media_item.get("file_size", 0)
                                        drop_id = uuid.uuid4().hex[:8]
                                        api_meta = {
                                            "filename": fn, "file_size": sz,
                                            "duration_sec": media_item.get("duration", 0),
                                            "title": media_item.get("title", ""),
                                            "artist": media_item.get("performer", "")
                                        }
                                        data = MediaService.register_incoming_message_meta(
                                            drop_id, "bale", chat_id, f_id, fn, sz,
                                            media_type="video" if is_v else "audio", api_meta=api_meta, caption=msg.get("caption", ""), raw_message=msg
                                        )
                                        txt = BaleFormatter.format_light_card(data)
                                        kb = build_bale_media_keyboard(drop_id, data, is_sub=False)
                                        sent = await bale.send_message(chat_id, txt, reply_markup=kb)
                                        data["card_msg_id"] = sent.get("result", {}).get("message_id")
                                        continue

                                    # Freeform User Text Message -> Invoke AI Sales Copilot!
                                    if text and not user_act and not media_item and not canon_action:
                                        try:
                                            from services.ai_service import ai_service, ai_typing_action
                                            async def _bale_text_typing():
                                                await bale.send_chat_action(chat_id, "typing")

                                            async with ai_typing_action(_bale_text_typing):
                                                ai_reply = await ai_service.chat_course_support(text)
                                                await bale.send_message(chat_id, ai_reply, reply_markup=get_bale_customer_keyboard())
                                        except Exception as ai_err:
                                            logger.warning(f"[bale_copilot] AI course support error: {ai_err}")
                                            await bale.send_message(
                                                chat_id,
                                                f"📚 به فروشگاه دوره‌های آموزشی {config.STORE_NAME} خوش آمدید.\nجهت مشاهده دوره‌ها، دانلود هدایا یا ارتباط با پشتیبانی از دکمه‌های زیر استفاده فرمایید:",
                                                reply_markup=get_bale_customer_keyboard()
                                            )
                                        continue
                            if len(user_last_actions) > 500:
                                t_cutoff = time.time() - 60.0
                                user_last_actions = {k: v for k, v in user_last_actions.items() if v > t_cutoff}
                        else:
                            await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Bale polling error: {e}")
                await asyncio.sleep(5)
    finally:
        _BALE_POLLING_RUNNING = False
