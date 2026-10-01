import re

def update_feed_crawler():
    p = 'services/feed_crawler.py'
    text = open(p, encoding='utf-8').read()

    new_login_method = r"""    @classmethod
    async def login_if_needed(cls) -> bool:
        session = await cls.get_session()
        
        # Priority 1: Direct Session Cookie Injection
        auth_cookie = (os.getenv("FEED_AUTH_COOKIE") or await get_system_setting("FEED_AUTH_COOKIE", "")).strip()
        if auth_cookie:
            # Smart Laravel Cookie Sanitizer
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
                session.cookie_jar.update_cookies(extracted_cookies)
                
            # Verify cookie validity against a protected URL
            try:
                # Probe a known gated URL
                async with session.get("https://abasmanesh.com/fa/living-in-paradise/", timeout=15) as resp:
                    html = await resp.text()
                    # Check if ungated or user profile is present
                    if "برای مشاهده این محتوا باید وارد شوید" not in html or "خروج" in html or "پروفایل" in html:
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
                    return True"""

    pattern = r'    @classmethod\n    async def login_if_needed\(cls\) -> bool:.*?if "خروج" in html or "پروفایل" in html:\n                    logger\.info\("\[FeedAuthManager\] Already logged in via saved cookies\."\)\n                    return True'
    text = re.sub(pattern, new_login_method, text, flags=re.DOTALL)
    open(p, 'w', encoding='utf-8').write(text)

update_feed_crawler()
