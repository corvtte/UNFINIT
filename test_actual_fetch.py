import asyncio, aiohttp

async def test_login():
    email = 'sajjadthvh@gmail.com'
    password = 'sajjad2//'
    
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Referer': 'https://abasmanesh.com/fa/login/',
        'Origin': 'https://abasmanesh.com'
    }
    
    async with aiohttp.ClientSession(headers=headers, cookie_jar=aiohttp.CookieJar()) as session:
        async with session.get('https://abasmanesh.com/fa/login/', timeout=10) as resp:
            html = await resp.text()
            import re
            m = re.search(r'name="_token"\s+value="([^"]+)"', html)
            csrf = m.group(1)
            
        data = {
            '_token': csrf,
            'login_method': 'email',
            'identifier': email,
            'password': password,
            'remember_me': '1'
        }
        
        await session.post('https://abasmanesh.com/fa/login/', data=data, allow_redirects=False, timeout=10)
        
        # Test article fetch!
        print("Fetching article...")
        async with session.get('https://abasmanesh.com/fa/take-it-easy-so-that-become-easy/', timeout=10) as art_resp:
            print("Article status:", art_resp.status)
            art_html = await art_resp.text()
            links = re.findall(r'(https?://[^\s\"\']+\.(?:mp3|mp4|zip))', art_html)
            for l in set(links):
                print("FOUND MEDIA:", l)
            if 'download.php' in art_html:
                print("download.php found in article!")
            elif 'دسترسی شما' in art_html:
                print("access denied message found")
            else:
                with open('article_dump.html', 'w', encoding='utf-8') as f:
                    f.write(art_html)
                print("Saved article HTML to article_dump.html")

asyncio.run(test_login())
