import re

filepath = 'services/web_panel.py'
text = open(filepath, encoding='utf-8').read()

old_logic = '''    from services.feed_crawler import FeedAuthManager
    await FeedAuthManager.invalidate_session()
    
    res = await FeedAuthManager.test_connection()
    if res.get("success"):
        return {"success": True, "message": "نشست با موفقیت ذخیره و فعال شد!"}
    else:
        return {"success": False, "message": res.get("message", "خطا در تأیید نشست.")}'''

new_logic = '''    from services.feed_crawler import FeedAuthManager
    await FeedAuthManager.invalidate_session()
    
    # Just save and return success. 
    # Don't block the save on the network connection test.
    return {"success": True, "message": "اطلاعات نشست با موفقیت ذخیره شد. برای اطمینان می‌توانید دکمه تست اتصال را بزنید."}'''

if old_logic in text:
    text = text.replace(old_logic, new_logic)
    open(filepath, 'w', encoding='utf-8').write(text)
    print('Fixed handle_crawler_save_auth_async')
else:
    print('Not found')
