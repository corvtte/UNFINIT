import re

def ext4():
    with open('services/web_panel.py', 'r', encoding='utf-8') as f:
        text = f.read()

    match = re.search(r'مدیریت کاربران', text)
    if match:
        start = max(0, match.start() - 500)
        end = min(len(text), match.end() + 2000)
        with open('users_ui.txt', 'w', encoding='utf-8') as f:
            f.write(text[start:end])

ext4()
