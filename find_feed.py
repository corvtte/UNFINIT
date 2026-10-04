import re
lines = open('app.py', encoding='utf-8').read()
m = re.findall(r'/api/feed/[^\'"]+', lines)
for x in set(m): print(x.strip())
