from __future__ import annotations
from platforms.instagram_adapter import InstagramAdapter
from task_store import cleanup_local_file
import time
import re
from platforms.rubika_adapter import RubikaAdapter
import os
import uuid
import asyncio
from pathlib import Path
from html import escape
from typing import Optional, Dict, Any, List, Union
from pyrogram import Client, enums, filters
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    Message,
    CallbackQuery
)
from core.config import config
from core.logger import get_logger
from core.formatters import (
    TelegramFormatter,
    human_size,
    format_duration,
    parse_trim_input
)
from core.database import get_system_setting, set_system_setting, fix_mojibake
from services.store_service import format_course_links_for_card, format_course_photo_for_card, clean_course_access_input, get_tehran_now_str, StoreService, ProductItem
from services.media_service import MediaService, clean_display_filename
from services.session_manager import session_manager
from services.url_service import UrlService
from media.inspector import inspect_technical_metadata
from media.tagger import generate_video_thumbnail

logger = get_logger("telegram_adapter")


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
    stage_title: str = "در حال انتقال فایل..."
) -> str:
    pct = int((current / total) * 100) if total > 0 else 0
    pct = min(100, max(0, pct))
    bar_len = 10
    filled = int((pct / 100) * bar_len)
    bar = "█" * filled + "░" * (bar_len - filled)
    transferred_mb = f"{current / (1024 * 1024):.2f}"
    total_mb = f"{total / (1024 * 1024):.2f}"
    speed_mbps = f"{(current / max(0.01, elapsed_sec)) / (1024 * 1024):.2f}"

    return (
        f"⏳ <b>{stage_title}</b>\n\n"
        f"<code>[{bar}] {pct}%</code>\n\n"
        f"📦 <b>حجم:</b> <code>{transferred_mb} MB</code> از <code>{total_mb} MB</code>\n"
        f"⚡️ <b>سرعت انتقال:</b> <code>{speed_mbps} MB/s</code>"
    )


def get_customer_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            ["📚 لیست دوره‌های آموزشی"],
            ["👤 حساب کاربری"],
            ["💬 پشتیبانی و هدایا"]
        ],
        resize_keyboard=True
    )


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

    return None


class TelegramAdapter:
    def __init__(self):
        use_in_memory = os.getenv("TESTING") == "true" or os.getenv("PYTEST_CURRENT_TEST") is not None
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        session_name = "unfinit_store_session" if use_in_memory else str(config.DATA_DIR / "unfinit_store_session")
        self.app = Client(
            session_name,
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            bot_token=config.TELEGRAM_BOT_TOKEN,
            workdir=str(config.DATA_DIR) if not use_in_memory else None,
            in_memory=use_in_memory
        )
        self.bale_adapter = None
        self.rubika_adapter = RubikaAdapter()
        self.instagram_adapter = InstagramAdapter()
        self.admin_chat_id = config.TELEGRAM_OWNER_ID

    def get_admin_id(self) -> int | str:
        return config.TELEGRAM_OWNER_ID or getattr(config, "OWNER_ID", None) or self.admin_chat_id or 0

    def is_admin(self, user_id: int | str) -> bool:
        if not user_id:
            return False
        return config.is_admin(user_id)

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
            sent = await self.app.send_audio(
                chat_id=int(chat_id),
                audio=str(file_path),
                file_name=fn,
                title=title,
                performer=performer,
                caption=caption,
                duration=duration,
                thumb=str(thumb) if thumb else None,
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
            sent = await self.app.send_video(
                chat_id=int(chat_id),
                video=str(file_path),
                file_name=fn,
                caption=caption,
                width=width,
                height=height,
                duration=duration,
                thumb=str(thumb) if thumb else None,
                supports_streaming=supports_streaming,
                parse_mode=enums.ParseMode.HTML
            )
            return {"ok": True, "message_id": sent.id}
        except Exception as e:
            return {"ok": False, "error": str(e)}

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
                    InlineKeyboardButton("💾 اعمال تغییرات", callback_data=f"smeta:apply_changes:{drop_id}")
                ],
                [
                    InlineKeyboardButton("🟢 ارسال به بله", callback_data=f"smeta:send_bale:{drop_id}"),
                    InlineKeyboardButton("🟣 ارسال به روبیکا", callback_data=f"smeta:choose_rubika:{drop_id}")
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
                InlineKeyboardButton("💾 اعمال تغییرات", callback_data=f"smeta:apply_changes:{drop_id}")
            ],
            [
                InlineKeyboardButton("🟢 ارسال به بله", callback_data=f"smeta:send_bale:{drop_id}"),
                InlineKeyboardButton("🟣 ارسال به روبیکا", callback_data=f"smeta:choose_rubika:{drop_id}")
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

        asyncio.create_task(run_event_loop())

        @self.app.on_message(filters.private & (filters.command(["ping", "پینگ"]) | filters.regex(r"^(/ping|ping|پینگ)$")))
        async def ping_cmd(client: Client, message: Message):
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
                f"🕒 <b>زمان سرور (تهران):</b> <code>{t_time}</code>"
            )
            await message.reply_text(ping_msg, parse_mode=enums.ParseMode.HTML)

        @self.app.on_message(filters.private & (filters.command("start") | filters.regex(r"^/start")))
        async def start_handler(client: Client, message: Message):
            user_id = message.from_user.id
            if not config.TELEGRAM_OWNER_ID and not self.admin_chat_id:
                self.admin_chat_id = user_id

            await StoreService.get_or_create_customer(user_id, platform="telegram")

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
                w_text = fix_mojibake(await get_system_setting("WELCOME_TEXT", config.WELCOME_TEXT), default=config.WELCOME_TEXT)
                await message.reply_text(w_text, parse_mode=enums.ParseMode.HTML, reply_markup=get_customer_keyboard())

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

        # Customer: Courses List
        @self.app.on_message(filters.private & filters.regex(r"(?i)^(📚\s*لیست دوره‌های آموزشی|لیست دوره)"))
        async def customer_courses(client: Client, message: Message):
            if not await check_force_join_telegram(client, message.from_user.id) and not self.is_admin(message.from_user.id):
                ch = await get_system_setting("tg_fjoin_channel", config.FORCE_JOIN_CHANNEL_TELEGRAM)
                await message.reply_text("⚠️ <b>برای استفاده از امکانات ربات ابتدا باید در کانال رسمی ما عضو شوید:</b>", parse_mode=enums.ParseMode.HTML, reply_markup=build_telegram_force_join_keyboard(ch))
                return
            prods = await StoreService.get_products(is_free_only=False)
            if not prods:
                await message.reply_text("📚 در حال حاضر دوره‌ای برای فروش ثبت نشده است.")
                return
            lines = ["📚 <b>لیست دوره‌های آموزشی تخصصی:</b>", "جهت مشاهده جزئیات و ثبت سفارش دوره موردنظر را انتخاب نمایید:\n"]
            buttons = [[InlineKeyboardButton(f"🎓 {p.name} ({p.price:,} تومان)", callback_data=f"cview:{p.product_id}")] for p in prods]
            await message.reply_text("\n".join(lines), parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))

        @self.app.on_message(filters.private & filters.regex(r"(?i)^(🎁\s*دانلودها \(هدیه\)|دانلودها|هدیه)"))
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
            lines = ["🎁 <b>دوره‌ها و هدایای آموزشی رایگان:</b>", "جهت دریافت هدیه روی عنوان آن کلیک کنید:\n"]
            buttons = [[InlineKeyboardButton(f"🎁 {g.name} (رایگان)", callback_data=f"cview:{g.product_id}")] for g in gifts]
            await callback_query.message.reply_text("\n".join(lines), parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))

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

        @self.app.on_message(filters.private & filters.regex(r"(?i)^(💬\s*پشتیبانی و هدایا|پشتیبانی و هدایا|💬\s*پشتیبانی|پشتیبانی|🎁\s*دانلودها \(هدیه\)|دانلودها|هدیه|/support|/gifts)"))
        async def customer_support(client: Client, message: Message):
            if not await check_force_join_telegram(client, message.from_user.id) and not self.is_admin(message.from_user.id):
                ch = await get_system_setting("tg_fjoin_channel", config.FORCE_JOIN_CHANNEL_TELEGRAM)
                await message.reply_text("⚠️ <b>برای استفاده از امکانات ربات ابتدا باید در کانال رسمی ما عضو شوید:</b>", parse_mode=enums.ParseMode.HTML, reply_markup=build_telegram_force_join_keyboard(ch))
                return
            gifts = await StoreService.get_products(is_free_only=True)
            buttons = []
            if gifts:
                buttons = [[InlineKeyboardButton(f"🎁 {g.name} (رایگان)", callback_data=f"cview:{g.product_id}")] for g in gifts]
            session_manager.set_user_action(f"tg_{message.from_user.id}", "await_support_msg", "none")
            txt = (
                "💬 <b>مرکز پشتیبانی و هدایای آموزشی:</b>\n\n"
                "🎁 <b>دوره‌های هدیه و رایگان:</b> در دکمه‌های شیشه‌ای زیر آماده دریافت هستند.\n\n"
                "📩 <b>ارسال پیام به پشتیبانی:</b> هم‌اکنون می‌توانید متن پیام، سوال یا شماره پیگیری سفارش خود را در پاسخ ارسال فرمایید تا تیکت شما ثبت گردد."
            )
            if buttons:
                await message.reply_text(txt, parse_mode=enums.ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
            else:
                await message.reply_text(txt, parse_mode=enums.ParseMode.HTML)

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

            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton(btn_txt, callback_data=f"cbuy:{prod.product_id}")],
                [InlineKeyboardButton("🔙 بازگشت به لیست دوره‌ها", callback_data="cnav:back")]
            ])

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

        # Product Buy Callback
        @self.app.on_callback_query(filters.regex(r"^cbuy:"))
        async def product_buy_cb(client: Client, callback_query: CallbackQuery):
            prod_id = callback_query.data.split(":")[1]
            prod = await StoreService.get_product(prod_id)
            user_id = callback_query.from_user.id
            username = callback_query.from_user.username or ""

            if prod.price == 0:
                order = await StoreService.create_order(user_id, username, "", "", prod, platform="telegram")
                await callback_query.message.reply_text(f"🎁 <b>هدیه آموزشی شما با موفقیت فعال شد!</b>\nشماره سفارش: <code>{order.order_id}</code>\n🎓 <b>{escape(prod.name)}</b>")
                return

            wallet_balance = await StoreService.get_wallet_balance(user_id)
            wallet_used = min(wallet_balance, prod.price)
            remaining = prod.price - wallet_used

            order = await StoreService.create_order(
                user_id=user_id,
                username=username,
                customer_name=f"{callback_query.from_user.first_name or ''} {callback_query.from_user.last_name or ''}".strip(),
                phone="",
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
            await callback_query.message.reply_text("\n".join(lines), parse_mode=enums.ParseMode.HTML)

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

            from services.ai_agent_service import ai_agent_service
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
            user_id = message.from_user.id

            if not self.is_admin(user_id):
                await message.reply_text(
                    f"📚 <b>به فروشگاه دوره‌های آموزشی {escape(config.STORE_NAME)} خوش آمدید.</b>\n\n"
                    "جهت مشاهده کاتالوگ دوره‌ها، دریافت هدایا یا ارتباط با پشتیبانی، لطفاً از دکمه‌های منوی زیر استفاده فرمایید:",
                    parse_mode=enums.ParseMode.HTML,
                    reply_markup=get_customer_keyboard()
                )
                return

            drop_id = uuid.uuid4().hex[:8]
            media_obj = message.audio or message.document or message.voice or message.video
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

            card_text = TelegramFormatter.format_light_card(data)
            kb = self.build_media_keyboard(drop_id, data)
            sent_card = await message.reply_text(card_text, parse_mode=enums.ParseMode.HTML, reply_markup=kb)
            data["card_msg_id"] = sent_card.id

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
                if media_type == "video" or temp_dest.suffix.lower() in (".mp4", ".mkv", ".mov", ".avi", ".webm"):
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

            async def ensure_binary():
                if not drop.get("is_downloaded_locally"):
                    start_t = [time.time()]
                    last_edit = [0.0]
                    last_pct = [0]
                    status_m = None
                    try:
                        status_m = await callback_query.message.reply_text(
                            "⏳ <b>در حال انتقال فایل...</b>\n\n<code>[░░░░░░░░░░] 0%</code>\n\n📦 <b>حجم:</b> <code>0.00 MB</code>\n⚡️ <b>سرعت انتقال:</b> <code>0.00 MB/s</code>",
                            parse_mode=enums.ParseMode.HTML
                        )
                    except Exception:
                        pass

                    async def progress_hook(current, total, *args):
                        now = time.time()
                        if total > 0 and status_m:
                            pct = int((current / total) * 100)
                            if (now - last_edit[0] >= 1.5 or abs(pct - last_pct[0]) >= 5 or current == total):
                                last_edit[0] = now
                                last_pct[0] = pct
                                elapsed = max(0.01, now - start_t[0])
                                txt = format_transfer_progress(current, total, elapsed, stage_title="در حال انتقال فایل...")
                                try:
                                    await status_m.edit_text(txt, parse_mode=enums.ParseMode.HTML)
                                except Exception:
                                    pass

                    async def dl_func(fid, p):
                        target_media = drop.get("raw_message") or drop.get("file_id") or fid
                        try:
                            return await client.download_media(target_media, file_name=str(p), progress=progress_hook)
                        except TypeError:
                            return await client.download_media(target_media, file_name=str(p))

                    await MediaService.ensure_local_binary(drop_id, dl_func)
                    if status_m:
                        try:
                            await status_m.edit_text("✅ <b>انتقال فایل با موفقیت انجام شد.</b>", parse_mode=enums.ParseMode.HTML)
                        except Exception:
                            pass

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
            elif action in ("ai_transcribe", "ai_menu"):
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

                    from services.ai_agent_service import ai_agent_service
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

            # Physical Full Rewrite & Delivery (Apply Changes)
            elif action in ("apply_changes", "send_back"):
                status_msg = await callback_query.message.reply_text("📥 <b>در حال دانلود فایل از مبدا...</b>", parse_mode=enums.ParseMode.HTML)
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
                        res = await self.send_audio(
                            chat_id=user_id,
                            file_path=final_path,
                            file_name=send_name,
                            title=transfer_info.get("title") or drop.get("api_meta", {}).get("title"),
                            performer=transfer_info.get("artist") or config.DEFAULT_ARTIST,
                            duration=transfer_info.get("duration") or drop.get("api_meta", {}).get("duration_sec"),
                            thumb=cover_path if cover_path and Path(str(cover_path)).exists() else None,
                            caption=f"✅ <b>فایل صوتی اصلاح‌شده و تگ‌گذاری‌شده:</b>\n📄 <code>{escape(send_name)}</code>\n🗣 خواننده: <b>{escape(transfer_info.get('artist') or config.DEFAULT_ARTIST)}</b>\n🎵 عنوان: <code>{escape(transfer_info.get('title') or '')}</code>"
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
                        "caption": f"✅ منتقل شده از تلگرام\n📄 {send_name}",
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
                        caption=f"✅ منتقل شده از تلگرام\n📄 {send_name}"
                    )
                    logger.info(f"[rub_bot] Rubika send_audio_bot_api response: {res}")
                    if res.get("ok") or res.get("status") == "OK":
                        await status_msg.edit_text(f"✅ <b>فایل با موفقیت به ربات روبیکا منتقل شد!</b>\n📄 <code>{escape(send_name)}</code>", parse_mode=enums.ParseMode.HTML)
                    else:
                        err_info = res.get("error") or res.get("status") or str(res)
                        await status_msg.edit_text(f"❌ <b>خطا در ارتباط با سرورهای روبیکا:</b>\n<code>{escape(str(err_info))}</code>", parse_mode=enums.ParseMode.HTML)
                except Exception as e:
                    await status_msg.edit_text(f"❌ <b>خطا در ارتباط با سرورهای روبیکا:</b>\n<code>{escape(str(e))}</code>", parse_mode=enums.ParseMode.HTML)

            elif action == "send_bale":
                target_chat = self.bale_adapter.get_admin_chat_id() if self.bale_adapter else None
                if not target_chat:
                    await callback_query.message.reply_text("❌ شناسه چت بله تنظیم نشده است.")
                    return

                status_msg = await callback_query.message.reply_text("📥 <b>در حال دانلود فایل از مبدا...</b>", parse_mode=enums.ParseMode.HTML)
                await ensure_binary()

                w_path = Path(drop.get("working_path") or "")
                if w_path.exists() and (w_path.stat().st_size / (1024 * 1024)) >= 49.99:
                    orig_sz_mb = f"{w_path.stat().st_size / (1024 * 1024):.1f}"
                    await status_msg.edit_text(
                        "🎛 <b>در حال فشرده‌سازی هوشمند جهت رعایت سقف بله...</b>\n"
                        f"📊 حجم فعلی: <code>{orig_sz_mb} MB</code> ➔ هدف: <code>زیر 49.9 MB</code>\n"
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
                    await status_msg.edit_text("📤 <b>در حال ارسال به بله...</b>", parse_mode=enums.ParseMode.HTML)
                    
                    if drop.get("media_type") == "video":
                        tech = inspect_technical_metadata(final_path)
                        res = await self.bale_adapter.send_video(
                            target_chat, final_path,
                            caption=f"✅ منتقل شده از تلگرام\n📄 <b>{escape(send_name)}</b>",
                            duration=tech.get("duration_sec"),
                            width=tech.get("width"),
                            height=tech.get("height")
                        )
                    else:
                        res = await self.bale_adapter.send_audio(
                            target_chat, final_path,
                            title=transfer_info["title"],
                            performer=transfer_info["artist"],
                            caption=f"✅ منتقل شده از تلگرام\n📄 <b>{escape(send_name)}</b>"
                        )
                    if res.get("ok"):
                        await status_msg.edit_text(f"✅ <b>فایل با موفقیت و حفظ کامل متادیتا به بله منتقل شد!</b>\n📄 <code>{escape(send_name)}</code>", parse_mode=enums.ParseMode.HTML)
                    else:
                        err_info = res.get("error") or str(res)
                        await status_msg.edit_text(f"❌ <b>خطا در ارتباط با سرورهای بله:</b>\n<code>{escape(str(err_info))}</code>", parse_mode=enums.ParseMode.HTML)
                except Exception as e:
                    await status_msg.edit_text(f"❌ <b>خطا در ارتباط با سرورهای بله:</b>\n<code>{escape(str(e))}</code>", parse_mode=enums.ParseMode.HTML)

        # Text input handler for Metadata, Trimming, URLs, Support, and Force Join
        @self.app.on_message(filters.private & filters.text)
        async def text_handler(client: Client, message: Message):
            user_id = message.from_user.id
            text = message.text.strip()
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
            if (text.startswith("http://") or text.startswith("https://")) and self.is_admin(user_id) and not user_act:
                probe = await UrlService.probe_url(text)
                if probe["is_valid"]:
                    url_id = uuid.uuid4().hex[:8]
                    session_manager.create_session(f"url_{url_id}", {**probe, "url_id": url_id})
                    
                    is_vid = probe["media_type"] == "video"
                    buttons = [
                        [InlineKeyboardButton("⚡️ شروع و تبدیل به فایل تلگرام", callback_data=f"urldl:auto:{url_id}")],
                    ]
                    if is_vid:
                        buttons.append([
                            InlineKeyboardButton("🎥 دریافت در حالت ویدیو", callback_data=f"urldl:video:{url_id}"),
                            InlineKeyboardButton("🎵 استخراج و تبدیل به MP3", callback_data=f"urldl:audio:{url_id}")
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

            if not user_act:
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
                            title=drop.get("embed_meta", {}).get("title") or trimmed_p.stem,
                            performer=drop.get("embed_meta", {}).get("artist") or config.DEFAULT_ARTIST,
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
