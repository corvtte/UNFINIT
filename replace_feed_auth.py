import re

f = 'services/feed_crawler.py'
text = open(f, encoding='utf-8').read()

new_class = """class FeedAuthManager:
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
        auth_cookie = (os.getenv("AUTH_SESSION_COOKIES") or await get_system_setting("AUTH_SESSION_COOKIES", "") or os.getenv("FEED_AUTH_COOKIE") or await get_system_setting("FEED_AUTH_COOKIE", "")).strip()
        if auth_cookie:
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
                
            try:
                async with session.get("https://abasmanesh.com/fa/profile/", allow_redirects=False, timeout=10) as profile_resp:
                    if profile_resp.status == 200:
                        await cls.save_session()
                        return True
            except Exception as e:
                pass

        username = os.getenv("FEED_AUTH_EMAIL") or await get_system_setting("FEED_AUTH_EMAIL") or os.getenv("ABASMANESH_EMAIL") or await get_system_setting("ABASMANESH_EMAIL")
        password = os.getenv("FEED_AUTH_PASSWORD") or await get_system_setting("FEED_AUTH_PASSWORD") or os.getenv("ABASMANESH_PASSWORD") or await get_system_setting("ABASMANESH_PASSWORD")
        if not username or not password:
            return False
            
        try:
            async with session.get("https://abasmanesh.com/fa/login/", timeout=15) as resp:
                if resp.status != 200:
                    return False
                html = await resp.text()
                if "خروج" in html or "پروفایل" in html:
                    return True
                match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
                csrf = match.group(1) if match else ""
            
            headers = dict(session.headers)
            headers.update({
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": "https://abasmanesh.com/fa/login/",
                "Origin": "https://abasmanesh.com"
            })
            
            payload = {
                "csrf_token": csrf,
                "email": username.strip(),
                "password": password.strip(),
                "remember": "on"
            }
            
            async with session.post("https://abasmanesh.com/fa/login/", data=payload, headers=headers, timeout=15) as post_resp:
                post_html = await post_resp.text()
                if post_resp.status in [200, 302] and ("خروج" in post_html or "پروفایل" in post_html or post_resp.status == 302):
                    await cls.save_session()
                    return True
                else:
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
                    m = re.search(r'سلام[\s\\n]*<strong[^>]*>([^<]+)</strong>', html)
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

"""

start_idx = text.find("class FeedAuthManager:")
end_idx = text.find("class FeedCrawler:", start_idx)

if start_idx != -1 and end_idx != -1:
    new_text = text[:start_idx] + new_class + "\n\n" + text[end_idx:]
    open('services/feed_crawler.py', 'w', encoding='utf-8').write(new_text)
    print("Replaced FeedAuthManager completely")
else:
    print("Could not find class boundaries")
