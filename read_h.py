import re
with open('platforms/telegram_adapter.py', 'r', encoding='utf-8') as f:
    text = f.read()
match = re.search(r'action == "format_menu".*?elif action == "audio_specs"', text, re.DOTALL)
if match:
    with open('h_dump.txt', 'w', encoding='utf-8') as out:
        out.write(match.group(0))
