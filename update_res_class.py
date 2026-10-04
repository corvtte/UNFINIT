import sys
c = open('services/web_panel.py', encoding='utf-8').read()
old = '<div id="quickFeedAuthResult" class="hidden mt-2 p-3 rounded-xl text-[10px] font-mono border text-left whitespace-pre-wrap break-all" style="background: var(--card-bg); border-color: var(--card-border); color: var(--text-color);"></div>'
new = '<div id="quickFeedAuthResult" class="hidden mt-3 p-3 rounded-xl text-xs font-sans border text-right leading-relaxed shadow-sm" style="background: var(--card-bg); border-color: var(--card-border); color: var(--text-color);"></div>'
c = c.replace(old, new)

# Let's also check the JS where we populate `quickFeedAuthResult`
# It might add `<span class="text-emerald-500 font-bold">✅ ورود موفق:</span> `
# I will make sure the text alignment works well.
open('services/web_panel.py', 'w', encoding='utf-8').write(c)
print('Updated quickFeedAuthResult class')
