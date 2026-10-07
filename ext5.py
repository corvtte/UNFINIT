import re

def ext5():
    with open('services/web_panel.py', 'r', encoding='utf-8') as f:
        text = f.read()

    match = re.search(r'(<div id="usersTab" .*?)(<div id="settingsTab")', text, re.DOTALL)
    if not match:
        match = re.search(r'(<div id="usersTab".*?)(<div id=")', text, re.DOTALL)
        
    if match:
        with open('u_tab.txt', 'w', encoding='utf-8') as f:
            f.write(match.group(1))
        print("Success")

ext5()
