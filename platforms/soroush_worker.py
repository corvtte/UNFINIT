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
    FILE_API_BASE = "https://file.splus.ir/"

    def __init__(self, session_name: str = "soroush"):
        self.session_name = session_name
        self.session_dir = config.DATA_DIR / "sessions"
        self.session_dir.mkdir(parents=True, exist_ok=True)
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

    def is_connected(self) -> bool:
        """Returns True if a valid session exists."""
        if self._session_data and self._session_data.get("token"):
            return True
        data = self._load_session()
        return bool(data and data.get("token"))

    def get_masked_phone(self) -> str:
        """Returns masked phone number (e.g. 0912***4855)."""
        if not self.is_connected() or not self._session_data:
            return ""
        phone = str(self._session_data.get("phone", "")).strip().replace("+", "")
        if len(phone) >= 10:
            return f"{phone[:4]}***{phone[-4:]}"
        elif phone:
            return f"{phone[:2]}***{phone[-2:]}"
        return "متصل"

    def get_status(self) -> Dict[str, Any]:
        """Returns status payload for Web Panel dashboard and API."""
        connected = self.is_connected()
        return {
            "connected": connected,
            "masked_phone": self.get_masked_phone() if connected else "",
            "phone": self._session_data.get("phone", "") if (connected and self._session_data) else "",
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

        url = f"{self.WEB_API_BASE}auth/requestCode"
        headers = {"Content-Type": "application/json"}
        payload = {"phone": clean_phone}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers, timeout=15) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return {
                            "ok": True,
                            "phone": clean_phone,
                            "sms_id": data.get("sms_id") or data.get("result", {}).get("sms_id") or "",
                            "message": "کد تأیید پیامک شد."
                        }
                    else:
                        text = await resp.text()
                        logger.warning(f"[soroush_worker] requestCode failed HTTP {resp.status}: {text}")
                        return {"ok": False, "error": f"خطا در ارسال کد ({resp.status})", "detail": text}
        except Exception as e:
            logger.error(f"[soroush_worker] requestCode network error: {e}")
            return {"ok": False, "error": f"خطای شبکه در ارتباط با سرور سروش: {e}"}

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
        Uploads file to Soroush Plus CDN and dispatches it to 'Saved Messages' (پیام‌های ذخیره‌شده).
        """
        if not self.is_connected():
            return {"ok": False, "error": "سشن سروش‌پلاس متصل نیست."}

        p = Path(file_path)
        if not p.exists() or not p.is_file():
            return {"ok": False, "error": f"فایل یافت نشد: {file_path}"}

        token = self._session_data.get("token", "")
        headers = {"Authorization": f"Bearer {token}"}

        # Determine MIME type
        if not mime_type:
            mime_type, _ = mimetypes.guess_type(str(p))
            if not mime_type:
                mime_type = "application/octet-stream"

        try:
            # 1. Upload to Soroush File API
            upload_url = f"{self.FILE_API_BASE}upload"
            async with aiohttp.ClientSession() as session:
                data = aiohttp.FormData()
                data.add_field(
                    "file",
                    open(str(p), "rb"),
                    filename=p.name,
                    content_type=mime_type
                )
                async with session.post(upload_url, data=data, headers=headers, timeout=120) as up_resp:
                    if up_resp.status != 200:
                        up_text = await up_resp.text()
                        logger.warning(f"[soroush_worker] File upload failed: HTTP {up_resp.status}: {up_text}")
                        return {"ok": False, "error": f"خطا در آپلود فایل سروش ({up_resp.status})"}

                    up_res = await up_resp.json()
                    file_id = up_res.get("file_id") or up_res.get("result", {}).get("file_id")

                # 2. Dispatch to Saved Messages (dialog/saved_messages or chat with self)
                msg_url = f"{self.WEB_API_BASE}messages/send"
                msg_payload = {
                    "peer": "saved_messages",
                    "text": caption or p.name,
                    "file_id": file_id,
                    "mime_type": mime_type
                }
                async with session.post(msg_url, json=msg_payload, headers=headers, timeout=20) as msg_resp:
                    if msg_resp.status == 200:
                        logger.info(f"[soroush_worker] File successfully dispatched to Saved Messages: {p.name}")
                        return {"ok": True, "file_id": file_id}
                    else:
                        msg_text = await msg_resp.text()
                        logger.warning(f"[soroush_worker] Dispatch message failed: HTTP {msg_resp.status}: {msg_text}")
                        return {"ok": False, "error": f"خطا در ارسال پیام به Saved Messages ({msg_resp.status})"}
        except Exception as e:
            logger.error(f"[soroush_worker] send_file error: {e}")
            return {"ok": False, "error": str(e)}

# Singleton worker instance
soroush_worker = SoroushWorker()
