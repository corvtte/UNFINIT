import sys; sys.stdout.reconfigure(encoding='utf-8')
lines = open('services/web_panel.py', encoding='utf-8').read()

old_btns = """                    <div class="flex flex-col gap-2 mt-2">
                        <button type="button" onclick="saveQuickFeedAuth(this)" class="w-full py-2 rounded-xl text-[13px] font-bold bg-slate-700 hover:bg-slate-600 text-slate-300 transition flex justify-center items-center gap-1.5" style="background: var(--button-bg, #334155);">
                            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4"></path></svg>
                            <span>ذخیره دستی فرم در فایل Settings</span>
                        </button>
                        <div class="flex gap-2">
                            <button type="button" onclick="loginAndTestConnection(this)" class="flex-1 py-2 rounded-xl text-[13px] font-bold bg-emerald-600 hover:bg-emerald-500 text-white transition flex justify-center items-center gap-1.5">
                                <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 16l-4-4m0 0l4-4m-4 4h14m-5 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h7a3 3 0 013 3v1"></path></svg>
                                <span>ورود به حساب مرجع</span>
                            </button>
                            <button type="button" onclick="logoutCrawlerConnection(this)" class="flex-1 py-2 rounded-xl text-[13px] font-bold bg-rose-600 hover:bg-rose-500 text-white transition flex justify-center items-center gap-1.5">
                                <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"></path></svg>
                                <span>خروج از حساب</span>
                            </button>
                        </div>
                    </div>"""

new_btns = """                    <div class="flex flex-col gap-2 mt-2">
                        <button type="button" onclick="saveQuickFeedAuth(this)" class="w-full py-2 rounded-xl text-[13px] font-bold bg-slate-700 hover:bg-slate-600 text-slate-300 transition flex justify-center items-center gap-1.5" style="background: var(--button-bg, #334155);">
                            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4"></path></svg>
                            <span>ذخیره دستی فرم در فایل Settings</span>
                        </button>
                        <div class="flex gap-2">
                            <button type="button" id="btn_toggle_login_logout" onclick="toggleCrawlerAuth(this)" class="flex-1 py-2 rounded-xl text-[13px] font-bold bg-emerald-600 hover:bg-emerald-500 text-white transition flex justify-center items-center gap-1.5">
                                <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 16l-4-4m0 0l4-4m-4 4h14m-5 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h7a3 3 0 013 3v1"></path></svg>
                                <span>ورود به حساب مرجع</span>
                            </button>
                            <button type="button" onclick="testCrawlerConnection(this)" class="flex-1 py-2 rounded-xl text-[13px] font-bold bg-indigo-600 hover:bg-indigo-500 text-white transition flex justify-center items-center gap-1.5">
                                <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                                <span>تست و بررسی اتصال</span>
                            </button>
                        </div>
                    </div>"""

if old_btns in lines:
    lines = lines.replace(old_btns, new_btns)
    open('services/web_panel.py', 'w', encoding='utf-8').write(lines)
    print("Replaced HTML buttons successfully!")
else:
    print("Could not find old HTML buttons!")
