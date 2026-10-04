import re

f = 'services/feed_scraper.py'
text = open(f, encoding='utf-8').read()

old_code_cat = """                tasks = [
                    _fetch_single_article(session, url, title, card_cover=cover, card_tag=tag or cat.get("title", ""))
                    for url, title, cover, tag in articles_to_fetch[:limit]
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)"""

new_code_cat = """                sem = asyncio.Semaphore(5)
                async def fetch_with_sem_cat(u, t, c, tg):
                    async with sem:
                        return await _fetch_single_article(session, u, t, card_cover=c, card_tag=tg or cat.get("title", ""))

                tasks = [
                    fetch_with_sem_cat(url, title, cover, tag)
                    for url, title, cover, tag in articles_to_fetch[:limit]
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)"""

if old_code_cat in text:
    text = text.replace(old_code_cat, new_code_cat)
    open(f, 'w', encoding='utf-8').write(text)
    print("Fixed get_category_episodes")
else:
    print("Cat Code not found")
