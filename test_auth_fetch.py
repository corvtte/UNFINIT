import asyncio
import os
import sys

sys.path.append(os.getcwd())

async def test_fetch():
    from services.feed_crawler import FeedAuthManager
    from core.database import set_system_setting
    import re
    
    await set_system_setting("FEED_AUTH_EMAIL", "sajjadthvh@gmail.com")
    await set_system_setting("FEED_AUTH_PASSWORD", "sajjad2//")
    await set_system_setting("FEED_AUTH_COOKIE", "")
    
    print("Testing connection...")
    res = await FeedAuthManager.test_connection()
    print("Test connection:", res)
    
    url = "https://abasmanesh.com/fa/take-it-easy-so-that-become-easy/"
    print("Fetching:", url)
    status, html = await FeedAuthManager.fetch_html_with_auth(url, timeout=15)
    print("Status:", status)
    
    with open("downloaded_page.html", "w", encoding="utf-8") as f:
        f.write(html)
        
    links = re.findall(r'(https?://[^\s\"\'\)]+(?:mp3|mp4|zip|download|dl)[^\s\"\'\)]*)', html)
    print("Links found:")
    for l in set(links):
        print(l)
        
if __name__ == "__main__":
    asyncio.run(test_fetch())
