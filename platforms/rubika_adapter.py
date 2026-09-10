import asyncio
import os
import aiohttp
import re
import json
import logging
import uuid
import time
import shutil
import tempfile
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List, Union
from core.config import config
from core.logger import get_logger
from core.formatters import RubikaFormatter, human_size, format_duration, parse_trim_input
from services.store_service import StoreService
from services.media_service import MediaService, clean_display_filename, AUDIO_EXTENSIONS, VIDEO_EXTENSIONS
from services.session_manager import session_manager
from services.url_service import UrlService
from media.inspector import inspect_technical_metadata
from media.tagger import extract_cover_image, generate_video_thumbnail
from task_store import (
    has_rubika_session,
    find_existing_session_file,
    session_file_candidates,
    session_base_name,
    DATA_DIR,
    SESSION_DIR,
    cleanup_local_file
)

logger = get_logger("rubika_adapter")
RUBIKA_CONNECT_TIMEOUT = int(os.getenv("RUBIKA_CONNECT_TIMEOUT", "25") or 25)
RUBIKA_FINALIZE_RETRIES = int(os.getenv("RUBIKA_FINALIZE_RETRIES", "3") or 3)
RUBIKA_FINALIZE_RETRY_DELAY = float(os.getenv("RUBIKA_FINALIZE_RETRY_DELAY", "2") or 2)


def get_file_duration_sec(file_path: Path | str) -> int:
    try:
        from mutagen import File as MutagenFile
        audio = MutagenFile(str(file_path))
        if audio and audio.info and getattr(audio.info, "length", None):
            dur = int(round(audio.info.length))
            if dur > 0:
                return dur
    except Exception:
        pass
    try:
        tech = inspect_technical_metadata(file_path)
        dur = int(round(float(tech.get("duration_sec", 0) or 0)))
        if dur > 0:
            return dur
    except Exception:
        pass
    return 1


def build_rubika_inline_keyboard(rows: List[List[Dict[str, str]]]) -> Optional[Dict[str, Any]]:
    if not rows:
        return None
    formatted_rows = []
    for r in rows:
        btns = []
        for b in r:
            btn_id = str(b.get("id") or b.get("callback_data") or b.get("button_data") or b.get("button_text") or b.get("text") or "").strip()
            btn_text = str(b.get("button_text") or b.get("text") or "").strip()
            if btn_id and btn_text:
                btns.append({
                    "id": btn_id,
                    "type": "Simple",
                    "button_text": btn_text,
                    "button_data": btn_id,
                    "button_type": "Simple"
                })
        if btns:
            formatted_rows.append({"buttons": btns})
    return {"rows": formatted_rows} if formatted_rows else None


def build_rubika_chat_keyboard(rows: List[List[str]]) -> Optional[Dict[str, Any]]:
    if not rows:
        return None
    formatted_rows = []
    for r in rows:
        btns = [{"id": str(i), "type": "Simple", "button_text": str(text_val).strip()} for i, text_val in enumerate(r) if text_val and str(text_val).strip()]
        if btns:
            formatted_rows.append({"buttons": btns})
    return {"rows": formatted_rows, "resize_keyboard": True} if formatted_rows else None


def get_default_rubika_main_keyboard() -> Optional[Dict[str, Any]]:
    return build_rubika_inline_keyboard([
        [
            {"button_text": "📚 لیست دوره‌های آموزشی", "id": "btn_courses", "button_data": "btn_courses"},
            {"button_text": "🎁 دانلود هدیه رایگان", "id": "btn_gift", "button_data": "btn_gift"}
        ],
        [
            {"button_text": "👤 حساب کاربری و سفارشات", "id": "btn_account", "button_data": "btn_account"},
            {"button_text": "💬 ارتباط با پشتیبانی", "id": "btn_support", "button_data": "btn_support"}
        ]
    ])


def build_rubika_media_keyboard(drop_id: str, data: dict, is_sub: bool = False) -> Optional[Dict[str, Any]]:
    if is_sub:
        return build_rubika_inline_keyboard([
            [{"button_text": "🔙 بازگشت به منوی رسانه", "id": f"rmeta:back:{drop_id}"}],
            [{"button_text": "❌ لغو", "id": f"rmeta:cancel:{drop_id}"}]
        ])

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
                {"button_text": f"✏️ تغییر نام فایل{fn_check}", "id": f"rmeta:fn:{drop_id}"}
            ],
            [
                {"button_text": f"🗣 تغییر نام خواننده{perf_check}", "id": f"rmeta:perf:{drop_id}"},
                {"button_text": f"🎵 تغییر نام موزیک{title_check}", "id": f"rmeta:title:{drop_id}"}
            ],
            [
                {"button_text": "🎵 تبدیل به صوت / دریافت MP3", "id": f"rmeta:to_mp3:{drop_id}"}
            ],
            [
                {"button_text": "⚡️ اعمال سریع", "id": f"rmeta:quick_send:{drop_id}"},
                {"button_text": "💾 اعمال تغییرات", "id": f"rmeta:send_back:{drop_id}"}
            ],
            [
                {"button_text": "✈️ انتقال به تلگرام", "id": f"rmeta:send_tg:{drop_id}"},
                {"button_text": "🟢 انتقال به بله (زیر 50MB)", "id": f"rmeta:send_bale:{drop_id}"}
            ],
            [
                {"button_text": "🟣 انتقال به پیام‌های ذخیره‌شده (User)", "id": f"rmeta:send_saved:{drop_id}"}
            ]
        ]
        return build_rubika_inline_keyboard(rows)

    rows = [
        [
            {"button_text": f"✏️ تغییر نام فایل{fn_check}", "id": f"rmeta:fn:{drop_id}"}
        ],
        [
            {"button_text": f"🗣 تغییر نام خواننده{perf_check}", "id": f"rmeta:perf:{drop_id}"},
            {"button_text": f"🎵 تغییر نام موزیک{title_check}", "id": f"rmeta:title:{drop_id}"}
        ],
        [
            {"button_text": "✂️ برش فایل صوتی", "id": f"rmeta:trim:{drop_id}"}
        ],
        [
            {"button_text": "📋 اطلاعات تگ‌ها", "id": f"rmeta:tag_details:{drop_id}"},
            {"button_text": "📊 مشخصات فنی صوت", "id": f"rmeta:audio_specs:{drop_id}"}
        ],
        [
            {"button_text": f"🖼 تغییر تصویر بند انگشتی{thumb_check}", "id": f"rmeta:change_cov:{drop_id}"},
            {"button_text": "📥 دریافت تامبنیل", "id": f"rmeta:view_cov:{drop_id}"}
        ],
        [
            {"button_text": "🧹 حذف کامل متادیتا", "id": f"rmeta:strip_tags:{drop_id}"}
        ],
        [
            {"button_text": "⚡️ اعمال سریع", "id": f"rmeta:quick_send:{drop_id}"},
            {"button_text": "💾 اعمال تغییرات", "id": f"rmeta:send_back:{drop_id}"}
        ],
        [
            {"button_text": "✈️ انتقال به تلگرام", "id": f"rmeta:send_tg:{drop_id}"},
            {"button_text": "🟢 انتقال به بله (زیر 50MB)", "id": f"rmeta:send_bale:{drop_id}"}
        ],
        [
            {"button_text": "🟣 انتقال به پیام‌های ذخیره‌شده (User)", "id": f"rmeta:send_saved:{drop_id}"}
        ]
    ]
    return build_rubika_inline_keyboard(rows)


def extract_rubika_file_info(raw_msg: dict) -> Optional[dict]:
    if not isinstance(raw_msg, dict):
        return None
    
    sub_targets = [raw_msg]
    if "new_message" in raw_msg and isinstance(raw_msg["new_message"], dict):
        sub_targets.append(raw_msg["new_message"])
    if "message" in raw_msg and isinstance(raw_msg["message"], dict):
        sub_targets.append(raw_msg["message"])
    if "msg_obj" in raw_msg and isinstance(raw_msg["msg_obj"], dict):
        sub_targets.append(raw_msg["msg_obj"])
    if "raw" in raw_msg and isinstance(raw_msg["raw"], dict):
        sub_targets.append(raw_msg["raw"])

    for tgt in sub_targets:
        candidates = [
            tgt.get("file"),
            tgt.get("document"),
            tgt.get("audio"),
            tgt.get("video"),
            tgt.get("voice"),
            tgt.get("photo"),
            tgt.get("media"),
            tgt.get("file_inline"),
            tgt.get("music"),
        ]
        
        aux = tgt.get("aux_data")
        if isinstance(aux, dict):
            candidates.append(aux.get("file") or aux)
        elif isinstance(aux, str) and aux.strip().startswith("{"):
            try:
                parsed = json.loads(aux)
                if isinstance(parsed, dict):
                    candidates.append(parsed.get("file") or parsed)
            except Exception:
                pass

        for c in candidates:
            if isinstance(c, dict):
                f_id = c.get("file_id") or c.get("id")
                if f_id:
                    fn = c.get("file_name") or c.get("name") or "rubika_file"
                    sz = c.get("file_size") or c.get("size") or 0
                    f_type = str(c.get("type") or "").lower()
                    dur = c.get("duration") or c.get("time") or 0
                    title = c.get("title") or c.get("music_title") or ""
                    artist = c.get("performer") or c.get("music_performer") or c.get("artist") or ""
                    return {
                        "file_id": str(f_id).strip(),
                        "file_name": str(fn),
                        "file_size": int(sz or 0),
                        "type": f_type,
                        "duration": int(dur or 0),
                        "title": str(title),
                        "artist": str(artist),
                        "raw": c
                    }

        if tgt.get("file_id"):
            return {
                "file_id": str(tgt["file_id"]).strip(),
                "file_name": str(tgt.get("file_name") or "rubika_file"),
                "file_size": int(tgt.get("file_size") or 0),
                "type": str(tgt.get("type") or "").lower(),
                "duration": int(tgt.get("duration") or 0),
                "title": str(tgt.get("title") or ""),
                "artist": str(tgt.get("performer") or ""),
                "raw": tgt
            }

    return None


class RubikaBotClient:
    def __init__(self, token: Optional[str] = None):
        self.token = (token or config.RUBIKA_BOT_TOKEN or "").strip()
        self.base_url = f"https://botapi.rubika.ir/v3/{self.token}" if self.token else ""

    def is_configured(self) -> bool:
        return bool(self.token)

    async def get_me(self) -> Dict[str, Any]:
        if not self.is_configured():
            return {"ok": False, "error": "RUBIKA_BOT_TOKEN is missing"}
        url = f"{self.base_url}/getMe"
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
                async with session.post(url, json={}) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    return {"ok": False, "error": f"HTTP {resp.status}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    async def download_file(self, file_id: str, destination_path: Path | str) -> bool:
        if not self.is_configured():
            logger.warning("Rubika download_file: RUBIKA_BOT_TOKEN is missing")
            return False
        dest_p = Path(destination_path)
        logger.info(f"Rubika download_file requesting getFile for file_id='{file_id}'...")
        try:
            url = f"{self.base_url}/getFile"
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=45)) as session:
                async with session.post(url, json={"file_id": str(file_id).strip()}) as resp:
                    data = await resp.json()
                    logger.info(f"Rubika getFile status={resp.status} response={data}")
                    if resp.status != 200:
                        return False
                    dl_url = data.get("data", {}).get("download_url") or data.get("download_url")
                    if not dl_url:
                        logger.warning(f"Rubika getFile did not return download_url: {data}")
                        return False

            # Stream download from media server with generous timeout
            logger.info(f"Streaming Rubika file from {dl_url} to {dest_p.name}...")
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=1800, connect=30)) as dl_session:
                async with dl_session.get(dl_url) as dl_resp:
                    if dl_resp.status == 200:
                        dest_p.parent.mkdir(parents=True, exist_ok=True)
                        with open(dest_p, "wb") as f:
                            while True:
                                chunk = await dl_resp.content.read(512 * 1024)
                                if not chunk:
                                    break
                                f.write(chunk)
                        logger.info(f"Rubika file successfully downloaded: {dest_p} ({dest_p.stat().st_size} bytes)")
                        return True
                    else:
                        logger.warning(f"Rubika media server download returned HTTP {dl_resp.status}")
                        return False
        except Exception as e:
            logger.error(f"Rubika download_file error: {e}")
            return False

    async def send_photo(
        self,
        chat_id: str | int,
        photo_path: str | Path,
        caption: Optional[str] = None
    ) -> Dict[str, Any]:
        return await self.send_document(chat_id, photo_path, caption=caption)

    async def send_message(
        self,
        chat_id: str | int,
        text: str,
        inline_keypad: Optional[Dict[str, Any]] = None,
        chat_keypad: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if not self.is_configured():
            return {"ok": False, "error": "RUBIKA_BOT_TOKEN is missing"}
        
        clean_txt = RubikaFormatter.clean_text(text) if text else " "
        url = f"{self.base_url}/sendMessage"
        payload: Dict[str, Any] = {"chat_id": str(chat_id).strip(), "text": clean_txt}
        
        if inline_keypad and isinstance(inline_keypad, dict) and inline_keypad.get("rows"):
            payload["inline_keypad"] = inline_keypad

        if chat_keypad and isinstance(chat_keypad, dict) and chat_keypad.get("rows"):
            payload["chat_keypad"] = chat_keypad

        try:
            headers = {"Content-Type": "application/json"}
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
                async with session.post(url, json=payload, headers=headers) as resp:
                    data = await resp.json()
                    logger.info(f"Rubika Bot API sendMessage status={resp.status} response={data}")
                    return data
        except Exception as e:
            logger.warning(f"Rubika Bot API sendMessage warning: {e}")
            return {"ok": False, "error": str(e)}

    async def edit_message_text(
        self,
        chat_id: str | int,
        message_id: str | int,
        text: str,
        inline_keypad: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if not self.is_configured():
            return {"ok": False, "error": "RUBIKA_BOT_TOKEN is missing"}
        
        clean_txt = RubikaFormatter.clean_text(text)
        url = f"{self.base_url}/editMessageText"
        payload: Dict[str, Any] = {
            "chat_id": str(chat_id).strip(),
            "message_id": str(message_id).strip(),
            "text": clean_txt
        }
        if inline_keypad and isinstance(inline_keypad, dict) and inline_keypad.get("rows"):
            payload["inline_keypad"] = inline_keypad

        try:
            headers = {"Content-Type": "application/json"}
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20)) as session:
                async with session.post(url, json=payload, headers=headers) as resp:
                    data = await resp.json()
                    logger.info(f"Rubika Bot API editMessageText status={resp.status} response={data}")
                    return data
        except Exception as e:
            logger.warning(f"Rubika Bot API editMessageText warning: {e}")
            return {"ok": False, "error": str(e)}

    async def send_document(
        self,
        chat_id: str | int,
        file_path: str | Path,
        caption: Optional[str] = None
    ) -> Dict[str, Any]:
        if not self.is_configured():
            return {"ok": False, "error": "RUBIKA_BOT_TOKEN is missing"}

        path = Path(file_path)
        if not path.exists():
            return {"ok": False, "error": "فایل روی دیسک یافت نشد."}

        target_chat = str(chat_id or "").strip()
        if not target_chat or target_chat.lower() == "me":
            target_chat = config.RUBIKA_OWNER_ID if (config.RUBIKA_OWNER_ID and config.RUBIKA_OWNER_ID.lower() != "me") else ""
        if not target_chat:
            return {"ok": False, "error": "شناسه مقصد روبیکا (RUBIKA_OWNER_ID) مشخص نشده است."}

        clean_send_name = clean_display_filename(path.name)
        sz_bytes = path.stat().st_size
        sz_mb = sz_bytes / (1024 * 1024)
        if sz_mb > 50.0:
            return {
                "ok": False,
                "error": f"حجم فایل ({sz_mb:.1f} MB) از سقف مجاز بات روبیکا (50 MB) بیشتر است. لطفاً از گزینه [ارسال به پیام‌های ذخیره‌شده (User Session)] استفاده فرمایید."
            }

        duration = get_file_duration_sec(path)
        suffix = path.suffix.lower()

        # Check if file is an Ogg/Opus Telegram voice/audio and transcode to true MP3 if feasible
        upload_path = path
        tmp_converted_file = None
        try:
            with open(path, "rb") as f_chk:
                magic = f_chk.read(16)
            if magic.startswith(b"OggS") or suffix in (".ogg", ".m4a", ".wav", ".flac", ".opus", ".aac", ".wma"):
                import subprocess
                import tempfile
                tmp_mp3 = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
                tmp_mp3.close()
                cmd = ["ffmpeg", "-y", "-i", str(path), "-codec:a", "libmp3lame", "-b:a", "128k", tmp_mp3.name]
                sub_res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if sub_res.returncode == 0 and os.path.exists(tmp_mp3.name) and os.path.getsize(tmp_mp3.name) > 0:
                    upload_path = Path(tmp_mp3.name)
                    tmp_converted_file = tmp_mp3.name
                    sz_bytes = upload_path.stat().st_size
                    if not clean_send_name.lower().endswith(".mp3"):
                        clean_send_name = f"{Path(clean_send_name).stem}.mp3"
                    suffix = ".mp3"
        except Exception as trans_err:
            logger.warning(f"RubikaBotClient: could not auto-transcode audio: {trans_err}")

        # Determine preferred candidates: specific media type first, with 'File' fallback
        if suffix in (".mp4", ".mkv", ".mov", ".avi", ".webm"):
            candidate_types = ["Video", "File"]
        elif suffix in (".mp3", ".m4a", ".wav", ".ogg", ".flac", ".aac"):
            candidate_types = ["Music", "File"]
        elif suffix in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
            candidate_types = ["Image", "File"]
        else:
            candidate_types = ["File"]

        try:
            uploaded_file_id = None
            used_type = "File"

            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=900)) as session:
                headers = {"Content-Type": "application/json"}

                for cand_type in candidate_types:
                    try:
                        req_url = f"{self.base_url}/requestSendFile"
                        req_payload = {
                            "type": cand_type,
                            "file_name": clean_send_name,
                            "size": sz_bytes
                        }
                        async with session.post(req_url, json=req_payload, headers=headers) as req_resp:
                            req_data = await req_resp.json()
                            data_obj = req_data.get("data") or req_data.get("result") or {}
                            upload_url = data_obj.get("upload_url") or data_obj.get("server_url")

                        if not upload_url:
                            logger.warning(f"Rubika requestSendFile({cand_type}) returned no upload_url: {req_data}")
                            continue

                        logger.info(f"Uploading {clean_send_name} ({cand_type}) to Rubika media server: {upload_url}...")
                        form = aiohttp.FormData()
                        with open(upload_path, "rb") as f:
                            form.add_field("file", f, filename=clean_send_name, content_type="application/octet-stream")
                            async with session.post(upload_url, data=form) as up_resp:
                                up_text = await up_resp.text()
                                try:
                                    up_json = json.loads(up_text)
                                    if up_json.get("status") == "OK":
                                        up_data = up_json.get("data") or up_json.get("result") or up_json
                                        f_id = up_data.get("file_id") or up_data.get("id")
                                        if f_id:
                                            uploaded_file_id = f_id
                                            used_type = cand_type
                                            logger.info(f"Rubika media uploaded successfully with type '{used_type}', file_id='{uploaded_file_id}'")
                                            break
                                    else:
                                        logger.warning(f"Rubika media upload rejected type '{cand_type}': {up_text}")
                                except Exception as parse_e:
                                    logger.warning(f"Error parsing Rubika upload response: {parse_e}, body: {up_text}")
                    except Exception as cand_err:
                        logger.warning(f"Attempt with candidate type '{cand_type}' failed: {cand_err}")

                if not uploaded_file_id:
                    return {"ok": False, "error": "خطا در آپلود فایل به سرور رسانه روبیکا روی تمام استراتژی‌ها."}

                clean_caption = RubikaFormatter.clean_text(caption) if caption else f"📄 {clean_send_name}"
                send_file_url = f"{self.base_url}/sendFile"
                send_file_payload: Dict[str, Any] = {
                    "chat_id": target_chat,
                    "file_id": str(uploaded_file_id).strip(),
                    "type": used_type,
                    "text": clean_caption,
                    "file_name": clean_send_name
                }
                if used_type in ("Music", "Video") and duration > 1:
                    send_file_payload["duration"] = duration

                async with session.post(send_file_url, json=send_file_payload, headers=headers) as file_resp:
                    res_json = await file_resp.json()
                    logger.info(f"Rubika sendFile status={file_resp.status} response={res_json}")
                    if res_json.get("status") == "OK" or res_json.get("ok"):
                        return {"ok": True, "result": res_json}
                    return {"ok": False, "error": str(res_json.get("status_det") or res_json.get("status") or res_json)}

        except Exception as e:
            logger.error(f"Rubika Bot send_document error: {e}")
            return {"ok": False, "error": str(e)}
        finally:
            if tmp_converted_file and os.path.exists(tmp_converted_file):
                try:
                    os.remove(tmp_converted_file)
                except Exception:
                    pass


def clean_digits(text: Any) -> str:
    if not text:
        return ""
    trans = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
    return str(text).translate(trans).strip()

def normalize_rubika_phone(phone: Any) -> str:
    cleaned = clean_digits(phone).replace(" ", "").replace("-", "").replace("+", "").replace("(", "").replace(")", "")
    if cleaned.startswith("00"):
        cleaned = cleaned[2:]
    if cleaned.startswith("0"):
        cleaned = f"98{cleaned[1:]}"
    return cleaned


async def setup_rubika_client(client: Any, timeout: int = RUBIKA_CONNECT_TIMEOUT) -> Any:
    """
    Connects to Rubika and initializes cryptographic keys required by rubpy v7.
    RubPy's Client.connect() does not automatically populate client.key,
    client.decode_auth, or client.import_key, which causes:
    'NoneType' object has no attribute 'sign' during uploads and API calls.
    """
    if not hasattr(client, 'connection') or getattr(getattr(client, 'connection', None), 'session', None) is None or getattr(getattr(client.connection, 'session', None), 'closed', False):
        await asyncio.wait_for(client.connect(), timeout=timeout)

    if getattr(client, "auth", None):
        try:
            from rubpy.crypto import Crypto
            client.key = Crypto.passphrase(client.auth)
            client.decode_auth = Crypto.decode_auth(client.auth)
        except Exception as exc:
            logger.warning(f"Failed to derive rubika key/decode_auth: {exc}")

    priv_key = getattr(client, "private_key", None) or getattr(getattr(client, "session", None), "private_key", None)
    if priv_key:
        try:
            from Crypto.PublicKey import RSA
            from Crypto.Signature import pkcs1_15
            client.import_key = pkcs1_15.new(RSA.import_key(priv_key.encode()))
        except Exception as exc:
            logger.warning(f"Failed to initialize RSA import_key: {exc}")

    return client


class RubikaUserClient:
    def __init__(self, session_name: Optional[str] = None):
        self.session_name = (session_name or config.RUBIKA_SESSION or "unfinit_rubika").strip()
        self._auth_client = None

    def get_effective_session_path(self) -> Optional[Path]:
        return find_existing_session_file(self.session_name)

    def get_effective_session_name(self) -> str:
        f = self.get_effective_session_path()
        if f:
            base = Path(__file__).resolve().parent.parent
            if f.parent == base or str(f.parent) in (".", ""):
                return f.stem
            return str(f.with_suffix(""))
        return self.session_name

    def has_session(self) -> bool:
        return self.get_effective_session_path() is not None

    async def get_self_guid(self) -> Optional[str]:
        try:
            from rubpy import Client as RubikaClient
            sess_name = self.get_effective_session_name()
            client = RubikaClient(name=sess_name)
            await setup_rubika_client(client)
            user_guid = getattr(client, "guid", None) or getattr(getattr(client, "session", None), "guid", None)
            if user_guid:
                return str(user_guid).strip()
            
            me_info = await client.get_me()
            if isinstance(me_info, dict):
                data = me_info.get("data") or me_info.get("user") or me_info
                return (data.get("user_guid") or me_info.get("user_guid") or 
                        (data.get("user", {}).get("user_guid") if isinstance(data, dict) else None))
            return getattr(me_info, "user_guid", None) or getattr(getattr(me_info, "user", None), "user_guid", None)
        except Exception as e:
            logger.warning(f"Could not fetch self guid via rubpy: {e}")
            return None
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass

    async def upload_and_send(
        self,
        file_path: str | Path,
        target: str = "me",
        caption: Optional[str] = None,
        progress_cb = None
    ) -> Dict[str, Any]:
        path = Path(file_path)
        if not path.exists():
            return {"ok": False, "error": "فایل روی دیسک یافت نشد."}

        try:
            from rubpy import Client as RubikaClient
        except ImportError:
            return {"ok": False, "error": "پکیج rubpy نصب نشده است."}

        sess_name = self.get_effective_session_name()
        client = RubikaClient(name=sess_name)
        entered = False
        upload_name = clean_display_filename(path.name)
        duration = get_file_duration_sec(path)

        try:
            logger.info(f"Connecting to Rubika client (session={sess_name})...")
            client = await setup_rubika_client(client, timeout=RUBIKA_CONNECT_TIMEOUT)
            entered = True
        except asyncio.TimeoutError:
            return {"ok": False, "error": f"تایم‌اوت در اتصال به کلاینت روبیکا ({RUBIKA_CONNECT_TIMEOUT} ثانیه)."}
        except Exception as exc:
            return {"ok": False, "error": f"خطا در باز کردن سشن روبیکا: {exc}"}

        if not getattr(client, "auth", None):
            try:
                await client.disconnect()
            except Exception:
                pass
            return {"ok": False, "error": "سشن روبیکا فعال نیست. ابتدا وارد حساب روبیکا شوید."}

        try:
            logger.info(f"Uploading {upload_name} ({path.stat().st_size / (1024*1024):.1f} MB, {duration}s) to Rubika target '{target}'...")
            uploaded = await client.upload(
                str(path),
                callback=progress_cb,
                file_name=upload_name,
            )

            if isinstance(uploaded, dict):
                file_inline = dict(uploaded)
            elif callable(getattr(uploaded, "to_dict", None)):
                res = uploaded.to_dict()
                file_inline = dict(res) if isinstance(res, dict) else {}
            elif hasattr(uploaded, "to_dict") and isinstance(uploaded.to_dict, dict):
                file_inline = dict(uploaded.to_dict)
            else:
                file_inline = dict(uploaded) if hasattr(uploaded, "__iter__") else dict(getattr(uploaded, "__dict__", {}))
            inline_type = "Video" if path.suffix.lower() in VIDEO_EXTENSIONS else ("Music" if path.suffix.lower() in (".mp3", ".m4a", ".wav") else "File")
            
            payload = dict(file_inline)
            payload.update({
                "type": inline_type,
                "time": max(1, duration),
                "width": 200,
                "height": 200,
                "music_performer": config.DEFAULT_ARTIST or "",
                "is_spoil": False,
            })

            last_error = None
            for attempt in range(1, RUBIKA_FINALIZE_RETRIES + 1):
                try:
                    result = await client.send_message(
                        object_guid=target,
                        text=caption.strip() if caption and caption.strip() else None,
                        file_inline=payload,
                    )
                    logger.info(f"Rubika transfer complete to {target}: {result}")
                    return {"ok": True, "result": result}
                except Exception as error:
                    last_error = error
                    logger.warning(f"Rubika send attempt {attempt} failed: {error}")
                    await asyncio.sleep(RUBIKA_FINALIZE_RETRY_DELAY * attempt)

            return {"ok": False, "error": f"خطا در نهایی‌سازی پیام روبیکا: {last_error}"}
        except Exception as e:
            logger.error(f"Rubika upload error: {e}")
            return {"ok": False, "error": str(e)}
        finally:
            if entered:
                try:
                    await client.disconnect()
                except Exception:
                    pass

    async def send_code(self, phone: str, pass_key: Optional[str] = None) -> Dict[str, Any]:
        try:
            from rubpy import Client as RubikaClient
            clean_phone = normalize_rubika_phone(phone)
            logger.info(f"Rubika send_code request: clean_phone='{clean_phone}' (raw='{phone}')")
            if not clean_phone:
                return {"ok": False, "error": "شماره تلفن معتبر نیست."}

            if self._auth_client is not None:
                try:
                    await self._auth_client.disconnect()
                except Exception:
                    pass
            self._auth_client = RubikaClient(name=self.session_name)
            await self._auth_client.connect()

            res = await self._auth_client.send_code(phone_number=clean_phone, pass_key=pass_key)
            logger.info(f"Rubika send_code raw response: {res}")
            
            st = getattr(res, "status", None)
            if st == "SendPassKey":
                hint = getattr(res, "hint_pass_key", "")
                return {"ok": False, "status": "SendPassKey", "error": f"passkey required: {hint}"}
            
            hash_val = getattr(res, "phone_code_hash", "") or getattr(res, "hash", "")
            if not hash_val and isinstance(res, dict):
                hash_val = res.get("phone_code_hash") or res.get("hash", "")
            logger.info(f"Rubika send_code successful: hash='{hash_val}', phone='{clean_phone}'")
            return {"ok": True, "phone_code_hash": hash_val, "phone": clean_phone}
        except Exception as e:
            logger.error(f"Rubika send_code error: {e}")
            return {"ok": False, "error": str(e)}

    async def sign_in(self, phone: str, phone_code_hash: str, code: str, pass_key: Optional[str] = None) -> Dict[str, Any]:
        try:
            from rubpy import Client as RubikaClient
            from rubpy.crypto import Crypto
            from Crypto.PublicKey import RSA
            from Crypto.Signature import pkcs1_15

            clean_phone = normalize_rubika_phone(phone)
            clean_code = clean_digits(code)
            clean_hash = str(phone_code_hash or "").strip()
            logger.info(
                f"Rubika sign_in request: phone='{clean_phone}', code='{clean_code}', hash='{clean_hash}', "
                f"has_auth_client={self._auth_client is not None}"
            )

            if not clean_phone:
                return {"ok": False, "error": "شماره تلفن یافت نشد. لطفاً مجدداً با /set_rubika شماره خود را وارد فرمایید."}
            if not clean_code:
                return {"ok": False, "error": "کد ورود خالی است."}

            client = self._auth_client
            if client is None:
                logger.warning("Rubika sign_in: self._auth_client was None, creating fresh RubikaClient")
                client = RubikaClient(name=self.session_name)
                await client.connect()
            elif not hasattr(client, 'connection') or getattr(getattr(client.connection, 'session', None), 'closed', False):
                logger.info("Rubika sign_in: reconnecting client connection")
                await client.connect()

            public_key, client.private_key = Crypto.create_keys()

            result = await client.sign_in(
                phone_code=clean_code,
                phone_number=clean_phone,
                phone_code_hash=clean_hash,
                public_key=public_key
            )

            if getattr(result, "status", None) == "OK":
                result.auth = Crypto.decrypt_RSA_OAEP(client.private_key, result.auth)
                client.key = Crypto.passphrase(result.auth)
                client.auth = result.auth
                client.decode_auth = Crypto.decode_auth(client.auth)
                client.import_key = pkcs1_15.new(RSA.import_key(client.private_key.encode())) if client.private_key is not None else None
                client.session.insert(
                    auth=client.auth,
                    guid=result.user.user_guid,
                    user_agent=client.user_agent,
                    phone_number=result.user.phone,
                    private_key=client.private_key
                )
                try:
                    await client.register_device(device_model=client.name)
                except Exception as reg_e:
                    logger.warning(f"Rubika register_device warning: {reg_e}")

                try:
                    await client.disconnect()
                except Exception:
                    pass
                self._auth_client = None

                logger.info("Rubika user session successfully authorized and saved.")
                return {"ok": True}
            else:
                st = getattr(result, "status", None)
                st_det = getattr(result, "status_det", str(result))
                try:
                    await client.disconnect()
                except Exception:
                    pass
                self._auth_client = None
                logger.warning(f"Rubika sign_in failed: status={st}, status_det={st_det}")
                return {"ok": False, "status": st, "error": str(st_det)}
        except Exception as e:
            logger.error(f"Rubika sign_in error: {e}")
            self._auth_client = None
            return {"ok": False, "error": str(e)}


class RubikaAdapter:
    def __init__(self, session_name: Optional[str] = None):
        self.bot_client = RubikaBotClient()
        self.user_client = RubikaUserClient(session_name)

    def get_admin_guid(self) -> str:
        guid = config.RUBIKA_OWNER_ID if (config.RUBIKA_OWNER_ID and config.RUBIKA_OWNER_ID.lower() != "me") else ""
        return guid

    def is_admin(self, chat_id: str | int) -> bool:
        if not chat_id:
            return False
        cid = str(chat_id).strip()
        admin_guid = str(config.RUBIKA_OWNER_ID or "").strip()
        if admin_guid and admin_guid.lower() != "me" and cid == admin_guid:
            return True
        if hasattr(config, "ADMIN_USER_IDS") and config.ADMIN_USER_IDS:
            admin_ids = [str(x).strip() for x in config.ADMIN_USER_IDS if str(x).strip()]
            if cid in admin_ids:
                return True
        return False

    def has_user_session(self) -> bool:
        return self.user_client.has_session()

    async def get_me(self) -> Dict[str, Any]:
        return await self.bot_client.get_me()

    async def edit_message_text(
        self,
        chat_id: str | int,
        message_id: str | int,
        text: str,
        inline_keypad: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        return await self.bot_client.edit_message_text(chat_id, message_id, text, inline_keypad=inline_keypad)

    async def send_message(
        self,
        target_guid: str | int,
        text: str,
        inline_keypad: Optional[Dict[str, Any]] = None,
        chat_keypad: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        return await self.bot_client.send_message(
            target_guid,
            text,
            inline_keypad=inline_keypad,
            chat_keypad=chat_keypad
        )

    async def send_audio_bot_api(
        self,
        target_guid: str | int,
        file_path: str | Path,
        title: Optional[str] = None,
        performer: Optional[str] = None,
        caption: Optional[str] = None
    ) -> Dict[str, Any]:
        return await self.bot_client.send_document(target_guid, file_path, caption=caption)

    async def send_audio_user_session(
        self,
        file_path: str | Path,
        target: str = "me",
        caption: Optional[str] = None,
        progress_cb = None
    ) -> Dict[str, Any]:
        return await self.user_client.upload_and_send(file_path, target=target, caption=caption, progress_cb=progress_cb)

    async def send_audio(
        self,
        target_guid: str | int,
        file_path: str | Path,
        title: Optional[str] = None,
        performer: Optional[str] = None,
        caption: Optional[str] = None
    ) -> Dict[str, Any]:
        if str(target_guid).lower() == "me" or self.has_user_session():
            res = await self.send_audio_user_session(file_path, target="me", caption=caption)
            if res.get("ok"):
                return res
        return await self.send_audio_bot_api(target_guid, file_path, title=title, performer=performer, caption=caption)

    async def request_auth_code(self, phone: str, pass_key: Optional[str] = None) -> Dict[str, Any]:
        return await self.user_client.send_code(phone, pass_key=pass_key)

    async def submit_auth_code(self, phone: str, phone_code_hash: str, code: str, pass_key: Optional[str] = None) -> Dict[str, Any]:
        return await self.user_client.sign_in(phone, phone_code_hash, code, pass_key=pass_key)


def extract_universal_rubika_updates(data: Any) -> tuple[List[Dict[str, Any]], Optional[str]]:
    updates = []
    next_offset = None
    if isinstance(data, dict):
        next_offset = (
            data.get("data", {}).get("next_offset_id")
            or data.get("data", {}).get("next_offset")
            or data.get("next_offset")
            or data.get("next_offset_id")
            or (data.get("result", {}).get("next_offset_id") if isinstance(data.get("result"), dict) else None)
        )
        if "data" in data and isinstance(data["data"], dict) and "updates" in data["data"]:
            updates.extend(data["data"]["updates"])
        elif "result" in data and isinstance(data["result"], list):
            updates.extend(data["result"])
        elif "updates" in data and isinstance(data["updates"], list):
            updates.extend(data["updates"])
    elif isinstance(data, list):
        updates.extend(data)

    if not next_offset and updates:
        last_u = updates[-1]
        if isinstance(last_u, dict):
            next_offset = last_u.get("update_id") or last_u.get("id")

    normalized = []
    for u in updates:
        up_id = u.get("update_id", 0)
        up_type = str(u.get("type", "")).lower()

        msg_obj = u.get("new_message") or u.get("message") or {}
        btn_obj = u.get("button_clicked") or u.get("callback_query") or u.get("inline_message") or {}

        # 1. Check for Button Click / aux_data anywhere in the update structure
        aux_data = (
            u.get("aux_data")
            or msg_obj.get("aux_data")
            or btn_obj.get("aux_data")
            or u.get("button_id")
            or msg_obj.get("button_id")
            or btn_obj.get("button_id")
        )
        btn_id = ""
        if isinstance(aux_data, dict):
            btn_id = str(aux_data.get("button_id") or aux_data.get("id") or aux_data.get("data") or "").strip()
        elif isinstance(aux_data, str):
            btn_id = aux_data.strip()

        if not btn_id:
            btn_id = str(
                btn_obj.get("button_id")
                or btn_obj.get("button_data")
                or btn_obj.get("id")
                or btn_obj.get("data")
                or ""
            ).strip()

        raw_ts = (
            msg_obj.get("time")
            or msg_obj.get("date")
            or msg_obj.get("timestamp")
            or btn_obj.get("time")
            or btn_obj.get("date")
            or u.get("time")
            or u.get("date")
            or u.get("timestamp")
        )
        parsed_ts = None
        if raw_ts is not None:
            try:
                parsed_ts = float(raw_ts)
                if parsed_ts > 1e11:  # convert ms to seconds
                    parsed_ts /= 1000.0
            except (ValueError, TypeError):
                parsed_ts = None

        if btn_id:
            chat_id = str(
                btn_obj.get("chat_id")
                or msg_obj.get("chat_id")
                or u.get("chat_id")
                or msg_obj.get("sender_id")
                or ""
            )
            msg_id = str(btn_obj.get("message_id") or msg_obj.get("message_id") or u.get("message_id") or "")
            user_id = str(btn_obj.get("user_id") or msg_obj.get("sender_id") or chat_id)
            if chat_id and btn_id:
                normalized.append({
                    "update_id": up_id,
                    "event_type": "button_click",
                    "chat_id": chat_id,
                    "button_id": btn_id,
                    "message_id": msg_id,
                    "user_id": user_id,
                    "timestamp": parsed_ts,
                    "msg_obj": msg_obj,
                    "raw": u
                })
                continue

        # 2. Plain Message Event
        if "new_message" in u or "chat_id" in u or "message" in u:
            chat_id = str(u.get("chat_id") or msg_obj.get("chat_id") or msg_obj.get("sender_id") or "")
            sender_id = str(msg_obj.get("sender_id") or chat_id)
            msg_id = str(msg_obj.get("message_id") or "")
            text = (msg_obj.get("text") or "").strip()
            if chat_id:
                normalized.append({
                    "update_id": up_id,
                    "event_type": "message",
                    "chat_id": chat_id,
                    "sender_id": sender_id,
                    "message_id": msg_id,
                    "text": text,
                    "timestamp": parsed_ts,
                    "msg_obj": msg_obj,
                    "raw": u
                })

    return normalized, next_offset


async def run_rubika_polling_engine(telegram_adapter_instance=None, bale_adapter_instance=None):
    global ACTIVE_RUBIKA_ADMIN_ID
    bot_start_time = time.time()
    token = config.RUBIKA_BOT_TOKEN
    if not token:
        logger.info("RUBIKA_BOT_TOKEN is not set. Rubika Bot API polling skipped.")
        return

    rubika = RubikaAdapter()
    logger.info("Initializing Rubika Bot API connection test...")
    me = await rubika.get_me()
    logger.debug(f"Rubika Bot API connection response: {me}")

    logger.info(f"Rubika Universal Polling listener active (bot_start_time={bot_start_time:.2f}).")
    rubika_offset_file = config.DATA_DIR / "rubika_offset.txt"
    offset = None
    if rubika_offset_file.exists():
        try:
            stored_offset = rubika_offset_file.read_text(encoding="utf-8").strip()
            if stored_offset:
                offset = stored_offset
                logger.info(f"Loaded persistent Rubika offset: {offset}")
        except Exception as e:
            logger.warning(f"Failed to read rubika_offset.txt: {e}")

    seen_ids = set()
    is_first_poll = True

    async def send_rubika_start_flow(c_id: str):
        is_adm = rubika.is_admin(c_id)
        s_name = fix_mojibake(await get_system_setting("STORE_NAME", config.STORE_NAME), default=config.STORE_NAME)
        w_text = fix_mojibake(await get_system_setting("WELCOME_TEXT", config.WELCOME_TEXT), default=config.WELCOME_TEXT)
        if is_adm:
            admin_txt = (
                f"🎛 <b>پنل مدیریت یکپارچه هاب رسانه و فروشگاه {s_name} | روبیکا</b>\n\n"
                f"{w_text}\n\n"
                f"سلام مدیر گرامی روبیکا خوش آمدید.\n"
                f"شناسه شما (<code>{c_id}</code>) به عنوان ادمین تایید گردید.\n\n"
                "قابلیت‌های فعال:\n"
                "▫️ <b>هاب متادیتا:</b> ارسال هرگونه فایل یا ویدیو جهت تگ‌گذاری و استخراج صوت\n"
                "▫️ <b>انتقال بین پلتفرمی:</b> ارسال مستقیم فایل به تلگرام، بله و Saved Messages\n"
                "▫️ <b>دانلود مستقیم:</b> ارسال لینک مستقیم فایل جهت دانلود و بارگذاری ابری\n"
                "▫️ <b>فروشگاه دوره‌ها:</b> مدیریت و مشاهده سفارش‌های مشتریان"
            )
            await rubika.send_message(
                c_id,
                admin_txt,
                inline_keypad=get_default_rubika_main_keyboard()
            )
        else:
            await rubika.send_message(
                c_id,
                w_text,
                inline_keypad=get_default_rubika_main_keyboard()
            )

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
        while True:
            try:
                url = f"{rubika.bot_client.base_url}/getUpdates"
                payload: Dict[str, Any] = {"limit": 20}
                if offset:
                    payload["offset_id"] = str(offset)

                headers = {"Content-Type": "application/json"}
                async with session.post(url, json=payload, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        updates, next_offset = extract_universal_rubika_updates(data)
                        if next_offset:
                            offset = str(next_offset).strip()
                            try:
                                config.DATA_DIR.mkdir(parents=True, exist_ok=True)
                                rubika_offset_file.write_text(offset, encoding="utf-8")
                            except Exception as e:
                                logger.warning(f"Failed to write rubika_offset.txt: {e}")
                        elif updates:
                            last_id = str(updates[-1].get("update_id") or updates[-1].get("message_id") or "").strip()
                            if last_id:
                                offset = last_id
                                try:
                                    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
                                    rubika_offset_file.write_text(offset, encoding="utf-8")
                                except Exception:
                                    pass

                        if is_first_poll:
                            is_first_poll = False
                            for u in updates:
                                up_id = str(u.get("message_id") or u.get("update_id") or "").strip()
                                if up_id:
                                    seen_ids.add(up_id)
                            logger.debug(f"Rubika initial backlog flushed ({len(updates)} past updates ignored, offset={offset}).")
                            await asyncio.sleep(1.5)
                            continue

                        if updates:
                            logger.debug(f"Rubika raw update: {updates}")

                        for u in updates:
                            up_id = str(u.get("message_id") or u.get("update_id") or "").strip()
                            if up_id:
                                if up_id in seen_ids:
                                    continue
                                seen_ids.add(up_id)
                                if len(seen_ids) > 10000:
                                    seen_ids.clear()

                            # Discard messages with timestamp prior to bot startup
                            up_ts = u.get("timestamp")
                            if up_ts is not None and isinstance(up_ts, (int, float)):
                                if up_ts < (bot_start_time - 2):
                                    logger.debug(f"Rubika update {up_id} ignored (timestamp {up_ts} older than bot start {bot_start_time})")
                                    continue
                            chat_id = u["chat_id"]
                            event_type = u.get("event_type", "message")

                            if chat_id:
                                await StoreService.get_or_create_customer(chat_id, platform="rubika")

                            user_act = session_manager.get_user_action(f"rubika_{chat_id}")

                            # Handle Button Click Events
                            if event_type == "button_click":
                                btn_id = u.get("button_id", "")
                                msg_id = u.get("message_id", "")
                                logger.info(f"Rubika button clicked from {chat_id}: '{btn_id}'")

                                # Handle Start / Home / Menu Button clicks
                                if btn_id in ("start", "/start", "btn_start", "main_menu", "menu", "بازگشت به منوی اصلی", "شروع", "خانه", "home"):
                                    await send_rubika_start_flow(chat_id)
                                    continue

                                if btn_id in ("myid", "/myid", "شناسه من", "guid"):
                                    myid_msg = (
                                        "🆔 <b>شناسه اختصاصی شما در روبیکا (GUID):</b>\n\n"
                                        f"<code>{chat_id}</code>\n\n"
                                        "💡 <i>جهت تعریف خود به عنوان مدیر سیستم، این شناسه را در بخش سکرت‌های هاگینگ‌فیس به عنوان <code>RUBIKA_OWNER_ID</code> یا در پنل مدیریت وب وارد فرمایید.</i>"
                                    )
                                    await rubika.send_message(chat_id, myid_msg, inline_keypad=get_default_rubika_main_keyboard())
                                    continue

                                # URL Uploader Callbacks in Rubika
                                if btn_id.startswith("rurldl:"):
                                    parts = btn_id.split(":")
                                    mode = parts[1]
                                    url_id = parts[2]
                                    url_sess = session_manager.get_session(f"rurl_{url_id}")

                                    if not url_sess:
                                        await rubika.send_message(chat_id, "❌ مهلت لینک مستقیم به پایان رسیده است.")
                                        continue

                                    if mode == "cancel":
                                        session_manager.remove_session(f"rurl_{url_id}")
                                        await rubika.bot_client.edit_message_text(chat_id, msg_id, "❌ عملیات دانلود لینک مستقیم لغو گردید.")
                                        continue

                                    url_val = url_sess["url"]
                                    orig_fn = url_sess["filename"]
                                    temp_dest = config.TEMP_DIR / f"rurldl_{url_id}_{clean_display_filename(orig_fn)}"
                                    await rubika.bot_client.edit_message_text(chat_id, msg_id, "📥 <b>در حال دانلود استریم فایل از لینک مستقیم...</b>")

                                    ok = await UrlService.download_file_stream(url_val, temp_dest)
                                    if not ok or not temp_dest.exists():
                                        await rubika.send_message(chat_id, "❌ خطا در دانلود فایل از لینک مستقیم.")
                                        continue

                                    if mode == "audio" and temp_dest.suffix.lower() in VIDEO_EXTENSIONS:
                                        await rubika.send_message(chat_id, "🎵 در حال استخراج هوشمند صوت ویدیو به MP3...")
                                        mp3_p = config.TEMP_DIR / f"{temp_dest.stem}.mp3"
                                        c_ok, final_mp3 = MediaService.convert_video_to_mp3(temp_dest, output_path=mp3_p)
                                        if c_ok and final_mp3.exists():
                                            temp_dest = final_mp3
                                            orig_fn = final_mp3.name

                                    sz = temp_dest.stat().st_size
                                    sz_mb = sz / (1024 * 1024)
                                    if sz_mb > 50.0:
                                        await rubika.send_message(
                                            chat_id,
                                            f"⚠️ حجم فایل ({sz_mb:.1f} MB) از سقف مجاز بات روبیکا (50MB) بیشتر است. در حال ارسال مستقیم به پیام‌های ذخیره‌شده (Saved Messages)..."
                                        )
                                        res_user = await rubika.send_audio_user_session(temp_dest, target="me", caption=f"🌐 دانلود از لینک:\n📄 {orig_fn}")
                                        if res_user.get("ok"):
                                            await rubika.send_message(chat_id, f"✅ فایل با موفقیت در Saved Messages شما آپلود شد!\n📄 {orig_fn}")
                                        else:
                                            await rubika.send_message(chat_id, f"❌ خطا در آپلود به Saved Messages: {res_user.get('error')}")
                                        continue

                                    send_res = await rubika.bot_client.send_document(chat_id, temp_dest, caption=f"🌐 دریافت شده از لینک مستقیم:\n📄 {orig_fn}")
                                    if send_res.get("ok") or send_res.get("status") == "OK":
                                        new_drop_id = uuid.uuid4().hex[:8]
                                        is_v = temp_dest.suffix.lower() in VIDEO_EXTENSIONS
                                        new_data = MediaService.register_incoming_message_meta(
                                            new_drop_id, "rubika", chat_id, str(temp_dest), orig_fn, sz,
                                            media_type="video" if is_v else "audio",
                                            api_meta={"filename": orig_fn, "file_size": sz}
                                        )
                                        new_data["working_path"] = str(temp_dest)
                                        new_data["is_downloaded_locally"] = True
                                        new_card = RubikaFormatter.format_light_card(new_data)
                                        new_kb = build_rubika_media_keyboard(new_drop_id, new_data)
                                        sent_c = await rubika.send_message(chat_id, new_card, inline_keypad=new_kb)
                                        if sent_c and isinstance(sent_c, dict):
                                            new_data["card_msg_id"] = sent_c.get("data", {}).get("message_id") or sent_c.get("message_id")
                                    continue

                                # Media Callbacks in Rubika
                                if btn_id.startswith("rmeta:"):
                                    parts = btn_id.split(":")
                                    action = parts[1]
                                    drop_id = parts[2]
                                    drop = session_manager.get_session(drop_id)
                                    if not drop:
                                        await rubika.send_message(chat_id, "❌ مهلت فایل به پایان رسیده است.")
                                        continue

                                    async def ensure_rubika_binary():
                                        if not drop.get("is_downloaded_locally"):
                                            async def dl_func(fid, p):
                                                return await rubika.bot_client.download_file(fid, p)
                                            await MediaService.ensure_local_binary(drop_id, dl_func)

                                    if action == "cancel":
                                        session_manager.remove_session(drop_id)
                                        await rubika.bot_client.edit_message_text(chat_id, msg_id, "❌ عملیات مدیریت رسانه لغو شد.")
                                    elif action == "tag_details":
                                        await ensure_rubika_binary()
                                        MediaService.inspect_full(drop_id)
                                        txt = RubikaFormatter.format_tag_details(drop)
                                        kb = build_rubika_media_keyboard(drop_id, drop, is_sub=True)
                                        await rubika.bot_client.edit_message_text(chat_id, msg_id, txt, inline_keypad=kb)
                                    elif action == "audio_specs":
                                        await ensure_rubika_binary()
                                        MediaService.inspect_full(drop_id)
                                        txt = RubikaFormatter.format_audio_specs(drop)
                                        kb = build_rubika_media_keyboard(drop_id, drop, is_sub=True)
                                        await rubika.bot_client.edit_message_text(chat_id, msg_id, txt, inline_keypad=kb)
                                    elif action == "strip_tags":
                                        await ensure_rubika_binary()
                                        ok, raw_p = MediaService.strip_metadata_for_session(drop_id)
                                        if ok:
                                            txt = RubikaFormatter.format_light_card(drop)
                                            kb = build_rubika_media_keyboard(drop_id, drop, is_sub=False)
                                            await rubika.bot_client.edit_message_text(chat_id, msg_id, txt, inline_keypad=kb)
                                            await rubika.send_message(chat_id, "✅ تمام متادیتاها و تگ‌های فایل با موفقیت پاکسازی شد.")
                                        else:
                                            await rubika.send_message(chat_id, "❌ خطا در پاکسازی متادیتا.")
                                    elif action == "back":
                                        txt = RubikaFormatter.format_light_card(drop)
                                        kb = build_rubika_media_keyboard(drop_id, drop, is_sub=False)
                                        await rubika.bot_client.edit_message_text(chat_id, msg_id, txt, inline_keypad=kb)
                                    elif action == "fn":
                                        session_manager.set_user_action(f"rubika_{chat_id}", "await_fn", drop_id)
                                        await rubika.send_message(chat_id, "✏️ لطفاً نام فایل جدید را ارسال فرمایید:")
                                    elif action == "perf":
                                        session_manager.set_user_action(f"rubika_{chat_id}", "await_perf", drop_id)
                                        kb_quick = build_rubika_inline_keyboard([
                                            [{"button_text": f"⚡️ تنظیم روی مقدار پیش‌فرض ({config.DEFAULT_ARTIST})", "id": f"rmeta:set_def_artist:{drop_id}"}],
                                            [{"button_text": "🔙 انصراف", "id": f"rmeta:back:{drop_id}"}]
                                        ])
                                        await rubika.send_message(
                                            chat_id,
                                            "🗣 <b>لطفاً نام خواننده / سازنده جدید را ارسال فرمایید:</b>\nیا می‌توانید با لمس دکمه زیر، مستقیماً از مقدار پیش‌فرض استفاده کنید:",
                                            inline_keypad=kb_quick
                                        )
                                    elif action == "set_def_artist":
                                        MediaService.apply_default_artist(drop_id)
                                        session_manager.clear_user_action(f"rubika_{chat_id}")
                                        drop = session_manager.get_session(drop_id)
                                        txt = RubikaFormatter.format_light_card(drop)
                                        kb = build_rubika_media_keyboard(drop_id, drop, is_sub=False)
                                        await rubika.bot_client.edit_message_text(chat_id, msg_id, txt, inline_keypad=kb)
                                    elif action == "title":
                                        session_manager.set_user_action(f"rubika_{chat_id}", "await_title", drop_id)
                                        await rubika.send_message(chat_id, "🎵 لطفاً عنوان موزیک را ارسال فرمایید:")
                                    elif action == "trim":
                                        await ensure_rubika_binary()
                                        tech = inspect_technical_metadata(drop["working_path"])
                                        dur = tech.get("duration_sec", 0)
                                        session_manager.set_user_action(f"rubika_{chat_id}", "await_trim_time", drop_id)
                                        trim_prompt = (
                                            "✂️ بخش مورد نظر جهت برش فایل را مشخص فرمایید:\n\n"
                                            f"⏱️ مدت زمان کل فایل: {format_duration(dur)}\n\n"
                                            "نمونه‌های معتبر ارسال:\n"
                                            "▫️ شروع و پایان: 02:10 - 21:28 یا 02:10 21:28\n"
                                            "▫️ فقط زمان شروع (تا انتها): 02:10\n"
                                            "▫️ بر حسب ثانیه: 130 - 1288 یا 130"
                                        )
                                        await rubika.send_message(chat_id, trim_prompt)
                                    elif action == "to_mp3":
                                        await ensure_rubika_binary()
                                        await rubika.send_message(chat_id, "⏳ <b>در حال استخراج و تبدیل هوشمند صوت ویدیو به MP3...</b>")
                                        try:
                                            ok, final_mp3, info = MediaService.extract_audio_from_video(drop_id)
                                            if ok and final_mp3.exists():
                                                await rubika.bot_client.send_document(
                                                    chat_id, final_mp3,
                                                    caption=f"🎵 نسخه صوتی استخراج‌شده از ویدیو (MP3):\n📄 {info['file_name']}\n🗣 خواننده: {info['artist']}"
                                                )
                                                new_drop_id = uuid.uuid4().hex[:8]
                                                new_data = MediaService.register_incoming_message_meta(
                                                    new_drop_id, "rubika", chat_id, str(final_mp3), final_mp3.name, final_mp3.stat().st_size,
                                                    media_type="audio", api_meta={"filename": final_mp3.name, "title": info["title"], "artist": info["artist"]}
                                                )
                                                new_data["working_path"] = str(final_mp3)
                                                new_data["is_downloaded_locally"] = True
                                                new_card = RubikaFormatter.format_light_card(new_data)
                                                new_kb = build_rubika_media_keyboard(new_drop_id, new_data)
                                                sent_c = await rubika.send_message(chat_id, new_card, inline_keypad=new_kb)
                                                if sent_c and isinstance(sent_c, dict):
                                                    new_data["card_msg_id"] = sent_c.get("data", {}).get("message_id") or sent_c.get("message_id")
                                            else:
                                                await rubika.send_message(chat_id, "❌ خطا در استخراج صوت از ویدیو.")
                                        except Exception as e:
                                            await rubika.send_message(chat_id, f"❌ خطا در استخراج صوت: {e}")
                                    elif action == "view_cov":
                                        await ensure_rubika_binary()
                                        cov_p = MediaService.extract_cover(drop_id)
                                        if cov_p and Path(cov_p).exists() and Path(cov_p).stat().st_size > 50:
                                            await rubika.bot_client.send_photo(chat_id, cov_p, caption="🖼 تصویر بندانگشتی استخراج‌شده")
                                        else:
                                            await rubika.send_message(chat_id, "⚠️ این فایل فاقد تصویر بند انگشتی است.")
                                    elif action == "change_cov":
                                        session_manager.set_user_action(f"rubika_{chat_id}", "await_cover", drop_id)
                                        await rubika.send_message(chat_id, "🌇 لطفاً عکس بند انگشتی (تامبنیل) جدید را ارسال فرمایید:")
                                    elif action == "quick_send":
                                        await ensure_rubika_binary()
                                        draft_title = drop.get("draft_tags", {}).get("title") or drop.get("embed_meta", {}).get("title") or drop.get("api_meta", {}).get("title") or ""
                                        draft_artist = drop.get("draft_tags", {}).get("artist") or drop.get("embed_meta", {}).get("artist") or drop.get("api_meta", {}).get("artist") or ""
                                        fn = clean_display_filename(drop.get("audio_filename") or "rubika_audio.mp3")
                                        res = await rubika.bot_client.send_document(
                                            chat_id, drop["working_path"],
                                            caption=f"⚡️ فایل با متادیتای نمایشی جدید:\n📄 {fn}\n🗣 خواننده: {draft_artist}\n🎵 عنوان: {draft_title}"
                                        )
                                        if not (res.get("ok") or res.get("status") == "OK"):
                                            await rubika.send_message(chat_id, f"❌ خطا در ارسال سریع: {res.get('error') or res}")
                                    elif action == "send_back":
                                        await rubika.send_message(chat_id, "⏳ <b>در حال آماده‌سازی و اعمال متادیتا...</b>")
                                        await ensure_rubika_binary()
                                        try:
                                            final_p, fn, info = MediaService.prepare_for_transfer(drop_id, "rubika")
                                            res = await rubika.bot_client.send_document(
                                                chat_id, final_p,
                                                caption=f"✅ فایل اصلاح‌شده و تگ‌گذاری‌شده:\n📄 {clean_display_filename(fn)}\n🗣 خواننده: {info['artist']}\n🎵 عنوان: {info['title']}"
                                            )
                                            if not (res.get("ok") or res.get("status") == "OK"):
                                                await rubika.send_message(chat_id, f"❌ خطا در ارسال فایل: {res.get('error') or res}")
                                        except Exception as e:
                                            await rubika.send_message(chat_id, f"❌ خطا در اعمال متادیتا: {e}")
                                    elif action == "send_tg":
                                        logger.info(f"[rubika->tg] send_tg clicked for drop_id={drop_id} by {chat_id}")
                                        if telegram_adapter_instance:
                                            await rubika.send_message(chat_id, "⏳ در حال دانلود و آماده‌سازی فایل جهت انتقال به تلگرام...")
                                            await ensure_rubika_binary()
                                            try:
                                                final_p, fn, info = MediaService.prepare_for_transfer(drop_id, "telegram")
                                                target_tg_id = config.TELEGRAM_OWNER_ID or telegram_adapter_instance.get_admin_id()
                                                logger.info(f"[rubika->tg] Transferring {final_p.name} ({final_p.stat().st_size} bytes) to Telegram admin {target_tg_id}...")
                                                if drop.get("media_type") == "video":
                                                    tech = inspect_technical_metadata(final_p)
                                                    thumb_p = generate_video_thumbnail(final_p)
                                                    res = await telegram_adapter_instance.send_video(
                                                        target_tg_id, final_p,
                                                        caption=f"✅ منتقل شده از روبیکا\n📄 {clean_display_filename(fn)}",
                                                        width=tech.get("width"),
                                                        height=tech.get("height"),
                                                        duration=tech.get("duration_sec"),
                                                        thumb=thumb_p
                                                    )
                                                else:
                                                    res = await telegram_adapter_instance.send_audio(
                                                        target_tg_id, final_p,
                                                        title=info["title"],
                                                        performer=info["artist"],
                                                        caption=f"✅ منتقل شده از روبیکا\n📄 {clean_display_filename(fn)}"
                                                    )
                                                logger.info(f"[rubika->tg] Telegram result: {res}")
                                                if res.get("ok"):
                                                    await rubika.send_message(chat_id, f"✅ فایل با موفقیت به تلگرام منتقل شد!\n📄 {clean_display_filename(fn)}")
                                                else:
                                                    await rubika.send_message(chat_id, f"❌ خطا در ارسال به تلگرام: {res.get('error')}")
                                            except Exception as e:
                                                logger.error(f"[rubika->tg] Error transferring to Telegram: {e}")
                                                await rubika.send_message(chat_id, f"❌ خطا در انتقال به تلگرام: {e}")
                                        else:
                                            logger.warning(f"[rubika->tg] telegram_adapter_instance is None!")
                                            await rubika.send_message(chat_id, "❌ آداپتور تلگرام در حال حاضر متصل نیست.")
                                    elif action == "send_bale":
                                        logger.info(f"[rubika->bale] send_bale clicked for drop_id={drop_id} by {chat_id}")
                                        if bale_adapter_instance:
                                            await rubika.send_message(chat_id, "⏳ در حال دانلود و بهینه‌سازی فایل جهت انتقال به بله (زیر 50MB)...")
                                            await ensure_rubika_binary()
                                            try:
                                                final_p, fn, info = MediaService.prepare_for_transfer(drop_id, "bale")
                                                target_bale_id = bale_adapter_instance.get_admin_chat_id()
                                                logger.info(f"[rubika->bale] Transferring {final_p.name} ({final_p.stat().st_size} bytes) to Bale {target_bale_id}...")
                                                if drop.get("media_type") == "video":
                                                    tech = inspect_technical_metadata(final_p)
                                                    res = await bale_adapter_instance.send_video(
                                                        target_bale_id, final_p,
                                                        caption=f"✅ منتقل شده از روبیکا\n📄 {clean_display_filename(fn)}",
                                                        duration=tech.get("duration_sec"),
                                                        width=tech.get("width"),
                                                        height=tech.get("height")
                                                    )
                                                else:
                                                    res = await bale_adapter_instance.send_audio(
                                                        target_bale_id, final_p,
                                                        title=info["title"],
                                                        performer=info["artist"],
                                                        caption=f"✅ منتقل شده از روبیکا\n📄 {clean_display_filename(fn)}"
                                                    )
                                                logger.info(f"[rubika->bale] Bale result: {res}")
                                                if res.get("ok"):
                                                    await rubika.send_message(chat_id, f"✅ فایل با موفقیت به بله منتقل شد!\n📄 {clean_display_filename(fn)}")
                                                else:
                                                    await rubika.send_message(chat_id, f"❌ خطا در ارسال به بله: {res.get('error') or res}")
                                            except Exception as e:
                                                logger.error(f"[rubika->bale] Error transferring to Bale: {e}")
                                                await rubika.send_message(chat_id, f"❌ خطا در انتقال به بله: {e}")
                                        else:
                                            logger.warning(f"[rubika->bale] bale_adapter_instance is None!")
                                            await rubika.send_message(chat_id, "❌ آداپتور بله در حال حاضر متصل نیست.")
                                    elif action == "send_saved":
                                        logger.info(f"[rubika->saved] send_saved clicked for drop_id={drop_id} by {chat_id}")
                                        await rubika.send_message(chat_id, "⏳ در حال آماده‌سازی و ارسال به پیام‌های ذخیره‌شده (User Session)...")
                                        await ensure_rubika_binary()
                                        try:
                                            final_p, fn, info = MediaService.prepare_for_transfer(drop_id, "rubika")
                                            logger.info(f"[rubika->saved] Uploading {final_p.name} ({final_p.stat().st_size} bytes) via Rubika User Session...")
                                            res = await rubika.send_audio_user_session(
                                                final_p, target="me",
                                                caption=f"✅ منتقل شده از ربات روبیکا\n📄 {clean_display_filename(fn)}"
                                            )
                                            logger.info(f"[rubika->saved] User Session result: {res}")
                                            if res.get("ok"):
                                                await rubika.send_message(chat_id, f"✅ فایل با موفقیت به پیام‌های ذخیره‌شده (Saved Messages) شما منتقل شد!\n📄 {clean_display_filename(fn)}")
                                            else:
                                                await rubika.send_message(chat_id, f"❌ خطا در ارسال به پیام‌های ذخیره‌شده: {res.get('error') or res}")
                                        except Exception as e:
                                            logger.error(f"[rubika->saved] Error transferring to Saved Messages: {e}")
                                            await rubika.send_message(chat_id, f"❌ خطا در انتقال به پیام‌های ذخیره‌شده: {e}")
                                    continue

                                # Customer Buttons
                                if btn_id in ("btn_courses", "courses", "لیست دوره‌ها", "📚 لیست دوره‌های آموزشی"):
                                    prods = await StoreService.get_products(is_free_only=False)
                                    if not prods:
                                        await rubika.send_message(chat_id, "📚 در حال حاضر دوره‌ای فعال نیست.", inline_keypad=get_default_rubika_main_keyboard())
                                    else:
                                        lines = ["📚 <b>لیست دوره‌های آموزشی فعال:</b>\n"]
                                        for p in prods:
                                            lines.append(f"🎓 <b>{p.name}</b>\n💰 قیمت: {p.price:,} تومان\n📝 {p.description}\n")
                                        lines.append("جهت ثبت سفارش با پشتیبانی در ارتباط باشید.")
                                        await rubika.send_message(chat_id, "\n".join(lines), inline_keypad=get_default_rubika_main_keyboard())

                                elif btn_id in ("btn_gift", "gift", "هدیه", "🎁 دانلود هدیه رایگان"):
                                    gifts = await StoreService.get_products(is_free_only=True)
                                    if not gifts:
                                        await rubika.send_message(chat_id, "🎁 در حال حاضر فایل هدیه فعالی وجود ندارد.", inline_keypad=get_default_rubika_main_keyboard())
                                    else:
                                        g = gifts[0]
                                        txt = f"🎁 <b>هدیه ویژه شما:</b>\n\n🎓 {g.name}\n📝 {g.description}"
                                        await rubika.send_message(chat_id, txt, inline_keypad=get_default_rubika_main_keyboard())

                                elif btn_id in ("btn_account", "account", "حساب کاربری", "👤 حساب کاربری و سفارشات"):
                                    cust = await StoreService.get_or_create_customer(chat_id, platform="rubika")
                                    orders = await StoreService.get_customer_orders(chat_id, platform="rubika")
                                    txt = (
                                        f"👤 <b>اطلاعات حساب کاربری شما در روبیکا:</b>\n\n"
                                        f"🆔 شناسه: <code>{chat_id}</code>\n"
                                        f"💰 موجودی کیف پول: <code>{cust.wallet_balance:,} تومان</code>\n"
                                        f"📦 تعداد سفارش‌ها: <code>{len(orders)}</code>"
                                    )
                                    await rubika.send_message(chat_id, txt, inline_keypad=get_default_rubika_main_keyboard())

                                elif btn_id in ("btn_support", "support", "پشتیبانی", "💬 ارتباط با پشتیبانی"):
                                    txt = (
                                        "💬 <b>ارتباط با واحد پشتیبانی:</b>\n\n"
                                        "در صورت داشتن هرگونه سوال یا نیاز به راهنمایی، پیام خود را در همین گفتگو ارسال فرمایید."
                                    )
                                    await rubika.send_message(chat_id, txt, inline_keypad=get_default_rubika_main_keyboard())

                            # Handle Message Events
                            elif event_type == "message":
                                raw_msg = u.get("msg_obj") or u.get("raw") or {}
                                text = (u.get("text") or "").strip()

                                # Direct Download Link (URL Uploader Gate in Rubika)
                                if (text.startswith("http://") or text.startswith("https://")) and rubika.is_admin(chat_id) and not user_act:
                                    probe = await UrlService.probe_url(text)
                                    if probe["is_valid"]:
                                        url_id = uuid.uuid4().hex[:8]
                                        session_manager.create_session(f"rurl_{url_id}", {**probe, "url_id": url_id})
                                        card_txt = (
                                            "🌐 <b>لینک مستقیم دانلود شناسایی شد:</b>\n\n"
                                            f"📄 نام فایل: <code>{clean_display_filename(probe['filename'])}</code>\n"
                                            f"📦 حجم تقریبی: <b>{human_size(probe['file_size'])}</b>\n\n"
                                            "لطفاً نحوه دریافت و ارسال در روبیکا را انتخاب فرمایید:"
                                        )
                                        kb_url = build_rubika_inline_keyboard([
                                            [{"button_text": "⚡️ شروع و دریافت در روبیکا", "id": f"rurldl:auto:{url_id}"}],
                                            [
                                                {"button_text": "🎵 استخراج و تبدیل به MP3", "id": f"rurldl:audio:{url_id}"},
                                                {"button_text": "📁 دریافت در حالت فایل", "id": f"rurldl:doc:{url_id}"}
                                            ],
                                            [{"button_text": "❌ انصراف", "id": f"rurldl:cancel:{url_id}"}]
                                        ])
                                        await rubika.send_message(chat_id, card_txt, inline_keypad=kb_url)
                                        continue

                                # Handle Active User Actions (Text Inputs)
                                if user_act:
                                    # Audio Trimming
                                    if user_act.get("action") == "await_trim_time" and text:
                                        drop_id = user_act["drop_id"]
                                        drop = session_manager.get_session(drop_id)
                                        if drop:
                                            tech = inspect_technical_metadata(drop.get("working_path") or "")
                                            total_dur = float(tech.get("duration_sec", 0))
                                            start_s, end_s = parse_trim_input(text, total_duration=total_dur)
                                            if start_s is None:
                                                await rubika.send_message(chat_id, "❌ فرمت زمان نامعتبر است. لطفاً مانند 02:10 - 21:28 ارسال فرمایید.")
                                                continue
                                            session_manager.clear_user_action(f"rubika_{chat_id}")
                                            await rubika.send_message(chat_id, "⏳ در حال برش فایل صوتی...")
                                            ok, trimmed_p = MediaService.trim_audio(drop["working_path"], start_s, end_s)
                                            if ok and trimmed_p.exists():
                                                t_tech = inspect_technical_metadata(trimmed_p)
                                                t_dur = t_tech.get("duration_sec", 0)
                                                await rubika.bot_client.send_document(
                                                    chat_id, trimmed_p,
                                                    caption=f"✂️ فایل صوتی برش‌خورده ({format_duration(start_s)} تا {format_duration(end_s or total_dur)}):\n📄 {trimmed_p.name}"
                                                )
                                                new_drop_id = uuid.uuid4().hex[:8]
                                                new_data = MediaService.register_incoming_message_meta(
                                                    new_drop_id, "rubika", chat_id, str(trimmed_p), trimmed_p.name, trimmed_p.stat().st_size,
                                                    media_type="audio", api_meta={"filename": trimmed_p.name, "duration_sec": t_dur}
                                                )
                                                new_data["working_path"] = str(trimmed_p)
                                                new_data["is_downloaded_locally"] = True
                                                new_card = RubikaFormatter.format_light_card(new_data)
                                                new_kb = build_rubika_media_keyboard(new_drop_id, new_data)
                                                sent_c = await rubika.send_message(chat_id, new_card, inline_keypad=new_kb)
                                                if sent_c and isinstance(sent_c, dict):
                                                    new_data["card_msg_id"] = sent_c.get("data", {}).get("message_id") or sent_c.get("message_id")
                                            else:
                                                await rubika.send_message(chat_id, "❌ خطا در برش فایل صوتی.")
                                        continue

                                    # Metadata Text Editing
                                    if user_act.get("action") in ("await_fn", "await_perf", "await_title") and text:
                                        act = user_act["action"]
                                        drop_id = user_act["drop_id"]
                                        field_map = {"await_fn": "filename", "await_perf": "artist", "await_title": "title"}
                                        MediaService.update_draft_field(drop_id, field_map[act], text)
                                        session_manager.clear_user_action(f"rubika_{chat_id}")
                                        drop = session_manager.get_session(drop_id)
                                        if drop:
                                            txt = RubikaFormatter.format_light_card(drop)
                                            kb = build_rubika_media_keyboard(drop_id, drop, is_sub=False)
                                            card_msg_id = drop.get("card_msg_id")
                                            if card_msg_id:
                                                await rubika.bot_client.edit_message_text(chat_id, card_msg_id, txt, inline_keypad=kb)
                                            else:
                                                sent_m = await rubika.send_message(chat_id, txt, inline_keypad=kb)
                                                if sent_m and isinstance(sent_m, dict):
                                                    drop["card_msg_id"] = sent_m.get("data", {}).get("message_id") or sent_m.get("message_id")
                                        continue

                                    # Cover Image Uploading
                                    if user_act.get("action") == "await_cover":
                                        f_chk = extract_rubika_file_info(raw_msg)
                                        if f_chk:
                                            drop_id = user_act["drop_id"]
                                            cov_path = config.TEMP_DIR / f"cov_{drop_id}.jpg"
                                            dl_ok = await rubika.bot_client.download_file(f_chk["file_id"], cov_path)
                                            if dl_ok and cov_path.exists():
                                                MediaService.update_draft_field(drop_id, "thumb", str(cov_path))
                                                session_manager.clear_user_action(f"rubika_{chat_id}")
                                                drop = session_manager.get_session(drop_id)
                                                if drop:
                                                    txt = RubikaFormatter.format_light_card(drop)
                                                    kb = build_rubika_media_keyboard(drop_id, drop, is_sub=False)
                                                    card_msg_id = drop.get("card_msg_id")
                                                    if card_msg_id:
                                                        await rubika.bot_client.edit_message_text(chat_id, card_msg_id, txt, inline_keypad=kb)
                                                    else:
                                                        sent_m = await rubika.send_message(chat_id, txt, inline_keypad=kb)
                                                        if sent_m and isinstance(sent_m, dict):
                                                            drop["card_msg_id"] = sent_m.get("data", {}).get("message_id") or sent_m.get("message_id")
                                            continue

                                # Handle Incoming Media (Admin Media Hub)
                                file_info = extract_rubika_file_info(raw_msg)
                                if file_info and not user_act:
                                    is_adm = rubika.is_admin(chat_id)
                                    if not is_adm:
                                        txt = (
                                            f"📚 به فروشگاه دوره‌های آموزشی {config.STORE_NAME} خوش آمدید.\n"
                                            "جهت مشاهده دوره‌ها یا ارتباط با پشتیبانی از دکمه‌های زیر استفاده فرمایید:"
                                        )
                                        await rubika.send_message(chat_id, txt, inline_keypad=get_default_rubika_main_keyboard())
                                        continue

                                    f_id = file_info["file_id"]
                                    fn = clean_display_filename(file_info["file_name"])
                                    sz = file_info["file_size"]
                                    suffix = Path(fn).suffix.lower()
                                    is_v = file_info["type"] == "video" or suffix in VIDEO_EXTENSIONS

                                    # Check for existing session to prevent duplicate processing on restart
                                    existing_sess = MediaService.find_existing_session("rubika", chat_id, file_id=f_id, file_name=fn, file_size=sz)
                                    if existing_sess:
                                        logger.info(f"[rubika] File {fn} already registered as drop {existing_sess.get('drop_id')}. Skipping duplicate card.")
                                        continue

                                    drop_id = uuid.uuid4().hex[:8]
                                    api_meta = {
                                        "filename": fn,
                                        "file_size": sz,
                                        "duration_sec": file_info["duration"],
                                        "title": file_info["title"],
                                        "artist": file_info["artist"]
                                    }
                                    data = MediaService.register_incoming_message_meta(
                                        drop_id, "rubika", chat_id, f_id, fn, sz,
                                        media_type="video" if is_v else "audio",
                                        api_meta=api_meta,
                                        caption=text,
                                        raw_message=raw_msg
                                    )
                                    txt = RubikaFormatter.format_light_card(data)
                                    kb = build_rubika_media_keyboard(drop_id, data, is_sub=False)
                                    sent = await rubika.send_message(chat_id, txt, inline_keypad=kb)
                                    if sent and isinstance(sent, dict):
                                        data["card_msg_id"] = sent.get("data", {}).get("message_id") or sent.get("message_id")
                                    continue

                                # Text Commands (/start, /admin, etc.)
                                text_lower = text.lower()
                                if text_lower in ("/start", "start", "شروع", "/admin", "ادمین", "پنل"):
                                    logger.info(f"Rubika /start received from {chat_id}")
                                    await send_rubika_start_flow(chat_id)
                                    continue

                                elif text_lower in ("/myid", "myid", "شناسه من", "شناسه", "guid", "آیدی من", "/guid"):
                                    myid_msg = (
                                        "🆔 <b>شناسه اختصاصی شما در روبیکا (GUID):</b>\n\n"
                                        f"<code>{chat_id}</code>\n\n"
                                        "💡 <i>جهت تعریف خود به عنوان مدیر سیستم، این شناسه را در بخش سکرت‌های هاگینگ‌فیس به عنوان <code>RUBIKA_OWNER_ID</code> یا در پنل مدیریت وب وارد فرمایید.</i>"
                                    )
                                    await rubika.send_message(chat_id, myid_msg, inline_keypad=get_default_rubika_main_keyboard())
                                    continue

                                elif text_lower in ("/ping", "ping", "پینگ"):
                                    start_t = time.time()
                                    db_st = "متصل ✅"
                                    try:
                                        from core.database import fetch_one
                                        await fetch_one("SELECT 1")
                                    except Exception:
                                        db_st = "خطا در اتصال ❌"
                                    lat_ms = int((time.time() - start_t) * 1000)
                                    from services.store_service import get_tehran_now_str
                                    t_time = get_tehran_now_str()
                                    ping_msg = (
                                        "🏓 <b>پنگ سیستم | آنلاین و فعال</b>\n\n"
                                        "🟣 <b>پلتفرم:</b> پیام‌رسان روبیکا (Bot API)\n"
                                        f"⏱ <b>زمان پاسخگویی:</b> <code>{max(1, lat_ms)} ms</code>\n"
                                        f"💾 <b>دیتابیس SQLite:</b> {db_st}\n"
                                        "🌐 <b>سرور ابری:</b> آنلاین (Hugging Face Port 7860)\n"
                                        f"🕒 <b>زمان سرور (تهران):</b> <code>{t_time}</code>"
                                    )
                                    await rubika.send_message(chat_id, ping_msg)
                                    continue

                                elif text_lower in ("/courses", "دوره‌ها", "لیست دوره‌ها", "📚 لیست دوره‌های آموزشی"):
                                    prods = await StoreService.get_products(is_free_only=False)
                                    lines = ["📚 <b>لیست دوره‌های آموزشی فعال:</b>\n"]
                                    for p in prods:
                                        lines.append(f"🎓 <b>{p.name}</b> - {p.price:,} تومان\n{p.description}\n")
                                    await rubika.send_message(chat_id, "\n".join(lines), inline_keypad=get_default_rubika_main_keyboard())

                                elif text_lower in ("/help", "راهنما"):
                                    txt = "💡 <b>راهنمای ربات:</b>\nجهت استفاده از خدمات، دکمه‌های منو را انتخاب فرمایید."
                                    await rubika.send_message(chat_id, txt, inline_keypad=get_default_rubika_main_keyboard())

                        await asyncio.sleep(1.5)
                    else:
                        if resp.status in (502, 503, 504):
                            logger.warning(f"Rubika API gateway notice: HTTP {resp.status} (Temporary Gateway/Proxy unavailable) - retrying in 3s...")
                        else:
                            resp_text = await resp.text()
                            logger.warning(f"Rubika getUpdates non-200 response: status={resp.status} body={resp_text[:200]}")
                        await asyncio.sleep(3)
            except asyncio.TimeoutError:
                await asyncio.sleep(1)
            except Exception as e:
                err_str = str(e)
                if not any(k in err_str.lower() for k in ["timeout", "payload", "connection reset", "closed"]):
                    logger.warning(f"Rubika polling notice: {e}")
                await asyncio.sleep(3)
