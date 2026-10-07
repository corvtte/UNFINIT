import re

def fix():
    for fn in ['platforms/telegram_adapter.py', 'platforms/bale_adapter.py']:
        with open(fn, 'r', encoding='utf-8') as f: text = f.read()
        
        # fix the unescaped newlines in edit_message_text strings
        pattern = re.compile(r'(await (?:status_msg\.edit_text|bale\.edit_message_text)\(.*?)(⏳ <b>در حال ارسال [^"]*)\n\n([^"]*")\)', re.DOTALL)
        
        while pattern.search(text):
            text = pattern.sub(r'\1\2\\n\\n\3)', text)
            
        with open(fn, 'w', encoding='utf-8') as f: f.write(text)

fix()
