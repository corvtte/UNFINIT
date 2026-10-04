import asyncio, sys, re, aiohttp

async def fetch_home():
    headers = {'User-Agent': 'Mozilla/5.0'}
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get('https://abasmanesh.com/fa/') as resp:
            html = await resp.text()
            links = re.findall(r'(https?://[^\s\"\']+\.(?:mp3|mp4|zip))', html)
            for l in set(links):
                print("FOUND MEDIA:", l)
            if 'download.php' in html:
                print("download.php found!")

asyncio.run(fetch_home())
