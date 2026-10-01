import re
p = 'services/web_panel.py'
text = open(p, encoding='utf-8').read()

# Fix cfg_FEED_AUTH_EMAIL and cfg_FEED_AUTH_PASSWORD class
text = re.sub(r'id="cfg_FEED_AUTH_EMAIL"[^>]*class="[^"]*"', r'id="cfg_FEED_AUTH_EMAIL" placeholder="user@example.com" class="w-full rounded-xl px-4 py-2.5 text-xs font-mono transition focus:outline-none"', text)
text = re.sub(r'id="cfg_FEED_AUTH_PASSWORD"[^>]*class="[^"]*"', r'id="cfg_FEED_AUTH_PASSWORD" data-token-field="true" autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false" data-lpignore="true" class="w-full rounded-xl px-4 py-2.5 pl-9 text-xs font-mono transition focus:outline-none"', text)

# Fix cfg_FEED_AUTH_COOKIE class
text = re.sub(r'id="cfg_FEED_AUTH_COOKIE"[^>]*class="[^"]*"', r'id="cfg_FEED_AUTH_COOKIE" dir="ltr" rows="2" class="w-full rounded-xl px-4 py-2.5 text-xs font-mono transition focus:outline-none"', text)

# Fix Accordion 8 test button colors
text = text.replace('class="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs rounded-xl font-bold transition flex items-center gap-2 border border-slate-700"', 'class="px-4 py-2 text-xs rounded-xl font-bold transition flex items-center gap-2 border" style="background: var(--input-bg); border-color: var(--border-color); color: var(--text-color);"')

# Fix quick_FEED_AUTH_* inputs
text = re.sub(r'id="quick_FEED_AUTH_EMAIL"[^>]*class="[^"]*"', r'id="quick_FEED_AUTH_EMAIL" dir="ltr" class="w-full rounded-xl px-4 py-2.5 text-xs font-mono transition focus:outline-none"', text)
text = re.sub(r'id="quick_FEED_AUTH_PASSWORD"[^>]*class="[^"]*"', r'id="quick_FEED_AUTH_PASSWORD" dir="ltr" class="w-full rounded-xl px-4 py-2.5 pl-9 text-xs font-mono transition focus:outline-none"', text)
text = re.sub(r'id="quick_FEED_AUTH_COOKIE"[^>]*class="[^"]*"', r'id="quick_FEED_AUTH_COOKIE" dir="ltr" rows="2" class="w-full rounded-xl px-4 py-2.5 text-xs font-mono transition focus:outline-none"', text)

# Fix modal container background if it has hardcoded slate classes (wait, it uses var(--panel-bg))
# But let's verify if there are any bg-slate, text-slate inside the modal
text = text.replace('text-slate-300 leading-relaxed', 'leading-relaxed" style="color: var(--text-muted);')
text = text.replace('text-slate-400 mb-1', 'mb-1" style="color: var(--text-muted);')

open(p, 'w', encoding='utf-8').write(text)
