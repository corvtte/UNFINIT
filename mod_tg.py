import re

with open('platforms/telegram_adapter.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = re.sub(
    r'InlineKeyboardButton\("[^"]+", callback_data=f"smeta:to_mp3:\{drop_id\}"\)',
    'InlineKeyboardButton("🔄 تغییر فرمت", callback_data=f"smeta:format_menu:{drop_id}")',
    text
)

with open('platforms/telegram_adapter.py', 'w', encoding='utf-8') as f:
    f.write(text)

with open('platforms/bale_adapter.py', 'r', encoding='utf-8') as f:
    text2 = f.read()

text2 = re.sub(
    r'\{"text": "[^"]+", "callback_data": f"bmeta:to_mp3:\{drop_id\}"\}',
    '{"text": "🔄 تغییر فرمت", "callback_data": f"bmeta:format_menu:{drop_id}"}',
    text2
)

with open('platforms/bale_adapter.py', 'w', encoding='utf-8') as f:
    f.write(text2)
