import re

p_file = 'services/feed_crawler.py'
text = open(p_file, encoding='utf-8').read()

text = text.replace(r"r'(https?://[^\"']+\.mp4)'", r"r'(https?://[^\u0022\u0027]+\.mp4)'")
text = text.replace(r"r'(https?://[^\"']+\.(?:mp3|m4a))'", r"r'(https?://[^\u0022\u0027]+\.(?:mp3|m4a))'")

open(p_file, 'w', encoding='utf-8').write(text)
