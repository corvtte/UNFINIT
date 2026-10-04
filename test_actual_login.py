import asyncio, aiohttp

async def test_login():
    email = 'sajjadthvh@gmail.com'
    password = 'sajjad2//'
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://abasmanesh.com/fa/login/',
        'Origin': 'https://abasmanesh.com'
    }
    
    async with aiohttp.ClientSession(headers=headers, cookie_jar=aiohttp.CookieJar()) as session:
        async with session.get('https://abasmanesh.com/fa/login/', timeout=10) as resp:
            html = await resp.text()
            import re
            m = re.search(r'name="_token"\s+value="([^"]+)"', html)
            if not m:
                print('No CSRF token found!')
                return
            csrf = m.group(1)
            print('Found CSRF:', csrf)
            
        data = {
            '_token': csrf,
            'login_method': 'email',
            'identifier': email,
            'password': password,
            'remember_me': '1'
        }
        
        print('Posting data...')
        async with session.post('https://abasmanesh.com/fa/login/', data=data, allow_redirects=False, timeout=10) as resp:
            print('Login Status:', resp.status)
            print('Location Header:', resp.headers.get('Location'))
            print('Cookies:', session.cookie_jar.filter_cookies('https://abasmanesh.com'))
            if resp.status == 302 and '/profile' in str(resp.headers.get('Location', '')):
                print('LOGIN SUCCESSFUL')
                
                # Try fetching the article!
                print("Fetching article...")
                async with session.get('https://abasmanesh.com/fa/take-it-easy-so-that-become-easy/', timeout=10) as art_resp:
                    art_html = await art_resp.text()
                    links = re.findall(r'(https?://[^\s\"\']+\.(?:mp3|mp4|zip))', art_html)
                    for l in set(links):
                        print("FOUND MEDIA:", l)
                    if 'download.php' in art_html:
                        print("download.php found in article!")
                        
            else:
                print('LOGIN FAILED')

asyncio.run(test_login())
