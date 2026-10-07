import re

def fix_users_tab():
    with open('services/web_panel.py', 'r', encoding='utf-8') as f:
        text = f.read()

    # 1. Emjois:
    # Telegram emoji: ✈️
    # Bale emoji: 🟢
    # Rubika emoji: 🟣
    # Let's replace them with SVGs.
    tg_svg = '<svg class="w-4 h-4 text-cyan-400 inline" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.75"><path stroke-linecap="round" stroke-linejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" /></svg>'
    bale_svg = '<svg class="w-4 h-4 text-emerald-400 inline" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.75"><path stroke-linecap="round" stroke-linejoin="round" d="M12 2.25c-5.385 0-9.75 4.365-9.75 9.75s4.365 9.75 9.75 9.75 9.75-4.365 9.75-9.75S17.385 2.25 12 2.25z" /></svg>'
    
    text = text.replace('✈️', tg_svg)
    text = text.replace('🟢', bale_svg)
    
    # 2. Removing Rubika from UI
    # In user table:
    # we need to skip appending rubika users
    # "elif p == "rubika":"
    
    # In web_panel.py, there is probably a loop over platforms.
    # Let's search for rubika and remove it from lists.
    
    with open('services/web_panel.py', 'w', encoding='utf-8') as f:
        f.write(text)

fix_users_tab()
