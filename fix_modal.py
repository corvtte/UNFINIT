import re

def fix_modal():
    with open('services/web_panel.py', 'r', encoding='utf-8') as f:
        html = f.read()

    # Find the modal
    pattern = re.compile(r'(<div id="feedDispatchModal".*?>)(.*?)(</button>\n                </div>\n            </div>\n        </div>)', re.DOTALL)
    match = pattern.search(html)
    if not match:
        print("Modal not found")
        return

    modal_content = match.group(2)
    
    # Replace colors
    modal_content = modal_content.replace('border-slate-700/60', 'border-[var(--card-border)]')
    modal_content = modal_content.replace('text-slate-400', 'text-[var(--text-muted)]')
    modal_content = modal_content.replace('text-slate-200', 'text-[var(--text-main)]')
    modal_content = modal_content.replace('text-slate-300', 'text-[var(--text-main)]')
    modal_content = modal_content.replace('bg-cyan-700 hover:bg-cyan-600 text-white', 'theme-accent-btn')
    modal_content = modal_content.replace('border border-slate-800 text-xs font-bold text-cyan-300', 'border text-xs font-bold text-[var(--accent-color)]')
    modal_content = modal_content.replace('text-cyan-400', 'text-[var(--accent-color)]')
    modal_content = modal_content.replace('text-cyan-500', 'text-[var(--accent-color)]')
    modal_content = modal_content.replace('text-cyan-600', 'text-[var(--accent-color)]')
    modal_content = modal_content.replace('text-emerald-600', 'text-[var(--accent-color)]')
    modal_content = modal_content.replace('text-indigo-600', 'text-[var(--accent-color)]')
    
    # Button text fix:
    modal_content = re.sub(r'<span>ارسال به پلتفرم‌های انتخاب‌شده</span>', r'<span>انتقال به ربات</span>', modal_content)

    new_html = html[:match.start()] + match.group(1) + modal_content + match.group(3) + html[match.end():]
    
    with open('services/web_panel.py', 'w', encoding='utf-8') as f:
        f.write(new_html)

fix_modal()
