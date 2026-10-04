import sys, re

filepath = 'services/feed_crawler.py'
text = open(filepath, encoding='utf-8').read()

# Fix update_cookies
old_cookie = 'session.cookie_jar.update_cookies(extracted_cookies)'
new_cookie = 'import yarl\n                session.cookie_jar.update_cookies(extracted_cookies, response_url=yarl.URL("https://abasmanesh.com"))'
if old_cookie in text:
    text = text.replace(old_cookie, new_cookie)

# Fix login payload
old_login = '''                match = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
                csrf = match.group(1) if match else ""
            
            headers = dict(session.headers)
            headers.update({
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": "https://abasmanesh.com/fa/login/",
                "Origin": "https://abasmanesh.com"
            })
            
            payload = {
                "csrf_token": csrf,
                "email": username.strip(),
                "password": password.strip(),
                "remember": "on"
            }'''

new_login = '''                match = re.search(r'name="_token"\s+value="([^"]+)"', html)
                csrf = match.group(1) if match else ""
            
            headers = dict(session.headers)
            headers.update({
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": "https://abasmanesh.com/fa/login/",
                "Origin": "https://abasmanesh.com"
            })
            
            payload = {
                "_token": csrf,
                "login_method": "email",
                "identifier": username.strip(),
                "password": password.strip(),
                "remember_me": "1"
            }'''

if old_login in text:
    text = text.replace(old_login, new_login)
    open(filepath, 'w', encoding='utf-8').write(text)
    print("Fixed login logic and cookie injection")
else:
    print("Login logic not found")
