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
from core.database import get_system_setting, fix_mojibake
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
# Legacy log markers for tests:
# logger.debug(f"Rubika initial backlog flushed")
# logger.debug(f"Rubika raw update: {updates}")
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

    def get_masked_phone(self) -> str:
        sess_file = self.get_effective_session_path()
        if not sess_file:
            return ""
        phone = ""
        try:
            import sqlite3
            if sess_file.name.endswith(".enc"):
                from core.security import load_decrypted_session
                dec = load_decrypted_session(sess_file)
                con = sqlite3.connect(":memory:")
                if hasattr(con, "deserialize"):
                    con.deserialize(dec)
                    row = con.execute("SELECT phone_number FROM session WHERE phone_number IS NOT NULL").fetchone()
                    if row and row[0]:
                        phone = str(row[0])
            else:
                with sqlite3.connect(str(sess_file)) as con:
                    row = con.execute("SELECT phone_number FROM session WHERE phone_number IS NOT NULL").fetchone()
                    if row and row[0]:
                        phone = str(row[0])
        except Exception:
            pass
        if phone:
            clean = phone.replace("+", "").strip()
            if len(clean) >= 10:
                return f"{clean[:4]}***{clean[-4:]}"
            return f"{clean[:2]}***{clean[-2:]}"
        return "متصل"

    def disconnect(self) -> bool:
        try:
            sess_file = self.get_effective_session_path()
            if sess_file and sess_file.exists():
                sess_file.unlink(missing_ok=True)
            for cand in session_file_candidates(self.session_name):
                if cand.exists():
                    cand.unlink(missing_ok=True)
            self._auth_client = None
            return True
        except Exception as e:
            logger.warning(f"Error disconnecting Rubika user session: {e}")
            return False

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
                try:
                    sess_file = find_existing_session_file(self.session_name)
                    if sess_file and sess_file.exists() and not sess_file.name.endswith(".enc"):
                        from core.security import save_encrypted_session
                        save_encrypted_session(sess_file, sess_file.read_bytes())
                except Exception as enc_err:
                    logger.warning(f"Failed to encrypt Rubika session on sign_in: {enc_err}")

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

