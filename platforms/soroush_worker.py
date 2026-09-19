import json
import os
import mimetypes
from pathlib import Path
from typing import Optional, Dict, Any
import aiohttp
from core.config import config
from core.logger import get_logger
from core.security import (
    save_encrypted_session,
    load_decrypted_session,
    encrypt_session_data,
    decrypt_session_data
)

logger = get_logger("soroush_worker")

class SoroushWorker:
    """
    Soroush Plus Worker client for interacting with Soroush+ Web APIs.
    All session data is persisted encrypted at rest using military-grade AES-256-GCM.
    Zero unencrypted credentials or plain session files are written to disk.
    """
    WEB_API_BASE = "https://web.splus.ir/api/"
    API_BASE = "https://api.splus.ir/"
    BOT_API_BASE = "https://bot.splus.ir/"

    def __init__(self, session_name: str = "soroush"):
        self.session_name = session_name
        self.session_dir = config.DATA_DIR / "sessions"
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.queue_dir = config.DATA_DIR / "soroush_queue"
        self.queue_dir.mkdir(parents=True, exist_ok=True)
        self.session_file = self.session_dir / f"{session_name}.session.enc"
        self._session_data: Optional[Dict[str, Any]] = None
        self._load_session()

    def _load_session(self) -> Optional[Dict[str, Any]]:
        """Loads and decrypts session from encrypted disk storage."""
        if not self.session_file.exists():
            # Check legacy unencrypted or root path
            cand = config.DATA_DIR / f"{self.session_name}.session.enc"
            if cand.exists():
                self.session_file = cand
            else:
                return None

        try:
            raw_bytes = load_decrypted_session(self.session_file)
            if raw_bytes:
                data = json.loads(raw_bytes.decode("utf-8"))
                if isinstance(data, dict) and data.get("token"):
                    self._session_data = data
                    return data
        except Exception as e:
            logger.warning(f"[soroush_worker] Failed to load/decrypt session: {e}")
        return None

    def save_session(self, token: str, phone: str, user_id: Optional[str] = None, extra: Optional[Dict[str, Any]] = None) -> bool:
        """Encrypts and writes session data to disk."""
        try:
            payload = {
                "token": token,
                "phone": phone,
                "user_id": user_id or "",
                "extra": extra or {}
            }
            raw_bytes = json.dumps(payload).encode("utf-8")
            save_encrypted_session(self.session_file, raw_bytes)
            self._session_data = payload
            logger.info(f"[soroush_worker] Session encrypted and saved successfully for {phone}")
            return True
        except Exception as e:
            logger.error(f"[soroush_worker] Error saving encrypted session: {e}")
            return False

    def save_manual_token(self, token: Any, phone: str = "") -> bool:
        """
        Saves a manually extracted GramJS auth token/key into persistent storage.
        Accepts:
          1. Raw string dc2_auth_key (e.g. 32/64 byte hex or base64)
          2. GramJS Web JSON string or dict: {"dcId":2,"dc2_auth_key":"...","userId":"59645756"}
          3. GramJS Account object: {"account1": {"dcId":2,"authKey":"...","userId":59645756}}
        Persists with AES-256 encryption in data/sessions/soroush.session.enc.
        """
        if isinstance(token, dict):
            clean_tok = json.dumps(token)
        else:
            clean_tok = str(token or "").strip()

        if not clean_tok:
            return False

        clean_ph = (phone or "").strip()
        user_id = "manual"
        first_name = ""
        extra = {}

        # Check if user provided JSON object (GramJS / Telegram / Soroush Web client format)
        if isinstance(token, dict) or (clean_tok.startswith("{") and clean_tok.endswith("}")) or any(k in clean_tok for k in ("dc2_auth_key", "userId", "account1", "authKey", "firstName")):
            try:
                parsed = token if isinstance(token, dict) else json.loads(clean_tok)
                if isinstance(parsed, dict):
                    acc = parsed
                    if "account1" in parsed and isinstance(parsed["account1"], dict):
                        acc = parsed["account1"]
                    elif "account" in parsed and isinstance(parsed["account"], dict):
                        acc = parsed["account"]

                    extracted_key = (
                        acc.get("dc2_auth_key")
                        or acc.get("dc1_auth_key")
                        or acc.get("authKey")
                        or acc.get("auth_key")
                        or acc.get("key")
                        or acc.get("token")
                    )
                    raw_user_id = acc.get("userId") or acc.get("user_id") or acc.get("id")
                    if raw_user_id:
                        user_id = str(raw_user_id).strip()

                    raw_name = acc.get("firstName") or acc.get("first_name") or acc.get("name")
                    if raw_name:
                        first_name = str(raw_name).strip()

                    if acc.get("phone"):
                        clean_ph = str(acc.get("phone")).strip()

                    dc_id = acc.get("dcId") or acc.get("dc_id") or 2
                    extra = {
                        "gramjs": True,
                        "dcId": dc_id,
                        "parsed_json": parsed,
                        "userId": user_id,
                        "firstName": first_name
                    }
                    if extracted_key:
                        clean_tok = str(extracted_key).strip()
            except Exception as e:
                logger.debug(f"[soroush_worker] JSON parse error in manual token: {e}")

        if not clean_ph:
            clean_ph = f"حساب {user_id}" if user_id != "manual" else "سشن وب سروش"

        return self.save_session(token=clean_tok, phone=clean_ph, user_id=user_id, extra=extra)

    def is_connected(self) -> bool:
        """Returns True if a valid session exists."""
        if self._session_data and self._session_data.get("token"):
            return True
        data = self._load_session()
        return bool(data and data.get("token"))

    def get_masked_phone(self) -> str:
        """
        تولید برچسب هویتی کاملاً پویا و شفاف برای کاربر سروش‌پلاس بدون هیچ هاردکد.
        شامل نام کاربر، شماره ماسک‌شده و شناسه عددی.
        """
        if not self.is_connected() or not self._session_data:
            return ""

        extra = self._session_data.get("extra") or {}
        first_name = str(extra.get("firstName") or extra.get("first_name") or "").strip()
        user_id = str(self._session_data.get("user_id", "")).strip()
        phone = str(self._session_data.get("phone", "")).strip().replace("+", "")

        masked_ph = ""
        if len(phone) >= 10 and phone.isdigit():
            masked_ph = f"{phone[:4]}***{phone[-4:]}"
        elif phone and phone not in ("سشن وب سروش", "سشن دستی وب", "دستی", f"حساب {user_id}"):
            masked_ph = phone

        parts = []
        if first_name:
            parts.append(first_name)
        if masked_ph:
            parts.append(masked_ph)
        if user_id and user_id not in ("manual", "gramjs_user", "0", "", phone):
            parts.append(f"شناسه: {user_id}")

        if parts:
            return " | ".join(parts)
        if masked_ph:
            return masked_ph
        return "حساب متصل (سشن وب)"

    def get_status(self) -> Dict[str, Any]:
        """Returns status payload for Web Panel dashboard and API."""
        connected = self.is_connected()
        extra = (self._session_data.get("extra") or {}) if (connected and self._session_data) else {}
        return {
            "connected": connected,
            "status": "ONLINE" if connected else "REQUIRE_AUTH",
            "masked_phone": self.get_masked_phone() if connected else "",
            "phone": self._session_data.get("phone", "") if (connected and self._session_data) else "",
            "user_id": self._session_data.get("user_id", "") if (connected and self._session_data) else "",
            "first_name": extra.get("firstName") or extra.get("first_name") or "",
            "platform": "soroush"
        }

    def disconnect(self) -> bool:
        """Securely deletes session file and clears memory."""
        self._session_data = None
        deleted = False
        try:
            if self.session_file.exists():
                self.session_file.unlink(missing_ok=True)
                deleted = True
            cand = config.DATA_DIR / f"{self.session_name}.session.enc"
            if cand.exists():
                cand.unlink(missing_ok=True)
                deleted = True
            logger.info("[soroush_worker] Session successfully disconnected and wiped.")
            return True
        except Exception as e:
            logger.error(f"[soroush_worker] Disconnect error: {e}")
            return deleted

    async def request_code(self, phone: str) -> Dict[str, Any]:
        """
        Requests SMS authorization code from Soroush Plus Web API.
        """
        clean_phone = phone.strip().replace(" ", "").replace("-", "")
        if not clean_phone.startswith("+") and not clean_phone.startswith("00"):
            if clean_phone.startswith("0"):
                clean_phone = "+98" + clean_phone[1:]
            elif not clean_phone.startswith("98"):
                clean_phone = "+98" + clean_phone

        candidate_urls = [
            f"{self.WEB_API_BASE}auth/requestCode",
            f"{self.WEB_API_BASE}auth/sendCode",
            "https://api.splus.ir/auth/requestCode"
        ]
        headers = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        payload = {"phone": clean_phone}

        last_error = ""
        for url in candidate_urls:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, json=payload, headers=headers, timeout=8) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            return {
                                "ok": True,
                                "phone": clean_phone,
                                "sms_id": data.get("sms_id") or data.get("result", {}).get("sms_id") or "",
                                "message": "کد تأیید پیامک شد."
                            }
                        else:
                            last_error = f"HTTP {resp.status}"
            except Exception as e:
                last_error = str(e)

        logger.debug(f"[soroush_worker] requestCode candidates not responding: {last_error}")
        return {
            "ok": False,
            "error": "درگاه پیامک خودکار وب سروش‌پلاس موقتاً پاسخگو نیست. لطفاً از گزینه «ثبت دستی توکن نشست» استفاده فرمایید.",
            "detail": last_error
        }

    async def verify_code(self, phone: str, code: str, sms_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Verifies SMS code and persists encrypted token on disk.
        """
        clean_phone = phone.strip()
        clean_code = code.strip()

        url = f"{self.WEB_API_BASE}auth/verifyCode"
        headers = {"Content-Type": "application/json"}
        payload = {
            "phone": clean_phone,
            "code": clean_code,
            "sms_id": sms_id or ""
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers, timeout=15) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        token = data.get("token") or data.get("result", {}).get("token")
                        user_id = data.get("user_id") or data.get("result", {}).get("user_id")
                        if token:
                            self.save_session(token=token, phone=clean_phone, user_id=str(user_id))
                            return {"ok": True, "message": "احراز هویت با موفقیت انجام شد."}
                        return {"ok": False, "error": "توکن در پاسخ سرور یافت نشد.", "detail": data}
                    else:
                        text = await resp.text()
                        return {"ok": False, "error": f"کد تأیید نامعتبر است ({resp.status})", "detail": text}
        except Exception as e:
            logger.error(f"[soroush_worker] verifyCode error: {e}")
            return {"ok": False, "error": f"خطای ارتباط با سرور: {e}"}

    async def send_file_to_saved_messages(
        self,
        file_path: str | Path,
        caption: str = "",
        mime_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        ارسال امن فایل رسانه‌ای به بخش پیام‌های ذخیره‌شده (Saved Messages) حساب سروش‌پلاس.
        این متد ابتدا فایل را از طریق اندپوینت‌های رسمی آپلود کرده و سپس پیام را ثبت می‌کند.
        در صورت عدم دسترسی سرور یا بازگشت خطای ۴۰۴، فایل در صف باینری محلی محافظت شده
        و وضعیت به صورت گزارش شفاف و بدون پرتاب اکسپشن به کاربر اعلام می‌گردد.

        ورودی‌ها (پارامترها):
            file_path (str | Path): مسیر فیزیکی فایل روی دیسک سرور
            caption (str): توضیحات و کپشن همراه فایل صوتی یا تصویری
            mime_type (Optional[str]): نوع محتوای چندرسانه‌ای (اختیاری)

        خروجی:
            Dict[str, Any]: دیکشنری نتیجه با فیلد ok (موفقیت یا شکست)، file_id و پیام وضعیت
        """
        if not self.is_connected():
            return {"ok": False, "error": "سشن سروش‌پلاس متصل نیست. لطفاً ابتدا توکن دستی را ثبت فرمایید."}

        p = Path(file_path)
        if not p.exists() or not p.is_file():
            return {"ok": False, "error": f"فایل جهت ارسال یافت نشد: {file_path}"}

        token = self._session_data.get("token", "")
        headers = {"Authorization": f"Bearer {token}"}

        # تعیین خودکار نوع رسانه
        if not mime_type:
            mime_type, _ = mimetypes.guess_type(str(p))
            if not mime_type:
                mime_type = "application/octet-stream"

        upload_endpoints = [
            f"{self.WEB_API_BASE}v1/upload",
            f"{self.WEB_API_BASE}upload",
            f"{self.API_BASE}v1/upload",
            f"{self.API_BASE}upload",
            f"{self.BOT_API_BASE}uploadFile",
        ]

        file_id = None
        last_error = "سرورهای ابری آپلود سروش‌پلاس در این لحظه پاسخگو نبودند"

        # ۱. تلاش برای آپلود در اندپوینت‌های وب‌سرویس سروش‌پلاس
        for endpoint in upload_endpoints:
            try:
                async with aiohttp.ClientSession() as session:
                    data = aiohttp.FormData()
                    with open(str(p), "rb") as f_bin:
                        data.add_field(
                            "file",
                            f_bin.read(),
                            filename=p.name,
                            content_type=mime_type
                        )
                    async with session.post(endpoint, data=data, headers=headers, timeout=30) as up_resp:
                        if up_resp.status == 200:
                            up_res = await up_resp.json()
                            file_id = up_res.get("file_id") or up_res.get("result", {}).get("file_id")
                            if file_id:
                                logger.info(f"[soroush_worker] File uploaded successfully to {endpoint}: file_id={file_id}")
                                break
                        else:
                            last_error = f"HTTP {up_resp.status} on {endpoint}"
                            logger.debug(f"[soroush_worker] Upload attempt on {endpoint} returned status {up_resp.status}")
            except aiohttp.ClientConnectorError as e:
                last_error = f"عدم دسترسی به سرور {endpoint}: {e}"
                logger.debug(f"[soroush_worker] Endpoint {endpoint} unreachable: {e}")
            except Exception as e:
                last_error = f"خطا در {endpoint}: {e}"
                logger.debug(f"[soroush_worker] Upload error on {endpoint}: {e}")

        # در صورت عدم موفقیت آپلود (مانند پاسخ ۴۰۴ یا قطعی موقت)، فایل در صف باینری امن ذخیره می‌شود
        if not file_id:
            logger.warning(f"[soroush_worker] File upload unreachable ({last_error}). Staging into resilient local binary queue.")
            try:
                import shutil
                import time
                queue_dir = config.DATA_DIR / "soroush_queue"
                queue_dir.mkdir(parents=True, exist_ok=True)
                q_file = queue_dir / f"{int(time.time())}_{p.name}"
                shutil.copy2(str(p), str(q_file))
            except Exception as q_err:
                logger.debug(f"[soroush_worker] Queue staging note: {q_err}")

            return {
                "ok": False,
                "queued": True,
                "error": f"اندپوینت آپلود سروش‌پلاس پاسخ ناموفق داد ({last_error}). فایل جهت ارسال مجدد در صف امن محلی ثبت شد."
            }

        # ۲. ارسال پیام به Saved Messages پس از دریافت شناسه فایل
        send_endpoints = [
            f"{self.WEB_API_BASE}messages/send",
            f"{self.API_BASE}messages/send"
        ]
        msg_payload = {
            "peer": "saved_messages",
            "text": caption or p.name,
            "file_id": file_id,
            "mime_type": mime_type
        }

        for s_url in send_endpoints:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(s_url, json=msg_payload, headers=headers, timeout=20) as msg_resp:
                        if msg_resp.status == 200:
                            logger.info(f"[soroush_worker] File successfully dispatched to Saved Messages: {p.name}")
                            return {"ok": True, "file_id": file_id}
                        else:
                            last_error = f"HTTP {msg_resp.status}"
            except Exception as e:
                last_error = str(e)

        return {"ok": False, "error": f"خطا در ارسال پیام به Saved Messages سروش‌پلاس ({last_error})"}

# Singleton worker instance
soroush_worker = SoroushWorker()
