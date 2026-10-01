p = 'app.py'
t = open(p, encoding='utf-8').read()
t = t.replace('"FEED_AUTH_PASSWORD": "FEED_AUTH_PASSWORD",\n', '"FEED_AUTH_PASSWORD": "FEED_AUTH_PASSWORD",\n                    "FEED_AUTH_COOKIE": "FEED_AUTH_COOKIE",\n')
t = t.replace('                        "FEED_AUTH_COOKIE": "FEED_AUTH_COOKIE",\n', '"FEED_AUTH_COOKIE": "FEED_AUTH_COOKIE",\n') # just fix if it replaced twice wrongly. Wait, let's just use re.
import re
t = open(p, encoding='utf-8').read()
t = re.sub(r'("FEED_AUTH_PASSWORD": "FEED_AUTH_PASSWORD",)', r'\1\n                    "FEED_AUTH_COOKIE": "FEED_AUTH_COOKIE",', t)
open(p, 'w', encoding='utf-8').write(t)
