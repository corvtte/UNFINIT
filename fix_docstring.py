p = 'services/feed_crawler.py'
t = open(p, encoding='utf-8').read()
t = t.replace(r'\"\"\"Lightweight authenticated probe to check connection health and auth status\"\"\"', '"""Lightweight authenticated probe to check connection health and auth status"""')
open(p, 'w', encoding='utf-8').write(t)
