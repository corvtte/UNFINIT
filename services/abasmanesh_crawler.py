"""
ماژول خزشگر اختصاصی و جامع سایت عباس‌منش (Abasmanesh Crawler Module)
این ماژول وظیفه خزش، استخراج دسته‌بندی‌های رسمی، استخراج جلسات و فایل‌های صوتی و تصویری،
حل ریشه‌ای تصاویر شاخص لود تنبل (Lazy Loading) و مدیریت درخواست‌ها با هدرهای شبیه‌ساز مرورگر را بر عهده دارد.
"""

import asyncio
import logging
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import aiohttp

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

logger = logging.getLogger("abasmanesh_crawler")

# هدرهای اختصاصی و استاندارد شبیه‌ساز مرورگر جهت مهار خطاهای ۴۰۳ و ۴۲۹
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "fa,en-US;q=0.9,en;q=0.8",
    "Connection": "keep-alive"
}

BASE_SITE_URL = "https://abasmanesh.com"
FREE_DOWNLOAD_BASE_URL = "https://abasmanesh.com/fa/category/free-download/"

# فهرست رسمی ۱۷ دسته‌بندی استخراج‌شده زنده از ساختار واقعی سایت عباس‌منش
OFFICIAL_17_CATEGORIES: List[Dict[str, Any]] = [
    {
        "id": 1,
        "emoji": "🎁",
        "slug": "free-download",
        "title": "تمام دانلودها (آرشیو هدایا)",
        "url": "https://abasmanesh.com/fa/category/free-download/",
        "path": "/fa/category/free-download/"
    },
    {
        "id": 2,
        "emoji": "🎙️",
        "slug": "interview-with-master-abasmanesh",
        "title": "مصاحبه با استاد عباس‌منش",
        "url": "https://abasmanesh.com/fa/category/free-download/interview-with-master-abasmanesh/",
        "path": "/fa/category/free-download/interview-with-master-abasmanesh/"
    },
    {
        "id": 3,
        "emoji": "📹",
        "slug": "live-sessions",
        "title": "live با استاد عباس‌منش",
        "url": "https://abasmanesh.com/fa/category/free-download/live-sessions/",
        "path": "/fa/category/free-download/live-sessions/"
    },
    {
        "id": 4,
        "emoji": "🗽",
        "slug": "living-in-paradise",
        "title": "سریال زندگی در بهشت",
        "url": "https://abasmanesh.com/fa/category/free-download/living-in-paradise/",
        "path": "/fa/category/free-download/living-in-paradise/"
    },
    {
        "id": 5,
        "emoji": "🛣️",
        "slug": "cross-country-road-trip",
        "title": "سریال سفر به دور آمریکا",
        "url": "https://abasmanesh.com/fa/category/free-download/cross-country-road-trip/",
        "path": "/fa/category/free-download/cross-country-road-trip/"
    },
    {
        "id": 6,
        "emoji": "🌴",
        "slug": "the-series-of-focus-on-positive-points",
        "title": "سریال تمرکز بر نکات مثبت",
        "url": "https://abasmanesh.com/fa/category/free-download/the-series-of-focus-on-positive-points/",
        "path": "/fa/category/free-download/the-series-of-focus-on-positive-points/"
    },
    {
        "id": 7,
        "emoji": "⚖️",
        "slug": "indisputable-law-of-the-universe",
        "title": "قوانین بدون تغییر خداوند",
        "url": "https://abasmanesh.com/fa/category/free-download/indisputable-law-of-the-universe/",
        "path": "/fa/category/free-download/indisputable-law-of-the-universe/"
    },
    {
        "id": 8,
        "emoji": "🎯",
        "slug": "recognition-of-essential-from-nonessential",
        "title": "تواناییِ تشخیص اصل از فرع",
        "url": "https://abasmanesh.com/fa/category/free-download/recognition-of-essential-from-nonessential/",
        "path": "/fa/category/free-download/recognition-of-essential-from-nonessential/"
    },
    {
        "id": 9,
        "emoji": "🕋",
        "slug": "practical-monotheism",
        "title": "اجرای توحید در عمل",
        "url": "https://abasmanesh.com/fa/category/free-download/practical-monotheism/",
        "path": "/fa/category/free-download/practical-monotheism/"
    },
    {
        "id": 10,
        "emoji": "✨",
        "slug": "faith-takes-action",
        "title": "ایمانی که عمل می‌آورد",
        "url": "https://abasmanesh.com/fa/category/free-download/faith-takes-action/",
        "path": "/fa/category/free-download/faith-takes-action/"
    },
    {
        "id": 11,
        "emoji": "🧠",
        "slug": "the-power-of-mind-control",
        "title": "توانایی کنترل ذهن",
        "url": "https://abasmanesh.com/fa/category/free-download/the-power-of-mind-control/",
        "path": "/fa/category/free-download/the-power-of-mind-control/"
    },
    {
        "id": 12,
        "emoji": "💰",
        "slug": "wealth-creating-beliefs",
        "title": "باورهای ثروت ساز",
        "url": "https://abasmanesh.com/fa/category/free-download/%D8%A8%D8%A7%D9%88%D8%B1%D9%87%D8%A7%DB%8C-%D8%AB%D8%B1%D9%88%D8%AA-%D8%B3%D8%A7%D8%B2/",
        "path": "/fa/category/free-download/%D8%A8%D8%A7%D9%88%D8%B1%D9%87%D8%A7%DB%8C-%D8%AB%D8%B1%D9%88%D8%AA-%D8%B3%D8%A7%D8%B2/"
    },
    {
        "id": 13,
        "emoji": "💻",
        "slug": "be-your-own-life-developer",
        "title": "برنامه نویس زندگی‌ات باش",
        "url": "https://abasmanesh.com/fa/category/free-download/be-your-own-life-developer/",
        "path": "/fa/category/free-download/be-your-own-life-developer/"
    },
    {
        "id": 14,
        "emoji": "💎",
        "slug": "investing-in-yourself",
        "title": "سرمایه‌گذاری روی خودت",
        "url": "https://abasmanesh.com/fa/category/free-download/investing-in-yourself/",
        "path": "/fa/category/free-download/investing-in-yourself/"
    },
    {
        "id": 15,
        "emoji": "🕊️",
        "slug": "inner-piece",
        "title": "در صلح بودن با خودمان",
        "url": "https://abasmanesh.com/fa/category/inner-piece/",
        "path": "/fa/category/inner-piece/"
    },
    {
        "id": 16,
        "emoji": "🧘",
        "slug": "peace-in-light-of-awareness",
        "title": "آرامش در پرتو آگاهی",
        "url": "https://abasmanesh.com/fa/category/free-download/%D8%A2%D8%B1%D8%A7%D9%85%D8%B4-%D8%AF%D8%B1-%D9%BE%D8%B1%D8%AA%D9%88-%D8%A2%DA%AF%D8%A7%D9%87%DB%8C/",
        "path": "/fa/category/free-download/%D8%A2%D8%B1%D8%A7%D9%85%D8%B4-%D8%AF%D8%B1-%D9%BE%D8%B1%D8%AA%D9%88-%D8%A2%DA%AF%D8%A7%D9%87%DB%8C/"
    },
    {
        "id": 17,
        "emoji": "🪜",
        "slug": "evolutionary-steps-to-receive-guidance",
        "title": "قدم‌های تکاملی برای هدایت‌شدن",
        "url": "https://abasmanesh.com/fa/category/evolutionary-steps-to-receive-guidance/",
        "path": "/fa/category/evolutionary-steps-to-receive-guidance/"
    }
]


def extract_thumbnail_url(tag_or_soup: Any) -> str:
    """
    استخراج هوشمند و ضدگلوله آدرس تصویر بندانگشتی (کاور) با مهار کامل لود تنبل (Lazy Loading).
    
    این تابع صفات متعدد وردپرس و افزونه‌های کش مانند data-src، data-lazy-src، data-original،
    srcset و حتی ویژگی background-image را بررسی کرده و از بازگرداندن پلیس‌هولدرهای خالی
    (نظیر داده‌های data:image/svg+xml یا 1x1 gif) جلوگیری به عمل می‌آورد.
    
    ورودی:
        tag_or_soup: تگ img، کارت BeautifulSoup یا هر المان HTML
    خروجی:
        str: آدرس کامل و معتبر اینترنتی تصویر شاخص
    """
    if not tag_or_soup:
        return ""

    img = tag_or_soup if getattr(tag_or_soup, "name", None) == "img" else getattr(tag_or_soup, "find", lambda x: None)("img")

    candidate_url = ""

    if img:
        # ۱. بررسی صفات متداول بارگذاری تنبل
        for attr in ("data-src", "data-lazy-src", "data-original", "data-lazy", "data-url"):
            val = img.get(attr, "").strip()
            if val and not val.startswith("data:"):
                candidate_url = val
                break

        # ۲. بررسی صفت srcset جهت استخراج بالاترین کیفیت
        if not candidate_url and img.get("srcset"):
            raw_srcset = img["srcset"].strip()
            parts = [p.strip().split(" ")[0] for p in raw_srcset.split(",") if p.strip()]
            valid_parts = [p for p in parts if not p.startswith("data:")]
            if valid_parts:
                candidate_url = valid_parts[-1]

        # ۳. بررسی صفت src معمولی (به شرطی که پلیس‌هولدر data: نباشد)
        if not candidate_url and img.get("src"):
            raw_src = img["src"].strip()
            if raw_src and not raw_src.startswith("data:"):
                candidate_url = raw_src

    # ۴. بررسی استایل background-image در کل المان در صورت نبود تگ img یا خالی بودن آن
    if not candidate_url and hasattr(tag_or_soup, "find_all"):
        nodes = [tag_or_soup] + list(tag_or_soup.find_all(attrs={"style": True}))
        for node in nodes:
            style_str = node.get("style", "")
            m = re.search(r"background(?:-image)?\s*:\s*url\(\s*['\"]?(.*?)['\"]?\s*\)", style_str, re.IGNORECASE)
            if m:
                bg_val = m.group(1).strip()
                if bg_val and not bg_val.startswith("data:"):
                    candidate_url = bg_val
                    break

    # ۵. نرمال‌سازی آدرس (پروتکل‌های نسبی // و مسیرهای نسبی /)
    if candidate_url:
        if candidate_url.startswith("//"):
            candidate_url = "https:" + candidate_url
        elif candidate_url.startswith("/"):
            candidate_url = BASE_SITE_URL + candidate_url

    return candidate_url


def build_page_url(base_url: str, page_number: int = 1) -> str:
    """
    تولید آدرس استاندارد صفحه‌بندی سایت عباس‌منش با الگوی ?page={page_number}.
    
    ورودی:
        base_url (str): آدرس پایه دسته‌بندی یا دانلودها
        page_number (int): شماره صفحه (پیش‌فرض: ۱)
    خروجی:
        str: آدرس نهایی با پارامتر صفحه‌بندی
    """
    clean_base = base_url.strip()
    if page_number <= 1:
        return clean_base

    if "?" in clean_base:
        return f"{clean_base}&page={page_number}"
    return f"{clean_base.rstrip('/')}/?page={page_number}"


class AbasmaneshCrawler:
    """
    کلاس مدیریت خزش، دریافت مقالات و استخراج رسانه‌های آموزشی از سایت عباس‌منش.
    """
    CATEGORIES = OFFICIAL_17_CATEGORIES

    @classmethod
    def get_all_categories(cls) -> List[Dict[str, Any]]:
        """دریافت لیست ۱۷ دسته‌بندی رسمی عباس‌منش."""
        return list(cls.CATEGORIES)

    @classmethod
    def get_category_by_id_or_slug(cls, cat_id_or_slug: Union[int, str]) -> Optional[Dict[str, Any]]:
        """
        یافتن دسته‌بندی بر اساس شناسه عددی (۱ تا ۱۷)، اسلاگ یا آدرس URL.
        """
        s = str(cat_id_or_slug).strip()
        for c in cls.CATEGORIES:
            if str(c.get("id")) == s or c.get("slug") == s or s in c.get("url", ""):
                return c
        return None

    @classmethod
    async def fetch_article_details(
        cls,
        session: aiohttp.ClientSession,
        url: str,
        title: str = "",
        cover_url: str = "",
        tag: str = ""
    ) -> Dict[str, Any]:
        """
        واکشی عمیق صفحه یک مقاله جهت استخراج قطعی فایل‌های صوتی، ویدیویی و درس‌نامه.
        
        ورودی‌ها:
            session: سشن aiohttp
            url: آدرس صفحه مقاله
            title: عنوان اولیه استخراج‌شده از کارت
            cover_url: آدرس کاور اولیه
            tag: تگ دسته‌بندی
        خروجی:
            Dict شامل title, audio_url, video_url, cover_url, direct_download_url, lesson_text
        """
        clean_url = url.split("?")[0]
        audio_dl = ""
        video_dl = ""
        final_cover = cover_url or ""
        lesson_text = ""

        try:
            async with session.get(clean_url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    if BeautifulSoup:
                        soup = BeautifulSoup(html, "html.parser")
                        og_img = soup.find("meta", property="og:image")
                        if og_img and og_img.get("content"):
                            final_cover = og_img["content"].strip()

                        # جستجو در تگ‌های ویدیو و سورس
                        for v in soup.find_all(["video", "source"]):
                            v_src = (v.get("src") or v.get("data-src") or "").strip()
                            if v_src and ".mp4" in v_src and not video_dl:
                                video_dl = re.sub(r"^rhttp", "http", v_src)

                        # جستجو در لینک‌های دانلود مستقیم
                        for a in soup.find_all("a", href=True):
                            h = a["href"].strip()
                            if "download.php?url=" in h or (".mp3" in h and "http" in h) or (".mp4" in h and "http" in h):
                                clean_h = re.sub(r"^rhttp", "http", h).replace("cdneu.abasmanesh.com", "cdnir.abasmanesh.com")
                                if ".mp3" in clean_h and not audio_dl:
                                    audio_dl = clean_h
                                elif ".mp4" in clean_h and not video_dl:
                                    video_dl = clean_h

                        # استخراج متن درس‌نامه
                        entry_content = soup.find("div", class_=lambda c: c and any(k in c for k in ["entry-content", "post-content", "article__body", "article-content"]))
                        if entry_content:
                            p_nodes = [p.get_text(strip=True) for p in entry_content.find_all("p") if len(p.get_text(strip=True)) > 25]
                            if p_nodes:
                                lesson_text = "\n\n".join(p_nodes[:4])
                    else:
                        img_m = re.search(r'property="og:image"\s+content="([^"]+)"', html)
                        if img_m and not final_cover:
                            final_cover = img_m.group(1).strip()
                        for m in re.finditer(r'(?:href|src)=["\']([^"\']*(?:\.mp4|\.mp3|download\.php\?url=[^"\']+))["\']', html):
                            clean_h = re.sub(r"^rhttp", "http", m.group(1).strip()).replace("cdneu.abasmanesh.com", "cdnir.abasmanesh.com")
                            if ".mp3" in clean_h and not audio_dl:
                                audio_dl = clean_h
                            elif ".mp4" in clean_h and not video_dl:
                                video_dl = clean_h

                    # قرینه‌سازی لینک در صورت فقدان یکی از دو نسخه
                    if audio_dl and not video_dl and ".mp3" in audio_dl:
                        video_dl = audio_dl.replace(".mp3", ".mp4")
                    elif video_dl and not audio_dl and ".mp4" in video_dl:
                        audio_dl = video_dl.replace(".mp4", ".mp3")
        except Exception as e:
            logger.debug(f"[abasmanesh_crawler] Error inspecting article {clean_url}: {e}")

        return {
            "title": title or "جلسه آموزشی",
            "page_url": clean_url,
            "url": audio_dl or video_dl or clean_url,
            "cover_url": final_cover,
            "audio_download_url": audio_dl,
            "audio_url": audio_dl,
            "video_download_url": video_dl,
            "video_url": video_dl,
            "direct_download_url": audio_dl or video_dl,
            "lesson_text": lesson_text,
            "tag": tag or "آموزش"
        }

    @classmethod
    async def crawl_category(
        cls,
        cat_id_or_slug: Union[int, str],
        page: int = 1,
        limit: int = 15
    ) -> Dict[str, Any]:
        """
        خزش خودکار یک دسته‌بندی و استخراج جلسات همراه با لینک‌های دانلود مستقیم.
        
        ورودی‌ها:
            cat_id_or_slug: شناسه عددی یا اسلاگ دسته‌بندی
            page: شماره صفحه (پیش‌فرض: ۱ با پارامتر ?page=)
            limit: حداکثر تعداد جلسات در صفحه
        خروجی:
            Dict شامل مشخصات دسته‌بندی، لیست جلسات و پرچم صفحه بعد
        """
        cat = cls.get_category_by_id_or_slug(cat_id_or_slug) or cls.CATEGORIES[0]
        target_url = build_page_url(cat["url"], page_number=page)

        timeout = aiohttp.ClientTimeout(total=20)
        articles_to_fetch = []
        try:
            async with aiohttp.ClientSession(headers=BROWSER_HEADERS, timeout=timeout) as session:
                async with session.get(target_url) as resp:
                    if resp.status == 200:
                        html = await resp.text()
                        if BeautifulSoup:
                            soup = BeautifulSoup(html, "html.parser")
                            cards = soup.select("div.article-grid div.card, div.card.card--media, .card")
                            for card in cards:
                                a_link = card.find("a", class_="card__media-link") or card.find("a", href=lambda h: h and "/fa/" in h and not any(x in h for x in ["category", "cart", "account", "login"]))
                                if not a_link or not a_link.get("href"):
                                    continue
                                href = a_link["href"].strip()
                                full_href = (BASE_SITE_URL + href) if href.startswith("/") else href
                                card_cover = extract_thumbnail_url(card)
                                title = ""
                                body = card.find("div", class_="card__body")
                                if body:
                                    t_a = body.find("a")
                                    if t_a:
                                        title = t_a.get_text(strip=True)
                                if not title:
                                    title = a_link.get_text(strip=True)
                                articles_to_fetch.append((full_href, title, card_cover, cat.get("title", "")))
                                if len(articles_to_fetch) >= limit:
                                    break

                # واکشی همگام مشخصات فایل‌ها
                tasks = [
                    cls.fetch_article_details(session, u, t, c, tg)
                    for u, t, c, tg in articles_to_fetch[:limit]
                ]
                episodes = await asyncio.gather(*tasks, return_exceptions=True)
                valid_episodes = [ep for ep in episodes if isinstance(ep, dict) and ep.get("title")]

                return {
                    "ok": True,
                    "category": cat,
                    "episodes": valid_episodes,
                    "page": page,
                    "has_next": len(valid_episodes) >= limit
                }
        except Exception as e:
            logger.warning(f"[abasmanesh_crawler] Error crawling category {cat['slug']}: {e}")
            return {
                "ok": False,
                "category": cat,
                "episodes": [],
                "page": page,
                "has_next": False,
                "error": str(e)
            }


crawler = AbasmaneshCrawler()

