import sys

text = open('services/feed_scraper.py', encoding='utf-8').read()
old = 'if not cover_url or "og-default" not in og_content:\n                            cover_url = og_content'
new = 'og_content = og_content.replace("/storage//storage/", "/storage/")\n                        if not cover_url or "og-default" in cover_url:\n                            cover_url = og_content'

if old in text:
    text = text.replace(old, new)
    open('services/feed_scraper.py', 'w', encoding='utf-8').write(text)
    print('Fixed cover_url override bug')
else:
    print('Pattern not found')
