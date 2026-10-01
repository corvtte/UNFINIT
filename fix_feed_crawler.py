p = 'services/feed_crawler.py'
t = open(p, encoding='utf-8').read()
t = t.replace("parts = re.split(r'[;\n]', auth_cookie)", "parts = re.split(r'[;\\\\n]', auth_cookie)")
t = t.replace("r'[;\n]'", "r'[;\\\\n]'")
open(p, 'w', encoding='utf-8').write(t)
