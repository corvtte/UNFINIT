import sys
c = open('services/feed_scraper.py', encoding='utf-8').read()

old_get_cat = '''    target_url = build_page_url(cat["url"], page_number=page)

    timeout = aiohttp.ClientTimeout(total=20)
    articles_to_fetch = []
    try:
        async with aiohttp.ClientSession(headers=BROWSER_HEADERS, timeout=timeout) as session:
            async with session.get(target_url) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    articles_to_fetch, total_pages = _extract_articles_from_html(html, limit=limit)

            episodes = []
            if articles_to_fetch:
                sem = asyncio.Semaphore(5)
                async def fetch_with_sem_cat(u, t, c, tg):
                    async with sem:
                        return await _fetch_single_article(session, u, t, card_cover=c, card_tag=tg or cat.get("title", ""))'''

new_get_cat = '''    target_url = build_page_url(cat["url"], page_number=page)

    articles_to_fetch = []
    try:
        from services.feed_crawler import FeedAuthManager
        status, html = await FeedAuthManager.fetch_html_with_auth(target_url, timeout=20)
        
        if status == 200:
            articles_to_fetch, total_pages = _extract_articles_from_html(html, limit=limit)
        else:
            total_pages = 1

        episodes = []
        if articles_to_fetch:
            session = await FeedAuthManager.get_session()
            sem = asyncio.Semaphore(5)
            async def fetch_with_sem_cat(u, t, c, tg):
                async with sem:
                    return await _fetch_single_article(session, u, t, card_cover=c, card_tag=tg or cat.get("title", ""))'''

c = c.replace(old_get_cat, new_get_cat)
open('services/feed_scraper.py', 'w', encoding='utf-8').write(c)
print('Updated get_category_episodes to use FeedAuthManager')
