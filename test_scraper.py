import asyncio
import aiohttp
from services.feed_scraper import _fetch_single_article

async def test():
    url = 'https://abasmanesh.com/fa/life-in-paradise-179/'
    async with aiohttp.ClientSession() as session:
        data = await _fetch_single_article(session, url, 'test')
        print("Audio URL:", data.get('audio_url'))
        print("Video URL:", data.get('video_url'))
        print("Lesson text:", data.get('lesson_text'))

if __name__ == "__main__":
    asyncio.run(test())
