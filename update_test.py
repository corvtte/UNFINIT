import re

p = 'services/feed_crawler.py'
text = open(p, encoding='utf-8').read()

new_test = r"""    @classmethod
    async def test_connection(cls) -> dict:
        \"\"\"Lightweight authenticated probe to check connection health and auth status\"\"\"
        try:
            await cls.invalidate_session()
            await cls.login_if_needed()
            session = await cls.get_session()
            async with session.get("https://abasmanesh.com/fa/living-in-paradise/", timeout=15) as resp:
                html = await resp.text()
                status = resp.status
                redirect_url = str(resp.url)
                body_preview = html[:250].strip()
                
                is_ok = ("برای مشاهده این محتوا باید وارد شوید" not in html) and ("خروج" in html or "پروفایل" in html)
                
                if is_ok:
                    msg = f"اتصال و نشست با موفقیت تأیید شد.\nآدرس نهایی: {redirect_url}\nوضعیت: {status}"
                    logger.info(f"[FeedAuthManager] Test Connection Success - Status: {status}")
                    return {"success": True, "status_code": status, "message": msg, "authenticated": True}
                else:
                    msg = f"پاسخ خام (کد {status}):\n{body_preview}..."
                    logger.error(f"[FeedAuthManager] Test Connection Failed - Status: {status}, Body Preview: {body_preview}")
                    return {"success": False, "status_code": status, "message": msg, "authenticated": False}
        except Exception as e:
            logger.error(f"[FeedAuthManager] Test Connection Network Error: {e}")
            return {"success": False, "status_code": 500, "message": f"خطای ارتباطی: {str(e)}", "authenticated": False}"""

text = re.sub(r'    @classmethod\n    async def test_connection\(cls\) -> dict:.*?        except Exception as e:\n            return \{"success": False, "message": f"خطای ارتباطی: \{str\(e\)\}", "authenticated": False\}', new_test, text, flags=re.DOTALL)

open(p, 'w', encoding='utf-8').write(text)
