import os
import sys
import asyncio
import aiohttp
import json
import uuid
import re
import time
import urllib.parse
import collections
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
from core.config import config
from core.logger import get_logger
from core.formatters import (
    BaleFormatter,
    human_size,
    format_duration,
    parse_trim_input
)
from core.database import get_system_setting, set_system_setting, fix_mojibake
from services.store_service import format_course_links_for_card, format_course_photo_for_card, clean_course_access_input, get_tehran_now_str, StoreService
from services.media_service import MediaService, clean_display_filename
from services.session_manager import session_manager
from services.url_service import UrlService
from media.inspector import inspect_technical_metadata
from media.tagger import extract_cover_image, generate_video_thumbnail

logger = get_logger("bale_adapter")
ACTIVE_BALE_ADMIN_ID: Optional[str] = None
_BALE_POLLING_RUNNING: bool = False

def get_bale_customer_keyboard() -> dict:
    return {
        "keyboard": [
            [{"text": "📚 لیست دوره‌های آموزشی"}],
            [{"text": "👤 حساب کاربری"}],
            [{"text": "💬 پشتیبانی و هدایا"}]
        ],
        "resize_keyboard": True
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

    async def get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(limit=50, keepalive_timeout=60, enable_cleanup_closed=True)
            self._session = aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=25))
        return self._session


    def get_admin_chat_id(self) -> Optional[str]:
        return config.BALE_OWNER_ID or ACTIVE_BALE_ADMIN_ID or "402479514"

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

    async def send_photo(
        self,
        chat_id: str | int,
        photo_path: str | Path,
        caption: Optional[str] = None,
        reply_markup: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if not self.token:
            return {"ok": False, "error": "BALE_BOT_TOKEN missing"}
        path_obj = Path(str(photo_path))
        if not path_obj.exists():
            return {"ok": False, "error": "Photo not found"}
        
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
            with open(path_obj, "rb") as f:
                form.add_field("photo", f, filename=path_obj.name, content_type="image/jpeg")
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
                    async with session.post(url_photo, data=form) as resp:
                        return await resp.json()
        except Exception as e:
            return {"ok": False, "error": str(e)}

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
        file_path: str | Path,
        caption: Optional[str] = None,
        duration: Optional[int] = None,
        width: Optional[int] = None,
        height: Optional[int] = None
    ) -> Dict[str, Any]:
        if not self.token:
            return {"ok": False, "error": "BALE_BOT_TOKEN missing"}
        path_obj = Path(str(file_path))
        if not path_obj.exists():
            return {"ok": False, "error": "Video file not found on disk"}

        clean_send_name = clean_display_filename(urllib.parse.unquote(str(path_obj.name)))
        clean_caption = BaleFormatter.clean_text(urllib.parse.unquote(str(caption))) if caption else None
        url_video = f"{self.base_url}/sendVideo"
        form = aiohttp.FormData(quote_fields=False)
        form.add_field("chat_id", str(chat_id))
        if clean_caption: form.add_field("caption", clean_caption)
        if duration: form.add_field("duration", str(int(duration)))
        if width: form.add_field("width", str(int(width)))
        if height: form.add_field("height", str(int(height)))

        try:
            with open(path_obj, "rb") as f:
                form.add_field("video", f, filename=clean_send_name, content_type="video/mp4")
                timeout = aiohttp.ClientTimeout(total=1800, connect=30)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(url_video, data=form) as resp:
                        res = await resp.json()
                        if res.get("ok"):
                            logger.info(f"Bale sendVideo successful: {res}")
                            return res
                        logger.warning(f"Bale sendVideo returned error: {res}, falling back to sendDocument...")
        except Exception as e:
            logger.warning(f"Bale sendVideo exception: {e}, falling back to sendDocument...")

        # Fallback to sendDocument
        try:
            url_doc = f"{self.base_url}/sendDocument"
            form_doc = aiohttp.FormData(quote_fields=False)
            form_doc.add_field("chat_id", str(chat_id))
            if clean_caption: form_doc.add_field("caption", clean_caption)
            with open(path_obj, "rb") as f:
                form_doc.add_field("document", f, filename=clean_send_name, content_type="application/octet-stream")
                timeout = aiohttp.ClientTimeout(total=1800, connect=30)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(url_doc, data=form_doc) as resp:
                        res_doc = await resp.json()
                        return res_doc
        except Exception as e:
            return {"ok": False, "error": str(e)}

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
        photo_url: Optional[str] = None
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
        file_path: str | Path,
        title: Optional[str] = None,
        performer: Optional[str] = None,
        caption: Optional[str] = None,
        duration: Optional[int] = None
    ) -> Dict[str, Any]:
        if not self.token:
            return {"ok": False, "error": "BALE_BOT_TOKEN missing"}
        
        path_obj = Path(str(file_path))
        url_audio = f"{self.base_url}/sendAudio"

        clean_title = urllib.parse.unquote(str(title)).strip() if title else None
        clean_performer = urllib.parse.unquote(str(performer)).strip() if performer else None
        clean_caption = BaleFormatter.clean_text(urllib.parse.unquote(str(caption))) if caption else None

        if not path_obj.exists():
            payload = {
                "chat_id": str(chat_id),
                "audio": str(file_path)
            }
            if clean_title: payload["title"] = clean_title
            if clean_performer: payload["performer"] = clean_performer
            if clean_caption: payload["caption"] = clean_caption
            if duration: payload["duration"] = int(duration)
            try:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
                    async with session.post(url_audio, json=payload) as resp:
                        return await resp.json()
            except Exception as e:
                return {"ok": False, "error": str(e)}

        clean_send_name = clean_display_filename(urllib.parse.unquote(str(path_obj.name)))
        form = aiohttp.FormData(quote_fields=False)
        form.add_field("chat_id", str(chat_id))
        if clean_title: form.add_field("title", clean_title)
        if clean_performer: form.add_field("performer", clean_performer)
        if clean_caption: form.add_field("caption", clean_caption)
        if duration: form.add_field("duration", str(int(duration)))

        content_type = "audio/mp4" if path_obj.suffix.lower() == ".m4a" else "audio/mpeg"
        
        try:
            with open(path_obj, "rb") as f:
                form.add_field("audio", f, filename=clean_send_name, content_type=content_type)
                timeout = aiohttp.ClientTimeout(total=1800, connect=30)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(url_audio, data=form) as resp:
                        res = await resp.json()
                        if res.get("ok"):
                            logger.info(f"Bale sendAudio successful: {res}")
                            return res
                        logger.warning(f"Bale sendAudio returned error: {res}, attempting fallback to sendDocument...")
        except Exception as e:
            logger.warning(f"Bale sendAudio exception: {e}, attempting fallback to sendDocument...")

        # Fallback to sendDocument
        try:
            url_doc = f"{self.base_url}/sendDocument"
            form_doc = aiohttp.FormData(quote_fields=False)
            form_doc.add_field("chat_id", str(chat_id))
            if clean_caption: form_doc.add_field("caption", clean_caption)
            with open(path_obj, "rb") as f:
                form_doc.add_field("document", f, filename=clean_send_name, content_type="application/octet-stream")
                timeout = aiohttp.ClientTimeout(total=1800, connect=30)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(url_doc, data=form_doc) as resp:
                        res_doc = await resp.json()
                        return res_doc
        except Exception as e:
            logger.error(f"Bale sendDocument fallback error: {e}")
            return {"ok": False, "error": str(e)}

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
                {"text": f"✏️ تغییر نام فایل{fn_check}", "callback_data": f"bmeta:fn:{drop_id}"}
            ],
            [
                {"text": f"🗣 تغییر نام خواننده{perf_check}", "callback_data": f"bmeta:perf:{drop_id}"},
                {"text": f"🎵 تغییر نام موزیک{title_check}", "callback_data": f"bmeta:title:{drop_id}"}
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
            ]
        ]
        return {"inline_keyboard": rows}

    rows = [
        [
            {"text": f"✏️ تغییر نام فایل{fn_check}", "callback_data": f"bmeta:fn:{drop_id}"}
        ],
        [
            {"text": f"🗣 تغییر نام خواننده{perf_check}", "callback_data": f"bmeta:perf:{drop_id}"},
            {"text": f"🎵 تغییر نام موزیک{title_check}", "callback_data": f"bmeta:title:{drop_id}"}
        ],
        [
            {"text": "✂️ برش فایل صوتی", "callback_data": f"bmeta:trim:{drop_id}"},
            {"text": "🧠 دستیار هوش مصنوعی", "callback_data": f"bmeta:ai_transcribe:{drop_id}"}
        ],
        [
            {"text": "📋 اطلاعات تگ‌ها", "callback_data": f"bmeta:tag_details:{drop_id}"},
            {"text": "📊 مشخصات فنی صوت", "callback_data": f"bmeta:audio_specs:{drop_id}"}
        ],
        [
            {"text": f"🖼 تغییر تصویر بند انگشتی{thumb_check}", "callback_data": f"bmeta:change_cov:{drop_id}"}
        ],
        [
            {"text": "📥 دریافت تصویر بند انگشتی", "callback_data": f"bmeta:view_cov:{drop_id}"},
            {"text": "🧹 حذف کامل متادیتا", "callback_data": f"bmeta:strip_tags:{drop_id}"}
        ],
        [
            {"text": "⚡️ اعمال سریع", "callback_data": f"bmeta:quick_send:{drop_id}"},
            {"text": "💾 اعمال تغییرات", "callback_data": f"bmeta:send_back:{drop_id}"}
        ],
        [
            {"text": "✈️ انتقال به تلگرام", "callback_data": f"bmeta:send_tg:{drop_id}"},
            {"text": "🟣 انتقال به روبیکا", "callback_data": f"bmeta:send_rub:{drop_id}"}
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
                                        status_m = await bale.edit_message_text(chat_id, msg_id, "📥 <b>در حال دانلود استریم فایل از لینک مستقیم...</b>")

                                        ok = await UrlService.download_file_stream(url, temp_dest)
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

                                        # Safe 50 MB limit management for Bale
                                        final_send_path = temp_dest
                                        if sz_mb >= 49.0:
                                            orig_size_str = f"{sz_mb:.1f}"
                                            await bale.send_message(
                                                chat_id,
                                                "🎛 <b>در حال فشرده‌سازی هوشمند جهت رعایت سقف بله...</b>\n"
                                                f"📊 حجم فعلی: <code>{orig_size_str} MB</code> ➔ هدف: <code>زیر 49.9 MB</code>\n"
                                                "⚙️ فرآیند بهینه‌سازی صدا و تصویر در حال اجراست، لطفاً شکیبا باشید..."
                                            )
                                            if temp_dest.suffix.lower() in (".mp3", ".m4a", ".wav", ".aac"):
                                                from media.compressor import SmartAudioCompressor
                                                comp_p, _, _, _, was_c = SmartAudioCompressor.compress_if_needed(temp_dest)
                                                if was_c and comp_p.exists():
                                                    final_send_path = comp_p
                                            elif temp_dest.suffix.lower() in (".mp4", ".mkv", ".mov", ".avi", ".webm"):
                                                from media.compressor import SmartVideoCompressor
                                                comp_p, _, _, _, was_c = SmartVideoCompressor.compress_if_needed(temp_dest)
                                                if was_c and comp_p.exists():
                                                    final_send_path = comp_p
                                            await bale.send_message(chat_id, "📤 <b>در حال ارسال به بله...</b>")

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

                                    if cb_data.startswith("bcview:"):
                                        p_id = cb_data.split(":", 1)[1]
                                        prod = await StoreService.get_product(p_id)
                                        if not prod:
                                            await bale.send_message(chat_id, "❌ دوره مورد نظر یافت نشد.")
                                            continue

                                        desc_txt = prod.description or "بدون توضیحات"
                                        price_str = f"{prod.price:,} تومان" if prod.price > 0 else "رایگان 🎁"
                                        dl_txt = f"\n📦 همراه با فایل دانلودی / لینک مستقیم" if prod.download_link else ""
                                        c_card = (
                                            f"🎓 <b>{prod.name}</b>\n\n"
                                            f"▫️ قیمت دوره: <b>{price_str}</b>{dl_txt}\n"
                                            f"▫️ توضیحات کامل:\n{desc_txt}\n\n"
                                            "لطفاً روش پرداخت یا دریافت دوره را انتخاب فرمایید:"
                                        )
                                        c_btns = []
                                        bale_token = config.BALE_PAYMENT_TOKEN or await get_system_setting("bale_payment_token")
                                        if prod.price == 0:
                                            c_btns.append([{"text": "📥 دریافت و دانلود رایگان", "callback_data": f"bpay_free:{prod.product_id}"}])
                                        else:
                                            if prod.allow_bale and bale_token:
                                                c_btns.append([{"text": "💳 پرداخت آنلاین (کیف پول / کارت بله)", "callback_data": f"bpay_online:{prod.product_id}"}])
                                            if prod.allow_card:
                                                c_btns.append([{"text": "💳 پرداخت کارت به کارت (ثبت فیش)", "callback_data": f"bpay_card:{prod.product_id}"}])
                                        c_btns.append([{"text": "🔙 بازگشت به لیست دوره‌ها", "callback_data": "bale:courses_list"}])
                                        await bale.send_message(chat_id, c_card, reply_markup={"inline_keyboard": c_btns})
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
                                        elif action == "ai_transcribe":
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
                                                    send_mp3_p = final_mp3
                                                    if sz_mb >= 49.0:
                                                        orig_size_str = f"{sz_mb:.1f}"
                                                        await bale.send_message(
                                                            chat_id,
                                                            "🎛 <b>در حال فشرده‌سازی هوشمند جهت رعایت سقف بله...</b>\n"
                                                            f"📊 حجم فعلی: <code>{orig_size_str} MB</code> ➔ هدف: <code>زیر 49.9 MB</code>\n"
                                                            "⚙️ فرآیند بهینه‌سازی صدا و تصویر در حال اجراست، لطفاً شکیبا باشید..."
                                                        )
                                                        from media.compressor import SmartAudioCompressor
                                                        comp_p, _, _, _, was_c = SmartAudioCompressor.compress_if_needed(final_mp3)
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
                                                        caption=f"✅ منتقل شده از بله\n📄 {clean_display_filename(fn)}",
                                                        width=tech.get("width"),
                                                        height=tech.get("height"),
                                                        duration=tech.get("duration_sec"),
                                                        thumb=thumb_p
                                                    )
                                                else:
                                                    res = await telegram_adapter_instance.send_audio(
                                                        target_tg_id, final_p, title=info["title"], performer=info["artist"], caption=f"✅ منتقل شده از بله\n📄 {clean_display_filename(fn)}"
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
                                                    caption=f"✅ منتقل شده از بله\n📄 {clean_display_filename(fn)}"
                                                )
                                                if res.get("ok") or res.get("status") == "OK":
                                                    await bale.send_message(chat_id, f"✅ فایل با موفقیت به روبیکا منتقل شد!\n📄 {clean_display_filename(fn)}")
                                                else:
                                                    await bale.send_message(chat_id, f"❌ خطا در ارسال به روبیکا: {res.get('error') or res}")

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

                                        from services.ai_agent_service import ai_agent_service
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
                                        buttons = [[{"text": f"🎁 {g.name} (رایگان)", "callback_data": f"bcview:{g.product_id}"}] for g in gifts] if gifts else []
                                        txt = "🎁 <b>دوره‌ها و هدایای آموزشی رایگان:</b>\nجهت دریافت هر دوره روی آن کلیک کنید:"
                                        await bale.send_message(chat_id, txt, reply_markup={"inline_keyboard": buttons} if buttons else None)
                                        continue

                                    if cb_data == "bnav:support":
                                        session_manager.set_user_action(f"bale_{chat_id}", "await_support", "none")
                                        await bale.send_message(chat_id, "💬 <b>ارسال پیام به پشتیبانی:</b>\nلطفاً پیام یا سوال خود را ارسال فرمایید تا تیکت شما ثبت گردد:")
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

                                    # Successful Online Payment Handler
                                    sp = msg.get("successful_payment")
                                    if sp:
                                        order_id = sp.get("invoice_payload")
                                        logger.info(f"Bale successful_payment received for order {order_id}!")
                                        res_app = await StoreService.approve_order(order_id)
                                        prod_name = (res_app.get("product_name") if res_app else None) or "دوره آموزشی"
                                        cb_amount = res_app.get("cashback_amount", 0) if res_app else 0
                                    
                                        order_item = await StoreService.get_order(order_id)
                                        dl_content = ""
                                        if order_item:
                                            prod_item = await StoreService.get_product(order_item.product_id)
                                            if prod_item and prod_item.download_link:
                                                dl_content = prod_item.download_link

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
                                    if (text.startswith("http://") or text.startswith("https://")) and bale.is_admin(chat_id) and not user_act:
                                        probe = await UrlService.probe_url(text)
                                        if probe["is_valid"]:
                                            url_id = uuid.uuid4().hex[:8]
                                            session_manager.create_session(f"url_{url_id}", {**probe, "url_id": url_id})
                                        
                                            card_txt = (
                                                "🌐 لینک مستقیم دانلود شناسایی شد:\n\n"
                                                f"📄 نام فایل: {probe['filename']}\n"
                                                f"📦 حجم تقریبی: {human_size(probe['file_size'])}\n\n"
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
                                                        await bale.send_invoice(
                                                            chat_id=chat_id,
                                                            title=prod.name,
                                                            description=prod.description or f"پرداخت رسمی دوره {prod.name}",
                                                            payload=order_item.order_id,
                                                            provider_token=bale_token,
                                                            amount_tomans=prod.price,
                                                            photo_url=prod.photo_url or None
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
                                                    await bale.send_invoice(
                                                        chat_id=chat_id,
                                                        title=prod.name,
                                                        description=prod.description or f"پرداخت آنلاین دوره {prod.name}",
                                                        payload=order.order_id,
                                                        provider_token=bale_token,
                                                        amount_tomans=prod.price,
                                                        photo_url=prod.photo_url or None
                                                    )
                                                    continue
                                                else:
                                                    await bale.send_message(chat_id, "⚠️ درگاه پرداخت آنلاین بله هنوز تنظیم نشده است.")
                                                    continue
                                            await bale.send_message(chat_id, "❌ دوره مورد نظر یافت نشد.")
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
                                            f"🕒 <b>زمان سرور (تهران):</b> <code>{t_time}</code>"
                                        )
                                        await bale.send_message(chat_id, p_msg)
                                        continue

                                    if text in ("/start", "start", "شروع", "منوی اصلی", "خانه"):
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
                                                f"✈️ <b>ربات تلگرام:</b> <code>{'آنلاین ✅' if config.BOT_TOKEN else 'غیرفعال ❌'}</code>",
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

                                    if text == "📚 لیست دوره‌های آموزشی":
                                        prods = await StoreService.get_products(is_free_only=False)
                                        buttons = [[{"text": f"🎓 {p.name} ({p.price:,} تومان)", "callback_data": f"bcview:{p.product_id}"}] for p in prods]
                                        await bale.send_message(chat_id, "📚 لیست دوره‌های آموزشی تخصصی:", reply_markup={"inline_keyboard": buttons})
                                        continue

                                    if text in ("👤 دوره‌های من", "دوره‌های من", "/my_courses"):
                                        purchased = await StoreService.get_customer_purchased_courses(chat_id)
                                        if not purchased:
                                            await bale.send_message(chat_id, "📚 هنوز دوره‌ای در حساب شما ثبت نشده است.\nمی‌توانید دوره‌ها را از منوی «📚 لیست دوره‌های آموزشی» تهیه فرمایید.")
                                            continue
                                        await bale.send_message(chat_id, f"📚 <b>دوره‌های فعال و خریداری‌شده شما ({len(purchased)} دوره):</b>\n\nدر ادامه کارت‌های دسترسی به هر دوره تقدیم حضورتان می‌گردد:")
                                        for i, c in enumerate(purchased, 1):
                                            c_name = c.get("name") or "دوره آموزشی"
                                            card_txt, buttons = StoreService.format_customer_course_card(c_name, c.get("download_link"), i, len(purchased))
                                            c_kb = {"inline_keyboard": [[{"text": b["text"], "url": b["url"]}] for b in buttons]} if buttons else None
                                            await bale.send_message(chat_id, card_txt, reply_markup=c_kb)
                                        continue

                                    if any(text.startswith(cmd) for cmd in ["👤 حساب کاربری", "حساب کاربری", "📦 خریدهای من", "خریدهای من", "/profile"]):
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
                                                    [{"text": "💬 پشتیبانی و تیکت", "callback_data": "bnav:support"}]
                                                ]
                                            }
                                        else:
                                            lines.append("جهت دسترسی به دوره‌ها و لینک‌های آموزشی، دکمه زیر را لمس نمایید:")
                                            profile_kb = {
                                                "inline_keyboard": [
                                                    [{"text": f"📚 مشاهده دوره‌های من ({len(purchased)})", "callback_data": "bnav:courses_my"}],
                                                    [{"text": "🎁 هدایا و دانلودهای رایگان", "callback_data": "bnav:gifts"}],
                                                    [{"text": "💬 پشتیبانی و تیکت", "callback_data": "bnav:support"}]
                                                ]
                                            }
                                        await bale.send_message(chat_id, "\n".join(lines), reply_markup=profile_kb)
                                        continue

                                    if any(text.startswith(cmd) for cmd in ["💬 پشتیبانی و هدایا", "پشتیبانی و هدایا", "💬 پشتیبانی", "پشتیبانی", "🎁 دانلودها (هدیه)", "دانلودها", "هدیه", "/support", "/gifts"]):
                                        gifts = await StoreService.get_products(is_free_only=True)
                                        buttons = []
                                        if gifts:
                                            buttons = [[{"text": f"🎁 {g.name} (رایگان)", "callback_data": f"bcview:{g.product_id}"}] for g in gifts]
                                        session_manager.set_user_action(f"bale_{chat_id}", "await_support", "none")
                                        support_txt = (
                                            "💬 <b>مرکز پشتیبانی و هدایای آموزشی:</b>\n\n"
                                            "🎁 <b>دوره‌های هدیه و رایگان:</b> در دکمه‌های زیر آماده دریافت هستند.\n\n"
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
                                                    {"text": "✅ تایید سفارش و ارسال دوره", "callback_data": f"adm_approve:{order_id}"},
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

                                    # Handle Incoming Audio/Video in Bale (Admin Only)
                                    media_item = msg.get("audio") or msg.get("document") or msg.get("voice") or msg.get("video")
                                    if media_item and not user_act:
                                        raw_file_name = str(media_item.get("file_name") or "")
                                        is_v = bool(msg.get("video")) or raw_file_name.lower().endswith((".mp4", ".mkv", ".mov", ".avi"))
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
                                    if text and not user_act and not media_item:
                                        try:
                                            from services.ai_agent_service import ai_agent_service
                                            ai_reply = await ai_agent_service.chat_course_support(text)
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
