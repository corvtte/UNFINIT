import asyncio, sys, re
sys.path.append('c:/Users/Sajjad/Downloads/Compressed/unfinit_store_engine_v24.0')
from services.feed_crawler import FeedAuthManager

async def fetch_article():
    res = await FeedAuthManager.fetch_html_with_auth('https://abasmanesh.com/fa/take-it-easy-so-that-become-easy/')
    status, html = res
    print("STATUS:", status)
    
    links = re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>', html)
    print('LINKS:')
    for l in links:
        if 'mp4' in l.lower() or 'mp3' in l.lower() or 'download' in l.lower():
            print("FOUND LINK:", l)
            
    print('ALL MP3/MP4 LINES:')
    for line in html.split('\n'):
        if 'mp3' in line.lower() or 'mp4' in line.lower() or 'download' in line.lower():
            print(line.strip())

asyncio.run(fetch_article())
