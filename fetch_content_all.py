import asyncio
from services.feed_crawler import FeedAuthManager
from bs4 import BeautifulSoup

async def main():
    s, h = await FeedAuthManager.fetch_html_with_auth('https://abasmanesh.com/fa/take-it-easy-so-that-become-easy/')
    if s == 200:
        soup = BeautifulSoup(h, 'html.parser')
        
        for div in soup.find_all('div'):
            c = div.get('class', [])
            txt = div.get_text(strip=True)
            if len(txt) > 200 and any(x in str(c) for x in ['content', 'text', 'desc', 'box', 'article']):
                print(f"CLASS: {c} | TEXT: {txt[:100]}...")
asyncio.run(main())
