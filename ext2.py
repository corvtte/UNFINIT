import re

def ext2():
    with open('services/web_panel.py', 'r', encoding='utf-8') as f:
        text = f.read()

    matches = re.findall(r'id="([a-zA-Z]+Tab)"', text)
    print(set(matches))

ext2()
