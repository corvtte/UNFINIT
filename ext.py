import re

def ext():
    with open('services/web_panel.py', 'r', encoding='utf-8') as f:
        text = f.read()

    match = re.search(r'(<div id="usersTab".*?)(<div id="ordersTab")', text, re.DOTALL)
    if match:
        with open('users_tab.txt', 'w', encoding='utf-8') as f:
            f.write(match.group(1))
        print('Saved users_tab.txt')

ext()
