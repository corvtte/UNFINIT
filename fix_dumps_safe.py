import re

def fix_dumps(filepath):
    text = open(filepath, encoding='utf-8').read()
    
    # 1. Content-Type charset
    text = text.replace('"application/json"', '"application/json; charset=utf-8"')
    text = text.replace("'application/json'", "'application/json; charset=utf-8'")
    
    # Revert accepts
    text = text.replace('Accept", "application/json; charset=utf-8"', 'Accept", "application/json, text/html"')
    text = text.replace('Accept", "application/json; charset=utf-8, text/html"', 'Accept", "application/json, text/html"')
    text = text.replace('"application/json; charset=utf-8, text/html"', '"application/json, text/html"')
    text = text.replace('application/json; charset=utf-8; charset=utf-8', 'application/json; charset=utf-8')

    # 2. json.dumps ensure_ascii
    # We will find `json.dumps(` and balance parenthesis to find the end.
    def add_ensure_ascii(text):
        out = []
        i = 0
        while i < len(text):
            idx = text.find('json.dumps(', i)
            if idx == -1:
                out.append(text[i:])
                break
            out.append(text[i:idx+11])
            i = idx + 11
            
            # Balance parenthesis
            depth = 1
            start_arg = i
            while i < len(text) and depth > 0:
                if text[i] == '(':
                    depth += 1
                elif text[i] == ')':
                    depth -= 1
                i += 1
            
            args = text[start_arg:i-1]
            if 'ensure_ascii' not in args:
                out.append(args + ', ensure_ascii=False)')
            else:
                out.append(args + ')')
        return "".join(out)

    text = add_ensure_ascii(text)
    
    open(filepath, 'w', encoding='utf-8').write(text)

fix_dumps('app.py')
