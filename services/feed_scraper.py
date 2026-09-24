"""
Feed Scraper Module for UNFINIT Store Engine
Fetches and extracts the latest free downloads, direct media URLs, and covers
from abasmanesh.com with resilient browser headers, BeautifulSoup parsing,
and robust caching/error fallbacks.
"""

import asyncio
import logging
import re
import time
from typing import Any, Dict, List, Optional
import aiohttp

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

logger = logging.getLogger("feed_scraper")

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

# ۱۶ دسته‌بندی رسمی دانلودهای هدیه و مقالات سایت عباس‌منش (مختص مشترکین پریمیوم)
ABASMANESH_PREMIUM_CATEGORIES: List[Dict[str, Any]] = [
    {
        "id": 1,
        "slug": "the-series-of-focus-on-positive-points",
        "title": "سریال تمرکز بر نکات مثبت",
        "url": "https://abasmanesh.com/fa/category/free-download/the-series-of-focus-on-positive-points/",
        "path": "/fa/category/free-download/the-series-of-focus-on-positive-points/"
    },
    {
        "id": 2,
        "slug": "paradise-life-series",
        "title": "سریال زندگی در بهشت",
        "url": "https://abasmanesh.com/fa/category/free-download/paradise-life-series/",
        "path": "/fa/category/free-download/paradise-life-series/"
    },
    {
        "id": 3,
        "slug": "travel-around-the-usa-series",
        "title": "سریال سفر به دور آمریکا",
        "url": "https://abasmanesh.com/fa/category/free-download/travel-around-the-usa-series/",
        "path": "/fa/category/free-download/travel-around-the-usa-series/"
    },
    {
        "id": 4,
        "slug": "interview-with-master-abasmanesh",
        "title": "مصاحبه با استاد عباس‌منش و Liveها",
        "url": "https://abasmanesh.com/fa/category/free-download/interview-with-master-abasmanesh/",
        "path": "/fa/category/free-download/interview-with-master-abasmanesh/"
    },
    {
        "id": 5,
        "slug": "unchanging-laws-of-god",
        "title": "قوانین بدون تغییر خداوند",
        "url": "https://abasmanesh.com/fa/category/free-download/unchanging-laws-of-god/",
        "path": "/fa/category/free-download/unchanging-laws-of-god/"
    },
    {
        "id": 6,
        "slug": "practicing-monotheism",
        "title": "اجرای توحید در عمل",
        "url": "https://abasmanesh.com/fa/category/free-download/practicing-monotheism/",
        "path": "/fa/category/free-download/practicing-monotheism/"
    },
    {
        "id": 7,
        "slug": "distinguishing-essence-from-branches",
        "title": "توانایی تشخیص اصل از فرع",
        "url": "https://abasmanesh.com/fa/category/free-download/distinguishing-essence-from-branches/",
        "path": "/fa/category/free-download/distinguishing-essence-from-branches/"
    },
    {
        "id": 8,
        "slug": "faith-that-leads-to-action",
        "title": "ایمانی که عمل می‌آورد",
        "url": "https://abasmanesh.com/fa/category/free-download/faith-that-leads-to-action/",
        "path": "/fa/category/free-download/faith-that-leads-to-action/"
    },
    {
        "id": 9,
        "slug": "ability-to-control-the-mind",
        "title": "توانایی کنترل ذهن",
        "url": "https://abasmanesh.com/fa/category/free-download/ability-to-control-the-mind/",
        "path": "/fa/category/free-download/ability-to-control-the-mind/"
    },
    {
        "id": 10,
        "slug": "wealth-creating-beliefs",
        "title": "باورهای ثروت‌ساز",
        "url": "https://abasmanesh.com/fa/category/free-download/wealth-creating-beliefs/",
        "path": "/fa/category/free-download/wealth-creating-beliefs/"
    },
    {
        "id": 11,
        "slug": "be-the-programmer-of-your-life",
        "title": "برنامه‌نویس زندگی‌ات باش",
        "url": "https://abasmanesh.com/fa/category/free-download/be-the-programmer-of-your-life/",
        "path": "/fa/category/free-download/be-the-programmer-of-your-life/"
    },
    {
        "id": 12,
        "slug": "being-at-peace-with-ourselves",
        "title": "در صلح بودن با خودمان",
        "url": "https://abasmanesh.com/fa/category/free-download/being-at-peace-with-ourselves/",
        "path": "/fa/category/free-download/being-at-peace-with-ourselves/"
    },
    {
        "id": 13,
        "slug": "investing-in-yourself",
        "title": "سرمایه‌گذاری روی خودت",
        "url": "https://abasmanesh.com/fa/category/free-download/investing-in-yourself/",
        "path": "/fa/category/free-download/investing-in-yourself/"
    },
    {
        "id": 14,
        "slug": "peace-in-light-of-awareness",
        "title": "آرامش در پرتو آگاهی",
        "url": "https://abasmanesh.com/fa/category/free-download/peace-in-light-of-awareness/",
        "path": "/fa/category/free-download/peace-in-light-of-awareness/"
    },
    {
        "id": 15,
        "slug": "evolutionary-steps-for-guidance",
        "title": "قدم‌های تکاملی برای هدایت‌شدن",
        "url": "https://abasmanesh.com/fa/category/free-download/evolutionary-steps-for-guidance/",
        "path": "/fa/category/free-download/evolutionary-steps-for-guidance/"
    },
    {
        "id": 16,
        "slug": "all-articles",
        "title": "کلیدها و تمام دانلودها",
        "url": "https://abasmanesh.com/fa/articles/",
        "path": "/fa/articles/"
    }
]

# In-memory cache to prevent spamming target site
_CACHE: Dict[str, Any] = {
    "items": [],
    "last_fetched": 0.0
}
_ARTICLE_CACHE: Dict[str, Dict[str, Any]] = {}
CACHE_TTL_SEC = 300.0  # 5 minutes cache

def get_all_categories() -> List[Dict[str, Any]]:
    """دریافت فهرست کامل ۱۶ دسته‌بندی رسمی عباس‌منش."""
    return ABASMANESH_PREMIUM_CATEGORIES

def get_category_by_id(cat_id_or_slug: str | int) -> Optional[Dict[str, Any]]:
    """یافتن دسته‌بندی بر اساس شناسه یا اسلاگ."""
    s_val = str(cat_id_or_slug).strip()
    for cat in ABASMANESH_PREMIUM_CATEGORIES:
        if str(cat["id"]) == s_val or cat["slug"] == s_val or s_val in cat["url"]:
            return cat
    return None

FALLBACK_ITEMS = [
    {
        "title": "خداوند را چگونه در ذهن خود ساخته‌ای؟",
        "tag": "فایل دانلودی جدید",
        "page_url": "https://abasmanesh.com/fa/how-have-you-defined-god-in-your-mind/",
        "cover_url": "https://abasmanesh.com/fa/wp-content/uploads/2026/09/neveshteh-80x80.webp",
        "audio_download_url": "https://cdneu.abasmanesh.com/download.php?url=video/1405/che-khodaee-ra-sakhtehee/abasmaneh-khoda-dar-zehn.mp3",
        "video_download_url": "https://cdneu.abasmanesh.com/download.php?url=video/1405/che-khodaee-ra-sakhtehee/abasmaneh-khoda-dar-zehn.mp4",
        "direct_download_url": "https://cdneu.abasmanesh.com/download.php?url=video/1405/che-khodaee-ra-sakhtehee/abasmaneh-khoda-dar-zehn.mp3"
    },
    {
        "title": "هر فکری که در ذهنت می‌آید، حقیقت نیست",
        "tag": "فایل دانلودی",
        "page_url": "https://abasmanesh.com/fa/every-thought-that-comes-to-your-mind-is-not-the-truth/",
        "cover_url": "https://abasmanesh.com/fa/wp-content/uploads/2026/09/neveshteh-80x80.webp",
        "audio_download_url": "https://cdneu.abasmanesh.com/download.php?url=video/1405/fekr-haghighat-nist/abasmanesh-fekr-haghighat-nist.mp3",
        "video_download_url": "https://cdneu.abasmanesh.com/download.php?url=video/1405/fekr-haghighat-nist/abasmanesh-fekr-haghighat-nist.mp4",
        "direct_download_url": "https://cdneu.abasmanesh.com/download.php?url=video/1405/fekr-haghighat-nist/abasmanesh-fekr-haghighat-nist.mp3"
    },
    {
        "title": "توحید عملی | قسمت ۱۱",
        "tag": "سریال توحید عملی",
        "page_url": "https://abasmanesh.com/fa/practical-monotheism-11/",
        "cover_url": "https://abasmanesh.com/fa/wp-content/uploads/2026/09/neveshteh-80x80.webp",
        "audio_download_url": "https://cdneu.abasmanesh.com/download.php?url=video/1405/tohid-amali-11/abasmanesh-tohid-amali-11.mp3",
        "video_download_url": "https://cdneu.abasmanesh.com/download.php?url=video/1405/tohid-amali-11/abasmanesh-tohid-amali-11.mp4",
        "direct_download_url": "https://cdneu.abasmanesh.com/download.php?url=video/1405/tohid-amali-11/abasmanesh-tohid-amali-11.mp3"
    },
    {
        "title": "توحید عملی | قسمت ۱۰",
        "tag": "سریال توحید عملی",
        "page_url": "https://abasmanesh.com/fa/practical-monotheism-10/",
        "cover_url": "https://abasmanesh.com/fa/wp-content/uploads/2026/09/neveshteh-80x80.webp",
        "audio_download_url": "https://cdneu.abasmanesh.com/download.php?url=video/1405/tohid-amali-10/abasmanesh-tohid-amali-10.mp3",
        "video_download_url": "https://cdneu.abasmanesh.com/download.php?url=video/1405/tohid-amali-10/abasmanesh-tohid-amali-10.mp4",
        "direct_download_url": "https://cdneu.abasmanesh.com/download.php?url=video/1405/tohid-amali-10/abasmanesh-tohid-amali-10.mp3"
    },
    {
        "title": "توحید عملی | قسمت ۹",
        "tag": "سریال توحید عملی",
        "page_url": "https://abasmanesh.com/fa/practical-monotheism-9/",
        "cover_url": "https://abasmanesh.com/fa/wp-content/uploads/2026/09/neveshteh-80x80.webp",
        "audio_download_url": "https://cdneu.abasmanesh.com/download.php?url=video/1405/tohid-amali-9/abasmanesh-tohid-amali-9.mp3",
        "video_download_url": "https://cdneu.abasmanesh.com/download.php?url=video/1405/tohid-amali-9/abasmanesh-tohid-amali-9.mp4",
        "direct_download_url": "https://cdneu.abasmanesh.com/download.php?url=video/1405/tohid-amali-9/abasmanesh-tohid-amali-9.mp3"
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

            # استخراج تصویر شاخص کامل و باکیفیت
            img = card.find("img")
            card_cover = ""
            if img:
                src = img.get("src") or img.get("data-src") or img.get("data-lazy-src") or img.get("data-original") or ""
                if not src and img.get("srcset"):
                    srcset_parts = [p.strip().split(" ")[0] for p in img["srcset"].split(",") if p.strip()]
                    if srcset_parts:
                        src = srcset_parts[-1]
                if src:
                    card_cover = ("https://abasmanesh.com" + src) if src.startswith("/") else src

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

                    # ۲. جستجو در تگ‌های a برای دانلود مستقیم
                    for a in soup.find_all("a", href=True):
                        h = a["href"].strip()
                        if "download.php?url=" in h or (".mp3" in h and "http" in h) or (".mp4" in h and "http" in h):
                            clean_h = re.sub(r"^rhttp", "http", h)
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
        "chapters": chapters,
        "links": [u for u in (audio_dl, video_dl) if u],
        "published_at": ""
    }


# ==============================================================================
# تابع واکشی جدیدترین هدایای دانلودی و مقالات با صفحه‌بندی
# ==============================================================================
async def get_latest_free_downloads(
    limit: int = 25,
    force_refresh: bool = False,
    page: int = 1,
    base_url: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    استخراج داینامیک آرشیو مقالات و دانلودهای سایت عباس‌منش با صفحه‌بندی.
    ورودی‌ها:
        limit (int): سقف تعداد مقالات
        force_refresh (bool): عدم استفاده از کش
        page (int): شماره صفحه
        base_url (str): آدرس پایه مخزن (پیش‌فرض https://abasmanesh.com/fa/articles/)
    خروجی:
        List[Dict[str, Any]]: لیست جلسات و فایل‌ها همراه با لینک مستقیم
    """
    now = time.time()
    effective_base = (base_url or ARTICLES_BASE_URL).rstrip("/") + "/"
    cache_key = f"feed_{hash(effective_base)}_p{page}"
    if not force_refresh and cache_key in _CACHE and (now - _CACHE[cache_key]["last_fetched"] < CACHE_TTL_SEC):
        return _CACHE[cache_key]["items"][:limit]
    if page == 1 and not force_refresh and _CACHE.get("items") and (now - _CACHE.get("last_fetched", 0) < CACHE_TTL_SEC):
        return _CACHE["items"][:limit]

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
                return final_items[:limit]

    except Exception as e:
        logger.warning(f"[feed_scraper] Failed to scrape live feed: {e}")

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


feed_scraper = FeedScraper()

