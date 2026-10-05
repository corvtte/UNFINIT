# -*- coding: utf-8 -*-
"""
ماژول اختصاصی «نشانه امروز من» (My Today Sign Lead Magnet)
این ماژول بر مبنای شناسه کاربری و تاریخ جاری (هر ۲۴ ساعت یکبار)،
یک فایل صوتی آرامش‌بخش و اختصاصی را به صورت پایدار و قطعی (Deterministic)
از میان ۳۹ صفحه فایل‌های دانلودی سایت انتخاب کرده و در اختیار کاربر قرار می‌دهد.
دارای سیستم کش محلی جهت محافظت از سرور سایت و ممانعت از ارسال ریکوئست‌های تکراری.
"""

import hashlib
import json
import logging
import time
import urllib.parse
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from core.config import config
from services.feed_scraper import get_latest_free_downloads, FALLBACK_ITEMS

logger = logging.getLogger("sign_service")

# منطقه زمانی رسمی تهران (UTC+3:30)
TEHRAN_TZ = timezone(timedelta(hours=3, minutes=30))


class SignService:
    """
    سرویس مدیریت لید مگنت «نشانه امروز من».
    وظایف:
    ۱. انتخاب پایدار و هش‌محور فایل صوتی برای هر کاربر در هر روز تقویمی (۲۴ ساعت)
    ۲. مدیریت کش ذخیره‌سازی محلی در data/sign_cache
    ۳. ساخت پیام‌ها و متن‌های آرامش‌بخش و معنوی همراه با نشانه
    """

    CACHE_DIR: Path = config.DATA_DIR / "sign_cache"
    INDEX_FILE: Path = config.DATA_DIR / "sign_cache" / "user_signs.json"
    ABASMANESH_ARCHIVE_URL: str = "https://abasmanesh.com/fa/articles/"

    @classmethod
    def _ensure_storage(cls) -> None:
        """ایجاد دایرکتوری کش در صورت عدم وجود."""
        cls.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        if not cls.INDEX_FILE.exists():
            try:
                cls.INDEX_FILE.write_text(json.dumps({}, ensure_ascii=False), encoding="utf-8")
            except Exception as e:
                logger.warning(f"[sign_service] Failed to init index file: {e}")

    @classmethod
    def get_tehran_today_str(cls) -> str:
        """
        دریافت تاریخ امروز به وقت تهران با فرمت YYYY-MM-DD.
        خروجی:
            str: رشته تاریخ جاری تهران (مثلاً '2026-09-19')
        """
        now = datetime.now(TEHRAN_TZ)
        return now.strftime("%Y-%m-%d")

    @classmethod
    def _load_user_cache(cls) -> Dict[str, Any]:
        """بارگذاری کش نشانه‌های کاربران از فایل دیسک."""
        cls._ensure_storage()
        try:
            if cls.INDEX_FILE.exists():
                text = cls.INDEX_FILE.read_text(encoding="utf-8").strip()
                if text:
                    return json.loads(text)
        except Exception as e:
            logger.debug(f"[sign_service] Error reading cache file: {e}")
        return {}

    @classmethod
    def _save_user_cache(cls, data: Dict[str, Any]) -> None:
        """ذخیره امن کش نشانه‌های کاربران روی دیسک."""
        cls._ensure_storage()
        try:
            cls.INDEX_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error(f"[sign_service] Error writing cache file: {e}")

    @classmethod
    async def get_user_today_sign(
        cls,
        user_id: int | str,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """
        دریافت نشانه اختصاصی ۲۴ ساعته کاربر.
        این متد با ترکیب شناسه کاربری و تاریخ امروز تهران، هش پایدار تولید کرده
        و در تمام طول ۲۴ ساعت همان روز، دقیقاً همان فایل صوتی را بازمی‌گرداند.

        ورودی‌ها:
            user_id (int | str): شناسه عددی یا رشته‌ای کاربر
            force_refresh (bool): نادیده گرفتن کش در صورت نیاز ادمین

        خروجی:
            Dict[str, Any]: اطلاعات نشانه شامل title, audio_url, page_url, tag, cover_url, date
        """
        # ۱. استخراج شناسه یکتا بر اساس شماره همراه کاربر (قانون دوقلوهای همسان بله و تلگرام)
        unified_id = str(user_id).strip()
        try:
            from services.user_service import UserService
            u = UserService.get_user_by_any_id(user_id)
            if u and u.phone:
                unified_id = f"phone_{u.phone}"
        except Exception:
            pass

        uid = unified_id
        today = cls.get_tehran_today_str()
        cache = cls._load_user_cache()

        user_entry = cache.get(uid) or {}
        cached_sign = user_entry.get("sign")
        if (
            not force_refresh
            and user_entry.get("date") == today
            and cached_sign
            and (cached_sign.get("audio_url") or cached_sign.get("video_url"))
            and cached_sign.get("lesson_text")
        ):
            if not cached_sign.get("created_at"):
                cached_sign["created_at"] = user_entry.get("created_at") or user_entry.get("updated_at") or time.time()
            logger.debug(f"[sign_service] Serving cached sign for user {uid} on {today}")
            return cached_sign

        # ۲. محاسبه هش پایدار بر مبنای User ID یا شماره همراه یکتا و تاریخ روز
        seed_str = f"unfinit_sign_{uid}_{today}"
        hash_digest = hashlib.sha256(seed_str.encode("utf-8")).hexdigest()
        hash_int = int(hash_digest, 16)

        # ۳. نگاشت به شماره صفحه (۱ تا ۳۹)
        target_page = (hash_int % 39) + 1

        logger.info(f"[sign_service] Selecting deterministic sign for {uid}: page={target_page} (hash={hash_digest[:8]})")

        items = []
        try:
            res = await get_latest_free_downloads(page=target_page, limit=25, base_url="https://abasmanesh.com/fa/articles/")
            items = res[0] if isinstance(res, tuple) else res
        except Exception as e:
            logger.warning(f"[sign_service] Failed to fetch page {target_page}: {e}")

        if not items:
            items = FALLBACK_ITEMS

        # ۴. انتخاب آیتم از میان لیست صفحه
        item_idx = (hash_int // 39) % len(items)
        selected = dict(items[item_idx])

        # غنی‌سازی با جزئیات درس از صفحه اختصاصی در صورت ناقص بودن صوت یا متن
        p_url = selected.get("page_url")
        if p_url and (not selected.get("lesson_text") or not selected.get("audio_download_url")):
            try:
                from services.feed_scraper import _fetch_single_article
                full_art = await _fetch_single_article(None, p_url, title=selected.get("title", ""), card_tag=selected.get("tag", ""))
                if full_art:
                    selected.update(full_art)
            except Exception as art_err:
                logger.debug(f"[sign_service] Error enriching article {p_url}: {art_err}")

        # تفکیک دقیق و سخت‌گیرانه رسانه: هیچ‌وقت ویدیو را به عنوان صوت در نظر نگیر
        raw_audio = (selected.get("audio_download_url") or selected.get("audio_url") or "").strip()
        raw_video = (selected.get("video_download_url") or selected.get("video_url") or "").strip()

        if raw_audio and (".mp4" in raw_audio.lower()):
            if not raw_video:
                raw_video = raw_audio
            raw_audio = ""

        if raw_video and (".mp3" in raw_video.lower() or ".m4a" in raw_video.lower()):
            if not raw_audio:
                raw_audio = raw_video
            raw_video = ""

        direct_dl = (selected.get("direct_download_url") or "").strip()
        if direct_dl:
            if (".mp3" in direct_dl.lower() or ".m4a" in direct_dl.lower()) and not raw_audio:
                raw_audio = direct_dl
            elif ".mp4" in direct_dl.lower() and not raw_video:
                raw_video = direct_dl

        now_ts = time.time()
        sign_data = {
            "title": selected.get("title", "نشانه هدایت و آرامش امروز شما"),
            "tag": selected.get("tag", "فایل دانلودی"),
            "lesson_text": selected.get("lesson_text", ""),
            "chapters": selected.get("chapters", []),
            "audio_url": raw_audio,
            "video_url": raw_video,
            "page_url": selected.get("page_url", "https://abasmanesh.com/fa/articles/"),
            "cover_url": selected.get("cover_url", ""),
            "page_number": target_page,
            "date": today,
            "created_at": now_ts,
            "user_id": uid
        }

        # ۵. ذخیره در کش روزانه
        cache[uid] = {
            "date": today,
            "sign": sign_data,
            "created_at": now_ts,
            "updated_at": now_ts
        }
        cls._save_user_cache(cache)

        return sign_data

    @classmethod
    async def get_random_sign_for_test(cls) -> Dict[str, Any]:
        """
        دریافت یک نشانه تصادفی جهت آزمایش عملکرد توسط ادمین در پنل وب.
        """
        import random
        rnd_user = f"test_{random.randint(100000, 999999)}"
        return await cls.get_user_today_sign(rnd_user, force_refresh=True)

    @classmethod
    def format_sign_caption(
        cls,
        sign_data: Dict[str, Any],
        include_chapters: bool = True,
        reader_tag: str = "abasmanesh365",
        platform: str = "telegram"
    ) -> str:
        """
        ساخت متن و کپشن زیبا، معنوی و متناسب با رسانه برای ارسال به همراه فایل نشانه.

        ورودی:
            sign_data (Dict[str, Any]): دیکشنری مشخصات نشانه
            include_chapters (bool): وضعیت استخراج و نمایش سرفصل‌های آگاهی
            reader_tag (str): خواننده متادیتا (پیش‌فرض abasmanesh365)
            platform (str): پلتفرم مقصد

        خروجی:
            str: کپشن فرمت‌شده فارسی به همراه تاریخ شمسی رسمی و اعتبار ۲۴ ساعته
        """
        title = sign_data.get("title", "نشانه امروز من")
        tag = sign_data.get("tag", "پیام آگاهی و آرامش")
        page_url = sign_data.get("page_url", "")
        has_audio = bool(sign_data.get("audio_url"))
        has_video = bool(sign_data.get("video_url"))

        # ۱. تاریخ کوتاه شمسی و ساعت انقضای ۲۴ ساعته اختصاصی بر مبنای زمان صدور نشانه
        now = datetime.now(TEHRAN_TZ)
        from core.jalali import format_to_jalali, to_persian_digits
        from datetime import timedelta
        created_ts = sign_data.get("created_at")
        if created_ts:
            try:
                gen_dt = datetime.fromtimestamp(float(created_ts), TEHRAN_TZ)
            except Exception:
                gen_dt = now
        else:
            gen_dt = now

        date_str = to_persian_digits(format_to_jalali(gen_dt).split(" - ")[0])
        exp_dt = gen_dt + timedelta(hours=24)
        exp_time = to_persian_digits(exp_dt.strftime("%H:%M"))
        date_badge = f"📅 <b>تاریخ:</b> {date_str} | ⏳ <b>اعتبار:</b> تا فردا ساعت {exp_time}"

        clean_reader = str(reader_tag or "abasmanesh365").strip()
        if clean_reader and not clean_reader.startswith("@") and not clean_reader.startswith("http"):
            reader_display = f"@{clean_reader}"
        else:
            reader_display = clean_reader

        media_icon = "🎬" if (has_video and not has_audio) else "🎧"

        msg = (
            "🔮 <b>نشانه امروز من</b>\n"
            f"{date_badge}\n\n"
            "✨ <b>جهان همیشه در زمان مناسب، پیام مناسب را به قلبت می‌رساند:</b>\n\n"
            f"{media_icon} <b>عنوان:</b> {title}\n"
            f"🏷 <b>دسته‌بندی:</b> {tag}\n"
        )
        if reader_display:
            msg += f"🎙 <b>منبع و آگاهی:</b> {reader_display}\n"

        # ۲. گزیده متن درس و آموزش
        lesson_text = (sign_data.get("lesson_text") or "").strip()
        if lesson_text:
            short_lesson = lesson_text[:650] + ("..." if len(lesson_text) > 650 else "")
            msg += f"\n📝 <b>گزیده پیام و آموزش درس:</b>\n<i>«{short_lesson}»</i>\n"

        # ۳. سرفصل‌های آگاهی در صورت فعال بودن
        chapters = sign_data.get("chapters") or []
        if include_chapters and chapters:
            msg += "\n📖 <b>سرفصل‌های آگاهی این فایل:</b>\n"
            for ch in chapters[:4]:
                msg += f"▫️ {ch}\n"

        if page_url:
            msg += f"\n🌐 <a href=\"{page_url}\">مشاهده صفحه کامل و نظرات در سایت</a>"

        return msg

    @classmethod
    def build_sign_buttons(
        cls,
        sign_data: Dict[str, Any],
        platform: str = "telegram",
        is_vip: bool = False
    ) -> Any:
        """
        ساخت دکمه‌های شیشه‌ای دسترسی سریع به نشانه.
        برای کاربران عادی در نشانه‌های تصویری، لینک دانلود مستقیم ویدیو حذف و منحصراً دکمه عضویت پریمیوم نمایش داده می‌شود.
        """
        audio_url = (sign_data.get("audio_url") or "").strip()
        video_url = (sign_data.get("video_url") or "").strip()
        page_url = sign_data.get("page_url") or "https://abasmanesh.com/fa/articles/"
        is_video_only = bool(video_url and not audio_url)

        if platform == "telegram":
            from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            rows = []
            if is_video_only and not is_vip:
                # برای کاربر عادی در محتوای ویدیویی، هیچ لینک مستقیمی نمایش داده نمی‌شود
                rows.append([InlineKeyboardButton("💎 عضویت در اشتراک پریمیوم", callback_data="tg:vip_plan")])
                rows.append([InlineKeyboardButton("🌐 مشاهده کامل در سایت", url=page_url)])
                return InlineKeyboardMarkup(rows)

            row1 = []
            if audio_url and not (".mp4" in audio_url.lower()):
                row1.append(InlineKeyboardButton("🎧 دانلود مستقیم صوت از سرور سایت", url=audio_url))
            if video_url:
                row1.append(InlineKeyboardButton("🎬 دانلود مستقیم ویدیو از سرور سایت", url=video_url))
            if row1:
                rows.append(row1)

            # دکمه استخراج لاین صوتی با کیفیت مختص اعضای پریمیوم در صورت ویدیویی بودن
            if is_video_only and is_vip:
                rows.append([InlineKeyboardButton("✨ استخراج لاین صوتی با کیفیت (مختص اعضای پریمیوم)", callback_data="tg:sign_extract_audio")])

            rows.append([InlineKeyboardButton("🌐 مشاهده کامل در سایت", url=page_url)])
            if not is_vip:
                rows.append([InlineKeyboardButton("💎 عضویت در اشتراک پریمیوم", callback_data="tg:vip_plan")])
            return InlineKeyboardMarkup(rows)
        else:
            rows = []
            if is_video_only and not is_vip:
                # برای کاربر عادی در محتوای ویدیویی در بله
                rows.append([{"text": "💎 عضویت در اشتراک پریمیوم", "callback_data": "vip_club_info"}])
                rows.append([{"text": "🌐 مشاهده کامل در سایت", "url": page_url}])
                return {"inline_keyboard": rows}

            row1 = []
            if audio_url and not (".mp4" in audio_url.lower()):
                row1.append({"text": "🎧 دانلود مستقیم صوت از سرور سایت", "url": audio_url})
            if video_url:
                row1.append({"text": "🎬 دانلود مستقیم ویدیو از سرور سایت", "url": video_url})
            if row1:
                rows.append(row1)

            if is_video_only and is_vip:
                rows.append([{"text": "✨ استخراج لاین صوتی با کیفیت (مختص اعضای پریمیوم)", "callback_data": "bale:sign_extract_audio"}])

            rows.append([{"text": "🌐 مشاهده کامل در سایت", "url": page_url}])
            if not is_vip:
                rows.append([{"text": "💎 عضویت در اشتراک پریمیوم", "callback_data": "vip_club_info"}])
            return {"inline_keyboard": rows}

    @classmethod
    async def ensure_audio_downloaded(
        cls,
        sign_data: Dict[str, Any],
        reader_tag: str = "abasmanesh365"
    ) -> Optional[Path]:
        """
        دانلود و نگهداری فایل صوتی نشانه در کش محلی دیسک جهت ارسال امن و پرسرعت.
        """
        cls._ensure_storage()
        raw_url = (sign_data.get("audio_url") or "").strip()
        if not raw_url or ".mp4" in raw_url.lower():
            return None

        # اولویت‌بندی دامنه cdnir برای جلوگیری از خطای ۴۰۴
        candidates = []
        if "cdneu.abasmanesh.com" in raw_url:
            candidates.append(raw_url.replace("cdneu.abasmanesh.com", "cdnir.abasmanesh.com"))
            candidates.append(raw_url)
        elif "cdnir.abasmanesh.com" in raw_url:
            candidates.append(raw_url)
            candidates.append(raw_url.replace("cdnir.abasmanesh.com", "cdneu.abasmanesh.com"))
        else:
            candidates.append(raw_url)

        try:
            for audio_url in candidates:
                url_hash = hashlib.md5(audio_url.encode("utf-8")).hexdigest()[:12]
                parsed = urllib.parse.urlparse(audio_url)
                ext = Path(parsed.path).suffix.lower()
                if ext not in [".mp3", ".m4a", ".ogg", ".wav", ".aac"]:
                    ext = ".mp3"
                dest_file = cls.CACHE_DIR / f"sign_audio_{url_hash}{ext}"

                if dest_file.exists() and dest_file.stat().st_size > 1024:
                    return dest_file

                from services.url_service import UrlService
                logger.info(f"[sign_service] Downloading sign audio locally: {audio_url} -> {dest_file.name}")
                ok = await UrlService.download_file_stream(audio_url, dest_file)
                if ok and dest_file.exists() and dest_file.stat().st_size > 1024:
                    # بررسی اعتبارسنجی بایت‌های فایل صوتی جهت جلوگیری از کش شدن صفحات HTML خطای سرور
                    try:
                        with open(dest_file, "rb") as check_f:
                            head = check_f.read(100)
                            if b"<!DOCTYPE" in head or b"<html" in head.lower():
                                logger.warning(f"[sign_service] Downloaded file is HTML error, discarding: {audio_url}")
                                dest_file.unlink(missing_ok=True)
                                continue
                    except Exception:
                        pass

                    logger.info(f"[sign_service] Sign audio cached successfully: {dest_file} ({dest_file.stat().st_size} bytes)")
                    if dest_file.suffix.lower() == ".mp3":
                        try:
                            from mutagen.easyid3 import EasyID3
                            from mutagen.mp3 import MP3
                            audio = MP3(str(dest_file), ID3=EasyID3)
                            if reader_tag:
                                audio["artist"] = str(reader_tag)
                                audio["albumartist"] = str(reader_tag)
                            if sign_data.get("title"):
                                audio["title"] = str(sign_data["title"])
                            audio.save()
                        except Exception:
                            pass
                    return dest_file
                else:
                    logger.warning(f"[sign_service] Failed download attempt with {audio_url}")
            return None
        except Exception as e:
            logger.error(f"[sign_service] Error ensuring audio downloaded: {e}")
            return None

