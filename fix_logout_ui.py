import sys
filepath = 'services/web_panel.py'
text = open(filepath, encoding='utf-8').read()

old_btns = '''                        <button type="button" onclick="testCrawlerConnection(this)" class="flex-1 py-2 rounded-xl text-sm font-bold bg-slate-700 hover:bg-slate-600 text-white transition flex justify-center items-center gap-1.5" style="background: var(--button-bg, #334155);">
                            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
                            <span>تست اتصال</span>
                        </button>
                    </div>'''

new_btns = '''                        <button type="button" onclick="testCrawlerConnection(this)" class="flex-1 py-2 rounded-xl text-sm font-bold bg-slate-700 hover:bg-slate-600 text-white transition flex justify-center items-center gap-1.5" style="background: var(--button-bg, #334155);">
                            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
                            <span>تست اتصال</span>
                        </button>
                    </div>
                    <button type="button" onclick="logoutCrawlerConnection(this)" class="w-full mt-2 py-2 rounded-xl text-sm font-bold bg-rose-600 hover:bg-rose-500 text-white transition flex justify-center items-center gap-1.5">
                        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"></path></svg>
                        <span>خروج از اکانت مرجع</span>
                    </button>'''

if old_btns in text:
    text = text.replace(old_btns, new_btns)
    open(filepath, 'w', encoding='utf-8').write(text)
    print("Logout button added")
else:
    print("UI pattern not found")
