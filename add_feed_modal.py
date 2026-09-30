import os

p = 'services/web_panel.py'
text = open(p, encoding='utf-8').read()

modal_html = '''
        <!-- Feed Auth Quick Connect Modal -->
        <div id="feedAuthModal" class="hidden fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
            <div class="glass-card max-w-sm w-full p-6 rounded-2xl border shadow-2xl relative space-y-4" style="background: var(--card-bg, #1e293b); border-color: var(--card-border, #334155);">
                <div class="flex items-center justify-between border-b border-slate-700/60 pb-3">
                    <h3 class="text-sm font-bold text-white flex items-center gap-2">
                        <svg class="w-4 h-4 text-orange-400 stroke-[1.75]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M15.75 5.25a3 3 0 013 3m3 0a6 6 0 01-7.029 5.912c-.563-.097-1.159.026-1.563.43L10.5 17.25H8.25v2.25H6v2.25H2.25v-2.818c0-.597.237-1.17.659-1.591l6.499-6.499c.404-.404.527-1 .43-1.563A6 6 0 1121.75 8.25z" /></svg>
                        <span>تنظیم و تست اتصال منبع</span>
                    </h3>
                    <button onclick="closeFeedAuthModal()" class="text-slate-400 hover:text-white transition">
                        <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
                    </button>
                </div>
                <div class="space-y-3">
                    <div>
                        <label class="text-slate-300 font-medium text-xs mb-1.5 block">ایمیل ورود</label>
                        <input type="text" id="quick_FEED_AUTH_EMAIL" placeholder="user@example.com" class="w-full rounded-xl px-3 py-2 text-xs font-mono focus:outline-none focus:border-orange-500 transition" style="background: var(--input-bg); border-color: var(--border-color); color: var(--text-color);" dir="ltr">
                    </div>
                    <div class="relative">
                        <label class="text-slate-300 font-medium text-xs mb-1.5 block">رمز عبور</label>
                        <input type="password" id="quick_FEED_AUTH_PASSWORD" class="w-full rounded-xl px-3 py-2 text-xs font-mono focus:outline-none focus:border-orange-500 transition" style="background: var(--input-bg); border-color: var(--border-color); color: var(--text-color);" dir="ltr">
                    </div>
                </div>
                <div class="pt-2 flex flex-col gap-2">
                    <button type="button" onclick="saveQuickFeedAuth(this)" class="w-full py-2 px-4 rounded-xl bg-orange-700 hover:bg-orange-600 text-white text-xs font-bold transition flex items-center justify-center gap-2 shadow-sm">
                        <span>ذخیره و تست اتصال</span>
                    </button>
                </div>
            </div>
        </div>
'''

if 'feedAuthModal' not in text:
    text = text.replace('<!-- Feed Dispatch Format Selection Modal -->', modal_html + '\n        <!-- Feed Dispatch Format Selection Modal -->')

js_code = '''
        window.openFeedAuthModal = function() {
            const m = document.getElementById('feedAuthModal');
            if (m) {
                document.getElementById('quick_FEED_AUTH_EMAIL').value = document.getElementById('cfg_FEED_AUTH_EMAIL')?.value || '';
                document.getElementById('quick_FEED_AUTH_PASSWORD').value = document.getElementById('cfg_FEED_AUTH_PASSWORD')?.value || '';
                m.classList.remove('hidden');
            }
        };
        window.closeFeedAuthModal = function() {
            const m = document.getElementById('feedAuthModal');
            if (m) m.classList.add('hidden');
        };
        window.saveQuickFeedAuth = async function(btn) {
            const orig = btn.innerHTML;
            btn.innerHTML = 'در حال بررسی...';
            btn.disabled = true;
            try {
                const email = document.getElementById('quick_FEED_AUTH_EMAIL').value;
                const pass = document.getElementById('quick_FEED_AUTH_PASSWORD').value;
                const cfgE = document.getElementById('cfg_FEED_AUTH_EMAIL');
                const cfgP = document.getElementById('cfg_FEED_AUTH_PASSWORD');
                if (cfgE) cfgE.value = email;
                if (cfgP) cfgP.value = pass;
                
                const btnSave = document.getElementById('btnSaveSettings');
                if (btnSave && window.saveSettings) {
                    await window.saveSettings(btnSave);
                }
                
                const res = await fetch('/api/crawler/test-auth', { method: 'POST', body: '{}' });
                const data = await res.json();
                if (data.success) {
                    alert('✅ ' + data.message);
                    window.closeFeedAuthModal();
                } else {
                    alert('❌ ' + data.message);
                }
            } catch (e) {
                alert('❌ خطای شبکه');
            } finally {
                btn.innerHTML = orig;
                btn.disabled = false;
            }
        };
'''

if 'saveQuickFeedAuth' not in text:
    text = text.replace('window.openFeedDispatchModal = openFeedDispatchModal;', js_code + '\n                window.openFeedDispatchModal = openFeedDispatchModal;')

open(p, 'w', encoding='utf-8').write(text)
