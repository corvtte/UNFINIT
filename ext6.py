import re

def ext6():
    with open('services/web_panel.py', 'r', encoding='utf-8') as f:
        text = f.read()

    match = re.search(r'<div [^>]*id="[^"]*users[^"]*"', text)
    if match:
        print("Found:", match.group(0))

ext6()
