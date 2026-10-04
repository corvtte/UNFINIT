import re
h = open('login.html', encoding='utf-8').read()
if 'Just a moment...' in h or 'Cloudflare' in h:
    print('CLOUDFLARE DETECTED')
else:
    print('No CF. Token matches:', re.findall(r'name=["\']_token["\']\s+value=["\']([^"\']+)["\']', h))
