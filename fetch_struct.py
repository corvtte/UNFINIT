import asyncio
from services.feed_crawler import FeedAuthManager
from bs4 import BeautifulSoup

async def main():
    s, h = await FeedAuthManager.fetch_html_with_auth('https://abasmanesh.com/fa/living-in-paradise-56/')
    print('STATUS', s)
    if s == 200:
        soup = BeautifulSoup(h, 'html.parser')
        main = soup.find('main')
        if not main:
            print("NO MAIN")
            return
        
        for div in main.find_all('div', limit=20):
            c = div.get('class', [])
            txt = div.get_text(strip=True)[:100]
            if txt and ('box' in c or 'content' in c or any('desc' in x for x in c) or any('text' in x for x in c)):
                print(f"CLASS: {c} | TEXT: {txt}")
        
asyncio.run(main())
