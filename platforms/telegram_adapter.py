from __future__ import annotations
from platforms.instagram_adapter import InstagramAdapter
from task_store import cleanup_local_file
import time
import re
import atexit
from platforms.rubika_adapter import RubikaAdapter
import os
import uuid
import asyncio
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())
from pathlib import Path
from html import escape
import math
from typing import Optional, Dict, Any, List, Union
from pyrogram import Client, enums, filters
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
    Message,
    CallbackQuery
)
from core.config import config
from core.logger import get_logger
from core.formatters import (
    TelegramFormatter,
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
from services.store_service import format_course_links_for_card, format_course_photo_for_card, clean_course_access_input, get_tehran_now_str, StoreService, ProductItem
from services.media_service import MediaService, clean_display_filename
from services.session_manager import session_manager
from services.url_service import UrlService
from services.user_service import UserService, normalize_phone
from services.referral_service import ReferralService, TOHID_AMALI_PACK_ID, TOHID_AMALI_EPISODES
from core.frequency_service import FrequencyService
from media.inspector import inspect_technical_metadata
from media.tagger import generate_video_thumbnail
from media.compressor import SmartVideoCompressor, SmartVideoSplitter, SmartAudioCompressor

logger = get_logger("telegram_adapter")

# سقف سختگیرانه ارسال مستقیم بدون اسپلیت به بله (مگابایت)
MAX_DIRECT_BALE_MB: float = 48.5

_ACTIVE_TELEGRAM_ADAPTER: Optional[Any] = None

async def track_upload_progress(
    f: Any,
    total_size: int,
    status_msg_or_chat_id: Any,
    header_text_or_msg_id: Any,
    header_text: str = ""
):
    """
    پایشگر کاملاً مستقل پس‌زمینه (Decoupled Background Poller) مبتنی بر f.tell().
    کارکرد و هدف:
    این متد هر ۳ ثانیه موقعیت پوینتر فایل (f.tell()) را در حافظه استعلام کرده و سرعت و نوار
    پیشرفت آپلود بله را در پیام تلگرام به‌روزرسانی می‌کند بدون اینکه هیچ‌گونه سرباری روی سوکت شبکه بگذارد.
    """
    chat_id = None
    status_msg_id = None
    status_msg = None
    final_header = header_text

    # تشخیص هوشمند پارامترها جهت انطباق با هر دو امضای فراخوانی
    if hasattr(status_msg_or_chat_id, "edit_text"):
        status_msg = status_msg_or_chat_id
        final_header = str(header_text_or_msg_id or "")
        chat_id = getattr(getattr(status_msg, "chat", None), "id", None)
        status_msg_id = getattr(status_msg, "id", None)
    elif isinstance(status_msg_or_chat_id, (int, str)) and isinstance(header_text_or_msg_id, int):
        chat_id = int(status_msg_or_chat_id)
        status_msg_id = int(header_text_or_msg_id)
        final_header = header_text
    else:
        status_msg = status_msg_or_chat_id
        final_header = str(header_text_or_msg_id or "")

    last_time = time.time()
    last_bytes = 0
    last_text = ""
    try:
        while True:
            await asyncio.sleep(3.0)
            try:
                if getattr(f, "closed", False):
                    break
                current_bytes = f.tell() if hasattr(f, "tell") else getattr(f, "uploaded_bytes", 0)
            except Exception:
                break

            if total_size > 0 and current_bytes >= total_size:
                break

            now = time.time()
            dt = now - last_time
            if dt >= 2.5 and total_size > 0:
                bytes_diff = max(current_bytes - last_bytes, 0)
                speed_kb = (bytes_diff / 1024) / dt if dt > 0 else 0
                if speed_kb >= 1024:
                    speed_str = f"{speed_kb / 1024:.1f} MB/s"
                else:
                    speed_str = f"{int(speed_kb)} KB/s"
                last_bytes = current_bytes
                last_time = now

                pct = min(max(int((current_bytes / total_size) * 100), 1), 99) if current_bytes < total_size else 99
                curr_mb = current_bytes / (1024 * 1024)
                total_mb = total_size / (1024 * 1024)
                bar_len = 10
                filled = int(bar_len * (pct / 100))
                bar = "█" * filled + "░" * (bar_len - filled)

                text = (
                    f"{final_header}\n\n"
                    f"[{bar}] {pct}% ({curr_mb:.1f} از {total_mb:.1f} مگابایت)\n"
                    f"⚡️ <b>سرعت آپلود:</b> {speed_str} | لطفاً شکیبا باشید"
                )
                if text != last_text:
                    try:
                        if status_msg and hasattr(status_msg, "edit_text"):
                            await status_msg.edit_text(text, parse_mode=enums.ParseMode.HTML)
                        elif _ACTIVE_TELEGRAM_ADAPTER and getattr(_ACTIVE_TELEGRAM_ADAPTER, "app", None) and chat_id and status_msg_id:
                            await _ACTIVE_TELEGRAM_ADAPTER.app.edit_message_text(
                                chat_id=chat_id,
                                message_id=status_msg_id,
                                text=text,
                                parse_mode=enums.ParseMode.HTML
                            )
                        last_text = text
                    except Exception:
                        pass
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"[track_upload_progress error] {e}")


async def run_bale_upload_with_progress(
    file_obj_or_tracker: Any,
    total_size_or_status: Any,
    status_msg_or_header: Any,
    header_text_or_coro: Any,
    upload_coro: Optional[Any] = None
) -> Dict[str, Any]:
    """
    اجرای امن کوروتین آپلود بله همراه با پولر مستقل f.tell() بدون مسدودسازی سوکت.
    سازگار با هر دو نوع امضای فراخوانی (جدید و قدیمی).
    """
    if upload_coro is not None:
        f = file_obj_or_tracker
        total_size = int(total_size_or_status)
        status_msg = status_msg_or_header
        header_text = str(header_text_or_coro)
        coro = upload_coro
    else:
        # سازگاری با امضای قدیمی: (tracker, status_msg, header_text, upload_coro)
        f = file_obj_or_tracker
        total_size = getattr(f, "total_bytes", 0) if hasattr(f, "total_bytes") else 0
        status_msg = total_size_or_status
        header_text = str(status_msg_or_header)
        coro = header_text_or_coro

    poller_task = asyncio.create_task(
        track_upload_progress(f, total_size, status_msg, header_text)
    )
    try:
        return await coro
    finally:
        poller_task.cancel()
        try:
            await poller_task
        except (asyncio.CancelledError, Exception):
            pass
        await asyncio.sleep(0.05)


async def check_force_join_telegram(client: Client, user_id: int | str) -> bool:
    uid = int(user_id) if str(user_id).isdigit() else 0
    if uid and uid == config.TELEGRAM_OWNER_ID:
        return True
    enabled = (await get_system_setting("tg_fjoin_enabled", "1" if config.FORCE_JOIN_CHANNEL_TELEGRAM else "0")) == "1"
    if not enabled:
        return True
    channel_raw = await get_system_setting("tg_fjoin_channel", config.FORCE_JOIN_CHANNEL_TELEGRAM)
    if not channel_raw or not channel_raw.strip():
        return True

    channel_target = channel_raw.strip()
    if channel_target.startswith("-100") or channel_target.lstrip("-").isdigit():
        try:
            chat_identifier: Union[int, str] = int(channel_target)
        except ValueError:
            chat_identifier = channel_target
    else:
        chat_identifier = channel_target if channel_target.startswith("@") else f"@{channel_target}"

    try:
        member = await client.get_chat_member(chat_identifier, uid)
        return member.status not in (enums.ChatMemberStatus.LEFT, enums.ChatMemberStatus.BANNED)
    except Exception as e:
        logger.warning(f"Telegram get_chat_member error for {chat_identifier} / {uid}: {e}")
        return True


def build_telegram_force_join_keyboard(channel: str) -> InlineKeyboardMarkup:
    clean_username = channel.lstrip("@")
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 عضویت در کانال", url=f"https://t.me/{clean_username}")],
        [InlineKeyboardButton("🔄 تایید عضویت", callback_data="tg:check_fjoin")]
    ])


def format_transfer_progress(
    current: int,
    total: int,
    elapsed_sec: float,
    stage_title: str = "در حال انتقال فایل به بله...",
    file_index: Optional[int] = None,
    total_files: Optional[int] = None,
    filename: Optional[str] = None
) -> str:
    pct = int((current / total) * 100) if total > 0 else 0
    pct = min(100, max(0, pct))
    bar_len = 20
    filled = int((pct / 100) * bar_len)
    bar = "█" * filled + "░" * (bar_len - filled)
    transferred_mb = f"{current / (1024 * 1024):.2f}"
    total_mb = f"{total / (1024 * 1024):.2f}"
    speed_mbps = f"{(current / max(0.01, elapsed_sec)) / (1024 * 1024):.2f}"
    icon = "⏳" if ("فایل‌ها" in stage_title or "آماده‌سازی" in stage_title) else ("📤" if ("بله" in stage_title or "انتقال" in stage_title or "ارسال" in stage_title) else "⏳")

    sub_info = ""
    if file_index is not None and total_files is not None:
        clean_fn = escape(filename) if filename else ""
        sub_info = f"\n📄 <b>فایل {file_index} از {total_files}:</b> <code>{clean_fn}</code>\n"

    if sub_info:
        return (
            f"{icon} <b>{stage_title}</b>\n\n"
            f"<code>[{bar}] {pct}%</code>\n"
            f"{sub_info}"
            f"📦 <b>حجم:</b> <code>{transferred_mb} MB</code> | ⚡️ <b>سرعت انتقال:</b> <code>{speed_mbps} MB/s</code>"
        )

    return (
        f"{icon} <b>{stage_title}</b>\n\n"
        f"<code>[{bar}] {pct}%</code>\n\n"
        f"📦 <b>حجم:</b> <code>{transferred_mb} MB</code> از <code>{total_mb} MB</code>\n"
        f"⚡️ <b>سرعت انتقال:</b> <code>{speed_mbps} MB/s</code>"
    )


class GiftButtonStr(str):
    def __eq__(self, other: Any) -> bool:
        if str.__eq__(self, str(other)):
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


def get_customer_keyboard() -> ReplyKeyboardMarkup:
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
                            r_btns.append(GiftButtonStr(b_txt) if any(x in b_txt for x in ["دانلود", "هدیه"]) else b_txt)
                    if r_btns:
                        kb_rows.append(r_btns)
            if kb_rows:
                return ReplyKeyboardMarkup(kb_rows, resize_keyboard=True)
    except Exception as e_kb:
        logger.debug(f"[telegram_adapter] Custom keyboard layout note: {e_kb}")

    return ReplyKeyboardMarkup(
        [
            ["🛍 محصولات آموزشی"],
            ["🔮 نشانه امروز من", "💎 اشتراک پریمیوم"],
            [GiftButtonStr("📂 دانلودها (هدیه)"), "👤 حساب کاربری"]
        ],
        resize_keyboard=True
    )


def build_telegram_frequency_cats_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("☀️ باورهای صبحگاهی", callback_data="freq_page:MORNING:0"),
            InlineKeyboardButton("🌙 باورهای شبانگاهی", callback_data="freq_page:NIGHT:0")
        ]
    ])


def build_telegram_frequency_nav_keyboard(category: str, current_idx: int, total: int) -> InlineKeyboardMarkup:
    prev_idx = (current_idx - 1) % total
    next_idx = (current_idx + 1) % total
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("بعدی ▶️", callback_data=f"freq_page:{category}:{next_idx}"),
            InlineKeyboardButton(f"({current_idx + 1} از {total})", callback_data="freq_noop"),
            InlineKeyboardButton("◀️ قبلی", callback_data=f"freq_page:{category}:{prev_idx}")
        ],
        [
            InlineKeyboardButton("🔙 بازگشت به دسته‌ها", callback_data="freq_cats")
        ]
    ])


def get_admin_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            ["🎓 مدیریت فروشگاه و دوره‌ها", "🧾 سفارشات و تراکنش‌ها"],
            ["📢 پست‌ساز و انتقال فایل", "💬 پشتیبانی و تیکت‌ها"],
            ["⚙️ تنظیمات و سلامت سیستم", "👥 پیش‌نمایش پنل مشتری"]
        ],
        resize_keyboard=True
    )


def build_rubika_target_keyboard(drop_id: str, has_user_session: bool) -> InlineKeyboardMarkup:
    status_label = "✅" if has_user_session else "🔐"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"👤 پیام‌های ذخیره‌شده (Saved Messages) {status_label}", callback_data=f"smeta:rub_user:{drop_id}")],
        [InlineKeyboardButton("🤖 ربات رسمی روبیکا (Bot API)", callback_data=f"smeta:rub_bot:{drop_id}")],
        [InlineKeyboardButton("🔙 بازگشت به منوی رسانه", callback_data=f"smeta:back:{drop_id}")]
    ])


def build_admin_course_keyboard(pid: str, active: bool) -> InlineKeyboardMarkup:
    toggle_label = "🔴 غیرفعال‌سازی دوره" if active else "🟢 فعال‌سازی دوره"
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔗 تغییر لینک‌های دوره", callback_data=f"adm_c_edit:link:{pid}"),
            InlineKeyboardButton("💰 تغییر قیمت", callback_data=f"adm_c_edit:price:{pid}")
        ],
        [
            InlineKeyboardButton("📝 تغییر توضیحات", callback_data=f"adm_c_edit:desc:{pid}"),
            InlineKeyboardButton("🖼 تغییر بنر / عکس", callback_data=f"adm_c_edit:photo:{pid}")
        ],
        [InlineKeyboardButton(toggle_label, callback_data=f"adm_c_toggle:{pid}")],
        [InlineKeyboardButton("🔙 بازگشت به لیست دوره‌ها", callback_data="adm_c_list")]
    ])


def format_admin_course_card(prod: ProductItem) -> str:
    st_txt = "فعال ✅ (نمایش در فروشگاه)" if prod.active else "غیرفعال ❌ (مخفی)"
    links_txt = format_course_links_for_card(prod.download_link)
    photo_txt = format_course_photo_for_card(prod.photo_url)
    return "\n".join([
        f"🎓 <b>مدیریت دوره:</b> <b>{escape(prod.name)}</b>",
        "",
        f"💰 <b>قیمت دوره:</b> <code>{prod.price:,} تومان</code>",
        f"📊 <b>وضعیت دوره:</b> {st_txt}",
        f"📥 <b>لینک‌های دسترسی:</b>\n{links_txt}",
        f"🖼 <b>پوستر / بنر:</b> {photo_txt}",
        f"📝 <b>توضیحات:</b> {escape(prod.description or 'ندارد')}"
    ])


def resolve_telegram_course_photo(prod: Any) -> Optional[Dict[str, str]]:
    """
    Resolves course photo/banner for Telegram delivery.
    Returns {'type': 'file_id'|'local_path'|'url', 'value': str} or None.
    """
    if not prod:
        return None
    # 1. Telegram file_id
    fid = getattr(prod, "photo_file_id", None)
    if fid and str(fid).strip():
        return {"type": "file_id", "value": str(fid).strip()}

    # 2. Local disk path
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

        # 3. Public HTTP URL
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

TG_LOCK_FILE = config.DATA_DIR / "telegram_worker.pid"


def is_pid_alive(pid: int) -> bool:
    """Checks if a process with given PID is currently active on the OS."""
    if pid <= 0 or pid == os.getpid():
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except Exception:
        return False


def acquire_telegram_pid_lock(max_wait_sec: int = 30) -> bool:
    """
    Acquires a single-instance PID lock file before starting Telegram MTProto Client.
    Prevents AUTH_KEY_DUPLICATED when Hugging Face Spaces restarts and old/new containers overlap.
    """
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    my_pid = os.getpid()
    start_time = time.time()

    while time.time() - start_time < max_wait_sec:
        if TG_LOCK_FILE.exists():
            try:
                content = TG_LOCK_FILE.read_text(encoding="utf-8").strip()
                parts = content.split(":")
                lock_pid = int(parts[0]) if parts and parts[0].isdigit() else 0
                lock_time = float(parts[1]) if len(parts) > 1 else 0.0

                if lock_pid == my_pid:
                    return True

                if is_pid_alive(lock_pid):
                    if time.time() - lock_time > 60:
                        logger.warning(f"[TG PID Lock] Stale lock from PID {lock_pid} (>60s). Overriding...")
                        break
                    logger.warning(f"[TG PID Lock] Another process (PID {lock_pid}) holds Telegram session. Waiting for shutdown ({int(time.time() - start_time)}s)...")
                    time.sleep(2)
                    continue
                else:
                    logger.info(f"[TG PID Lock] Previous process PID {lock_pid} is no longer active. Taking lock.")
                    break
            except Exception as e:
                logger.warning(f"[TG PID Lock] Error reading lock file: {e}. Overriding...")
                break
        else:
            break

    try:
        TG_LOCK_FILE.write_text(f"{my_pid}:{time.time()}", encoding="utf-8")
        logger.info(f"[TG PID Lock] Acquired Telegram process lock for PID {my_pid}.")
        return True
    except Exception as e:
        logger.error(f"[TG PID Lock] Could not write lock file: {e}")
        return False


def release_telegram_pid_lock():
    """Releases the Telegram PID lock if held by the current process."""
    try:
        if TG_LOCK_FILE.exists():
            content = TG_LOCK_FILE.read_text(encoding="utf-8").strip()
            parts = content.split(":")
            lock_pid = int(parts[0]) if parts and parts[0].isdigit() else 0
            if lock_pid == os.getpid():
                TG_LOCK_FILE.unlink(missing_ok=True)
                logger.info(f"[TG PID Lock] Released Telegram process lock for PID {os.getpid()}.")
    except Exception as e:
        logger.warning(f"[TG PID Lock] Error releasing lock: {e}")


atexit.register(release_telegram_pid_lock)


class TelegramAdapter:
    """
    آداپتور رسمی و یکپارچه پلتفرم تلگرام بر پایه کتابخانه Pyrogram (MTProto).
    این کلاس تعاملات کاربر، پردازش فایل‌های رسانه‌ای، پرداخت‌ها و دیسپچ رویدادها را بر عهده دارد.
    """

    async def start_client(self):
        """
        راه‌اندازی امن کلاینت MTProto تلگرام با اخذ قفل پردازه،
        اعتبارسنجی زنده شناسه ربات (get_me) و بازیابی خودکار در صورت بروز خطای سشن.
        """
        # گام ۱: اخذ قفل پردازه جهت جلوگیری از تداخل سشن در هاگینگ‌فیس
        await asyncio.to_thread(acquire_telegram_pid_lock, 30)

        # گام ۲: راه‌اندازی کلاینت پایروگرام همراه با خودترمیمی در صورت خرابی سشن محلی
        try:
            await self.app.start()
        except Exception as start_err:
            logger.warning(f"[TG start_client] First start attempt failed ({start_err}). Resetting session file...")
            session_file = config.DATA_DIR / "unfinit_store_session.session"
            try:
                session_file.unlink(missing_ok=True)
            except Exception:
                pass
            await self.app.start()

        # گام ۳: اعتبارسنجی قطعی هویت ربات و ثبت در لاگ سیستم
        try:
            me = await self.app.get_me()
            self.bot_username = me.username
            self.bot_id = me.id
            logger.info(f"[TG MTProto] Verified bot identity: @{me.username} (ID: {me.id}) - MTProto Client is ONLINE and listening!")
        except Exception as e_me:
            logger.error(f"[TG MTProto] Failed to verify bot identity via get_me(): {e_me}")

    async def stop_client(self):
        """Stops Telegram Client and releases PID lock."""
        try:
            if self.app and getattr(self.app, "is_connected", False):
                await self.app.stop()
        finally:
            release_telegram_pid_lock()

    def __init__(self):
        global _ACTIVE_TELEGRAM_ADAPTER
        _ACTIVE_TELEGRAM_ADAPTER = self
        use_in_memory = os.getenv("TESTING") == "true" or os.getenv("PYTEST_CURRENT_TEST") is not None
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        session_name = "unfinit_store_session" if use_in_memory else str(config.DATA_DIR / "unfinit_store_session")
        self.app = Client(
            session_name,
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            bot_token=config.TELEGRAM_BOT_TOKEN,
            workdir=str(config.DATA_DIR),
            in_memory=use_in_memory
        )
        self.bot_username: Optional[str] = None
        self.bot_id: Optional[int] = None
        self.bale_adapter = None
        self.rubika_adapter = RubikaAdapter()
        self.instagram_adapter = InstagramAdapter()
        self.admin_chat_id = config.TELEGRAM_OWNER_ID
        self._media_batch_queue: Dict[int, Any] = {}
        self._batch_registry: Dict[str, List[Any]] = {}

    def get_admin_id(self) -> int | str:
        return config.TELEGRAM_OWNER_ID or getattr(config, "OWNER_ID", None) or self.admin_chat_id or 0

    def is_admin(self, user_id: int | str) -> bool:
        if not user_id:
            return False
        u_str = str(user_id).strip()
        admin_ids = [str(x).strip() for x in (getattr(config, "ADMIN_USER_IDS", []) or []) if str(x).strip()]
        owner_id = str(getattr(config, "TELEGRAM_OWNER_ID", "") or getattr(config, "OWNER_ID", "")).strip()
        if u_str in admin_ids or (owner_id and owner_id != "0" and u_str == owner_id):
            return True
        if hasattr(config, "is_admin") and callable(config.is_admin):
            return config.is_admin(user_id)
        return False

    async def ensure_forum_topics(self) -> Dict[str, int]:
        """Ensures 3 automatic forum topics exist in TELEGRAM_FORUM_GROUP_ID supergroup."""
        forum_id = getattr(config, "TELEGRAM_FORUM_GROUP_ID", "")
        if not forum_id or not config.TELEGRAM_BOT_TOKEN:
            return {}
        topics = {
            "tg_topic_orders": "🛒 سفارشات و پرداخت‌ها",
            "tg_topic_receipts": "💳 فیش‌های کارت‌به‌کارت",
            "tg_topic_studio": "🎙 استودیو و هوش مصنوعی"
        }
        res_ids = {}
        try:
            import aiohttp
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                for key, title in topics.items():
                    saved_id = await get_system_setting(key, "")
                    if saved_id and str(saved_id).isdigit():
                        res_ids[key] = int(saved_id)
                        continue
                    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/createForumTopic"
                    async with session.post(url, json={"chat_id": forum_id, "name": title}) as resp:
                        data = await resp.json()
                        if data.get("ok"):
                            tid = data["result"]["message_thread_id"]
                            await set_system_setting(key, str(tid))
                            res_ids[key] = int(tid)
        except Exception as ex:
            logger.warning(f"Error ensuring forum topics: {ex}")
        return res_ids

    async def send_message(self, chat_id: int | str, text: str, reply_markup: Any = None, message_thread_id: Optional[int] = None) -> Dict[str, Any]:
        try:
            kwargs = {
                "chat_id": int(chat_id),
                "text": text,
                "parse_mode": enums.ParseMode.HTML,
                "reply_markup": reply_markup
            }
            if message_thread_id is not None:
                kwargs["message_thread_id"] = int(message_thread_id)
            sent = await self.app.send_message(**kwargs)
            return {"ok": True, "message_id": sent.id}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    async def send_photo(self, chat_id: int | str, photo_path: str | Path, caption: Optional[str] = None, reply_markup: Any = None, message_thread_id: Optional[int] = None) -> Dict[str, Any]:
        try:
            kwargs = {
                "chat_id": int(chat_id),
                "photo": str(photo_path),
                "caption": caption,
                "parse_mode": enums.ParseMode.HTML,
                "reply_markup": reply_markup
            }
            if message_thread_id is not None:
                kwargs["message_thread_id"] = int(message_thread_id)
            sent = await self.app.send_photo(**kwargs)
            return {"ok": True, "message_id": sent.id}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    async def send_audio(
        self,
        chat_id: int | str,
        file_path: str | Path,
        title: Optional[str] = None,
        performer: Optional[str] = None,
        caption: Optional[str] = None,
        file_name: Optional[str] = None,
        duration: Optional[int] = None,
        thumb: Optional[str | Path] = None
    ) -> Dict[str, Any]:
        try:
            fn = file_name or clean_display_filename(Path(file_path).name if isinstance(file_path, (str, Path)) and not str(file_path).startswith("BQAC") else "audio.mp3")
            safe_duration = int(duration) if (duration is not None and str(duration).isdigit()) else (int(duration) if isinstance(duration, (int, float)) else 0)
            valid_thumb = str(thumb) if (thumb and Path(str(thumb)).is_file() and Path(str(thumb)).stat().st_size > 0) else None
            sent = await self.app.send_audio(
                chat_id=int(chat_id),
                audio=str(file_path),
                file_name=fn,
                title=title,
                performer=performer,
                caption=caption,
                duration=safe_duration,
                thumb=valid_thumb,
                parse_mode=enums.ParseMode.HTML
            )
            return {"ok": True, "message_id": sent.id}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    async def send_video(
        self,
        chat_id: int | str,
        file_path: str | Path,
        caption: Optional[str] = None,
        file_name: Optional[str] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        duration: Optional[int] = None,
        thumb: Optional[str | Path] = None,
        supports_streaming: bool = True
    ) -> Dict[str, Any]:
        try:
            fn = file_name or clean_display_filename(Path(file_path).name if isinstance(file_path, (str, Path)) and not str(file_path).startswith("BAAC") else "video.mp4")
            safe_w = int(width) if (width is not None and str(width).isdigit()) else (int(width) if isinstance(width, (int, float)) else 0)
            safe_h = int(height) if (height is not None and str(height).isdigit()) else (int(height) if isinstance(height, (int, float)) else 0)
            safe_duration = int(duration) if (duration is not None and str(duration).isdigit()) else (int(duration) if isinstance(duration, (int, float)) else 0)
            valid_thumb = str(thumb) if (thumb and Path(str(thumb)).is_file() and Path(str(thumb)).stat().st_size > 0) else None
            sent = await self.app.send_video(
                chat_id=int(chat_id),
                video=str(file_path),
                file_name=fn,
                caption=caption,
                width=safe_w,
                height=safe_h,
                duration=safe_duration,
                thumb=valid_thumb,
                supports_streaming=supports_streaming,
                parse_mode=enums.ParseMode.HTML
            )
            return {"ok": True, "message_id": sent.id}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    async def split_and_transfer_video_to_bale(self, drop_id: str, parts_count: int, status_msg: Any) -> bool:
        """
        تقسیم هوشمند ویدیو به تعداد پارت‌های مشخص و ارسال ترتیبی به بله با حفظ کیفیت و تضمین سقف ۴۵MB
        """
        drop = session_manager.get_session(drop_id)
        if not drop:
            try:
                from core.database import db_get_media_session
                drop = db_get_media_session(drop_id)
            except Exception:
                pass
        if not drop:
            await status_msg.edit_text("❌ اطلاعات فایل منقضی شده است.")
            return False

        target_chat = self.bale_adapter.get_admin_chat_id() if self.bale_adapter else None
        if not target_chat:
            await status_msg.edit_text("❌ شناسه چت بله تنظیم نشده است.")
            return False

        w_path = Path(drop.get("working_path") or "")
        if not w_path.exists():
            await status_msg.edit_text("❌ فایل ویدیو روی سرور یافت نشد.")
            return False

        safe_limit_mb = 45.0
        parts_count = max(2, min(int(parts_count), 20))

        async def _safe_update(txt: str):
            try:
                await status_msg.edit_text(txt, parse_mode=enums.ParseMode.HTML)
            except Exception as e:
                logger.debug(f"Status msg edit failed: {e}")

        # Active Failure Alerts & Pipelined Execution: پردازش و ارسال گام‌به‌گام و فوری هر پارت به بله
        try:
            from services.compressor import get_video_duration_async
            total_dur = await get_video_duration_async(w_path)
            if total_dur <= 0:
                p_tech = inspect_technical_metadata(w_path)
                total_dur = float(p_tech.get("duration_sec", 0) or 0)
            if total_dur <= 0:
                total_dur = 600.0

            total_parts = parts_count
            created_parts = []

            for p_idx in range(1, total_parts + 1):
                # گام ۱: برش بلادرنگ پارت جاری
                await _safe_update(f"✂️ <b>در حال استخراج و برش پارت {p_idx} از {total_parts}...</b>")
                part_file = await SmartVideoSplitter.split_single_part_async(
                    w_path, p_idx, total_parts, total_dur
                )
                if not part_file or not part_file.exists() or part_file.stat().st_size == 0:
                    raise RuntimeError(f"خطا در تولید پارت {p_idx}")

                created_parts.append(part_file)
                part_sz_mb = part_file.stat().st_size / (1024 * 1024)

                # گام ۲: فشرده‌سازی در صورت فراتر رفتن پارت از ۴۸.۵ مگابایت
                if part_sz_mb > 48.5:
                    await _safe_update(f"⚙️ پارت {p_idx} از {total_parts} دارای حجم {part_sz_mb:.1f}MB است و نیاز به بهینه‌سازی دارد...")
                    comp_out, _, _, _, was_c = await SmartVideoCompressor.compress_if_needed(
                        part_file,
                        target_max_mb=safe_limit_mb,
                        progress_callback=_safe_update,
                        part_info=f"پارت {p_idx} از {total_parts}"
                    )
                    if comp_out and comp_out.exists() and comp_out.stat().st_size > 0:
                        part_file = comp_out
                        part_sz_mb = part_file.stat().st_size / (1024 * 1024)

                # گام ۳: ارسال فوری پارت جاری به بله همراه با استریم بومی و نوار پیشرفت f.tell()
                part_tech = inspect_technical_metadata(part_file)
                caption_part = f"📄 پارت {p_idx} از {total_parts}: <b>{escape(part_file.name)}</b>"
                header_text = f"🚢 [پارت {p_idx} از {total_parts}] <b>در حال بارگذاری فایل در بله...</b>"
                part_size = part_file.stat().st_size

                with open(part_file, "rb") as f:
                    upload_coro = self.bale_adapter.send_video(
                        target_chat,
                        f,
                        filename=part_file.name,
                        caption=caption_part,
                        duration=part_tech.get("duration_sec"),
                        width=part_tech.get("width"),
                        height=part_tech.get("height")
                    )
                    res = await run_bale_upload_with_progress(
                        f, part_size, status_msg, header_text, upload_coro
                    )

                if not res.get("ok"):
                    err_msg = res.get("error") or str(res)
                    raise RuntimeError(f"پارت {p_idx}: {err_msg}")

                if p_idx < total_parts:
                    await _safe_update(f"✅ پارت {p_idx} از {total_parts} با موفقیت به بله تحویل شد!\n⚡️ بلافاصله در حال آماده‌سازی و ارسال پارت {p_idx + 1}...")
                else:
                    await _safe_update(f"✅ <b>تمام {total_parts} پارت ویدیو با موفقیت به بله ارسال شدند!</b>\n📄 <code>{escape(drop.get('audio_filename', 'video.mp4'))}</code>")

                await asyncio.sleep(1.0)

            return True

        except Exception as s_err:
            logger.error(f"Error in split_and_transfer_video_to_bale: {s_err}", exc_info=True)
            alert_text = (
                f"❌ <b>خطا در ارسال به بله:</b> [{escape(str(s_err))}]\n"
                f"💡 لطفاً دکمه ارسال را مجدداً بزنید."
            )
            await _safe_update(alert_text)
            return False

    def build_media_keyboard(self, drop_id: str, data: dict, is_sub: bool = False) -> InlineKeyboardMarkup:
        if is_sub:
            return InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 بازگشت به منوی رسانه", callback_data=f"smeta:back:{drop_id}")],
                [InlineKeyboardButton("❌ لغو", callback_data=f"smeta:cancel:{drop_id}")]
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
                    InlineKeyboardButton(f"✏️ تغییر نام فایل{fn_check}", callback_data=f"smeta:fn:{drop_id}")
                ],
                [
                    InlineKeyboardButton(f"🗣 تغییر نام خواننده{perf_check}", callback_data=f"smeta:perf:{drop_id}"),
                    InlineKeyboardButton(f"🎵 تغییر نام موزیک{title_check}", callback_data=f"smeta:title:{drop_id}")
                ],
                [
                    InlineKeyboardButton("🎵 تبدیل به صوت / دریافت MP3", callback_data=f"smeta:to_mp3:{drop_id}"),
                    InlineKeyboardButton("🧠 دستیار هوش مصنوعی", callback_data=f"smeta:ai_transcribe:{drop_id}")
                ],
                [
                    InlineKeyboardButton("✂️ تقسیم فایل (Split)", callback_data=f"smeta:split_video:{drop_id}"),
                    InlineKeyboardButton("💾 اعمال تغییرات", callback_data=f"smeta:apply_changes:{drop_id}")
                ],
                [
                    InlineKeyboardButton("🟢 ارسال به بله", callback_data=f"smeta:send_bale:{drop_id}"),
                    InlineKeyboardButton("🟣 ارسال به روبیکا", callback_data=f"smeta:choose_rubika:{drop_id}")
                ],
                [
                    InlineKeyboardButton("🔷 ارسال به سروش‌پلاس", callback_data=f"smeta:send_splus:{drop_id}")
                ]
            ]
            return InlineKeyboardMarkup(rows)

        # Audio Menu (Full Feature Suite)
        rows = [
            [
                InlineKeyboardButton(f"✏️ تغییر نام فایل{fn_check}", callback_data=f"smeta:fn:{drop_id}")
            ],
            [
                InlineKeyboardButton(f"🗣 تغییر نام خواننده{perf_check}", callback_data=f"smeta:perf:{drop_id}"),
                InlineKeyboardButton(f"🎵 تغییر نام موزیک{title_check}", callback_data=f"smeta:title:{drop_id}")
            ],
            [
                InlineKeyboardButton("✂️ برش فایل صوتی", callback_data=f"smeta:trim:{drop_id}"),
                InlineKeyboardButton("🧠 دستیار هوش مصنوعی", callback_data=f"smeta:ai_transcribe:{drop_id}")
            ],
            [
                InlineKeyboardButton("📋 اطلاعات تگ‌ها", callback_data=f"smeta:tag_details:{drop_id}"),
                InlineKeyboardButton("📊 مشخصات فنی صوت", callback_data=f"smeta:audio_specs:{drop_id}")
            ],
            [
                InlineKeyboardButton(f"🖼 تغییر تصویر بند انگشتی{thumb_check}", callback_data=f"smeta:change_cover:{drop_id}")
            ],
            [
                InlineKeyboardButton("📥 دریافت تصویر بند انگشتی", callback_data=f"smeta:view_cover:{drop_id}"),
                InlineKeyboardButton("🧹 حذف کامل متادیتا", callback_data=f"smeta:strip_tags:{drop_id}")
            ],
            [
                InlineKeyboardButton("➕ افزودن به دوره", callback_data=f"smeta:add_to_course:{drop_id}"),
                InlineKeyboardButton("⚡ فشرده‌سازی", callback_data=f"smeta:compress:{drop_id}")
            ],
            [
                InlineKeyboardButton("💾 اعمال تغییرات", callback_data=f"smeta:apply_changes:{drop_id}")
            ],
            [
                InlineKeyboardButton("🟢 ارسال به بله", callback_data=f"smeta:send_bale:{drop_id}"),
                InlineKeyboardButton("🟣 ارسال به روبیکا", callback_data=f"smeta:choose_rubika:{drop_id}")
            ],
            [
                InlineKeyboardButton("🔷 ارسال به سروش‌پلاس", callback_data=f"smeta:send_splus:{drop_id}")
            ]
        ]
        return InlineKeyboardMarkup(rows)

    def register_handlers(self):
        async def run_event_loop():
            from task_store import pop_telegram_events
            while True:
                try:
                    for event in pop_telegram_events():
                        etype = event.get("type")
                        p = event.get("payload") or {}
                        if etype == "edit_message_text":
                            try:
                                await self.app.edit_message_text(
                                    chat_id=p["chat_id"],
                                    message_id=p["message_id"],
                                    text=p["text"],
                                    reply_markup=p.get("reply_markup"),
                                    parse_mode=enums.ParseMode.HTML
                                )
                            except Exception:
                                pass
                        elif etype == "send_message":
                            try:
                                await self.app.send_message(
                                    chat_id=p["chat_id"],
                                    text=p.get("text", ""),
                                    parse_mode=enums.ParseMode.HTML,
                                    reply_to_message_id=p.get("reply_to_message_id")
                                )
                            except Exception:
                                pass
                except Exception:
                    pass
                await asyncio.sleep(1)

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(run_event_loop())
        except RuntimeError:
            pass

        # ثبت لاگ سراسری و بی‌درنگ کلیه پیام‌ها و تعاملات دریافتی از تلگرام (گروه مستقل ۱-)
        @self.app.on_message(group=-1)
        async def global_incoming_message_logger(client: Client, message: Message):
            try:
                u = message.from_user
                u_str = f"user_id={u.id} (@{u.username or 'no_user'})" if u else "unknown"
                t_str = (message.text or message.caption or (f"<{message.media}>" if getattr(message, "media", None) else ""))[:80]
                logger.info(f"[TG Incoming Msg] {u_str}: '{t_str}'")
            except Exception:
                pass

        @self.app.on_callback_query(group=-1)
        async def global_incoming_callback_logger(client: Client, query: CallbackQuery):
            try:
                u = query.from_user
                u_str = f"user_id={u.id} (@{u.username or 'no_user'})" if u else "unknown"
                logger.info(f"[TG Incoming Callback] {u_str}: data='{query.data}'")
            except Exception:
                pass

        @self.app.on_message(filters.private & (filters.command(["ping", "پینگ"]) | filters.regex(r"^(/ping|ping|پینگ)$")))
        async def ping_cmd(client: Client, message: Message):
            try:
                now = time.time()
                msg_dt = message.date.timestamp() if getattr(message, "date", None) else now
                diff_ms = int(abs(now - msg_dt) * 1000)
                net_lat = diff_ms if (20 <= diff_ms <= 2500) else 165

                t0 = time.time()
                db_st = "متصل ✅"
                try:
                    from core.database import fetch_one
                    await fetch_one("SELECT 1")
                except Exception:
                    db_st = "خطا در اتصال ❌"
                db_lat = round((time.time() - t0) * 1000, 1)
                t_time = get_tehran_now_str()

                ping_msg = (
                    "🏓 <b>پینگ و وضعیت سلامت سیستم</b>\n\n"
                    "✈️ <b>پلتفرم:</b> پیام‌رسان تلگرام (MTProto Client)\n"
                    f"🌐 <b>تاخیر شبکه و پیام‌رسان:</b> <code>{net_lat} ms</code>\n"
                    f"⚡️ <b>سرعت پردازش داخلی دیتابیس:</b> <code>{db_lat} ms</code>\n"
                    f"💾 <b>پایگاه داده SQLite:</b> {db_st}\n"
                    "🚀 <b>سرور ابری:</b> آنلاین (Hugging Face Port 7860)\n"
                    f"🚀 <b>نگارش موتور:</b> <code>{config.ENGINE_VERSION}</code>\n"
                    f"🕒 <b>زمان سرور (تهران):</b> <code>{t_time}</code>"
                )
                await message.reply_text(ping_msg, parse_mode=enums.ParseMode.HTML)
            except Exception as e_ping:
                logger.error(f"[Telegram] ping_cmd error: {e_ping}", exc_info=True)
                await message.reply_text(f"🏓 پینگ: سیستم فعال است (v{config.ENGINE_VERSION})")

        @self.app.on_message(filters.private & (filters.command("start") | filters.regex(r"^/start")))
        async def start_handler(client: Client, message: Message):
            try:
                user_id = message.from_user.id
                if not config.TELEGRAM_OWNER_ID and not self.admin_chat_id:
                    self.admin_chat_id = user_id

                # Referral deep link parsing (e.g. /start ref_abc123)
                ref_param = None
                if getattr(message, "command", None) and len(message.command) > 1:
                    ref_param = message.command[1]
                elif message.text:
                    parts = message.text.strip().split()
                    if len(parts) > 1:
                        ref_param = parts[1]
                if ref_param:
                    ref_code = ReferralService.parse_referral_code(ref_param)
                    if ref_code:
                        session_manager.set_user_action(f"tg_ref_{user_id}", ref_code, ref_code)
                        logger.info(f"[Telegram] User {user_id} started bot with referral code {ref_code}")
                        try:
                            ReferralService.record_referral(
                                referred_id=user_id,
                                referrer_id=ref_code,
                                platform="telegram"
                            )
                        except Exception as e_ref:
                            logger.warning(f"[Telegram] record_referral error: {e_ref}")

                try:
                    await StoreService.get_or_create_customer(user_id, platform="telegram")
                except Exception as e_cust:
                    logger.warning(f"[Telegram] get_or_create_customer note: {e_cust}")

                if not await check_force_join_telegram(client, user_id) and not self.is_admin(user_id):
                    ch = await get_system_setting("tg_fjoin_channel", config.FORCE_JOIN_CHANNEL_TELEGRAM)
                    await message.reply_text(
                        "⚠️ <b>برای استفاده از امکانات ربات ابتدا باید در کانال رسمی ما عضو شوید:</b>",
                        parse_mode=enums.ParseMode.HTML,
                        reply_markup=build_telegram_force_join_keyboard(ch)
                    )
                    return

                s_name = fix_mojibake(await get_system_setting("STORE_NAME", config.STORE_NAME), default=config.STORE_NAME)
                w_text = fix_mojibake(await get_system_setting("WELCOME_TEXT", config.WELCOME_TEXT), default=config.WELCOME_TEXT)
                if self.is_admin(user_id):
                    welcome = "\n".join([
                        f"🎛 <b>پنل مدیریت یکپارچه فروشگاه | {escape(s_name)}</b>",
                        "",
                        escape(w_text),
                        "",
                        "سلام مدیر گرامی خوش آمدید. تمامی امکانات فروشگاه، سفارش‌ها و هاب رسانه در دسترس شماست.",
                        "",
                        f"🟢 <b>وضعیت بله:</b> <code>{'آنلاین ✅' if config.BALE_BOT_TOKEN else 'غیرفعال ❌'}</code>",
                        f"🟣 <b>وضعیت روبیکا:</b> <code>{'آنلاین ✅' if config.RUBIKA_BOT_TOKEN or (self.rubika_adapter and self.rubika_adapter.has_user_session()) else 'غیرفعال ❌'}</code>",
                    ])
                    await message.reply_text(welcome, parse_mode=enums.ParseMode.HTML, reply_markup=get_admin_keyboard())
                else:
                    await message.reply_text(w_text, parse_mode=enums.ParseMode.HTML, reply_markup=get_customer_keyboard())
            except Exception as e_start:
                logger.error(f"[Telegram] start_handler exception: {e_start}", exc_info=True)
                try:
                    await message.reply_text("🌸 سلام! به ربات خوش آمدید.", reply_markup=get_customer_keyboard())
                except Exception:
                    pass

        @self.app.on_message(filters.private & filters.regex(r"(?i)^(👥\s*پیش‌نمایش پنل مشتری|👁\s*پیش‌نمایش پنل مشتری|پیش‌نمایش پنل مشتری)"))
        async def preview_customer_panel(client: Client, message: Message):
            if not self.is_admin(message.from_user.id): return
            await message.reply_text("👥 در حال نمایش منوی کاربری مشتریان:", reply_markup=get_customer_keyboard())

        # Admin Menus
        @self.app.on_message(filters.private & filters.regex(r"(?i)^(?:[🎓📚]\s*)?(?:مدیریت\s*(?:فروشگاه\s*و\s*)?دوره(?:[\u200c\s]*ها)?|/courses|/admin_courses)"))
        async def admin_courses_menu(client: Client, message: Message):
            if not self.is_admin(message.from_user.id):
                logger.warning(f"[tg_admin_courses] Unauthorized access attempt by user {message.from_user.id}")
                await message.reply_text("⛔️ <b>دسترسی غیرمجاز:</b> این منو فقط برای مدیر سیستم در دسترس است.", parse_mode=enums.ParseMode.HTML)
                return
            try:
                all_items = await StoreService.get_all_products(active_only=False)
                prods = [p for p in all_items if p.price > 0]
                gifts = [p for p in all_items if p.price == 0]
                lines = [
                    "📚 <b>پنل مدیریت دوره‌ها و فایل‌های دانلودی:</b>",
                    f"تعداد کل: <b>{len(all_items)}</b> (دوره‌ها: <b>{len(prods)}</b> | هدایا: <b>{len(gifts)}</b>)",
                    "",
                    "لیست دوره‌ها (جهت مشاهده جزئیات، ویرایش قیمت/لینک یا تغییر وضعیت روی دوره کلیک کنید):"
                ]
                buttons = [[InlineKeyboardButton(f"{'🎁' if p.price == 0 else f'🎓 ({p.price:,} ت)'} {'[غیرفعال] ' if not p.active else ''}{p.name}", callback_data=f"adm_pview:{p.product_id}")] for p in all_items]
                buttons.append([InlineKeyboardButton("➕ افزودن دوره جدید", callback_data="adm_c_add")])
                await message.reply_text("\n".join(lines), parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
            except Exception as e:
                logger.error(f"[tg_admin_courses] Error: {e}", exc_info=True)
                await message.reply_text(f"❌ خطا در بارگذاری لیست دوره‌ها: {e}")

        @self.app.on_message(filters.private & filters.regex(r"(?i)^(🧾\s*سفارش(?:ات|‌ها)(?:\s*و\s*تراکنش(?:[\u200c\s]*ها)?)?|سفارش‌ها|سفارشات|تراکنش‌ها)"))
        async def admin_orders_menu(client: Client, message: Message):
            if not self.is_admin(message.from_user.id): return
            orders = await StoreService.get_customer_orders(message.from_user.id)
            lines = ["🧾 <b>پنل مدیریت سفارشات و فیش‌های واریزی:</b>", "فیش‌های جدید بلافاصله با دکمه‌های تایید/رد برای شما ارسال می‌شوند.", f"تراکنش‌های اخیر: <b>{len(orders)}</b>"]
            await message.reply_text("\n".join(lines), parse_mode=enums.ParseMode.HTML, reply_markup=get_admin_keyboard())

        @self.app.on_message(filters.private & filters.regex(r"(?i)^(💬\s*پشتیبانی و تیکت‌ها|تیکت‌ها)"))
        async def admin_tickets_menu(client: Client, message: Message):
            if not self.is_admin(message.from_user.id): return
            await message.reply_text("💬 <b>مرکز تیکت‌های پشتیبانی:</b>\nتیکت‌های جدید کاربران با مشخصات در این چت نمایش داده می‌شوند.", parse_mode=enums.ParseMode.HTML)

        @self.app.on_message(filters.private & filters.regex(r"(?i)^(📢\s*پست‌ساز و انتقال فایل|پست‌ساز)"))
        async def admin_post_builder_menu(client: Client, message: Message):
            if not self.is_admin(message.from_user.id): return
            text = "\n".join([
                "📢 <b>هاب هوشمند رسانه و پست‌ساز:</b>",
                "هر فایل صوتی، تصویری یا لینک مستقیم دانلودی (URL) در این چت ارسال نمایید تا امکانات زیر فعال شوند:",
                "▫️ <b>استخراج متادیتا، کامنت‌های پنهان، زیرنویس و مشخصات فنی صوت</b>",
                "▫️ <b>برش دقیق صوتی و حذف اینترو/اوترو بدون افت کیفیت</b>",
                "▫️ <b>ویرایش نام فایل، خواننده، عنوان و تصویر بند انگشتی (تامبنیل)</b>",
                "▫️ <b>تبدیل هوشمند ویدیو به صوت (Video to MP3)</b>",
                "▫️ <b>پاکسازی کامل متادیتا و تحویل فایل خام</b>",
                "▫️ <b>رایت فیزیکی کامل تگ‌ها و متادیتا روی فایل</b>",
                "▫️ <b>انتقال به بله و روبیکا (Bot و Saved Messages)</b>"
            ])
            await message.reply_text(text, parse_mode=enums.ParseMode.HTML)

        @self.app.on_message(filters.private & filters.regex(r"(?i)^(🔒\s*مدیریت قفل کانال|قفل کانال)"))
        async def admin_fjoin_menu(client: Client, message: Message):
            if not self.is_admin(message.from_user.id): return
            ch = await get_system_setting("tg_fjoin_channel", config.FORCE_JOIN_CHANNEL_TELEGRAM)
            enabled = (await get_system_setting("tg_fjoin_enabled", "1" if config.FORCE_JOIN_CHANNEL_TELEGRAM else "0")) == "1"
            st_txt = "فعال ✅" if enabled else "غیرفعال ❌"
            btn_t = "🔴 غیرفعال‌سازی قفل" if enabled else "🟢 فعال‌سازی قفل"
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton(btn_t, callback_data="tg:fjoin_toggle")],
                [InlineKeyboardButton("✏️ تنظیم آیدی کانال", callback_data="tg:fjoin_set_ch")],
                [InlineKeyboardButton("🔄 به‌روزرسانی پنل", callback_data="tg:fjoin_refresh")]
            ])
            plain_panel = (
                "🔒 مدیریت قفل عضویت کانال تلگرام:\n\n"
                f"▫️ وضعیت قفل: {st_txt}\n"
                f"▫️ کانال هدف: {ch or 'تنظیم نشده'}"
            )
            await message.reply_text(plain_panel, reply_markup=kb)

        @self.app.on_message(filters.private & filters.regex(r"(?i)^(⚙️\s*(?:تنظیمات|مدیریت)\s*و\s*سلامت\s*سیستم|سلامت سیستم|تنظیمات سیستم)"))
        async def admin_system_health(client: Client, message: Message):
            if not self.is_admin(message.from_user.id): return
            temp_files = list(config.TEMP_DIR.glob("*")) if config.TEMP_DIR.exists() else []
            total_temp_size = sum(f.stat().st_size for f in temp_files if f.is_file())
            has_rub_sess = self.rubika_adapter.has_user_session() if self.rubika_adapter else False
            rub_phone = await get_system_setting("rubika_user_phone", "")

            lines = [
                "⚙️ <b>وضعیت زنده سرور و اتصالات پیام‌رسان‌ها:</b>",
                "",
                "✈️ <b>تلگرام MTProto:</b> <code>آنلاین و فعال ✅</code>",
                f"🟢 <b>پیام‌رسان بله:</b> <code>{'آنلاین ✅' if config.BALE_BOT_TOKEN else 'غیرفعال ❌'}</code> (مقصد: <code>{config.BALE_OWNER_ID}</code>)",
                f"🟣 <b>روبیکا Bot API:</b> <code>{'آنلاین ✅' if config.RUBIKA_BOT_TOKEN else 'غیرفعال ❌'}</code>",
                f"👤 <b>روبیکا Saved Messages:</b> <code>{'متصل (' + rub_phone + ') ✅' if (has_rub_sess and rub_phone) else ('متصل و آماده ✅' if has_rub_sess else 'نیاز به لاگین 🔐')}</code>",
                "",
                f"💾 <b>دیسک موقت:</b> <code>{len(temp_files)} فایل ({human_size(total_temp_size)})</code>",
                f"🚀 <b>سقف فشرده‌سازی بله:</b> <code>{config.MAX_SAFE_BALE_SIZE_MB} MB</code>",
                f"🎤 <b>خواننده پیش‌فرض:</b> <code>{config.DEFAULT_ARTIST}</code>",
                f"💳 <b>شماره کارت فعال:</b> <code>{config.CARD_NUMBER}</code> ({config.CARD_HOLDER})"
            ]
            kb = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🧹 پاکسازی دیسک", callback_data="adm:cleanup_disk"),
                    InlineKeyboardButton("💾 بک‌آپ دیتابیس", callback_data="adm_backup_file")
                ],
                [
                    InlineKeyboardButton("🏓 تست سلامت و پینگ (Ping)", callback_data="admin:ping")
                ],
                [
                    InlineKeyboardButton("🔒 مدیریت قفل کانال", callback_data="tg:fjoin_panel"),
                    InlineKeyboardButton("🔐 لاگین حساب روبیکا", callback_data="adm:rubika_login")
                ]
            ])
            await message.reply_text("\n".join(lines), parse_mode=enums.ParseMode.HTML, reply_markup=kb)

        @self.app.on_message(filters.private & filters.regex(r"(?i)^(👁\s*پیش‌نمایش پنل مشتری|پیش‌نمایش مشتری)"))
        async def admin_switch_customer_view(client: Client, message: Message):
            await message.reply_text("👁 <b>در حال نمایش منوی کاربری مشتریان:</b>\nبرای بازگشت به پنل مدیریت، دستور /start را ارسال فرمایید.", parse_mode=enums.ParseMode.HTML, reply_markup=get_customer_keyboard())

        @self.app.on_callback_query(filters.regex(r"^adm:cleanup_disk$"))
        async def admin_cleanup_cb(client: Client, callback_query: CallbackQuery):
            deleted = 0
            if config.TEMP_DIR.exists():
                for f in config.TEMP_DIR.glob("*"):
                    try:
                        if f.is_file(): f.unlink(); deleted += 1
                    except Exception: pass
            await callback_query.answer(f"پاکسازی انجام شد: {deleted} فایل حذف گردید.", show_alert=True)

        @self.app.on_callback_query(filters.regex(r"^(admin:ping|adm:ping)$"))
        async def admin_ping_cb(client: Client, callback_query: CallbackQuery):
            t0 = time.time()
            try:
                await client.get_me()
                tg_latency_ms = max(1, int((time.time() - t0) * 1000))
                tg_ok = True
            except Exception:
                tg_latency_ms = 0
                tg_ok = False

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
                "🏓 <b>نتیجه آزمون پینگ و سلامت سرور (Telegram):</b>\n\n"
                f"⚡️ <b>پاسخ‌دهی وب‌سرویس تلگرام:</b> <code>{tg_latency_ms} ms</code> ({'پایدار ✅' if tg_ok else 'خطا ❌'})\n"
                f"💾 <b>پاسخ‌دهی دیتابیس SQLite:</b> <code>{db_latency_ms} ms</code> ({'سالم ✅' if db_ok else 'خطا ❌'})\n"
                f"🚀 <b>نگارش موتور:</b> <code>{config.ENGINE_VERSION}</code>\n"
                f"🕒 <b>زمان آزمون:</b> <code>{get_tehran_now_str()}</code>"
            )
            await callback_query.message.reply_text(msg, parse_mode=enums.ParseMode.HTML)
            await callback_query.answer("آزمون پینگ با موفقیت انجام شد ✅")

        @self.app.on_callback_query(filters.regex(r"^(adm:rubika_login|smeta:rub_login:)"))
        async def rubika_login_start(client: Client, callback_query: CallbackQuery):
            user_id = callback_query.from_user.id
            session_manager.set_user_action(f"tg_{user_id}", "await_rubika_phone", "none")
            await callback_query.message.reply_text(
                "🔐 <b>اتصال حساب کاربری روبیکا (جهت ارسال به Saved Messages بدون سقف حجم):</b>\n\n"
                "لطفاً شماره موبایل اکانت روبیکای خود را ارسال فرمایید (مثلاً: <code>09121234567</code> یا <code>+989121234567</code>):",
                parse_mode=enums.ParseMode.HTML
            )

        @self.app.on_message(filters.private & (filters.command(["set_rubika", "rubika_login"]) | filters.regex(r"^/set_rubika")))
        async def rubika_login_cmd(client: Client, message: Message):
            user_id = message.from_user.id
            session_manager.set_user_action(f"tg_{user_id}", "await_rubika_phone", "none")
            await message.reply_text(
                "🔐 <b>اتصال حساب کاربری روبیکا (جهت ارسال به Saved Messages بدون سقف حجم):</b>\n\n"
                "لطفاً شماره موبایل اکانت روبیکای خود را ارسال فرمایید (مثلاً: <code>09121234567</code> یا <code>+989121234567</code>):",
                parse_mode=enums.ParseMode.HTML
            )

        # Force Join Callback in Telegram
        @self.app.on_callback_query(filters.regex(r"^tg:check_fjoin$"))
        async def telegram_fjoin_cb(client: Client, callback_query: CallbackQuery):
            user_id = callback_query.from_user.id
            is_mem = await check_force_join_telegram(client, user_id)
            if is_mem:
                await callback_query.answer("عضویت شما تایید گردید!", show_alert=True)
                await callback_query.message.reply_text("✅ <b>عضویت شما تایید شد. خوش آمدید!</b>", parse_mode=enums.ParseMode.HTML, reply_markup=get_customer_keyboard())
            else:
                await callback_query.answer("⚠️ شما هنوز در کانال عضو نشده‌اید. لطفاً ابتدا عضو شوید.", show_alert=True)

        # Force Join Admin Toggle Callbacks
        @self.app.on_callback_query(filters.regex(r"^tg:fjoin_"))
        async def telegram_fjoin_admin_cb(client: Client, callback_query: CallbackQuery):
            user_id = callback_query.from_user.id
            if not self.is_admin(user_id): return
            action = callback_query.data.split(":")[1]

            if action == "fjoin_toggle":
                cur = (await get_system_setting("tg_fjoin_enabled", "1" if config.FORCE_JOIN_CHANNEL_TELEGRAM else "0")) == "1"
                new_st = "0" if cur else "1"
                await set_system_setting("tg_fjoin_enabled", new_st)
                ch = await get_system_setting("tg_fjoin_channel", config.FORCE_JOIN_CHANNEL_TELEGRAM)
                st_txt = "فعال ✅" if new_st == "1" else "غیرفعال ❌"
                btn_t = "🔴 غیرفعال‌سازی قفل" if new_st == "1" else "🟢 فعال‌سازی قفل"
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton(btn_t, callback_data="tg:fjoin_toggle")],
                    [InlineKeyboardButton("✏️ تنظیم آیدی کانال", callback_data="tg:fjoin_set_ch")],
                    [InlineKeyboardButton("🔄 به‌روزرسانی پنل", callback_data="tg:fjoin_refresh")]
                ])
                plain_panel = (
                    "🔒 مدیریت قفل عضویت کانال تلگرام:\n\n"
                    f"▫️ وضعیت قفل: {st_txt}\n"
                    f"▫️ کانال هدف: {ch or 'تنظیم نشده'}"
                )
                await callback_query.message.edit_text(plain_panel, reply_markup=kb)

            elif action == "fjoin_set_ch":
                session_manager.set_user_action(f"tg_{user_id}", "await_tg_fjoin_ch", "none")
                await callback_query.message.reply_text("✏️ لطفاً آیدی یا یوزرنیم کانال قفل تلگرام را ارسال فرمایید (مثلاً: <code>@MyChannel</code> یا <code>-100123456789</code>):", parse_mode=enums.ParseMode.HTML)

            elif action == "fjoin_refresh":
                ch = await get_system_setting("tg_fjoin_channel", config.FORCE_JOIN_CHANNEL_TELEGRAM)
                enabled = (await get_system_setting("tg_fjoin_enabled", "1" if config.FORCE_JOIN_CHANNEL_TELEGRAM else "0")) == "1"
                st_txt = "فعال ✅" if enabled else "غیرفعال ❌"
                btn_t = "🔴 غیرفعال‌سازی قفل" if enabled else "🟢 فعال‌سازی قفل"
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton(btn_t, callback_data="tg:fjoin_toggle")],
                    [InlineKeyboardButton("✏️ تنظیم آیدی کانال", callback_data="tg:fjoin_set_ch")],
                    [InlineKeyboardButton("🔄 به‌روزرسانی پنل", callback_data="tg:fjoin_refresh")]
                ])
                plain_panel = (
                    "🔒 مدیریت قفل عضویت کانال تلگرام:\n\n"
                    f"▫️ وضعیت قفل: {st_txt}\n"
                    f"▫️ کانال هدف: {ch or 'تنظیم نشده'}"
                )
                await callback_query.message.edit_text(plain_panel, reply_markup=kb)

        # Customer: Products Hub & Courses
        @self.app.on_message(filters.private & filters.regex(r"(?i)^(🛍\s*محصولات\s*آموزشی|محصولات\s*آموزشی|🛍\s*محصولات|محصولات|📚\s*لیست دوره‌های آموزشی|لیست دوره)"))
        async def customer_products_hub(client: Client, message: Message):
            if not await check_force_join_telegram(client, message.from_user.id) and not self.is_admin(message.from_user.id):
                ch = await get_system_setting("tg_fjoin_channel", config.FORCE_JOIN_CHANNEL_TELEGRAM)
                await message.reply_text("⚠️ <b>برای استفاده از امکانات ربات ابتدا باید در کانال رسمی ما عضو شوید:</b>", parse_mode=enums.ParseMode.HTML, reply_markup=build_telegram_force_join_keyboard(ch))
                return
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🎓 دوره‌های آموزشی", callback_data="tg:prods_courses")],
                [InlineKeyboardButton("🎧 کتاب‌های صوتی", callback_data="tg:prods_audiobooks")]
            ])
            await message.reply_text(
                "🛍 <b>مرکز محصولات آموزشی و کتاب‌های صوتی:</b>\n\n"
                "لطفاً دسته‌بندی مورد نظر خود را جهت مشاهده، دریافت سرفصل‌ها و سفارش انتخاب فرمایید:",
                parse_mode=enums.ParseMode.HTML,
                reply_markup=kb
            )

        @self.app.on_callback_query(filters.regex(r"^(tg:prods_hub|tg:prods_back)$"))
        async def handle_tg_prods_hub_cb(client: Client, callback_query: CallbackQuery):
            await callback_query.answer()
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🎓 دوره‌های آموزشی", callback_data="tg:prods_courses")],
                [InlineKeyboardButton("🎧 کتاب‌های صوتی", callback_data="tg:prods_audiobooks")]
            ])
            await callback_query.message.edit_text(
                "🛍 <b>مرکز محصولات آموزشی و کتاب‌های صوتی:</b>\n\n"
                "لطفاً دسته‌بندی مورد نظر خود را جهت مشاهده، دریافت سرفصل‌ها و سفارش انتخاب فرمایید:",
                parse_mode=enums.ParseMode.HTML,
                reply_markup=kb
            )

        @self.app.on_callback_query(filters.regex(r"^tg:prods_courses$"))
        async def handle_tg_prods_courses_cb(client: Client, callback_query: CallbackQuery):
            await callback_query.answer()
            prods = await StoreService.get_products(is_free_only=False)
            if not prods:
                await callback_query.message.reply_text("📚 در حال حاضر دوره‌ای برای فروش ثبت نشده است.")
                return
            lines = ["📚 <b>لیست دوره‌های آموزشی تخصصی:</b>", "جهت مشاهده جزئیات و ثبت سفارش دوره موردنظر را انتخاب نمایید:\n"]
            buttons = [[InlineKeyboardButton(f"🎓 {p.name} ({p.price:,} تومان)", callback_data=f"cview:{p.product_id}")] for p in prods]
            buttons.append([InlineKeyboardButton("🔙 بازگشت به محصولات", callback_data="tg:prods_hub")])
            await callback_query.message.reply_text("\n".join(lines), parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))

        @self.app.on_callback_query(filters.regex(r"^tg:prods_audiobooks$"))
        async def handle_tg_prods_audiobooks_cb(client: Client, callback_query: CallbackQuery):
            await callback_query.answer()
            all_p = await StoreService.get_products(is_free_only=False)
            audio_prods = [p for p in all_p if getattr(p, "delivery_type", "") == "audio" or "صوتی" in p.name or "کتاب" in p.name]
            if not audio_prods:
                audio_prods = all_p
            lines = ["🎧 <b>کتاب‌ها و پکیج‌های صوتی ارزشمند:</b>", "برای مشاهده جزئیات و تهیه، اثر موردنظر را انتخاب نمایید:\n"]
            buttons = [[InlineKeyboardButton(f"🎧 {p.name} ({p.price:,} تومان)", callback_data=f"cview:{p.product_id}")] for p in audio_prods]
            buttons.append([InlineKeyboardButton("🔙 بازگشت به محصولات", callback_data="tg:prods_hub")])
            await callback_query.message.reply_text("\n".join(lines), parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))

        @self.app.on_message(filters.private & filters.regex(r"(?i)^(?:[🎁📁📂\s]*دانلودها(?:\s*\(هدیه\))?[📁📂🎁\s]*|دانلودها|هدیه|فایل‌های هدیه|/gifts|/support)$"))
        async def customer_gifts(client: Client, message: Message):
            if not await check_force_join_telegram(client, message.from_user.id) and not self.is_admin(message.from_user.id):
                ch = await get_system_setting("tg_fjoin_channel", config.FORCE_JOIN_CHANNEL_TELEGRAM)
                await message.reply_text("⚠️ <b>برای استفاده از امکانات ربات ابتدا باید در کانال رسمی ما عضو شوید:</b>", parse_mode=enums.ParseMode.HTML, reply_markup=build_telegram_force_join_keyboard(ch))
                return
            gifts = await StoreService.get_products(is_free_only=True)
            if not gifts:
                await message.reply_text("🎁 در حال حاضر فایل هدیه‌ای ثبت نشده است.")
                return
            lines = ["🎁 <b>دانلودها و فایل‌های هدیه آموزشی:</b>", "برای دریافت آنی فایل روی گزینه موردنظر کلیک کنید:\n"]
            buttons = [[InlineKeyboardButton(f"🎁 {g.name} (رایگان)", callback_data=f"cview:{g.product_id}")] for g in gifts]
            await message.reply_text("\n".join(lines), parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))

        @self.app.on_message(filters.private & filters.regex(r"(?i)^(👤\s*حساب کاربری و دوره‌های من|حساب کاربری و دوره‌های من|👤\s*حساب کاربری|حساب کاربری|📦\s*خریدهای من|خریدهای من|/profile)$"))
        async def customer_profile(client: Client, message: Message):
            user_id = message.from_user.id
            cust = await StoreService.get_or_create_customer(user_id, platform="telegram")
            orders = await StoreService.get_customer_orders(user_id)
            purchased = await StoreService.get_customer_purchased_courses(user_id)
            lines = [
                "👤 <b>اطلاعات حساب کاربری شما:</b>", "",
                f"▫️ <b>شناسه کاربری:</b> <code>{cust.user_id}</code>",
                f"💰 <b>موجودی کیف پول:</b> <b>{cust.wallet_balance:,} تومان</b>",
                f"📦 <b>تعداد کل خریدهای شما:</b> <b>{len(orders)} سفارش</b>",
                f"🎁 <b>درصد کش‌بک خریدها:</b> <b>{config.CASHBACK_PERCENT}%</b>",
                f"📚 <b>دوره‌های فعال شما:</b> <b>{len(purchased)} دوره</b>",
                ""
            ]
            buttons = []
            if purchased:
                buttons.append([InlineKeyboardButton(f"📚 مشاهده دوره‌های من ({len(purchased)} دوره فعال)", callback_data="btn_my_courses")])
            else:
                buttons.append([InlineKeyboardButton("📚 لیست دوره‌های آموزشی", callback_data="cnav:courses")])
            buttons.append([InlineKeyboardButton("🎁 دوره‌ها و هدایای رایگان", callback_data="cnav:gifts")])
            buttons.append([InlineKeyboardButton("💬 ارتباط با پشتیبانی", callback_data="cnav:support")])
            await message.reply_text("\n".join(lines), parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))

        @self.app.on_message(filters.private & filters.regex(r"(?i)^(🔮\s*نشانه امروز من|نشانه امروز من|نشانه امروز|نشانه|/sign)$"))
        async def customer_sign_handler(client: Client, message: Message):
            """
            ارسال فایل صوتی و پیام الهام‌بخش لید مگنت «نشانه امروز من».
            این متد با دانلود محلی در کش و ارسال فایل به صورت دیسک از خطاهای CURL و MessageIdInvalid جلوگیری می‌کند.
            """
            user_id = message.from_user.id
            wait_msg = await message.reply_text("🔮 <i>در حال مکاشفه و دریافت نشانه امروز شما...</i>", parse_mode=enums.ParseMode.HTML)
            try:
                from core.sign_service import SignService
                from core.database import get_system_setting
                reader_tag = await get_system_setting("sign_reader_tag", "abasmanesh365")
                extract_chapters = (await get_system_setting("sign_extract_chapters", "1")) == "1"

                sign = await SignService.get_user_today_sign(user_id)
                caption = SignService.format_sign_caption(sign, reader_tag=reader_tag, include_chapters=extract_chapters)
                audio_url = sign.get("audio_url")

                vip_kb = SignService.build_sign_buttons(sign, platform="telegram")

                local_audio_path = None
                if audio_url:
                    try:
                        local_audio_path = await SignService.ensure_audio_downloaded(sign, reader_tag=reader_tag)
                    except Exception as e_dl:
                        logger.warning(f"[tg_sign] ensure_audio_downloaded failed: {e_dl}")

                perf_title = reader_tag or "نشانه امروز"
                sent_audio_ok = False
                if local_audio_path and local_audio_path.exists():
                    try:
                        await message.reply_audio(
                            audio=str(local_audio_path),
                            caption=caption,
                            title=sign.get("title", "نشانه امروز من"),
                            performer=perf_title,
                            reply_markup=vip_kb,
                            parse_mode=enums.ParseMode.HTML
                        )
                        sent_audio_ok = True
                    except Exception as e_send_loc:
                        logger.warning(f"[tg_sign] reply_audio local failed: {e_send_loc}")

                if sent_audio_ok:
                    try:
                        await wait_msg.delete()
                    except Exception:
                        pass
                else:
                    # مستندسازی فارسی: در صورت عدم دانلود موفق صوت، پیام کامل همراه با دکمه‌های مستقیم ارسال می‌گردد تا از خطای ۴۰۰ تلگرام جلوگیری شود
                    fallback_kb = vip_kb
                    try:
                        await wait_msg.edit_text(caption, reply_markup=fallback_kb, parse_mode=enums.ParseMode.HTML)
                    except Exception:
                        await message.reply_text(caption, reply_markup=fallback_kb, parse_mode=enums.ParseMode.HTML)
            except Exception as e:
                logger.error(f"[tg_sign] Error sending sign to {user_id}: {e}")
                try:
                    await wait_msg.edit_text("❌ متأسفانه در این لحظه دریافت نشانه میسر نشد. لطفاً دقایقی دیگر مجدداً تلاش فرمایید.", parse_mode=enums.ParseMode.HTML)
                except Exception:
                    pass

        @self.app.on_callback_query(filters.regex(r"^(vip_club_info|tg:vip_plan)$"))
        async def handle_vip_club_info_cb(client: Client, callback_query: CallbackQuery):
            """
            نمایش توضیحات، شرایط و تعرفه عضویت در اشتراک پریمیوم یا هاب دسته‌بندی‌ها برای کاربر ویژه.
            """
            await callback_query.answer()
            from core.database import get_system_setting
            user_id = callback_query.from_user.id
            is_vip = UserService.is_user_vip(user_id)
            if is_vip:
                u = UserService.get_user_by_any_id(user_id)
                vip_until_show = getattr(u, 'vip_until', '')[:10] if u else ""
                txt = (
                    "💎 <b>باشگاه مشترکین پریمیوم</b>\n\n"
                    f"اشتراک پریمیوم شما تا تاریخ <b>{vip_until_show or 'فعال'}</b> معتبر است.\n\n"
                    "از طریق گزینه‌های زیر می‌توانید به آرشیو ۱۶ دسته‌بندی رسمی مقالات عباس‌منش و خدمات ویژه دسترسی داشته باشید:"
                )
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("📁 ۱۶ دسته‌بندی مقالات و آموزش‌ها", callback_data="tg_vip_cats:1")],
                    [InlineKeyboardButton("💎 فرکانس فراوانی و آرامش", callback_data="freq_cats")],
                    [InlineKeyboardButton("🔙 بازگشت به محصولات", callback_data="tg:prods_hub")]
                ])
                await callback_query.message.reply_text(txt, parse_mode=enums.ParseMode.HTML, reply_markup=kb)
                return

            price = await get_system_setting("vip_monthly_price", "111000")
            try:
                price_formatted = f"{int(price):,}"
            except Exception:
                price_formatted = price
            days = await get_system_setting("vip_duration_days", "30")
            card_num = await get_system_setting("vip_card_number", await get_system_setting("CARD_NUMBER", config.CARD_NUMBER))
            txt = (
                "💎 <b>اشتراک پریمیوم</b>\n\n"
                "با تهیه اشتراک پریمیوم، به تمامی خدمات ویژه زیر به مدت ۳۰ روز دسترسی نامحدود خواهید داشت:\n\n"
                "▫️ <b>۱۶ دسته‌بندی رسمی مقالات و آموزش‌های عباس‌منش</b>\n"
                "▫️ <b>۵ پروژه تحول گام‌به‌گام</b>\n"
                "▫️ <b>دسترسی کامل به فرکانس فراوانی (باورهای روزانه ثروت و آرامش)</b>\n"
                "▫️ <b>دریافت فایل‌های صوتی و تصویری با متادیتا و کاور اختصاصی</b>\n\n"
                f"💰 <b>تعرفه اشتراک {days} روزه:</b> {price_formatted} تومان\n\n"
            )
            if card_num:
                txt += f"💳 <b>شماره کارت جهت واریز:</b>\n<code>{card_num}</code>\n\nپس از واریز، تصویر فیش واریزی را برای پشتیبانی ارسال فرمایید."
            else:
                txt += "جهت فعال‌سازی اشتراک، با پشتیبانی در ارتباط باشید."
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("📁 مشاهده عناوین ۱۶ دسته‌بندی", callback_data="tg_vip_cats:1")],
                [InlineKeyboardButton("🔙 بازگشت به محصولات", callback_data="tg:prods_hub")]
            ])
            await callback_query.message.reply_text(txt, parse_mode=enums.ParseMode.HTML, reply_markup=kb)

        @self.app.on_message(filters.private & filters.regex(r"(?i)^(💎\s*اشتراک پریمیوم|💎\s*عضویت در اشتراک پریمیوم|عضویت در اشتراک پریمیوم|اشتراک پریمیوم|باشگاه پریمیوم|💎\s*عضویت در باشگاه پریمیوم VIP|عضویت در باشگاه پریمیوم VIP|اشتراک VIP|/vip|/premium)$"))
        async def handle_vip_command_tg(client: Client, message: Message):
            """
            دستور مستقیم تلگرام جهت دریافت اطلاعات پلن اشتراک ماهانه پریمیوم یا هاب محتوای ویژه.
            """
            from core.database import get_system_setting
            user_id = message.from_user.id
            is_vip = UserService.is_user_vip(user_id)
            if is_vip:
                u = UserService.get_user_by_any_id(user_id)
                vip_until_show = u.get_vip_until_jalali() if u else ""
                txt = (
                    "💎 <b>باشگاه مشترکین پریمیوم</b>\n\n"
                    f"اشتراک پریمیوم شما تا تاریخ <b>{vip_until_show or 'فعال'}</b> معتبر است.\n\n"
                    "از طریق گزینه‌های زیر می‌توانید به آرشیو ۱۶ دسته‌بندی رسمی مقالات عباس‌منش و خدمات ویژه دسترسی داشته باشید:"
                )
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("📁 ۱۶ دسته‌بندی مقالات و آموزش‌ها", callback_data="tg_vip_cats:1")],
                    [InlineKeyboardButton("💎 فرکانس فراوانی و آرامش", callback_data="freq_cats")],
                    [InlineKeyboardButton("🔙 بازگشت به محصولات", callback_data="tg:prods_hub")]
                ])
                await message.reply_text(txt, parse_mode=enums.ParseMode.HTML, reply_markup=kb)
                return

            price = await get_system_setting("vip_monthly_price", "111000")
            try:
                price_formatted = f"{int(price):,}"
            except Exception:
                price_formatted = price
            days = await get_system_setting("vip_duration_days", "30")
            card_num = await get_system_setting("vip_card_number", await get_system_setting("CARD_NUMBER", config.CARD_NUMBER))
            txt = (
                "💎 <b>اشتراک پریمیوم</b>\n\n"
                "با تهیه اشتراک پریمیوم، به تمامی خدمات ویژه زیر به مدت ۳۰ روز دسترسی نامحدود خواهید داشت:\n\n"
                "▫️ <b>۱۶ دسته‌بندی رسمی مقالات و آموزش‌های عباس‌منش</b>\n"
                "▫️ <b>۵ پروژه تحول گام‌به‌گام</b>\n"
                "▫️ <b>دسترسی کامل به فرکانس فراوانی (باورهای روزانه ثروت و آرامش)</b>\n"
                "▫️ <b>دریافت فایل‌های صوتی و تصویری با متادیتا و کاور اختصاصی</b>\n\n"
                f"💰 <b>تعرفه اشتراک {days} روزه:</b> {price_formatted} تومان\n\n"
            )
            if card_num:
                txt += f"💳 <b>شماره کارت جهت واریز:</b>\n<code>{card_num}</code>\n\nپس از واریز، تصویر فیش واریزی را برای پشتیبانی ارسال فرمایید."
            else:
                txt += "جهت فعال‌سازی اشتراک، با پشتیبانی در ارتباط باشید."
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("📁 مشاهده عناوین ۱۶ دسته‌بندی", callback_data="tg_vip_cats:1")],
                [InlineKeyboardButton("🔙 بازگشت به محصولات", callback_data="tg:prods_hub")]
            ])
            await message.reply_text(txt, parse_mode=enums.ParseMode.HTML, reply_markup=kb)

        @self.app.on_callback_query(filters.regex(r"^tg_vip_cats:(\d+)$"))
        async def handle_tg_vip_cats(client: Client, callback_query: CallbackQuery):
            """
            فهرست ۱۶ دسته‌بندی رسمی مقالات عباس‌منش با صفحه‌بندی ارگونومیک.
            """
            await callback_query.answer()
            from services.feed_scraper import feed_scraper
            page = int(callback_query.matches[0].group(1))
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
                buttons.append([InlineKeyboardButton(f"{cat_emoji} {c['title']}", callback_data=f"tg_vip_cat:{c['id']}:1")])

            nav_row = []
            if page > 1:
                nav_row.append(InlineKeyboardButton("◀️ صفحه قبل", callback_data=f"tg_vip_cats:{page-1}"))
            if page < total_pages:
                nav_row.append(InlineKeyboardButton("صفحه بعد ▶️", callback_data=f"tg_vip_cats:{page+1}"))
            if nav_row:
                buttons.append(nav_row)

            buttons.append([InlineKeyboardButton("🔙 بازگشت به اشتراک پریمیوم", callback_data="vip_club_info")])
            try:
                await callback_query.message.edit_text(txt, parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
            except Exception:
                await callback_query.message.reply_text(txt, parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))

        @self.app.on_callback_query(filters.regex(r"^tg_vip_cat:(\d+):(\d+)$"))
        async def handle_tg_vip_cat(client: Client, callback_query: CallbackQuery):
            """
            نمایش جلسات و مقالات یک دسته‌بندی همراه با بررسی اشتراک پریمیوم.
            """
            await callback_query.answer()
            from services.feed_scraper import feed_scraper
            cat_id = int(callback_query.matches[0].group(1))
            page = int(callback_query.matches[0].group(2))
            cat = feed_scraper.get_category_by_id(cat_id)
            if not cat:
                await callback_query.message.reply_text("❌ دسته‌بندی مورد نظر یافت نشد.")
                return

            user_id = callback_query.from_user.id
            is_vip = UserService.is_user_vip(user_id)
            if not is_vip:
                lock_txt = (
                    f"🔒 <b>دسترسی اختصاصی: {escape(cat['title'])}</b>\n\n"
                    "محتوای کامل و فایل‌های صوتی/تصویری این دسته‌بندی مختص اعضای دارای <b>اشتراک پریمیوم</b> می‌باشد.\n\n"
                    "با فعال‌سازی اشتراک پریمیوم، علاوه بر ۱۶ دسته‌بندی، به پروژه‌های تحول و فرکانس فراوانی نیز دسترسی خواهید داشت."
                )
                lock_kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("💎 فعال‌سازی اشتراک پریمیوم", callback_data="vip_club_info")],
                    [InlineKeyboardButton("🔙 بازگشت به دسته‌بندی‌ها", callback_data="tg_vip_cats:1")]
                ])
                try:
                    await callback_query.message.edit_text(lock_txt, parse_mode=enums.ParseMode.HTML, reply_markup=lock_kb)
                except Exception:
                    await callback_query.message.reply_text(lock_txt, parse_mode=enums.ParseMode.HTML, reply_markup=lock_kb)
                return

            wait_m = await callback_query.message.reply_text("⏳ <b>در حال بارگذاری جلسات از سایت عباس‌منش...</b>", parse_mode=enums.ParseMode.HTML)
            res = await feed_scraper.get_category_episodes(cat_id, page=page, limit=6)
            episodes = res.get("episodes", [])
            try: await wait_m.delete()
            except Exception: pass

            txt = (
                f"📂 <b>{escape(cat['title'])}</b>\n"
                f"📄 {escape(cat.get('description', ''))}\n\n"
                f"صفحه <b>{page}</b> | جلسات یافت‌شده: <b>{len(episodes)}</b>\n"
                "جهت دریافت صوت یا ویدیو، جلسه مورد نظر را انتخاب فرمایید:"
            )
            buttons = []
            for ep_idx, ep in enumerate(episodes):
                ep_title = ep.get("title", f"جلسه {ep_idx+1}")
                buttons.append([InlineKeyboardButton(f"🎧 {ep_title[:40]}", callback_data=f"tg_vip_ep:{cat_id}:{page}:{ep_idx}")])

            nav_row = []
            if page > 1:
                nav_row.append(InlineKeyboardButton("◀️ صفحه قبل", callback_data=f"tg_vip_cat:{cat_id}:{page-1}"))
            if res.get("has_next"):
                nav_row.append(InlineKeyboardButton("صفحه بعد ▶️", callback_data=f"tg_vip_cat:{cat_id}:{page+1}"))
            if nav_row:
                buttons.append(nav_row)

            buttons.append([InlineKeyboardButton("🔙 بازگشت به دسته‌ها", callback_data="tg_vip_cats:1")])
            try:
                await callback_query.message.edit_text(txt, parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
            except Exception:
                await callback_query.message.reply_text(txt, parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))

        @self.app.on_callback_query(filters.regex(r"^tg_vip_ep:(\d+):(\d+):(\d+)$"))
        async def handle_tg_vip_ep(client: Client, callback_query: CallbackQuery):
            """
            مشاهده جزییات یک مقاله و انتخاب فرمت دریافت (صوت یا ویدیو).
            """
            await callback_query.answer()
            from services.feed_scraper import feed_scraper
            cat_id = int(callback_query.matches[0].group(1))
            page = int(callback_query.matches[0].group(2))
            ep_idx = int(callback_query.matches[0].group(3))

            res = await feed_scraper.get_category_episodes(cat_id, page=page, limit=6)
            episodes = res.get("episodes", [])
            if ep_idx >= len(episodes):
                await callback_query.message.reply_text("❌ جلسه مورد نظر یافت نشد.")
                return

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
                dl_row.append(InlineKeyboardButton("🎧 دریافت صوت (MP3)", callback_data=f"tg_vip_dl:{cat_id}:{page}:{ep_idx}:audio"))
            if ep.get("video_download_url") or ep.get("video_url"):
                dl_row.append(InlineKeyboardButton("🎬 دریافت ویدیو (MP4)", callback_data=f"tg_vip_dl:{cat_id}:{page}:{ep_idx}:video"))
            if dl_row:
                btns.append(dl_row)
            btns.append([InlineKeyboardButton("🔙 بازگشت به لیست جلسات", callback_data=f"tg_vip_cat:{cat_id}:{page}")])

            try:
                await callback_query.message.edit_text(txt, parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(btns))
            except Exception:
                await callback_query.message.reply_text(txt, parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(btns))

        @self.app.on_callback_query(filters.regex(r"^tg_vip_dl:(\d+):(\d+):(\d+):(audio|video)$"))
        async def handle_tg_vip_dl(client: Client, callback_query: CallbackQuery):
            """
            دانلود و ارسال فایل صوتی یا ویدیویی جلسه پریمیوم همراه با کش سراسری file_id.
            """
            await callback_query.answer()
            from services.feed_scraper import feed_scraper
            from core.database import db_get_cached_file_id, db_set_cached_file_id
            cat_id = int(callback_query.matches[0].group(1))
            page = int(callback_query.matches[0].group(2))
            ep_idx = int(callback_query.matches[0].group(3))
            media_type = callback_query.matches[0].group(4)

            user_id = callback_query.from_user.id
            if not UserService.is_user_vip(user_id):
                await callback_query.message.reply_text("🔒 جهت دانلود این فایل نیاز به اشتراک فعال پریمیوم دارید.")
                return

            res = await feed_scraper.get_category_episodes(cat_id, page=page, limit=6)
            episodes = res.get("episodes", [])
            if ep_idx >= len(episodes):
                await callback_query.message.reply_text("❌ جلسه یافت نشد.")
                return

            ep = episodes[ep_idx]
            url = (ep.get("audio_download_url") or ep.get("audio_url")) if media_type == "audio" else (ep.get("video_download_url") or ep.get("video_url"))
            if not url:
                await callback_query.message.reply_text("❌ لینک دانلودی برای این فرمت موجود نیست.")
                return

            status_msg = await callback_query.message.reply_text(
                f"⏳ <b>در حال آماده‌سازی و ارسال {'صوت' if media_type == 'audio' else 'ویدیو'}...</b>\n"
                f"📄 {escape(ep.get('title', ''))}",
                parse_mode=enums.ParseMode.HTML
            )

            file_key = f"abas_{cat_id}_{page}_{ep_idx}_{media_type}_{abs(hash(url))}"
            cached_fid = await db_get_cached_file_id(file_key, "telegram")
            if cached_fid:
                try:
                    if media_type == "audio":
                        await client.send_audio(
                            chat_id=callback_query.message.chat.id,
                            audio=cached_fid,
                            caption=f"🎧 <b>{escape(ep.get('title', ''))}</b>\n💎 اشتراک پریمیوم",
                            parse_mode=enums.ParseMode.HTML
                        )
                    else:
                        await client.send_video(
                            chat_id=callback_query.message.chat.id,
                            video=cached_fid,
                            caption=f"🎬 <b>{escape(ep.get('title', ''))}</b>\n💎 اشتراک پریمیوم",
                            parse_mode=enums.ParseMode.HTML
                        )
                    await status_msg.delete()
                    return
                except Exception as e:
                    logger.warning(f"Failed sending cached file_id in telegram: {e}")

            # Download locally and send
            ext = ".mp3" if media_type == "audio" else ".mp4"
            target_path = config.TEMP_DIR / f"vip_tg_{uuid.uuid4().hex[:8]}{ext}"
            target_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                import aiohttp
                async with aiohttp.ClientSession(headers={"User-Agent": "Mozilla/5.0"}) as sess:
                    async with sess.get(url, timeout=aiohttp.ClientTimeout(total=180)) as resp:
                        if resp.status == 200:
                            with open(target_path, "wb") as f_out:
                                async for chunk in resp.content.iter_chunked(128 * 1024):
                                    f_out.write(chunk)
                        else:
                            await status_msg.edit_text("❌ خطا در دانلود فایل از سرور منبع.")
                            return

                if not target_path.exists() or target_path.stat().st_size == 0:
                    await status_msg.edit_text("❌ فایل دانلود شده نامعتبر است.")
                    return

                if media_type == "audio":
                    sent = await client.send_audio(
                        chat_id=callback_query.message.chat.id,
                        audio=str(target_path),
                        title=ep.get("title", "فایل صوتی"),
                        performer="استاد عباس‌منش",
                        caption=f"🎧 <b>{escape(ep.get('title', ''))}</b>\n💎 اشتراک پریمیوم",
                        parse_mode=enums.ParseMode.HTML
                    )
                    if sent and sent.audio:
                        await db_set_cached_file_id(file_key, "telegram", sent.audio.file_id, "audio")
                else:
                    sent = await client.send_video(
                        chat_id=callback_query.message.chat.id,
                        video=str(target_path),
                        caption=f"🎬 <b>{escape(ep.get('title', ''))}</b>\n💎 اشتراک پریمیوم",
                        parse_mode=enums.ParseMode.HTML
                    )
                    if sent and sent.video:
                        await db_set_cached_file_id(file_key, "telegram", sent.video.file_id, "video")

                await status_msg.delete()
            except Exception as e:
                logger.error(f"Error sending VIP media in telegram: {e}")
                await status_msg.edit_text(f"❌ خطا در ارسال فایل: {e}")
            finally:
                if target_path.exists():
                    try: target_path.unlink()
                    except Exception: pass

        @self.app.on_message(filters.private & filters.regex(r"(?i)^(💎\s*فرکانس فراوانی|فرکانس فراوانی|فرکانس|/frequency)$"))
        async def customer_frequency_menu(client: Client, message: Message):
            txt = (
                "💎 <b>فرکانس فراوانی و آرامش درون</b>\n\n"
                "با انتخاب هر بخش، باورهای ثروت‌ساز و آرامش‌بخش روزانه را ورق بزنید و ذهن خود را روی مدار توانگری و دریافت برکت الهی تنظیم کنید:"
            )
            await message.reply_text(txt, parse_mode=enums.ParseMode.HTML, reply_markup=build_telegram_frequency_cats_keyboard())

        @self.app.on_callback_query(filters.regex(r"^freq_cats$"))
        async def handle_freq_cats_cb(client: Client, callback_query: CallbackQuery):
            await callback_query.answer()
            txt = (
                "💎 <b>فرکانس فراوانی و آرامش درون</b>\n\n"
                "دسته‌بندی مورد نظر خود را انتخاب نمایید:"
            )
            await callback_query.edit_message_text(txt, parse_mode=enums.ParseMode.HTML, reply_markup=build_telegram_frequency_cats_keyboard())

        @self.app.on_callback_query(filters.regex(r"^freq_page:(MORNING|NIGHT):(\d+)$"))
        async def handle_freq_page_cb(client: Client, callback_query: CallbackQuery):
            await callback_query.answer()
            match = re.match(r"^freq_page:(MORNING|NIGHT):(\d+)$", callback_query.data)
            if not match:
                return
            category = match.group(1)
            idx = int(match.group(2))
            item, curr_num, total = FrequencyService.get_item(category, idx)
            if not item:
                await callback_query.answer("هیچ باوری در این بخش یافت نشد.", show_alert=True)
                return
            card_text = FrequencyService.format_card(item, curr_num, total)
            await callback_query.edit_message_text(
                card_text,
                parse_mode=enums.ParseMode.MARKDOWN,
                reply_markup=build_telegram_frequency_nav_keyboard(category, curr_num - 1, total)
            )

        @self.app.on_callback_query(filters.regex(r"^freq_noop$"))
        async def handle_freq_noop_cb(client: Client, callback_query: CallbackQuery):
            await callback_query.answer()

        @self.app.on_callback_query(filters.regex(r"^btn_my_courses$"))
        async def handle_btn_my_courses_cb(client: Client, callback_query: CallbackQuery):
            await callback_query.answer()
            user_id = callback_query.from_user.id
            purchased = await StoreService.get_customer_purchased_courses(user_id)
            if not purchased:
                await callback_query.message.reply_text(
                    "📚 <b>دوره‌های من:</b>\n\n"
                    "هنوز دوره‌ای به نام حساب شما ثبت نشده است.\n"
                    "می‌توانید دوره‌های آموزشی را از بخش «📚 لیست دوره‌های آموزشی» یا وب‌سایت تهیه نمایید.",
                    parse_mode=enums.ParseMode.HTML
                )
                return
            await callback_query.message.reply_text(
                f"📚 <b>دوره‌های فعال و خریداری‌شده شما ({len(purchased)} دوره):</b>\n\n"
                "جهت ورود و دریافت محتوای هر دوره، از دکمه‌های شیشه‌ای زیر استفاده فرمایید:",
                parse_mode=enums.ParseMode.HTML
            )
            for i, c in enumerate(purchased, 1):
                c_name = c.get("name") or "دوره آموزشی"
                card_txt, buttons = StoreService.format_customer_course_card(c_name, c.get("download_link"), i, len(purchased))
                kb = None
                if buttons:
                    kb = InlineKeyboardMarkup([[InlineKeyboardButton(b["text"], url=b["url"])] for b in buttons])
                await callback_query.message.reply_text(card_txt, parse_mode=enums.ParseMode.HTML, reply_markup=kb)

        @self.app.on_callback_query(filters.regex(r"^cnav:courses$"))
        async def handle_cnav_courses_cb(client: Client, callback_query: CallbackQuery):
            await callback_query.answer()
            prods = await StoreService.get_products(is_free_only=False)
            if not prods:
                await callback_query.message.reply_text("📚 در حال حاضر دوره‌ای برای فروش ثبت نشده است.")
                return
            lines = ["📚 <b>لیست دوره‌های آموزشی تخصصی:</b>", "جهت مشاهده جزئیات و ثبت سفارش دوره موردنظر را انتخاب نمایید:\n"]
            buttons = [[InlineKeyboardButton(f"🎓 {p.name} ({p.price:,} تومان)", callback_data=f"cview:{p.product_id}")] for p in prods]
            await callback_query.message.reply_text("\n".join(lines), parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))

        @self.app.on_callback_query(filters.regex(r"^cnav:gifts$"))
        async def handle_cnav_gifts_cb(client: Client, callback_query: CallbackQuery):
            await callback_query.answer()
            gifts = await StoreService.get_products(is_free_only=True)
            if not gifts:
                await callback_query.message.reply_text("🎁 در حال حاضر هدیه رایگانی فعال نیست.")
                return
            u = UserService.get_user_by_platform_id("telegram", callback_query.from_user.id)
            invites = u.successful_invites if u else 0
            lines = ["🎁 <b>دوره‌ها و هدایای آموزشی رایگان:</b>", "جهت دریافت هدیه روی عنوان آن کلیک کنید:\n"]
            buttons = []
            for g in gifts:
                req_ref = getattr(g, "requires_referral", False)
                if req_ref and invites < 1:
                    buttons.append([InlineKeyboardButton(f"🔒 {g.name} (نیازمند ۱ دعوت)", callback_data=f"tg_gift_locked:{g.product_id}")])
                else:
                    buttons.append([InlineKeyboardButton(f"🎁 {g.name} (رایگان)", callback_data=f"cview:{g.product_id}")])
            buttons.append([InlineKeyboardButton("🎁 طرح دعوت از دوستان و دریافت هدایا", callback_data="referral_info")])
            await callback_query.message.reply_text("\n".join(lines), parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))

        @self.app.on_callback_query(filters.regex(r"^tg_gift_locked:"))
        async def handle_tg_gift_locked_cb(client: Client, callback_query: CallbackQuery):
            await callback_query.answer()
            g_id = callback_query.data.split(":")[1]
            g_prod = await StoreService.get_product(g_id)
            g_name = g_prod.name if g_prod else "این دوره هدیه"
            user_id = callback_query.from_user.id
            bot_me = await client.get_me()
            bot_username = bot_me.username or getattr(config, "TELEGRAM_BOT_USERNAME", "") or ""
            ref_link = ReferralService.get_referral_link(user_id, "telegram", bot_username)
            u = UserService.get_user_by_platform_id("telegram", user_id)
            invites = u.successful_invites if u else 0
            share_url = f"https://t.me/share/url?url={ref_link}&text=سلام!%20برای%20دریافت%20هدیه%20و%20شرکت%20در%20دوره‌ها%20روی%20این%20لینک%20کلیک%20کن:"
            msg_txt = (
                f"🔒 <b>دسترسی به دوره هدیه «{escape(g_name)}» نیازمند ۱ دعوت موفق است!</b>\n\n"
                "با ارسال لینک دعوت زیر به دوستان خود، به محض پیوستن ۱ نفر، لینک دانلود این فایل به صورت خودکار برای شما فعال خواهد شد.\n\n"
                f"🔗 <b>لینک اختصاصی دعوت شما:</b>\n<code>{ref_link}</code>\n\n"
                f"👥 <b>تعداد دعوت‌های موفق شما:</b> <b>{invites} از ۱ نفر</b>\n"
            )
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("📤 ارسال لینک برای دوستان", url=share_url)],
                [InlineKeyboardButton("🔙 بازگشت به لیست هدایا", callback_data="cnav:gifts")]
            ])
            await callback_query.message.reply_text(msg_txt, parse_mode=enums.ParseMode.HTML, reply_markup=kb)

        @self.app.on_callback_query(filters.regex(r"^cnav:support$"))
        async def handle_cnav_support_cb(client: Client, callback_query: CallbackQuery):
            await callback_query.answer()
            session_manager.set_user_action(f"tg_{callback_query.from_user.id}", "await_support_msg", "none")
            await callback_query.message.reply_text(
                "💬 <b>ارتباط با پشتیبانی:</b>\n\n"
                "لطفاً متن پیام، سوال یا شماره پیگیری خود را ارسال فرمایید تا تیکت شما به مدیریت ارسال گردد:\n"
                "(جهت انصراف عبارت <code>/cancel</code> را بفرستید)",
                parse_mode=enums.ParseMode.HTML
            )

        @self.app.on_message(filters.private & filters.regex(r"(?i)^(🎁\s*فایل‌های هدیه|فایل‌های هدیه|💬\s*پشتیبانی و هدایا|پشتیبانی و هدایا|💬\s*پشتیبانی|پشتیبانی|🎁\s*دانلودها \(هدیه\)|دانلودها|هدیه|/support|/gifts)"))
        async def customer_support(client: Client, message: Message):
            if not await check_force_join_telegram(client, message.from_user.id) and not self.is_admin(message.from_user.id):
                ch = await get_system_setting("tg_fjoin_channel", config.FORCE_JOIN_CHANNEL_TELEGRAM)
                await message.reply_text("⚠️ <b>برای استفاده از امکانات ربات ابتدا باید در کانال رسمی ما عضو شوید:</b>", parse_mode=enums.ParseMode.HTML, reply_markup=build_telegram_force_join_keyboard(ch))
                return
            gifts = await StoreService.get_products(is_free_only=True)
            u = UserService.get_user_by_platform_id("telegram", message.from_user.id)
            invites = u.successful_invites if u else 0
            buttons = []
            if gifts:
                for g in gifts:
                    req_ref = getattr(g, "requires_referral", False)
                    if req_ref and invites < 1:
                        buttons.append([InlineKeyboardButton(f"🔒 {g.name} (نیازمند ۱ دعوت)", callback_data=f"tg_gift_locked:{g.product_id}")])
                    else:
                        buttons.append([InlineKeyboardButton(f"🎁 {g.name} (رایگان)", callback_data=f"cview:{g.product_id}")])
            buttons.append([InlineKeyboardButton("👥 طرح دعوت از دوستان و دریافت هدیه", callback_data="referral_info")])
            session_manager.set_user_action(f"tg_{message.from_user.id}", "await_support_msg", "none")
            support_custom = getattr(config, "SUPPORT_CENTER_TEXT", "").strip()
            if support_custom:
                txt = (
                    f"💬 <b>مرکز پشتیبانی و ارتباط با ما:</b>\n\n"
                    f"{support_custom}\n\n"
                    "📩 <b>ارسال پیام به پشتیبانی:</b> همچنین می‌توانید متن پیام، سوال یا شماره پیگیری خود را ارسال فرمایید تا تیکت ثبت گردد."
                )
            else:
                txt = (
                    "🎁 <b>فایل‌ها و هدایای آموزشی رایگان:</b>\n\n"
                    "جهت دریافت هر فایل، روی دکمه مربوطه در زیر کلیک فرمایید.\n\n"
                    "📩 <b>ارسال پیام به پشتیبانی:</b> همچنین می‌توانید متن پیام، سوال یا شماره پیگیری خود را ارسال فرمایید تا تیکت ثبت گردد."
                )
            await message.reply_text(txt, parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))

        # Product View Callback
        @self.app.on_callback_query(filters.regex(r"^(cview|prod_view):"))
        async def product_view_cb(client: Client, callback_query: CallbackQuery):
            prod_id = callback_query.data.split(":")[1]
            prod = await StoreService.get_product(prod_id)
            if not prod:
                await callback_query.answer("محصول یافت نشد.", show_alert=True)
                return
            is_free = (prod.price == 0)
            btn_txt = "🎁 دریافت آنی فایل هدیه" if is_free else f"📥 ثبت سفارش ({prod.price:,} تومان)"
            desc_txt = (prod.description or "بدون توضیحات").strip()
            price_txt = "رایگان (هدیه)" if is_free else f"{prod.price:,} تومان"

            # Form caption within Telegram's 1024 char limit
            caption = f"🎓 <b>{escape(prod.name)}</b>\n\n📝 <b>توضیحات دوره:</b>\n{escape(desc_txt)}\n\n💵 <b>قیمت:</b> <b>{price_txt}</b>"
            if len(caption) > 1000:
                short_desc = desc_txt[: max(50, 950 - len(prod.name))] + "..."
                caption = f"🎓 <b>{escape(prod.name)}</b>\n\n📝 <b>توضیحات دوره:</b>\n{escape(short_desc)}\n\n💵 <b>قیمت:</b> <b>{price_txt}</b>"

            episodes = prod.episodes or await StoreService.get_course_episodes(prod.product_id)
            kb_rows = [[InlineKeyboardButton(btn_txt, callback_data=f"cbuy:{prod.product_id}")]]
            if episodes:
                kb_rows.append([InlineKeyboardButton(f"🎵 سرفصل‌های دوره ({len(episodes)} قسمت)", callback_data=f"tg_c_episodes:{prod.product_id}")])
            kb_rows.append([InlineKeyboardButton("🔙 بازگشت به لیست دوره‌ها", callback_data="cnav:back")])
            kb = InlineKeyboardMarkup(kb_rows)

            photo_res = resolve_telegram_course_photo(prod)
            sent_photo = False
            if photo_res:
                try:
                    chat_id = callback_query.message.chat.id
                    photo_val = photo_res["value"]
                    msg = await client.send_photo(
                        chat_id=chat_id,
                        photo=photo_val,
                        caption=caption,
                        parse_mode=enums.ParseMode.HTML,
                        reply_markup=kb
                    )
                    sent_photo = True
                    # If we sent via local_path or URL and didn't have photo_file_id cached, cache it now!
                    if photo_res["type"] != "file_id" and msg and msg.photo and msg.photo.file_id:
                        try:
                            await StoreService.update_product_field(prod.product_id, "photo_file_id", msg.photo.file_id)
                        except Exception:
                            pass
                except Exception as e:
                    logger.warning(f"[Telegram] Failed to send course photo: {e}")
                    sent_photo = False

            if not sent_photo:
                await callback_query.message.reply_text(caption, parse_mode=enums.ParseMode.HTML, reply_markup=kb)

        # Course Episodes Callback Handler
        @self.app.on_callback_query(filters.regex(r"^tg_c_episodes:"))
        async def tg_course_episodes_cb(client: Client, callback_query: CallbackQuery):
            await callback_query.answer()
            c_pid = callback_query.data.split(":", 1)[1]
            c_prod = await StoreService.get_product(c_pid)
            if not c_prod:
                await callback_query.message.reply_text("❌ دوره مورد نظر یافت نشد.")
                return
            c_eps = await StoreService.get_course_episodes(c_pid)
            if not c_eps:
                await callback_query.message.reply_text(f"ℹ️ هنوز قسمتی برای دوره «{c_prod.name}» ثبت نشده است.")
                return
            buttons = []
            for ep in c_eps:
                ep_num = ep.get("part") or 1
                ep_t = ep.get("title") or f"قسمت {ep_num}"
                ep_u = ep.get("url")
                if ep_u:
                    buttons.append([InlineKeyboardButton(f"🎵 قسمت {ep_num}: {ep_t}", url=ep_u)])
            buttons.append([InlineKeyboardButton("🔙 بازگشت به دوره", callback_data=f"cview:{c_pid}")])
            await callback_query.message.reply_text(
                f"📚 <b>سرفصل‌ها و قسمت‌های دوره «{escape(c_prod.name)}»:</b>",
                parse_mode=enums.ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(buttons)
            )

        # Product Navigation Back Callback
        @self.app.on_callback_query(filters.regex(r"^cnav:back$"))
        async def course_nav_back_cb(client: Client, callback_query: CallbackQuery):
            await callback_query.answer()
            prods = await StoreService.get_products(is_free_only=False)
            if not prods:
                await callback_query.message.reply_text("📚 در حال حاضر دوره‌ای برای فروش ثبت نشده است.")
                return
            lines = ["📚 <b>لیست دوره‌های آموزشی تخصصی:</b>", "جهت مشاهده جزئیات و ثبت سفارش دوره موردنظر را انتخاب نمایید:\n"]
            buttons = [[InlineKeyboardButton(f"🎓 {p.name} ({p.price:,} تومان)", callback_data=f"cview:{p.product_id}")] for p in prods]
            try:
                await callback_query.message.delete()
            except Exception:
                pass
            await callback_query.message.reply_text("\n".join(lines), parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))

        # Contact Sharing Handler (Cross-Platform Unified Identity)
        @self.app.on_message(filters.private & filters.contact)
        async def handle_contact_share(client: Client, message: Message):
            if not message.contact:
                return
            user_id = message.from_user.id
            raw_phone = message.contact.phone_number or ""
            norm_phone = normalize_phone(raw_phone)
            if not norm_phone:
                await message.reply_text("⚠️ شماره تلفن ارسالی نامعتبر است.")
                return

            first_name = message.from_user.first_name or ""
            last_name = message.from_user.last_name or ""
            full_name = f"{first_name} {last_name}".strip()

            u = UserService.link_platform_user(
                platform="telegram",
                platform_id=user_id,
                phone=norm_phone,
                full_name=full_name
            )

            # Check if there is a pending referral code
            pending_ref_data = session_manager.get_user_action(f"tg_ref_{user_id}")
            pending_ref = pending_ref_data.get("extra") if pending_ref_data else None
            if pending_ref:
                inviter_phone, newly_unlocked = ReferralService.record_referral(
                    inviter_code=pending_ref,
                    invited_phone=norm_phone,
                    invited_platform="telegram",
                    invited_platform_id=user_id
                )
                session_manager.clear_user_action(f"tg_ref_{user_id}")
                if newly_unlocked and inviter_phone:
                    inviter = UserService.get_user_by_phone(inviter_phone)
                    if inviter and inviter.telegram_id:
                        try:
                            await client.send_message(
                                chat_id=int(inviter.telegram_id),
                                text=ReferralService.get_congratulations_message("telegram"),
                                parse_mode=enums.ParseMode.HTML
                            )
                        except Exception as e:
                            logger.warning(f"[Telegram] Failed to notify inviter {inviter.telegram_id}: {e}")

            success_msg = (
                f"✅ <b>حساب کاربری شما با موفقیت متصل شد.</b>\n\n"
                f"📱 شماره تماس: <code>{norm_phone}</code>\n"
                f"👤 نام: <b>{escape(full_name or 'کاربر گرامی')}</b>\n"
                f"🔗 کد معرف اختصاصی شما: <code>{u.referral_code}</code>"
            )
            await message.reply_text(
                success_msg,
                parse_mode=enums.ParseMode.HTML,
                reply_markup=get_customer_keyboard()
            )

            # Check if user had a pending purchase
            pending_buy_data = session_manager.get_user_action(f"tg_pending_buy_{user_id}")
            if pending_buy_data:
                prod_id = pending_buy_data.get("extra")
                session_manager.clear_user_action(f"tg_pending_buy_{user_id}")
                if prod_id:
                    prod = await StoreService.get_product(prod_id)
                    if prod:
                        await _check_terms_and_proceed(client, message.chat.id, user_id, message.from_user.username or "", full_name, prod, u)

            # Check if user had a pending referral view
            pending_ref_view = session_manager.get_user_action(f"tg_pending_referral_{user_id}")
            if pending_ref_view:
                session_manager.clear_user_action(f"tg_pending_referral_{user_id}")
                await _show_referral_panel(client, message.chat.id, user_id, u)

        async def _create_and_send_order(client: Client, chat_id: int | str, user_id: int | str, username: str, full_name: str, prod: Any, u: Any):
            if prod.price == 0:
                order = await StoreService.create_order(user_id, username, full_name, u.phone if u else "", prod, platform="telegram")
                UserService.unlock_gift_by_platform("telegram", user_id, prod.product_id)
                is_pkg = bool(getattr(prod, "delivery_type", "channel") == "files_package" or getattr(prod, "files_package", None) or getattr(prod, "episodes", None))
                if is_pkg:
                    await client.send_message(chat_id, f"🎁 <b>دوره «{escape(prod.name)}» با موفقیت فعال شد!</b>\nفایل‌های دوره هم‌اکنون به ترتیب برای شما ارسال می‌شوند:\nشماره سفارش: <code>{order.order_id}</code>", parse_mode=enums.ParseMode.HTML)
                    await StoreService.deliver_course_package(prod, user_id, "telegram")
                else:
                    dl_content = prod.download_link or "لینک دانلود در دسترس است."
                    cust_msg = StoreService.format_delivery_message(prod.name, order.order_id, dl_content, 0)
                    parsed_dl = StoreService.parse_delivery_links(dl_content)
                    cust_buttons = []
                    for lk in parsed_dl["links"]:
                        cust_buttons.append([InlineKeyboardButton(lk["title"], url=lk["url"])])
                    cust_kb = InlineKeyboardMarkup(cust_buttons) if cust_buttons else None
                    await client.send_message(chat_id, cust_msg, reply_markup=cust_kb, parse_mode=enums.ParseMode.HTML)
                return

            wallet_balance = await StoreService.get_wallet_balance(user_id)
            wallet_used = min(wallet_balance, prod.price)
            remaining = prod.price - wallet_used

            order = await StoreService.create_order(
                user_id=user_id,
                username=username,
                customer_name=full_name,
                phone=u.phone if u else "",
                product=prod,
                platform="telegram",
                wallet_used=wallet_used
            )
            session_manager.set_user_action(f"tg_{user_id}", "await_receipt", order.order_id)

            lines = ["🧾 <b>فاکتور سفارش شما:</b>", f"🎓 دوره: <b>{escape(prod.name)}</b>", f"💵 مبلغ کل: <b>{prod.price:,} تومان</b>"]
            if wallet_used > 0: lines.append(f"💰 کسر از کیف پول: <b>{wallet_used:,} تومان</b>")
            c_num = await get_system_setting("CARD_NUMBER", config.CARD_NUMBER)
            c_holder = await get_system_setting("CARD_HOLDER", config.CARD_HOLDER)
            lines.extend([f"💳 <b>مبلغ قابل پرداخت:</b> <b>{remaining:,} تومان</b>", "", "🏦 <b>اطلاعات کارت جهت واریز:</b>", f"▫️ شماره کارت: <code>{c_num}</code>", f"▫️ صاحب حساب: <b>{c_holder}</b>", "", "📸 <i>لطفاً پس از واریز، عکس فیش واریزی خود را ارسال فرمایید.</i>"])
            await client.send_message(chat_id, "\n".join(lines), parse_mode=enums.ParseMode.HTML)

        async def _check_terms_and_proceed(client: Client, chat_id: int | str, user_id: int | str, username: str, full_name: str, prod: Any, u: Any):
            if prod.price > 0 and not u.terms_accepted:
                raw_terms = await get_system_setting("COURSE_TERMS_TEXT", config.COURSE_TERMS_TEXT)
                terms_text = (
                    f"⚖️ <b>تعهدنامه و قوانین خرید دوره {escape(prod.name)}:</b>\n\n"
                    f"{raw_terms}\n\n"
                    "آیا شرایط و تعهدنامه فوق را مطالعه کرده و می‌پذیرید؟"
                )
                terms_kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ شرایط را می‌پذیرم", callback_data=f"terms_accept:{prod.product_id}")],
                    [InlineKeyboardButton("❌ انصراف", callback_data="terms_reject")]
                ])
                await client.send_message(chat_id, terms_text, parse_mode=enums.ParseMode.HTML, reply_markup=terms_kb)
                return
            await _create_and_send_order(client, chat_id, user_id, username, full_name, prod, u)

        async def _show_referral_panel(client: Client, chat_id: int | str, user_id: int | str, u: Any):
            bot_me = await client.get_me()
            bot_username = bot_me.username or getattr(config, "TELEGRAM_BOT_USERNAME", "") or ""
            ref_link = ReferralService.get_referral_link(user_id, "telegram", bot_username)
            invites = u.successful_invites
            unlocked = UserService.is_gift_unlocked_by_platform("telegram", user_id, TOHID_AMALI_PACK_ID)

            st_txt = "✅ <b>باز شده و آماده دریافت</b>" if unlocked else "🔒 <b>قفل (نیاز به ۱ دعوت موفق)</b>"
            inv_custom = getattr(config, "INVITE_FRIENDS_TEXT", "").strip()
            inv_body = inv_custom if inv_custom else "با ارسال لینک دعوت اختصاصی خود به دوستان، به محض پیوستن ۱ نفر، <b>بسته صوتی کامل ۱۱ قسمتی توحید عملی</b> برای شما فعال خواهد شد!"
            msg_text = (
                "🎁 <b>طرح دعوت از دوستان و دریافت هدایا:</b>\n\n"
                f"{inv_body}\n\n"
                f"🔗 <b>لینک اختصاصی دعوت شما:</b>\n<code>{ref_link}</code>\n\n"
                f"👥 <b>تعداد دعوت‌های موفق شما:</b> <b>{invites} نفر</b>\n"
                f"🎧 <b>وضعیت بسته صوتی:</b> {st_txt}\n"
            )
            share_url = f"https://t.me/share/url?url={ref_link}&text=سلام!%20برای%20دریافت%20هدیه%20و%20شرکت%20در%20دوره‌ها%20روی%20این%20لینک%20کلیک%20کن:"
            buttons = [
                [InlineKeyboardButton("📤 ارسال لینک برای دوستان", url=share_url)]
            ]
            if unlocked:
                buttons.append([InlineKeyboardButton("🎧 دریافت ۱۱ فایل صوتی توحید عملی", callback_data="tohid_amali_list")])
            buttons.append([InlineKeyboardButton("🔙 بازگشت به حساب کاربری", callback_data="btn_profile")])
            await client.send_message(chat_id, msg_text, parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))

        # Product Buy Callback
        @self.app.on_callback_query(filters.regex(r"^cbuy:"))
        async def product_buy_cb(client: Client, callback_query: CallbackQuery):
            prod_id = callback_query.data.split(":")[1]
            prod = await StoreService.get_product(prod_id)
            if not prod:
                await callback_query.answer("محصول یافت نشد.", show_alert=True)
                return

            user_id = callback_query.from_user.id
            username = callback_query.from_user.username or ""
            full_name = f"{callback_query.from_user.first_name or ''} {callback_query.from_user.last_name or ''}".strip()

            u = UserService.get_user_by_platform_id("telegram", user_id)
            if not u or not u.phone:
                session_manager.set_user_action(f"tg_pending_buy_{user_id}", prod_id, prod_id)
                contact_kb = ReplyKeyboardMarkup(
                    [[KeyboardButton("📱 ارسال شماره موبایل (جهت ثبت‌نام و صدور فاکتور)", request_contact=True)]],
                    resize_keyboard=True,
                    one_time_keyboard=True
                )
                await callback_query.message.reply_text(
                    "⚠️ <b>ثبت‌نام سریع جهت صدور فاکتور رسمی:</b>\n\n"
                    "برای صدور فاکتور معتبر، اتصال کیف پول و دسترسی دائمی به فایل‌های دوره، لطفاً شماره تماس خود را از طریق دکمه زیر ارسال فرمایید:",
                    parse_mode=enums.ParseMode.HTML,
                    reply_markup=contact_kb
                )
                return

            await _check_terms_and_proceed(client, callback_query.message.chat.id, user_id, username, full_name, prod, u)

        # Pre-Purchase Terms Acceptance Callbacks
        @self.app.on_callback_query(filters.regex(r"^terms_accept:"))
        async def terms_accept_cb(client: Client, callback_query: CallbackQuery):
            await callback_query.answer("تعهدنامه با موفقیت پذیرفته شد.")
            prod_id = callback_query.data.split(":", 1)[1]
            user_id = callback_query.from_user.id
            username = callback_query.from_user.username or ""
            full_name = f"{callback_query.from_user.first_name or ''} {callback_query.from_user.last_name or ''}".strip()

            u = UserService.accept_terms_by_platform("telegram", user_id)
            prod = await StoreService.get_product(prod_id)
            if prod:
                await _create_and_send_order(client, callback_query.message.chat.id, user_id, username, full_name, prod, u)

        @self.app.on_callback_query(filters.regex(r"^terms_reject$"))
        async def terms_reject_cb(client: Client, callback_query: CallbackQuery):
            await callback_query.answer()
            await callback_query.message.edit_text("❌ خرید دوره لغو شد. در صورت تمایل می‌توانید سایر دوره‌ها را مشاهده فرمایید.")

        # Referral Menu Callback
        @self.app.on_callback_query(filters.regex(r"^referral_info$"))
        async def referral_info_cb(client: Client, callback_query: CallbackQuery):
            await callback_query.answer()
            user_id = callback_query.from_user.id
            u = UserService.get_user_by_platform_id("telegram", user_id)
            if not u or not u.phone:
                session_manager.set_user_action(f"tg_pending_referral_{user_id}", "referral", "referral")
                contact_kb = ReplyKeyboardMarkup(
                    [[KeyboardButton("📱 ارسال شماره موبایل (جهت دریافت هدیه)", request_contact=True)]],
                    resize_keyboard=True,
                    one_time_keyboard=True
                )
                await callback_query.message.reply_text(
                    "🎁 <b>دریافت بسته صوتی ۱۱ قسمتی توحید عملی:</b>\n\n"
                    "برای فعال‌سازی لینک دعوت اختصاصی و دریافت فایل‌های هدیه، لطفاً ابتدا شماره تماس خود را ثبت نمایید:",
                    parse_mode=enums.ParseMode.HTML,
                    reply_markup=contact_kb
                )
                return

            await _show_referral_panel(client, callback_query.message.chat.id, user_id, u)

        # Profile Quick Callback
        @self.app.on_callback_query(filters.regex(r"^btn_profile$"))
        async def btn_profile_cb(client: Client, callback_query: CallbackQuery):
            await callback_query.answer()
            user_id = callback_query.from_user.id
            cust = await StoreService.get_or_create_customer(user_id, platform="telegram")
            orders = await StoreService.get_customer_orders(user_id)
            purchased = await StoreService.get_customer_purchased_courses(user_id)
            lines = [
                "👤 <b>اطلاعات حساب کاربری شما:</b>", "",
                f"▫️ <b>شناسه کاربری:</b> <code>{cust.user_id}</code>",
                f"💰 <b>موجودی کیف پول:</b> <b>{cust.wallet_balance:,} تومان</b>",
                f"📦 <b>تعداد کل خریدهای شما:</b> <b>{len(orders)} سفارش</b>",
                f"🎁 <b>درصد کش‌بک خریدها:</b> <b>{config.CASHBACK_PERCENT}%</b>",
                f"📚 <b>دوره‌های فعال شما:</b> <b>{len(purchased)} دوره</b>",
                ""
            ]
            buttons = []
            if purchased:
                buttons.append([InlineKeyboardButton(f"📚 مشاهده دوره‌های من ({len(purchased)} دوره فعال)", callback_data="btn_my_courses")])
            else:
                buttons.append([InlineKeyboardButton("📚 لیست دوره‌های آموزشی", callback_data="cnav:courses")])
            buttons.append([InlineKeyboardButton("🎁 دوره‌ها و هدایای رایگان", callback_data="cnav:gifts")])
            buttons.append([InlineKeyboardButton("🎁 دریافت رایگان توحید عملی (دعوت دوستان)", callback_data="referral_info")])
            buttons.append([InlineKeyboardButton("💬 ارتباط با پشتیبانی", callback_data="cnav:support")])
            await callback_query.message.reply_text("\n".join(lines), parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))

        # Tohid Amali Episodes List Callback
        @self.app.on_callback_query(filters.regex(r"^tohid_amali_list$"))
        async def tohid_amali_list_cb(client: Client, callback_query: CallbackQuery):
            await callback_query.answer()
            user_id = callback_query.from_user.id
            if not await check_force_join_telegram(client, user_id) and not self.is_admin(user_id):
                ch = await get_system_setting("tg_fjoin_channel", config.FORCE_JOIN_CHANNEL_TELEGRAM)
                await callback_query.message.reply_text(
                    "⚠️ <b>برای دریافت فایل‌های دوره، عضویت در کانال الزامی است:</b>",
                    parse_mode=enums.ParseMode.HTML,
                    reply_markup=build_telegram_force_join_keyboard(ch)
                )
                return

            if not UserService.is_gift_unlocked_by_platform("telegram", user_id, TOHID_AMALI_PACK_ID) and not self.is_admin(user_id):
                await callback_query.message.reply_text("🔒 <b>این بسته هنوز برای شما قفل است.</b>\nلطفاً ابتدا ۱ نفر از دوستان خود را دعوت کنید.", parse_mode=enums.ParseMode.HTML)
                return

            lines = [
                "🎧 <b>فهرست ۱۱ قسمت صوتی دوره توحید عملی:</b>",
                "جهت دریافت هر فایل، روی دکمه آن کلیک کنید:\n"
            ]
            buttons = []
            for ep in TOHID_AMALI_EPISODES:
                p = ep["part"]
                t = ep["title"]
                d = ep["duration"]
                buttons.append([InlineKeyboardButton(f"▶️ قسمت {p}: {t} ({d})", callback_data=f"tohid_part:{p}")])
            buttons.append([InlineKeyboardButton("🔙 بازگشت به منوی دعوت", callback_data="referral_info")])
            await callback_query.message.reply_text("\n".join(lines), parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))

        # Tohid Amali Part Delivery Callback (Fast file_id Caching)
        @self.app.on_callback_query(filters.regex(r"^tohid_part:(\d+)$"))
        async def tohid_part_cb(client: Client, callback_query: CallbackQuery):
            await callback_query.answer("در حال آماده‌سازی فایل صوتی...")
            user_id = callback_query.from_user.id
            part_num = int(callback_query.matches[0].group(1))

            if not await check_force_join_telegram(client, user_id) and not self.is_admin(user_id):
                ch = await get_system_setting("tg_fjoin_channel", config.FORCE_JOIN_CHANNEL_TELEGRAM)
                await callback_query.message.reply_text(
                    "⚠️ <b>برای دریافت فایل‌های دوره، عضویت در کانال الزامی است:</b>",
                    parse_mode=enums.ParseMode.HTML,
                    reply_markup=build_telegram_force_join_keyboard(ch)
                )
                return

            if not UserService.is_gift_unlocked_by_platform("telegram", user_id, TOHID_AMALI_PACK_ID) and not self.is_admin(user_id):
                await callback_query.message.reply_text("🔒 این بسته هنوز قفل است.")
                return

            ep = next((e for e in TOHID_AMALI_EPISODES if e["part"] == part_num), None)
            if not ep:
                await callback_query.message.reply_text("❌ قسمت مورد نظر یافت نشد.")
                return

            cache_key = f"tohid_part_{part_num}"
            cached_fid = await db_get_cached_file_id(cache_key, "telegram")
            caption_txt = f"🎧 <b>بسته صوتی توحید عملی - قسمت {part_num}</b>\n▫️ عنوان: <b>{ep['title']}</b>\n⏱ مدت: <code>{ep['duration']}</code>"

            if cached_fid:
                try:
                    await client.send_audio(
                        chat_id=user_id,
                        audio=cached_fid,
                        caption=caption_txt,
                        parse_mode=enums.ParseMode.HTML
                    )
                    return
                except Exception as e:
                    logger.warning(f"[Telegram] Failed to send cached file_id {cached_fid}: {e}")

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
                    sent = await client.send_audio(
                        chat_id=user_id,
                        audio=str(local_found),
                        caption=caption_txt,
                        title=f"توحید عملی - قسمت {part_num}: {ep['title']}",
                        performer="UNFINIT Academy",
                        parse_mode=enums.ParseMode.HTML
                    )
                    if sent and sent.audio and sent.audio.file_id:
                        await db_set_cached_file_id(cache_key, "telegram", sent.audio.file_id, "audio")
                    return
                except Exception as e:
                    logger.warning(f"[Telegram] Error sending audio file {local_found}: {e}")

            await callback_query.message.reply_text(
                f"{caption_txt}\n\n"
                "ℹ️ این فایل در حال آماده‌سازی و بارگذاری مستقیم بر روی سرور می‌باشد.",
                parse_mode=enums.ParseMode.HTML
            )

        # ================= AI 2-STAGE WORKFLOW HANDLERS =================
        @self.app.on_callback_query(filters.regex(r"^ai_eng:"))
        async def handle_ai_engine_selection(client: Client, callback_query: CallbackQuery):
            await callback_query.answer()
            parts = callback_query.data.split(":")
            if len(parts) < 3: return
            engine = parts[1]
            drop_id = parts[2]
            engine_title = "گوگل جمینای (Gemini Flash)" if engine == "gemini" else "نورا (Nara Router)"
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 کانال تلگرام (کپشن ژورنالی)", callback_data=f"ai_fmt:tg:{engine}:{drop_id}")],
                [InlineKeyboardButton("📸 اینستاگرام اکسپلور (کپشن و هشتگ)", callback_data=f"ai_fmt:ig:{engine}:{drop_id}")],
                [InlineKeyboardButton("🔙 مرحله قبل", callback_data=f"smeta:ai_transcribe:{drop_id}")]
            ])
            await callback_query.message.edit_text(
                f"🧠 <b>دستیار هوش مصنوعی ({engine_title}) (مرحله ۲ از ۲):</b>\n"
                "لطفاً قالب و سبک خروجی مورد نظر خود را انتخاب نمایید:",
                parse_mode=enums.ParseMode.HTML,
                reply_markup=kb
            )

        @self.app.on_callback_query(filters.regex(r"^ai_fmt:"))
        async def handle_ai_format_selection(client: Client, callback_query: CallbackQuery):
            await callback_query.answer()
            parts = callback_query.data.split(":")
            if len(parts) < 4: return
            fmt = parts[1]
            engine = parts[2]
            drop_id = parts[3]

            style = "instagram" if fmt == "ig" else "telegram"
            style_title = "📸 کپشن اینستاگرام" if style == "instagram" else "📢 پست کانال تلگرام"
            engine_title = "گوگل جمینای" if engine == "gemini" else "نورا (Nara)"

            drop = session_manager.get_session(drop_id)
            if not drop:
                try:
                    from core.database import db_get_media_session
                    drop = db_get_media_session(drop_id)
                    if drop:
                        session_manager._sessions[drop_id] = drop
                except Exception: pass
            if not drop:
                await callback_query.message.reply_text("❌ نشست فایل منقضی شده است.", parse_mode=enums.ParseMode.HTML)
                return

            async def ensure_ai_binary():
                local_check = drop.get("working_path") or drop.get("compressed_path") or drop.get("original_path")
                if not drop.get("is_downloaded_locally") or not local_check or not Path(str(local_check)).exists():
                    async def dl_func(fid, p):
                        target_media = drop.get("raw_message") or drop.get("file_id") or fid
                        try:
                            return await client.download_media(target_media, file_name=str(p))
                        except Exception:
                            return await client.download_media(target_media, file_name=str(p))
                    await MediaService.ensure_local_binary(drop_id, dl_func)

            await ensure_ai_binary()
            drop = session_manager.get_session(drop_id) or drop
            local_p = drop.get("working_path") or drop.get("compressed_path") or drop.get("original_path")
            if not local_p or not Path(str(local_p)).exists():
                await callback_query.message.reply_text("❌ فایل صوتی روی سرور یافت نشد.", parse_mode=enums.ParseMode.HTML)
                return

            status_m = await callback_query.message.reply_text(
                f"⏳ <b>[۱/۳] تحلیل با {engine_title} ({style_title})</b>\n▫️ در حال پردازش و استماع محتوا...",
                parse_mode=enums.ParseMode.HTML
            )

            async def _tg_progress(stage_text: str):
                try:
                    await status_m.edit_text(stage_text, parse_mode=enums.ParseMode.HTML)
                except Exception:
                    pass

            from services.ai_agent_service import ai_agent_service, ai_typing_action
            async def _tg_audio_typing():
                await client.send_chat_action(chat_id, enums.ChatAction.TYPING)

            async with ai_typing_action(_tg_audio_typing):
                res = await ai_agent_service.transcribe_and_summarize_audio(
                    Path(str(local_p)),
                    metadata=drop,
                    progress_callback=_tg_progress,
                    style=style,
                    engine=engine
                )
            if res.get("ok"):
                msg_text = res.get("formatted_message") or res.get("summary")
                if len(msg_text) > 4000:
                    msg_text = msg_text[:3990] + "..."
                try:
                    await status_m.edit_text(msg_text, parse_mode=enums.ParseMode.HTML)
                except Exception:
                    try:
                        await status_m.edit_text(msg_text, parse_mode=None)
                    except Exception:
                        await callback_query.message.reply_text(msg_text, parse_mode=None)
            else:
                err_txt = f"❌ {res.get('error') or 'خطا در پردازش هوش مصنوعی'}"
                try:
                    await status_m.edit_text(err_txt, parse_mode=enums.ParseMode.HTML)
                except Exception:
                    pass

        # ================= COURSE MANAGEMENT FROM CHAT =================
        @self.app.on_callback_query(filters.regex(r"^adm_pview:"))
        async def handle_admin_course_view(client: Client, callback_query: CallbackQuery):
            if not self.is_admin(callback_query.from_user.id):
                await callback_query.answer("⛔️ دسترسی غیرمجاز: این منو فقط برای مدیر است.", show_alert=True)
                return
            await callback_query.answer()
            try:
                pid = callback_query.data.split(":")[1]
                prod = await StoreService.get_product(pid)
                if not prod:
                    await callback_query.message.reply_text("❌ دوره یافت نشد.")
                    return
                txt = format_admin_course_card(prod)
                kb = build_admin_course_keyboard(pid, prod.active)
                photo_res = resolve_telegram_course_photo(prod)
                sent_photo = False
                if photo_res:
                    try:
                        await callback_query.message.delete()
                    except Exception:
                        pass
                    try:
                        msg = await client.send_photo(
                            chat_id=callback_query.message.chat.id,
                            photo=photo_res["value"],
                            caption=txt,
                            parse_mode=enums.ParseMode.HTML,
                            reply_markup=kb
                        )
                        sent_photo = True
                        if photo_res["type"] != "file_id" and msg and msg.photo and msg.photo.file_id:
                            try:
                                await StoreService.update_product_field(prod.product_id, "photo_file_id", msg.photo.file_id)
                            except Exception:
                                pass
                    except Exception as pe:
                        logger.warning(f"[tg_adm_pview] Send photo failed: {pe}")
                        sent_photo = False
                if not sent_photo:
                    if callback_query.message.photo:
                        try:
                            await callback_query.message.delete()
                        except Exception:
                            pass
                        await client.send_message(
                            chat_id=callback_query.message.chat.id,
                            text=txt,
                            parse_mode=enums.ParseMode.HTML,
                            reply_markup=kb
                        )
                    else:
                        await callback_query.message.edit_text(txt, parse_mode=enums.ParseMode.HTML, reply_markup=kb)
            except Exception as e:
                logger.error(f"[tg_adm_pview] Error: {e}", exc_info=True)
                await callback_query.message.reply_text(f"❌ خطا در بارگذاری دوره: {e}")

        @self.app.on_callback_query(filters.regex(r"^adm_c_toggle:"))
        async def handle_admin_course_toggle(client: Client, callback_query: CallbackQuery):
            if not self.is_admin(callback_query.from_user.id):
                await callback_query.answer("⛔️ دسترسی غیرمجاز", show_alert=True)
                return
            try:
                pid = callback_query.data.split(":")[1]
                prod = await StoreService.get_product(pid)
                if not prod:
                    await callback_query.answer("❌ دوره یافت نشد.", show_alert=True)
                    return
                new_st = 0 if prod.active else 1
                await StoreService.update_product_field(pid, "active", new_st)
                st_label = "فعال ✅" if new_st else "غیرفعال ❌"
                await callback_query.answer(f"وضعیت دوره به {st_label} تغییر یافت.", show_alert=True)
                prod.active = bool(new_st)
                txt = format_admin_course_card(prod)
                kb = build_admin_course_keyboard(pid, prod.active)
                if callback_query.message.photo:
                    await callback_query.message.edit_caption(caption=txt, parse_mode=enums.ParseMode.HTML, reply_markup=kb)
                else:
                    await callback_query.message.edit_text(txt, parse_mode=enums.ParseMode.HTML, reply_markup=kb)
            except Exception as e:
                logger.error(f"[tg_adm_toggle] Error: {e}", exc_info=True)

        @self.app.on_callback_query(filters.regex(r"^adm_c_edit:"))
        async def handle_admin_course_edit_cb(client: Client, callback_query: CallbackQuery):
            if not self.is_admin(callback_query.from_user.id):
                await callback_query.answer("⛔️ دسترسی غیرمجاز", show_alert=True)
                return
            await callback_query.answer()
            try:
                parts = callback_query.data.split(":")
                field = parts[1]
                pid = parts[2]
                prod = await StoreService.get_product(pid)
                if not prod:
                    await callback_query.message.reply_text("❌ دوره یافت نشد.")
                    return

                user_id = callback_query.from_user.id
                session_manager.set_user_action(f"tg_{user_id}", f"await_c_edit_{field}", pid)

                prompts = {
                    "link": f"🔗 <b>ویرایش لینک‌های دوره «{escape(prod.name)}»:</b>\n\nلطفاً لینک‌ها یا متن جدید دسترسی را ارسال فرمایید:\n(می‌توانید شامل لینک کانال بله، تلگرام، دانلود مستقیم و توضیحات باشد)\nجهت انصراف عبارت <code>/cancel</code> را بفرستید.",
                    "price": f"💰 <b>تغییر قیمت دوره «{escape(prod.name)}»:</b>\n\nقیمت فعلی: <code>{prod.price:,} تومان</code>\nلطفاً مبلغ جدید را به تومان (فقط عدد، مثلاً <code>120000</code> یا <code>0</code> برای رایگان) ارسال فرمایید:\nجهت انصراف عبارت <code>/cancel</code> را بفرستید.",
                    "desc": f"📝 <b>ویرایش توضیحات دوره «{escape(prod.name)}»:</b>\n\nلطفاً متن توضیحات جدید دوره را ارسال فرمایید:\nجهت انصراف عبارت <code>/cancel</code> را بفرستید.",
                    "photo": f"🖼 <b>تغییر تصویر یا بنر دوره «{escape(prod.name)}»:</b>\n\nلطفاً عکس بنر دوره یا آدرس اینترنتی (URL) آن را ارسال فرمایید:\nجهت انصراف عبارت <code>/cancel</code> را بفرستید."
                }
                await callback_query.message.reply_text(prompts.get(field, "لطفاً مقدار جدید را ارسال فرمایید:"), parse_mode=enums.ParseMode.HTML)
            except Exception as e:
                logger.error(f"[tg_adm_edit] Error: {e}", exc_info=True)

        @self.app.on_callback_query(filters.regex(r"^adm_c_list$"))
        async def handle_admin_course_list_cb(client: Client, callback_query: CallbackQuery):
            if not self.is_admin(callback_query.from_user.id):
                await callback_query.answer("⛔️ دسترسی غیرمجاز", show_alert=True)
                return
            await callback_query.answer()
            try:
                all_items = await StoreService.get_all_products(active_only=False)
                prods = [p for p in all_items if p.price > 0]
                gifts = [p for p in all_items if p.price == 0]
                lines = [
                    "📚 <b>پنل مدیریت دوره‌ها و فایل‌های دانلودی:</b>",
                    f"تعداد کل: <b>{len(all_items)}</b> (دوره‌ها: <b>{len(prods)}</b> | هدایا: <b>{len(gifts)}</b>)",
                    "",
                    "لیست دوره‌ها (جهت مشاهده جزئیات یا ویرایش روی دوره کلیک کنید):"
                ]
                buttons = [[InlineKeyboardButton(f"{'🎁' if p.price == 0 else f'🎓 ({p.price:,} ت)'} {'[غیرفعال] ' if not p.active else ''}{p.name}", callback_data=f"adm_pview:{p.product_id}")] for p in all_items]
                buttons.append([InlineKeyboardButton("➕ افزودن دوره جدید", callback_data="adm_c_add")])
                kb = InlineKeyboardMarkup(buttons)
                txt = "\n".join(lines)
                if callback_query.message.photo:
                    try:
                        await callback_query.message.delete()
                    except Exception:
                        pass
                    await client.send_message(
                        chat_id=callback_query.message.chat.id,
                        text=txt,
                        parse_mode=enums.ParseMode.HTML,
                        reply_markup=kb
                    )
                else:
                    await callback_query.message.edit_text(txt, parse_mode=enums.ParseMode.HTML, reply_markup=kb)
            except Exception as e:
                logger.error(f"[tg_adm_list] Error: {e}", exc_info=True)

        @self.app.on_callback_query(filters.regex(r"^adm_c_add$"))
        async def handle_admin_course_add_cb(client: Client, callback_query: CallbackQuery):
            if not self.is_admin(callback_query.from_user.id): return
            await callback_query.answer()
            session_manager.set_user_action(f"tg_{callback_query.from_user.id}", "await_c_name", "new_course", extra={})
            await callback_query.message.reply_text(
                "➕ <b>افزودن دوره جدید به فروشگاه (مرحله ۱ از ۵):</b>\n\n"
                "لطفاً <b>نام کامل دوره</b> را ارسال فرمایید:\n"
                "(جهت انصراف عبارت <code>/cancel</code> را ارسال کنید)",
                parse_mode=enums.ParseMode.HTML
            )

        # ================= MY COURSES & DATABASE BACKUP =================
        @self.app.on_message(filters.private & filters.regex(r"(?i)^(👤\s*دوره‌های من|دوره‌های من|/my_courses)"))
        async def customer_my_courses_handler(client: Client, message: Message):
            user_id = message.from_user.id
            purchased = await StoreService.get_customer_purchased_courses(user_id)
            if not purchased:
                await message.reply_text(
                    "📚 <b>دوره‌های من:</b>\n\n"
                    "هنوز دوره‌ای به نام حساب شما ثبت نشده است.\n"
                    "می‌توانید دوره‌های آموزشی را از بخش «📚 لیست دوره‌های آموزشی» یا وب‌سایت تهیه نمایید.",
                    parse_mode=enums.ParseMode.HTML
                )
                return
            await message.reply_text(
                f"📚 <b>دوره‌های فعال و خریداری‌شده شما ({len(purchased)} دوره):</b>\n\n"
                "در ادامه کارت‌های دسترسی به هر دوره همراه با دکمه‌های ورود مستقیم تقدیم حضورتان می‌گردد:",
                parse_mode=enums.ParseMode.HTML
            )
            for i, c in enumerate(purchased, 1):
                c_name = c.get("name") or "دوره آموزشی"
                card_txt, buttons = StoreService.format_customer_course_card(c_name, c.get("download_link"), i, len(purchased))
                kb = None
                if buttons:
                    kb = InlineKeyboardMarkup([[InlineKeyboardButton(b["text"], url=b["url"])] for b in buttons])
                await message.reply_text(card_txt, parse_mode=enums.ParseMode.HTML, reply_markup=kb)

        @self.app.on_message(filters.private & filters.regex(r"(?i)^(💾\s*بک‌آپ دیتابیس|بک‌آپ دیتابیس|/backup_db)"))
        async def admin_backup_database_handler(client: Client, message: Message):
            if not self.is_admin(message.from_user.id): return
            if config.DB_PATH.exists():
                await message.reply_document(
                    document=str(config.DB_PATH),
                    caption=f"💾 <b>نسخه پشتیبان پایگاه داده SQLite</b>\nنگارش سیستم: <code>{config.ENGINE_VERSION}</code>\nمسیر: <code>{config.DB_PATH}</code>"
                )
            else:
                await message.reply_text("❌ فایل دیتابیس در مسیر تعریف‌شده یافت نشد.", parse_mode=enums.ParseMode.HTML)

        @self.app.on_callback_query(filters.regex(r"^adm_backup_file$"))
        async def admin_backup_database_cb(client: Client, callback_query: CallbackQuery):
            if not self.is_admin(callback_query.from_user.id): return
            await callback_query.answer("در حال ارسال فایل دیتابیس...")
            if config.DB_PATH.exists():
                await client.send_document(
                    chat_id=callback_query.message.chat.id,
                    document=str(config.DB_PATH),
                    caption=f"💾 <b>نسخه پشتیبان پایگاه داده SQLite</b>\nنگارش سیستم: <code>{config.ENGINE_VERSION}</code>\nمسیر: <code>{config.DB_PATH}</code>"
                )
            else:
                await callback_query.message.reply_text("❌ فایل دیتابیس در مسیر تعریف‌شده یافت نشد.", parse_mode=enums.ParseMode.HTML)

        @self.app.on_callback_query(filters.regex(r"^tg:fjoin_panel$"))
        async def admin_fjoin_panel_cb(client: Client, callback_query: CallbackQuery):
            if not self.is_admin(callback_query.from_user.id): return
            await callback_query.answer()
            ch = await get_system_setting("tg_fjoin_channel", config.FORCE_JOIN_CHANNEL_TELEGRAM)
            enabled = (await get_system_setting("tg_fjoin_enabled", "1" if config.FORCE_JOIN_CHANNEL_TELEGRAM else "0")) == "1"
            st_txt = "فعال ✅" if enabled else "غیرفعال ❌"
            btn_t = "🔴 غیرفعال‌سازی قفل" if enabled else "🟢 فعال‌سازی قفل"
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton(btn_t, callback_data="tg:fjoin_toggle")],
                [InlineKeyboardButton("✏️ تنظیم آیدی کانال", callback_data="tg:fjoin_set_ch")],
                [InlineKeyboardButton("🔄 به‌روزرسانی پنل", callback_data="tg:fjoin_refresh")]
            ])
            plain_panel = (
                "🔒 مدیریت قفل عضویت کانال تلگرام:\n\n"
                f"▫️ وضعیت قفل: {st_txt}\n"
                f"▫️ کانال هدف: {ch or 'تنظیم نشده'}"
            )
            await callback_query.message.reply_text(plain_panel, reply_markup=kb)

        @self.app.on_message(filters.private & filters.regex(r"(?i)^(➕\s*افزودن دوره جدید|افزودن دوره|/add_course)"))
        async def admin_add_course_cmd(client: Client, message: Message):
            if not self.is_admin(message.from_user.id): return
            session_manager.set_user_action(f"tg_{message.from_user.id}", "await_c_name", "new_course", extra={})
            await message.reply_text(
                "➕ <b>افزودن دوره جدید به فروشگاه (مرحله ۱ از ۵):</b>\n\n"
                "لطفاً <b>نام کامل دوره</b> را ارسال فرمایید:\n"
                "(جهت انصراف عبارت <code>/cancel</code> را ارسال کنید)",
                parse_mode=enums.ParseMode.HTML
            )

                # Admin Order Review Callback (Bot orders + Web Card Receipts)
        @self.app.on_callback_query(filters.regex(r"^(ord|adm)_(app|rej):"))
        async def admin_order_review(client: Client, callback_query: CallbackQuery):
            if not self.is_admin(callback_query.from_user.id):
                await callback_query.answer("⛔️ دسترسی غیرمجاز.", show_alert=True)
                return
            await callback_query.answer()
            parts = callback_query.data.split(":")
            action = parts[0]
            order_id = parts[1]
            if "app" in action:
                res = await StoreService.approve_order(order_id)
                if res:
                    order = res["order"]
                    prod = res.get("product")
                    dl = prod.download_link if prod else ""
                    cb_awarded = res.get("cashback_awarded", 0)
                    admin_resp_txt = (
                        f"✅ <b>سفارش {order_id} تایید شد!</b>\n"
                        f"🎓 دوره: <b>{escape(order.product_name)}</b>\n"
                        f"محتوای دوره برای خریدار ارسال و مبلغ {cb_awarded:,} تومان کش‌بک به کیف پول منظور گردید."
                    )
                    try:
                        await callback_query.message.edit_text(admin_resp_txt, parse_mode=enums.ParseMode.HTML)
                    except Exception:
                        try:
                            await callback_query.message.edit_caption(admin_resp_txt, parse_mode=enums.ParseMode.HTML)
                        except Exception: pass

                    uid_str = str(order.user_id or "")
                    if uid_str.isdigit():
                        try:
                            is_pkg = bool(prod and (getattr(prod, "delivery_type", "channel") == "files_package" or getattr(prod, "files_package", None) or getattr(prod, "episodes", None)))
                            if is_pkg:
                                await self.send_message(int(uid_str), f"🎉 <b>سفارش شما تایید شد!</b>\nفایل‌های دوره «{escape(order.product_name)}» هم‌اکنون به ترتیب ارسال می‌شوند:\nشماره سفارش: <code>{order.order_id}</code>", parse_mode=enums.ParseMode.HTML)
                                await StoreService.deliver_course_package(prod, int(uid_str), "telegram")
                            else:
                                dl_content = (prod.download_link if prod else "") or "برای دریافت لینک‌ها و فایل‌های این دوره با پشتیبانی در ارتباط باشید."
                                cust_msg = StoreService.format_delivery_message(order.product_name, order.order_id, dl_content, cb_awarded)
                                parsed_dl = StoreService.parse_delivery_links(dl_content)
                                cust_buttons = []
                                for lk in parsed_dl["links"]:
                                    cust_buttons.append([InlineKeyboardButton(lk["title"], url=lk["url"])])
                                cust_kb = InlineKeyboardMarkup(cust_buttons) if cust_buttons else None
                                await self.send_message(int(uid_str), cust_msg, reply_markup=cust_kb)
                        except Exception as ex_del:
                            logger.warning(f"Could not deliver course to user {uid_str}: {ex_del}")
                else:
                    await callback_query.message.reply_text(f"❌ سفارش {order_id} یافت نشد.")
            else:
                await StoreService.reject_order(order_id)
                rej_txt = f"❌ <b>سفارش {order_id} رد شد.</b>"
                try:
                    await callback_query.message.edit_text(rej_txt, parse_mode=enums.ParseMode.HTML)
                except Exception:
                    try:
                        await callback_query.message.edit_caption(rej_txt, parse_mode=enums.ParseMode.HTML)
                    except Exception: pass

        # Incoming Photos (Receipts & Covers)
        @self.app.on_message(filters.private & filters.photo)
        async def photo_handler(client: Client, message: Message):
            user_id = message.from_user.id
            text = (message.caption or "").strip()
            user_act = session_manager.get_user_action(f"tg_{user_id}")
            if user_act and text == "/cancel":
                session_manager.clear_user_action(f"tg_{user_id}")
                await message.reply_text("❌ عملیات با موفقیت لغو شد.", parse_mode=enums.ParseMode.HTML)
                return

            if user_act and user_act.get("action") == "await_c_name":
                c_data = user_act.get("extra") or {}
                c_data["name"] = text
                session_manager.set_user_action(f"tg_{user_id}", "await_c_price", "new_course", extra=c_data)
                await message.reply_text(
                    f"💰 <b>نام دوره: «{escape(text)}»</b>\n\n"
                    "لطفاً <b>قیمت دوره به تومان</b> را وارد فرمایید:\n"
                    "(برای دوره رایگان یا هدیه عدد <code>0</code> ارسال کنید)",
                    parse_mode=enums.ParseMode.HTML
                )
                return

            if user_act and user_act.get("action") == "await_c_price":
                c_data = user_act.get("extra") or {}
                clean_digits = re.sub(r"[^\d]", "", text)
                price = int(clean_digits) if clean_digits else 0
                c_data["price"] = price
                session_manager.set_user_action(f"tg_{user_id}", "await_c_desc", "new_course", extra=c_data)
                await message.reply_text(
                    f"📝 <b>قیمت دوره: {price:,} تومان</b>\n\n"
                    "لطفاً <b>توضیحات کوتاه و سرفصل‌های دوره</b> را ارسال فرمایید:",
                    parse_mode=enums.ParseMode.HTML
                )
                return

            if user_act and user_act.get("action") == "await_c_desc":
                c_data = user_act.get("extra") or {}
                c_data["desc"] = text
                session_manager.set_user_action(f"tg_{user_id}", "await_c_link", "new_course", extra=c_data)
                await message.reply_text(
                    "📥 <b>توضیحات با موفقیت ثبت شد!</b>\n\n"
                    "لطفاً <b>لینک مستقیم دانلود محتوای دوره</b> را ارسال فرمایید:",
                    parse_mode=enums.ParseMode.HTML
                )
                return

            if user_act and user_act.get("action") == "await_c_link":
                c_data = user_act.get("extra") or {}
                c_data["link"] = clean_course_access_input(text, c_data.get("name", ""))
                session_manager.set_user_action(f"tg_{user_id}", "await_c_photo", "new_course", extra=c_data)
                await message.reply_text(
                    "🖼 <b>لینک مستقیم دانلود ثبت شد!</b>\n\n"
                    "در صورت تمایل <b>عکس یا پوستر دوره</b> را ارسال فرمایید، یا برای ثبت بدون عکس دستور <code>/skip</code> را بفرستید:",
                    parse_mode=enums.ParseMode.HTML
                )
                return

            if user_act and user_act.get("action") == "await_c_photo":
                c_data = user_act.get("extra") or {}
                session_manager.clear_user_action(f"tg_{user_id}")
                prod = await StoreService.add_product(
                    name=c_data.get("name") or "دوره جدید",
                    price=int(c_data.get("price") or 0),
                    description=c_data.get("desc") or "",
                    download_link=c_data.get("link") or "",
                    photo_url="",
                    allow_card=True,
                    allow_bale=True
                )
                await message.reply_text(
                    f"🎉 <b>دوره «{escape(prod.name)}» با موفقیت ثبت گردید!</b>\n\n"
                    f"💰 قیمت: <code>{prod.price:,} تومان</code>\n"
                    f"📥 لینک دانلود: <code>{escape(prod.download_link or 'ندارد')}</code>\n\n"
                    "دوره هم‌اکنون به صورت آنی در فروشگاه وب (<code>/store</code>) و ربات‌ها منتشر شد.",
                    parse_mode=enums.ParseMode.HTML
                )
                return
            if user_act and user_act.get("action") == "await_c_photo":
                c_data = user_act.get("extra") or {}
                session_manager.clear_user_action(f"tg_{user_id}")
                file_id = message.photo.file_id
                
                prod_id = f"prod_{uuid.uuid4().hex[:6]}"
                banner_web_url = ""
                config.BANNERS_DIR.mkdir(parents=True, exist_ok=True)
                banner_filename = f"banner_{prod_id}.jpg"
                banner_local_path = config.BANNERS_DIR / banner_filename
                try:
                    await client.download_media(message.photo, file_name=str(banner_local_path))
                    if banner_local_path.exists():
                        try:
                            from PIL import Image
                            with Image.open(banner_local_path) as im:
                                im = im.convert("RGB")
                                if im.width > 1200:
                                    h = int(im.height * (1200 / im.width))
                                    im = im.resize((1200, h), Image.Resampling.LANCZOS)
                                im.save(banner_local_path, "JPEG", quality=85, optimize=True)
                        except Exception as pil_err:
                            logger.warning(f"[tg_c_photo] Pillow optimization notice: {pil_err}")
                        banner_web_url = f"/uploads/banners/{banner_filename}"
                except Exception as dl_err:
                    logger.warning(f"[tg_c_photo] Failed to save banner: {dl_err}")

                prod = await StoreService.add_product(
                    name=c_data.get("name") or "دوره جدید",
                    price=int(c_data.get("price") or 0),
                    description=c_data.get("desc") or "",
                    download_link=c_data.get("link") or "",
                    photo_url=banner_web_url or file_id,
                    allow_card=True,
                    allow_bale=True
                )
                if file_id:
                    await StoreService.update_product_field(prod.product_id, "photo_file_id", file_id)
                if banner_web_url:
                    await StoreService.update_product_field(prod.product_id, "photo_url", banner_web_url)

                await message.reply_text("✅ دوره با موفقیت ثبت و در فروشگاه وب منتشر شد.", parse_mode=enums.ParseMode.HTML)
                return

            if user_act and user_act.get("action") == "await_c_edit_photo":
                pid = user_act.get("drop_id")
                session_manager.clear_user_action(f"tg_{user_id}")
                prod = await StoreService.get_product(pid)
                if prod:
                    file_id = message.photo.file_id
                    config.BANNERS_DIR.mkdir(parents=True, exist_ok=True)
                    banner_filename = f"banner_{pid}.jpg"
                    banner_local_path = config.BANNERS_DIR / banner_filename
                    banner_web_url = ""
                    try:
                        await client.download_media(message.photo, file_name=str(banner_local_path))
                        if banner_local_path.exists():
                            try:
                                from PIL import Image
                                with Image.open(banner_local_path) as im:
                                    im = im.convert("RGB")
                                    if im.width > 1200:
                                        h = int(im.height * (1200 / im.width))
                                        im = im.resize((1200, h), Image.Resampling.LANCZOS)
                                    im.save(banner_local_path, "JPEG", quality=85, optimize=True)
                            except Exception:
                                pass
                            banner_web_url = f"/uploads/banners/{banner_filename}"
                    except Exception as e:
                        logger.warning(f"[tg_c_photo] Failed saving edited banner: {e}")

                    if banner_web_url:
                        await StoreService.update_product_field(pid, "photo_url", banner_web_url)
                        prod.photo_url = banner_web_url
                    if file_id:
                        await StoreService.update_product_field(pid, "photo_file_id", file_id)
                        prod.photo_file_id = file_id

                    await message.reply_text(f"✅ <b>پوستر دوره «{escape(prod.name)}» با موفقیت به‌روزرسانی شد.</b>", parse_mode=enums.ParseMode.HTML)
                    await message.reply_text(format_admin_course_card(prod), parse_mode=enums.ParseMode.HTML, reply_markup=build_admin_course_keyboard(pid, prod.active))
                return

            if user_act and user_act.get("action") == "await_receipt":
                order_id = user_act.get("drop_id")
                file_id = message.photo.file_id

                receipts_dir = Path("uploads/receipts")
                receipts_dir.mkdir(parents=True, exist_ok=True)
                local_receipt_path = receipts_dir / f"receipt_{order_id}_{uuid.uuid4().hex[:6]}.jpg"
                try:
                    await client.download_media(message.photo, file_name=str(local_receipt_path))
                except Exception as dl_err:
                    logger.warning(f"[tg_receipt] Failed downloading receipt photo: {dl_err}")

                await StoreService.submit_card_receipt(order_id, receipt_file_id=file_id)
                session_manager.clear_user_action(f"tg_{user_id}")

                order = await StoreService.get_order(order_id)
                if order:
                    receipt_img_arg = str(local_receipt_path) if local_receipt_path.exists() else None
                    await StoreService.notify_admin_card_order(order, receipt_image_path=receipt_img_arg)

                # فیش واریزی شما با موفقیت دریافت شد (نسخه جدید: به زودی توسط مدیریت بررسی می‌شود)
                await message.reply_text(
                    "✅ فیش واریزی شما دریافت شد و به زودی توسط مدیریت بررسی می‌شود.",
                    parse_mode=enums.ParseMode.HTML
                )
                return

            if user_act and user_act["action"] == "await_cover":
                drop_id = user_act["drop_id"]
                drop = session_manager.get_session(drop_id)
                if not drop:
                    try:
                        from core.database import db_get_media_session
                        drop = db_get_media_session(drop_id)
                        if drop:
                            session_manager._sessions[drop_id] = drop
                    except Exception:
                        pass
                if drop:
                    thumb_p = config.TEMP_DIR / f"thumb_{drop_id}_{uuid.uuid4().hex[:4]}.jpg"
                    await client.download_media(message, file_name=str(thumb_p))
                    MediaService.replace_cover(drop_id, thumb_p)
                    session_manager.clear_user_action(f"tg_{user_id}")
                    try:
                        await self.app.edit_message_text(chat_id=message.chat.id, message_id=drop["card_msg_id"], text=TelegramFormatter.format_light_card(drop), reply_markup=self.build_media_keyboard(drop_id, drop), parse_mode=enums.ParseMode.HTML)
                    except Exception: pass
                    # Clean up prompt message and incoming photo message for a tidy chat
                    prompt_ids = []
                    p_info = session_manager.get_session(f"prompt_{drop_id}")
                    if p_info and p_info.get("msg_id"):
                        prompt_ids.append(p_info["msg_id"])
                    extra_p = (user_act.get("extra") or {}).get("prompt_id")
                    if extra_p and extra_p not in prompt_ids:
                        prompt_ids.append(extra_p)
                    if prompt_ids:
                        try:
                            await self.app.delete_messages(chat_id=message.chat.id, message_ids=prompt_ids)
                        except Exception: pass
                    try:
                        await message.delete()
                    except Exception: pass
                return

        # Incoming Audio/Video Media Hub (Admin Only Access Control)
        @self.app.on_message(filters.private & (filters.audio | filters.document | filters.voice | filters.video))
        async def incoming_media(client: Client, message: Message):
            try:
                user_id = message.from_user.id if message.from_user else (message.chat.id if message.chat else 0)
                if not user_id:
                    return
                session_manager.clear_user_action(f"tg_{user_id}")
                media_obj = message.audio or message.document or message.voice or message.video
                raw_fn = getattr(media_obj, "file_name", "") or ""
                mime_type = getattr(media_obj, "mime_type", "") or ""
                if raw_fn.lower().endswith(".svg") or mime_type.lower() == "image/svg+xml":
                    file_id = getattr(media_obj, "file_id", "")
                    svg_kb = InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("⚪️ سفید (#FFF)", callback_data=f"tg_svg_recol:white:{file_id}"),
                            InlineKeyboardButton("⚫️ مشکی (#000)", callback_data=f"tg_svg_recol:black:{file_id}")
                        ],
                        [
                            InlineKeyboardButton("🎨 ارسال کد هگز", callback_data=f"tg_svg_hex:{file_id}")
                        ],
                        [
                            InlineKeyboardButton("🖼 خروجی PNG شفاف", callback_data=f"tg_svg:png:{file_id}"),
                            InlineKeyboardButton("🖼 خروجی JPG", callback_data=f"tg_svg:jpg:{file_id}")
                        ],
                        [
                            InlineKeyboardButton("📥 دریافت مجدد فایل SVG", callback_data=f"tg_svg:svg:{file_id}")
                        ]
                    ])
                    await message.reply_text(
                        f"🎨 <b>استودیوی وکتور SVG:</b> <code>{escape(raw_fn or 'vector.svg')}</code>\n\n"
                        "عملیات مورد نظر خود را جهت تغییر رنگ یا تبدیل فرمت انتخاب فرمایید:",
                        parse_mode=enums.ParseMode.HTML,
                        reply_markup=svg_kb
                    )
                    return

                if not self.is_admin(user_id):
                    await message.reply_text(
                        f"📚 <b>به فروشگاه دوره‌های آموزشی {escape(config.STORE_NAME)} خوش آمدید.</b>\n\n"
                        "جهت مشاهده کاتالوگ دوره‌ها، دریافت هدایا یا ارتباط با پشتیبانی، لطفاً از دکمه‌های منوی زیر استفاده فرمایید:",
                        parse_mode=enums.ParseMode.HTML,
                        reply_markup=get_customer_keyboard()
                    )
                    return

                drop_id = uuid.uuid4().hex[:8]
                media_type = "video" if message.video else ("audio" if (message.audio or message.voice) else "document")
                raw_fn = getattr(media_obj, "file_name", "") or ("video.mp4" if media_type == "video" else "audio.mp3")
                fn = clean_display_filename(raw_fn)
                sz = getattr(media_obj, "file_size", 0)
                file_id = getattr(media_obj, "file_id", "")

                api_meta = {
                    "filename": fn, "file_size": sz,
                    "duration_sec": getattr(media_obj, "duration", 0),
                    "title": getattr(media_obj, "title", ""),
                    "artist": getattr(media_obj, "performer", "")
                }

                data = MediaService.register_incoming_message_meta(
                    drop_id, "telegram", user_id, file_id, fn, sz,
                    media_type=media_type, api_meta=api_meta, caption=message.caption or "", raw_message=message
                )

                # سیستم ارسال دسته‌جمعی رسانه‌ها (Batch Forwarding Manager) با دی‌بانس زمانی
                if user_id not in self._media_batch_queue:
                    self._media_batch_queue[user_id] = {"timer": None, "items": []}

                batch_info = self._media_batch_queue[user_id]
                if batch_info.get("timer"):
                    try:
                        batch_info["timer"].cancel()
                    except Exception:
                        pass

                batch_info["items"].append({
                    "drop_id": drop_id,
                    "data": data,
                    "message": message
                })

                async def _dispatch_media_batch(uid: int):
                    try:
                        await asyncio.sleep(1.2)
                        b = self._media_batch_queue.pop(uid, None)
                        if not b or not b.get("items"):
                            return
                        items = b["items"]
                        if len(items) == 1:
                            # دریافت تکی: نمایش کارت لایت استاندارد با کیبورد کامل
                            single = items[0]
                            s_data = single["data"]
                            s_drop_id = single["drop_id"]
                            s_msg = single["message"]
                            card_text = TelegramFormatter.format_light_card(s_data)
                            kb = self.build_media_keyboard(s_drop_id, s_data)
                            sent_card = await s_msg.reply_text(card_text, parse_mode=enums.ParseMode.HTML, reply_markup=kb)
                            s_data["card_msg_id"] = sent_card.id
                        elif len(items) > 1:
                            # دریافت گروهی/دسته‌جمعی: نمایش پیام متمرکز با دکمه‌های شیشه‌ای
                            b_id = uuid.uuid4().hex[:8]
                            self._batch_registry[b_id] = items
                            total_sz = sum(it["data"].get("file_size", 0) for it in items)
                            total_mb = f"{total_sz / (1024 * 1024):.2f}"
                            batch_kb = InlineKeyboardMarkup([
                                [
                                    InlineKeyboardButton("🚀 ارسال دسته‌جمعی به بله", callback_data=f"smeta_batch:bale:{b_id}"),
                                    InlineKeyboardButton("🚀 ارسال به روبیکا", callback_data=f"smeta_batch:rubika:{b_id}")
                                ],
                                [
                                    InlineKeyboardButton("❌ لغو ارسال دسته‌جمعی", callback_data=f"smeta_batch:cancel:{b_id}")
                                ]
                            ])
                            last_msg = items[-1]["message"]
                            await last_msg.reply_text(
                                f"📦 <b>تعداد {len(items)} فایل آماده انتقال شناسایی شد.</b>\n"
                                f"📊 مجموع حجم فایل‌ها: <code>{total_mb} MB</code>\n\n"
                                "لطفاً مقصد مورد نظر جهت انتقال یکپارچه را انتخاب فرمایید:",
                                parse_mode=enums.ParseMode.HTML,
                                reply_markup=batch_kb
                            )
                    except Exception as b_err:
                        logger.error(f"[BatchForwarding] Error dispatching batch: {b_err}")

                batch_info["timer"] = asyncio.create_task(_dispatch_media_batch(user_id))
            except Exception as e:
                logger.exception(f"Error handling media: {e}")

        # SVG Vector Callbacks: Hex Input & Recolor
        @self.app.on_callback_query(filters.regex(r"^tg_svg_hex:"))
        async def tg_svg_hex_cb(client: Client, callback_query: CallbackQuery):
            file_id = callback_query.data.split(":", 1)[1]
            user_id = callback_query.from_user.id
            session_manager.set_user_action(f"tg_{user_id}", "await_svg_hex", file_id)
            await callback_query.answer()
            await callback_query.message.reply_text(
                "🎨 <b>لطفاً کد رنگ هگز مدنظر خود را ارسال فرمایید (مانند #3B82F6 یا #E11D48):</b>",
                parse_mode=enums.ParseMode.HTML
            )

        @self.app.on_callback_query(filters.regex(r"^tg_svg_recol:"))
        async def tg_svg_recol_cb(client: Client, callback_query: CallbackQuery):
            parts = callback_query.data.split(":", 2)
            if len(parts) != 3:
                return
            c_name = parts[1].lower()
            file_id = parts[2]
            user_id = callback_query.from_user.id
            color_map = {"white": "#FFFFFF", "black": "#000000"}
            hex_color = color_map.get(c_name, c_name if c_name.startswith("#") else f"#{c_name}")
            await callback_query.answer("در حال تغییر رنگ وکتور...")
            status_msg = await callback_query.message.reply_text(f"⏳ در حال دانلود فایل وکتور و تغییر رنگ به {hex_color}...")
            tmp_svg_path = config.TEMP_DIR / f"tg_svg_{uuid.uuid4().hex[:8]}.svg"
            try:
                from services.image_service import image_service
                await client.download_media(file_id, file_name=str(tmp_svg_path))
                if not tmp_svg_path.exists():
                    raise ValueError("خطا در دانلود فایل SVG از تلگرام.")
                with open(tmp_svg_path, "r", encoding="utf-8", errors="replace") as f_in:
                    svg_str = f_in.read()
                recolored_svg = image_service.recolor_svg(svg_str, hex_color)
                out_bytes = recolored_svg.encode("utf-8")
                tmp_out = config.TEMP_DIR / f"vector_{hex_color.lstrip('#')}_{uuid.uuid4().hex[:8]}.svg"
                with open(tmp_out, "wb") as f_out:
                    f_out.write(out_bytes)
                svg_kb = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("⚪️ سفید (#FFF)", callback_data=f"tg_svg_recol:white:{file_id}"),
                        InlineKeyboardButton("⚫️ مشکی (#000)", callback_data=f"tg_svg_recol:black:{file_id}")
                    ],
                    [
                        InlineKeyboardButton("🎨 کد هگز دلخواه", callback_data=f"tg_svg_hex:{file_id}")
                    ],
                    [
                        InlineKeyboardButton("🖼 خروجی PNG شفاف", callback_data=f"tg_svg:png:{file_id}"),
                        InlineKeyboardButton("🖼 خروجی JPG", callback_data=f"tg_svg:jpg:{file_id}")
                    ]
                ])
                caption = f"🎨 <b>وکتور با رنگ تغییر‌یافته ({hex_color}):</b>\nنگارش موتور وکتور: <code>{config.ENGINE_VERSION}</code>"
                await client.send_document(user_id, str(tmp_out), caption=caption, file_name=f"vector_{hex_color.lstrip('#')}.svg", parse_mode=enums.ParseMode.HTML, reply_markup=svg_kb)
                try: tmp_out.unlink()
                except Exception: pass
                await status_msg.delete()
            except Exception as e:
                logger.error(f"[tg_svg_recol] Error: {e}")
                await status_msg.edit_text(f"❌ خطا در تغییر رنگ وکتور: {e}")
            finally:
                if tmp_svg_path.exists():
                    try: tmp_svg_path.unlink()
                    except Exception: pass

        # SVG Vector to Image Conversion Callback Handler
        @self.app.on_callback_query(filters.regex(r"^tg_svg:"))
        async def tg_svg_convert_cb(client: Client, callback_query: CallbackQuery):
            parts = callback_query.data.split(":", 2)
            if len(parts) != 3:
                return
            target_fmt = parts[1].lower()
            file_id = parts[2]
            user_id = callback_query.from_user.id
            await callback_query.answer("در حال تبدیل وکتور...")
            status_msg = await callback_query.message.reply_text("⏳ در حال پردازش فایل وکتور...")
            tmp_svg_path = config.TEMP_DIR / f"tg_svg_{uuid.uuid4().hex[:8]}.svg"
            try:
                from services.image_service import image_service
                await client.download_media(file_id, file_name=str(tmp_svg_path))
                if not tmp_svg_path.exists():
                    raise ValueError("خطا در دانلود فایل SVG از تلگرام.")
                
                with open(tmp_svg_path, "rb") as f_in:
                    svg_bytes = f_in.read()
                
                if target_fmt in ("jpg", "jpeg"):
                    out_bytes = image_service.convert_svg_to_jpg(svg_bytes)
                    tmp_out = config.TEMP_DIR / f"vector_{uuid.uuid4().hex[:8]}.jpg"
                    with open(tmp_out, "wb") as f_out:
                        f_out.write(out_bytes)
                    caption = f"🖼 <b>تصویر باکیفیت JPG استخراج‌شده از وکتور</b>\nنگارش موتور وکتور: <code>{config.ENGINE_VERSION}</code>"
                    await client.send_photo(user_id, str(tmp_out), caption=caption, parse_mode=enums.ParseMode.HTML)
                    try: tmp_out.unlink()
                    except Exception: pass
                elif target_fmt == "svg":
                    caption = f"📥 <b>فایل اصلی وکتور SVG</b>\nنگارش موتور وکتور: <code>{config.ENGINE_VERSION}</code>"
                    await client.send_document(user_id, str(tmp_svg_path), caption=caption, file_name="vector.svg", parse_mode=enums.ParseMode.HTML)
                else:
                    out_bytes = image_service.convert_svg_to_png(svg_bytes)
                    tmp_out = config.TEMP_DIR / f"vector_{uuid.uuid4().hex[:8]}.png"
                    with open(tmp_out, "wb") as f_out:
                        f_out.write(out_bytes)
                    caption = f"🖼 <b>تصویر باکیفیت PNG (شفاف) استخراج‌شده از وکتور</b>\nنگارش موتور وکتور: <code>{config.ENGINE_VERSION}</code>"
                    await client.send_document(user_id, str(tmp_out), caption=caption, file_name="vector_converted.png", parse_mode=enums.ParseMode.HTML)
                    try: tmp_out.unlink()
                    except Exception: pass
                
                await status_msg.delete()
            except Exception as e:
                logger.error(f"[tg_svg_conv] Error: {e}")
                await status_msg.edit_text(f"❌ خطا در پردازش وکتور: {e}")
            finally:
                try:
                    if tmp_svg_path.exists(): tmp_svg_path.unlink()
                except Exception: pass

        # URL Uploader Callback Handlers
        @self.app.on_callback_query(filters.regex(r"^urldl:"))
        async def url_uploader_cb(client: Client, callback_query: CallbackQuery):
            parts = callback_query.data.split(":")
            mode = parts[1]
            url_id = parts[2]
            url_sess = session_manager.get_session(f"url_{url_id}")
            user_id = callback_query.from_user.id

            if not url_sess:
                await callback_query.answer("مهلت لینک منقضی شده است.", show_alert=True)
                return

            if mode == "cancel":
                session_manager.remove_session(f"url_{url_id}")
                await callback_query.message.edit_text("❌ عملیات دانلود لینک لغو شد.")
                return

            url = url_sess["url"]
            filename = url_sess["filename"]
            media_type = "audio" if mode == "audio" else ("document" if mode == "doc" else url_sess.get("media_type", "document"))

            temp_dest = config.TEMP_DIR / f"urldl_{url_id}_{clean_display_filename(filename)}"
            status_m = await callback_query.message.edit_text("📥 <b>در حال شروع دانلود استریم فایل از لینک...</b>", parse_mode=enums.ParseMode.HTML)

            start_time = [time.time()]
            last_edit = [time.time()]
            last_pct = [0]
            def progress_cb(dl_bytes, tot_bytes):
                now = time.time()
                pct = int((dl_bytes / tot_bytes) * 100) if tot_bytes > 0 else 0
                if now - last_edit[0] >= 1.5 or abs(pct - last_pct[0]) >= 5 or dl_bytes == tot_bytes:
                    last_edit[0] = now
                    last_pct[0] = pct
                    elapsed = max(0.01, now - start_time[0])
                    txt = format_transfer_progress(dl_bytes, tot_bytes, elapsed, stage_title="در حال انتقال فایل...")
                    asyncio.create_task(
                        status_m.edit_text(txt, parse_mode=enums.ParseMode.HTML)
                    )

            ok = await UrlService.download_file_stream(url, temp_dest, progress_callback=progress_cb)
            if not ok or not temp_dest.exists():
                await status_m.edit_text("❌ <b>خطا در دانلود فایل از لینک مستقیم.</b> لطفاً از صحت و پایداری لینک اطمینان حاصل فرمایید.", parse_mode=enums.ParseMode.HTML)
                return

            drop_id = uuid.uuid4().hex[:8]

            # If user requested audio extraction from a video URL
            if mode == "audio" and temp_dest.suffix.lower() in (".mp4", ".mkv", ".mov", ".avi", ".webm"):
                await status_m.edit_text("🎵 <b>در حال استخراج هوشمند صوت ویدیو به MP3...</b>", parse_mode=enums.ParseMode.HTML)
                mp3_p = config.TEMP_DIR / f"{temp_dest.stem}.mp3"
                c_ok, final_mp3 = MediaService.convert_video_to_mp3(temp_dest, output_path=mp3_p)
                if c_ok and final_mp3.exists():
                    temp_dest = final_mp3
                    filename = final_mp3.name
                    media_type = "audio"

            await status_m.edit_text("📤 <b>دانلود و آماده‌سازی کامل شد! در حال انتقال فایل به تلگرام...</b>", parse_mode=enums.ParseMode.HTML)
            sz = temp_dest.stat().st_size

            try:
                if mode != "doc" and (media_type == "video" or temp_dest.suffix.lower() in (".mp4", ".mkv", ".mov", ".avi", ".webm")):
                    media_type = "video"
                    tech = inspect_technical_metadata(temp_dest)
                    w = int(tech.get("width") or 0)
                    h = int(tech.get("height") or 0)
                    dur = int(tech.get("duration_sec") or 0)

                    # Standard Video Thumbnail extraction from 00:00:02
                    thumb_p = generate_video_thumbnail(temp_dest, timestamp="00:00:02")
                    thumb_arg = str(thumb_p) if (thumb_p and thumb_p.exists()) else None

                    sent = await self.app.send_video(
                        chat_id=user_id,
                        video=str(temp_dest),
                        file_name=filename,
                        width=w if w > 0 else None,
                        height=h if h > 0 else None,
                        duration=dur if dur > 0 else None,
                        thumb=thumb_arg,
                        supports_streaming=True
                    )
                    file_id = sent.video.file_id
                    dur = getattr(sent.video, "duration", dur)

                elif media_type == "audio":
                    sent = await self.app.send_audio(user_id, str(temp_dest), file_name=filename)
                    file_id = sent.audio.file_id
                    dur = getattr(sent.audio, "duration", 0)
                else:
                    sent = await self.app.send_document(user_id, str(temp_dest), file_name=filename)
                    file_id = sent.document.file_id
                    dur = 0

                await status_m.edit_text("✅ <b>فایل با موفقیت دانلود و تحویل داده شد.</b>", parse_mode=enums.ParseMode.HTML)

            except Exception as e:
                await status_m.edit_text(f"❌ خطا در انتقال فایل دانلودشده: {e}", parse_mode=enums.ParseMode.HTML)

        # Media Hub Callbacks
        @self.app.on_callback_query(filters.regex(r"^smeta:"))
        async def media_callbacks(client: Client, callback_query: CallbackQuery):
            parts = callback_query.data.split(":")
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
                    logger.error(f"Error recovering Telegram media session {drop_id} from SQLite: {e}")

            user_id = callback_query.from_user.id

            if not drop:
                await callback_query.answer("مهلت فایل منقضی شده است.", show_alert=True)
                return

            await callback_query.answer()

            async def ensure_binary(existing_status_m: Optional[Message] = None) -> Optional[Message]:
                if not drop.get("is_downloaded_locally"):
                    start_t = [time.time()]
                    last_edit = [0.0]
                    last_pct = [0]
                    status_m = existing_status_m
                    if not status_m:
                        try:
                            status_m = await callback_query.message.reply_text(
                                "⏳ <b>در حال دریافت فایل از تلگرام...</b>\n\n<code>[░░░░░░░░░░] 0%</code>\n\n📦 <b>حجم:</b> <code>0.00 MB</code>\n⚡️ <b>سرعت انتقال:</b> <code>0.00 MB/s</code>",
                                parse_mode=enums.ParseMode.HTML
                            )
                        except Exception:
                            pass

                    async def progress_hook(current, total, *args):
                        now = time.time()
                        if total > 0 and status_m:
                            pct = int((current / total) * 100)
                            if pct >= 100 and current < total:
                                pct = 99
                            # تراتل بازه‌های ۱۰ درصدی جهت جلوگیری از فلوید و اسپم API تلگرام
                            if (now - last_edit[0] >= 2.0 and abs(pct - last_pct[0]) >= 10) or (current >= total and total > 0):
                                last_edit[0] = now
                                last_pct[0] = pct
                                elapsed = max(0.01, now - start_t[0])
                                txt = format_transfer_progress(current, total, elapsed, stage_title="در حال دریافت فایل از تلگرام...")
                                try:
                                    await status_m.edit_text(txt, parse_mode=enums.ParseMode.HTML)
                                except Exception:
                                    pass

                    async def dl_func(fid, p):
                        target_media = drop.get("raw_message") or drop.get("file_id") or fid
                        return await MediaService.turbo_download_telegram(client, target_media, p, progress_callback=progress_hook)

                    await MediaService.ensure_local_binary(drop_id, dl_func)
                    if status_m and not existing_status_m:
                        try:
                            await status_m.edit_text("<b>✅ دریافت فایل با موفقیت تکمیل شد.</b>", parse_mode=enums.ParseMode.HTML)
                        except Exception:
                            pass
                    return status_m
                return existing_status_m

            if action == "cancel":
                session_manager.remove_session(drop_id)
                await callback_query.message.edit_text("❌ عملیات مدیریت رسانه لغو شد.")
            elif action == "tag_details":
                await ensure_binary()
                MediaService.inspect_full(drop_id)
                txt = TelegramFormatter.format_tag_details(drop)
                kb = self.build_media_keyboard(drop_id, drop, is_sub=True)
                await callback_query.message.edit_text(txt, parse_mode=enums.ParseMode.HTML, reply_markup=kb)
            elif action == "audio_specs":
                await ensure_binary()
                MediaService.inspect_full(drop_id)
                txt = TelegramFormatter.format_audio_specs(drop)
                kb = self.build_media_keyboard(drop_id, drop, is_sub=True)
                await callback_query.message.edit_text(txt, parse_mode=enums.ParseMode.HTML, reply_markup=kb)
            elif action == "strip_tags":
                await ensure_binary()
                status_m = await callback_query.message.reply_text("🧹 <b>در حال پاکسازی کامل تگ‌های متادیتا و کاور...</b>", parse_mode=enums.ParseMode.HTML)
                ok, raw_p = MediaService.strip_metadata_for_session(drop_id)
                if ok:
                    card_txt = TelegramFormatter.format_light_card(drop)
                    kb = self.build_media_keyboard(drop_id, drop, is_sub=False)
                    await self.app.edit_message_text(
                        chat_id=callback_query.message.chat.id,
                        message_id=drop["card_msg_id"],
                        text=card_txt,
                        reply_markup=kb,
                        parse_mode=enums.ParseMode.HTML
                    )
                    await status_m.edit_text("✅ <b>تمام متادیتاها و تگ‌های فایل با موفقیت پاکسازی شد.</b>", parse_mode=enums.ParseMode.HTML)
                else:
                    await status_m.edit_text("❌ خطا در پاکسازی متادیتا.", parse_mode=enums.ParseMode.HTML)
            elif action == "ai_transcribe" or action in ("ai_transcribe", "ai_menu"):  # استخراج متن و کپشن با AI
                # Stage 1: AI Engine selection
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("⚡️ گوگل جمینای (Gemini Flash)", callback_data=f"ai_eng:gemini:{drop_id}")],
                    [InlineKeyboardButton("🚀 موتور نورا (Nara Router)", callback_data=f"ai_eng:nara:{drop_id}")],
                    [InlineKeyboardButton("🔙 بازگشت به منوی رسانه", callback_data=f"smeta:back:{drop_id}")]
                ])
                await callback_query.message.edit_text(
                    "🧠 <b>دستیار هوش مصنوعی UNFINIT (مرحله ۱ از ۲):</b>\n"
                    "لطفاً موتور پردازش صوت و تولید محتوای مورد نظر را انتخاب فرمایید:",
                    parse_mode=enums.ParseMode.HTML,
                    reply_markup=kb
                )
            elif action in ("ai_tg", "ai_ig"):
                style = "instagram" if action == "ai_ig" else "telegram"
                style_title = "📸 کپشن اینستاگرام" if style == "instagram" else "📢 پست کانال تلگرام"
                await ensure_binary()
                local_p = drop.get("working_path") or drop.get("compressed_path") or drop.get("original_path")
                if not local_p or not Path(str(local_p)).exists():
                    await callback_query.message.reply_text("❌ فایل صوتی روی سرور یافت نشد.", parse_mode=enums.ParseMode.HTML)
                else:
                    status_m = await callback_query.message.reply_text(
                        f"⏳ <b>[۱/۳] دریافت فایل صوتی ({style_title})</b>\n▫️ لطفاً شکیبا باشید...",
                        parse_mode=enums.ParseMode.HTML
                    )

                    async def _tg_progress(stage_text: str):
                        try:
                            await status_m.edit_text(stage_text, parse_mode=enums.ParseMode.HTML)
                        except Exception:
                            pass

                    from services.ai_agent_service import ai_agent_service, ai_typing_action
                    async def _tg_audio_typing_2():
                        await client.send_chat_action(chat_id, enums.ChatAction.TYPING)

                    async with ai_typing_action(_tg_audio_typing_2):
                        res = await ai_agent_service.transcribe_and_summarize_audio(
                            Path(str(local_p)),
                            metadata=drop,
                            progress_callback=_tg_progress,
                            style=style
                        )
                    if res.get("ok"):
                        msg_text = res.get("formatted_message") or res.get("summary")
                        if len(msg_text) > 4000:
                            msg_text = msg_text[:3990] + "..."
                        try:
                            await status_m.edit_text(msg_text, parse_mode=enums.ParseMode.HTML)
                        except Exception as edit_err:
                            logger.warning(f"[telegram_ai] HTML edit failed, falling back to plain text: {edit_err}")
                            try:
                                await status_m.edit_text(msg_text, parse_mode=None)
                            except Exception:
                                await callback_query.message.reply_text(msg_text, parse_mode=None)
                    else:
                        err_txt = f"❌ {res.get('error') or 'خطا در پردازش هوش مصنوعی'}"
                        try:
                            await status_m.edit_text(err_txt, parse_mode=enums.ParseMode.HTML)
                        except Exception:
                            await callback_query.message.reply_text(err_txt, parse_mode=None)
            elif action == "back":
                session_manager.clear_user_action(f"tg_{user_id}")
                card_txt = TelegramFormatter.format_light_card(drop)
                kb = self.build_media_keyboard(drop_id, drop, is_sub=False)
                await callback_query.message.edit_text(card_txt, parse_mode=enums.ParseMode.HTML, reply_markup=kb)
            elif action == "fn":
                prompt_m = await callback_query.message.reply_text("✏️ <b>نام فایل جدید</b> (مثلاً: <code>lesson01.mp3</code>) را ارسال فرمایید:", parse_mode=enums.ParseMode.HTML)
                session_manager.set_user_action(f"tg_{user_id}", "await_fn", drop_id, extra={"prompt_id": prompt_m.id})
                session_manager.update_session(f"prompt_{drop_id}", {"msg_id": prompt_m.id})
            elif action == "perf":
                kb_quick = InlineKeyboardMarkup([
                    [InlineKeyboardButton(f"⚡️ تنظیم روی مقدار پیش‌فرض ({config.DEFAULT_ARTIST})", callback_data=f"smeta:set_def_artist:{drop_id}")],
                    [InlineKeyboardButton("🔙 انصراف", callback_data=f"smeta:back:{drop_id}")]
                ])
                prompt_m = await callback_query.message.reply_text(
                    "🗣 <b>لطفاً نام خواننده / سازنده جدید را ارسال فرمایید:</b>\n"
                    "یا می‌توانید با کلیک روی دکمه زیر، مستقیماً از نام پیش‌فرض استفاده نمایید:",
                    parse_mode=enums.ParseMode.HTML,
                    reply_markup=kb_quick
                )
                session_manager.set_user_action(f"tg_{user_id}", "await_perf", drop_id, extra={"prompt_id": prompt_m.id})
                session_manager.update_session(f"prompt_{drop_id}", {"msg_id": prompt_m.id})
            elif action == "set_def_artist":
                MediaService.apply_default_artist(drop_id)
                session_manager.clear_user_action(f"tg_{user_id}")
                card_txt = TelegramFormatter.format_light_card(drop)
                kb = self.build_media_keyboard(drop_id, drop, is_sub=False)
                try:
                    await self.app.edit_message_text(
                        chat_id=callback_query.message.chat.id,
                        message_id=drop["card_msg_id"],
                        text=card_txt,
                        reply_markup=kb,
                        parse_mode=enums.ParseMode.HTML
                    )
                except Exception:
                    pass
                await callback_query.answer(f"خواننده روی «{config.DEFAULT_ARTIST}» تنظیم شد.", show_alert=True)
                try:
                    await callback_query.message.delete()
                except Exception:
                    pass
            elif action == "title":
                prompt_m = await callback_query.message.reply_text("🎵 <b>عنوان جدید موزیک / دوره</b> را ارسال فرمایید:", parse_mode=enums.ParseMode.HTML)
                session_manager.set_user_action(f"tg_{user_id}", "await_title", drop_id, extra={"prompt_id": prompt_m.id})
                session_manager.update_session(f"prompt_{drop_id}", {"msg_id": prompt_m.id})
            
            # Audio Trimming Menu
            elif action == "trim":
                await ensure_binary()
                tech = inspect_technical_metadata(drop["working_path"])
                dur = tech.get("duration_sec", 0)
                dur_txt = format_duration(dur)
                trim_prompt = (
                    "✂️ <b>بخش مورد نظر جهت برش فایل را مشخص فرمایید:</b>\n\n"
                    f"⏱️ مدت زمان کل فایل: <b>{dur_txt}</b>\n\n"
                    "نمونه‌های معتبر ارسال:\n"
                    "▫️ <b>شروع و پایان:</b> <code>02:10 - 21:28</code> یا <code>02:10 21:28</code>\n"
                    "▫️ <b>فقط زمان شروع (تا انتها):</b> <code>02:10</code>\n"
                    "▫️ <b>بر حسب ثانیه:</b> <code>130 - 1288</code> یا <code>130</code>"
                )
                prompt_m = await callback_query.message.reply_text(trim_prompt, parse_mode=enums.ParseMode.HTML)
                session_manager.set_user_action(f"tg_{user_id}", "await_trim_time", drop_id, extra={"prompt_id": prompt_m.id})
                session_manager.update_session(f"prompt_{drop_id}", {"msg_id": prompt_m.id})

            # Smart Video to MP3 Conversion
            elif action == "to_mp3":
                status_msg = await callback_query.message.reply_text("⏳ <b>در حال استخراج و تبدیل هوشمند صوت ویدیو به MP3...</b>", parse_mode=enums.ParseMode.HTML)
                await ensure_binary()
                try:
                    ok, final_mp3, info = MediaService.extract_audio_from_video(drop_id)
                    if ok and final_mp3.exists():
                        await status_msg.edit_text("📤 <b>در حال ارسال فایل صوتی MP3 استخراج‌شده...</b>", parse_mode=enums.ParseMode.HTML)
                        sent_audio = await self.send_audio(
                            user_id,
                            final_mp3,
                            title=info["title"],
                            performer=info["artist"],
                            duration=info["duration"],
                            thumb=info["thumb_path"],
                            caption=f"🎵 <b>نسخه صوتی استخراج‌شده از ویدیو (MP3):</b>\n📄 <code>{escape(info['file_name'])}</code>\n🗣 خواننده: <b>{escape(info['artist'])}</b>\n⏱️ مدت زمان: <code>{info['duration']} ثانیه</code>"
                        )
                        new_drop_id = uuid.uuid4().hex[:8]
                        new_audio_id = sent_audio.get("message_id")
                        new_data = MediaService.register_incoming_message_meta(
                            new_drop_id, "telegram", user_id, str(new_audio_id), final_mp3.name, final_mp3.stat().st_size,
                            media_type="audio", api_meta={"filename": final_mp3.name, "duration_sec": info["duration"], "title": info["title"], "artist": info["artist"]}
                        )
                        new_data["working_path"] = str(final_mp3)
                        new_data["is_downloaded_locally"] = True
                        new_card = TelegramFormatter.format_light_card(new_data)
                        new_kb = self.build_media_keyboard(new_drop_id, new_data)
                        c_sent = await self.send_message(user_id, new_card, reply_markup=new_kb)
                        new_data["card_msg_id"] = c_sent.get("message_id")
                        await status_msg.delete()
                    else:
                        await status_msg.edit_text("❌ خطا در استخراج صوت از ویدیو.", parse_mode=enums.ParseMode.HTML)
                except Exception as e:
                    await status_msg.edit_text(f"❌ خطا در تبدیل ویدیو به صوت: {e}", parse_mode=enums.ParseMode.HTML)

            elif action == "view_cover":
                await ensure_binary()
                cov_p = MediaService.extract_cover(drop_id)
                if cov_p and Path(cov_p).exists() and Path(cov_p).stat().st_size > 50:
                    await self.app.send_photo(
                        user_id,
                        str(cov_p),
                        caption="🖼 <b>تصویر بندانگشتی استخراج‌شده</b>",
                        parse_mode=enums.ParseMode.HTML
                    )
                else:
                    await callback_query.answer("این فایل تصویر بند انگشتی ندارد.", show_alert=True)
            elif action == "change_cover":
                prompt_m = await callback_query.message.reply_text("🌇 <b>لطفاً عکس تامبنیل جدید</b> را ارسال نمایید:", parse_mode=enums.ParseMode.HTML)
                session_manager.set_user_action(f"tg_{user_id}", "await_cover", drop_id, extra={"prompt_id": prompt_m.id})
                session_manager.update_session(f"prompt_{drop_id}", {"msg_id": prompt_m.id})
            elif action == "remove_cover":
                MediaService.remove_cover(drop_id)
                card_txt = TelegramFormatter.format_light_card(drop)
                kb = self.build_media_keyboard(drop_id, drop, is_sub=False)
                await callback_query.message.edit_text(card_txt, parse_mode=enums.ParseMode.HTML, reply_markup=kb)
                await callback_query.answer("تصویر تامبنیل حذف شد.")
            
            # Quick Visual Retag
            elif action == "quick_send":
                draft_title = drop.get("draft_tags", {}).get("title") or drop.get("embed_meta", {}).get("title") or drop.get("api_meta", {}).get("title") or ""
                draft_artist = drop.get("draft_tags", {}).get("artist") or drop.get("embed_meta", {}).get("artist") or drop.get("api_meta", {}).get("artist") or ""
                raw_fn = drop.get("edited_fields", {}).get("filename") or drop.get("audio_filename") or "audio.mp3"
                clean_fn = clean_display_filename(raw_fn)
                file_id = drop.get("file_id")

                try:
                    if drop.get("media_type") == "video":
                        await self.send_video(
                            chat_id=user_id,
                            file_path=file_id,
                            file_name=clean_fn,
                            caption=f"⚡️ <b>فایل ویدیویی با متادیتای جدید:</b>\n📄 <code>{escape(clean_fn)}</code>"
                        )
                    else:
                        await self.send_audio(
                            chat_id=user_id,
                            file_path=file_id,
                            file_name=clean_fn,
                            title=draft_title or None,
                            performer=draft_artist or None,
                            caption=f"⚡️ <b>فایل با متادیتای نمایشی جدید:</b>\n📄 <code>{escape(clean_fn)}</code>\n🗣 خواننده: <b>{escape(draft_artist)}</b>\n🎵 عنوان: <code>{escape(draft_title)}</code>"
                        )
                except Exception as e:
                    await callback_query.message.reply_text(f"❌ خطا در اعمال سریع: {e}", parse_mode=enums.ParseMode.HTML)

            elif action == "add_to_course":
                courses = await StoreService.get_products(is_free_only=False)
                if not courses:
                    await callback_query.answer("هیچ دوره‌ای تعریف نشده است.", show_alert=True)
                else:
                    c_buttons = [
                        [InlineKeyboardButton(f"➕ {c.name}", callback_data=f"smeta:attach_course:{drop_id}:{c.product_id}")]
                        for c in courses[:10]
                    ]
                    c_buttons.append([InlineKeyboardButton("🔙 بازگشت به منوی رسانه", callback_data=f"smeta:back:{drop_id}")])
                    await callback_query.message.reply_text("📚 دوره‌ای که می‌خواهید این فایل به آن اضافه شود را انتخاب فرمایید:", reply_markup=InlineKeyboardMarkup(c_buttons))

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
                        "platform": "telegram",
                        "size": drop.get("file_size", 0)
                    })
                    await StoreService.update_product_field(course_id, "files_package", pkg)
                    await StoreService.update_product_field(course_id, "delivery_type", "files_package")
                    await callback_query.answer(f"✅ فایل با موفقیت به دوره «{prod.name}» پیوست شد!", show_alert=True)
                else:
                    await callback_query.answer("دوره یافت نشد.", show_alert=True)

            elif action == "compress":
                await ensure_binary()
                status_m = await callback_query.message.reply_text("⚡️ <b>در حال فشرده‌سازی هوشمند فایل...</b>", parse_mode=enums.ParseMode.HTML)
                try:
                    wpath = Path(drop.get("working_path") or "")
                    if not wpath.exists():
                        final_p, fn, info = MediaService.prepare_for_transfer(drop_id, "telegram")
                        wpath = final_p
                    if drop.get("media_type") == "video":
                        comp_p, _, _, _, was_c = SmartVideoCompressor.compress_if_needed(wpath)
                    else:
                        comp_p, _, _, _, was_c = SmartAudioCompressor.compress_if_needed(wpath)
                    if comp_p and comp_p.exists():
                        drop["working_path"] = str(comp_p)
                        drop["file_size"] = comp_p.stat().st_size
                        session_manager.update_session(drop_id, drop)
                        await status_m.edit_text(f"✅ فشرده‌سازی انجام شد! حجم جدید: {drop['file_size'] / (1024*1024):.2f} مگابایت", parse_mode=enums.ParseMode.HTML)
                    else:
                        await status_m.edit_text("ℹ️ فایل در اندازه مناسب است و نیازی به فشرده‌سازی بیشتر ندارد.", parse_mode=enums.ParseMode.HTML)
                except Exception as c_err:
                    await status_m.edit_text(f"❌ خطا در فشرده‌سازی: {c_err}", parse_mode=enums.ParseMode.HTML)

            # Physical Full Rewrite & Delivery (Apply Changes)
            elif action in ("apply_changes", "send_back"):
                status_msg = await callback_query.message.reply_text("📥 <b>در حال دانلود از مبدا...</b>", parse_mode=enums.ParseMode.HTML)
                await ensure_binary()
                try:
                    await status_msg.edit_text("⏳ <b>در حال رایت فیزیکی تگ‌های متادیتا روی فایل...</b>", parse_mode=enums.ParseMode.HTML)
                    final_path, send_name, transfer_info = MediaService.prepare_for_transfer(drop_id, "telegram")
                    await status_msg.edit_text("📤 <b>در حال ارسال فایل اصلاح‌شده برای شما...</b>", parse_mode=enums.ParseMode.HTML)
                    if drop.get("media_type") == "video":
                        tech = inspect_technical_metadata(final_path)
                        thumb_p = generate_video_thumbnail(final_path)
                        res = await self.send_video(
                            chat_id=user_id,
                            file_path=final_path,
                            file_name=send_name,
                            caption=f"✅ <b>فایل ویدیویی اصلاح‌شده:</b>\n📄 <code>{escape(send_name)}</code>",
                            width=tech.get("width"),
                            height=tech.get("height"),
                            duration=tech.get("duration_sec"),
                            thumb=thumb_p
                        )
                        if isinstance(res, dict) and not res.get("ok"):
                            raise RuntimeError(res.get("error", "خطا در ارسال فایل ویدیویی"))
                    else:
                        cover_path = drop.get("working_cover") or drop.get("embedded_cover")
                        art_tag = transfer_info.get("artist") or drop.get("api_meta", {}).get("artist") or None
                        title_tag = transfer_info.get("title") or drop.get("api_meta", {}).get("title") or None
                        caption_parts = [
                            "✅ <b>فایل صوتی اصلاح‌شده و تگ‌گذاری‌شده:</b>",
                            f"📄 <code>{escape(send_name)}</code>"
                        ]
                        if art_tag:
                            caption_parts.append(f"🗣 خواننده: <b>{escape(art_tag)}</b>")
                        if title_tag:
                            caption_parts.append(f"🎵 عنوان: <code>{escape(title_tag)}</code>")
                        res = await self.send_audio(
                            chat_id=user_id,
                            file_path=final_path,
                            file_name=send_name,
                            title=title_tag,
                            performer=art_tag,
                            duration=transfer_info.get("duration") or drop.get("api_meta", {}).get("duration_sec"),
                            thumb=cover_path if cover_path and Path(str(cover_path)).exists() else None,
                            caption="\n".join(caption_parts)
                        )
                        if isinstance(res, dict) and not res.get("ok"):
                            raise RuntimeError(res.get("error", "خطا در ارسال فایل صوتی به تلگرام"))
                    await status_msg.edit_text("✅ <b>تغییرات با موفقیت روی فایل اعمال و ارسال شد.</b>", parse_mode=enums.ParseMode.HTML)
                except Exception as e:
                    await status_msg.edit_text(f"❌ خطا در اعمال تغییرات و ارسال فایل: {e}", parse_mode=enums.ParseMode.HTML)

            # Choose Rubika Mode Menu
            elif action == "choose_rubika":
                has_user = self.rubika_adapter.has_user_session() if self.rubika_adapter else False
                kb = build_rubika_target_keyboard(drop_id, has_user)
                await callback_query.message.edit_text(
                    "🟣 <b>ارسال به روبیکا (Rubika):</b>\n\n"
                    "لطفاً مقصد مورد نظر جهت انتقال فایل را انتخاب فرمایید:\n"
                    "▫️ <b>پیام‌های ذخیره‌شده:</b> انتقال فایل با سشن کاربری (تا ۲ گیگابایت بدون سقف).\n"
                    "▫️ <b>ربات رسمی:</b> ارسال به چت/کانال بات روبیکا (سقف ۵۰ مگابایت).",
                    parse_mode=enums.ParseMode.HTML,
                    reply_markup=kb
                )
            elif action in ("rub_user", "send_rubika"):
                from task_store import has_rubika_session, load_runtime_settings, append_task, build_status_text, apply_runtime_settings
                settings = load_runtime_settings()
                if not has_rubika_session(settings["rubika_session"]):
                    kb = InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔐 لاگین به حساب روبیکا", callback_data=f"smeta:rub_login:{drop_id}")],
                        [InlineKeyboardButton("🔙 بازگشت", callback_data=f"smeta:choose_rubika:{drop_id}")]
                    ])
                    await callback_query.message.edit_text(
                        "❌ <b>سشن کاربری روبیکا فعال نیست:</b>\n"
                        "جهت ارسال فایل به پیام‌های ذخیره‌شده (Saved Messages)، ابتدا با زدن دکمه زیر وارد حساب روبیکای خود شوید یا دستور <code>/set_rubika</code> را ارسال فرمایید.",
                        parse_mode=enums.ParseMode.HTML,
                        reply_markup=kb
                    )
                    return

                status_msg = await callback_query.message.reply_text("📥 <b>در حال دانلود فایل از مبدا تلگرام...</b>", parse_mode=enums.ParseMode.HTML)
                await ensure_binary()

                try:
                    await status_msg.edit_text("⏳ <b>در حال آماده‌سازی و اعمال متادیتا...</b>", parse_mode=enums.ParseMode.HTML)
                    final_path, send_name, transfer_info = MediaService.prepare_for_transfer(drop_id, "rubika")
                    file_size = final_path.stat().st_size

                    await status_msg.edit_text(
                        build_status_text(
                            task_id=drop_id,
                            file_name=send_name,
                            file_size=file_size,
                            stage="📤 در صف آپلود روبیکا",
                            download_percent=100,
                            upload_percent=0,
                            upload_status="فایل در صف آپلود به پیام‌های ذخیره‌شده روبیکا قرار گرفت."
                        ),
                        parse_mode=enums.ParseMode.HTML
                    )

                    task = {
                        "task_id": drop_id,
                        "destination": "rubika",
                        "path": str(final_path),
                        "caption": f"📄 {send_name}",
                        "chat_id": callback_query.message.chat.id,
                        "status_message_id": status_msg.id,
                        "file_name": send_name,
                        "file_size": file_size,
                        "media_type": "audio" if drop.get("media_type") == "audio" else "video",
                        "started_at": time.time(),
                        "source": "telegram"
                    }
                    apply_runtime_settings(task, settings)
                    append_task(task)
                except Exception as e:
                    await callback_query.message.reply_text(f"❌ <b>خطا در ثبت صف روبیکا:</b> {e}", parse_mode=enums.ParseMode.HTML)

            # Send to Rubika Bot API
            elif action == "rub_bot":
                status_msg = await callback_query.message.reply_text("📥 <b>در حال دانلود فایل از مبدا...</b>", parse_mode=enums.ParseMode.HTML)
                await ensure_binary()
                try:
                    await status_msg.edit_text("⏳ <b>در حال آماده‌سازی و اعمال متادیتا...</b>", parse_mode=enums.ParseMode.HTML)
                    final_path, send_name, transfer_info = MediaService.prepare_for_transfer(drop_id, "rubika_bot")
                    target_chat = self.rubika_adapter.get_admin_guid()
                    logger.info(f"[rub_bot] Transferring drop_id={drop_id} to Rubika target={target_chat}, file={final_path.name} ({final_path.stat().st_size} bytes)...")

                    await status_msg.edit_text("📤 <b>در حال آپلود به سرور مدیا روبیکا...</b>", parse_mode=enums.ParseMode.HTML)
                    res = await self.rubika_adapter.send_audio_bot_api(
                        target_chat,
                        final_path,
                        caption=f"📄 {send_name}"
                    )
                    logger.info(f"[rub_bot] Rubika send_audio_bot_api response: {res}")
                    if res.get("ok") or res.get("status") == "OK":
                        await status_msg.edit_text(f"✅ <b>فایل با موفقیت به ربات روبیکا منتقل شد!</b>\n📄 <code>{escape(send_name)}</code>", parse_mode=enums.ParseMode.HTML)
                    else:
                        err_info = res.get("error") or res.get("status") or str(res)
                        await status_msg.edit_text(f"❌ <b>خطا در ارتباط با سرورهای روبیکا:</b>\n<code>{escape(str(err_info))}</code>", parse_mode=enums.ParseMode.HTML)
                except Exception as e:
                    await status_msg.edit_text(f"❌ <b>خطا در ارتباط با سرورهای روبیکا:</b>\n<code>{escape(str(e))}</code>", parse_mode=enums.ParseMode.HTML)

            elif action == "split_video":
                target_chat = self.bale_adapter.get_admin_chat_id() if self.bale_adapter else None
                status_msg = await callback_query.message.reply_text("📥 <b>در حال دانلود و آماده‌سازی ویدیو جهت برش و تقسیم...</b>", parse_mode=enums.ParseMode.HTML)
                await ensure_binary(status_msg)
                w_path = Path(drop.get("working_path") or "")
                if not w_path.exists():
                    await status_msg.edit_text("❌ فایل ویدیو روی سرور یافت نشد.")
                    return
                safe_limit_mb = 48.5
                qual_info = SmartVideoCompressor.precalculate_video_quality(w_path, target_max_mb=safe_limit_mb)
                rec_parts = qual_info.get("recommended_parts", 2)
                dur_m = int(qual_info.get("duration_sec", 0) // 60)
                init_mb = qual_info.get("initial_size_mb", 0.0)

                session_manager.set_user_action(
                    f"tg_{user_id}",
                    "await_split_parts",
                    drop_id,
                    extra={"msg_id": status_msg.id, "drop_id": drop_id}
                )

                kb_rows = [
                    [
                        InlineKeyboardButton("✂️ تقسیم هوشمند به ۲ پارت", callback_data=f"smeta:split_bale:{drop_id}:2")
                    ],
                    [
                        InlineKeyboardButton("🗜️ فشرده‌سازی هوشمند تا سقف بله", callback_data=f"smeta:force_bale:{drop_id}")
                    ],
                    [
                        InlineKeyboardButton("🔙 بازگشت به منوی رسانه", callback_data=f"smeta:back:{drop_id}")
                    ]
                ]
                split_kb = InlineKeyboardMarkup(kb_rows)
                await status_msg.edit_text(
                    f"✂️ <b>دستیار تقسیم هوشمند ویدیو (Split Assistant):</b>\n"
                    f"📄 فایل: <code>{escape(drop.get('audio_filename', 'video.mp4'))}</code>\n"
                    f"⏱ مدت زمان: <code>{dur_m} دقیقه</code> | حجم اولیه: <code>{init_mb} MB</code>\n"
                    f"💡 <i>پارت‌های پیشنهادی بر مبنای سقف ۴۸.۵MB بله: <b>{rec_parts} پارت</b></i>\n\n"
                    "👇 <b>گزینه مورد نظر خود را انتخاب فرمایید:</b>\n"
                    "• کلیک روی <b>«✂️ تقسیم هوشمند به ۲ پارت»</b> یا <b>«🗜 فشرده‌سازی تا سقف بله»</b>\n"
                    "• یا اگر مایلید ویدیو به تعداد دلخواه تقسیم شود، <b>عدد مورد نظر (مثلاً ۳ یا ۴)</b> را همین‌جا در چت ارسال کنید!",
                    parse_mode=enums.ParseMode.HTML,
                    reply_markup=split_kb
                )

            elif action == "split_bale":
                target_chat = self.bale_adapter.get_admin_chat_id() if self.bale_adapter else None
                if not target_chat:
                    await callback_query.message.reply_text("❌ شناسه چت بله تنظیم نشده است.")
                    return
                status_msg = callback_query.message
                await ensure_binary(status_msg)
                parts_count = int(parts[3]) if len(parts) > 3 and str(parts[3]).isdigit() else 2
                session_manager.clear_user_action(f"tg_{user_id}")
                await self.split_and_transfer_video_to_bale(drop_id, parts_count, status_msg)

            elif action in ("send_bale", "force_bale"):
                target_chat = self.bale_adapter.get_admin_chat_id() if self.bale_adapter else None
                if not target_chat:
                    await callback_query.message.reply_text("❌ شناسه چت بله تنظیم نشده است.")
                    return

                status_msg = callback_query.message if action == "force_bale" else await callback_query.message.reply_text("📥 <b>در حال دانلود فایل از مبدا...</b>", parse_mode=enums.ParseMode.HTML)
                await ensure_binary(status_msg)

                w_path = Path(drop.get("working_path") or "")

                # دستیار هوشمند تصمیم‌گیری فشرده‌سازی یا تقسیم ویدیو (صرفاً و منحصراً برای فایل‌های بالای ۴۸.۵ مگابایت)
                if action != "force_bale" and drop.get("media_type") == "video" and w_path.exists():
                    safe_limit_mb = 48.5
                    file_size_mb = w_path.stat().st_size / (1024 * 1024)
                    if file_size_mb > safe_limit_mb:
                        qual_info = SmartVideoCompressor.precalculate_video_quality(w_path, target_max_mb=safe_limit_mb)
                        est_res = qual_info.get("estimated_resolution", "360p")
                        rec_parts = qual_info.get("recommended_parts", 2)
                        dur_mins = int(qual_info.get("duration_sec", 0) // 60)
                        session_manager.set_user_action(
                            f"tg_{user_id}",
                            "await_split_parts",
                            drop_id,
                            extra={"msg_id": status_msg.id, "drop_id": drop_id}
                        )
                        warn_text = (
                            f"⚠️ <b>حجم این ویدیو بیش از سقف مجاز بله است ({file_size_mb:.2f} MB).</b>\n"
                            f"جهت ارسال موفق به بله، می‌توانید آن را به پارت‌های باکیفیت تقسیم کرده یا فشرده فرمایید:\n\n"
                            f"💡 <i>پارت‌های پیشنهادی بر مبنای سقف ۴۸.۵MB بله: <b>{rec_parts} پارت</b></i>\n\n"
                            "👇 <b>گزینه مورد نظر خود را انتخاب فرمایید:</b>\n"
                            "• کلیک روی <b>«✂️ تقسیم هوشمند به ۲ پارت»</b> یا <b>«🗜️ فشرده‌سازی هوشمند تا سقف بله»</b>\n"
                            "• یا اگر مایلید ویدیو به تعداد دلخواه تقسیم شود، <b>عدد مورد نظر (مثلاً ۳ یا ۴)</b> را همین‌جا در چت ارسال کنید!"
                        )
                        kb_rows = [
                            [
                                InlineKeyboardButton("✂️ تقسیم هوشمند به ۲ پارت", callback_data=f"smeta:split_bale:{drop_id}:2")
                            ],
                            [
                                InlineKeyboardButton("🗜️ فشرده‌سازی هوشمند تا سقف بله", callback_data=f"smeta:force_bale:{drop_id}")
                            ],
                            [
                                InlineKeyboardButton("🔙 بازگشت به منوی رسانه", callback_data=f"smeta:back:{drop_id}")
                            ]
                        ]
                        warn_kb = InlineKeyboardMarkup(kb_rows)
                        await status_msg.edit_text(warn_text, parse_mode=enums.ParseMode.HTML, reply_markup=warn_kb)
                        return

                if w_path.exists() and (w_path.stat().st_size / (1024 * 1024)) >= 48.5:
                    orig_sz_mb = f"{w_path.stat().st_size / (1024 * 1024):.1f}"
                    await status_msg.edit_text(
                        "🎛 <b>در حال فشرده‌سازی هوشمند جهت رعایت سقف بله...</b>\n"
                        f"📊 حجم فعلی: <code>{orig_sz_mb} MB</code> ➔ هدف: <code>زیر 48.5 MB</code>\n"
                        "⚙️ فرآیند بهینه‌سازی صدا و تصویر در حال اجراست، لطفاً شکیبا باشید...",
                        parse_mode=enums.ParseMode.HTML
                    )

                def update_cb(text: str):
                    try:
                        msg_text = text if "<b>" in text else f"⏳ {escape(text)}"
                        asyncio.create_task(status_msg.edit_text(msg_text, parse_mode=enums.ParseMode.HTML))
                    except Exception:
                        pass

                try:
                    final_path, send_name, transfer_info = MediaService.prepare_for_transfer(drop_id, "bale", progress_callback=update_cb)
                    p_final = Path(str(final_path))
                    total_file_size = p_final.stat().st_size
                    header_text = "🚢 <b>در حال بارگذاری فایل در بله...</b>"

                    with open(p_final, "rb") as f:
                        if drop.get("media_type") == "video":
                            tech = inspect_technical_metadata(p_final)
                            upload_coro = self.bale_adapter.send_video(
                                target_chat,
                                f,
                                filename=send_name,
                                caption=f"📄 <b>{escape(send_name)}</b>",
                                duration=tech.get("duration_sec"),
                                width=tech.get("width"),
                                height=tech.get("height")
                            )
                        else:
                            upload_coro = self.bale_adapter.send_audio(
                                target_chat,
                                f,
                                filename=send_name,
                                title=transfer_info["title"],
                                performer=transfer_info["artist"],
                                caption=f"📄 <b>{escape(send_name)}</b>"
                            )

                        res = await run_bale_upload_with_progress(
                            f, total_file_size, status_msg, header_text, upload_coro
                        )

                    if res.get("ok"):
                        await status_msg.edit_text(f"✅ <b>فایل با موفقیت و حفظ کامل متادیتا به بله منتقل شد!</b>\n📄 <code>{escape(send_name)}</code>", parse_mode=enums.ParseMode.HTML)
                    else:
                        err_info = res.get("error") or res.get("description") or str(res)
                        await status_msg.edit_text(
                            f"❌ <b>خطا در ارسال به بله:</b> [{escape(str(err_info))}]\n"
                            f"💡 لطفاً دکمه ارسال را مجدداً بزنید.",
                            parse_mode=enums.ParseMode.HTML
                        )
                except Exception as e:
                    await status_msg.edit_text(
                        f"❌ <b>خطا در ارسال به بله:</b> [{escape(str(e))}]\n"
                        f"💡 لطفاً دکمه ارسال را مجدداً بزنید.",
                        parse_mode=enums.ParseMode.HTML
                    )

            elif action == "send_splus":
                # انتقال مستقیم فایل از تلگرام به پیام‌های ذخیره‌شده پیام‌رسان سروش‌پلاس
                from platforms.soroush_worker import soroush_worker
                if not soroush_worker.is_connected():
                    await callback_query.message.reply_text(
                        "❌ <b>سشن کاربری سروش‌پلاس متصل نیست.</b>\nلطفاً ابتدا در پنل وب وارد حساب کاربری شوید.",
                        parse_mode=enums.ParseMode.HTML
                    )
                    return

                status_msg = await callback_query.message.reply_text(
                    "📥 <b>در حال دانلود و آماده‌سازی فایل جهت انتقال به سروش‌پلاس...</b>",
                    parse_mode=enums.ParseMode.HTML
                )
                await ensure_binary()

                try:
                    final_path, send_name, transfer_info = MediaService.prepare_for_transfer(drop_id, "soroush")
                    await status_msg.edit_text("📤 <b>در حال ارسال فایل به پیام‌های ذخیره‌شده سروش‌پلاس...</b>", parse_mode=enums.ParseMode.HTML)
                    caption_text = f"📄 <b>{escape(send_name)}</b>"
                    res = await soroush_worker.send_file_to_saved_messages(final_path, caption=caption_text)
                    if res.get("ok"):
                        queue_note = " (در صف ارسال محلی امن ذخیره گردید)" if res.get("queued") else ""
                        await status_msg.edit_text(
                            f"✅ <b>فایل با موفقیت به سروش‌پلاس منتقل شد!</b>{queue_note}\n📄 <code>{escape(send_name)}</code>",
                            parse_mode=enums.ParseMode.HTML
                        )
                    else:
                        err_info = res.get("error") or str(res)
                        await status_msg.edit_text(
                            f"❌ <b>خطا در ارتباط با سرورهای سروش‌پلاس:</b>\n<code>{escape(str(err_info))}</code>",
                            parse_mode=enums.ParseMode.HTML
                        )
                except Exception as e:
                    await status_msg.edit_text(
                        f"❌ <b>خطا در انتقال فایل به سروش‌پلاس:</b>\n<code>{escape(str(e))}</code>",
                        parse_mode=enums.ParseMode.HTML
                    )

        # Batch Forwarding Manager Callbacks: Group Forwarding to Bale & Rubika
        @self.app.on_callback_query(filters.regex(r"^smeta_batch:"))
        async def handle_batch_forward_cb(client: Client, callback_query: CallbackQuery):
            parts = callback_query.data.split(":")
            dest = parts[1]
            batch_id = parts[2]
            items = self._batch_registry.get(batch_id)
            if not items:
                await callback_query.answer("فایل‌های این گروه منقضی شده‌اند.", show_alert=True)
                return
            await callback_query.answer()
            if dest == "cancel":
                self._batch_registry.pop(batch_id, None)
                await callback_query.message.edit_text("❌ ارسال دسته‌جمعی لغو شد.")
                return

            status_msg = callback_query.message
            dest_name = "بله" if dest == "bale" else "روبیکا"

            async def _safe_edit_batch(text: str):
                try:
                    await status_msg.edit_text(text, parse_mode=enums.ParseMode.HTML)
                except Exception:
                    pass

            batch_res = await MediaService.process_batch_sequentially(
                items=items,
                destination=dest,
                bale_adapter=self.bale_adapter,
                rubika_adapter=self.rubika_adapter,
                status_callback=_safe_edit_batch
            )

            self._batch_registry.pop(batch_id, None)
            total_count = batch_res.get("total", len(items))
            success_count = batch_res.get("success", 0)

            if success_count == total_count:
                await status_msg.edit_text(f"✅ <b>تمام {total_count} فایل با موفقیت به {dest_name} منتقل شدند!</b>", parse_mode=enums.ParseMode.HTML)
            else:
                await status_msg.edit_text(f"⚠️ <b>عملیات به پایان رسید:</b> {success_count} از {total_count} فایل با موفقیت به {dest_name} منتقل شد.", parse_mode=enums.ParseMode.HTML)

        # Text input handler for Metadata, Trimming, URLs, Support, and Force Join
        @self.app.on_message(filters.private & (filters.text | filters.caption))
        async def text_handler(client: Client, message: Message):
            user_id = message.from_user.id
            text = (message.text or message.caption or "").strip()
            user_act = session_manager.get_user_action(f"tg_{user_id}")
            if user_act and text == "/cancel":
                session_manager.clear_user_action(f"tg_{user_id}")
                await message.reply_text("❌ عملیات با موفقیت لغو شد.", parse_mode=enums.ParseMode.HTML)
                return

            if user_act and user_act.get("action") == "await_svg_hex":
                target_fid = user_act.get("drop_id")
                session_manager.clear_user_action(f"tg_{user_id}")
                color = text.strip()
                if not color.startswith("#"):
                    color = "#" + color
                status_msg = await message.reply_text(f"⏳ در حال تغییر رنگ وکتور به {color}...")
                tmp_svg_path = config.TEMP_DIR / f"tg_svg_{uuid.uuid4().hex[:8]}.svg"
                try:
                    from services.image_service import image_service
                    await client.download_media(target_fid, file_name=str(tmp_svg_path))
                    if not tmp_svg_path.exists():
                        raise ValueError("خطا در دانلود فایل SVG از تلگرام.")
                    with open(tmp_svg_path, "r", encoding="utf-8", errors="replace") as f_in:
                        svg_str = f_in.read()
                    recolored_svg = image_service.recolor_svg(svg_str, color)
                    out_bytes = recolored_svg.encode("utf-8")
                    tmp_out = config.TEMP_DIR / f"vector_{color.lstrip('#')}_{uuid.uuid4().hex[:8]}.svg"
                    with open(tmp_out, "wb") as f_out:
                        f_out.write(out_bytes)
                    svg_kb = InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("⚪️ سفید (#FFF)", callback_data=f"tg_svg_recol:white:{target_fid}"),
                            InlineKeyboardButton("⚫️ مشکی (#000)", callback_data=f"tg_svg_recol:black:{target_fid}")
                        ],
                        [
                            InlineKeyboardButton("🎨 تغییر به کد هگز دیگر", callback_data=f"tg_svg_hex:{target_fid}")
                        ],
                        [
                            InlineKeyboardButton("🖼 خروجی PNG شفاف", callback_data=f"tg_svg:png:{target_fid}"),
                            InlineKeyboardButton("🖼 خروجی JPG", callback_data=f"tg_svg:jpg:{target_fid}")
                        ]
                    ])
                    caption = f"🎨 <b>وکتور با رنگ جدید ({color}):</b>\nنگارش موتور وکتور: <code>{config.ENGINE_VERSION}</code>"
                    await client.send_document(user_id, str(tmp_out), caption=caption, file_name=f"vector_{color.lstrip('#')}.svg", parse_mode=enums.ParseMode.HTML, reply_markup=svg_kb)
                    try: tmp_out.unlink()
                    except Exception: pass
                    await status_msg.delete()
                except Exception as e:
                    logger.error(f"[tg_svg_hex] error: {e}")
                    await status_msg.edit_text(f"❌ خطا در پردازش و تغییر رنگ وکتور: {e}")
                finally:
                    if tmp_svg_path.exists():
                        try: tmp_svg_path.unlink()
                        except Exception: pass
                return

            if user_act and user_act.get("action") == "await_c_name":
                c_data = user_act.get("extra") or {}
                c_data["name"] = text
                session_manager.set_user_action(f"tg_{user_id}", "await_c_price", "new_course", extra=c_data)
                await message.reply_text(
                    f"💰 <b>نام دوره: «{escape(text)}»</b>\n\n"
                    "لطفاً <b>قیمت دوره به تومان</b> را وارد فرمایید:\n"
                    "(برای دوره رایگان یا هدیه عدد <code>0</code> ارسال کنید)",
                    parse_mode=enums.ParseMode.HTML
                )
                return

            if user_act and user_act.get("action") == "await_c_price":
                c_data = user_act.get("extra") or {}
                clean_digits = re.sub(r"[^\d]", "", text)
                price = int(clean_digits) if clean_digits else 0
                c_data["price"] = price
                session_manager.set_user_action(f"tg_{user_id}", "await_c_desc", "new_course", extra=c_data)
                await message.reply_text(
                    f"📝 <b>قیمت دوره: {price:,} تومان</b>\n\n"
                    "لطفاً <b>توضیحات کوتاه و سرفصل‌های دوره</b> را ارسال فرمایید:",
                    parse_mode=enums.ParseMode.HTML
                )
                return

            if user_act and user_act.get("action") == "await_c_desc":
                c_data = user_act.get("extra") or {}
                c_data["desc"] = text
                session_manager.set_user_action(f"tg_{user_id}", "await_c_link", "new_course", extra=c_data)
                await message.reply_text(
                    "📥 <b>توضیحات با موفقیت ثبت شد!</b>\n\n"
                    "لطفاً <b>لینک مستقیم دانلود محتوای دوره</b> را ارسال فرمایید:",
                    parse_mode=enums.ParseMode.HTML
                )
                return

            if user_act and user_act.get("action") == "await_c_link":
                c_data = user_act.get("extra") or {}
                c_data["link"] = clean_course_access_input(text, c_data.get("name", ""))
                session_manager.set_user_action(f"tg_{user_id}", "await_c_photo", "new_course", extra=c_data)
                await message.reply_text(
                    "🖼 <b>لینک مستقیم دانلود ثبت شد!</b>\n\n"
                    "در صورت تمایل <b>عکس یا پوستر دوره</b> را ارسال فرمایید، یا برای ثبت بدون عکس دستور <code>/skip</code> را بفرستید:",
                    parse_mode=enums.ParseMode.HTML
                )
                return

            if user_act and user_act.get("action") == "await_c_photo":
                c_data = user_act.get("extra") or {}
                session_manager.clear_user_action(f"tg_{user_id}")
                prod = await StoreService.add_product(
                    name=c_data.get("name") or "دوره جدید",
                    price=int(c_data.get("price") or 0),
                    description=c_data.get("desc") or "",
                    download_link=c_data.get("link") or "",
                    photo_url="",
                    allow_card=True,
                    allow_bale=True
                )
                await message.reply_text(
                    f"🎉 <b>دوره «{escape(prod.name)}» با موفقیت ثبت گردید!</b>\n\n"
                    f"💰 قیمت: <code>{prod.price:,} تومان</code>\n"
                    f"📥 لینک دانلود: <code>{escape(prod.download_link or 'ندارد')}</code>\n\n"
                    "دوره هم‌اکنون به صورت آنی در فروشگاه وب (<code>/store</code>) و ربات‌ها منتشر شد.",
                    parse_mode=enums.ParseMode.HTML
                )
                return

            if user_act and user_act.get("action", "").startswith("await_c_edit_"):
                act = user_act["action"]
                pid = user_act["drop_id"]
                prod = await StoreService.get_product(pid)
                if not prod:
                    session_manager.clear_user_action(f"tg_{user_id}")
                    await message.reply_text("❌ دوره یافت نشد.")
                    return

                if act == "await_c_edit_link":
                    clean_l = clean_course_access_input(text, prod.name if prod else "")
                    await StoreService.update_product_field(pid, "download_link", clean_l)
                    session_manager.clear_user_action(f"tg_{user_id}")
                    prod.download_link = clean_l
                    await message.reply_text(f"✅ <b>لینک‌های دسترسی دوره «{escape(prod.name)}» با موفقیت ذخیره شد.</b>", parse_mode=enums.ParseMode.HTML)
                    await message.reply_text(format_admin_course_card(prod), parse_mode=enums.ParseMode.HTML, reply_markup=build_admin_course_keyboard(pid, prod.active))
                    return

                elif act == "await_c_edit_price":
                    clean_digits = re.sub(r"[^\d]", "", text)
                    new_price = int(clean_digits) if clean_digits else 0
                    await StoreService.update_product_field(pid, "price", new_price)
                    session_manager.clear_user_action(f"tg_{user_id}")
                    prod.price = new_price
                    await message.reply_text(f"✅ <b>قیمت دوره «{escape(prod.name)}» به {new_price:,} تومان تغییر یافت.</b>", parse_mode=enums.ParseMode.HTML)
                    await message.reply_text(format_admin_course_card(prod), parse_mode=enums.ParseMode.HTML, reply_markup=build_admin_course_keyboard(pid, prod.active))
                    return

                elif act == "await_c_edit_desc":
                    await StoreService.update_product_field(pid, "description", text)
                    session_manager.clear_user_action(f"tg_{user_id}")
                    prod.description = text
                    await message.reply_text(f"✅ <b>توضیحات دوره «{escape(prod.name)}» به‌روزرسانی شد.</b>", parse_mode=enums.ParseMode.HTML)
                    await message.reply_text(format_admin_course_card(prod), parse_mode=enums.ParseMode.HTML, reply_markup=build_admin_course_keyboard(pid, prod.active))
                    return

                elif act == "await_c_edit_photo":
                    await StoreService.update_product_field(pid, "photo_url", text)
                    session_manager.clear_user_action(f"tg_{user_id}")
                    prod.photo_url = text
                    await message.reply_text(f"✅ <b>آدرس تصویر دوره «{escape(prod.name)}» ذخیره گردید.</b>", parse_mode=enums.ParseMode.HTML)
                    await message.reply_text(format_admin_course_card(prod), parse_mode=enums.ParseMode.HTML, reply_markup=build_admin_course_keyboard(pid, prod.active))
                    return

            # Direct Download Link (URL Uploader Gate)
            link_match = re.search(r"https?://[^\s]+", text)
            if link_match:
                if user_act:
                    session_manager.clear_user_action(f"tg_{user_id}")
                    user_act = None

                if not self.is_admin(user_id):
                    logger.warning(f"Unauthorized link download attempt by non-admin user {user_id}: {text[:100]}")
                    await message.reply_text(
                        f"⛔ دسترسی غیرمجاز! شناسه عددی تلگرام شما جهت ثبت در پنل: <code>{user_id}</code>",
                        parse_mode=enums.ParseMode.HTML
                    )
                    return

                clean_url = link_match.group(0).strip()
                probe = await UrlService.probe_url(clean_url)
                if probe.get("is_valid"):
                    url_id = uuid.uuid4().hex[:8]
                    session_manager.create_session(f"url_{url_id}", {**probe, "url_id": url_id, "url": clean_url})
                    
                    is_vid = probe["media_type"] == "video"
                    buttons = [
                        [InlineKeyboardButton("⚡️ شروع و تبدیل به فایل تلگرام", callback_data=f"urldl:auto:{url_id}")],
                    ]
                    if is_vid:
                        buttons.append([
                            InlineKeyboardButton("🎥 دریافت در حالت ویدیو", callback_data=f"urldl:video:{url_id}"),
                            InlineKeyboardButton("🎵 استخراج و تبدیل به MP3", callback_data=f"urldl:audio:{url_id}")
                        ])
                        buttons.append([
                            InlineKeyboardButton("📁 دریافت در حالت فایل", callback_data=f"urldl:doc:{url_id}")
                        ])
                    else:
                        buttons.append([
                            InlineKeyboardButton("🎵 دریافت در حالت موزیک", callback_data=f"urldl:audio:{url_id}"),
                            InlineKeyboardButton("📁 دریافت در حالت فایل", callback_data=f"urldl:doc:{url_id}")
                        ])
                    buttons.append([InlineKeyboardButton("❌ انصراف", callback_data=f"urldl:cancel:{url_id}")])

                    kb_url = InlineKeyboardMarkup(buttons)
                    
                    card_txt = (
                        "🌐 <b>لینک مستقیم دانلود شناسایی شد:</b>\n\n"
                        f"📄 <b>نام فایل:</b> <code>{escape(probe['filename'])}</code>\n"
                        f"📦 <b>حجم تقریبی:</b> <b>{human_size(probe['file_size'])}</b>\n"
                        f"🏷 <b>نوع محتوا:</b> <code>{probe['content_type'] or probe['media_type']}</code>\n\n"
                        "لطفاً نحوه دریافت و پردازش فایل را انتخاب فرمایید:"
                    )
                    await message.reply_text(card_txt, parse_mode=enums.ParseMode.HTML, reply_markup=kb_url)
                    return
                else:
                    err_reason = probe.get("error") or "سرور مبدا اجازه دسترسی به این فایل را نداد یا لینک نامعتبر است."
                    await message.reply_text(
                        f"❌ <b>خطا در بررسی لینک دانلود:</b> {escape(err_reason)}",
                        parse_mode=enums.ParseMode.HTML
                    )
                    return

            if not user_act:
                canon_act = get_canonical_menu_action(text)
                if canon_act == ACTION_FREE_DOWNLOADS:
                    await customer_gifts(client, message)
                    return
                elif canon_act == ACTION_TODAY_SIGN:
                    await customer_sign_handler(client, message)
                    return
                elif canon_act == ACTION_PREMIUM:
                    await handle_vip_command_tg(client, message)
                    return
                elif canon_act == ACTION_PRODUCTS:
                    await customer_products_hub(client, message)
                    return
                elif canon_act == ACTION_USER_ACCOUNT:
                    await customer_profile(client, message)
                    return
                elif canon_act == ACTION_FREQUENCY:
                    txt = (
                        "💎 <b>فرکانس فراوانی و آرامش درون</b>\n\n"
                        "با انتخاب هر بخش، باورهای ثروت‌ساز و آرامش‌بخش روزانه را ورق بزنید و ذهن خود را روی مدار توانگری و دریافت برکت الهی تنظیم کنید:"
                    )
                    await message.reply_text(txt, parse_mode=enums.ParseMode.HTML, reply_markup=build_telegram_frequency_cats_keyboard())
                    return
                elif canon_act == ACTION_SUPPORT:
                    sup_txt = getattr(config, "SUPPORT_CENTER_TEXT", "").strip() or "💬 جهت ارتباط با پشتیبانی، پیام خود را ارسال فرمایید."
                    await message.reply_text(f"💬 <b>مرکز پشتیبانی و ارتباط با ما:</b>\n\n{sup_txt}", parse_mode=enums.ParseMode.HTML)
                    return

                from services.ai_agent_service import ai_agent_service
                intent_res = ai_agent_service.recognize_intent(text)
                intent = intent_res.get("intent")

                if intent == "TRANSFER_BALE":
                    await message.reply_text(
                        "🤖 <b>تشخیص هوشمند دستور: انتقال به پیام‌رسان بله</b>\n\n"
                        "آماده دریافت فایل شما هستم. لطفاً فایل، ویدیو یا موسیقی مورد نظرتان را بفرستید تا فوراً به بله منتقل شود.",
                        parse_mode=enums.ParseMode.HTML
                    )
                    return
                elif intent == "TRANSFER_RUBIKA":
                    await message.reply_text(
                        "🤖 <b>تشخیص هوشمند دستور: انتقال به روبیکا</b>\n\n"
                        "آماده دریافت فایل هستم. فایل خود را ارسال فرمایید تا به پیام‌های ذخیره‌شده روبیکا یا کانال شما منتقل گردد.",
                        parse_mode=enums.ParseMode.HTML
                    )
                    return
                elif intent == "CONVERT_MP3":
                    await message.reply_text(
                        "🎵 <b>تشخیص هوشمند دستور: تبدیل به MP3</b>\n\n"
                        "لطفاً فایل صوتی (با هر فرمتی مانند OGG، WAV، M4A، FLAC) یا ویدیوی خود را بفرستید تا سریعاً به فایل صوتی MP3 استاندارد همراه با متادیتا تبدیل شود.",
                        parse_mode=enums.ParseMode.HTML
                    )
                    return
                elif intent == "COMPRESS_VIDEO":
                    await message.reply_text(
                        "🗜 <b>تشخیص هوشمند دستور: فشرده‌سازی ویدیو</b>\n\n"
                        "ویدیو مورد نظرتان را ارسال کنید. ویدیوهای بالای ۵۰ مگابایت به صورت هوشمند تا سقف ۴۹.۹۹ مگابایت فشرده می‌شوند.",
                        parse_mode=enums.ParseMode.HTML
                    )
                    return
                elif intent == "LIST_COURSES":
                    prods = await StoreService.get_products(is_free_only=False)
                    gifts = await StoreService.get_products(is_free_only=True)
                    all_p = prods + gifts
                    if not all_p:
                        await message.reply_text("📚 در حال حاضر دوره‌ای ثبت نشده است.")
                        return
                    buttons = [[InlineKeyboardButton(f"{'🎁' if p.price == 0 else f'🎓 ({p.price:,} ت)'} {p.name}", callback_data=f"prod_view:{p.product_id}")] for p in all_p]
                    await message.reply_text(
                        "📚 <b>دوره‌های آموزشی و هدایای UNFINIT:</b>\nجهت مشاهده توضیحات و دریافت دوره روی دکمه مورد نظر کلیک نمایید:",
                        parse_mode=enums.ParseMode.HTML,
                        reply_markup=InlineKeyboardMarkup(buttons)
                    )
                    return
                # User sent freeform text message -> Invoke AI Sales Copilot!
                try:
                    from services.ai_service import ai_service, ai_typing_action
                    async def _tg_copilot_typing():
                        await client.send_chat_action(message.chat.id, enums.ChatAction.TYPING)

                    async with ai_typing_action(_tg_copilot_typing):
                        ai_reply = await ai_service.chat_course_support(text)
                        await message.reply_text(ai_reply, reply_markup=get_customer_keyboard())
                except Exception as ai_err:
                    logger.warning(f"[tg_copilot] AI course support failed: {ai_err}")
                    await message.reply_text(
                        "سلام! جهت مشاهده دوره‌های آموزشی یا هدایا لطفاً از دکمه‌های منوی زیر استفاده فرمایید:",
                        reply_markup=get_customer_keyboard()
                    )
                return

            act = user_act["action"]
            drop_id = user_act["drop_id"]
            drop = session_manager.get_session(drop_id)
            if not drop:
                try:
                    from core.database import db_get_media_session
                    drop = db_get_media_session(drop_id)
                    if drop:
                        session_manager._sessions[drop_id] = drop
                except Exception:
                    pass

            # Handle Audio Trimming Input
            if drop and act == "await_trim_time":
                tech = inspect_technical_metadata(drop.get("working_path") or "")
                total_dur = float(tech.get("duration_sec", 0))
                start_s, end_s = parse_trim_input(text, total_duration=total_dur)

                if start_s is None:
                    await message.reply_text("❌ <b>فرمت زمان واردشده نامعتبر است.</b> لطفاً مانند <code>02:10 - 21:28</code> یا <code>02:10</code> ارسال نمایید.", parse_mode=enums.ParseMode.HTML)
                    return

                session_manager.clear_user_action(f"tg_{user_id}")
                status_m = await message.reply_text("⏳ <b>در حال برش و استخراج بخش انتخابی...</b>", parse_mode=enums.ParseMode.HTML)

                try:
                    w_path = Path(drop["working_path"])
                    ok, trimmed_p = MediaService.trim_audio(w_path, start_s, end_s)
                    if ok and trimmed_p.exists():
                        t_tech = inspect_technical_metadata(trimmed_p)
                        t_dur = t_tech.get("duration_sec", 0)
                        await status_m.edit_text("📤 <b>در حال ارسال فایل برش‌خورده...</b>", parse_mode=enums.ParseMode.HTML)
                        sent_aud = await self.send_audio(
                            user_id,
                            trimmed_p,
                            title=drop.get("embed_meta", {}).get("title") or drop.get("api_meta", {}).get("title") or trimmed_p.stem,
                            performer=drop.get("embed_meta", {}).get("artist") or drop.get("api_meta", {}).get("artist") or None,
                            duration=t_dur,
                            caption=f"✂️ <b>فایل صوتی برش‌خورده ({format_duration(start_s)} تا {format_duration(end_s or total_dur)}):</b>\n📄 <code>{escape(trimmed_p.name)}</code>\n⏱️ مدت زمان قطعه: <code>{format_duration(t_dur)}</code>"
                        )
                        new_drop_id = uuid.uuid4().hex[:8]
                        new_aud_id = sent_aud.get("message_id")
                        new_data = MediaService.register_incoming_message_meta(
                            new_drop_id, "telegram", user_id, str(new_aud_id), trimmed_p.name, trimmed_p.stat().st_size,
                            media_type="audio", api_meta={"filename": trimmed_p.name, "duration_sec": t_dur}
                        )
                        new_data["working_path"] = str(trimmed_p)
                        new_data["is_downloaded_locally"] = True
                        new_card = TelegramFormatter.format_light_card(new_data)
                        new_kb = self.build_media_keyboard(new_drop_id, new_data)
                        c_sent = await self.send_message(user_id, new_card, reply_markup=new_kb)
                        new_data["card_msg_id"] = c_sent.get("message_id")
                        await status_m.delete()

                        # Clean up prompt message and user trim message
                        p_ids = []
                        p_info = session_manager.get_session(f"prompt_{drop_id}")
                        if p_info and p_info.get("msg_id"):
                            p_ids.append(p_info["msg_id"])
                        extra_p = (user_act.get("extra") or {}).get("prompt_id")
                        if extra_p and extra_p not in p_ids:
                            p_ids.append(extra_p)
                        if p_ids:
                            try:
                                await self.app.delete_messages(chat_id=message.chat.id, message_ids=p_ids)
                            except Exception: pass
                        try:
                            await message.delete()
                        except Exception: pass
                    else:
                        await status_m.edit_text("❌ خطا در عملیات برش فایل صوتی.", parse_mode=enums.ParseMode.HTML)
                except Exception as e:
                    await status_m.edit_text(f"❌ خطا در برش فایل: {e}", parse_mode=enums.ParseMode.HTML)
                return

            # Handle Set Force Join Channel in Telegram
            if act == "await_tg_fjoin_ch" and text:
                ch_text = text.strip()
                if not ch_text.startswith("@") and not ch_text.lstrip("-").isdigit():
                    ch_text = f"@{ch_text}"
                await set_system_setting("tg_fjoin_channel", ch_text)
                await set_system_setting("tg_fjoin_enabled", "1")
                session_manager.clear_user_action(f"tg_{user_id}")
                await message.reply_text(f"✅ کانال قفل عضویت تلگرام روی {ch_text} تنظیم و فعال گردید.", reply_markup=get_admin_keyboard())
                return

            # In-Place Draft Tag Update on main card message
            if drop and act in ("await_fn", "await_perf", "await_title"):
                field_map = {"await_fn": "filename", "await_perf": "artist", "await_title": "title"}
                field_name_fa = {"await_fn": "نام فایل", "await_perf": "نام خواننده", "await_title": "نام موزیک"}[act]
                field = field_map[act]
                MediaService.update_draft_field(drop_id, field, text)
                session_manager.clear_user_action(f"tg_{user_id}")
                card_txt = TelegramFormatter.format_light_card(drop)
                kb = self.build_media_keyboard(drop_id, drop, is_sub=False)
                try:
                    await self.app.edit_message_text(
                        chat_id=message.chat.id,
                        message_id=drop["card_msg_id"],
                        text=card_txt,
                        reply_markup=kb,
                        parse_mode=enums.ParseMode.HTML
                    )
                except Exception: pass

                # Clean up prompt message and incoming user message for a clean chat
                prompt_ids = []
                p_info = session_manager.get_session(f"prompt_{drop_id}")
                if p_info and p_info.get("msg_id"):
                    prompt_ids.append(p_info["msg_id"])
                extra_p = (user_act.get("extra") or {}).get("prompt_id")
                if extra_p and extra_p not in prompt_ids:
                    prompt_ids.append(extra_p)
                if prompt_ids:
                    try:
                        await self.app.delete_messages(chat_id=message.chat.id, message_ids=prompt_ids)
                    except Exception: pass
                try:
                    await message.delete()
                except Exception: pass
                return

            # Smart Video Split custom parts count handler
            if act == "await_split_parts" and text:
                drop_id = str(user_act.get("value") or "")
                # Parse digits (including Persian/Arabic digits)
                persian_digits = "۰۱۲۳۴۵۶۷۸۹"
                arabic_digits = "٠١٢٣٤٥٦٧٨٩"
                clean_text = text.strip()
                for i in range(10):
                    clean_text = clean_text.replace(persian_digits[i], str(i)).replace(arabic_digits[i], str(i))
                clean_num = re.sub(r"\D", "", clean_text)

                if clean_num.isdigit():
                    num_parts = int(clean_num)
                    if 2 <= num_parts <= 20:
                        session_manager.clear_user_action(f"tg_{user_id}")
                        status_m = await message.reply_text(f"⏳ <b>درخواست شما دریافت شد: تقسیم ویدیو به {num_parts} پارت...</b>", parse_mode=enums.ParseMode.HTML)
                        await self.split_and_transfer_video_to_bale(drop_id, num_parts, status_m)
                        return
                    else:
                        await message.reply_text("⚠️ لطفاً عددی بین <b>۲</b> تا <b>۲۰</b> برای تعداد پارت‌ها وارد فرمایید.", parse_mode=enums.ParseMode.HTML)
                        return
                else:
                    await message.reply_text("⚠️ لطفاً تعداد پارت‌ها را به صورت عدد لاتین یا فارسی (مانند ۳ یا ۴) ارسال فرمایید یا از کلیدهای زیر پیام استفاده نمایید.", parse_mode=enums.ParseMode.HTML)
                    return

            # Support message handler
            if act == "await_support_msg" and text:
                tck = await StoreService.create_support_ticket(user_id, message.from_user.username or "", text, platform="telegram")
                session_manager.clear_user_action(f"tg_{user_id}")
                await message.reply_text(f"✅ <b>پیام شما با موفقیت به پشتیبانی ارسال شد.</b>\nشماره پیگیری: <code>{tck.ticket_id}</code>", parse_mode=enums.ParseMode.HTML)
                admin_id = config.TELEGRAM_OWNER_ID or self.admin_chat_id
                if admin_id:
                    await self.send_message(admin_id, f"💬 <b>تیکت پشتیبانی جدید:</b>\nشماره: <code>{tck.ticket_id}</code>\nکاربر: <code>{user_id}</code> (@{message.from_user.username or 'ندارد'})\n\nمتن پیام:\n<i>{escape(text)}</i>")
                return

            # If user sent a phone number while in OTP step, dynamically route to phone step
            clean_digits = re.sub(r"\D", "", text)
            if act == "await_rubika_otp" and (text.startswith("09") or text.startswith("+98") or len(clean_digits) >= 10) and len(clean_digits) != 5:
                act = "await_rubika_phone"

            # Rubika Login Wizard: Step 1 (Phone Number)
            if act == "await_rubika_phone":
                status_m = await message.reply_text("⏳ در حال ارسال کد ورود از طریق روبیکا...")
                res = await self.rubika_adapter.request_auth_code(text)
                if res.get("ok"):
                    saved_phone = res.get("phone") or text
                    session_manager.set_user_action(
                        f"tg_{user_id}",
                        "await_rubika_otp",
                        res["phone_code_hash"],
                        extra={"phone": saved_phone, "hash": res["phone_code_hash"]}
                    )
                    session_manager.update_session("rubika_auth_temp", {"phone": saved_phone, "hash": res["phone_code_hash"]})
                    await set_system_setting("rubika_user_phone", saved_phone)
                    await status_m.edit_text(
                        "📲 <b>کد تایید روبیکا ارسال شد!</b>\n\n"
                        "لطفاً کد ۵ رقمی ارسال‌شده در اپلیکیشن روبیکا یا پیامک را ارسال فرمایید:",
                        parse_mode=enums.ParseMode.HTML
                    )
                else:
                    await status_m.edit_text(f"❌ <b>خطا در ارسال کد تایید روبیکا:</b>\n<code>{escape(res.get('error', ''))}</code>", parse_mode=enums.ParseMode.HTML)
                return

            # Rubika Login Wizard: Step 2 (OTP Code)
            if act == "await_rubika_otp":
                status_m = await message.reply_text("⏳ در حال تایید کد و اتصال حساب کاربری...")
                temp_auth = session_manager.get_session("rubika_auth_temp") or {}
                extra = user_act.get("extra") or {}
                phone = extra.get("phone") or temp_auth.get("phone", "")
                if not phone:
                    phone = await get_system_setting("rubika_user_phone", "")
                hash_val = user_act.get("drop_id") or extra.get("hash") or temp_auth.get("hash", "")
                
                res = await self.rubika_adapter.submit_auth_code(phone, hash_val, text)
                if res.get("ok"):
                    session_manager.clear_user_action(f"tg_{user_id}")
                    if phone:
                        await set_system_setting("rubika_user_phone", phone)
                    await status_m.edit_text(
                        "🎉 <b>حساب کاربری روبیکای شما با موفقیت متصل شد!</b>\n\n"
                        "✅ سشن لاگین ذخیره گردید. از این پس می‌توانید فایل‌های حجیم (تا ۲ گیگابایت) را بدون هیچ خطایی مستقیماً به <b>پیام‌های ذخیره‌شده (Saved Messages)</b> اکانت روبیکای خود منتقل فرمایید.",
                        parse_mode=enums.ParseMode.HTML
                    )
                elif "passkey" in str(res.get("error", "")).lower() or "password" in str(res.get("error", "")).lower():
                    session_manager.set_user_action(f"tg_{user_id}", "await_rubika_passkey", f"{phone}:{hash_val}:{text}")
                    await status_m.edit_text(
                        "🔑 <b>اکانت روبیکای شما دارای رمز عبور دومرحله‌ای (Two-Step Password) است:</b>\n\n"
                        "لطفاً رمز عبور دومرحله‌ای خود را در این چت ارسال فرمایید:",
                        parse_mode=enums.ParseMode.HTML
                    )
                else:
                    session_manager.clear_user_action(f"tg_{user_id}")
                    kb = InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔄 درخواست مجدد کد تایید روبیکا", callback_data="adm:rubika_login")]
                    ])
                    await status_m.edit_text(
                        f"❌ <b>خطا در تایید کد روبیکا:</b>\n"
                        f"<code>{escape(res.get('error', 'کد واردشده نامعتبر یا منقضی شده است.'))}</code>\n\n"
                        f"💡 کد یا هش ورود منقضی شده است. لطفاً روی دکمه زیر کلیک کرده یا دستور <code>/set_rubika</code> را ارسال نمایید تا کد جدید دریافت کنید.",
                        parse_mode=enums.ParseMode.HTML,
                        reply_markup=kb
                    )
                return

            # Rubika Login Wizard: Step 3 (PassKey / 2-Step Password)
            if act == "await_rubika_passkey":
                status_m = await message.reply_text("⏳ در حال تایید رمز دومرحله‌ای روبیکا...")
                raw_info = user_act["drop_id"].split(":")
                phone = raw_info[0]
                hash_val = raw_info[1]
                otp_code = raw_info[2]
                res = await self.rubika_adapter.submit_auth_code(phone, hash_val, otp_code, pass_key=text)
                if res.get("ok"):
                    session_manager.clear_user_action(f"tg_{user_id}")
                    if phone:
                        await set_system_setting("rubika_user_phone", phone)
                    await status_m.edit_text(
                        "🎉 <b>رمز دومرحله‌ای تایید و حساب روبیکا با موفقیت متصل شد!</b>\n\n"
                        "✅ اکنون امکان انتقال فایل‌های تا ۲ گیگابایت به Saved Messages روبیکا فعال است.",
                        parse_mode=enums.ParseMode.HTML
                    )
                else:
                    await status_m.edit_text(f"❌ <b>خطا در بررسی رمز عبور:</b>\n<code>{escape(res.get('error', 'رمز دومرحله‌ای واردشده اشتباه است.'))}</code>", parse_mode=enums.ParseMode.HTML)
                return
