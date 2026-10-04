import sys
lines = open('services/feed_crawler.py', encoding='utf-8').read()

old_test_conn = """                if status == 200:
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
                    return {"success": False, "status_code": status, "message": msg, "authenticated": False}"""

new_test_conn = """                loc = str(resp.headers.get("Location", ""))
                is_valid = False
                if status == 200:
                    is_valid = True
                elif status in (301, 302) and "login" not in loc.lower():
                    is_valid = True
                    
                if is_valid:
                    username = "کاربر تایید شده"
                    m = re.search(r'سلام[\s\n]*<strong[^>]*>([^<]+)</strong>', html)
                    if m: username = m.group(1).strip()
                    msg = f"نشست فعال با هویت معتبر ({username}) تأیید شد."
                    return {"success": True, "status_code": status, "message": msg, "authenticated": True}
                elif status in (301, 302):
                    msg = f"نام کاربری یا رمز عبور اشتباه است، یا کوکی منقضی شده (کد {status})."
                    return {"success": False, "status_code": status, "message": msg, "authenticated": False}
                else:
                    msg = f"خطای ناشناخته از سرور مرجع (کد {status})"
                    return {"success": False, "status_code": status, "message": msg, "authenticated": False}"""

if old_test_conn in lines:
    lines = lines.replace(old_test_conn, new_test_conn)
    open('services/feed_crawler.py', 'w', encoding='utf-8').write(lines)
    print('test_connection logic updated!')
else:
    print('Pattern not found!')
