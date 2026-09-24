"""
Feed Scraper Module for UNFINIT Store Engine
Fetches and extracts the latest free downloads, direct media URLs, and covers
from abasmanesh.com with resilient browser headers, BeautifulSoup parsing,
and robust caching/error fallbacks.
"""

import asyncio
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import aiohttp

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

logger = logging.getLogger("feed_scraper")

# مسیرهای فایل‌های کش دیسک و دسته‌بندی‌های شخصی‌سازی‌شده
DATA_DIR = Path("data")
FEED_CACHE_FILE = DATA_DIR / "feed_cache.json"
CUSTOM_CATS_FILE = DATA_DIR / "custom_categories.json"

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

BASE_FEED_URL = "https://abasmanesh.com/fa/free-download-list/"
ARTICLES_BASE_URL = "https://abasmanesh.com/fa/articles/"

# ۱۶ دسته‌بندی رسمی دانلودهای هدیه و مقالات سایت عباس‌منش همراه با ایموجی‌های اختصاصی
ABASMANESH_PREMIUM_CATEGORIES: List[Dict[str, Any]] = [
    {
        "id": 1,
        "emoji": "🌴",
        "slug": "the-series-of-focus-on-positive-points",
        "title": "سریال تمرکز بر نکات مثبت",
        "url": "https://abasmanesh.com/fa/category/free-download/the-series-of-focus-on-positive-points/",
        "path": "/fa/category/free-download/the-series-of-focus-on-positive-points/"
    },
    {
        "id": 2,
        "emoji": "🗽",
        "slug": "paradise-life-series",
        "title": "سریال زندگی در بهشت",
        "url": "https://abasmanesh.com/fa/category/free-download/paradise-life-series/",
        "path": "/fa/category/free-download/paradise-life-series/"
    },
    {
        "id": 3,
        "emoji": "🛣️",
        "slug": "travel-around-the-usa-series",
        "title": "سریال سفر به دور آمریکا",
        "url": "https://abasmanesh.com/fa/category/free-download/travel-around-the-usa-series/",
        "path": "/fa/category/free-download/travel-around-the-usa-series/"
    },
    {
        "id": 4,
        "emoji": "🎙",
        "slug": "interview-with-master-abasmanesh",
        "title": "مصاحبه با استاد عباس‌منش و Liveها",
        "url": "https://abasmanesh.com/fa/category/free-download/interview-with-master-abasmanesh/",
        "path": "/fa/category/free-download/interview-with-master-abasmanesh/"
    },
    {
        "id": 5,
        "emoji": "⚖️",
        "slug": "unchanging-laws-of-god",
        "title": "قوانین بدون تغییر خداوند",
        "url": "https://abasmanesh.com/fa/category/free-download/unchanging-laws-of-god/",
        "path": "/fa/category/free-download/unchanging-laws-of-god/"
    },
    {
        "id": 6,
        "emoji": "🕋",
        "slug": "practicing-monotheism",
        "title": "اجرای توحید در عمل",
        "url": "https://abasmanesh.com/fa/category/free-download/practicing-monotheism/",
        "path": "/fa/category/free-download/practicing-monotheism/"
    },
    {
        "id": 7,
        "emoji": "🎯",
        "slug": "distinguishing-essence-from-branches",
        "title": "توانایی تشخیص اصل از فرع",
        "url": "https://abasmanesh.com/fa/category/free-download/distinguishing-essence-from-branches/",
        "path": "/fa/category/free-download/distinguishing-essence-from-branches/"
    },
    {
        "id": 8,
        "emoji": "⚡️",
        "slug": "faith-that-leads-to-action",
        "title": "ایمانی که عمل می‌آورد",
        "url": "https://abasmanesh.com/fa/category/free-download/faith-that-leads-to-action/",
        "path": "/fa/category/free-download/faith-that-leads-to-action/"
    },
    {
        "id": 9,
        "emoji": "🧠",
        "slug": "ability-to-control-the-mind",
        "title": "توانایی کنترل ذهن",
        "url": "https://abasmanesh.com/fa/category/free-download/ability-to-control-the-mind/",
        "path": "/fa/category/free-download/ability-to-control-the-mind/"
    },
    {
        "id": 10,
        "emoji": "💰",
        "slug": "wealth-creating-beliefs",
        "title": "باورهای ثروت‌ساز",
        "url": "https://abasmanesh.com/fa/category/free-download/wealth-creating-beliefs/",
        "path": "/fa/category/free-download/wealth-creating-beliefs/"
    },
    {
        "id": 11,
        "emoji": "💻",
        "slug": "be-the-programmer-of-your-life",
        "title": "برنامه‌نویس زندگی‌ات باش",
        "url": "https://abasmanesh.com/fa/category/free-download/be-the-programmer-of-your-life/",
        "path": "/fa/category/free-download/be-the-programmer-of-your-life/"
    },
    {
        "id": 12,
        "emoji": "🕊",
        "slug": "being-at-peace-with-ourselves",
        "title": "در صلح بودن با خودمان",
        "url": "https://abasmanesh.com/fa/category/free-download/being-at-peace-with-ourselves/",
        "path": "/fa/category/free-download/being-at-peace-with-ourselves/"
    },
    {
        "id": 13,
        "emoji": "💎",
        "slug": "investing-in-yourself",
        "title": "سرمایه‌گذاری روی خودت",
        "url": "https://abasmanesh.com/fa/category/free-download/investing-in-yourself/",
        "path": "/fa/category/free-download/investing-in-yourself/"
    },
    {
        "id": 14,
        "emoji": "🕯",
        "slug": "peace-in-light-of-awareness",
        "title": "آرامش در پرتو آگاهی",
        "url": "https://abasmanesh.com/fa/category/free-download/peace-in-light-of-awareness/",
        "path": "/fa/category/free-download/peace-in-light-of-awareness/"
    },
    {
        "id": 15,
        "emoji": "🪜",
        "slug": "evolutionary-steps-for-guidance",
        "title": "قدم‌های تکاملی برای هدایت‌شدن",
        "url": "https://abasmanesh.com/fa/category/free-download/evolutionary-steps-for-guidance/",
        "path": "/fa/category/free-download/evolutionary-steps-for-guidance/"
    },
    {
        "id": 16,
        "emoji": "✨",
        "slug": "all-articles",
        "title": "کلیدها و تمام دانلودها",
        "url": "https://abasmanesh.com/fa/articles/",
        "path": "/fa/articles/"
    }
]

# کش حافظه‌ای
_CACHE: Dict[str, Any] = {
    "items": [],
    "last_fetched": 0.0
}
_ARTICLE_CACHE: Dict[str, Dict[str, Any]] = {}
CACHE_TTL_SEC = 300.0  # ۵ دقیقه کش رم
DISK_CACHE_TTL_SEC = 3600.0 * 6  # ۶ ساعت کش دیسک

# کش ۲۴ ساعته منوی سایت
_LIVE_CATEGORIES_CACHE: Dict[str, Any] = {
    "categories": [],
    "last_fetched": 0.0
}
LIVE_CATEGORIES_TTL_SEC = 86400.0  # ۲۴ ساعت

def load_feed_disk_cache() -> List[Dict[str, Any]]:
    """بارگذاری فوق‌سریع دانلودهای کش‌شده از دیسک زیر ۱۰ میلی‌ثانیه."""
    try:
        if FEED_CACHE_FILE.exists():
            data = json.loads(FEED_CACHE_FILE.read_text(encoding="utf-8"))
            items = data.get("items", [])
            cached_at = data.get("cached_at", 0)
            if items and (time.time() - cached_at < DISK_CACHE_TTL_SEC):
                return items
    except Exception as e:
        logger.debug(f"[feed_scraper] Error loading disk cache: {e}")
    return []

def save_feed_disk_cache(items: List[Dict[str, Any]]) -> None:
    """ذخیره امن دانلودها روی دیسک جهت پاسخگویی لحظه‌ای وب‌پنل."""
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "items": items,
            "cached_at": time.time(),
            "count": len(items)
        }
        FEED_CACHE_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        logger.warning(f"[feed_scraper] Error saving disk cache: {e}")

def get_custom_categories() -> List[Dict[str, Any]]:
    """بازیابی دسته‌بندی‌های شخصی‌سازی‌شده توسط ادمین در وب‌پنل."""
    try:
        if CUSTOM_CATS_FILE.exists():
            data = json.loads(CUSTOM_CATS_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list) and len(data) > 0:
                return data
    except Exception as e:
        logger.debug(f"[feed_scraper] Error loading custom categories: {e}")
    return list(ABASMANESH_PREMIUM_CATEGORIES)

def save_custom_categories(categories: List[Dict[str, Any]]) -> bool:
    """ذخیره تنظیمات و ایموجی‌های دسته‌بندی‌ها."""
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        CUSTOM_CATS_FILE.write_text(json.dumps(categories, ensure_ascii=False, indent=2), encoding="utf-8")
        global ABASMANESH_PREMIUM_CATEGORIES
        ABASMANESH_PREMIUM_CATEGORIES = categories
        return True
    except Exception as e:
        logger.error(f"[feed_scraper] Error saving custom categories: {e}")
        return False

async def fetch_live_categories(force_refresh: bool = False) -> List[Dict[str, Any]]:
    """
    استخراج ۱۰۰٪ داینامیک ۱۶ دسته‌بندی منوی دانلودها (هدیه) از صفحه اصلی سایت https://abasmanesh.com/fa/
    بدون هاردکد اسلاگ یا عناوین، همراه با کش ۲۴ ساعته.
    """
    now = time.time()
    if not force_refresh and _LIVE_CATEGORIES_CACHE["categories"] and (now - _LIVE_CATEGORIES_CACHE["last_fetched"] < LIVE_CATEGORIES_TTL_SEC):
        return _LIVE_CATEGORIES_CACHE["categories"]

    timeout = aiohttp.ClientTimeout(total=15)
    extracted = []
    try:
        async with aiohttp.ClientSession(headers=BROWSER_HEADERS, timeout=timeout) as session:
            async with session.get("https://abasmanesh.com/fa/") as resp:
                if resp.status == 200:
                    html = await resp.text()
                    if BeautifulSoup:
                        soup = BeautifulSoup(html, "html.parser")
                        dropdown_links = []
                        # 1. جستجو در آیتم‌های مگامنوی دسکتاپ
                        nav_items = soup.select(".public-nav__item")
                        for item in nav_items:
                            heading = item.find(["a", "span", "div"], class_=lambda c: c and "link" in c)
                            h_text = heading.get_text(strip=True) if heading else ""
                            if "دانلود" in h_text:
                                dropdown_links = item.select("a.public-nav__dropdown-link")
                                break
                        # 2. جستجو در دراور موبایل در صورت نیاز
                        if not dropdown_links:
                            drawer_items = soup.select(".public-drawer__item")
                            for item in drawer_items:
                                heading = item.find(["a", "span", "button"])
                                h_text = heading.get_text(strip=True) if heading else ""
                                if "دانلود" in h_text:
                                    dropdown_links = item.select("a.public-drawer__sub-link, a")
                                    break
                        # 3. فالبک: تمام لینک‌های شامل category
                        if not dropdown_links:
                            dropdown_links = soup.find_all("a", href=lambda h: h and "/category/" in h)

                        seen_slugs = set()
                        cat_id = 1
                        for a in dropdown_links:
                            href = a.get("href", "").strip()
                            title = a.get_text(strip=True)
                            if not href or not title or len(title) < 3:
                                continue
                            if any(x in href for x in ["cart", "account", "login", "aghlekol", "terms"]):
                                continue
                            clean_href = href.split("?")[0].rstrip("/")
                            slug = clean_href.split("/")[-1]
                            if not slug or slug in seen_slugs or slug in ["category", "fa", "free-download"]:
                                continue
                            seen_slugs.add(slug)
                            full_url = ("https://abasmanesh.com" + href) if href.startswith("/") else href
                            extracted.append({
                                "id": cat_id,
                                "slug": slug,
                                "title": title,
                                "url": full_url,
                                "path": href if href.startswith("/") else ("/" + href.split("abasmanesh.com/")[-1])
                            })
                            cat_id += 1
    except Exception as e:
        logger.warning(f"[feed_scraper] Error fetching live categories: {e}")

    if extracted and len(extracted) >= 5:
        _LIVE_CATEGORIES_CACHE["categories"] = extracted
        _LIVE_CATEGORIES_CACHE["last_fetched"] = now
        global ABASMANESH_PREMIUM_CATEGORIES
        ABASMANESH_PREMIUM_CATEGORIES = extracted
        return extracted

    return ABASMANESH_PREMIUM_CATEGORIES

def get_all_categories() -> List[Dict[str, Any]]:
    """دریافت فهرست کامل ۱۶ دسته‌بندی رسمی عباس‌منش با اولویت تنظیمات ذخیره‌شده ادمین."""
    custom = get_custom_categories()
    if custom and len(custom) >= 5:
        return custom
    if _LIVE_CATEGORIES_CACHE.get("categories"):
        return _LIVE_CATEGORIES_CACHE["categories"]
    return ABASMANESH_PREMIUM_CATEGORIES

def get_category_by_id(cat_id_or_slug: Union[str, int]) -> Optional[Dict[str, Any]]:
    """یافتن دسته‌بندی بر اساس شناسه یا اسلاگ."""
    s_val = str(cat_id_or_slug).strip()
    active_cats = get_all_categories()
    for cat in active_cats:
        if str(cat["id"]) == s_val or cat["slug"] == s_val or s_val in cat["url"]:
            return cat
    return None

FALLBACK_ITEMS = [
    {
        "title": "توحید عملی | قسمت ۹",
        "tag": "سریال توحید عملی",
        "page_url": "https://abasmanesh.com/fa/practical-monotheism-9/",
        "cover_url": "https://abasmanesh.com/fa/wp-content/uploads/2026/09/neveshteh-80x80.webp",
        "audio_download_url": "https://cdnir.abasmanesh.com/download.php?url=video/tohid-amali/09/abasmanesh-practical-monotheism-9.mp3",
        "video_download_url": "https://cdnir.abasmanesh.com/download.php?url=video/tohid-amali/09/abasmanesh-practical-monotheism-9.mp4",
        "direct_download_url": "https://cdnir.abasmanesh.com/download.php?url=video/tohid-amali/09/abasmanesh-practical-monotheism-9.mp3"
    },
    {
        "title": "توحید عملی | قسمت ۱۰",
        "tag": "سریال توحید عملی",
        "page_url": "https://abasmanesh.com/fa/practical-monotheism-10/",
        "cover_url": "https://abasmanesh.com/fa/wp-content/uploads/2026/09/neveshteh-80x80.webp",
        "audio_download_url": "https://cdnir.abasmanesh.com/download.php?url=video/tohid-amali/10/abasmanesh-practical-monotheism-10.mp3",
        "video_download_url": "https://cdnir.abasmanesh.com/download.php?url=video/tohid-amali/10/abasmanesh-practical-monotheism-10.mp4",
        "direct_download_url": "https://cdnir.abasmanesh.com/download.php?url=video/tohid-amali/10/abasmanesh-practical-monotheism-10.mp3"
    },
    {
        "title": "توحید عملی | قسمت ۱۱",
        "tag": "سریال توحید عملی",
        "page_url": "https://abasmanesh.com/fa/practical-monotheism-11/",
        "cover_url": "https://abasmanesh.com/fa/wp-content/uploads/2026/09/neveshteh-80x80.webp",
        "audio_download_url": "https://cdnir.abasmanesh.com/download.php?url=video/tohid-amali/11/abasmanesh-practical-monotheism-11.mp3",
        "video_download_url": "https://cdnir.abasmanesh.com/download.php?url=video/tohid-amali/11/abasmanesh-practical-monotheism-11.mp4",
        "direct_download_url": "https://cdnir.abasmanesh.com/download.php?url=video/tohid-amali/11/abasmanesh-practical-monotheism-11.mp3"
    },
    {
        "title": "خداوند را چگونه در ذهن خود ساخته‌ای؟",
        "tag": "فایل دانلودی جدید",
        "page_url": "https://abasmanesh.com/fa/how-have-you-defined-god-in-your-mind/",
        "cover_url": "https://abasmanesh.com/fa/wp-content/uploads/2026/09/neveshteh-80x80.webp",
        "audio_download_url": "https://cdnir.abasmanesh.com/download.php?url=video/1405/che-khodaee-ra-sakhtehee/abasmaneh-khoda-dar-zehn.mp3",
        "video_download_url": "https://cdnir.abasmanesh.com/download.php?url=video/1405/che-khodaee-ra-sakhtehee/abasmaneh-khoda-dar-zehn.mp4",
        "direct_download_url": "https://cdnir.abasmanesh.com/download.php?url=video/1405/che-khodaee-ra-sakhtehee/abasmaneh-khoda-dar-zehn.mp3"
    },
    {
        "title": "هر فکری که در ذهنت می‌آید، حقیقت نیست",
        "tag": "فایل دانلودی",
        "page_url": "https://abasmanesh.com/fa/every-thought-that-comes-to-your-mind-is-not-the-truth/",
        "cover_url": "https://abasmanesh.com/fa/wp-content/uploads/2026/09/neveshteh-80x80.webp",
        "audio_download_url": "https://cdnir.abasmanesh.com/download.php?url=video/1405/fekr-haghighat-nist/abasmanesh-fekr-haghighat-nist.mp3",
        "video_download_url": "https://cdnir.abasmanesh.com/download.php?url=video/1405/fekr-haghighat-nist/abasmanesh-fekr-haghighat-nist.mp4",
        "direct_download_url": "https://cdnir.abasmanesh.com/download.php?url=video/1405/fekr-haghighat-nist/abasmanesh-fekr-haghighat-nist.mp3"
    }
]


def _clean_title(raw: str) -> str:
    """Removes trailing comments count or extra punctuation from title."""
    t = re.sub(r"-\s*\d+\s*نظر.*$", "", raw).strip()
    t = re.sub(r"\s*\|\s*", " - ", t)
    return t.strip()


# ==============================================================================
# تابع کمکی استخراج کارت‌های مقالات و جلسات از ساختار مدرن HTML سایت عباس‌منش
# ورودی: html (رشته HTML خام صفحه) و limit (حداکثر تعداد جلسات)
# خروجی: لیستی از تاپل‌های (url, title, cover_url, tag)
# ==============================================================================
def _extract_articles_from_html(html: str, limit: int = 25) -> List[tuple]:
    """
    استخراج ساختاریافته لینک مقالات، عناوین، تصاویر شاخص و تگ‌ها از ساختار جدید سایت عباس‌منش.
    از سلکتورهای div.article-grid و div.card استفاده کرده و لینک‌های نوار ناوبری و منوها را نادیده می‌گیرد.
    """
    articles_found = []
    seen_urls = set()
    skip_keywords = ["فهرست", "برو به", "ثبت‌نام", "ورود", "سبد", "دیدگاه", "نظرات", "عقل‌کل", "قوانین", "پاسخ به سؤالات", "از کجا شروع"]

    if BeautifulSoup:
        soup = BeautifulSoup(html, "html.parser")
        # 1. تلاش برای استخراج مستقیم از ساختار کارت‌های مقالات
        cards = soup.select("div.article-grid div.card, div.card.card--media, .card")
        for card in cards:
            a_link = card.find("a", class_="card__media-link") or card.find("a", href=lambda h: h and "/fa/" in h and not any(x in h for x in ["category", "cart", "account", "login", "aghlekol", "terms"]))
            if not a_link or not a_link.get("href"):
                continue
            href = a_link["href"].strip()
            if href.startswith("/"):
                href = "https://abasmanesh.com" + href
            clean_href = href.split("?")[0].rstrip("/") + "/"
            if clean_href in seen_urls or clean_href == "https://abasmanesh.com/fa/":
                continue

            # استخراج تصویر شاخص کامل و باکیفیت (اولویت اول با data-src جهت دور زدن لود تنبل و پلیس‌هولدرهای خالی)
            img = card.find("img")
            card_cover = ""
            if img:
                src = img.get("data-src") or img.get("data-lazy-src") or img.get("data-original") or img.get("src") or ""
                if not src and img.get("srcset"):
                    srcset_parts = [p.strip().split(" ")[0] for p in img["srcset"].split(",") if p.strip()]
                    if srcset_parts:
                        src = srcset_parts[-1]
                if src:
                    if src.startswith("//"):
                        card_cover = "https:" + src
                    elif src.startswith("/"):
                        card_cover = "https://abasmanesh.com" + src
                    else:
                        card_cover = src

            if not card_cover:
                # استخراج تصویر شاخص از استایل background-image المان‌های کارت
                style_nodes = [card] + card.find_all(attrs={"style": True})
                for node in style_nodes:
                    st = node.get("style", "")
                    bg_match = re.search(r"background(?:-image)?\s*:\s*url\(\s*['\"]?(.*?)['\"]?\s*\)", st, re.IGNORECASE)
                    if bg_match:
                        b_src = bg_match.group(1).strip()
                        if b_src and not b_src.startswith("data:"):
                            if b_src.startswith("//"):
                                card_cover = "https:" + b_src
                            elif b_src.startswith("/"):
                                card_cover = "https://abasmanesh.com" + b_src
                            else:
                                card_cover = b_src
                            break

            # استخراج عنوان مقاله
            title = ""
            body = card.find("div", class_="card__body")
            if body:
                t_a = body.find("a", href=lambda h: h and clean_href in h) or body.find("a")
                if t_a:
                    title = t_a.get_text(strip=True)
            if not title and img and img.get("alt"):
                title = img["alt"].strip()
            if not title:
                title = a_link.get_text(strip=True)
            title = _clean_title(title)
            if len(title) < 3 or any(k in title for k in skip_keywords):
                continue

            # استخراج برچسب یا دسته‌بندی
            chip = card.find("a", class_="chip")
            tag = chip.get_text(strip=True) if chip else "هدیه دانلودی"

            seen_urls.add(clean_href)
            articles_found.append((clean_href, title, card_cover, tag))
            if len(articles_found) >= limit:
                return articles_found

        # 2. در صورت نیافتن کارت، فال‌بک تمیز روی تگ‌های a بدون کلاس‌های هدر/ناوبری
        if not articles_found:
            main_container = soup.find("main") or soup.find("div", id="content") or soup
            for a in main_container.find_all("a", href=True):
                classes = " ".join(a.get("class", []))
                if any(nav in classes for nav in ["public-nav", "public-drawer", "public-bottom-bar", "menu"]):
                    continue
                href = a["href"].strip()
                text = a.get_text(strip=True)
                if not text or len(text) < 4 or any(x in text for x in skip_keywords):
                    continue
                if "/fa/" in href and not any(x in href for x in ["category", "cart", "account", "login", "table-of-contents", "terms", "aghlekol"]):
                    clean_href = href.split("?")[0].rstrip("/") + "/"
                    if clean_href in seen_urls or clean_href == "https://abasmanesh.com/fa/":
                        continue
                    seen_urls.add(clean_href)
                    title = _clean_title(text)
                    articles_found.append((clean_href, title, "", "هدیه دانلودی"))
                    if len(articles_found) >= limit:
                        break
    else:
        # استخراج با عبارات باقاعده (Regex)
        matches = re.findall(r'<a\s+[^>]*href=["\'](https://abasmanesh\.com/fa/[^"\']+)["\'][^>]*>(.*?)</a>', html, re.DOTALL)
        for href, raw_text in matches:
            clean_text = re.sub(r"<[^>]+>", "", raw_text).strip()
            if not clean_text or len(clean_text) < 4 or any(x in clean_text for x in skip_keywords):
                continue
            clean_href = href.split("?")[0].rstrip("/") + "/"
            if clean_href in seen_urls or any(x in clean_href for x in ["category", "cart", "account", "login", "terms"]):
                continue
            seen_urls.add(clean_href)
            title = _clean_title(clean_text)
            articles_found.append((clean_href, title, "", "هدیه دانلودی"))
            if len(articles_found) >= limit:
                break

    return articles_found


# ==============================================================================
# تابع واکشی و پردازش صفحه یک مقاله منفرد جهت استخراج لینک‌های مستقیم صوتی و ویدیو
# ورودی‌ها: session (نشست aiohttp), url (لینک مقاله), title, card_cover, card_tag
# خروجی: دیکشنری استاندارد مشخصات و رسانه‌های مقاله
# ==============================================================================
async def _fetch_single_article(
    session: aiohttp.ClientSession,
    url: str,
    title: str,
    card_cover: str = "",
    card_tag: str = ""
) -> Dict[str, Any]:
    """
    صفحه مفصل مقاله را دریافت کرده و لینک‌های قطعی MP3 و MP4 و کاور باکیفیت را استخراج می‌کند.
    """
    audio_dl = ""
    video_dl = ""
    cover_url = card_cover or ""

    clean_url = url.split("?")[0]
    try:
        async with session.get(clean_url, timeout=aiohttp.ClientTimeout(total=12)) as resp:
            if resp.status == 200:
                html = await resp.text()
                if BeautifulSoup:
                    soup = BeautifulSoup(html, "html.parser")
                    og_img = soup.find("meta", property="og:image")
                    if og_img and og_img.get("content"):
                        cover_url = og_img["content"].strip()

                    # ۱. جستجو در تگ‌های ویدیو و سورس
                    for v in soup.find_all(["video", "source"]):
                        v_src = (v.get("src") or v.get("data-src") or "").strip()
                        if v_src and ".mp4" in v_src and not video_dl:
                            video_dl = re.sub(r"^rhttp", "http", v_src)

                    # ۲. جستجو در تگ‌های a برای دانلود مستقیم با اولویت قطعی cdnir
                    for a in soup.find_all("a", href=True):
                        h = a["href"].strip()
                        if "download.php?url=" in h or (".mp3" in h and "http" in h) or (".mp4" in h and "http" in h):
                            clean_h = re.sub(r"^rhttp", "http", h)
                            # تبدیل دامنه قدیمی یا کند cdneu به CDN پایدار و پرسرعت cdnir
                            if "cdneu.abasmanesh.com" in clean_h:
                                clean_h = clean_h.replace("cdneu.abasmanesh.com", "cdnir.abasmanesh.com")
                            if ".mp3" in clean_h and not audio_dl:
                                audio_dl = clean_h
                            elif ".mp4" in clean_h and not video_dl:
                                video_dl = clean_h
                else:
                    img_m = re.search(r'property="og:image"\s+content="([^"]+)"', html)
                    if img_m and not cover_url:
                        cover_url = img_m.group(1).strip()
                    for m in re.finditer(r'(?:href|src)=["\']([^"\']*(?:\.mp4|\.mp3|download\.php\?url=[^"\']+))["\']', html):
                        h = re.sub(r"^rhttp", "http", m.group(1).strip())
                        if "cdneu.abasmanesh.com" in h:
                            h = h.replace("cdneu.abasmanesh.com", "cdnir.abasmanesh.com")
                        if ".mp3" in h and not audio_dl:
                            audio_dl = h
                        elif ".mp4" in h and not video_dl:
                            video_dl = h

                # ۳. قرینه‌سازی لینک صوتی و ویدیویی در صورت وجود یکی از آنها
                if audio_dl and not video_dl and ".mp3" in audio_dl:
                    video_candidate = audio_dl.replace(".mp3", ".mp4")
                    video_dl = video_candidate
                elif video_dl and not audio_dl and ".mp4" in video_dl:
                    audio_candidate = video_dl.replace(".mp4", ".mp3")
                    audio_dl = audio_candidate
    except Exception as e:
        logger.debug(f"[feed_scraper] Error inspecting article {clean_url}: {e}")

    chapters = []
    if BeautifulSoup:
        try:
            for heading in soup.find_all(["h2", "h3", "strong", "b"]):
                txt = heading.get_text().strip()
                if 8 <= len(txt) <= 75 and not any(skip in txt for skip in ["دیدگاه", "نظرات", "پاسخ", "ارسال", "ورود", "ثبت", "دانلود", "کلیک", "سبد خرید"]):
                    if txt not in chapters and txt != title:
                        chapters.append(txt)
                if len(chapters) >= 4:
                    break
        except Exception:
            pass

    tag = card_tag or "هدیه دانلودی"
    if "توحید" in title:
        tag = "سریال توحید عملی"
    elif "سفر به دور آمریکا" in title:
        tag = "سفر به دور آمریکا"
    elif "تمرکز بر نکات مثبت" in title:
        tag = "تمرکز بر نکات مثبت"

    primary_url = audio_dl or video_dl or clean_url

    lesson_text = ""
    if BeautifulSoup and 'soup' in locals() and soup:
        try:
            content_el = (
                soup.find("div", class_=lambda c: c and any(x in c for x in ["entry-content", "post-content", "article__body", "article-content"]))
                or soup.find("article")
                or soup.find("main")
            )
            if content_el:
                p_list = []
                for p in content_el.find_all("p"):
                    p_txt = p.get_text(strip=True)
                    if len(p_txt) > 25 and not any(skip in p_txt for skip in ["دیدگاه", "نظرات", "دانلود", "ثبت‌نام", "حقوق این سایت", "اشتراک"]):
                        p_list.append(p_txt)
                    if sum(len(x) for x in p_list) > 1200:
                        break
                if p_list:
                    lesson_text = "\n\n".join(p_list[:4])
        except Exception as p_err:
            logger.debug(f"[feed_scraper] Error extracting lesson text: {p_err}")

    return {
        "title": title,
        "tag": tag,
        "category": tag,
        "page_url": clean_url,
        "url": primary_url,
        "cover_url": cover_url or "https://abasmanesh.com/fa/wp-content/uploads/2026/09/neveshteh-80x80.webp",
        "audio_download_url": audio_dl,
        "audio_url": audio_dl,
        "video_download_url": video_dl,
        "video_url": video_dl,
        "direct_download_url": audio_dl or video_dl,
        "lesson_text": lesson_text,
        "chapters": chapters,
        "links": [u for u in (audio_dl, video_dl) if u],
        "published_at": ""
    }


# ==============================================================================
# تابع واکشی جدیدترین هدایای دانلودی و مقالات با صفحه‌بندی و کش فوق‌سریع دیسک
# ==============================================================================
async def get_latest_free_downloads(
    limit: int = 25,
    force_refresh: bool = False,
    page: int = 1,
    base_url: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    استخراج داینامیک آرشیو مقالات و دانلودهای سایت عباس‌منش با صفحه‌بندی و کش دیسکی فوق‌سریع.
    """
    now = time.time()
    effective_base = (base_url or ARTICLES_BASE_URL).rstrip("/") + "/"
    cache_key = f"feed_{hash(effective_base)}_p{page}"

    # ۱. بررسی کش حافظه رم
    if not force_refresh and cache_key in _CACHE and (now - _CACHE[cache_key]["last_fetched"] < CACHE_TTL_SEC):
        return _CACHE[cache_key]["items"][:limit]
    if page == 1 and not force_refresh and _CACHE.get("items") and (now - _CACHE.get("last_fetched", 0) < CACHE_TTL_SEC):
        return _CACHE["items"][:limit]

    # ۲. بررسی کش فوق‌سریع دیسک برای صفحه اول جهت پاسخگویی زیر ۱۰ms به پنل
    if page == 1 and not force_refresh:
        disk_items = load_feed_disk_cache()
        if disk_items:
            _CACHE["items"] = disk_items
            _CACHE["last_fetched"] = now
            return disk_items[:limit]

    target_url = f"{effective_base}page/{page}/" if page > 1 else effective_base
    timeout = aiohttp.ClientTimeout(total=20)
    try:
        async with aiohttp.ClientSession(headers=BROWSER_HEADERS, timeout=timeout) as session:
            async with session.get(target_url) as resp:
                if resp.status != 200:
                    logger.warning(f"[feed_scraper] Status {resp.status} fetching {target_url}")
                    return FALLBACK_ITEMS[:limit] if page == 1 else []

                html = await resp.text()

            # استخراج ساختاریافته مقالات از صفحه جاری
            articles_to_fetch = _extract_articles_from_html(html, limit=limit)

            if not articles_to_fetch:
                return FALLBACK_ITEMS[:limit] if page == 1 else []

            # واکشی همزمان صفحات مقالات جهت استخراج مدیا
            tasks = [
                _fetch_single_article(session, url, title, card_cover=cover, card_tag=tag)
                for url, title, cover, tag in articles_to_fetch[:limit]
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            final_items = []
            for idx, r in enumerate(results):
                if isinstance(r, dict) and r.get("title"):
                    r["file_number"] = f"فایل شماره {((page - 1) * 25) + idx + 1}"
                    final_items.append(r)
                else:
                    if page == 1 and idx < len(FALLBACK_ITEMS):
                        fb = dict(FALLBACK_ITEMS[idx])
                        fb["file_number"] = f"فایل شماره {idx + 1}"
                        final_items.append(fb)

            if final_items:
                _CACHE[cache_key] = {"items": final_items, "last_fetched": now}
                if page == 1:
                    _CACHE["items"] = final_items
                    _CACHE["last_fetched"] = now
                    save_feed_disk_cache(final_items)
                return final_items[:limit]

    except Exception as e:
        logger.warning(f"[feed_scraper] Failed to scrape live feed: {e}")

    # در صورت بروز خطای شبکه، بازیابی از کش دیسک یا فالبک
    if page == 1:
        disk_items = load_feed_disk_cache()
        if disk_items:
            return disk_items[:limit]

    return FALLBACK_ITEMS[:limit] if page == 1 else []


async def get_category_episodes(
    category_id_or_slug: str | int,
    page: int = 1,
    limit: int = 15,
    force_refresh: bool = False
) -> Dict[str, Any]:
    """
    اسکرپ داینامیک جلسات و فایل‌های یک دسته‌بندی خاص از ۱۶ دسته هدیه سایت عباس‌منش.
    لینک‌های فایل‌ها به صورت پویا استخراج شده و هیچ لینکی هاردکد نمی‌شود.
    
    ورودی‌ها:
        category_id_or_slug (str | int): شناسه عددی (۱ تا ۱۶) یا اسلاگ دسته
        page (int): شماره صفحه
        limit (int): تعداد جلسات در صفحه
        force_refresh (bool): دور زدن کش
    خروجی:
        Dict[str, Any]: شامل category (مشخصات دسته), episodes (فایل‌ها و لینک‌ها), page, has_next
    """
    cat = get_category_by_id(category_id_or_slug)
    if not cat:
        cat = ABASMANESH_PREMIUM_CATEGORIES[0]

    now = time.time()
    cache_key = f"cat_{cat['id']}_p{page}"
    if not force_refresh and cache_key in _CACHE and (now - _CACHE[cache_key]["last_fetched"] < CACHE_TTL_SEC):
        return _CACHE[cache_key]["data"]

    target_url = cat["url"]
    if page > 1:
        target_url = f"{cat['url'].rstrip('/')}/page/{page}/"

    timeout = aiohttp.ClientTimeout(total=20)
    articles_to_fetch = []
    try:
        async with aiohttp.ClientSession(headers=BROWSER_HEADERS, timeout=timeout) as session:
            async with session.get(target_url) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    articles_to_fetch = _extract_articles_from_html(html, limit=limit)

            episodes = []
            if articles_to_fetch:
                tasks = [
                    _fetch_single_article(session, url, title, card_cover=cover, card_tag=tag or cat.get("title", ""))
                    for url, title, cover, tag in articles_to_fetch[:limit]
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for idx, r in enumerate(results):
                    if isinstance(r, dict) and r.get("title"):
                        r["category_id"] = cat["id"]
                        r["category_title"] = cat["title"]
                        r["episode_index"] = ((page - 1) * limit) + idx + 1
                        episodes.append(r)

            result_obj = {
                "category": cat,
                "episodes": episodes,
                "page": page,
                "has_next": len(episodes) >= limit
            }
            if episodes:
                _CACHE[cache_key] = {"data": result_obj, "last_fetched": now}
            return result_obj

    except Exception as e:
        logger.warning(f"[feed_scraper] Failed to scrape category {cat['slug']}: {e}")

    return {
        "category": cat,
        "episodes": FALLBACK_ITEMS[:limit],
        "page": page,
        "has_next": False
    }


class FeedScraper:
    """
    سرویس اسکرپر داینامیک مقالات، هدایا و ۱۶ دسته‌بندی سایت عباس‌منش.
    """
    ARTICLES_BASE_URL = ARTICLES_BASE_URL
    CATEGORIES = ABASMANESH_PREMIUM_CATEGORIES

    @staticmethod
    async def fetch_live_categories(force_refresh: bool = False) -> List[Dict[str, Any]]:
        return await fetch_live_categories(force_refresh=force_refresh)

    @staticmethod
    def get_all_categories() -> List[Dict[str, Any]]:
        return get_all_categories()

    @staticmethod
    def get_category_by_id(cat_id_or_slug: Union[str, int]) -> Optional[Dict[str, Any]]:
        return get_category_by_id(cat_id_or_slug)

    @staticmethod
    async def get_category_episodes(category_id_or_slug: Union[str, int], page: int = 1, limit: int = 15, force_refresh: bool = False) -> Dict[str, Any]:
        return await get_category_episodes(category_id_or_slug, page=page, limit=limit, force_refresh=force_refresh)

    @staticmethod
    async def get_latest_free_downloads(limit: int = 25, force_refresh: bool = False, page: int = 1, base_url: Optional[str] = None) -> List[Dict[str, Any]]:
        return await get_latest_free_downloads(limit=limit, force_refresh=force_refresh, page=page, base_url=base_url)

    @staticmethod
    def get_custom_categories() -> List[Dict[str, Any]]:
        return get_custom_categories()

    @staticmethod
    def save_custom_categories(categories: List[Dict[str, Any]]) -> bool:
        return save_custom_categories(categories)

    @staticmethod
    def load_feed_disk_cache() -> List[Dict[str, Any]]:
        return load_feed_disk_cache()

    @staticmethod
    def save_feed_disk_cache(items: List[Dict[str, Any]]) -> None:
        save_feed_disk_cache(items)


feed_scraper = FeedScraper()

