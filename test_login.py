import asyncio, aiohttp, sys, re

async def check_login(username, password):
    headers = {'User-Agent': 'Mozilla/5.0'}
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get('https://abasmanesh.com/fa/login/', allow_redirects=True) as resp:
            text = await resp.text()
            match = re.search(r'name="_token"\s+value="([^"]+)"', text)
            csrf = match.group(1) if match else ''
        payload = {'_token': csrf, 'login_method': 'email', 'identifier': username, 'password': password, 'remember_me': '1'}
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
        async with session.post('https://abasmanesh.com/fa/login/', data=payload, headers=headers, allow_redirects=False) as resp2:
            print(resp2.status, resp2.headers.get('Location'))
            if resp2.status == 302:
                # check where it goes
                pass

asyncio.run(check_login('test@test.com', 'wrongpass123'))
