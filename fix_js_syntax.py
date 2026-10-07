import re

def fix_syntax():
    with open('services/web_panel.py', 'r', encoding='utf-8') as f:
        text = f.read()

    broken_code = """                    const filtered = allLoadedUsers.filter(u => {{
                        const id = String(u.user_id || '').toLowerCase();
                        const name = String(u.username || u.name || '').toLowerCase();
                        const phone = String(u.phone || '').toLowerCase();
                        const ref = String(u.referred_by || '').toLowerCase();
                        return id.includes(q) || name.includes(q) || phone.includes(q) || ref.includes(q);
                    }});
                    renderUsersTable(filtered);
                }}"""
    
    text = text.replace(broken_code, "")
    
    with open('services/web_panel.py', 'w', encoding='utf-8') as f:
        f.write(text)

fix_syntax()
