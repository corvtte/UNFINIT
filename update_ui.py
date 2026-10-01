import re

p = 'services/web_panel.py'
text = open(p, encoding='utf-8').read()

# Make sure the inputs have the exact class
# I will use regex to find the inputs for FEED_AUTH_EMAIL, FEED_AUTH_PASSWORD, and FEED_AUTH_COOKIE
# and replace their class and style attributes.
def replace_input_class(match):
    prefix = match.group(1)
    return prefix + 'class="w-full rounded-xl px-4 py-2.5 text-xs font-mono transition focus:outline-none" style="background: var(--input-bg); border-color: var(--border-color); color: var(--text-color);"'

text = re.sub(r'(id="cfg_FEED_AUTH_EMAIL"[^>]*?)class="[^"]*"[^>]*style="[^"]*"', replace_input_class, text)
text = re.sub(r'(id="cfg_FEED_AUTH_PASSWORD"[^>]*?)class="[^"]*"[^>]*style="[^"]*"', replace_input_class, text)
text = re.sub(r'(id="cfg_FEED_AUTH_COOKIE"[^>]*?)class="[^"]*"[^>]*style="[^"]*"', replace_input_class, text)
text = re.sub(r'(id="quick_FEED_AUTH_EMAIL"[^>]*?)class="[^"]*"[^>]*style="[^"]*"', replace_input_class, text)
text = re.sub(r'(id="quick_FEED_AUTH_PASSWORD"[^>]*?)class="[^"]*"[^>]*style="[^"]*"', replace_input_class, text)
text = re.sub(r'(id="quick_FEED_AUTH_COOKIE"[^>]*?)class="[^"]*"[^>]*style="[^"]*"', replace_input_class, text)

# Add clear button next to FEED_AUTH_COOKIE in Accordion 8
# We have a label and a textarea. We can wrap the textarea in a relative div or just add a flex container.
# Wait, the instructions say "Add an inline SVG clear button next to FEED_AUTH_COOKIE".
# Let's wrap textarea in a relative div and put the button inside, or just a flex header.
# Let's see the current Accordion 8 layout for cookie:
# <label class="...">سشن کوکی ...</label>
# <textarea id="cfg_FEED_AUTH_COOKIE"...
# Let's replace the label with a flex container containing the label and the clear button.
clear_btn = """<button type="button" onclick="document.getElementById('cfg_FEED_AUTH_COOKIE').value=''; if(document.getElementById('quick_FEED_AUTH_COOKIE')) document.getElementById('quick_FEED_AUTH_COOKIE').value='';" class="text-slate-400 hover:text-rose-400 transition" title="پاک کردن کوکی">
                                            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                                        </button>"""

text = re.sub(r'(<label class="block text-xs font-bold text-slate-400 mb-1">سشن کوکی مرورگر[^<]*</label>)',
              r'<div class="flex items-center justify-between mb-1">\1' + clear_btn + '</div>', text)

# Also add the clear button to the modal's quick_FEED_AUTH_COOKIE
modal_clear_btn = """<button type="button" onclick="document.getElementById('quick_FEED_AUTH_COOKIE').value=''; if(document.getElementById('cfg_FEED_AUTH_COOKIE')) document.getElementById('cfg_FEED_AUTH_COOKIE').value='';" class="text-slate-400 hover:text-rose-400 transition" title="پاک کردن کوکی">
                            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                        </button>"""

text = re.sub(r'(<label class="block text-\[11px\] font-bold text-slate-400 mb-1">FEED_AUTH_COOKIE \(سشن کوکی مرورگر - اولویت\)</label>)',
              r'<div class="flex items-center justify-between mb-1">\1' + modal_clear_btn + '</div>', text)

# Ensure font-family on auth modal and error alerts
# Adding style="font-family: 'IRANSans', 'Vazirmatn', sans-serif;" to the modal container.
text = text.replace('id="feedAuthModal" class="fixed inset-0', 'id="feedAuthModal" style="font-family: \'IRANSans\', \'Vazirmatn\', sans-serif;" class="fixed inset-0')
text = text.replace("resDiv.className = 'mt-3 p-3 rounded-xl text-[10px] font-mono border text-left whitespace-pre-wrap break-all bg-rose-950/40 border-rose-900/50 text-rose-300';", "resDiv.className = 'mt-3 p-3 rounded-xl text-[10px] border text-left whitespace-pre-wrap break-all bg-rose-950/40 border-rose-900/50 text-rose-300'; resDiv.style.fontFamily = \"'IRANSans', 'Vazirmatn', sans-serif\";")

open(p, 'w', encoding='utf-8').write(text)
