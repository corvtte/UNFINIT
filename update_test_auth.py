import re
c = open('services/web_panel.py', encoding='utf-8').read()

old_block = '''async def handle_crawler_test_auth_async(payload: dict) -> dict:
    from services.feed_crawler import FeedAuthManager
    return await FeedAuthManager.test_connection()'''

new_block = '''async def handle_crawler_test_auth_async(payload: dict) -> dict:
    from services.feed_crawler import FeedAuthManager
    force_login = payload.get("force_login", False)
    return await FeedAuthManager.test_connection(force_login=force_login)'''

open('services/web_panel.py', 'w', encoding='utf-8').write(c.replace(old_block, new_block))
print('Updated web_panel.py successfully!')
