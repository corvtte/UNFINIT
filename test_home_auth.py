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
        
        async with session.get('https://abasmanesh.com/fa/', allow_redirects=False) as r:
            html = await r.text()
            if 'خروج' in html: print("Found خروج")
            if 'پروفایل' in html: print("Found پروفایل")
            if 'sajjadthvh' in html: print("Found username")
            
            # Let's save a snippet to see what user info is available
            import re
            user_json = re.search(r'window\.user\s*=\s*(\{.*?\});', html, re.DOTALL)
            if user_json:
                print("Found window.user:", user_json.group(1)[:100])
            else:
                print("No window.user found")

asyncio.run(test_home())
