import os
p = 'services/feed_crawler.py'
lines = open(p, encoding='utf-8').readlines()
start = [i for i, l in enumerate(lines) if 'class FeedAuthManager' in l][0]
end = [i for i, l in enumerate(lines) if 'class FeedCrawler:' in l][0]

new_class = '''class FeedAuthManager:
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
            session.cookie_jar.update_cookies({"session_cookie": auth_cookie}) # Simplified injection, actually aiohttp requires Cookie dict format but we can just set headers.
            # Wait, best to just put it in headers, but aiohttp cookie_jar needs SimpleCookie.
            # Let's just set the Cookie header manually on the session if provided, or parse it.
            from http.cookies import SimpleCookie
            cookie = SimpleCookie()
            cookie.load(auth_cookie)
            for key, morsel in cookie.items():
                session.cookie_jar.update_cookies({key: morsel.value})
                
            # Verify cookie validity
            try:
                async with session.get("https://abasmanesh.com/fa/login/", timeout=15) as resp:
                    html = await resp.text()
                    # Check if ungated or user profile is present
                    if "خروج" in html or "پروفایل" in html or "برای مشاهده این محتوا" not in html:
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
            logged_in = await cls.login_if_needed()
            if logged_in:
                return {"success": True, "message": "اتصال و نشست با موفقیت تأیید شد.", "authenticated": True}
            else:
                return {"success": False, "message": "خطا در احراز هویت: اطلاعات ورود نامعتبر است یا مشکلی پیش آمده. لاگ سرور را بررسی کنید.", "authenticated": False}
        except Exception as e:
            return {"success": False, "message": f"خطای ارتباطی: {str(e)}", "authenticated": False}

'''
open(p, 'w', encoding='utf-8').write(''.join(lines[:start]) + new_class + ''.join(lines[end:]))
