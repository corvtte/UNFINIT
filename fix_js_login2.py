import sys
lines = open('services/web_panel.py', encoding='utf-8').read()

bad_js = """                window.loginAndTestConnection = async function(btn) {
                    const origHtml = btn.innerHTML;
                    btn.disabled = true;
                    btn.innerHTML = '<span class="flex items-center gap-2"><svg class="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg> در حال ورود...</span>';
                    try {
                        const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                        const payload = {
                            cookie: document.getElementById('quick_FEED_AUTH_COOKIE').value,
                            email: document.getElementById('quick_FEED_AUTH_EMAIL').value,
                            password: document.getElementById('quick_FEED_AUTH_PASSWORD').value
                        };
                        const saveRes = await fetch('/api/crawler/save-auth', { method: 'POST', headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + pwd }, body: JSON.stringify(payload) });
                        const saveData = await saveRes.json();
                        
                        if (saveData.success) {
                            const res = await fetch('/api/crawler/test-auth', { method: 'POST', body: '{}' });
                            const data = await res.json();
                            const resDiv = document.getElementById('quickFeedAuthResult');
                            if (resDiv) {
                                resDiv.classList.remove('hidden');
                                if (data.success) {
                                    resDiv.innerHTML = '<span class="text-emerald-500 font-bold">✅ ورود موفق:</span> ' + data.message;
                                    showToast('✅ ورود موفقیت‌آمیز بود');
                                    const b = document.getElementById('crawlerStatusBadge');
                                    if (b) {
                                        b.className = 'text-[10px] px-2 py-0.5 rounded-full bg-emerald-600 text-white shadow-sm';
                                        b.innerText = 'متصل به حساب مرجع (ONLINE)';
                                    }
                                } else {
                                    resDiv.innerHTML = '<span class="text-rose-500 font-bold">❌ ورود ناموفق:</span> ' + (data.message || data.error || 'بررسی کنید.');
                                    showToast('❌ ' + data.message, 'error');
                                }
                            }
                        } else {
                            showToast('خطا در ذخیره فرم', 'error');
                        }
                    } catch (e) {
                        showToast('❌ خطای شبکه: ' + e.message, 'error');
                    } finally {
                        btn.innerHTML = origHtml;
                        btn.disabled = false;
                    }
                };"""

good_js = """                window.loginAndTestConnection = async function(btn) {{
                    const origHtml = btn.innerHTML;
                    btn.disabled = true;
                    btn.innerHTML = '<span class="flex items-center gap-2"><svg class="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg> در حال ورود...</span>';
                    try {{
                        const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                        const payload = {{
                            cookie: document.getElementById('quick_FEED_AUTH_COOKIE').value,
                            email: document.getElementById('quick_FEED_AUTH_EMAIL').value,
                            password: document.getElementById('quick_FEED_AUTH_PASSWORD').value
                        }};
                        const saveRes = await fetch('/api/crawler/save-auth', {{ method: 'POST', headers: {{ 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + pwd }}, body: JSON.stringify(payload) }});
                        const saveData = await saveRes.json();
                        
                        if (saveData.success) {{
                            const res = await fetch('/api/crawler/test-auth', {{ method: 'POST', body: '{{}}' }});
                            const data = await res.json();
                            const resDiv = document.getElementById('quickFeedAuthResult');
                            if (resDiv) {{
                                resDiv.classList.remove('hidden');
                                if (data.success) {{
                                    resDiv.innerHTML = '<span class="text-emerald-500 font-bold">✅ ورود موفق:</span> ' + data.message;
                                    showToast('✅ ورود موفقیت‌آمیز بود');
                                    const b = document.getElementById('crawlerStatusBadge');
                                    if (b) {{
                                        b.className = 'text-[10px] px-2 py-0.5 rounded-full bg-emerald-600 text-white shadow-sm';
                                        b.innerText = 'متصل به حساب مرجع (ONLINE)';
                                    }}
                                }} else {{
                                    resDiv.innerHTML = '<span class="text-rose-500 font-bold">❌ ورود ناموفق:</span> ' + (data.message || data.error || 'بررسی کنید.');
                                    showToast('❌ ' + data.message, 'error');
                                }}
                            }}
                        }} else {{
                            showToast('خطا در ذخیره فرم', 'error');
                        }}
                    }} catch (e) {{
                        showToast('❌ خطای شبکه: ' + e.message, 'error');
                    }} finally {{
                        btn.innerHTML = origHtml;
                        btn.disabled = false;
                    }}
                }};"""

if bad_js in lines:
    lines = lines.replace(bad_js, good_js)
    open('services/web_panel.py', 'w', encoding='utf-8').write(lines)
    print('JS fixed!')
else:
    print('JS anchor not found!')
