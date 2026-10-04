import sys
c = open('services/feed_crawler.py', encoding='utf-8').read()
new_cat = """    {
        "id": 1,
        "emoji": "🌐",
        "slug": "all-downloads",
        "title": "تمام دانلودها",
        "url": "https://abasmanesh.com/fa/articles/",
        "path": "/fa/articles/"
    },
"""
c = c.replace('OFFICIAL_17_CATEGORIES: List[Dict[str, Any]] = [\n', 'OFFICIAL_17_CATEGORIES: List[Dict[str, Any]] = [\n' + new_cat)
open('services/feed_crawler.py', 'w', encoding='utf-8').write(c)
print('Added All Downloads category!')
