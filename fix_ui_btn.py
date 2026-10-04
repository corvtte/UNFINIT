import sys

filepath = 'services/web_panel.py'
text = open(filepath, encoding='utf-8').read()

old_html = '''                    <button type="button" onclick="saveQuickFeedAuth(this)" class="w-full mt-2 py-2.5 rounded-xl text-sm font-bold bg-orange-600 hover:bg-orange-500 text-white transition flex justify-center items-center gap-2">
                        <span>ذخیره و تست اتصال</span>
                    </button>'''

new_html = '''                    <div class="flex gap-2 mt-2">
                        <button type="button" onclick="saveQuickFeedAuth(this)" class="flex-1 py-2 rounded-xl text-sm font-bold bg-orange-600 hover:bg-orange-500 text-white transition flex justify-center items-center gap-1.5">
                            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4"></path></svg>
                            <span>ذخیره نشست</span>
                        </button>
                        <button type="button" onclick="testCrawlerConnection(this)" class="flex-1 py-2 rounded-xl text-sm font-bold bg-slate-700 hover:bg-slate-600 text-white transition flex justify-center items-center gap-1.5" style="background: var(--button-bg, #334155);">
                            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
                            <span>تست اتصال</span>
                        </button>
                    </div>'''

if old_html in text:
    text = text.replace(old_html, new_html)
    open(filepath, 'w', encoding='utf-8').write(text)
    print("Replaced HTML buttons successfully.")
else:
    print("HTML pattern not found!")
