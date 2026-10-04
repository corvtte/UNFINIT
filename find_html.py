import sys, re
c = open('services/web_panel.py', encoding='utf-8').read()
m = re.search(r'<div[^>]*id=[\'"]quickFeedAuthResult[\'"][^>]*>.*?</div', c, re.DOTALL)
if m: print(m.group(0))
