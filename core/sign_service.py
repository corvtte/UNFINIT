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
        uid = str(user_id).strip()
        today = cls.get_tehran_today_str()
        cache = cls._load_user_cache()

        user_entry = cache.get(uid) or {}
        if not force_refresh and user_entry.get("date") == today and user_entry.get("sign"):
            logger.debug(f"[sign_service] Serving cached sign for user {uid} on {today}")
            return user_entry["sign"]

        # ۱. محاسبه هش پایدار بر مبنای User ID و تاریخ روز
        seed_str = f"unfinit_sign_{uid}_{today}"
        hash_digest = hashlib.sha256(seed_str.encode("utf-8")).hexdigest()
        hash_int = int(hash_digest, 16)

        # ۲. نگاشت به شماره صفحه (۱ تا ۳۹)
        target_page = (hash_int % 39) + 1

        logger.info(f"[sign_service] Selecting deterministic sign for {uid}: page={target_page} (hash={hash_digest[:8]})")

        items = []
        try:
            items = await get_latest_free_downloads(page=target_page, limit=25)
        except Exception as e:
            logger.warning(f"[sign_service] Failed to fetch page {target_page}: {e}")

        if not items:
            items = FALLBACK_ITEMS

        # ۳. انتخاب آیتم از میان لیست صفحه
        item_idx = (hash_int // 39) % len(items)
        selected = items[item_idx]

        sign_data = {
            "title": selected.get("title", "نشانه هدایت و آرامش امروز شما"),
            "tag": selected.get("tag", "فایل دانلودی"),
            "audio_url": selected.get("audio_download_url") or selected.get("audio_url") or selected.get("direct_download_url", ""),
            "video_url": selected.get("video_download_url") or selected.get("video_url", ""),
            "page_url": selected.get("page_url", "https://abasmanesh.com/fa/free-download-list/"),
            "cover_url": selected.get("cover_url", ""),
            "page_number": target_page,
            "date": today,
            "user_id": uid
        }

        # ۴. ذخیره در کش روزانه
        cache[uid] = {
            "date": today,
            "sign": sign_data,
            "updated_at": time.time()
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
    def format_sign_caption(cls, sign_data: Dict[str, Any]) -> str:
        """
        ساخت متن و کپشن زیبا، معنوی و آرامش‌بخش برای ارسال به همراه فایل نشانه.

        ورودی:
            sign_data (Dict[str, Any]): دیکشنری مشخصات نشانه

        خروجی:
            str: کپشن فرمت‌شده فارسی به همراه ایموجی و ساختار RTL
        """
        title = sign_data.get("title", "نشانه امروز من")
        tag = sign_data.get("tag", "پیام آگاهی و آرامش")
        page_url = sign_data.get("page_url", "")
        today = sign_data.get("date", "")

        msg = (
            "🔮 <b>نشانه امروز من</b>\n"
            f"📅 <i>{today}</i>\n\n"
            "✨ <b>جهان همیشه در زمان مناسب، پیام مناسب را به قلبت می‌رساند:</b>\n\n"
            f"🎧 <b>عنوان:</b> {title}\n"
            f"🏷 <b>دسته‌بندی:</b> {tag}\n\n"
            "▫️ این فایل صوتی با آرامش و تمرکز برای آگاهی امروز شما انتخاب شده است. "
            "پیشنهاد می‌کنیم در خلوت خود با هندزفری به آن گوش جان بسپارید.\n\n"
        )
        if page_url:
            msg += f"🌐 <a href=\"{page_url}\">مشاهده صفحه کامل و نظرات در سایت</a>\n\n"
        msg += "💎 <b>UNFINIT Store Engine</b>"
        return msg
