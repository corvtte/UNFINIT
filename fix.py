with open('services/web_panel.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace("b.setAttribute('draggable', 'true')", "b.setAttribute('draggable', 'false')")
text = text.replace('draggable="true"', 'draggable="false"')

with open('services/web_panel.py', 'w', encoding='utf-8') as f:
    f.write(text)
