import asyncio, aiohttp

async def test_profile():
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
        
        async with session.get('https://abasmanesh.com/fa/profile/', allow_redirects=False) as r:
            print('Profile status:', r.status)
            print('Profile Location:', r.headers.get('Location'))
            if r.status in (301, 302):
                loc = r.headers.get('Location')
                if loc:
                    async with session.get(loc, allow_redirects=False) as r2:
                        print('Redirect status:', r2.status)
                        print('Redirect Location:', r2.headers.get('Location'))
                        html2 = await r2.text()
                        if 'کاربر' in html2: print('Found "کاربر"')

asyncio.run(test_profile())
