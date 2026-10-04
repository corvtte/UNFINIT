import sys
sys.stdout.reconfigure(encoding='utf-8')
lines = open('services/web_panel.py', encoding='utf-8').readlines()
idx = next((i for i, l in enumerate(lines) if "id='feedAuthModal'" in l or 'id="feedAuthModal"' in l), -1)
if idx != -1:
    print(''.join(lines[idx:idx+45]))
