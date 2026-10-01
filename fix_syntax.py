import re

p = 'app.py'
text = open(p, encoding='utf-8').read()

# Fix unmatched parenthesis
text = text.replace('}, ensure_ascii=False), ensure_ascii=False).encode', '}, ensure_ascii=False).encode')
text = text.replace('}, ensure_ascii=False)', '}')

# Wait, `}, ensure_ascii=False)` could be valid if it's the end of json.dumps.
# Let's be careful. The errors came from my blind string replacements in `fix_dumps.py`:
# text = text.replace('str(e)})', 'str(e)}, ensure_ascii=False)')
# text = text.replace('dict(r)]}', 'dict(r)]}, ensure_ascii=False)')
# text = text.replace('u.is_vip()}', 'u.is_vip()}, ensure_ascii=False)')
# text = text.replace('len(cats)}', 'len(cats)}, ensure_ascii=False)')
# text = text.replace('u.to_dict()}', 'u.to_dict()}, ensure_ascii=False)')
# text = text.replace('len(out_bytes)}', 'len(out_bytes)}, ensure_ascii=False)')
# text = text.replace('bool(new_state)}', 'bool(new_state)}, ensure_ascii=False)')

# If it's `str(e)}, ensure_ascii=False)`, but the line was `json.dumps({"ok": False, "error": str(e)})`
# then it became `json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))`
# Let's fix `}, ensure_ascii=False))` to `}, ensure_ascii=False)`
text = text.replace('}, ensure_ascii=False))', '}, ensure_ascii=False)')

# The error above is `{"ok": True, "active": bool(new_state)}, ensure_ascii=False), ensure_ascii=False).encode("utf-8")`
text = text.replace('}, ensure_ascii=False), ensure_ascii=False)', '}, ensure_ascii=False)')

# What about `{"ok": True, "active": bool(new_state)}, ensure_ascii=False).encode("utf-8")`?
# Is that `json.dumps({"ok": True, "active": bool(new_state)}, ensure_ascii=False).encode("utf-8")`? Yes.
# But wait, earlier we had `res = {"ok": True, "categories": cats, "count": len(cats)}, ensure_ascii=False)`
text = text.replace('res = {"ok": True, "categories": cats, "count": len(cats)}, ensure_ascii=False)', 'res = {"ok": True, "categories": cats, "count": len(cats)}')
text = text.replace('res = {"ok": True, "categories": cats, "count": len(cats)}', 'res = {"ok": True, "categories": cats, "count": len(cats)}')

open(p, 'w', encoding='utf-8').write(text)
