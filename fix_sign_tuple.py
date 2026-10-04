import sys
c = open('core/sign_service.py', encoding='utf-8').read()

old_code = '''        items = []
        try:
            items = await get_latest_free_downloads(page=target_page, limit=25, base_url="https://abasmanesh.com/fa/articles/")
        except Exception as e:
            logger.warning(f"[sign_service] Failed to fetch page {target_page}: {e}")

        if not items:
            items = FALLBACK_ITEMS

        # ۳. انتخاب آیتم از میان لیست صفحه
        item_idx = (hash_int // 39) % len(items)
        selected = dict(items[item_idx])'''

new_code = '''        items = []
        try:
            res = await get_latest_free_downloads(page=target_page, limit=25, base_url="https://abasmanesh.com/fa/articles/")
            items = res[0] if isinstance(res, tuple) else res
        except Exception as e:
            logger.warning(f"[sign_service] Failed to fetch page {target_page}: {e}")

        if not items:
            items = FALLBACK_ITEMS

        # ۳. انتخاب آیتم از میان لیست صفحه
        item_idx = (hash_int // 39) % len(items)
        selected = dict(items[item_idx])'''

c = c.replace(old_code, new_code)
open('core/sign_service.py', 'w', encoding='utf-8').write(c)
print("Fixed items tuple bug in sign_service.py")
