import sys
lines = open('services/web_panel.py', encoding='utf-8').read()

idx1 = lines.find('window.loginAndTestConnection = async function(btn) {{')
idx2 = lines.find('        window.openBaleBuyModal = openBaleBuyModal;')

if idx1 != -1 and idx2 != -1:
    old_js = lines[idx1:idx2]
    
    new_js = """window.toggleCrawlerAuth = async function(btn) {{
                    const origHtml = btn.innerHTML;
                    const isLogout = origHtml.includes('خروج از حساب');
                    btn.disabled = true;
                    btn.innerHTML = '<span class="flex items-center gap-2"><svg class="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg> لطفا کمی صبر کنید...</span>';
                    
                    try {{
                        if (isLogout) {{
                            const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                            const res = await fetch('/api/crawler/logout', {{ method: 'POST', body: '{}', headers: {{'Authorization': 'Bearer ' + pwd}} }});
                            const data = await res.json();
                            showToast('✅ خروج از حساب مرجع با موفقیت انجام شد.');
                            btn.className = 'flex-1 py-2 rounded-xl text-[13px] font-bold bg-emerald-600 hover:bg-emerald-500 text-white transition flex justify-center items-center gap-1.5';
                            btn.innerHTML = '<svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 16l-4-4m0 0l4-4m-4 4h14m-5 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h7a3 3 0 013 3v1"></path></svg><span>ورود به حساب مرجع</span>';
                            const b = document.getElementById('crawlerStatusBadge');
                            if (b) {{
                                b.className = 'text-[10px] px-2 py-0.5 rounded-full bg-rose-600 text-white shadow-sm';
                                b.innerText = 'نشست مرجع قطع است (OFFLINE)';
                            }}
                            const resDiv = document.getElementById('quickFeedAuthResult');
                            if (resDiv) resDiv.classList.add('hidden');
                        }} else {{
                            const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                            const payload = {{
                                cookie: document.getElementById('quick_FEED_AUTH_COOKIE').value,
                                email: document.getElementById('quick_FEED_AUTH_EMAIL').value,
                                password: document.getElementById('quick_FEED_AUTH_PASSWORD').value
                            }};
                            const saveRes = await fetch('/api/crawler/save-auth', {{ method: 'POST', headers: {{ 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + pwd }}, body: JSON.stringify(payload) }});
                            const saveData = await saveRes.json();
                            
                            if (saveData.success) {{
                                const res = await fetch('/api/crawler/test-auth', {{ method: 'POST', body: '{}', headers: {{'Authorization': 'Bearer ' + pwd}} }});
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
                                        btn.className = 'flex-1 py-2 rounded-xl text-[13px] font-bold bg-rose-600 hover:bg-rose-500 text-white transition flex justify-center items-center gap-1.5';
                                        btn.innerHTML = '<svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"></path></svg><span>خروج از حساب</span>';
                                    }} else {{
                                        resDiv.innerHTML = '<span class="text-rose-500 font-bold">❌ ورود ناموفق:</span> ' + (data.message || data.error || 'بررسی کنید.');
                                        showToast('❌ ' + data.message, 'error');
                                        btn.innerHTML = origHtml;
                                    }}
                                }}
                            }} else {{
                                showToast('خطا در ذخیره فرم', 'error');
                                btn.innerHTML = origHtml;
                            }}
                        }}
                    }} catch (e) {{
                        showToast('❌ خطای شبکه: ' + e.message, 'error');
                        btn.innerHTML = origHtml;
                    }} finally {{
                        btn.disabled = false;
                    }}
                }};
                
                window.testCrawlerConnection = async function(btn) {{
                    const origHtml = btn.innerHTML;
                    btn.disabled = true;
                    btn.innerHTML = '<span class="flex items-center gap-2"><svg class="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg> در حال بررسی...</span>';
                    try {{
                        const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                        const res = await fetch('/api/crawler/test-auth', {{ method: 'POST', body: '{}', headers: {{'Authorization': 'Bearer ' + pwd}} }});
                        const data = await res.json();
                        
                        const resDiv = document.getElementById('quickFeedAuthResult');
                        const toggleBtn = document.getElementById('btn_toggle_login_logout');
                        if (resDiv) resDiv.classList.remove('hidden');
                        
                        if (data.success) {{
                            showToast('✅ ' + data.message);
                            if (resDiv) resDiv.innerHTML = '<span class="text-emerald-500 font-bold">✅ وضعیت:</span> ' + data.message;
                            const b = document.getElementById('crawlerStatusBadge');
                            if (b) {{
                                b.className = 'text-[10px] px-2 py-0.5 rounded-full bg-emerald-600 text-white shadow-sm';
                                b.innerText = 'متصل به حساب مرجع (ONLINE)';
                            }}
                            if (toggleBtn) {{
                                toggleBtn.className = 'flex-1 py-2 rounded-xl text-[13px] font-bold bg-rose-600 hover:bg-rose-500 text-white transition flex justify-center items-center gap-1.5';
                                toggleBtn.innerHTML = '<svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"></path></svg><span>خروج از حساب</span>';
                            }}
                        }} else {{
                            showToast('❌ ' + data.message, 'error');
                            if (resDiv) resDiv.innerHTML = '<span class="text-rose-500 font-bold">❌ خطا:</span> ' + data.message;
                            const b = document.getElementById('crawlerStatusBadge');
                            if (b) {{
                                b.className = 'text-[10px] px-2 py-0.5 rounded-full bg-rose-600 text-white shadow-sm';
                                b.innerText = 'نشست مرجع قطع است (OFFLINE)';
                            }}
                            if (toggleBtn) {{
                                toggleBtn.className = 'flex-1 py-2 rounded-xl text-[13px] font-bold bg-emerald-600 hover:bg-emerald-500 text-white transition flex justify-center items-center gap-1.5';
                                toggleBtn.innerHTML = '<svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 16l-4-4m0 0l4-4m-4 4h14m-5 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h7a3 3 0 013 3v1"></path></svg><span>ورود به حساب مرجع</span>';
                            }}
                        }}
                    }} catch (e) {{
                        showToast('❌ خطای شبکه: ' + e.message, 'error');
                    }} finally {{
                        btn.innerHTML = origHtml;
                        btn.disabled = false;
                    }}
                }};
                
"""
    lines = lines.replace(old_js, new_js)
    open('services/web_panel.py', 'w', encoding='utf-8').write(lines)
    print("JS updated successfully!")
else:
    print("Failed to find JS blocks!")
