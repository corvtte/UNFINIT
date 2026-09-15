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

# In-memory cache to prevent spamming target site
_CACHE: Dict[str, Any] = {
    "items": [],
    "last_fetched": 0.0
}
CACHE_TTL_SEC = 300.0  # 5 minutes cache

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


async def _fetch_single_article(session: aiohttp.ClientSession, url: str, title: str) -> Dict[str, Any]:
    """Fetches single article page and parses direct media links & cover."""
    audio_dl = ""
    video_dl = ""
    cover_url = ""

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

                    for a in soup.find_all("a", href=True):
                        h = a["href"].strip()
                        if "download.php?url=" in h or (".mp3" in h and "http" in h) or (".mp4" in h and "http" in h):
                            # normalize rhttps:// or malformed links
                            clean_h = re.sub(r"^rhttp", "http", h)
                            if ".mp3" in clean_h and not audio_dl:
                                audio_dl = clean_h
                            elif ".mp4" in clean_h and not video_dl:
                                video_dl = clean_h
                else:
                    # Regex fallback
                    img_m = re.search(r'property="og:image"\s+content="([^"]+)"', html)
                    if img_m:
                        cover_url = img_m.group(1).strip()
                    for m in re.finditer(r'href="([^"]*download\.php\?url=[^"]+)"', html):
                        h = re.sub(r"^rhttp", "http", m.group(1).strip())
                        if ".mp3" in h and not audio_dl:
                            audio_dl = h
                        elif ".mp4" in h and not video_dl:
                            video_dl = h
    except Exception as e:
        logger.debug(f"[feed_scraper] Error inspecting article {clean_url}: {e}")

    tag = "هدیه دانلودی"
    if "توحید" in title:
        tag = "سریال توحید عملی"
    elif "سفر به دور آمریکا" in title:
        tag = "سفر به دور آمریکا"
    elif "تمرکز بر نکات مثبت" in title:
        tag = "تمرکز بر نکات مثبت"

    return {
        "title": title,
        "tag": tag,
        "page_url": clean_url,
        "cover_url": cover_url or "https://abasmanesh.com/fa/wp-content/uploads/2026/09/neveshteh-80x80.webp",
        "audio_download_url": audio_dl,
        "video_download_url": video_dl,
        "direct_download_url": audio_dl or video_dl,
        "links": [u for u in (audio_dl, video_dl) if u]
    }


async def get_latest_free_downloads(limit: int = 5, force_refresh: bool = False) -> List[Dict[str, Any]]:
    """
    Scrapes the 5 most recent free downloads from abasmanesh.com/fa/free-download-list/.
    Returns a structured list of dicts with title, direct media links, and cover.
    """
    now = time.time()
    if not force_refresh and _CACHE["items"] and (now - _CACHE["last_fetched"] < CACHE_TTL_SEC):
        return _CACHE["items"][:limit]

    timeout = aiohttp.ClientTimeout(total=20)
    try:
        async with aiohttp.ClientSession(headers=BROWSER_HEADERS, timeout=timeout) as session:
            async with session.get(BASE_FEED_URL) as resp:
                if resp.status != 200:
                    logger.warning(f"[feed_scraper] Status {resp.status} fetching {BASE_FEED_URL}")
                    return FALLBACK_ITEMS[:limit]

                html = await resp.text()

            articles_to_fetch = []
            if BeautifulSoup:
                soup = BeautifulSoup(html, "html.parser")
                main_container = soup.find("main") or soup.find("div", id="content") or soup
                links = main_container.find_all("a", href=True)
                seen_urls = set()
                for a in links:
                    href = a["href"].strip()
                    text = a.get_text(strip=True)
                    if not text or len(text) < 4:
                        continue
                    if any(x in text for x in ["فهرست", "برو به", "ثبت‌نام", "ورود", "سبد", "دیدگاه"]):
                        continue
                    if "/fa/" in href and not any(x in href for x in ["category", "cart", "account", "login", "table-of-contents"]):
                        clean_href = href.split("?")[0].rstrip("/") + "/"
                        if clean_href in seen_urls or clean_href == "https://abasmanesh.com/fa/":
                            continue
                        seen_urls.add(clean_href)
                        title = _clean_title(text)
                        articles_to_fetch.append((clean_href, title))
                        if len(articles_to_fetch) >= limit:
                            break
            else:
                # Regex extraction
                seen_urls = set()
                matches = re.findall(r'<a\s+[^>]*href=["\'](https://abasmanesh\.com/fa/[^"\']+)["\'][^>]*>(.*?)</a>', html, re.DOTALL)
                for href, raw_text in matches:
                    clean_text = re.sub(r"<[^>]+>", "", raw_text).strip()
                    if not clean_text or len(clean_text) < 4:
                        continue
                    if any(x in clean_text for x in ["فهرست", "برو به", "ثبت‌نام", "ورود", "سبد", "دیدگاه"]):
                        continue
                    clean_href = href.split("?")[0].rstrip("/") + "/"
                    if clean_href in seen_urls or "category" in clean_href:
                        continue
                    seen_urls.add(clean_href)
                    title = _clean_title(clean_text)
                    articles_to_fetch.append((clean_href, title))
                    if len(articles_to_fetch) >= limit:
                        break

            if not articles_to_fetch:
                return FALLBACK_ITEMS[:limit]

            # Concurrently fetch article pages
            tasks = [
                _fetch_single_article(session, url, title)
                for url, title in articles_to_fetch[:limit]
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            final_items = []
            for idx, r in enumerate(results):
                if isinstance(r, dict) and r.get("title"):
                    final_items.append(r)
                else:
                    if idx < len(FALLBACK_ITEMS):
                        final_items.append(FALLBACK_ITEMS[idx])

            if final_items:
                _CACHE["items"] = final_items
                _CACHE["last_fetched"] = now
                return final_items[:limit]

    except Exception as e:
        logger.warning(f"[feed_scraper] Failed to scrape live feed: {e}")

    return FALLBACK_ITEMS[:limit]
