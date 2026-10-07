import re
def dump2():
    with open('services/web_panel.py', 'r', encoding='utf-8') as f:
        text = f.read()

    match = re.search(r'(<div id="usersTab".*?)(<div id="settingsTab"|<div id="ordersTab"|<div id="studioTab")', text, re.DOTALL)
    if match:
        with open('users_ui2.txt', 'w', encoding='utf-8') as f:
            f.write(match.group(1))

dump2()
