import asyncio, aiohttp

async def test_home():
    email = 'sajjadthvh@gmail.com'
    password = 'sajjad2//'
    headers = {'User-Agent': 'Mozilla/5.0'}
    async with aiohttp.ClientSession(headers=headers, cookie_jar=aiohttp.CookieJar()) as session:
        async with session.get('https://abasmanesh.com/fa/login/') as r:
            h = await r.text()
            import re
            m = re.search(r'name="_token"\s+value="([^"]+)"', h)
            csrf = m.group(1) if m else ''
        data = {'_token': csrf, 'login_method': 'email', 'identifier': email, 'password': password, 'remember_me': '1'}
        await session.post('https://abasmanesh.com/fa/login/', data=data, allow_redirects=False)
        
        async with session.get('https://abasmanesh.com/fa/', allow_redirects=True) as r:
            html = await r.text()
            with open('home_dump.html', 'w', encoding='utf-8') as f:
                f.write(html)
            print("Status:", r.status)

asyncio.run(test_home())
