import re
import os

def fix_utf8(filepath):
    text = open(filepath, encoding='utf-8').read()
    
    # 1. Fix Content-Type
    text = text.replace('"application/json"', '"application/json; charset=utf-8"')
    text = text.replace("'application/json'", "'application/json; charset=utf-8'")
    
    # Revert if it replaced inside accept headers or double applied
    text = text.replace('application/json; charset=utf-8; charset=utf-8', 'application/json; charset=utf-8')
    text = text.replace('Accept", "application/json; charset=utf-8"', 'Accept", "application/json, text/html"')
    
    # 2. Fix json.dumps
    # Find all json.dumps calls
    def dumps_replacer(match):
        inner = match.group(1)
        if 'ensure_ascii' not in inner:
            return f"json.dumps({inner}, ensure_ascii=False)"
        return match.group(0)
        
    text = re.sub(r'json\.dumps\((.*?)\)', dumps_replacer, text, flags=re.DOTALL)
    
    open(filepath, 'w', encoding='utf-8').write(text)

fix_utf8('app.py')
fix_utf8('services/web_panel.py')
