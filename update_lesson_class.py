import sys
import re

for filename in ['services/feed_crawler.py', 'services/feed_scraper.py']:
    c = open(filename, encoding='utf-8').read()
    c = c.replace('["entry-content", "post-content", "article__body", "article-content"]', '["content-markdown--card", "entry-content", "post-content", "article__body", "article-content"]')
    open(filename, 'w', encoding='utf-8').write(c)

print('Updated lesson_text class selectors!')
