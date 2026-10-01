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
import os
import random
from core.database import get_system_setting

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

logger = logging.getLogger("feed_crawler")

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
FREE_DOWNLOAD_BASE_URL = "https://abasmanesh.com/fa/articles/"

# فهرست رسمی ۱۷ دسته‌بندی استخراج‌شده زنده از ساختار واقعی سایت عباس‌منش
OFFICIAL_17_CATEGORIES: List[Dict[str, Any]] = [
    {
        "id": 1,
        "emoji": "🎁",
        "slug": "free-download",
        "title": "تمام دانلودها (آرشیو هدایا)",
        "url": "https://abasmanesh.com/fa/articles/",
        "path": "/fa/articles/"
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
    """
    if not tag_or_soup:
        return ""

    candidate_url = ""

    if hasattr(tag_or_soup, "find"):
        meta_og = tag_or_soup.find("meta", property="og:image")
        if meta_og and meta_og.get("content"):
            candidate_url = meta_og.get("content").strip()

    if not candidate_url and hasattr(tag_or_soup, "find_all"):
        for img_tag in tag_or_soup.find_all("img"):
            src = img_tag.get("src", "") or img_tag.get("data-src", "")
            if "/storage/media/" in src and not src.startswith("data:"):
                candidate_url = src.strip()
                break

    img = tag_or_soup if getattr(tag_or_soup, "name", None) == "img" else getattr(tag_or_soup, "find", lambda x: None)("img")

    if not candidate_url and img:
        for attr in ("data-src", "data-lazy-src", "data-original", "data-lazy", "data-url"):
            val = img.get(attr, "").strip()
            if val and not val.startswith("data:"):
                candidate_url = val
                break

        if not candidate_url and img.get("srcset"):
            raw_srcset = img["srcset"].strip()
            parts = [p.strip().split(" ")[0] for p in raw_srcset.split(",") if p.strip()]
            valid_parts = [p for p in parts if not p.startswith("data:")]
            if valid_parts:
                candidate_url = valid_parts[-1]

        if not candidate_url and img.get("src"):
            raw_src = img["src"].strip()
            if raw_src and not raw_src.startswith("data:"):
                candidate_url = raw_src

    if not candidate_url and hasattr(tag_or_soup, "find_all"):
        nodes = [tag_or_soup] + list(tag_or_soup.find_all(attrs={"style": True}))
        for node in nodes:
            style_str = node.get("style", "")
            import re
            m = re.search(r"background(?:-image)?\s*:\s*url\(\s*['\"]?(.*?)['\"]?\s*\)", style_str, re.IGNORECASE)
            if m:
                bg_val = m.group(1).strip()
                if bg_val and not bg_val.startswith("data:"):
                    candidate_url = bg_val
                    break

    if candidate_url:
        if candidate_url.startswith("//"):
            candidate_url = "https:" + candidate_url
        elif candidate_url.startswith("/"):
            candidate_url = "https://abasmanesh.com" + candidate_url

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



SESSION_FILE = "data/abasmanesh_session.json"

class FeedAuthManager:
    _session = None
    _semaphore = asyncio.Semaphore(1)

    @classmethod
    def get_semaphore(cls):
        return cls._semaphore

    @classmethod
    async def get_session(cls) -> aiohttp.ClientSession:
        if cls._session is None or cls._session.closed:
            jar = aiohttp.CookieJar(unsafe=True)
            if os.path.exists(SESSION_FILE):
                try:
                    jar.load(SESSION_FILE)
                except Exception as e:
                    logger.error(f"[FeedAuthManager] Error loading cookies: {e}")
            cls._session = aiohttp.ClientSession(headers=BROWSER_HEADERS, cookie_jar=jar)
        return cls._session

    @classmethod
    async def save_session(cls):
        if cls._session and cls._session.cookie_jar:
            try:
                os.makedirs("data", exist_ok=True)
                cls._session.cookie_jar.save(SESSION_FILE)
            except Exception as e:
                logger.error(f"[FeedAuthManager] Error saving cookies: {e}")

    @classmethod
    async def login_if_needed(cls) -> bool:
        session = await cls.get_session()
        
        # Priority 1: Direct Session Cookie Injection
        auth_cookie = (os.getenv("FEED_AUTH_COOKIE") or await get_system_setting("FEED_AUTH_COOKIE", "")).strip()
        if auth_cookie:
            # Smart Laravel Cookie Sanitizer
            directives = {"expires", "max-age", "path", "domain", "samesite", "secure", "httponly"}
            parts = re.split(r'[;\\n]', auth_cookie)
            extracted_cookies = {}
            for part in parts:
                part = part.strip()
                if not part:
                    continue
                if "=" in part:
                    k, v = part.split("=", 1)
                    k = k.strip()
                    v = v.strip()
                    if k.lower() not in directives:
                        extracted_cookies[k] = v
            
            if extracted_cookies:
                session.cookie_jar.update_cookies(extracted_cookies)
                
            # Verify cookie validity against a protected URL
            try:
                # Probe a known gated URL
                async with session.get("https://abasmanesh.com/fa/", timeout=15) as resp:
                    html = await resp.text()
                    # Check if ungated or user profile is present
                    if ("ورود / عضویت" not in html) and ("خروج" in html or "پروفایل" in html):
                        logger.info("[FeedAuthManager] Priority Cookie Injection successful!")
                        await cls.save_session()
                        return True
            except Exception as e:
                logger.error(f"[FeedAuthManager] Priority Cookie Auth failed: {e}")

        # Priority 2: Alpine.js / Custom Form Auto Login
        email = (os.getenv("FEED_AUTH_EMAIL") or os.getenv("ABASMANESH_EMAIL") or await get_system_setting("FEED_AUTH_EMAIL", "") or await get_system_setting("ABASMANESH_EMAIL", "")).strip()
        password = (os.getenv("FEED_AUTH_PASSWORD") or os.getenv("ABASMANESH_PASSWORD") or await get_system_setting("FEED_AUTH_PASSWORD", "") or await get_system_setting("ABASMANESH_PASSWORD", "")).strip()
        
        if not email or not password:
            logger.warning("[FeedAuthManager] Missing Auth Credentials.")
            return False

        try:
            # 1. Fetch login page to grab CSRF/XSRF tokens
            async with session.get("https://abasmanesh.com/fa/login/", timeout=15) as resp:
                html = await resp.text()
                if "خروج" in html or "پروفایل" in html:
                    logger.info("[FeedAuthManager] Already logged in via saved cookies.")
                    return True
                
                # Extract CSRF token from meta or inputs
                csrf_token = ""
                m = re.search(r'<meta name="csrf-token" content="([^"]+)">', html)
                if m:
                    csrf_token = m.group(1)
                else:
                    m = re.search(r'name="_token" value="([^"]+)"', html)
                    if m:
                        csrf_token = m.group(1)

            # 2. Prepare modern headers
            headers = dict(BROWSER_HEADERS)
            headers.update({
                "Accept": "application/json, text/html, */*",
                "X-Requested-With": "XMLHttpRequest",
            })
            if csrf_token:
                headers["X-CSRF-TOKEN"] = csrf_token

            payload = {
                "email": email,
                "password": password,
                "_token": csrf_token,
                "remember": "on"
            }
            
            async with session.post("https://abasmanesh.com/fa/login/", data=payload, headers=headers, timeout=15) as post_resp:
                post_html = await post_resp.text()
                if post_resp.status in [200, 302] and ("خروج" in post_html or "پروفایل" in post_html or post_resp.status == 302):
                    logger.info("[FeedAuthManager] Alpine.js Login successful!")
                    await cls.save_session()
                    return True
                else:
                    logger.error(f"[FeedAuthManager] Login failed. HTTP {post_resp.status}. Snippet: {post_html[:100]}")
                    return False
        except Exception as e:
            logger.error(f"[FeedAuthManager] Login exception: {e}")
            return False

    @classmethod
    async def invalidate_session(cls):
        if cls._session and not cls._session.closed:
            await cls._session.close()
        cls._session = None
        if os.path.exists(SESSION_FILE):
            try:
                os.remove(SESSION_FILE)
            except:
                pass

    @classmethod
    async def fetch_html_with_auth(cls, url: str, timeout=15) -> tuple[int, str]:
        async with cls.get_semaphore():
            await asyncio.sleep(random.uniform(1.5, 3.5))
            session = await cls.get_session()
            async with session.get(url, timeout=timeout) as resp:
                status = resp.status
                html = await resp.text()
            
            if "برای مشاهده این محتوا باید وارد شوید" in html or "login" in str(resp.url):
                logger.warning(f"[FeedAuthManager] Auth wall detected at {url}. Auto-healing...")
                await cls.invalidate_session()
                logged_in = await cls.login_if_needed()
                if logged_in:
                    await asyncio.sleep(random.uniform(1.5, 3.5))
                    session = await cls.get_session()
                    async with session.get(url, timeout=timeout) as resp2:
                        status = resp2.status
                        html = await resp2.text()
                else:
                    return 401, html
            
            return status, html

    @classmethod
    async def test_connection(cls) -> dict:
        """Lightweight authenticated probe to check connection health and auth status"""
        try:
            await cls.invalidate_session()
            await cls.login_if_needed()
            session = await cls.get_session()
            async with session.get("https://abasmanesh.com/fa/", timeout=15) as resp:
                html = await resp.text()
                status = resp.status
                redirect_url = str(resp.url)
                body_preview = html[:250].strip()
                
                is_ok = ("ورود / عضویت" not in html) and ("خروج" in html or "پروفایل" in html)
                
                if is_ok:
                    msg = "نشست فعال با هویت معتبر کاربر تأیید شد."
                    logger.info(f"[FeedAuthManager] Test Connection Success - Status: {status}")
                    return {"success": True, "status_code": status, "message": msg, "authenticated": True}
                else:
                    msg = f"پاسخ خام (کد {status}):\n{body_preview}..."
                    logger.error(f"[FeedAuthManager] Test Connection Failed - Status: {status}, Body Preview: {body_preview}")
                    return {"success": False, "status_code": status, "message": msg, "authenticated": False}
        except Exception as e:
            logger.error(f"[FeedAuthManager] Test Connection Network Error: {e}")
            return {"success": False, "status_code": 500, "message": f"خطای ارتباطی: {str(e)}", "authenticated": False}

class FeedCrawler:

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
            status, html = await FeedAuthManager.fetch_html_with_auth(clean_url, timeout=15)
            if status == 200:
                    if BeautifulSoup:
                        soup = BeautifulSoup(html, "html.parser")
                        og_img = soup.find("meta", property="og:image")
                        if og_img and og_img.get("content"):
                            final_cover = og_img["content"].strip()

                        # جستجو در تگ‌های ویدیو و سورس
                        for v in soup.find_all(["video", "audio", "source"]):
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
            logger.debug(f"[feed_crawler] Error inspecting article {clean_url}: {e}")

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
    async def scrape_single_item(cls, url: str) -> Optional[Dict[str, Any]]:
        sess = await FeedAuthManager.get_session()
        res = await cls.fetch_article_details(sess, url)
        if res:
            dl_links = []
            if res.get("audio_url"):
                dl_links.append({"type": "audio", "url": res["audio_url"]})
            if res.get("video_url"):
                dl_links.append({"type": "video", "url": res["video_url"]})
            if res.get("direct_download_url"):
                dl_links.append({"type": "file", "url": res["direct_download_url"]})
            res["download_links"] = dl_links
            return res
        return None

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

        timeout = 20
        articles_to_fetch = []
        try:
            status, html = await FeedAuthManager.fetch_html_with_auth(target_url, timeout=timeout)
            if status == 401:
                 return {"ok": False, "category": cat, "episodes": [], "page": page, "has_next": False, "error": "LOGIN_REQUIRED"}
            if status == 200:
                session = await FeedAuthManager.get_session()
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
            logger.warning(f"[feed_crawler] Error crawling category {cat['slug']}: {e}")
            return {
                "ok": False,
                "category": cat,
                "episodes": [],
                "page": page,
                "has_next": False,
                "error": str(e)
            }


crawler = FeedCrawler()

