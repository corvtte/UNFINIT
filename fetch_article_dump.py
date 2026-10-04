import asyncio, aiohttp

async def fetch_article():
    email = 'sajjadthvh@gmail.com'
    password = 'sajjad2//'
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    async with aiohttp.ClientSession(headers=headers, cookie_jar=aiohttp.CookieJar()) as session:
        # Get CSRF
        async with session.get('https://abasmanesh.com/fa/login/') as r:
            h = await r.text()
            import re
            m = re.search(r'name="_token"\s+value="([^"]+)"', h)
            if not m:
                print("CSRF not found")
                return
            csrf = m.group(1)
            
        data = {'_token': csrf, 'login_method': 'email', 'identifier': email, 'password': password, 'remember_me': '1'}
        await session.post('https://abasmanesh.com/fa/login/', data=data, allow_redirects=False)
        
        async with session.get('https://abasmanesh.com/fa/take-it-easy-so-that-become-easy/', allow_redirects=True) as r:
            print("Article status:", r.status)
            html = await r.text()
            with open('article_dump.html', 'w', encoding='utf-8') as f:
                f.write(html)
            
            links = re.findall(r'(https?://[^\s\"\']+\.(?:mp3|mp4|zip))', html)
            for l in set(links):
                print("FOUND DIRECT LINK:", l)
            if 'download.php' in html:
                print("Found download.php")
                
            # Let's search for typical download links in Laravel
            import bs4
            soup = bs4.BeautifulSoup(html, 'html.parser')
            for a in soup.find_all('a'):
                if a.get('href') and ('download' in a.get('href') or 'dl' in a.get('href') or 'mp3' in a.get('href') or 'mp4' in a.get('href')):
                    print("Possible download link:", a.get('href'))

asyncio.run(fetch_article())
