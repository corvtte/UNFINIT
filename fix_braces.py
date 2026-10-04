import sys
lines = open('services/web_panel.py', encoding='utf-8').read()
lines = lines.replace("body: '{}'", "body: '{{}}'")
open('services/web_panel.py', 'w', encoding='utf-8').write(lines)
