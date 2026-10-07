import re
def dump_js():
    with open('services/web_panel.py', 'r', encoding='utf-8') as f:
        text = f.read()

    match = re.search(r'(async function loadUsersData\(\) \{.*?)(async function toggleUserVip)', text, re.DOTALL)
    if match:
        with open('users_js.txt', 'w', encoding='utf-8') as f:
            f.write(match.group(1))

dump_js()
