import re

def ext():
    with open('services/web_panel.py', 'r', encoding='utf-8') as f:
        text = f.read()

    match = re.search(r'(def render_dashboard_html.*?)(return html_template)', text, re.DOTALL)
    if match:
        with open('dash.txt', 'w', encoding='utf-8') as f:
            f.write(match.group(1))

ext()
