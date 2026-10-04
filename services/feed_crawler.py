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
    import urllib.parse
    if not tag_or_soup:
        return ""

    candidate_url = ""

    def get_highest_res_from_srcset(srcset_str):
        if not srcset_str: return ""
        parts = [p.strip() for p in srcset_str.split(',') if p.strip()]
        best_url = ""
        max_w = -1
        for p in parts:
            pieces = p.split()
            if pieces:
                url = pieces[0]
                w = 0
                if len(pieces) > 1 and pieces[1].endswith('w'):
                    try:
                        w = int(pieces[1][:-1])
                    except:
                        pass
                if w > max_w and not "80x80" in url and not ".svg" in url:
                    max_w = w
                    best_url = url
        return best_url

    if hasattr(tag_or_soup, "find"):
        meta_og = tag_or_soup.find("meta", property="og:image")
        if meta_og and meta_og.get("content"):
            candidate_url = meta_og.get("content").strip()

    if not candidate_url and hasattr(tag_or_soup, "find"):
        img_tag = tag_or_soup.find("img")
        if img_tag:
            # 1. srcset
            for attr in ("data-srcset", "srcset"):
                val = img_tag.get(attr, "").strip()
                if val:
                    best = get_highest_res_from_srcset(val)
                    if best:
                        candidate_url = best
                        break
            # 2. lazy attributes
            if not candidate_url:
                for attr in ("data-large-file", "data-src", "data-lazy-src", "data-original", "data-lazy", "data-url", "src"):
                    val = img_tag.get(attr, "").strip()
                    if val and not val.startswith("data:") and not "data:image/svg+xml" in val and not "80x80" in val:
                        candidate_url = val
                        break

    if candidate_url:
        candidate_url = urllib.parse.urljoin("https://abasmanesh.com", candidate_url)
        candidate_url = candidate_url.replace("/storage//storage/", "/storage/")

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
    _sessions = {}
    _semaphores = {}

    @classmethod
    def get_semaphore(cls):
        try:
            loop = asyncio.get_running_loop()
        except:
            return asyncio.Semaphore(1)
        if loop not in cls._semaphores:
            cls._semaphores[loop] = asyncio.Semaphore(1)
        return cls._semaphores[loop]

    @classmethod
    async def get_session(cls) -> aiohttp.ClientSession:
        try:
            loop = asyncio.get_running_loop()
        except:
            loop = None
            
        sess = cls._sessions.get(loop) if loop else None
        if sess is None or sess.closed:
            jar = aiohttp.CookieJar(unsafe=True)
            if os.path.exists(SESSION_FILE):
                try:
                    jar.load(SESSION_FILE)
                except Exception as e:
                    pass
            sess = aiohttp.ClientSession(headers=BROWSER_HEADERS, cookie_jar=jar)
            if loop:
                cls._sessions[loop] = sess
        return sess

    @classmethod
    async def save_session(cls):
        sess = await cls.get_session()
        if sess and sess.cookie_jar:
            try:
                os.makedirs("data", exist_ok=True)
                sess.cookie_jar.save(SESSION_FILE)
            except Exception as e:
                pass

    @classmethod
    async def login_if_needed(cls) -> bool:
        session = await cls.get_session()
        
        # Priority 1: Direct Session Cookie Injection
        auth_cookie = (await get_system_setting("FEED_AUTH_COOKIE", "")).strip()
        if auth_cookie:
            directives = {"expires", "max-age", "path", "domain", "samesite", "secure", "httponly"}
            parts = re.split(r'[;\n]', auth_cookie)
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
                import yarl
                session.cookie_jar.update_cookies(extracted_cookies, response_url=yarl.URL("https://abasmanesh.com"))
                
            try:
                async with session.get("https://abasmanesh.com/fa/profile/", allow_redirects=False, timeout=10) as profile_resp:
                    if profile_resp.status == 200:
                        await cls.save_session()
                        return True
            except Exception as e:
                pass

        username = (await get_system_setting("FEED_AUTH_EMAIL", "")).strip()
        password = (await get_system_setting("FEED_AUTH_PASSWORD", "")).strip()
        if not username or not password:
            return False
            
        try:
            async with session.get("https://abasmanesh.com/fa/login/", timeout=15) as resp:
                if resp.status != 200:
                    return False
                html = await resp.text()
                if "خروج" in html or "پروفایل" in html:
                    return True
                match = re.search(r'name="_token"\s+value="([^"]+)"', html)
                csrf = match.group(1) if match else ""
            
            headers = dict(session.headers)
            headers.update({
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": "https://abasmanesh.com/fa/login/",
                "Origin": "https://abasmanesh.com"
            })
            
            payload = {
                "_token": csrf,
                "login_method": "email",
                "identifier": username.strip(),
                "password": password.strip(),
                "remember_me": "1"
            }
            
            async with session.post("https://abasmanesh.com/fa/login/", data=payload, headers=headers, timeout=15, allow_redirects=False) as post_resp:
                if post_resp.status in [301, 302]:
                    loc = post_resp.headers.get("Location", "")
                    if "login" not in loc.lower():
                        await cls.save_session()
                        return True
                    return False
                post_html = await post_resp.text()
                if "خروج" in post_html or "پروفایل" in post_html:
                    await cls.save_session()
                    return True
                return False
        except Exception as e:
            return False

    @classmethod
    async def invalidate_session(cls):
        try:
            loop = asyncio.get_running_loop()
        except:
            loop = None
            
        sess = cls._sessions.get(loop) if loop else None
        if sess and not sess.closed:
            await sess.close()
            
        if loop and loop in cls._sessions:
            del cls._sessions[loop]
            
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
                await cls.invalidate_session()
                logged_in = await cls.login_if_needed()
                if logged_in:
                    await asyncio.sleep(random.uniform(1.5, 3.5))
                    session = await cls.get_session()
                    async with session.get(url, timeout=timeout) as resp2:
                        return resp2.status, await resp2.text()
                else:
                    return 401, html
            
            return status, html

    @classmethod
    async def test_connection(cls) -> dict:
        try:
            await cls.invalidate_session()
            await cls.login_if_needed()
            session = await cls.get_session()
            async with session.get("https://abasmanesh.com/fa/profile/", timeout=25, allow_redirects=False) as resp:
                status = resp.status
                html = await resp.text()
                
                if status == 200:
                    username = "کاربر تایید شده"
                    m = re.search(r'سلام[\s\n]*<strong[^>]*>([^<]+)</strong>', html)
                    if m: username = m.group(1).strip()
                    msg = f"نشست فعال با هویت معتبر ({username}) تأیید شد."
                    return {"success": True, "status_code": status, "message": msg, "authenticated": True}
                elif status in (301, 302):
                    msg = f"سشن نامعتبر است؛ لطفاً کوکی جدید مرورگر را وارد کنید (کد {status})."
                    return {"success": False, "status_code": status, "message": msg, "authenticated": False}
                else:
                    msg = f"خطای ناشناخته از سرور مرجع (کد {status})"
                    return {"success": False, "status_code": status, "message": msg, "authenticated": False}
        except Exception as e:
            return {"success": False, "status_code": 500, "message": f"خطای ارتباطی: {str(e) or repr(e)}", "authenticated": False}



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
                            if v_src and (".mp3" in v_src or ".m4a" in v_src) and not audio_dl:
                                audio_dl = re.sub(r"^rhttp", "http", v_src)

                        # جستجو در اسکریپت‌ها (JavaScript player configs)
                        if not video_dl or not audio_dl:
                            import re
                            for script in soup.find_all("script"):
                                if script.string:
                                    # Find .mp4 and .mp3 URLs in script strings
                                    mp4_matches = re.findall(r'(https?://[^"\' ]+\.mp4)', script.string)
                                    mp3_matches = re.findall(r'(https?://[^"\' ]+\.(?:mp3|m4a))', script.string)
                                    if mp4_matches and not video_dl:
                                        video_dl = mp4_matches[0].replace("\\/", "/")
                                    if mp3_matches and not audio_dl:
                                        audio_dl = mp3_matches[0].replace("\\/", "/")

                        # جستجو در لینک‌های دانلود مستقیم
                        for a in soup.find_all("a", href=True):
                            h = a["href"].strip()
                            if "download.php?url=" in h or (".mp3" in h and "http" in h) or (".m4a" in h and "http" in h) or (".mp4" in h and "http" in h):
                                clean_h = re.sub(r"^rhttp", "http", h).replace("cdneu.abasmanesh.com", "cdnir.abasmanesh.com")
                                if (".mp3" in clean_h or ".m4a" in clean_h) and not audio_dl:
                                    audio_dl = clean_h
                                elif ".mp4" in clean_h and not video_dl:
                                    video_dl = clean_h
                                    
                        # Persist directly to abasmanesh_feed if it's the specific file or generally
                        from core.database import execute_query, fetch_all
                        try:
                            # Use sync logic or fire-and-forget for db if in async context? execute_query is async
                            await execute_query(
                                "UPDATE abasmanesh_feed SET audio_url = ?, video_url = ?, thumbnail_url = ? WHERE source_url = ?", 
                                (audio_dl, video_dl, final_cover, clean_url)
                            )
                            # Update crawler_cache.json
                            import json
                            from pathlib import Path
                            from core.config import config
                            cache_file = getattr(config, "DATA_DIR", Path("data")) / "crawler_cache.json"
                            if getattr(config, "FEED_CACHE_FILE", None):
                                cache_file = getattr(config, "FEED_CACHE_FILE")
                            if cache_file.exists():
                                data = json.loads(cache_file.read_text(encoding="utf-8"))
                                cached_items = data.get("items", [])
                                for ci in cached_items:
                                    if ci.get("url", "").strip("/") == clean_url.strip("/"):
                                        ci["audio_url"] = audio_dl
                                        ci["video_url"] = video_dl
                                        ci["cover_url"] = final_cover
                                cache_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                                
                            try:
                                from services.feed_scraper import _CACHE
                                _CACHE.clear()
                            except:
                                pass
                        except Exception as ex:
                            import logging
                            logging.getLogger().debug(f"SQLite update error in fetch_article_details: {ex}")

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
        res = await cls.fetch_article_details(url)
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
    async def sync_feed(cls) -> dict:
        """
        به‌روزرسانی بلادرنگ فید (پایش هوشمند صفحه اول) و پاکسازی تمامی کش‌ها
        """
        try:
            from services.feed_scraper import _CACHE, _extract_articles_from_html, _fetch_single_article, save_feed_disk_cache
            from core.database import execute_query
            
            import aiohttp, asyncio
            from core.logger import get_logger
            logger = get_logger("feed_crawler")
            
            target_urls = [
                "https://abasmanesh.com/fa/articles/",
                "https://abasmanesh.com/fa/category/free-download/practical-monotheism/",
                "https://abasmanesh.com/fa/category/free-download/recognition-of-essential-from-nonessential/"
            ]
            
            articles_to_fetch = []
            seen_urls = set()
            
            for url in target_urls:
                status, html = await FeedAuthManager.fetch_html_with_auth(url, timeout=20)
                if status == 200:
                    arts, _ = _extract_articles_from_html(html, limit=100)
                    for a_url, a_title, a_cover, a_tag in arts:
                        if a_url not in seen_urls:
                            seen_urls.add(a_url)
                            articles_to_fetch.append((a_url, a_title, a_cover, a_tag))
            
            if not articles_to_fetch:
                return {"ok": False, "error": "هیچ مقاله‌ای یافت نشد"}
                
            session = await FeedAuthManager.get_session()
            tasks = [
                _fetch_single_article(session, a_url, a_title, card_cover=a_cover, card_tag=a_tag)
                for a_url, a_title, a_cover, a_tag in articles_to_fetch[:60]  # Increased limit for full sync
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            final_items = []
            for idx, r in enumerate(results):
                if isinstance(r, dict) and r.get("title"):
                    r["file_number"] = f"فایل شماره {idx + 1}"
                    final_items.append(r)
                    
            if not final_items:
                return {"ok": False, "error": "Could not parse media for any article"}
                
            # 1. Update SQLite
            import sqlite3
            await execute_query('''
                CREATE TABLE IF NOT EXISTS abasmanesh_feed (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_url TEXT UNIQUE,
                    title TEXT,
                    thumbnail_url TEXT,
                    audio_url TEXT,
                    video_url TEXT,
                    tags TEXT,
                    is_free BOOLEAN DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            for item in final_items:
                await execute_query(
                    '''
                    INSERT INTO abasmanesh_feed 
                    (source_url, title, thumbnail_url, audio_url, video_url, tags, is_free)
                    VALUES (?, ?, ?, ?, ?, ?, 1)
                    ON CONFLICT(source_url) DO UPDATE SET
                    title=excluded.title,
                    thumbnail_url=excluded.thumbnail_url,
                    audio_url=excluded.audio_url,
                    video_url=excluded.video_url,
                    tags=excluded.tags
                    ''',
                    (
                        item["url"],
                        item["title"],
                        item.get("cover_url", ""),
                        item.get("audio_url", ""),
                        item.get("video_url", ""),
                        item.get("category", "")
                    )
                )
                
            # 2. Update Disk Cache
            save_feed_disk_cache(final_items)
            
            # 3. Clear RAM Cache
            _CACHE.clear()
            _CACHE["items"] = final_items
            _CACHE["total_pages"] = total_pages
            
            import time
            _CACHE["last_fetched"] = time.time()
            
            # 4. Clear crawler_cache.json
            from core.config import config
            try:
                import json
                cc_path = config.DATA_DIR / "crawler_cache.json"
                if cc_path.exists():
                    cc_path.unlink()
            except: pass
            
            return {"ok": True, "count": len(final_items)}
        except Exception as e:
            return {"ok": False, "error": str(e)}
            
        except Exception as e:
            import logging
            logging.getLogger().error(f"sync_thumbnails error: {e}")
            return {"ok": False, "error": str(e)}

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
                    cls.fetch_article_details(u, t, c, tg)
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