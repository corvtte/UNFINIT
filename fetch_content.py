import asyncio
from services.feed_crawler import FeedAuthManager
from bs4 import BeautifulSoup

async def main():
    s, h = await FeedAuthManager.fetch_html_with_auth('https://abasmanesh.com/fa/take-it-easy-so-that-become-easy/')
    print('STATUS', s)
    if s == 200:
        soup = BeautifulSoup(h, 'html.parser')
        main_tag = soup.find('main')
        if not main_tag:
            print('NO MAIN')
            return
        
        for div in main_tag.find_all('div'):
            c = div.get('class', [])
            if any('box' in x for x in c) or any('content' in x for x in c) or any('text' in x for x in c):
                txt = div.get_text(strip=True)
                if len(txt) > 50:
                    print(f"CLASS: {c} | TEXT: {txt[:100]}...")
asyncio.run(main())
