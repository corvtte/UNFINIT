import re

def fix_dumps(filepath):
    text = open(filepath, encoding='utf-8').read()
    
    # Add charset to application/json
    text = text.replace('"application/json"', '"application/json; charset=utf-8"')
    text = text.replace("'application/json'", "'application/json; charset=utf-8'")
    
    # Revert accept headers
    text = text.replace('Accept", "application/json; charset=utf-8"', 'Accept", "application/json, text/html"')
    text = text.replace('Accept", "application/json; charset=utf-8, text/html"', 'Accept", "application/json, text/html"')
    text = text.replace('"application/json; charset=utf-8, text/html"', '"application/json, text/html"')
    text = text.replace('application/json; charset=utf-8; charset=utf-8', 'application/json; charset=utf-8')

    # Replace json.dumps to add ensure_ascii=False
    def dumps_replacer(match):
        inner = match.group(1)
        if 'ensure_ascii' not in inner:
            return f"json.dumps({inner}, ensure_ascii=False)"
        return match.group(0)

    # Simple matching for json.dumps({ ... })
    text = re.sub(r'json\.dumps\((\{.*?\})\)', dumps_replacer, text, flags=re.DOTALL)
    
    # Specifically for those multiline dumps calls
    text = text.replace('str(e)})', 'str(e)}, ensure_ascii=False)')
    text = text.replace('dict(r)]}', 'dict(r)]}, ensure_ascii=False)')
    text = text.replace('u.is_vip()}', 'u.is_vip()}, ensure_ascii=False)')
    text = text.replace('len(cats)}', 'len(cats)}, ensure_ascii=False)')
    text = text.replace('u.to_dict()}', 'u.to_dict()}, ensure_ascii=False)')
    text = text.replace('len(out_bytes)}', 'len(out_bytes)}, ensure_ascii=False)')
    text = text.replace('bool(new_state)}', 'bool(new_state)}, ensure_ascii=False)')

    # Revert if I added it twice
    text = text.replace('ensure_ascii=False, ensure_ascii=False', 'ensure_ascii=False')

    open(filepath, 'w', encoding='utf-8').write(text)

fix_dumps('app.py')
fix_dumps('services/web_panel.py')
