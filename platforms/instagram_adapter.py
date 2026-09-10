import os
import json
import random
import asyncio
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List
from core.config import config
from core.logger import get_logger
from services.keyword_service import KeywordService

logger = get_logger("instagram_adapter")

INSTAGRAM_LISTENER_TASK: Optional[asyncio.Task] = None

def convert_audio_to_instagram_voice(src_path: Path | str, out_dir: Optional[Path] = None) -> Path:
    """
    Converts any audio file (mp3, wav, ogg, etc.) to a standard .m4a AAC voice container
    that is strictly compliant with Instagram Direct voice notes.
    """
    src = Path(src_path)
    if not src.exists():
        raise FileNotFoundError(f"Audio file not found: {src}")

    target_dir = out_dir or config.TEMP_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    out_file = target_dir / f"ig_voice_{src.stem}.m4a"

    if src.suffix.lower() == ".m4a" and src.exists():
        return src

    cmd = [
        "ffmpeg", "-y", "-i", str(src),
        "-vn",
        "-c:a", "aac",
        "-b:a", "128k",
        "-ar", "44100",
        "-ac", "1",
        str(out_file)
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if res.returncode == 0 and out_file.exists():
        return out_file
    logger.warning(f"Voice conversion warning, falling back to source: {res.stderr}")
    return src


class InstagramAdapter:
    def __init__(self):
        self.username = (config.INSTAGRAM_USERNAME or "").strip()
        self.password = (config.INSTAGRAM_PASSWORD or "").strip()
        self.session_file = Path(config.INSTAGRAM_SESSION_FILE or "/tmp/instagram_session.json")
        self.client = None
        self.is_authenticated = False
        self.seen_messages = set()

    def has_session(self) -> bool:
        return self.session_file.exists() and self.session_file.stat().st_size > 10

    def get_status_summary(self) -> Dict[str, Any]:
        has_creds = bool(self.username and self.password)
        has_sess = self.has_session()
        is_online = self.is_authenticated
        return {
            "username": self.username or "تنظیم نشده",
            "has_credentials": has_creds,
            "has_session": has_sess,
            "is_online": is_online,
            "status_text": "🟢 متصل و آنلاین (درحال مانیتور دایرکت‌ها)" if is_online else ("🟡 سشن ذخیره‌شده دارد (آماده تست)" if has_sess else ("⚪️ آماده ورود با نام کاربری" if has_creds else "🔴 نام کاربری/رمز ست نشده"))
        }

    def init_client(self) -> bool:
        try:
            from instagrapi import Client
            self.client = Client()
            self.client.delay_range = [2, 5]

            if self.has_session():
                logger.info(f"Loading Instagram session dump from {self.session_file}...")
                self.client.load_settings(str(self.session_file))
                try:
                    # Validate active session
                    self.client.get_timeline_feed()
                    self.is_authenticated = True
                    logger.info("Instagram session restored and verified successfully.")
                    return True
                except Exception as val_err:
                    logger.warning(f"Cached session expired: {val_err}")

            if self.username and self.password:
                logger.info(f"Authenticating Instagram client with username: {self.username}...")
                self.client.login(self.username, self.password)
                self.session_file.parent.mkdir(parents=True, exist_ok=True)
                self.client.dump_settings(str(self.session_file))
                self.is_authenticated = True
                logger.info("Instagram login successful and session dump saved.")
                return True

            return False
        except Exception as e:
            logger.error(f"Instagram initialization error: {e}")
            self.is_authenticated = False
            return False

    async def test_or_login(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        verification_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Interactive login and connection tester handling 2FA / Security Code challenges.
        """
        def _run():
            try:
                from instagrapi import Client
                from instagrapi.exceptions import (
                    TwoFactorRequired,
                    BadPassword,
                    PleaseWaitFewMinutes,
                    ChallengeRequired
                )

                uname = (username or self.username or config.INSTAGRAM_USERNAME or "").strip()
                pwd = (password or self.password or config.INSTAGRAM_PASSWORD or "").strip()

                if not uname or not pwd:
                    return {"status": "ERROR", "error": "نام کاربری یا رمز عبور اینستاگرام ست نشده است."}

                if not self.client:
                    self.client = Client()
                    self.client.delay_range = [2, 5]

                # If verification code provided, complete 2FA login
                if verification_code:
                    logger.info(f"Submitting 2FA verification code for @{uname}...")
                    self.client.login(uname, pwd, verification_code=verification_code.strip())
                    self.session_file.parent.mkdir(parents=True, exist_ok=True)
                    self.client.dump_settings(str(self.session_file))
                    self.is_authenticated = True
                    return {"status": "OK", "message": "ورود دو مرحله‌ای با موفقیت تایید و نشست ذخیره شد."}

                # Try loading existing session first
                if self.has_session():
                    try:
                        self.client.load_settings(str(self.session_file))
                        self.client.get_timeline_feed()
                        self.is_authenticated = True
                        return {"status": "OK", "message": "اتصال سشن قبلی معتبر است و حساب آنلاین می‌باشد."}
                    except Exception:
                        logger.info("Existing session expired, performing fresh login...")

                # Fresh login
                try:
                    self.client.login(uname, pwd)
                    self.session_file.parent.mkdir(parents=True, exist_ok=True)
                    self.client.dump_settings(str(self.session_file))
                    self.is_authenticated = True
                    return {"status": "OK", "message": "ورود به حساب اینستاگرام با موفقیت انجام شد و نشست ذخیره گردید."}
                except TwoFactorRequired:
                    return {
                        "status": "NEED_2FA",
                        "message": "حساب شما دارای تایید دو مرحله‌ای (2FA) است. لطفاً کد تایید پیامک‌شده یا اپلیکیشن Authenticator را ارسال فرمایید:"
                    }
                except ChallengeRequired:
                    return {
                        "status": "NEED_CHALLENGE",
                        "message": "اینستاگرام درخواست تایید امنیتی (Security Challenge) داده است. کد ارسال‌شده به ایمیل یا شماره موبایل اکانت را ارسال فرمایید:"
                    }
                except BadPassword:
                    return {"status": "ERROR", "error": "رمز عبور اینستاگرام اشتباه است."}
                except PleaseWaitFewMinutes:
                    return {"status": "ERROR", "error": "محدودیت موقت اینستاگرام (Please wait a few minutes). لطفاً چند دقیقه دیگر تلاش کنید."}

            except Exception as e:
                logger.error(f"Instagram test_or_login error: {e}")
                err_str = str(e)
                if "two_factor" in err_str.lower() or "twofactor" in err_str.lower():
                    return {
                        "status": "NEED_2FA",
                        "message": "حساب نیازمند کد تایید دو مرحله‌ای است. لطفاً کد را ارسال فرمایید:"
                    }
                if "challenge" in err_str.lower():
                    return {
                        "status": "NEED_CHALLENGE",
                        "message": "کد چالش امنیتی اینستاگرام را ارسال فرمایید:"
                    }
                return {"status": "ERROR", "error": err_str}

        return await asyncio.to_thread(_run)

    async def logout(self) -> bool:
        def _logout():
            try:
                if self.session_file.exists():
                    self.session_file.unlink()
                self.is_authenticated = False
                self.client = None
                return True
            except Exception as e:
                logger.error(f"Logout error: {e}")
                return False
        return await asyncio.to_thread(_logout)

    async def send_direct_message(
        self,
        user_id_or_username: str | int,
        text: str,
        thread_id: Optional[str] = None
    ) -> Dict[str, Any]:
        if not self.is_authenticated or not self.client:
            if not self.init_client():
                return {"ok": False, "error": "حساب اینستاگرام متصل نیست. لطفاً ابتدا لاگین فرمایید."}

        def _send():
            try:
                if thread_id:
                    res = self.client.direct_send(text, thread_ids=[int(thread_id)])
                else:
                    target_id = str(user_id_or_username)
                    if not target_id.isdigit():
                        target_id = str(self.client.user_id_from_username(str(user_id_or_username)))
                    res = self.client.direct_send(text, user_ids=[int(target_id)])
                return {"ok": True, "result": str(res)}
            except Exception as e:
                logger.error(f"Instagram direct_send error: {e}")
                return {"ok": False, "error": str(e)}
        return await asyncio.to_thread(_send)

    async def send_direct_voice(
        self,
        user_id_or_username: str | int,
        voice_path: str | Path,
        thread_id: Optional[str] = None
    ) -> Dict[str, Any]:
        if not self.is_authenticated or not self.client:
            if not self.init_client():
                return {"ok": False, "error": "حساب اینستاگرام متصل نیست."}

        def _send_voice():
            try:
                converted_voice = convert_audio_to_instagram_voice(voice_path)
                if thread_id:
                    res = self.client.direct_send_voice(str(converted_voice), thread_ids=[int(thread_id)])
                else:
                    target_id = str(user_id_or_username)
                    if not target_id.isdigit():
                        target_id = str(self.client.user_id_from_username(str(user_id_or_username)))
                    res = self.client.direct_send_voice(str(converted_voice), user_ids=[int(target_id)])
                return {"ok": True, "result": str(res)}
            except Exception as e:
                logger.error(f"Instagram direct_send_voice error: {e}")
                return {"ok": False, "error": str(e)}
        return await asyncio.to_thread(_send_voice)

    async def get_direct_threads(self, amount: int = 10) -> List[Any]:
        if not self.is_authenticated or not self.client:
            if not self.init_client():
                return []
        def _get():
            try:
                return self.client.direct_threads(amount=amount)
            except Exception as e:
                logger.error(f"Instagram get_direct_threads error: {e}")
                return []
        return await asyncio.to_thread(_get)


async def run_instagram_listener_engine(telegram_adapter_instance=None):
    """
    Continuous background monitor listening for new Instagram direct messages.
    Automatically starts and stays resilient even before/after user login.
    """
    ig = InstagramAdapter()
    logger.info("Instagram Auto-responder supervisor started.")

    while True:
        try:
            if not ig.is_authenticated:
                if not ig.init_client():
                    # Wait for user login via Telegram panel
                    await asyncio.sleep(20.0)
                    continue

            my_pk = str(getattr(ig.client, "user_id", "") or "")
            await asyncio.sleep(random.uniform(12.0, 22.0))

            threads = await ig.get_direct_threads(amount=8)
            for t in threads:
                if not getattr(t, "messages", None):
                    continue

                latest_msg = t.messages[0]
                msg_id = str(getattr(latest_msg, "id", "") or "")
                sender_pk = str(getattr(latest_msg, "user_id", "") or "")

                if not msg_id or msg_id in ig.seen_messages or sender_pk == my_pk:
                    continue

                ig.seen_messages.add(msg_id)
                msg_text = str(getattr(latest_msg, "text", "") or "").strip()
                if not msg_text:
                    continue

                logger.info(f"Instagram incoming message from thread {t.id}: '{msg_text}'")

                rule = await KeywordService.match_keyword(msg_text, platform="INSTAGRAM")
                if not rule:
                    continue

                jitter_delay = random.uniform(2.5, 5.5)
                logger.info(f"Keyword matched rule ID={rule.id} ('{rule.keyword}'). Waiting {jitter_delay:.1f}s anti-ban jitter...")
                await asyncio.sleep(jitter_delay)

                sender_username = "کاربر"
                if getattr(t, "users", None) and len(t.users) > 0:
                    sender_username = getattr(t.users[0], "username", "کاربر")

                # 1. Send Text Reply
                if rule.response_type in ("TEXT", "TEXT_VOICE") and rule.response_text:
                    await ig.send_direct_message(sender_pk, rule.response_text, thread_id=t.id)
                    logger.info(f"Auto-replied text to @{sender_username} on Instagram.")

                # 2. Send Voice Note
                if rule.response_type in ("VOICE", "TEXT_VOICE") and rule.media_id:
                    voice_file = Path(rule.media_id)
                    if voice_file.exists():
                        await asyncio.sleep(random.uniform(1.5, 3.0))
                        await ig.send_direct_voice(sender_pk, voice_file, thread_id=t.id)
                        logger.info(f"Auto-sent voice note to @{sender_username} on Instagram.")

                # 3. Notify Admin on Telegram
                if telegram_adapter_instance:
                    admin_id = config.TELEGRAM_OWNER_ID or telegram_adapter_instance.get_admin_id()
                    if admin_id:
                        noti_txt = (
                            f"📸 <b>پاسخ خودکار اینستاگرام ارسال شد!</b>\n\n"
                            f"👤 <b>کاربر:</b> <code>@{sender_username}</code>\n"
                            f"🎯 <b>کلمه کلیدی:</b> <code>{rule.keyword}</code>\n"
                            f"📝 <b>متن دریافتی:</b> <i>{msg_text}</i>\n"
                            f"⚡️ <b>نوع پاسخ:</b> <code>{rule.response_type}</code>"
                        )
                        asyncio.create_task(telegram_adapter_instance.send_message(admin_id, noti_txt))

        except Exception as e:
            logger.error(f"Instagram listener loop error: {e}")
            await asyncio.sleep(25.0)
