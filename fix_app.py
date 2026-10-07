import re

def fix_app():
    with open('app.py', 'r', encoding='utf-8') as f:
        text = f.read()

    # Find the merged_map[uid] = { ... } in app.py
    # We need to make sure created_at is returned, either from User object (u) or from customer row
    # In app.py around line 400:
    # "is_vip": UserService.is_user_vip(uid),
    
    # Let's replace the merged_map generation to include created_at
    # Actually, all_users are already serialized: `for p, u in all_users.items(): d = u.to_dict()`
    # `d` already has `created_at`!
    # The `merged_map` just creates a mock User dict for customers that aren't in `all_users`!
    # So I just need to add `"created_at": rc.get("created_at") or 0,` to the else block.
    
    text = text.replace('"is_vip": UserService.is_user_vip(uid),', '"is_vip": UserService.is_user_vip(uid),\n                            "created_at": rc.get("created_at") or 0,')
    
    with open('app.py', 'w', encoding='utf-8') as f:
        f.write(text)

fix_app()
