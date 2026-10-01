import re

p_file = 'services/web_panel.py'
text = open(p_file, encoding='utf-8').read()

# Replace saveQuickFeedAuth
new_save_quick = """                                                window.saveQuickFeedAuth = async function(btn) {{
                    const orig = btn.innerHTML;
                    btn.innerHTML = 'در حال بررسی...';
                    btn.disabled = true;
                    const resDiv = document.getElementById('quickFeedAuthResult');
                    if (resDiv) resDiv.classList.add('hidden');
                    try {{
                        const cookie = document.getElementById('quick_FEED_AUTH_COOKIE').value;
                        const email = document.getElementById('quick_FEED_AUTH_EMAIL').value;
                        const pass = document.getElementById('quick_FEED_AUTH_PASSWORD').value;
                        
                        const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                        
                        const res = await fetch('/api/crawler/save-auth', {{
                            method: 'POST',
                            headers: {{
                                'Content-Type': 'application/json',
                                'Authorization': 'Bearer ' + pwd,
                                'X-Admin-Password': pwd
                            }},
                            body: JSON.stringify({{ cookie: cookie, email: email, password: pass }})
                        }});
                        
                        const data = await res.json();
                        
                        if (data.success) {{
                            showToast('✅ ' + (data.message || 'ورود موفقیت‌آمیز بود و نشست معتبر دریافت شد.'), 'success');
                            if (window.closeFeedAuthModal) window.closeFeedAuthModal();
                            const b = document.getElementById('crawlerStatusBadge');
                            if (b) {{
                                b.className = 'px-2 py-1 rounded text-xs bg-emerald-950 text-emerald-400 border border-emerald-800 flex items-center gap-1.5 shadow-sm';
                                b.innerHTML = '<span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span> نشست فعال (ONLINE)';
                            }}
                        }} else {{
                            if (resDiv) {{
                                resDiv.classList.remove('hidden');
                                resDiv.innerHTML = '<span class="text-rose-500 font-bold">❌ خطا:</span> ' + (data.message || 'مشکلی رخ داد.');
                            }}
                            showToast('خطا در ذخیره نشست', 'error');
                        }}
                    }} catch (err) {{
                        console.error(err);
                        showToast('خطای شبکه در ارتباط با سرور', 'error');
                    }} finally {{
                        btn.innerHTML = orig;
                        btn.disabled = false;
                    }}
                }};"""

text = re.sub(r'window\.saveQuickFeedAuth = async function\(btn\) \{\{.*?\n                \}\};', new_save_quick, text, flags=re.DOTALL)

# Replace showToast for deduplication
new_toast = """        window.showToast = function(msg, type='info') {{
            const container = document.getElementById('toast-container') || (function() {{
                const c = document.createElement('div');
                c.id = 'toast-container';
                c.className = 'fixed bottom-4 right-4 z-[9999] flex flex-col gap-2';
                document.body.appendChild(c);
                return c;
            }})();
            
            const cleanMsg = msg.replace(/^[❌✅]/, '').trim();
            for (const el of container.children) {{
                if (el.dataset.msg === cleanMsg) {{
                    clearTimeout(el.toastTimer);
                    el.toastTimer = setTimeout(() => {{
                        el.classList.add('translate-x-full', 'opacity-0');
                        setTimeout(() => el.remove(), 300);
                    }}, 3500);
                    return;
                }}
            }}
            
            const t = document.createElement('div');
            t.dataset.msg = cleanMsg;
            const isErr = type === 'error' || msg.includes('❌') || msg.includes('خطا');
            const isOk = type === 'success' || msg.includes('✅') || msg.includes('موفق');
            const bg = isErr ? 'bg-rose-950/90 border-rose-800 text-rose-200' : (isOk ? 'bg-emerald-950/90 border-emerald-800 text-emerald-200' : 'bg-slate-800/90 border-slate-700 text-slate-200');
            const icon = isErr ? '<svg class="w-5 h-5 text-rose-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>' : 
                         (isOk ? '<svg class="w-5 h-5 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>' : 
                         '<svg class="w-5 h-5 text-sky-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>');
            t.className = `flex items-center gap-3 px-4 py-3 rounded-xl border backdrop-blur-md shadow-lg transform transition-all duration-300 translate-x-full opacity-0 ${{bg}}`;
            t.innerHTML = `${{icon}} <span class="text-sm font-bold font-sans" style="font-family: 'IRANSans', 'Vazirmatn', sans-serif;">${{cleanMsg}}</span>`;
            container.appendChild(t);
            requestAnimationFrame(() => {{
                t.classList.remove('translate-x-full', 'opacity-0');
            }});
            t.toastTimer = setTimeout(() => {{
                t.classList.add('translate-x-full', 'opacity-0');
                setTimeout(() => t.remove(), 300);
            }}, 3500);
        }};"""

text = re.sub(r'window\.showToast = function.*?\}\};', new_toast, text, flags=re.DOTALL)

# Add SVG clear button for cookie textarea
cookie_html = """<div class="relative">
                        <textarea id="quick_FEED_AUTH_COOKIE" dir="ltr" rows="2" class="w-full rounded-xl px-4 py-2.5 pr-10 text-xs font-mono transition focus:outline-none" style="background: var(--input-bg); border: 1px solid var(--border-color); color: var(--text-color);" placeholder="session_cookie=..."></textarea>
                        <button type="button" onclick="document.getElementById('quick_FEED_AUTH_COOKIE').value=''" class="absolute right-2 top-2 p-1.5 text-slate-400 hover:text-rose-400 transition" title="پاک کردن کوکی">
                            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
                        </button>
                    </div>"""
text = text.replace('<textarea id="quick_FEED_AUTH_COOKIE" dir="ltr" rows="2" class="w-full rounded-xl px-4 py-2.5 text-xs font-mono transition focus:outline-none" style="background: var(--input-bg); border-color: var(--border-color); color: var(--text-color);" placeholder="session_cookie=..."></textarea>', cookie_html)

open(p_file, 'w', encoding='utf-8').write(text)
