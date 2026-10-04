import sys

filepath = 'services/feed_crawler.py'
text = open(filepath, encoding='utf-8').read()

old_auth_cookie = 'auth_cookie = (os.getenv("AUTH_SESSION_COOKIES") or await get_system_setting("AUTH_SESSION_COOKIES", "") or os.getenv("FEED_AUTH_COOKIE") or await get_system_setting("FEED_AUTH_COOKIE", "")).strip()'
new_auth_cookie = 'auth_cookie = (await get_system_setting("FEED_AUTH_COOKIE", "")).strip()'

if old_auth_cookie in text:
    text = text.replace(old_auth_cookie, new_auth_cookie)
    
old_creds = 'username = os.getenv("FEED_AUTH_EMAIL") or await get_system_setting("FEED_AUTH_EMAIL") or os.getenv("ABASMANESH_EMAIL") or await get_system_setting("ABASMANESH_EMAIL")\n        password = os.getenv("FEED_AUTH_PASSWORD") or await get_system_setting("FEED_AUTH_PASSWORD") or os.getenv("ABASMANESH_PASSWORD") or await get_system_setting("ABASMANESH_PASSWORD")'
new_creds = 'username = (await get_system_setting("FEED_AUTH_EMAIL", "")).strip()\n        password = (await get_system_setting("FEED_AUTH_PASSWORD", "")).strip()'

if old_creds in text:
    text = text.replace(old_creds, new_creds)

old_post = '''            async with session.post("https://abasmanesh.com/fa/login/", data=payload, headers=headers, timeout=15) as post_resp:
                post_html = await post_resp.text()
                if post_resp.status in [200, 302] and ("خروج" in post_html or "پروفایل" in post_html or post_resp.status == 302):
                    await cls.save_session()
                    return True
                else:
                    return False'''
new_post = '''            async with session.post("https://abasmanesh.com/fa/login/", data=payload, headers=headers, timeout=15, allow_redirects=False) as post_resp:
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
                return False'''

if old_post in text:
    text = text.replace(old_post, new_post)
    
open(filepath, 'w', encoding='utf-8').write(text)
print("Updated feed_crawler logic!")
