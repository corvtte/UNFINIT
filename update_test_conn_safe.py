import re

c = open('services/feed_crawler.py', encoding='utf-8').read()

idx1 = c.find('    @classmethod\n    async def test_connection')
idx2 = c.find('class FeedCrawler:')
old_block = c[idx1:idx2]

new_block = '''    @classmethod
    async def test_connection(cls, force_login=False) -> dict:
        try:
            if force_login:
                await cls.invalidate_session()
                await cls.login_if_needed()
            session = await cls.get_session()
            async with session.get("https://abasmanesh.com/fa/profile/", timeout=25, allow_redirects=False) as resp:
                status = resp.status
                html = await resp.text()
                
                loc = str(resp.headers.get("Location", ""))
                is_valid = False
                if status == 200:
                    is_valid = True
                elif status in (301, 302) and "login" not in loc.lower():
                    is_valid = True
                    
                if is_valid:
                    username = "کاربر تایید شده"
                    m = re.search(r'سلام[\s\n]*<strong[^>]*>([^<]+)</strong>', html)
                    if m: username = m.group(1).strip()
                    
                    import yarl
                    cookies = session.cookie_jar.filter_cookies(yarl.URL("https://abasmanesh.com"))
                    cookie_str = "; ".join([f"{k}={v.value}" for k, v in cookies.items()])
                    
                    from core.database import set_system_setting
                    await set_system_setting("FEED_AUTH_COOKIE", cookie_str)
                    
                    msg = f"نشست فعال با هویت معتبر ({username}) تأیید شد."
                    return {"success": True, "status_code": status, "message": msg, "authenticated": True, "cookie": cookie_str}
                elif status in (301, 302):
                    msg = f"سشن نامعتبر است؛ لطفاً کوکی جدید مرورگر را وارد کنید (کد {status})."
                    return {"success": False, "status_code": status, "message": msg, "authenticated": False}
                else:
                    msg = f"خطای ناشناخته از سرور مرجع (کد {status})"
                    return {"success": False, "status_code": status, "message": msg, "authenticated": False}
        except Exception as e:
            return {"success": False, "status_code": 500, "message": f"خطای ارتباطی: {str(e) or repr(e)}", "authenticated": False}


'''

open('services/feed_crawler.py', 'w', encoding='utf-8').write(c.replace(old_block, new_block))
print('Updated test_connection safely!')
