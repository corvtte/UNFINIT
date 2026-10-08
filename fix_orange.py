import re

with open('services/web_panel.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Let's replace hardcoded orange classes in the platforms section!
# In the dashboard, there is a span:
# <span class="bg-orange-500/10 text-orange-400 text-[10px] px-2 py-0.5 rounded-full border border-orange-500/20">نشست فعال</span>
# We should change it to use theme CSS vars! Like text-accent-400 or just `theme-accent-btn` or similar, or a generic dynamic accent class!
# Actually, the user says "نشست فعال" should be green if the platform is active, and use the theme accent!
# Right now it's probably bg-orange-500/10 text-orange-400.

target = r'bg-orange-500/10 text-orange-400.*?border-orange-500/20'
repl = r'bg-teal-500/10 text-teal-400 text-[10px] px-2 py-0.5 rounded-full border border-teal-500/20'
# But wait, the user said "اصلا به این تم سبز ما نمیخوره". We should make it inherit from theme!
# style="color: var(--accent-color); background: color-mix(in srgb, var(--accent-color) 10%, transparent); border-color: color-mix(in srgb, var(--accent-color) 20%, transparent);"
repl_css = r'text-[10px] px-2 py-0.5 rounded-full border" style="color: var(--accent-color); background: color-mix(in srgb, var(--accent-color) 10%, transparent); border-color: color-mix(in srgb, var(--accent-color) 20%, transparent);"'

new_text = re.sub(target, repl_css, text)

# Let's also check for any hardcoded white text that might look bad
# "توش اومده با یه سفید کم‌رنگی که اصلا به این تم سبز ما نمی‌خوره"

with open('services/web_panel.py', 'w', encoding='utf-8') as f:
    f.write(new_text)
print("Replaced orange platform badges with theme-colored badges.")
