import re
lines = open('services/web_panel.py', encoding='utf-8').read()
m = re.findall(r'/api/(?:store|admin)/[^\'"]+', lines)
for x in set(m): print(x.strip())
