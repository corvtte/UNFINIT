import re

p_file = 'services/web_panel.py'
text = open(p_file, encoding='utf-8').read()

new_handlers = """
async def handle_crawler_save_auth_async(payload: dict) -> dict:
    from pathlib import Path
    import json
    
    email = payload.get("email", "").strip()
    password = payload.get("password", "").strip()
    cookie = payload.get("cookie", "").strip()
    
    settings_file = getattr(config, "SETTINGS_JSON_FILE", None) or (Path(getattr(config, "DATA_DIR", "data")) / "settings.json")
    settings = {}
    if settings_file.exists():
        try:
            with open(settings_file, "r", encoding="utf-8") as f:
                settings = json.load(f)
        except:
            pass
            
    settings["FEED_AUTH_EMAIL"] = email
    settings["FEED_AUTH_PASSWORD"] = password
    settings["FEED_AUTH_COOKIE"] = cookie
    
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    with open(settings_file, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)
        
    from services.feed_crawler import FeedAuthManager
    await FeedAuthManager.invalidate_session()
    
    res = await FeedAuthManager.test_connection()
    if res.get("success"):
        return {"success": True, "message": "نشست با موفقیت ذخیره و فعال شد!"}
    else:
        return {"success": False, "message": res.get("message", "خطا در تأیید نشست.")}

def handle_crawler_save_auth(payload: dict) -> dict:
    return _run_sync(handle_crawler_save_auth_async(payload))
"""

text = text.replace('def handle_crawler_test_auth(payload: dict) -> dict:\n    return _run_sync(handle_crawler_test_auth_async(payload))', 'def handle_crawler_test_auth(payload: dict) -> dict:\n    return _run_sync(handle_crawler_test_auth_async(payload))\n' + new_handlers)

open(p_file, 'w', encoding='utf-8').write(text)
