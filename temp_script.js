
                window.showToast = function(msg, type='info') {{
            const container = document.getElementById('toast-container') || (function() {{
                const c = document.createElement('div');
                c.id = 'toast-container';
                c.className = 'fixed bottom-4 right-4 z-[9999] flex flex-col gap-2';
                document.body.appendChild(c);
                return c;
            }})();
            
            const cleanMsg = msg.replace(/^[âŒâœ…]/, '').trim();
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
            const isErr = type === 'error' || msg.includes('âŒ') || msg.includes('Ø®Ø·Ø§');
            const isOk = type === 'success' || msg.includes('âœ…') || msg.includes('Ù…ÙˆÙÙ‚');
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
        }};

        window.COURSES_CACHE = {courses_data_json};
        window.coursesData = window.COURSES_CACHE;

        // Global Auth & State Access
        window.currentAdminPassword = window.currentAdminPassword || sessionStorage.getItem('unfinit_admin_pwd') || localStorage.getItem('unfinit_admin_pwd') || '';

        // =========================================================================
        // MODULE 1: NAVIGATION & TAB SWITCHING (Sandboxed IIFE)
        // =========================================================================
        (function initNavModule() {{
            try {{
                function updateCharCounter(inputId, counterId, maxLen) {{
                    const input = document.getElementById(inputId);
                    const counter = document.getElementById(counterId);
                    if (!input || !counter) return;
                    const len = input.value.length;
                    if (len > maxLen) {{
                        const diff = maxLen - len;
                        counter.innerText = diff + ' (Ø¨ÛŒØ´ Ø§Ø² Ø³Ù‚Ù Ù…Ø¬Ø§Ø² ÙØ§Ú©ØªÙˆØ± Ø¨Ù„Ù‡)';
                        counter.className = 'text-[11px] font-mono text-rose-500 font-bold';
                    }} else if (len === maxLen) {{
                        counter.innerText = len + ' / ' + maxLen;
                        counter.className = 'text-[11px] font-mono text-rose-400 font-bold';
                    }} else if (len >= maxLen * 0.85) {{
                        counter.innerText = len + ' / ' + maxLen;
                        counter.className = 'text-[11px] font-mono text-amber-400 font-bold';
                    }} else {{
                        counter.innerText = len + ' / ' + maxLen;
                        counter.className = 'text-[11px] font-mono text-slate-400';
                    }}
                }}
                window.updateCharCounter = updateCharCounter;

                async function testCrawlerConnection(btn) {{
                    const origHtml = btn.innerHTML;
                    btn.disabled = true;
                    btn.innerHTML = '<span class="flex items-center gap-2"><svg class="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg> Ø¯Ø± Ø­Ø§Ù„ Ø¨Ø±Ø±Ø³ÛŒ...</span>';
                    try {{
                        const res = await fetch('/api/crawler/test-auth', {{ method: 'POST', body: '{{}}' }});
                        const data = await res.json();
                        if (data.success) {{
                            showToast('âœ… ' + data.message);
                        }} else {{
                            showToast('âŒ ' + data.message);
                        }}
                    }} catch (e) {{
                        showToast('âŒ Ø®Ø·Ø§ÛŒ Ø´Ø¨Ú©Ù‡: ' + e.message);
                    }} finally {{
                        btn.disabled = false;
                        btn.innerHTML = origHtml;
                    }}
                }}

                function togglePasswordVisibility(inputId, btn) {{
                    const inp = document.getElementById(inputId);
                    if (!inp) return;
                    const isMasked = (inp.type === 'password' || inp.style.webkitTextSecurity === 'disc');
                    const iconEye = '<svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/><path stroke-linecap="round" stroke-linejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/></svg>';
                    const iconEyeOff = '<svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21"/></svg>';
                    if (isMasked) {{
                        inp.type = 'text';
                        inp.style.webkitTextSecurity = 'none';
                        btn.innerHTML = iconEyeOff;
                    }} else {{
                        if (inp.hasAttribute('data-token-field')) {{
                            inp.type = 'text';
                            inp.style.webkitTextSecurity = 'disc';
                        }} else {{
                            inp.type = 'password';
                        }}
                        btn.innerHTML = iconEye;
                    }}
                }}
                window.togglePasswordVisibility = togglePasswordVisibility;

                                window.openFeedAuthModal = function() {{
                    const m = document.getElementById('feedAuthModal');
                    if (m) {{
                        const ck = document.getElementById('quick_FEED_AUTH_COOKIE');
                        const em = document.getElementById('quick_FEED_AUTH_EMAIL');
                        const pw = document.getElementById('quick_FEED_AUTH_PASSWORD');
                        const cc = document.getElementById('cfg_FEED_AUTH_COOKIE');
                        const ce = document.getElementById('cfg_FEED_AUTH_EMAIL');
                        const cp = document.getElementById('cfg_FEED_AUTH_PASSWORD');
                        if (ck && cc) ck.value = cc.value || '';
                        if (em && ce) em.value = ce.value || '';
                        if (pw && cp) pw.value = cp.value || '';
                        
                        const resDiv = document.getElementById('quickFeedAuthResult');
                        if (resDiv) resDiv.classList.add('hidden');
                        
                        m.classList.remove('hidden');
                    }}
                }};

                window.closeFeedAuthModal = function() {{
                    const m = document.getElementById('feedAuthModal');
                    if (m) m.classList.add('hidden');
                }};

                                                                                                window.saveQuickFeedAuth = async function(btn) {{
                    const orig = btn.innerHTML;
                    btn.innerHTML = 'Ø¯Ø± Ø­Ø§Ù„ Ø¨Ø±Ø±Ø³ÛŒ...';
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
                            showToast('âœ… ' + (data.message || 'ÙˆØ±ÙˆØ¯ Ù…ÙˆÙÙ‚ÛŒØªâ€ŒØ¢Ù…ÛŒØ² Ø¨ÙˆØ¯ Ùˆ Ù†Ø´Ø³Øª Ù…Ø¹ØªØ¨Ø± Ø¯Ø±ÛŒØ§ÙØª Ø´Ø¯.'), 'success');
                            if (window.closeFeedAuthModal) window.closeFeedAuthModal();
                            const b = document.getElementById('crawlerStatusBadge');
                            if (b) {{
                                b.className = 'px-2 py-1 rounded text-xs bg-emerald-950 text-emerald-400 border border-emerald-800 flex items-center gap-1.5 shadow-sm';
                                b.innerHTML = '<span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span> Ù†Ø´Ø³Øª ÙØ¹Ø§Ù„ (ONLINE)';
                            }}
                        }} else {{
                            if (resDiv) {{
                                resDiv.classList.remove('hidden');
                                resDiv.innerHTML = '<span class="text-rose-500 font-bold">âŒ Ø®Ø·Ø§:</span> ' + (data.message || data.error || 'Ù…Ø´Ú©Ù„ÛŒ Ø±Ø® Ø¯Ø§Ø¯.');
                            }}
                            showToast('Ø®Ø·Ø§ Ø¯Ø± Ø°Ø®ÛŒØ±Ù‡ Ù†Ø´Ø³Øª', 'error');
                        }}
                    }} catch (err) {{
                        console.error(err);
                        showToast('Ø®Ø·Ø§ÛŒ Ø´Ø¨Ú©Ù‡ Ø¯Ø± Ø§Ø±ØªØ¨Ø§Ø· Ø¨Ø§ Ø³Ø±ÙˆØ±', 'error');
                    }} finally {{
                        btn.innerHTML = orig;
                        btn.disabled = false;
                    }}
                }};

                                                window.toggleCrawlerAuth = async function(btn) {{
                    const origHtml = btn.innerHTML;
                    const isLogout = origHtml.includes('Ø®Ø±ÙˆØ¬ Ø§Ø² Ø­Ø³Ø§Ø¨');
                    btn.disabled = true;
                    btn.innerHTML = '<span class="flex items-center gap-2"><svg class="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg> Ù„Ø·ÙØ§ Ú©Ù…ÛŒ ØµØ¨Ø± Ú©Ù†ÛŒØ¯...</span>';
                    
                    try {{
                        if (isLogout) {{
                            const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                            const res = await fetch('/api/crawler/logout', {{ method: 'POST', body: '{{}}', headers: {{'Authorization': 'Bearer ' + pwd}} }});
                            const data = await res.json();
                            showToast('âœ… Ø®Ø±ÙˆØ¬ Ø§Ø² Ø­Ø³Ø§Ø¨ Ù…Ø±Ø¬Ø¹ Ø¨Ø§ Ù…ÙˆÙÙ‚ÛŒØª Ø§Ù†Ø¬Ø§Ù… Ø´Ø¯.');
                            btn.className = 'flex-1 py-2 rounded-xl text-[13px] font-bold bg-emerald-600 hover:bg-emerald-500 text-white transition flex justify-center items-center gap-1.5';
                            btn.innerHTML = '<svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 16l-4-4m0 0l4-4m-4 4h14m-5 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h7a3 3 0 013 3v1"></path></svg><span>ÙˆØ±ÙˆØ¯ Ø¨Ù‡ Ø­Ø³Ø§Ø¨ Ù…Ø±Ø¬Ø¹</span>';
                            const b = document.getElementById('crawlerStatusBadge');
                            if (b) {{
                                b.className = 'text-[10px] px-2 py-0.5 rounded-full bg-rose-600 text-white shadow-sm';
                                b.innerText = 'Ù†Ø´Ø³Øª Ù…Ø±Ø¬Ø¹ Ù‚Ø·Ø¹ Ø§Ø³Øª (OFFLINE)';
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
                                const res = await fetch('/api/crawler/test-auth', {{ method: 'POST', body: JSON.stringify({{force_login: true}}), headers: {{'Content-Type': 'application/json', 'Authorization': 'Bearer ' + pwd}} }});
                                const data = await res.json();
                                if (data.cookie) {{
                                    document.getElementById('quick_FEED_AUTH_COOKIE').value = data.cookie;
                                    
                                    await fetch('/api/crawler/save-auth', {{ 
                                        method: 'POST', 
                                        headers: {{ 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + pwd }}, 
                                        body: JSON.stringify({{cookie: data.cookie, email: document.getElementById('quick_FEED_AUTH_EMAIL').value, password: document.getElementById('quick_FEED_AUTH_PASSWORD').value}}) 
                                    }});
                                }}
                                const resDiv = document.getElementById('quickFeedAuthResult');
                                if (resDiv) {{
                                    resDiv.classList.remove('hidden');
                                    if (data.success) {{
                                        resDiv.innerHTML = '<span class="text-emerald-500 font-bold">âœ… ÙˆØ±ÙˆØ¯ Ù…ÙˆÙÙ‚:</span> ' + data.message;
                                        showToast('âœ… ÙˆØ±ÙˆØ¯ Ù…ÙˆÙÙ‚ÛŒØªâ€ŒØ¢Ù…ÛŒØ² Ø¨ÙˆØ¯');
                                        const b = document.getElementById('crawlerStatusBadge');
                                        if (b) {{
                                            b.className = 'text-[10px] px-2 py-0.5 rounded-full bg-emerald-600 text-white shadow-sm';
                                            b.innerText = 'Ù…ØªØµÙ„ Ø¨Ù‡ Ø­Ø³Ø§Ø¨ Ù…Ø±Ø¬Ø¹ (ONLINE)';
                                        }}
                                        btn.className = 'flex-1 py-2 rounded-xl text-[13px] font-bold bg-rose-600 hover:bg-rose-500 text-white transition flex justify-center items-center gap-1.5';
                                        btn.innerHTML = '<svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"></path></svg><span>Ø®Ø±ÙˆØ¬ Ø§Ø² Ø­Ø³Ø§Ø¨</span>';
                                    }} else {{
                                        resDiv.innerHTML = '<span class="text-rose-500 font-bold">âŒ ÙˆØ±ÙˆØ¯ Ù†Ø§Ù…ÙˆÙÙ‚:</span> ' + (data.message || data.error || 'Ø¨Ø±Ø±Ø³ÛŒ Ú©Ù†ÛŒØ¯.');
                                        showToast('âŒ ' + data.message, 'error');
                                        btn.innerHTML = origHtml;
                                    }}
                                }}
                            }} else {{
                                showToast('Ø®Ø·Ø§ Ø¯Ø± Ø°Ø®ÛŒØ±Ù‡ ÙØ±Ù…', 'error');
                                btn.innerHTML = origHtml;
                            }}
                        }}
                    }} catch (e) {{
                        showToast('âŒ Ø®Ø·Ø§ÛŒ Ø´Ø¨Ú©Ù‡: ' + e.message, 'error');
                        btn.innerHTML = origHtml;
                    }} finally {{
                        btn.disabled = false;
                    }}
                }};
                
                window.testCrawlerConnection = async function(btn) {{
                    const origHtml = btn.innerHTML;
                    btn.disabled = true;
                    btn.innerHTML = '<span class="flex items-center gap-2"><svg class="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg> Ø¯Ø± Ø­Ø§Ù„ Ø¨Ø±Ø±Ø³ÛŒ...</span>';
                    try {{
                        const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                        const res = await fetch('/api/crawler/test-auth', {{ method: 'POST', body: JSON.stringify({{force_login: true}}), headers: {{'Content-Type': 'application/json', 'Authorization': 'Bearer ' + pwd}} }});
                                const data = await res.json();
                                if (data.cookie) {{
                                    document.getElementById('quick_FEED_AUTH_COOKIE').value = data.cookie;
                                    
                                    await fetch('/api/crawler/save-auth', {{ 
                                        method: 'POST', 
                                        headers: {{ 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + pwd }}, 
                                        body: JSON.stringify({{cookie: data.cookie, email: document.getElementById('quick_FEED_AUTH_EMAIL').value, password: document.getElementById('quick_FEED_AUTH_PASSWORD').value}}) 
                                    }});
                                }}
                        
                        const resDiv = document.getElementById('quickFeedAuthResult');
                        const toggleBtn = document.getElementById('btn_toggle_login_logout');
                        if (resDiv) resDiv.classList.remove('hidden');
                        
                        if (data.success) {{
                            showToast('âœ… ' + data.message);
                            if (resDiv) resDiv.innerHTML = '<span class="text-emerald-500 font-bold">âœ… ÙˆØ¶Ø¹ÛŒØª:</span> ' + data.message;
                            const b = document.getElementById('crawlerStatusBadge');
                            if (b) {{
                                b.className = 'text-[10px] px-2 py-0.5 rounded-full bg-emerald-600 text-white shadow-sm';
                                b.innerText = 'Ù…ØªØµÙ„ Ø¨Ù‡ Ø­Ø³Ø§Ø¨ Ù…Ø±Ø¬Ø¹ (ONLINE)';
                            }}
                            if (toggleBtn) {{
                                toggleBtn.className = 'flex-1 py-2 rounded-xl text-[13px] font-bold bg-rose-600 hover:bg-rose-500 text-white transition flex justify-center items-center gap-1.5';
                                toggleBtn.innerHTML = '<svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"></path></svg><span>Ø®Ø±ÙˆØ¬ Ø§Ø² Ø­Ø³Ø§Ø¨</span>';
                            }}
                        }} else {{
                            showToast('âŒ ' + data.message, 'error');
                            if (resDiv) resDiv.innerHTML = '<span class="text-rose-500 font-bold">âŒ Ø®Ø·Ø§:</span> ' + data.message;
                            const b = document.getElementById('crawlerStatusBadge');
                            if (b) {{
                                b.className = 'text-[10px] px-2 py-0.5 rounded-full bg-rose-600 text-white shadow-sm';
                                b.innerText = 'Ù†Ø´Ø³Øª Ù…Ø±Ø¬Ø¹ Ù‚Ø·Ø¹ Ø§Ø³Øª (OFFLINE)';
                            }}
                            if (toggleBtn) {{
                                toggleBtn.className = 'flex-1 py-2 rounded-xl text-[13px] font-bold bg-emerald-600 hover:bg-emerald-500 text-white transition flex justify-center items-center gap-1.5';
                                toggleBtn.innerHTML = '<svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 16l-4-4m0 0l4-4m-4 4h14m-5 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h7a3 3 0 013 3v1"></path></svg><span>ÙˆØ±ÙˆØ¯ Ø¨Ù‡ Ø­Ø³Ø§Ø¨ Ù…Ø±Ø¬Ø¹</span>';
                            }}
                        }}
                    }} catch (e) {{
                        showToast('âŒ Ø®Ø·Ø§ÛŒ Ø´Ø¨Ú©Ù‡: ' + e.message, 'error');
                    }} finally {{
                        btn.innerHTML = origHtml;
                        btn.disabled = false;
                    }}
                }};
                
                async function handleLoginSubmit() {{
                    const btn = document.getElementById('loginBtn');
                    const errMsg = document.getElementById('loginErrorMsg');
                    const pwd = document.getElementById('adminPasswordInput').value.trim();

                    if (errMsg) {{
                        errMsg.style.display = 'none';
                        errMsg.innerText = '';
                    }}

                    if (!pwd) {{
                        if (errMsg) {{
                            errMsg.innerText = 'âŒ Ù„Ø·ÙØ§Ù‹ Ø±Ù…Ø² Ø¹Ø¨ÙˆØ± Ø±Ø§ ÙˆØ§Ø±Ø¯ Ú©Ù†ÛŒØ¯.';
                            errMsg.style.display = 'block';
                        }}
                        return;
                    }}

                    if (btn) {{
                        btn.disabled = true;
                        btn.innerHTML = 'â³ Ø¯Ø± Ø­Ø§Ù„ Ø¨Ø±Ø±Ø³ÛŒ...';
                    }}

                    try {{
                        const res = await fetch('/api/login', {{
                            method: 'POST',
                            headers: {{ 'Content-Type': 'application/json; charset=utf-8' }},
                            body: JSON.stringify({{ password: pwd }})
                        }});
                        const data = await res.json();
                        if (data && data.ok) {{
                            localStorage.setItem('unfinit_auth_token', 'authenticated');
                            localStorage.setItem('unfinit_admin_pwd', pwd);
                            sessionStorage.setItem('unfinit_auth_token', 'authenticated');
                            sessionStorage.setItem('unfinit_admin_pwd', pwd);
                            window.currentAdminPassword = pwd;

                            const gate = document.getElementById('loginGate');
                            const app = document.getElementById('appMain');
                            if (gate) {{
                                gate.style.display = 'none';
                                gate.classList.add('hidden');
                            }}
                            if (app) {{
                                app.style.removeProperty('display');
                                app.style.display = 'block';
                                app.classList.remove('hidden');
                            }}
                            try {{
                                const savedTab = localStorage.getItem('unfinit_active_tab') || 'studio';
                                if (typeof window.switchTab === 'function') {{
                                    window.switchTab(savedTab);
                                }}
                            }} catch (e) {{
                                console.warn('[Navigation] Tab switch notice:', e);
                            }}
                        }} else {{
                            if (errMsg) {{
                                errMsg.innerText = 'âŒ Ø±Ù…Ø² Ø¹Ø¨ÙˆØ± Ø§Ø´ØªØ¨Ø§Ù‡ Ø§Ø³Øª.';
                                errMsg.style.display = 'block';
                            }}
                        }}
                    }} catch (err) {{
                        if (errMsg) {{
                            errMsg.innerText = 'âŒ Ø®Ø·Ø§ÛŒ Ø§Ø±ØªØ¨Ø§Ø· Ø¨Ø§ Ø³Ø±ÙˆØ±: ' + (err.message || 'Ù†Ø§Ù…Ø´Ø®Øµ');
                            errMsg.style.display = 'block';
                        }}
                    }} finally {{
                        if (btn) {{
                            btn.disabled = false;
                            btn.innerHTML = '<span>âž”</span> ÙˆØ±ÙˆØ¯ Ø¨Ù‡ Ù¾Ù†Ù„';
                        }}
                    }}
                }}
                window.handleLoginSubmit = handleLoginSubmit;
                window.handleMainLogin = handleLoginSubmit;

                function handleLogout() {{
                    sessionStorage.removeItem('unfinit_auth');
                    sessionStorage.removeItem('unfinit_auth_token');
                    sessionStorage.removeItem('unfinit_admin_pwd');
                    localStorage.removeItem('unfinit_auth');
                    localStorage.removeItem('unfinit_auth_token');
                    localStorage.removeItem('unfinit_admin_pwd');
                    location.reload();
                }}
                window.handleLogout = handleLogout;

                function toggleSidebar(forceState) {{
                    const sidebar = document.getElementById('mainSidebar');
                    const content = document.getElementById('contentWrapper');
                    const overlay = document.getElementById('drawerOverlay');
                    const isMobile = window.innerWidth < 768;

                    if (isMobile) {{
                        if (!overlay || !sidebar) return;
                        const isClosed = sidebar.classList.contains('translate-x-full');
                        const shouldOpen = (typeof forceState === 'boolean') ? forceState : isClosed;
                        if (shouldOpen) {{
                            overlay.classList.remove('hidden');
                            sidebar.classList.remove('translate-x-full');
                            sidebar.classList.add('translate-x-0');
                        }} else {{
                            overlay.classList.add('hidden');
                            sidebar.classList.remove('translate-x-0');
                            sidebar.classList.add('translate-x-full');
                        }}
                    }} else {{
                        if (!sidebar) return;
                        const isCollapsed = sidebar.classList.contains('sidebar-collapsed');
                        const shouldCollapse = (typeof forceState === 'boolean') ? !forceState : !isCollapsed;
                        if (shouldCollapse) {{
                            sidebar.classList.add('sidebar-collapsed');
                            if (content) content.classList.add('sidebar-collapsed');
                            try {{ localStorage.setItem('unfinit_sidebar_collapsed', 'true'); }} catch (_) {{}}
                        }} else {{
                            sidebar.classList.remove('sidebar-collapsed');
                            if (content) content.classList.remove('sidebar-collapsed');
                            try {{ localStorage.setItem('unfinit_sidebar_collapsed', 'false'); }} catch (_) {{}}
                        }}
                    }}
                }}
                window.toggleSidebar = toggleSidebar;
                window.toggleMobileDrawer = toggleSidebar;
                window.toggleMobileMenu = toggleSidebar;

                function initSidebarState() {{
                    try {{
                        const isCollapsed = localStorage.getItem('unfinit_sidebar_collapsed') === 'true';
                        if (isCollapsed && window.innerWidth >= 768) {{
                            const sidebar = document.getElementById('mainSidebar');
                            const content = document.getElementById('contentWrapper');
                            if (sidebar) sidebar.classList.add('sidebar-collapsed');
                            if (content) content.classList.add('sidebar-collapsed');
                        }}
                    }} catch (_) {{}}
                }}
                window.initSidebarState = initSidebarState;

                const tabMeta = {{
                    'dashboard': {{
                        title: 'Ø¯Ø§Ø´Ø¨ÙˆØ±Ø¯ Ùˆ ÙˆØ¶Ø¹ÛŒØª Ø²Ù†Ø¯Ù‡ Ù…ÙˆØªÙˆØ± UNFINIT',
                        desc: 'Ù¾Ø§ÛŒØ´ Ù„Ø­Ø¸Ù‡â€ŒØ§ÛŒ Ø§ØªØµØ§Ù„Ø§ØªØŒ Ø¢Ù…Ø§Ø± ÙØ§ÛŒÙ„â€ŒÙ‡Ø§ØŒ Ø³Ù‚Ù Ø§ÛŒÙ…Ù† Ø¨Ù„Ù‡ Ùˆ Ù„Ø§Ú¯â€ŒÙ‡Ø§ÛŒ Ø²Ù†Ø¯Ù‡'
                    }},
                    'downloads': {{
                        title: 'ÙØ§ÛŒÙ„â€ŒÙ‡Ø§ÛŒ Ø¯Ø§Ù†Ù„ÙˆØ¯ÛŒ Ø±Ø§ÛŒÚ¯Ø§Ù† Ø³Ø§ÛŒØª',
                        desc: 'Ù¾Ø§ÛŒØ´ Ø®ÙˆØ¯Ú©Ø§Ø± ØµÙØ­Ø§Øª Ø³Ø§ÛŒØª Ù…Ø±Ø¬Ø¹ Ùˆ Ù¾Ú©ÛŒØ¬â€ŒØ¨Ù†Ø¯ÛŒ Ø³Ø±ÙØµÙ„â€ŒÙ‡Ø§ÛŒ Ø¯ÙˆØ±Ù‡â€ŒÙ‡Ø§'
                    }},
                    'studio': {{
                        title: 'Ø§Ø³ØªÙˆØ¯ÛŒÙˆÛŒ Ù¾ÛŒØ´Ø±ÙØªÙ‡ Ø±Ø³Ø§Ù†Ù‡ Ùˆ Ù…ØªØ§Ø¯ÛŒØªØ§',
                        desc: 'ÙˆÛŒØ±Ø§ÛŒØ´Ú¯Ø± ØªÚ¯ ØµÙˆØªÛŒ ID3ØŒ Ù¾Ø®Ø´â€ŒÚ©Ù†Ù†Ø¯Ù‡ ÙˆÛŒÙˆÙØ±Ù… ØµÙˆØªÛŒ Ùˆ Ø§Ø³ØªÙˆØ¯ÛŒÙˆÛŒ ÙˆÚ©ØªÙˆØ± SVG'
                    }},
                    'courses': {{
                        title: 'Ù…Ø¯ÛŒØ±ÛŒØª Ø¯ÙˆØ±Ù‡â€ŒÙ‡Ø§ÛŒ Ø¢Ù…ÙˆØ²Ø´ÛŒ Ùˆ Ø¯Ø±Ú¯Ø§Ù‡ Ù¾Ø±Ø¯Ø§Ø®Øª',
                        desc: 'ØªÙ†Ø¸ÛŒÙ… Ù‚ÛŒÙ…ØªØŒ ÙØ§ÛŒÙ„â€ŒÙ‡Ø§ØŒ Ø³Ø±ÙØµÙ„â€ŒÙ‡Ø§ Ùˆ Ø¯Ø±Ú¯Ø§Ù‡ Ù…Ø³ØªÙ‚ÛŒÙ… Ú©Ø§Ø±Øª Ø¨Ù‡ Ú©Ø§Ø±Øª Ø¨Ù„Ù‡'
                    }},
                    'orders': {{
                        title: 'Ø³ÙØ§Ø±Ø´Ø§ØªØŒ ØªØ±Ø§Ú©Ù†Ø´â€ŒÙ‡Ø§ Ùˆ Ú©ÙˆÙ¾Ù†â€ŒÙ‡Ø§ÛŒ ØªØ®ÙÛŒÙ',
                        desc: 'Ù…Ø¯ÛŒØ±ÛŒØª ÙÛŒØ´â€ŒÙ‡Ø§ÛŒ Ø¨Ø§Ù†Ú©ÛŒØŒ ØªØ£ÛŒÛŒØ¯ Ø®ÙˆØ¯Ú©Ø§Ø±/Ø¯Ø³ØªÛŒ Ø³ÙØ§Ø±Ø´Ø§Øª Ùˆ Ú©Ø¯Ù‡Ø§ÛŒ ØªØ®ÙÛŒÙ'
                    }},
                    'users': {{
                        title: 'Ø¨Ø§Ø´Ú¯Ø§Ù‡ Ù…Ø´ØªØ±ÛŒØ§Ù† Ùˆ Ø´Ø¨Ú©Ù‡ ÙˆØ§ÛŒØ±Ø§Ù„ Ø±ÙØ±Ø§Ù„',
                        desc: 'Ú©Ø§Ø±Ø¨Ø±Ø§Ù† Ø«Ø¨Øªâ€ŒÙ†Ø§Ù…â€ŒØ´Ø¯Ù‡ØŒ Ù…ÙˆØ¬ÙˆØ¯ÛŒ Ú©ÛŒÙ Ù¾ÙˆÙ„ØŒ Ø³ÛŒØ³ØªÙ… Ø¯Ø¹ÙˆØª Ø¯ÙˆØ³ØªØ§Ù† Ùˆ Ø®Ø±ÙˆØ¬ÛŒ CSV Ù…Ø®Ø§Ø·Ø¨ÛŒÙ†'
                    }},
                    'tokens': {{
                        title: 'Ù‡Ø§Ø¨ Ù‡ÙˆØ´ Ù…ØµÙ†ÙˆØ¹ÛŒ Ùˆ Ù…Ø¯ÛŒØ±ÛŒØª Ø³Ú©Ø±Øªâ€ŒÙ‡Ø§',
                        desc: 'Ù¾ÛŒÚ©Ø±Ø¨Ù†Ø¯ÛŒ Ù‡ÙˆØ´ Ú†Ù†Ø¯Ù…Ø¯Ù„Ù‡ (VyceAI, Nara, Gemini) Ùˆ ØªÙˆÚ©Ù†â€ŒÙ‡Ø§ÛŒ Ù¾Ù„ØªÙØ±Ù…â€ŒÙ‡Ø§'
                    }},
                    'frequencies': {{
                        title: 'Ø§Ø´ØªØ±Ø§Ú© Ù¾Ø±ÛŒÙ…ÛŒÙˆÙ… Ùˆ Ù…Ø¯ÛŒØ±ÛŒØª Ù…Ø­ØªÙˆØ§',
                        desc: 'ØªÙ†Ø¸ÛŒÙ…Ø§Øª Ø§Ø´ØªØ±Ø§Ú© Ù…Ø§Ù‡Ø§Ù†Ù‡ Ù¾Ø±ÛŒÙ…ÛŒÙˆÙ…ØŒ Ø´Ø®ØµÛŒâ€ŒØ³Ø§Ø²ÛŒ Ù†Ø´Ø§Ù†Ù‡ Ø±ÙˆØ²Ø§Ù†Ù‡ Ùˆ Ú©Ø§Ø±Øªâ€ŒÙ‡Ø§ÛŒ ÙØ±Ú©Ø§Ù†Ø³ ÙØ±Ø§ÙˆØ§Ù†ÛŒ'
                    }},
                    'settings': {{
                        title: 'ØªÙ†Ø¸ÛŒÙ…Ø§Øª Ø³ÛŒØ³ØªÙ…ÛŒØŒ Ø¯ÛŒØªØ§Ø¨ÛŒØ³ Ùˆ Ù„Ø§Ú¯â€ŒÙ‡Ø§',
                        desc: 'Ù¾ÛŒÚ©Ø±Ø¨Ù†Ø¯ÛŒ Ø³Ù‚Ù Ø¨Ù„Ù‡ØŒ Ù¾Ø§ÛŒÚ¯Ø§Ù‡ Ø¯Ø§Ø¯Ù‡ Ø±Ù…Ø²Ù†Ú¯Ø§Ø±ÛŒâ€ŒØ´Ø¯Ù‡ AES-256 Ùˆ Ú©Ù†Ø³ÙˆÙ„ Ù„Ø§Ú¯'
                    }}
                }};

                function switchTab(tabId) {{
                    try {{
                        if (!tabId) tabId = 'dashboard';
                        let rawTab = tabId.startsWith('tab-') ? tabId.replace('tab-', '') : tabId;
                        const validTabs = ['dashboard', 'downloads', 'studio', 'courses', 'orders', 'users', 'tokens', 'frequencies', 'settings'];
                        if (!validTabs.includes(rawTab)) {{
                            rawTab = 'dashboard';
                        }}
                        const fullTabId = 'tab-' + rawTab;
                        try {{
                            localStorage.setItem('unfinit_active_tab', rawTab);
                        }} catch (_) {{}}

                        validTabs.forEach(id => {{
                            const el = document.getElementById('tab-' + id);
                            if (el) el.classList.add('hidden');
                        }});

                        // Update sidebar buttons
                        document.querySelectorAll('.sidebar-nav-btn').forEach(btn => {{
                            btn.classList.remove('active');
                        }});
                        const activeSidebarBtn = document.getElementById('s-btn-tab-' + rawTab);
                        if (activeSidebarBtn) {{
                            activeSidebarBtn.classList.add('active');
                        }}

                        // Update legacy tab-btn for compatibility
                        document.querySelectorAll('.tab-btn').forEach(btn => {{
                            btn.classList.remove('active');
                            btn.classList.add('bg-slate-800/80', 'text-slate-300');
                        }});
                        const targetBtn = document.getElementById('btn-tab-' + rawTab);
                        if (targetBtn) {{
                            targetBtn.classList.add('active');
                            targetBtn.classList.remove('bg-slate-800/80', 'text-slate-300');
                        }}
                        const mobileBtn = document.getElementById('m-btn-tab-' + rawTab);
                        if (mobileBtn) {{
                            mobileBtn.classList.add('active');
                            mobileBtn.classList.remove('bg-slate-800/80', 'text-slate-300');
                        }}

                        // Update Mobile Bottom Nav Active State
                        const bottomNav = document.getElementById('mobileBottomNav');
                        if (bottomNav) {{
                            bottomNav.querySelectorAll('[data-tab]').forEach(btn => {{
                                btn.classList.remove('active', 'text-cyan-400');
                                btn.classList.add('text-slate-400');
                            }});
                            const activeBottomBtn = bottomNav.querySelector(`[data-tab="${{rawTab}}"]`);
                            if (activeBottomBtn) {{
                                activeBottomBtn.classList.add('active', 'text-cyan-400');
                                activeBottomBtn.classList.remove('text-slate-400');
                            }}
                        }}

                        const targetTab = document.getElementById(fullTabId);
                        if (targetTab) {{
                            targetTab.classList.remove('hidden');
                        }}

                        const titleEl = document.getElementById('currentTabTitle');
                        const descEl = document.getElementById('currentTabDesc');
                        if (titleEl && tabMeta[rawTab]) titleEl.innerText = tabMeta[rawTab].title;
                        if (descEl && tabMeta[rawTab]) descEl.innerText = tabMeta[rawTab].desc;

                        if (rawTab === 'dashboard') {{
                            if (typeof window.loadDashboardData === 'function') window.loadDashboardData();
                        }}
                        if (rawTab === 'users') {{
                            if (typeof window.loadUsersData === 'function') window.loadUsersData();
                        }}
                        if (rawTab === 'frequencies') {{
                            if (typeof window.loadVipSettings === 'function') window.loadVipSettings();
                            if (typeof window.loadFrequenciesTable === 'function') window.loadFrequenciesTable();
                        }}
                        if (rawTab === 'settings' || rawTab === 'tokens') {{
                            if (typeof window.loadSettings === 'function') window.loadSettings();
                            if (typeof window.loadFrequenciesTable === 'function') window.loadFrequenciesTable();
                        }}
                        if (rawTab === 'courses') {{
                            if (typeof window.loadStoreAnalytics === 'function') window.loadStoreAnalytics();
                        }}
                        if (rawTab === 'orders') {{
                            if (typeof window.loadStoreOrders === 'function') window.loadStoreOrders();
                            if (typeof window.loadStoreCoupons === 'function') window.loadStoreCoupons();
                            if (typeof window.loadStoreAnalytics === 'function') window.loadStoreAnalytics();
                        }}
                        if (rawTab === 'downloads') {{
                            if (typeof window.lazyLoadDownloadsFeed === 'function') window.lazyLoadDownloadsFeed();
                        }}
                    }} catch (err) {{
                        console.error('[UNFINIT Navigation Module Error] switchTab error:', err);
                    }}
                }}
                window.switchTab = switchTab;

                window.downloadsFeedLoaded = false;
                window.lazyLoadDownloadsFeed = function() {{
                    if (!window.downloadsFeedLoaded) {{
                        window.downloadsFeedLoaded = true;
                        if (typeof window.fetchFeedDownloads === 'function') window.fetchFeedDownloads(false);
                        if (typeof window.loadFeedCategories === 'function') window.loadFeedCategories();
                    }}
                }};

                let drawerAllLines = [];

                function filterDrawerLogs() {{
                    const q = (document.getElementById('drawerLogSearch')?.value || '').toLowerCase().trim();
                    const streamBox = document.getElementById('dashboardRecentLogs');
                    if (!streamBox) return;
                    if (!q) {{
                        streamBox.innerText = drawerAllLines.slice(-30).join('\\n') || '// Ù„Ø§Ú¯ÛŒ Ø¨Ø±Ø§ÛŒ Ù†Ù…Ø§ÛŒØ´ Ù…ÙˆØ¬ÙˆØ¯ Ù†ÛŒØ³Øª.';
                    }} else {{
                        const filtered = drawerAllLines.filter(l => l.toLowerCase().includes(q));
                        streamBox.innerText = filtered.join('\\n') || '// Ù…ÙˆØ±Ø¯ÛŒ ÛŒØ§ÙØª Ù†Ø´Ø¯.';
                    }}
                    const autoScroll = document.getElementById('drawerAutoScroll');
                    if (!autoScroll || autoScroll.checked) {{
                        streamBox.scrollTop = streamBox.scrollHeight;
                    }}
                }}
                window.filterDrawerLogs = filterDrawerLogs;

                async function copyDrawerLogs() {{
                    const streamBox = document.getElementById('dashboardRecentLogs');
                    if (!streamBox) return;
                    try {{
                        await navigator.clipboard.writeText(streamBox.innerText);
                        const btn = document.getElementById('drawerCopyBtn');
                        if (btn) {{
                            const orig = btn.innerHTML;
                            btn.innerHTML = '<span class="text-emerald-400 font-sans text-xs">Ú©Ù¾ÛŒ Ø´Ø¯ âœ“</span>';
                            setTimeout(() => {{ btn.innerHTML = orig; }}, 2000);
                        }}
                    }} catch (e) {{
                        showToast('Ø®Ø·Ø§ Ø¯Ø± Ú©Ù¾ÛŒ Ù„Ø§Ú¯â€ŒÙ‡Ø§: ' + e.message);
                    }}
                }}
                window.copyDrawerLogs = copyDrawerLogs;

                async function loadDashboardData() {{
                    try {{
                        const streamBox = document.getElementById('dashboardRecentLogs');
                        const mainLogs = document.getElementById('logContainer');
                        if (streamBox && mainLogs && mainLogs.innerText.trim()) {{
                            const lines = mainLogs.innerText.trim().split('\\n').filter(Boolean);
                            drawerAllLines = lines;
                            const q = (document.getElementById('drawerLogSearch')?.value || '').trim();
                            if (!q) {{
                                const recent = lines.slice(-30).join('\\n');
                                if (recent) streamBox.innerText = recent;
                            }}
                            const autoScroll = document.getElementById('drawerAutoScroll');
                            if (!autoScroll || autoScroll.checked) {{
                                streamBox.scrollTop = streamBox.scrollHeight;
                            }}
                            const prev = document.getElementById('dashboardLatestLogPreview');
                            if (prev && lines.length > 0) {{
                                prev.textContent = lines[lines.length - 1];
                            }}
                        }}
                        const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                        const res = await fetch('/api/store/analytics', {{
                            headers: {{ 'Authorization': 'Bearer ' + pwd, 'X-Admin-Password': pwd }}
                        }});
                        if (res.ok) {{
                            const data = await res.json();
                            if (data.active_drops !== undefined) {{
                                const el = document.getElementById('dashTotalDrops');
                                if (el) el.innerText = data.active_drops;
                            }}
                        }}
                    }} catch (e) {{
                        console.warn('loadDashboardData error:', e);
                    }}
                }}
                window.loadDashboardData = loadDashboardData;

                function toggleLogsDrawer(show) {{
                    const drawer = document.getElementById('logsDrawer');
                    const overlay = document.getElementById('logsDrawerOverlay');
                    if (!drawer) return;
                    const isHidden = drawer.classList.contains('-translate-x-full');
                    const shouldShow = (typeof show === 'boolean') ? show : isHidden;
                    if (shouldShow) {{
                        drawer.classList.remove('-translate-x-full');
                        if (overlay) overlay.classList.remove('hidden');
                        if (typeof loadDashboardData === 'function') loadDashboardData();
                    }} else {{
                        drawer.classList.add('-translate-x-full');
                        if (overlay) overlay.classList.add('hidden');
                    }}
                }}
                window.toggleLogsDrawer = toggleLogsDrawer;

                function openBaleCapModal() {{
                    const m = document.getElementById('modalBaleCapSettings');
                    if (m) m.classList.remove('hidden');
                    calcEffectiveCap();
                }}
                window.openBaleCapModal = openBaleCapModal;

                function closeBaleCapModal() {{
                    const m = document.getElementById('modalBaleCapSettings');
                    if (m) m.classList.add('hidden');
                }}
                window.closeBaleCapModal = closeBaleCapModal;

                function calcEffectiveCap() {{
                    const cInput = document.getElementById('baleCapInput');
                    const bInput = document.getElementById('baleBufferInput');
                    const c = parseFloat(cInput ? cInput.value : 50.0) || 50.0;
                    const b = parseFloat(bInput ? bInput.value : 3.0) || 3.0;
                    const eff = (c * (1.0 - (b / 100.0))).toFixed(2);
                    const el = document.getElementById('previewEffectiveCap');
                    if (el) el.textContent = eff;
                }}
                window.calcEffectiveCap = calcEffectiveCap;

                async function submitBaleCapSettings(e) {{
                    e.preventDefault();
                    const cInput = document.getElementById('baleCapInput');
                    const bInput = document.getElementById('baleBufferInput');
                    const c = parseFloat(cInput ? cInput.value : 50.0);
                    const b = parseFloat(bInput ? bInput.value : 3.0);
                    if (isNaN(c) || c <= 0 || c > 50) {{
                        showToast('Ø³Ù‚Ù Ù…Ø¬Ø§Ø² Ø¨Ø§ÛŒØ¯ Ø¹Ø¯Ø¯ÛŒ Ø¨ÛŒÙ† Û± ØªØ§ ÛµÛ° Ù…Ú¯Ø§Ø¨Ø§ÛŒØª Ø¨Ø§Ø´Ø¯.');
                        return;
                    }}
                    if (isNaN(b) || b < 0 || b > 15) {{
                        showToast('Ø¨Ø§ÙØ± Ø§Ù…Ù†ÛŒØªÛŒ Ø¨Ø§ÛŒØ¯ Ø¨ÛŒÙ† Û° ØªØ§ Û±Ûµ Ø¯Ø±ØµØ¯ Ø¨Ø§Ø´Ø¯.');
                        return;
                    }}
                    const eff = (c * (1.0 - (b / 100.0))).toFixed(2);
                    const btn = document.getElementById('btnSaveBaleCap');
                    if (btn) {{
                        btn.disabled = true;
                        btn.innerHTML = '<span>Ø¯Ø± Ø­Ø§Ù„ Ø°Ø®ÛŒØ±Ù‡...</span>';
                    }}
                    try {{
                        const pwd = window.currentAdminPassword || sessionStorage.getItem('unfinit_admin_pwd') || localStorage.getItem('unfinit_admin_pwd') || '';
                        const res = await fetch('/api/settings/save', {{
                            method: 'POST',
                            credentials: 'same-origin',
                            headers: {{
                                'Content-Type': 'application/json; charset=utf-8',
                                'Authorization': 'Bearer ' + pwd,
                                'X-Admin-Password': pwd
                            }},
                            body: JSON.stringify({{
                                password: pwd,
                                settings: {{
                                    bale_max_file_size_mb: c,
                                    bale_safety_buffer_percent: b,
                                    MAX_SAFE_BALE_SIZE_MB: c
                                }},
                                bale_max_file_size_mb: c,
                                bale_safety_buffer_percent: b
                            }})
                        }});
                        const data = await res.json();
                        if (data.ok) {{
                            const d1 = document.getElementById('baleCardSafeSize');
                            const d2 = document.getElementById('baleCardBuffer');
                            const d3 = document.getElementById('baleCardEffective');
                            const d4 = document.getElementById('dashBaleSafeSize');
                            if (d1) d1.textContent = c.toFixed(1) + ' MB';
                            if (d2) d2.textContent = b.toFixed(1) + '%';
                            if (d3) d3.textContent = eff + ' MB';
                            if (d4) d4.textContent = c.toFixed(1) + ' MB';
                            closeBaleCapModal();
                        }} else {{
                            showToast('Ø®Ø·Ø§ Ø¯Ø± Ø°Ø®ÛŒØ±Ù‡ ØªÙ†Ø¸ÛŒÙ…Ø§Øª: ' + (data.error || 'Ø¹Ù…Ù„ÛŒØ§Øª Ù†Ø§Ù…ÙˆÙÙ‚ Ø¨ÙˆØ¯'));
                        }}
                    }} catch (err) {{
                        showToast('Ø®Ø·Ø§ Ø¯Ø± Ø¨Ø±Ù‚Ø±Ø§Ø±ÛŒ Ø§Ø±ØªØ¨Ø§Ø·: ' + err.message);
                    }} finally {{
                        if (btn) {{
                            btn.disabled = false;
                            btn.innerHTML = '<span>Ø°Ø®ÛŒØ±Ù‡ ØªÙ†Ø¸ÛŒÙ…Ø§Øª</span>';
                        }}
                    }}
                }}
                window.submitBaleCapSettings = submitBaleCapSettings;
                window.editBaleSafeLimit = openBaleCapModal;

                /**
                 * ØªØ§Ø¨Ø¹ Ù‚Ø·Ø¹ Ø§Ø±ØªØ¨Ø§Ø· Ùˆ Ø­Ø°Ù Ù†Ø´Ø³Øª Ù¾Ù„ØªÙØ±Ù…â€ŒÙ‡Ø§ Ø¨Ù‡ ØµÙˆØ±Øª ØºÛŒØ±Ù‡Ù…Ú¯Ø§Ù… (AJAX)
                 * Ø·Ø¨Ù‚ Ù‚Ø§Ù†ÙˆÙ† Ø§Ú©Ø´Ù†â€ŒÙ‡Ø§ÛŒ Ø¨Ø¯ÙˆÙ† Ø±ÙØ±Ø´ (Zero Page-Reload Principle)ØŒ Ø§Ù„Ù…Ø§Ù†â€ŒÙ‡Ø§ÛŒ DOM Ø±Ø§ Ø¨Ø¯ÙˆÙ† Ø¨Ø§Ø±Ú¯Ø°Ø§Ø±ÛŒ Ù…Ø¬Ø¯Ø¯ ØµÙØ­Ù‡ Ø¨Ù‡â€ŒØ±ÙˆØ²Ø±Ø³Ø§Ù†ÛŒ Ù…ÛŒâ€ŒÚ©Ù†Ø¯.
                 * @param {{string}} platform - Ù†Ø§Ù… Ù¾Ù„ØªÙØ±Ù… ('soroush' ÛŒØ§ 'rubika')
                 */
                async function disconnectSession(platform) {{
                    const platName = (platform === 'soroush' ? 'Ø³Ø±ÙˆØ´â€ŒÙ¾Ù„Ø§Ø³' : 'Ø±ÙˆØ¨ÛŒÚ©Ø§');
                    if (!confirm('Ø¢ÛŒØ§ Ø§Ø² Ù‚Ø·Ø¹ Ø§ØªØµØ§Ù„ Ùˆ Ø­Ø°Ù Ø§Ù…Ù† Ø³Ø´Ù† ' + platName + ' Ø§Ø·Ù…ÛŒÙ†Ø§Ù† Ø¯Ø§Ø±ÛŒØ¯ØŸ')) return;
                    try {{
                        const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                        const res = await fetch('/api/sessions/disconnect', {{
                            method: 'POST',
                            headers: {{
                                'Content-Type': 'application/json; charset=utf-8',
                                'Authorization': 'Bearer ' + pwd,
                                'X-Admin-Password': pwd
                            }},
                            body: JSON.stringify({{ platform: platform }})
                        }});
                        const data = await res.json();
                        if (data.ok) {{
                            if (platform === 'soroush') {{
                                const b = document.getElementById('soroushStatusBadge');
                                if (b) {{
                                    b.className = 'px-2 py-0.5 rounded text-xs font-bold bg-amber-950 text-amber-400 border border-amber-800';
                                    b.textContent = 'Ù†ÛŒØ§Ø²Ù…Ù†Ø¯ Ø±Ø§Ù‡â€ŒØ§Ù†Ø¯Ø§Ø²ÛŒ';
                                }}
                                const pEl = document.getElementById('soroushPhoneDisplay');
                                if (pEl) pEl.textContent = 'Ø¹Ø¯Ù… Ø§ØªØµØ§Ù„';
                                const btnBox = document.getElementById('soroushBtnContainer');
                                if (btnBox) {{
                                    btnBox.innerHTML = '<button type="button" onclick="openSoroushLoginModal()" class="w-full py-1.5 px-2 rounded-lg theme-accent-btn text-[11px] font-bold transition flex items-center justify-center gap-1.5"><svg class="w-3.5 h-3.5 stroke-[1.75]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M15.75 5.25a3 3 0 013 3m3 0a6 6 0 01-7.029 5.912c-.563-.097-1.159.026-1.563.43L10.5 17.25H8.25v2.25H6v2.25H2.25v-2.818c0-.597.237-1.17.659-1.591l6.499-6.499c.404-.404.527-1 .43-1.563A6 6 0 1121.75 8.25z" /></svg><span>ÙˆØ±ÙˆØ¯ Ø¨Ù‡ Ø­Ø³Ø§Ø¨ Ø³Ø±ÙˆØ´â€ŒÙ¾Ù„Ø§Ø³</span></button>';
                                }}
                            }} else if (platform === 'rubika') {{
                                const b = document.getElementById('rubikaStatusBadge');
                                if (b) {{
                                    b.className = 'px-2 py-0.5 rounded text-xs font-bold bg-amber-950 text-amber-400 border border-amber-800';
                                    b.textContent = 'REQUIRE_AUTH';
                                }}
                                const pEl = document.getElementById('rubikaPhoneDisplay');
                                if (pEl) pEl.textContent = 'Ø¨Ø¯ÙˆÙ† Ø´Ù…Ø§Ø±Ù‡';
                                const btnBox = document.getElementById('rubikaBtnContainer');
                                if (btnBox) {{
                                    btnBox.innerHTML = '<p class="text-[11px] text-amber-400 text-center py-1">Ø³Ø´Ù† ØºÛŒØ±ÙØ¹Ø§Ù„ Ø§Ø³Øª</p>';
                                }}
                            }}
                            showToast('âœ… Ø³Ø´Ù† ' + platName + ' Ø¨Ø§ Ù…ÙˆÙÙ‚ÛŒØª Ù‚Ø·Ø¹ Ùˆ Ø§Ø² Ø³Ø±ÙˆØ± Ù¾Ø§Ú©Ø³Ø§Ø²ÛŒ Ø´Ø¯.');
                        }} else {{
                            showToast('âŒ Ø®Ø·Ø§: ' + (data.error || 'Ø¹Ù…Ù„ÛŒØ§Øª Ù†Ø§Ù…ÙˆÙÙ‚ Ø¨ÙˆØ¯'));
                        }}
                    }} catch (e) {{
                        showToast('âŒ Ø®Ø·Ø§ÛŒ Ø§Ø±ØªØ¨Ø§Ø· Ø¨Ø§ Ø³Ø±ÙˆØ±: ' + e.message);
                    }}
                }}
                window.disconnectSession = disconnectSession;

                function switchUserSubTab(subTab) {{
                    const listSec = document.getElementById('userSubTabContentList');
                    const refSec = document.getElementById('userSubTabContentRef');
                    const btnList = document.getElementById('btnUserSubTabList');
                    const btnRef = document.getElementById('btnUserSubTabRef');
                    if (subTab === 'referrals') {{
                        if (listSec) listSec.classList.add('hidden');
                        if (refSec) refSec.classList.remove('hidden');
                        if (btnRef) {{
                            btnRef.className = 'px-4 py-2 rounded-xl text-xs font-bold transition flex items-center gap-2 theme-accent-btn';
                        }}
                        if (btnList) {{
                            btnList.className = 'px-4 py-2 rounded-xl text-xs font-bold transition flex items-center gap-2 theme-card-btn text-slate-300';
                        }}
                    }} else {{
                        if (refSec) refSec.classList.add('hidden');
                        if (listSec) listSec.classList.remove('hidden');
                        if (btnList) {{
                            btnList.className = 'px-4 py-2 rounded-xl text-xs font-bold transition flex items-center gap-2 theme-accent-btn';
                        }}
                        if (btnRef) {{
                            btnRef.className = 'px-4 py-2 rounded-xl text-xs font-bold transition flex items-center gap-2 theme-card-btn text-slate-300';
                        }}
                    }}
                }}
                window.switchUserSubTab = switchUserSubTab;

                let pendingSoroushPhone = '';

                function openSoroushLoginModal() {{
                    const modal = document.getElementById('soroushLoginModal');
                    if (modal) {{
                        modal.classList.remove('hidden');
                        resetSoroushLoginForm();
                    }}
                }}
                function closeSoroushLoginModal() {{
                    const modal = document.getElementById('soroushLoginModal');
                    if (modal) modal.classList.add('hidden');
                }}
                function switchSoroushTab(tab) {{
                    const smsPhone = document.getElementById('soroushStepPhone');
                    const smsCode = document.getElementById('soroushStepCode');
                    const manStep = document.getElementById('soroushStepManual');
                    const btnSms = document.getElementById('tabBtnSoroushSms');
                    const btnMan = document.getElementById('tabBtnSoroushManual');
                    const errBox = document.getElementById('soroushLoginError');
                    if (errBox) errBox.classList.add('hidden');
                    if (tab === 'manual') {{
                        if (smsPhone) smsPhone.classList.add('hidden');
                        if (smsCode) smsCode.classList.add('hidden');
                        if (manStep) manStep.classList.remove('hidden');
                        if (btnMan) {{ btnMan.className = 'flex-1 py-1.5 rounded-lg text-xs font-bold transition theme-card-btn'; }}
                        if (btnSms) {{ btnSms.className = 'flex-1 py-1.5 rounded-lg text-xs font-bold text-slate-400 hover:text-white transition'; }}
                    }} else {{
                        if (manStep) manStep.classList.add('hidden');
                        if (smsPhone) smsPhone.classList.remove('hidden');
                        if (smsCode) smsCode.classList.add('hidden');
                        if (btnSms) {{ btnSms.className = 'flex-1 py-1.5 rounded-lg text-xs font-bold transition theme-card-btn'; }}
                        if (btnMan) {{ btnMan.className = 'flex-1 py-1.5 rounded-lg text-xs font-bold text-slate-400 hover:text-white transition'; }}
                    }}
                }}
                function resetSoroushLoginForm() {{
                    switchSoroushTab('sms');
                    const errBox = document.getElementById('soroushLoginError');
                    if (errBox) {{ errBox.classList.add('hidden'); errBox.textContent = ''; }}
                    const phoneInput = document.getElementById('soroushPhoneInput');
                    if (phoneInput) phoneInput.value = '';
                    const codeInput = document.getElementById('soroushCodeInput');
                    if (codeInput) codeInput.value = '';
                    const manTokInput = document.getElementById('soroushManualTokenInput');
                    if (manTokInput) manTokInput.value = '';
                    const manPhInput = document.getElementById('soroushManualPhoneInput');
                    if (manPhInput) manPhInput.value = '';
                }}
                async function submitSoroushPhone() {{
                    const phoneInput = document.getElementById('soroushPhoneInput');
                    const phone = phoneInput ? phoneInput.value.trim() : '';
                    if (!phone || phone.length < 10) {{
                        showToast('Ø´Ù…Ø§Ø±Ù‡ ØªÙ„ÙÙ† Ù†Ø§Ù…Ø¹ØªØ¨Ø± Ø§Ø³Øª.');
                        return;
                    }}
                    const btn = document.getElementById('btnSoroushSendCode');
                    const errBox = document.getElementById('soroushLoginError');
                    if (btn) {{ btn.disabled = true; btn.textContent = 'Ø¯Ø± Ø­Ø§Ù„ Ø§Ø±Ø³Ø§Ù„ Ø¯Ø±Ø®ÙˆØ§Ø³Øª...'; }}
                    if (errBox) errBox.classList.add('hidden');
                    try {{
                        const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                        const res = await fetch('/api/soroush/login/request', {{
                            method: 'POST',
                            headers: {{
                                'Content-Type': 'application/json; charset=utf-8',
                                'Authorization': 'Bearer ' + pwd,
                                'X-Admin-Password': pwd
                            }},
                            body: JSON.stringify({{ phone: phone }})
                        }});
                        const data = await res.json();
                        if (data.ok) {{
                            pendingSoroushPhone = phone;
                            const disp = document.getElementById('soroushTargetPhoneDisplay');
                            if (disp) disp.textContent = phone;
                            const pStep = document.getElementById('soroushStepPhone');
                            const cStep = document.getElementById('soroushStepCode');
                            if (pStep) pStep.classList.add('hidden');
                            if (cStep) cStep.classList.remove('hidden');
                        }} else {{
                            if (errBox) {{
                                errBox.textContent = data.error || 'Ø®Ø·Ø§ Ø¯Ø± Ø§Ø±Ø³Ø§Ù„ Ú©Ø¯';
                                errBox.classList.remove('hidden');
                            }} else {{
                                showToast(data.error || 'Ø®Ø·Ø§ Ø¯Ø± Ø§Ø±Ø³Ø§Ù„ Ú©Ø¯');
                            }}
                        }}
                    }} catch (e) {{
                        showToast('Ø®Ø·Ø§: ' + e.message);
                    }} finally {{
                        if (btn) {{ btn.disabled = false; btn.textContent = 'Ø¯Ø±ÛŒØ§ÙØª Ú©Ø¯ ØªØ§ÛŒÛŒØ¯ Ù¾ÛŒØ§Ù…Ú©ÛŒ'; }}
                    }}
                }}
                /**
                 * Ø§Ø±Ø³Ø§Ù„ Ú©Ø¯ ØªØ§ÛŒÛŒØ¯ Ù¾ÛŒØ§Ù…Ú©ÛŒ Ùˆ ØªØ§ÛŒÛŒØ¯ Ù†Ù‡Ø§ÛŒÛŒ Ø³Ø´Ù† Ø³Ø±ÙˆØ´â€ŒÙ¾Ù„Ø§Ø³
                 * Ø§Ù„Ù…Ø§Ù†â€ŒÙ‡Ø§ÛŒ Ú©Ø§Ø±Øª Ø¯Ø§Ø´Ø¨ÙˆØ±Ø¯ Ø±Ø§ Ø¨Ø¯ÙˆÙ† Ø¨Ø§Ø±Ú¯Ø°Ø§Ø±ÛŒ Ù…Ø¬Ø¯Ø¯ ØµÙØ­Ù‡ Ø¨Ù‡â€ŒØ±ÙˆØ²Ø±Ø³Ø§Ù†ÛŒ Ù…ÛŒâ€ŒÚ©Ù†Ø¯.
                 */
                async function submitSoroushCode() {{
                    const codeInput = document.getElementById('soroushCodeInput');
                    const code = codeInput ? codeInput.value.trim() : '';
                    if (!code) {{
                        showToast('Ù„Ø·ÙØ§Ù‹ Ú©Ø¯ ØªØ§ÛŒÛŒØ¯ Ø±Ø§ ÙˆØ§Ø±Ø¯ Ù†Ù…Ø§ÛŒÛŒØ¯.');
                        return;
                    }}
                    const btn = document.getElementById('btnSoroushVerifyCode');
                    const errBox = document.getElementById('soroushLoginError');
                    if (btn) {{ btn.disabled = true; btn.textContent = 'Ø¯Ø± Ø­Ø§Ù„ ØªØ§ÛŒÛŒØ¯...'; }}
                    if (errBox) errBox.classList.add('hidden');
                    try {{
                        const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                        const res = await fetch('/api/soroush/login/verify', {{
                            method: 'POST',
                            headers: {{
                                'Content-Type': 'application/json; charset=utf-8',
                                'Authorization': 'Bearer ' + pwd,
                                'X-Admin-Password': pwd
                            }},
                            body: JSON.stringify({{ phone: pendingSoroushPhone, code: code }})
                        }});
                        const data = await res.json();
                        if (data.ok) {{
                            const b = document.getElementById('soroushStatusBadge');
                            if (b) {{
                                b.className = 'px-2 py-0.5 rounded text-xs font-bold bg-emerald-950 text-emerald-400 border border-emerald-800';
                                b.textContent = 'ONLINE';
                            }}
                            const pEl = document.getElementById('soroushPhoneDisplay');
                            if (pEl) pEl.textContent = data.masked_phone || pendingSoroushPhone || 'Ù…ØªØµÙ„';
                            const btnBox = document.getElementById('soroushBtnContainer');
                            if (btnBox) {{
                                const dcBtn = document.createElement('button');
                                dcBtn.type = 'button';
                                dcBtn.onclick = function() {{ disconnectSession('soroush'); }};
                                dcBtn.className = 'w-full py-1.5 px-2 rounded-lg bg-rose-950/60 hover:bg-rose-900/80 text-rose-300 border border-rose-800 text-[11px] font-bold transition flex items-center justify-center gap-1.5';
                                dcBtn.innerHTML = '<svg class="w-3.5 h-3.5 stroke-[1.75]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M5.636 5.636a9 9 0 1012.728 0M12 3v9" /></svg><span>Ù‚Ø·Ø¹ Ø§ØªØµØ§Ù„ / Ø®Ø±ÙˆØ¬</span>';
                                btnBox.innerHTML = '';
                                btnBox.appendChild(dcBtn);
                            }}
                            showToast('ÙˆØ±ÙˆØ¯ Ø¨Ø§ Ù…ÙˆÙÙ‚ÛŒØª Ø§Ù†Ø¬Ø§Ù… Ø´Ø¯ Ùˆ Ø³Ø´Ù† Ø³Ø±ÙˆØ´â€ŒÙ¾Ù„Ø§Ø³ Ø¨Ø§ Ø§Ø³ØªØ§Ù†Ø¯Ø§Ø±Ø¯ AES-256 Ø±Ù…Ø²Ù†Ú¯Ø§Ø±ÛŒ Ùˆ ÙØ¹Ø§Ù„ Ú¯Ø±Ø¯ÛŒØ¯.');
                            closeSoroushLoginModal();
                        }} else {{
                            if (errBox) {{
                                errBox.textContent = data.error || 'Ú©Ø¯ ØªØ§ÛŒÛŒØ¯ Ø§Ø´ØªØ¨Ø§Ù‡ Ø§Ø³Øª.';
                                errBox.classList.remove('hidden');
                            }} else {{
                                showToast(data.error || 'Ú©Ø¯ ØªØ§ÛŒÛŒØ¯ Ø§Ø´ØªØ¨Ø§Ù‡ Ø§Ø³Øª.');
                            }}
                        }}
                    }} catch (e) {{
                        showToast('Ø®Ø·Ø§: ' + e.message);
                    }} finally {{
                        if (btn) {{ btn.disabled = false; btn.textContent = 'ØªØ§ÛŒÛŒØ¯ Ùˆ ÙØ¹Ø§Ù„â€ŒØ³Ø§Ø²ÛŒ Ø³Ø´Ù† Ø§Ù…Ù†'; }}
                    }}
                }}

                /**
                 * Ø«Ø¨Øª Ø¯Ø³ØªÛŒ Ø³Ø´Ù† Ø³Ø±ÙˆØ´â€ŒÙ¾Ù„Ø§Ø³ (ØªÙˆÚ©Ù† ÛŒØ§ Ø¢Ø¨Ø¬Ú©Øª JSON Ú©Ø§Ù…Ù„ account1)
                 * Ù¾Ø³ Ø§Ø² Ø±Ù…Ø²Ù†Ú¯Ø§Ø±ÛŒ Ùˆ Ø§Ø¹ØªØ¨Ø§Ø±Ø³Ù†Ø¬ÛŒ Ø³Ø±ÙˆØ±ØŒ Ú©Ø§Ø±Øª Ø±Ø§ Ø¯Ø± DOM Ø¨Ø¯ÙˆÙ† Ø±ÙØ±Ø´ Ø¨Ù‡â€ŒØ±ÙˆØ² Ù…ÛŒâ€ŒÚ©Ù†Ø¯.
                 */
                async function submitSoroushManualToken() {{
                    const tokInput = document.getElementById('soroushManualTokenInput');
                    const phInput = document.getElementById('soroushManualPhoneInput');
                    const token = tokInput ? tokInput.value.trim() : '';
                    const phone = phInput ? phInput.value.trim() : '';
                    if (!token) {{
                        showToast('ØªÙˆÚ©Ù† Ù†Ø´Ø³Øª Ø§Ù„Ø²Ø§Ù…ÛŒ Ø§Ø³Øª.');
                        return;
                    }}
                    const btn = document.getElementById('btnSoroushManualSubmit');
                    const errBox = document.getElementById('soroushLoginError');
                    if (btn) {{ btn.disabled = true; btn.textContent = 'Ø¯Ø± Ø­Ø§Ù„ Ø°Ø®ÛŒØ±Ù‡â€ŒØ³Ø§Ø²ÛŒ...'; }}
                    if (errBox) errBox.classList.add('hidden');
                    try {{
                        const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                        const res = await fetch('/api/soroush/login/manual', {{
                            method: 'POST',
                            headers: {{
                                'Content-Type': 'application/json; charset=utf-8',
                                'Authorization': 'Bearer ' + pwd,
                                'X-Admin-Password': pwd
                            }},
                            body: JSON.stringify({{ token: token, phone: phone }})
                        }});
                        const data = await res.json();
                        if (data.ok) {{
                            const b = document.getElementById('soroushStatusBadge');
                            if (b) {{
                                b.className = 'px-2 py-0.5 rounded text-xs font-bold bg-emerald-950 text-emerald-400 border border-emerald-800';
                                b.textContent = 'ONLINE';
                            }}
                            const pEl = document.getElementById('soroushPhoneDisplay');
                            if (pEl) pEl.textContent = data.masked_phone || phone || 'Ù…ØªØµÙ„';
                            const btnBox = document.getElementById('soroushBtnContainer');
                            if (btnBox) {{
                                const dcBtn = document.createElement('button');
                                dcBtn.type = 'button';
                                dcBtn.onclick = function() {{ disconnectSession('soroush'); }};
                                dcBtn.className = 'w-full py-1.5 px-2 rounded-lg bg-rose-950/60 hover:bg-rose-900/80 text-rose-300 border border-rose-800 text-[11px] font-bold transition flex items-center justify-center gap-1.5';
                                dcBtn.innerHTML = '<svg class="w-3.5 h-3.5 stroke-[1.75]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M5.636 5.636a9 9 0 1012.728 0M12 3v9" /></svg><span>Ù‚Ø·Ø¹ Ø§ØªØµØ§Ù„ / Ø®Ø±ÙˆØ¬</span>';
                                btnBox.innerHTML = '';
                                btnBox.appendChild(dcBtn);
                            }}
                            showToast('Ø³Ø´Ù† Ø³Ø±ÙˆØ´â€ŒÙ¾Ù„Ø§Ø³ Ø¨Ø§ Ù…ÙˆÙÙ‚ÛŒØª Ø«Ø¨Øª Ùˆ ÙØ¹Ø§Ù„ Ø´Ø¯.');
                            closeSoroushLoginModal();
                        }} else {{
                            if (errBox) {{
                                errBox.textContent = data.error || 'Ø®Ø·Ø§ Ø¯Ø± Ø«Ø¨Øª ØªÙˆÚ©Ù†';
                                errBox.classList.remove('hidden');
                            }} else {{
                                showToast(data.error || 'Ø®Ø·Ø§ Ø¯Ø± Ø«Ø¨Øª ØªÙˆÚ©Ù†');
                            }}
                        }}
                    }} catch (e) {{
                        showToast('Ø®Ø·Ø§: ' + e.message);
                    }} finally {{
                        if (btn) {{ btn.disabled = false; btn.textContent = 'Ø°Ø®ÛŒØ±Ù‡ Ù…Ø³ØªÙ‚ÛŒÙ… ØªÙˆÚ©Ù† Ùˆ ÙØ¹Ø§Ù„â€ŒØ³Ø§Ø²ÛŒ Ø³Ø´Ù†'; }}
                    }}
                }}

                window.openSoroushLoginModal = openSoroushLoginModal;
                window.closeSoroushLoginModal = closeSoroushLoginModal;
                window.switchSoroushTab = switchSoroushTab;
                window.resetSoroushLoginForm = resetSoroushLoginForm;
                window.submitSoroushPhone = submitSoroushPhone;
                window.submitSoroushCode = submitSoroushCode;
                window.submitSoroushManualToken = submitSoroushManualToken;

                let allLoadedUsers = [];

                async function loadUsersData() {{
                    const tbody = document.getElementById('usersTableBody');
                    if (!tbody) return;
                    tbody.innerHTML = '<tr><td colspan="8" class="p-6 text-center text-slate-400 font-sans">Ø¯Ø± Ø­Ø§Ù„ Ø¯Ø±ÛŒØ§ÙØª ÙÙ‡Ø±Ø³Øª Ø§Ø¹Ø¶Ø§ Ùˆ Ø®Ø±ÛŒØ¯Ø§Ø±Ø§Ù†...</td></tr>';
                    try {{
                        const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                        const res = await fetch('/api/users', {{
                            headers: {{ 'Authorization': 'Bearer ' + pwd, 'X-Admin-Password': pwd }}
                        }});
                        const data = await res.json();
                        const users = data.users || [];
                        const customers = data.customers || [];
                        const rawList = (users && users.length) ? users : customers;
                        allLoadedUsers = rawList.map(c => {{
                            const p = (c.platform || 'bale').toLowerCase();
                            const uid = c.user_id || c.id || c.chat_id || '';
                            let uname = c.username || c.customer_name || c.name || c.full_name || '';
                            if (!uname || uname === 'undefined' || uname === 'None') {{
                                if (p.includes('tele')) uname = 'Ú©Ø§Ø±Ø¨Ø± ØªÙ„Ú¯Ø±Ø§Ù…';
                                else if (p.includes('soroush')) uname = 'Ú©Ø§Ø±Ø¨Ø± Ø³Ø±ÙˆØ´â€ŒÙ¾Ù„Ø§Ø³';
                                else if (p.includes('rubika')) uname = 'Ú©Ø§Ø±Ø¨Ø± Ø±ÙˆØ¨ÛŒÚ©Ø§';
                                else uname = 'Ú©Ø§Ø±Ø¨Ø± Ø¨Ù„Ù‡';
                            }}
                            return {{
                                platform: p,
                                user_id: uid,
                                username: uname,
                                full_name: c.full_name || uname,
                                phone: (c.phone && c.phone !== 'None' && c.phone !== 'undefined') ? c.phone : '',
                                referred_by: (c.referred_by && c.referred_by !== 'None' && c.referred_by !== 'undefined') ? c.referred_by : '',
                                wallet_balance: Number(c.wallet_balance) || 0,
                                commitment_signed: !!c.commitment_signed,
                                is_vip: Boolean(c.is_vip || (c.vip_until && new Date(c.vip_until) > new Date())),
                                vip_until: c.vip_until || '',
                                purchased_courses: c.purchased_courses || [],
                                successful_invites: c.successful_invites || 0
                            }};
                        }});

                        const statTotal = document.getElementById('statTotalUsers');
                        if (statTotal) statTotal.innerText = allLoadedUsers.length;

                        const refUsersCount = allLoadedUsers.filter(u => u.referred_by).length;
                        const statRef = document.getElementById('statRefUsers');
                        if (statRef) statRef.innerText = refUsersCount;

                        const totalWallet = allLoadedUsers.reduce((acc, u) => acc + (Number(u.wallet_balance) || 0), 0);
                        const statWallet = document.getElementById('statTotalWallet');
                        if (statWallet) statWallet.innerText = totalWallet.toLocaleString('fa-IR') + ' ØªÙˆÙ…Ø§Ù†';

                        renderUsersTable(allLoadedUsers);
                    }} catch (err) {{
                        console.error('loadUsersData error:', err);
                        tbody.innerHTML = '<tr><td colspan="9" class="p-6 text-center text-rose-400 font-sans">Ø®Ø·Ø§ Ø¯Ø± Ø¨Ø§Ø±Ú¯Ø°Ø§Ø±ÛŒ ÙÙ‡Ø±Ø³Øª Ú©Ø§Ø±Ø¨Ø±Ø§Ù†</td></tr>';
                    }}
                }}
                window.loadUsersData = loadUsersData;

                async function saveVipHubSettings() {{
                    const priceInput = document.getElementById('viphub_price');
                    const daysInput = document.getElementById('viphub_days');
                    const cardInput = document.getElementById('viphub_card');
                    const promoInput = document.getElementById('viphub_promo');
                    const btn = document.getElementById('btnSaveVipHub');
                    
                    const price = priceInput ? priceInput.value.replace(/[,ØŒ\\s]/g, '') : '111000';
                    const days = daysInput ? daysInput.value.trim() : '30';
                    const card = cardInput ? cardInput.value.trim() : '';
                    const promo = promoInput ? promoInput.value.trim() : '';

                    if (btn) btn.innerHTML = '<span>â³</span> Ø¯Ø± Ø­Ø§Ù„ Ø°Ø®ÛŒØ±Ù‡...';
                    try {{
                        const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                        const res = await fetch('/api/settings/save', {{
                            method: 'POST',
                            headers: {{ 'Content-Type': 'application/json; charset=utf-8', 'Authorization': 'Bearer ' + pwd, 'X-Admin-Password': pwd }},
                            body: JSON.stringify({{
                                vip_monthly_price: parseInt(price) || 111000,
                                vip_duration_days: parseInt(days) || 30,
                                vip_card_number: card,
                                vip_promo_text: promo,
                                admin_password: pwd
                            }})
                        }});
                        const data = await res.json();
                        if (data.ok) {{
                            showToast('ØªÙ†Ø¸ÛŒÙ…Ø§Øª Ù¾Ù„Ù† Ù¾Ø±ÛŒÙ…ÛŒÙˆÙ… Ø¨Ø§ Ù…ÙˆÙÙ‚ÛŒØª Ø°Ø®ÛŒØ±Ù‡ Ø´Ø¯.');
                        }} else {{
                            showToast('Ø®Ø·Ø§ Ø¯Ø± Ø°Ø®ÛŒØ±Ù‡ ØªÙ†Ø¸ÛŒÙ…Ø§Øª: ' + (data.error || 'Ù†Ø§Ù…Ø´Ø®Øµ'));
                        }}
                    }} catch (e) {{
                        showToast('Ø®Ø·Ø§ÛŒ Ø§Ø±ØªØ¨Ø§Ø·: ' + e.message);
                    }} finally {{
                        if (btn) btn.innerHTML = '<svg class="w-4 h-4 stroke-[2]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5"/></svg><span>Ø°Ø®ÛŒØ±Ù‡ ÙÙˆØ±ÛŒ ØªÙ†Ø¸ÛŒÙ…Ø§Øª Ù¾Ø±ÛŒÙ…ÛŒÙˆÙ…</span>';
                    }}
                }}
                window.saveVipHubSettings = saveVipHubSettings;

                function renderUsersTable(users) {{
                    const tbody = document.getElementById('usersTableBody');
                    if (!tbody) return;
                    if (!users || users.length === 0) {{
                        tbody.innerHTML = '<tr><td colspan="9" class="p-6 text-center text-slate-500 font-sans">Ù‡ÛŒÚ† Ú©Ø§Ø±Ø¨Ø±ÛŒ Ø«Ø¨Øª Ù†Ø´Ø¯Ù‡ Ø§Ø³Øª.</td></tr>';
                        return;
                    }}
                    tbody.innerHTML = users.map(u => {{
                        try {{
                            if (!u) return '';
                            const p = (u.platform || 'bale').toLowerCase();
                            let platformBadge = '';
                            if (p.includes('tele')) {{
                                platformBadge = '<span class="px-2 py-0.5 rounded text-[10px] bg-cyan-950 text-cyan-400 border border-cyan-800 font-sans inline-flex items-center gap-1"><svg class="w-3 h-3 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"/></svg> ØªÙ„Ú¯Ø±Ø§Ù…</span>';
                            }} else if (p.includes('soroush')) {{
                                platformBadge = '<span class="px-2 py-0.5 rounded text-[10px] bg-sky-950 text-sky-400 border border-sky-800 font-sans inline-flex items-center gap-1"><svg class="w-3 h-3 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/></svg> Ø³Ø±ÙˆØ´â€ŒÙ¾Ù„Ø§Ø³</span>';
                            }} else if (p.includes('rubika')) {{
                                platformBadge = '<span class="px-2 py-0.5 rounded text-[10px] bg-purple-950 text-purple-400 border border-purple-800 font-sans inline-flex items-center gap-1"><svg class="w-3 h-3 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"/></svg> Ø±ÙˆØ¨ÛŒÚ©Ø§</span>';
                            }} else {{
                                platformBadge = '<span class="px-2 py-0.5 rounded text-[10px] bg-emerald-950 text-emerald-400 border border-emerald-800 font-sans inline-flex items-center gap-1"><svg class="w-3 h-3 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg> Ø¨Ù„Ù‡</span>';
                            }}
                            const isUserVip = Boolean(u.is_vip || (u.vip_until && new Date(u.vip_until) > new Date()));
                            let vipBadge = '<span class="px-2 py-0.5 rounded text-[10px] bg-slate-800 text-slate-400 border border-slate-700 font-sans">Ø¹Ø§Ø¯ÛŒ</span>';
                            if (isUserVip) {{
                                const expDate = u.vip_until_jalali ? u.vip_until_jalali : ((u.vip_until || '').slice(0, 10));
                                vipBadge = '<span class="px-2 py-0.5 rounded text-[10px] bg-amber-500/10 text-amber-300 border border-amber-500/30 font-sans inline-flex items-center gap-1" title="Ø§Ù†Ù‚Ø¶Ø§: ' + escapeHtml(u.vip_until || '') + '">' +
                                    '<svg class="w-3 h-3 text-amber-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z"/></svg>' +
                                    ' Ù¾Ø±ÛŒÙ…ÛŒÙˆÙ… (' + escapeHtml(expDate) + ')' +
                                '</span>';
                            }}
                            const phone = u.phone ? ('<span dir="ltr">' + escapeHtml(u.phone) + '</span>') : '<span class="text-slate-600 font-sans">-</span>';
                            const name = escapeHtml(u.username || ('Ú©Ø§Ø±Ø¨Ø± ' + (u.user_id || '')));
                            const ref = u.referred_by ? ('<span class="text-indigo-400" dir="ltr">' + escapeHtml(String(u.referred_by)) + '</span>') : '<span class="text-slate-600 font-sans">Ù…Ø³ØªÙ‚ÛŒÙ…</span>';
                            const wallet = (Number(u.wallet_balance) || 0).toLocaleString('fa-IR') + ' Øª';
                            const commitment = u.commitment_signed 
                                ? '<span class="text-emerald-400 font-sans">Ø§Ù…Ø¶Ø§ Ø´Ø¯Ù‡ âœ“</span>'
                                : '<span class="text-slate-500 font-sans">Ø¯Ø± Ø§Ù†ØªØ¸Ø§Ø±</span>';
                            const userIdClean = escapeHtml(String(u.user_id || '-'));
                            
                            const vipBtn = isUserVip
                                ? '<div class="inline-flex items-center gap-1">' +
                                    '<button type="button" data-user-action="grant_10" data-user-id="' + userIdClean + '" title="ØªÙ…Ø¯ÛŒØ¯ Û±Û° Ø±ÙˆØ²Ù‡" class="px-2 py-1 rounded-lg border border-emerald-500/40 text-emerald-400 hover:bg-emerald-500/20 transition-all font-sans text-xs inline-flex items-center gap-0.5 cursor-pointer font-bold">' +
                                        '<span>+Û±Û°</span>' +
                                    '</button>' +
                                    '<button type="button" data-user-action="grant_30" data-user-id="' + userIdClean + '" title="ØªÙ…Ø¯ÛŒØ¯ Û³Û° Ø±ÙˆØ²Ù‡" class="px-2 py-1 rounded-lg border border-cyan-500/40 text-cyan-400 hover:bg-cyan-500/20 transition-all font-sans text-xs inline-flex items-center gap-0.5 cursor-pointer font-bold">' +
                                        '<span>+Û³Û°</span>' +
                                    '</button>' +
                                    '<button type="button" data-user-action="revoke_vip" data-user-id="' + userIdClean + '" title="Ù„ØºÙˆ Ø§Ø´ØªØ±Ø§Ú© Ù¾Ø±ÛŒÙ…ÛŒÙˆÙ…" class="px-2 py-1 rounded-lg border border-amber-500/40 text-amber-400 hover:bg-amber-500/20 transition-all font-sans text-xs inline-flex items-center gap-0.5 cursor-pointer">' +
                                        '<span>Ù„ØºÙˆ</span>' +
                                    '</button>' +
                                  '</div>'
                                : '<div class="inline-flex items-center gap-1">' +
                                    '<button type="button" data-user-action="grant_10" data-user-id="' + userIdClean + '" title="Ø§Ø¹Ø·Ø§ÛŒ Û±Û° Ø±ÙˆØ²Ù‡" class="px-2 py-1 rounded-lg border border-emerald-500/40 text-emerald-400 hover:bg-emerald-500/20 transition-all font-sans text-xs inline-flex items-center gap-0.5 cursor-pointer font-bold">' +
                                        '<span>+Û±Û° Ø±ÙˆØ²</span>' +
                                    '</button>' +
                                    '<button type="button" data-user-action="grant_30" data-user-id="' + userIdClean + '" title="Ø§Ø¹Ø·Ø§ÛŒ Û³Û° Ø±ÙˆØ²Ù‡" class="px-2 py-1 rounded-lg border border-cyan-500/40 text-cyan-400 hover:bg-cyan-500/20 transition-all font-sans text-xs inline-flex items-center gap-0.5 cursor-pointer font-bold">' +
                                        '<span>+Û³Û° Ø±ÙˆØ²</span>' +
                                    '</button>' +
                                  '</div>';

                            return '<tr class="hover:bg-white/[0.03] transition">' +
                                '<td class="p-3">' + platformBadge + '</td>' +
                                '<td class="p-3 text-cyan-300 font-mono" dir="ltr">' + userIdClean + '</td>' +
                                '<td class="p-3 text-slate-200 font-sans font-medium">' + name + '</td>' +
                                '<td class="p-3 text-slate-300">' + phone + '</td>' +
                                '<td class="p-3">' + vipBadge + '</td>' +
                                '<td class="p-3">' + ref + '</td>' +
                                '<td class="p-3 text-amber-400 font-bold">' + wallet + '</td>' +
                                '<td class="p-3 text-xs">' + commitment + '</td>' +
                                '<td class="p-3 text-center">' +
                                    '<div class="inline-flex items-center gap-1.5">' +
                                        '<button type="button" data-user-action="view_profile" data-user-id="' + userIdClean + '" title="Ù…Ø´Ø§Ù‡Ø¯Ù‡ Ù¾Ø±ÙˆÙØ§ÛŒÙ„ Ùˆ Ø¯ÙˆØ±Ù‡â€ŒÙ‡Ø§" class="p-1.5 rounded-lg border border-slate-700 text-slate-300 hover:bg-slate-800 transition-all font-sans text-xs inline-flex items-center gap-1 cursor-pointer">' +
                                            '<svg class="w-3.5 h-3.5 pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/></svg>' +
                                        '</button>' +
                                        vipBtn +
                                        '<button type="button" data-user-action="delete_user" data-user-id="' + userIdClean + '" title="Ø­Ø°Ù Ø¯Ø§Ø¦Ù… Ú©Ø§Ø±Ø¨Ø±" class="p-1.5 rounded-lg border border-rose-500/40 text-rose-400 hover:bg-rose-500/20 transition-all font-sans text-xs inline-flex items-center gap-1 cursor-pointer">' +
                                            '<svg class="w-3.5 h-3.5 pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>' +
                                        '</button>' +
                                    '</div>' +
                                '</td>' +
                            '</tr>';
                        }} catch (rowErr) {{
                            console.warn('Error rendering user row:', rowErr, u);
                            return '';
                        }}
                    }}).join('');

                    if (!tbody._delegated) {{
                        tbody._delegated = true;
                        tbody.addEventListener('click', function(e) {{
                            const btn = e.target.closest('button[data-user-action]');
                            if (!btn) return;
                            const act = btn.getAttribute('data-user-action');
                            const uid = btn.getAttribute('data-user-id');
                            if (!uid || uid === '-') return;
                            if (act === 'revoke_vip') toggleUserVip(uid, 'revoke');
                            else if (act === 'grant_10') toggleUserVip(uid, 'grant_10');
                            else if (act === 'grant_30' || act === 'grant_vip') toggleUserVip(uid, 'grant_30');
                            else if (act === 'view_profile') viewUserProfile(uid);
                            else if (act === 'delete_user') deleteUserRow(uid);
                        }});
                    }}
                }}
                window.renderUsersTable = renderUsersTable;

                async function toggleUserVip(userId, action) {{
                    if (!userId || userId === '-') return;
                    let actName = 'ØªÙ…Ø¯ÛŒØ¯ Û³Û° Ø±ÙˆØ²Ù‡';
                    let reqDays = 30;
                    if (action === 'revoke') actName = 'Ù„ØºÙˆ';
                    else if (action === 'grant_10') {{ actName = 'Ø§Ø¹Ø·Ø§ / ØªÙ…Ø¯ÛŒØ¯ Û±Û° Ø±ÙˆØ²Ù‡'; reqDays = 10; }}
                    else if (action === 'grant_30') {{ actName = 'Ø§Ø¹Ø·Ø§ / ØªÙ…Ø¯ÛŒØ¯ Û³Û° Ø±ÙˆØ²Ù‡'; reqDays = 30; }}

                    if (!confirm('Ø¢ÛŒØ§ Ø§Ø² ' + actName + ' Ø§Ø´ØªØ±Ø§Ú© Ù¾Ø±ÛŒÙ…ÛŒÙˆÙ… Ø¨Ø±Ø§ÛŒ Ú©Ø§Ø±Ø¨Ø± ' + userId + ' Ø§Ø·Ù…ÛŒÙ†Ø§Ù† Ø¯Ø§Ø±ÛŒØ¯ØŸ')) return;
                    try {{
                        const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                        const res = await fetch('/api/users/toggle_vip', {{
                            method: 'POST',
                            headers: {{ 'Content-Type': 'application/json; charset=utf-8', 'Authorization': 'Bearer ' + pwd, 'X-Admin-Password': pwd }},
                            body: JSON.stringify({{ user_id: userId, action: action, days: reqDays, admin_password: pwd }})
                        }});
                        const data = await res.json();
                        if (data.ok) {{
                            const uIdx = allLoadedUsers.findIndex(u => String(u.user_id) === String(userId) || String(u.phone) === String(userId));
                            if (uIdx !== -1) {{
                                allLoadedUsers[uIdx].is_vip = data.is_vip;
                                allLoadedUsers[uIdx].vip_until = data.vip_until;
                                if (data.vip_until_jalali) allLoadedUsers[uIdx].vip_until_jalali = data.vip_until_jalali;
                            }}
                            renderUsersTable(allLoadedUsers);
                        }} else {{
                            showToast('Ø®Ø·Ø§: ' + (data.error || 'Ø¹Ù…Ù„ÛŒØ§Øª Ù†Ø§Ù…ÙˆÙÙ‚ Ø¨ÙˆØ¯'));
                        }}
                    }} catch (e) {{
                        showToast('Ø®Ø·Ø§ÛŒ Ø§Ø±ØªØ¨Ø§Ø·: ' + e.message);
                    }}
                }}
                window.toggleUserVip = toggleUserVip;

                async function viewUserProfile(userId) {{
                    if (!userId || userId === '-') return;
                    const modal = document.getElementById('userProfileModal');
                    const content = document.getElementById('userProfileModalContent');
                    if (!modal || !content) return;
                    content.innerHTML = '<div class="p-8 text-center text-slate-400">Ø¯Ø± Ø­Ø§Ù„ Ø¯Ø±ÛŒØ§ÙØª Ø§Ø·Ù„Ø§Ø¹Ø§Øª Ø¬Ø§Ù…Ø¹ Ú©Ø§Ø±Ø¨Ø±...</div>';
                    modal.classList.remove('hidden');
                    try {{
                        const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                        const res = await fetch('/api/users/profile', {{
                            method: 'POST',
                            headers: {{ 'Content-Type': 'application/json; charset=utf-8', 'Authorization': 'Bearer ' + pwd, 'X-Admin-Password': pwd }},
                            body: JSON.stringify({{ user_id: userId, admin_password: pwd }})
                        }});
                        const data = await res.json();
                        if (data.ok && data.user) {{
                            const u = data.user;
                            const isVip = Boolean(u.is_vip || (u.vip_until && new Date(u.vip_until) > new Date()));
                            const expDate = (u.vip_until || '').slice(0, 10);
                            const vipText = isVip ? ('<span class="text-amber-400 font-bold">ðŸ’Ž Ø§Ø´ØªØ±Ø§Ú© Ù¾Ø±ÛŒÙ…ÛŒÙˆÙ… ØªØ§ ' + escapeHtml(expDate) + '</span>') : '<span class="text-slate-500">Ø¹Ø§Ø¯ÛŒ (ÙØ§Ù‚Ø¯ Ø§Ø´ØªØ±Ø§Ú©)</span>';
                            const coursesCount = (u.purchased_courses || []).length;
                            const coursesList = (u.purchased_courses && u.purchased_courses.length) ? u.purchased_courses.map(escapeHtml).join('ØŒ ') : 'Ù‡Ù†ÙˆØ² Ø¯ÙˆØ±Ù‡â€ŒØ§ÛŒ Ø®Ø±ÛŒØ¯Ø§Ø±ÛŒ Ù†Ø´Ø¯Ù‡ Ø§Ø³Øª.';
                            const avatarLetter = escapeHtml((u.full_name || u.username || 'U')[0].toUpperCase());
                            const userName = escapeHtml(u.full_name || u.username || 'Ú©Ø§Ø±Ø¨Ø±');
                            const userPlatform = escapeHtml(u.platform || 'bale');
                            const userUid = escapeHtml(u.user_id || '-');
                            const userPhone = escapeHtml(u.phone || 'ÙØ§Ù‚Ø¯ Ø´Ù…Ø§Ø±Ù‡');
                            const userWallet = Number(u.wallet_balance || 0).toLocaleString('fa-IR') + ' ØªÙˆÙ…Ø§Ù†';
                            const userInvites = (u.successful_invites || 0) + ' Ù†ÙØ±';

                            content.innerHTML = 
                                '<div class="space-y-4 text-xs font-sans">' +
                                    '<div class="flex items-center justify-between pb-3 border-b border-slate-700/60">' +
                                        '<div class="flex items-center gap-3">' +
                                            '<div class="w-10 h-10 rounded-xl bg-cyan-500/10 text-cyan-400 flex items-center justify-center font-bold text-sm">' +
                                                avatarLetter +
                                            '</div>' +
                                            '<div>' +
                                                '<h4 class="font-bold text-sm text-white">' + userName + '</h4>' +
                                                '<span class="text-slate-400 font-mono text-[11px]">' + userPlatform + ' | ' + userUid + '</span>' +
                                            '</div>' +
                                        '</div>' +
                                        '<div class="text-left">' + vipText + '</div>' +
                                    '</div>' +
                                    '<div class="grid grid-cols-2 gap-3 text-right">' +
                                        '<div class="p-3 rounded-xl  border border-slate-800">' +
                                            '<span class="text-slate-500 block text-[11px]">Ø´Ù…Ø§Ø±Ù‡ ØªÙ…Ø§Ø³:</span>' +
                                            '<span class="font-mono text-slate-200" dir="ltr">' + userPhone + '</span>' +
                                        '</div>' +
                                        '<div class="p-3 rounded-xl  border border-slate-800">' +
                                            '<span class="text-slate-500 block text-[11px]">Ù…ÙˆØ¬ÙˆØ¯ÛŒ Ú©ÛŒÙ Ù¾ÙˆÙ„:</span>' +
                                            '<span class="font-mono text-amber-400 font-bold">' + userWallet + '</span>' +
                                        '</div>' +
                                        '<div class="p-3 rounded-xl  border border-slate-800">' +
                                            '<span class="text-slate-500 block text-[11px]">Ø¯ÙˆØ±Ù‡â€ŒÙ‡Ø§ÛŒ Ø«Ø¨Øªâ€ŒØ´Ø¯Ù‡:</span>' +
                                            '<span class="font-bold text-emerald-400">' + coursesCount + ' Ø¯ÙˆØ±Ù‡</span>' +
                                        '</div>' +
                                        '<div class="p-3 rounded-xl  border border-slate-800">' +
                                            '<span class="text-slate-500 block text-[11px]">Ø¯Ø¹ÙˆØªâ€ŒÙ‡Ø§ÛŒ Ù…ÙˆÙÙ‚ Ø±ÙØ±Ø§Ù„:</span>' +
                                            '<span class="font-bold text-cyan-400">' + userInvites + '</span>' +
                                        '</div>' +
                                    '</div>' +
                                    '<div class="p-3 rounded-xl  border border-slate-800">' +
                                        '<span class="text-slate-500 block text-[11px] mb-1">Ø¯ÙˆØ±Ù‡â€ŒÙ‡Ø§ÛŒ Ø®Ø±ÛŒØ¯Ø§Ø±ÛŒâ€ŒØ´Ø¯Ù‡:</span>' +
                                        '<span class="text-slate-300 font-sans">' + coursesList + '</span>' +
                                    '</div>' +
                                    '<div class="flex justify-end gap-2 pt-2">' +
                                        '<button type="button" onclick="closeUserProfileModal()" class="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-bold transition cursor-pointer">Ø¨Ø³ØªÙ†</button>' +
                                    '</div>' +
                                '</div>';
                        }} else {{
                            content.innerHTML = '<div class="p-6 text-center text-rose-400">Ø§Ø·Ù„Ø§Ø¹Ø§Øª Ú©Ø§Ø±Ø¨Ø± ÛŒØ§ÙØª Ù†Ø´Ø¯.</div>';
                        }}
                    }} catch (err) {{
                        content.innerHTML = '<div class="p-6 text-center text-rose-400">Ø®Ø·Ø§: ' + escapeHtml(err.message) + '</div>';
                    }}
                }}
                window.viewUserProfile = viewUserProfile;

                function closeUserProfileModal() {{
                    const modal = document.getElementById('userProfileModal');
                    if (modal) modal.classList.add('hidden');
                }}
                window.closeUserProfileModal = closeUserProfileModal;

                function switchProductSubTab(subTabId) {{
                    ['courses', 'audiobooks', 'vip'].forEach(id => {{
                        const contentEl = document.getElementById('subtab-prods-' + id + '-content');
                        const btnEl = document.getElementById('btn-subtab-prods-' + id);
                        if (contentEl) {{
                            if (id === subTabId) contentEl.classList.remove('hidden');
                            else contentEl.classList.add('hidden');
                        }}
                        if (btnEl) {{
                            if (id === subTabId) {{
                                btnEl.style.background = 'var(--accent-color)';
                                btnEl.style.color = '#fff';
                                btnEl.classList.add('font-bold');
                                btnEl.classList.remove('text-slate-400');
                            }} else {{
                                btnEl.style.background = 'transparent';
                                btnEl.style.color = '';
                                btnEl.classList.remove('font-bold');
                                btnEl.classList.add('text-slate-400');
                            }}
                        }}
                    }});
                }}
                window.switchProductSubTab = switchProductSubTab;

                /**
                 * Ù…Ø¯ÛŒØ±ÛŒØª Ú©Ø´ÛŒØ¯Ù† Ùˆ Ø±Ù‡Ø§ Ú©Ø±Ø¯Ù† (Drag & Drop) Û³ Ø³Ø§Ø¨â€ŒØªØ¨ Ù…Ø­ØµÙˆÙ„Ø§Øª Ùˆ Ù…Ø§Ù†Ø¯Ú¯Ø§Ø±ÛŒ Ú†ÛŒØ¯Ù…Ø§Ù† Ø¯Ø± localStorage
                 * ÙˆØ±ÙˆØ¯ÛŒ: Ù†Ø¯Ø§Ø±Ø¯
                 * Ø®Ø±ÙˆØ¬ÛŒ: Ù†Ø¯Ø§Ø±Ø¯ (Ø¨Ù‡â€ŒØ±ÙˆØ²Ø±Ø³Ø§Ù†ÛŒ DOM Ùˆ Ø±ÙˆÛŒØ¯Ø§Ø¯Ù‡Ø§)
                 */
                function initProductSubtabsDragAndDrop() {{
                    const container = document.getElementById('productSubtabsContainer');
                    if (!container) return;

                    try {{
                        const savedOrder = JSON.parse(localStorage.getItem('unfinit_products_subtabs_order') || '[]');
                        if (Array.isArray(savedOrder) && savedOrder.length > 0) {{
                            const btnMap = {{}};
                            const buttons = Array.from(container.querySelectorAll('.prod-subtab-btn'));
                            buttons.forEach(btn => {{
                                const subtab = btn.getAttribute('data-subtab');
                                if (subtab) btnMap[subtab] = btn;
                            }});
                            savedOrder.forEach(subtab => {{
                                if (btnMap[subtab]) {{
                                    container.appendChild(btnMap[subtab]);
                                }}
                            }});
                        }}
                    }} catch (e) {{
                        console.warn('Error loading product subtabs order:', e);
                    }}

                    let draggedBtn = null;

                    container.addEventListener('dragstart', (e) => {{
                        const target = e.target.closest('.prod-subtab-btn');
                        if (!target) return;
                        draggedBtn = target;
                        e.dataTransfer.effectAllowed = 'move';
                        e.dataTransfer.setData('text/plain', target.getAttribute('data-subtab') || '');
                        target.classList.add('opacity-40', 'scale-95');
                    }});

                    container.addEventListener('dragend', (e) => {{
                        const target = e.target.closest('.prod-subtab-btn');
                        if (target) target.classList.remove('opacity-40', 'scale-95');
                        draggedBtn = null;
                        saveProductSubtabsOrder();
                    }});

                    container.addEventListener('dragover', (e) => {{
                        e.preventDefault();
                        e.dataTransfer.dropEffect = 'move';
                        const target = e.target.closest('.prod-subtab-btn');
                        if (target && target !== draggedBtn) {{
                            const rect = target.getBoundingClientRect();
                            const next = (e.clientX - rect.left) / (rect.right - rect.left) > 0.5;
                            container.insertBefore(draggedBtn, next ? target.nextSibling : target);
                        }}
                    }});

                    function saveProductSubtabsOrder() {{
                        const buttons = Array.from(container.querySelectorAll('.prod-subtab-btn'));
                        const order = buttons.map(b => b.getAttribute('data-subtab')).filter(Boolean);
                        localStorage.setItem('unfinit_products_subtabs_order', JSON.stringify(order));
                    }}
                }}
                window.initProductSubtabsDragAndDrop = initProductSubtabsDragAndDrop;

                function inlineRenameTab(element, tabId) {{
                    const currentText = element.textContent.trim();
                    const input = document.createElement('input');
                    input.type = 'text';
                    input.value = currentText;
                    input.className = 'w-full  text-white text-xs px-2 py-1 rounded border border-cyan-500 focus:outline-none';
                    
                    const saveRename = async () => {{
                        const newTitle = input.value.trim();
                        if (newTitle && newTitle !== currentText) {{
                            element.textContent = newTitle;
                            try {{
                                const renames = JSON.parse(localStorage.getItem('unfinit_tab_renames') || '{{}}');
                                renames[tabId] = newTitle;
                                localStorage.setItem('unfinit_tab_renames', JSON.stringify(renames));
                            }} catch (e) {{}}
                            try {{
                                const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                                await fetch('/api/settings/rename', {{
                                    method: 'POST',
                                    headers: {{ 'Content-Type': 'application/json; charset=utf-8', 'Authorization': 'Bearer ' + pwd, 'X-Admin-Password': pwd }},
                                    body: JSON.stringify({{ tab_id: tabId, title: newTitle, admin_password: pwd }})
                                }});
                            }} catch (e) {{
                                console.warn('Failed to save tab rename:', e);
                            }}
                        }} else {{
                            element.textContent = currentText;
                        }}
                    }};

                    input.onblur = saveRename;
                    input.onkeydown = (e) => {{
                        if (e.key === 'Enter') {{
                            input.blur();
                        }} else if (e.key === 'Escape') {{
                            element.textContent = currentText;
                        }}
                    }};

                    element.textContent = '';
                    element.appendChild(input);
                    input.focus();
                    input.select();
                }}
                window.inlineRenameTab = inlineRenameTab;

                function restoreTabRenames() {{
                    try {{
                        const renames = JSON.parse(localStorage.getItem('unfinit_tab_renames') || '{{}}');
                        for (const [tabId, title] of Object.entries(renames)) {{
                            const btn = document.querySelector(`.sidebar-nav-btn[data-tab="${{tabId}}"] span.text-right`) ||
                                        document.querySelector(`.sidebar-nav-btn[data-tab="${{tabId}}"] span`);
                            if (btn && title) {{
                                btn.textContent = title;
                            }}
                        }}
                    }} catch (e) {{}}
                }}
                window.restoreTabRenames = restoreTabRenames;

                async function deleteUserRow(userId) {{
                    if (!userId || userId === '-' || userId === 'undefined') return;
                    if (!confirm(`Ø¢ÛŒØ§ Ø§Ø² Ø­Ø°Ù Ú©Ø§Ù…Ù„ Ú©Ø§Ø±Ø¨Ø± Ø¨Ø§ Ø´Ù†Ø§Ø³Ù‡ ${{userId}} Ø§Ø² Ù¾Ø§ÛŒÚ¯Ø§Ù‡ Ø¯Ø§Ø¯Ù‡ Ø§Ø·Ù…ÛŒÙ†Ø§Ù† Ø¯Ø§Ø±ÛŒØ¯ØŸ`)) return;
                    try {{
                        const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                        const res = await fetch('/api/users/delete', {{
                            method: 'POST',
                            headers: {{ 'Content-Type': 'application/json; charset=utf-8', 'Authorization': 'Bearer ' + pwd, 'X-Admin-Password': pwd }},
                            body: JSON.stringify({{ user_id: userId, admin_password: pwd }})
                        }});
                        const data = await res.json();
                        if (data.ok) {{
                            allLoadedUsers = allLoadedUsers.filter(u => String(u.user_id) !== String(userId));
                            renderUsersTable(allLoadedUsers);
                            const statTotal = document.getElementById('statTotalUsers');
                            if (statTotal) statTotal.innerText = allLoadedUsers.length;
                        }} else {{
                            showToast('Ø®Ø·Ø§ Ø¯Ø± Ø­Ø°Ù Ú©Ø§Ø±Ø¨Ø±: ' + (data.error || 'Ù†Ø§Ù…Ø´Ø®Øµ'));
                        }}
                    }} catch (e) {{
                        showToast('Ø®Ø·Ø§ÛŒ Ø§Ø±ØªØ¨Ø§Ø·: ' + e.message);
                    }}
                }}
                window.deleteUserRow = deleteUserRow;

                async function purgeTestUsers() {{
                    if (!confirm('Ù‡Ø´Ø¯Ø§Ø±: Ø¢ÛŒØ§ Ù…Ø·Ù…Ø¦Ù† Ù‡Ø³ØªÛŒØ¯ Ú©Ù‡ Ù…ÛŒâ€ŒØ®ÙˆØ§Ù‡ÛŒØ¯ ØªÙ…Ø§Ù… Ú©Ø§Ø±Ø¨Ø±Ø§Ù† Ø¢Ø²Ù…Ø§ÛŒØ´ÛŒ Ùˆ Ø³Ø§Ø®ØªÚ¯ÛŒ Ø±Ø§ Ù¾Ø§Ú©Ø³Ø§Ø²ÛŒ Ú©Ù†ÛŒØ¯ØŸ')) return;
                    try {{
                        const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                        const res = await fetch('/api/users/purge_test', {{
                            method: 'POST',
                            headers: {{ 'Content-Type': 'application/json; charset=utf-8', 'Authorization': 'Bearer ' + pwd, 'X-Admin-Password': pwd }},
                            body: JSON.stringify({{ admin_password: pwd }})
                        }});
                        const data = await res.json();
                        if (data.ok) {{
                            showToast(`Ù¾Ø§Ú©Ø³Ø§Ø²ÛŒ Ø§Ù†Ø¬Ø§Ù… Ø´Ø¯. ${{data.deleted_count || 0}} Ú©Ø§Ø±Ø¨Ø± Ø¢Ø²Ù…Ø§ÛŒØ´ÛŒ Ø­Ø°Ù Ø´Ø¯Ù†Ø¯.`);
                            loadUsersData();
                        }} else {{
                            showToast('Ø®Ø·Ø§ Ø¯Ø± Ù¾Ø§Ú©Ø³Ø§Ø²ÛŒ: ' + (data.error || 'Ù†Ø§Ù…Ø´Ø®Øµ'));
                        }}
                    }} catch (e) {{
                        showToast('Ø®Ø·Ø§ÛŒ Ø§Ø±ØªØ¨Ø§Ø·: ' + e.message);
                    }}
                }}
                window.purgeTestUsers = purgeTestUsers;

                function filterUsersTable() {{
                    const q = (document.getElementById('usersSearchInput')?.value || '').toLowerCase().trim();
                    if (!q) {{
                        renderUsersTable(allLoadedUsers);
                        return;
                    }}
                    const filtered = allLoadedUsers.filter(u => {{
                        const id = String(u.user_id || '').toLowerCase();
                        const name = String(u.username || u.name || '').toLowerCase();
                        const phone = String(u.phone || '').toLowerCase();
                        const ref = String(u.referred_by || '').toLowerCase();
                        return id.includes(q) || name.includes(q) || phone.includes(q) || ref.includes(q);
                    }});
                    renderUsersTable(filtered);
                }}
                window.filterUsersTable = filterUsersTable;

                function exportUsersCsv() {{
                    if (!allLoadedUsers || allLoadedUsers.length === 0) {{
                        showToast('Ú©Ø§Ø±Ø¨Ø±ÛŒ Ø¨Ø±Ø§ÛŒ Ø®Ø±ÙˆØ¬ÛŒ Ù…ÙˆØ¬ÙˆØ¯ Ù†ÛŒØ³Øª.');
                        return;
                    }}
                    const header = ['Ù¾Ù„ØªÙØ±Ù…', 'Ø´Ù†Ø§Ø³Ù‡', 'Ù†Ø§Ù…', 'Ø´Ù…Ø§Ø±Ù‡ ØªÙ…Ø§Ø³', 'Ù…Ø¹Ø±Ù', 'Ú©ÛŒÙ Ù¾ÙˆÙ„', 'ØªØ¹Ù‡Ø¯Ù†Ø§Ù…Ù‡'];
                    const rows = allLoadedUsers.map(u => [
                        u.platform || '',
                        u.user_id || '',
                        u.username || u.name || '',
                        u.phone || '',
                        u.referred_by || '',
                        u.wallet_balance || 0,
                        u.commitment_signed ? 'Ø§Ù…Ø¶Ø§ Ø´Ø¯Ù‡' : 'Ø®ÛŒØ±'
                    ]);
                    const csvContent = "\\uFEFF" + [header.join(','), ...rows.map(r => r.map(c => `"${{String(c).replace(/"/g, '""')}}"`).join(','))].join('\\n');
                    const blob = new Blob([csvContent], {{ type: 'text/csv;charset=utf-8;' }});
                    const url = URL.createObjectURL(blob);
                    const link = document.createElement('a');
                    link.href = url;
                    link.download = `unfinit_users_${{new Date().toISOString().slice(0,10)}}.csv`;
                    link.click();
                    URL.revokeObjectURL(url);
                }}
                window.exportUsersCsv = exportUsersCsv;

                function checkAuthOnLoad() {{
                    const token = localStorage.getItem('unfinit_auth_token') || sessionStorage.getItem('unfinit_auth_token');
                    const pwd = localStorage.getItem('unfinit_admin_pwd') || sessionStorage.getItem('unfinit_admin_pwd');
                    const gate = document.getElementById('loginGate');
                    const app = document.getElementById('appMain');
                    if (token === 'authenticated' && pwd) {{
                        window.currentAdminPassword = pwd;
                        if (gate) {{
                            gate.style.display = 'none';
                            gate.classList.add('hidden');
                        }}
                        if (app) {{
                            app.style.removeProperty('display');
                            app.style.display = 'block';
                            app.classList.remove('hidden');
                        }}
                        try {{
                            const savedTab = localStorage.getItem('unfinit_active_tab') || 'dashboard';
                            window.switchTab(savedTab);
                        }} catch (e) {{
                            console.warn('[Navigation] Tab switch notice:', e);
                        }}
                    }} else {{
                        if (gate) {{
                            gate.style.removeProperty('display');
                            gate.classList.remove('hidden');
                        }}
                        if (app) {{
                            app.classList.add('hidden');
                            app.style.display = 'none';
                        }}
                    }}
                }}

                function bindNavDelegation() {{
                    const sidebarNav = document.getElementById('sidebarNavList');
                    if (sidebarNav) {{
                        sidebarNav.addEventListener('click', function(e) {{
                            const btn = e.target.closest('[data-tab]');
                            if (btn) {{
                                const tab = btn.getAttribute('data-tab');
                                if (tab && window.switchTab) window.switchTab(tab);
                            }}
                        }});
                    }}
                    const desktopNav = document.getElementById('desktopNavTabs');
                    if (desktopNav) {{
                        desktopNav.addEventListener('click', function(e) {{
                            const btn = e.target.closest('[data-tab]');
                            if (btn) {{
                                const tab = btn.getAttribute('data-tab');
                                if (tab && window.switchTab) window.switchTab(tab);
                            }}
                        }});
                    }}
                    const mobileNav = document.getElementById('mobileNavMenu');
                    if (mobileNav) {{
                        mobileNav.addEventListener('click', function(e) {{
                            const btn = e.target.closest('[data-tab]');
                            if (btn) {{
                                const tab = btn.getAttribute('data-tab');
                                if (tab && window.switchTab) {{
                                    window.switchTab(tab);
                                    if (typeof window.toggleMobileMenu === 'function') {{
                                        window.toggleMobileMenu(false);
                                    }}
                                }}
                            }}
                        }});
                    }}
                }}

                function persistTabsOrder() {{
                    const sidebarNav = document.getElementById('sidebarNavList');
                    const desktopNav = document.getElementById('desktopNavTabs');
                    let currentOrder = [];
                    if (sidebarNav) {{
                        currentOrder = Array.from(sidebarNav.querySelectorAll('[data-tab]')).map(b => b.getAttribute('data-tab')).filter(Boolean);
                    }}
                    if (currentOrder.length === 0 && desktopNav) {{
                        currentOrder = Array.from(desktopNav.querySelectorAll('[data-tab]')).map(b => b.getAttribute('data-tab')).filter(Boolean);
                    }}
                    if (currentOrder.length === 0) return;
                    // ØªØ¶Ù…ÛŒÙ† Ù‚Ø·Ø¹ÛŒ Ù‚Ø±Ø§Ø± Ú¯Ø±ÙØªÙ† ØªØ¨ Ø¯Ø§Ø´Ø¨ÙˆØ±Ø¯ Ø¯Ø± Ù†Ø®Ø³ØªÛŒÙ† Ø¬Ø§ÛŒÚ¯Ø§Ù‡ Ø³Ø§ÛŒØ¯Ø¨Ø§Ø± (index: 0)
                    currentOrder = ['dashboard', ...currentOrder.filter(t => t !== 'dashboard')];
                    localStorage.setItem('unfinit_nav_order', JSON.stringify(currentOrder));
                    localStorage.setItem('unfinit_tabs_order', JSON.stringify(currentOrder));
                    try {{
                        const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                        if (pwd) {{
                            fetch('/api/settings/save', {{
                                method: 'POST',
                                headers: {{ 'Content-Type': 'application/json; charset=utf-8' }},
                                body: JSON.stringify({{
                                    password: pwd,
                                    settings: {{ NAV_TABS_ORDER: currentOrder }}
                                }})
                            }}).catch(e => console.warn('[DragDrop] Cloud save failed:', e));
                        }}
                    }} catch (e) {{}}
                }}

                function initTabsDragAndDrop() {{
                    const sidebarNav = document.getElementById('sidebarNavList');
                    const desktopNav = document.getElementById('desktopNavTabs');

                    try {{
                        let savedOrder = JSON.parse(localStorage.getItem('unfinit_nav_order') || localStorage.getItem('unfinit_tabs_order') || '[]');
                        if (Array.isArray(savedOrder) && savedOrder.length > 0) {{
                            // ØªØ«Ø¨ÛŒØª Ø±ØªØ¨Ù‡ Ø§ÙˆÙ„ Ø¨Ø±Ø§ÛŒ Ø¯Ø§Ø´Ø¨ÙˆØ±Ø¯ Ø¯Ø± Ù‡Ù†Ú¯Ø§Ù… Ø¨Ø§Ø±Ú¯Ø°Ø§Ø±ÛŒ
                            savedOrder = ['dashboard', ...savedOrder.filter(t => t !== 'dashboard')];
                            if (sidebarNav) {{
                                savedOrder.forEach(tabId => {{
                                    const btn = sidebarNav.querySelector(`[data-tab="${{tabId}}"]`);
                                    if (btn) sidebarNav.appendChild(btn);
                                }});
                            }}
                            if (desktopNav) {{
                                savedOrder.forEach(tabId => {{
                                    const btn = desktopNav.querySelector(`[data-tab="${{tabId}}"]`);
                                    if (btn) desktopNav.appendChild(btn);
                                }});
                            }}
                        }}
                    }} catch (e) {{
                        console.warn('[DragDrop] Error loading saved tab order:', e);
                    }}

                    function setupDragForContainer(container, isVertical) {{
                        if (!container) return;
                        let draggedItem = null;

                        // Set draggable="true" on all tab items while preserving cursor: pointer
                        container.querySelectorAll('[data-tab]').forEach(b => {{
                            b.setAttribute('draggable', 'true');
                            b.style.cursor = 'pointer';
                        }});

                        // Mouse Drag & Drop (Native HTML5: Clicks fire instantly, dragging initiates reorder)
                        container.addEventListener('dragstart', function(e) {{
                            const btn = e.target.closest('[data-tab]');
                            if (!btn) return;
                            draggedItem = btn;
                            e.dataTransfer.effectAllowed = 'move';
                            e.dataTransfer.setData('text/plain', btn.getAttribute('data-tab'));
                            btn.classList.add('opacity-40');
                        }});

                        container.addEventListener('dragend', function(e) {{
                            const btn = e.target.closest('[data-tab]');
                            if (btn) {{
                                btn.classList.remove('opacity-40');
                            }}
                            container.querySelectorAll('[data-tab]').forEach(b => {{
                                b.classList.remove('opacity-40');
                                b.setAttribute('draggable', 'true');
                                b.style.cursor = 'pointer';
                            }});
                            draggedItem = null;
                            persistTabsOrder();
                        }});

                        container.addEventListener('dragover', function(e) {{
                            e.preventDefault();
                            e.dataTransfer.dropEffect = 'move';
                            const targetBtn = e.target.closest('[data-tab]');
                            if (targetBtn && targetBtn !== draggedItem && targetBtn.parentElement === container) {{
                                const rect = targetBtn.getBoundingClientRect();
                                const midpoint = isVertical ? (rect.y + rect.height / 2) : (rect.x + rect.width / 2);
                                const coord = isVertical ? e.clientY : e.clientX;
                                if (coord < midpoint) {{
                                    container.insertBefore(draggedItem, targetBtn);
                                }} else {{
                                    container.insertBefore(draggedItem, targetBtn.nextSibling);
                                }}
                            }}
                        }});

                        container.addEventListener('drop', function(e) {{
                            e.preventDefault();
                            persistTabsOrder();
                        }});

                        // Mobile Touch with 500ms long-press
                        let touchTimer = null;
                        let touchDraggedItem = null;

                        container.addEventListener('touchstart', function(e) {{
                            const btn = e.target.closest('[data-tab]');
                            if (!btn) return;
                            touchTimer = setTimeout(function() {{
                                touchDraggedItem = btn;
                                btn.classList.add('opacity-40', 'scale-95');
                                if (navigator.vibrate) navigator.vibrate(50);
                            }}, 500);
                        }}, {{ passive: true }});

                        container.addEventListener('touchmove', function(e) {{
                            if (!touchDraggedItem) {{
                                if (touchTimer) {{ clearTimeout(touchTimer); touchTimer = null; }}
                                return;
                            }}
                            e.preventDefault();
                            const touch = e.touches[0];
                            const targetEl = document.elementFromPoint(touch.clientX, touch.clientY);
                            if (!targetEl) return;
                            const targetBtn = targetEl.closest('[data-tab]');
                            if (targetBtn && targetBtn !== touchDraggedItem && targetBtn.parentElement === container) {{
                                const rect = targetBtn.getBoundingClientRect();
                                const midpoint = isVertical ? (rect.y + rect.height / 2) : (rect.x + rect.width / 2);
                                const coord = isVertical ? touch.clientY : touch.clientX;
                                if (coord < midpoint) {{
                                    container.insertBefore(touchDraggedItem, targetBtn);
                                }} else {{
                                    container.insertBefore(touchDraggedItem, targetBtn.nextSibling);
                                }}
                            }}
                        }}, {{ passive: false }});

                        function endTouchDrag() {{
                            if (touchTimer) {{ clearTimeout(touchTimer); touchTimer = null; }}
                            if (touchDraggedItem) {{
                                touchDraggedItem.classList.remove('opacity-40', 'scale-95');
                                container.querySelectorAll('[data-tab]').forEach(b => b.classList.remove('opacity-40', 'scale-95'));
                                touchDraggedItem = null;
                                persistTabsOrder();
                            }}
                        }}
                        container.addEventListener('touchend', endTouchDrag);
                        container.addEventListener('touchcancel', endTouchDrag);
                    }}

                    setupDragForContainer(sidebarNav, true);
                    setupDragForContainer(desktopNav, false);
                }}

                function initUptimeTicker() {{
                    const el = document.getElementById('uptimeDisplay');
                    if (!el) return;
                    const startSec = parseInt(el.getAttribute('data-start')) || 0;
                    if (!startSec) return;
                    function updateUptime() {{
                        const now = Math.floor(Date.now() / 1000);
                        let diff = Math.max(0, now - startSec);
                        const h = Math.floor(diff / 3600);
                        const m = Math.floor((diff % 3600) / 60);
                        const s = diff % 60;
                        el.textContent = `${{h}}h ${{m}}m ${{s}}s`;
                    }}
                    setInterval(updateUptime, 1000);
                }}

                if (document.readyState === 'loading') {{
                    document.addEventListener('DOMContentLoaded', function() {{
                        bindNavDelegation();
                        initTabsDragAndDrop();
                        initSidebarState();
                        initUptimeTicker();
                        checkAuthOnLoad();
                        restoreTabRenames();
                    }});
                }} else {{
                    bindNavDelegation();
                    initTabsDragAndDrop();
                    initSidebarState();
                    initUptimeTicker();
                    checkAuthOnLoad();
                    restoreTabRenames();
                }}
            }} catch (err) {{
                console.error('[UNFINIT Navigation Module Error]:', err);
            }}
        }})();

        // =========================================================================
        // MODULE 2: STUDIO & MEDIA HUB (Sandboxed IIFE)
        // =========================================================================
        (function initStudioModule() {{
            try {{
        // WEB MP3TAG STUDIO CLIENT LOGIC
        // =========================================================================

        const studioDropzone = document.getElementById('studioDropzone');
        if (studioDropzone) {{
            ['dragenter', 'dragover'].forEach(name => {{
                studioDropzone.addEventListener(name, (e) => {{
                    e.preventDefault();
                    e.stopPropagation();
                    studioDropzone.classList.add('dragover');
                }});
            }});
            ['dragleave', 'drop'].forEach(name => {{
                studioDropzone.addEventListener(name, (e) => {{
                    e.preventDefault();
                    e.stopPropagation();
                    studioDropzone.classList.remove('dragover');
                }});
            }});
            studioDropzone.addEventListener('drop', (e) => {{
                e.preventDefault();
                e.stopPropagation();
                studioDropzone.classList.remove('dragover');
                const dt = e.dataTransfer;
                if (dt && dt.files && dt.files.length > 0) {{
                    handleStudioFilesSelect(dt.files);
                }}
            }});
        }}

        async function handleStudioFilesSelect(fileList) {{
            if (!fileList || fileList.length === 0) return;
            const progressEl = document.getElementById('studioUploadProgress');
            if (progressEl) {{
                progressEl.classList.remove('hidden');
                progressEl.innerText = `â³ Ø¯Ø± Ø­Ø§Ù„ Ø¢Ù…Ø§Ø¯Ù‡â€ŒØ³Ø§Ø²ÛŒ Ùˆ Ø¨Ø§Ø±Ú¯Ø°Ø§Ø±ÛŒ ${{fileList.length}} ÙØ§ÛŒÙ„...`;
            }}

            let successCount = 0;
            for (let i = 0; i < fileList.length; i++) {{
                const file = fileList[i];
                if (progressEl) progressEl.innerText = `â³ Ø¯Ø± Ø­Ø§Ù„ Ø¢Ù¾Ù„ÙˆØ¯ (${{i+1}}/${{fileList.length}}): ${{file.name}}...`;
                try {{
                    const b64 = await readFileAsBase64(file);
                    const res = await fetch('/api/studio/upload', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json; charset=utf-8' }},
                        body: JSON.stringify({{ filename: file.name, data: b64 }})
                    }});
                    const data = await res.json();
                    if (data.ok) successCount++;
                }} catch (err) {{
                    console.error('Upload error:', err);
                }}
            }}

            if (progressEl) {{
                progressEl.innerText = `âœ… ØªØ¹Ø¯Ø§Ø¯ ${{successCount}} ÙØ§ÛŒÙ„ Ø¨Ø§ Ù…ÙˆÙÙ‚ÛŒØª Ø¨Ø§Ø±Ú¯Ø°Ø§Ø±ÛŒ Ùˆ Ø¯Ø± Ø§Ø³ØªÙˆØ¯ÛŒÙˆ Ø«Ø¨Øª Ú¯Ø±Ø¯ÛŒØ¯!`;
            }}
            setTimeout(() => {{
                if (progressEl) progressEl.classList.add('hidden');
                refreshStudioList();
            }}, 800);
        }}

        function readFileAsBase64(file) {{
            return new Promise((resolve, reject) => {{
                const reader = new FileReader();
                reader.onload = () => resolve(reader.result);
                reader.onerror = error => reject(error);
                reader.readAsDataURL(file);
            }});
        }}

        function previewStudioCover(input, previewImgId, b64InputId) {{
            const file = input.files[0];
            if (!file) return;
            const reader = new FileReader();
            reader.onload = function(e) {{
                const img = document.getElementById(previewImgId);
                if (img) img.src = e.target.result;
                const b64 = document.getElementById(b64InputId);
                if (b64) b64.value = e.target.result;
            }};
            reader.readAsDataURL(file);
        }}

        // Specs Modal
        async function openSpecsModal(dropId) {{
            const modal = document.getElementById('specsModal');
            const loading = document.getElementById('specsLoading');
            const body = document.getElementById('specsBody');
            modal.classList.remove('hidden');
            loading.classList.remove('hidden');
            body.classList.add('hidden');

            try {{
                const res = await fetch('/api/studio/specs/' + dropId);
                const data = await res.json();
                if (data.ok) {{
                    document.getElementById('specFilename').innerText = data.filename || '-';
                    document.getElementById('specBitrate').innerText = (data.bitrate_kbps ? data.bitrate_kbps + ' kbps' : 'Ù†Ø§Ù…Ø´Ø®Øµ');
                    document.getElementById('specSampleRate').innerText = (data.sample_rate ? data.sample_rate + ' Hz' : 'Ù†Ø§Ù…Ø´Ø®Øµ');
                    document.getElementById('specChannels').innerText = data.channels || 'Ù†Ø§Ù…Ø´Ø®Øµ';
                    document.getElementById('specCodec').innerText = data.codec || '-';
                    document.getElementById('specDuration').innerText = data.duration_str || '-';
                    document.getElementById('specSize').innerText = data.size_str || '-';
                    const covEl = document.getElementById('specCoverStatus');
                    covEl.innerText = data.has_cover ? 'âœ… Ù…ÙˆØ¬ÙˆØ¯' : 'âŒ ÙØ§Ù‚Ø¯ Ú©Ø§ÙˆØ±';
                    covEl.className = data.has_cover ? 'text-emerald-400 font-bold' : 'text-slate-500 font-bold';

                    loading.classList.add('hidden');
                    body.classList.remove('hidden');
                }} else {{
                    showToast('âŒ Ø®Ø·Ø§ Ø¯Ø± Ø¯Ø±ÛŒØ§ÙØª Ù…Ø´Ø®ØµØ§Øª ÙÙ†ÛŒ: ' + (data.error || ''));
                    closeSpecsModal();
                }}
            }} catch (err) {{
                showToast('âŒ Ø®Ø·Ø§ÛŒ Ø´Ø¨Ú©Ù‡: ' + err.message);
                closeSpecsModal();
            }}
        }}

        function closeSpecsModal() {{
            document.getElementById('specsModal').classList.add('hidden');
        }}

        // Single Tag Modal
        function openTagModal(dropId, title, artist, album, filename) {{
            document.getElementById('tagDropId').value = dropId;
            document.getElementById('tagTitle').value = title || '';
            document.getElementById('tagArtist').value = artist || '';
            document.getElementById('tagAlbum').value = album || '';
            document.getElementById('tagFilename').value = filename || '';
            document.getElementById('tagCoverB64').value = '';
            document.getElementById('tagRemoveCover').checked = false;
            
            const prev = document.getElementById('tagCoverPreview');
            prev.src = '/api/studio/cover/' + dropId + '?t=' + Date.now();
            prev.onerror = () => {{
                prev.src = 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="%2364748b"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3"/></svg>';
            }};

            document.getElementById('tagModal').classList.remove('hidden');
        }}

        function closeTagModal() {{
            document.getElementById('tagModal').classList.add('hidden');
        }}

        async function handleSaveStudioTags(e) {{
            e.preventDefault();
            const btn = document.getElementById('btnSaveTag');
            if (btn) {{
                btn.disabled = true;
                btn.innerText = 'â³ Ø¯Ø± Ø­Ø§Ù„ Ø°Ø®ÛŒØ±Ù‡ Ø¢Ù†ÛŒ Ù…ØªØ§Ø¯ÛŒØªØ§...';
            }}

            const payload = {{
                drop_id: document.getElementById('tagDropId').value,
                title: document.getElementById('tagTitle').value,
                artist: document.getElementById('tagArtist').value,
                album: document.getElementById('tagAlbum').value,
                new_filename: document.getElementById('tagFilename').value,
                cover_data: document.getElementById('tagCoverB64').value,
                remove_cover: document.getElementById('tagRemoveCover').checked
            }};

            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 60000);

            try {{
                const res = await fetch('/api/studio/edit_tags', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json; charset=utf-8' }},
                    body: JSON.stringify(payload),
                    signal: controller.signal
                }});
                clearTimeout(timeoutId);
                const data = await res.json();
                if (data.ok) {{
                    showToast('âœ… ' + (data.message || 'Ù…ØªØ§Ø¯ÛŒØªØ§ Ø¨Ø§ Ù…ÙˆÙÙ‚ÛŒØª Ø°Ø®ÛŒØ±Ù‡ Ø´Ø¯!'));
                    closeTagModal();
                    refreshStudioList();
                }} else {{
                    showToast('âŒ Ø®Ø·Ø§: ' + (data.error || 'Ø°Ø®ÛŒØ±Ù‡ Ù…ØªØ§Ø¯ÛŒØªØ§ Ù†Ø§Ù…ÙˆÙÙ‚ Ø¨ÙˆØ¯'));
                }}
            }} catch (err) {{
                clearTimeout(timeoutId);
                showToast('âŒ Ø®Ø·Ø§ÛŒ Ø§Ø±ØªØ¨Ø§Ø· ÛŒØ§ Ø²Ù…Ø§Ù†â€ŒØ¨Ù†Ø¯ÛŒ: ' + err.message);
            }} finally {{
                if (btn) {{
                    btn.disabled = false;
                    btn.innerText = 'ðŸ’¾ Ø°Ø®ÛŒØ±Ù‡ Ø¢Ù†ÛŒ Ù…ØªØ§Ø¯ÛŒØªØ§';
                }}
            }}
        }}

        // Selection and Batch Edit
        function toggleSelectAllDrops(masterChk) {{
            document.querySelectorAll('.drop-chk').forEach(c => c.checked = masterChk.checked);
            updateSelectedCount();
        }}

        function updateSelectedCount() {{
            const checked = document.querySelectorAll('.drop-chk:checked');
            const badge = document.getElementById('selectedCountBadge');
            if (badge) badge.innerText = checked.length + ' ÙØ§ÛŒÙ„ Ø§Ù†ØªØ®Ø§Ø¨ Ø´Ø¯Ù‡';
        }}

        function getSelectedDropIds() {{
            const checked = document.querySelectorAll('.drop-chk:checked');
            return Array.from(checked).map(c => c.getAttribute('data-drop-id'));
        }}

        function openBatchTagModal() {{
            const ids = getSelectedDropIds();
            if (ids.length === 0) {{
                showToast('âš ï¸ Ù„Ø·ÙØ§Ù‹ Ø­Ø¯Ø§Ù‚Ù„ ÛŒÚ© ÙØ§ÛŒÙ„ Ø±Ø§ Ø¨Ø±Ø§ÛŒ ÙˆÛŒØ±Ø§ÛŒØ´ Ú¯Ø±ÙˆÙ‡ÛŒ Ø§Ù†ØªØ®Ø§Ø¨ ÙØ±Ù…Ø§ÛŒÛŒØ¯.');
                return;
            }}
            document.getElementById('batchCountBadge').innerText = ids.length;
            document.getElementById('batchCoverB64').value = '';
            document.getElementById('batchRemoveCover').checked = false;
            document.getElementById('batchCoverPreview').src = '';
            document.getElementById('batchTagModal').classList.remove('hidden');
        }}

        function closeBatchTagModal() {{
            document.getElementById('batchTagModal').classList.add('hidden');
        }}

        async function handleSaveBatchTags(e) {{
            e.preventDefault();
            const ids = getSelectedDropIds();
            if (ids.length === 0) return;

            const btn = document.getElementById('btnSaveBatch');
            btn.disabled = true;
            btn.innerText = 'â³ Ø¯Ø± Ø­Ø§Ù„ Ø§Ø¹Ù…Ø§Ù„ ØªØºÛŒÛŒØ±Ø§Øª Ú¯Ø±ÙˆÙ‡ÛŒ...';

            const payload = {{
                drop_ids: ids,
                album: document.getElementById('batchAlbum').value,
                artist: document.getElementById('batchArtist').value,
                auto_number: document.getElementById('batchAutoNumber').checked,
                title_pattern: document.getElementById('batchTitlePattern').value,
                cover_data: document.getElementById('batchCoverB64').value,
                remove_cover: document.getElementById('batchRemoveCover').checked
            }};

            try {{
                const res = await fetch('/api/studio/batch_edit', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json; charset=utf-8' }},
                    body: JSON.stringify(payload)
                }});
                const data = await res.json();
                if (data.ok) {{
                    showToast('âœ… ' + (data.message || 'ÙˆÛŒØ±Ø§ÛŒØ´ Ú¯Ø±ÙˆÙ‡ÛŒ Ø¨Ø§ Ù…ÙˆÙÙ‚ÛŒØª Ø§Ø¹Ù…Ø§Ù„ Ú¯Ø±Ø¯ÛŒØ¯!'));
                    closeBatchTagModal();
                    refreshStudioList();
                }} else {{
                    showToast('âŒ Ø®Ø·Ø§: ' + (data.error || 'Ø¹Ù…Ù„ÛŒØ§Øª Ú¯Ø±ÙˆÙ‡ÛŒ Ù†Ø§Ù…ÙˆÙÙ‚ Ø¨ÙˆØ¯'));
                }}
            }} catch (err) {{
                showToast('âŒ Ø®Ø·Ø§ÛŒ Ø§Ø±ØªØ¨Ø§Ø·: ' + err.message);
            }} finally {{
                btn.disabled = false;
                btn.innerText = 'ðŸš€ Ø§Ø¹Ù…Ø§Ù„ Ø±ÙˆÛŒ ØªÙ…Ø§Ù… ÙØ§ÛŒÙ„â€ŒÙ‡Ø§';
            }}
        }}

        /**
         * Ø§Ø±Ø³Ø§Ù„ Ù…Ø³ØªÙ‚ÛŒÙ… ÛŒÚ© ÙØ§ÛŒÙ„ Ø§Ø² Ø§Ø³ØªÙˆØ¯ÛŒÙˆÛŒ Ø±Ø³Ø§Ù†Ù‡ Ø¨Ù‡ Ù¾Ù„ØªÙØ±Ù…â€ŒÙ‡Ø§ÛŒ Ù¾ÛŒØ§Ù…â€ŒØ±Ø³Ø§Ù† (ØªÙ„Ú¯Ø±Ø§Ù…ØŒ Ø¨Ù„Ù‡ØŒ Ø±ÙˆØ¨ÛŒÚ©Ø§ØŒ Ø³Ø±ÙˆØ´â€ŒÙ¾Ù„Ø§Ø³).
         * ÙˆØ±ÙˆØ¯ÛŒâ€ŒÙ‡Ø§: dropId (Ø´Ù†Ø§Ø³Ù‡ Ø¯Ø±Ø§Ù¾ ÙÛŒØ²ÛŒÚ©ÛŒ)ØŒ target (Ù†Ø§Ù… Ù¾Ù„ØªÙØ±Ù… Ù…Ù‚ØµØ¯)
         */
        async function dispatchDrop(dropId, target) {{
            const names = {{ telegram: 'ØªÙ„Ú¯Ø±Ø§Ù…', bale: 'Ø¨Ù„Ù‡', rubika: 'Ø±ÙˆØ¨ÛŒÚ©Ø§', soroush: 'Ø³Ø±ÙˆØ´â€ŒÙ¾Ù„Ø§Ø³', splus: 'Ø³Ø±ÙˆØ´â€ŒÙ¾Ù„Ø§Ø³' }};
            const targetName = names[target] || target;
            if (!confirm(`Ø¢ÛŒØ§ Ù…ÛŒâ€ŒØ®ÙˆØ§Ù‡ÛŒØ¯ Ø§ÛŒÙ† ÙØ§ÛŒÙ„ Ù…Ø³ØªÙ‚ÛŒÙ…Ø§Ù‹ Ø¨Ù‡ ${{targetName}} Ø§Ø±Ø³Ø§Ù„ Ø´ÙˆØ¯ØŸ`)) return;

            try {{
                const res = await fetch('/api/studio/dispatch', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json; charset=utf-8' }},
                    body: JSON.stringify({{ drop_id: dropId, target: target }})
                }});
                const data = await res.json();
                if (data.ok) {{
                    showToast('âœ… ' + (data.message || `ÙØ§ÛŒÙ„ Ø¨Ø§ Ù…ÙˆÙÙ‚ÛŒØª Ø¨Ù‡ ${{targetName}} Ø§Ø±Ø³Ø§Ù„ Ø´Ø¯!`));
                }} else {{
                    showToast('âŒ Ø®Ø·Ø§: ' + (data.error || 'Ø§Ø±Ø³Ø§Ù„ ÙØ§ÛŒÙ„ Ù†Ø§Ù…ÙˆÙÙ‚ Ø¨ÙˆØ¯'));
                }}
            }} catch (err) {{
                showToast('âŒ Ø®Ø·Ø§ÛŒ Ø§Ø±ØªØ¨Ø§Ø· Ø¨Ø§ Ø³Ø±ÙˆØ±: ' + err.message);
            }}
        }}

        // =========================================================================
        // WAVESURFER AUDIO CUTTER & STUDIO ACTION LOGIC
        // =========================================================================
        let wavesurfer = null;

        function formatSecToTime(seconds) {{
            if (isNaN(seconds) || seconds < 0) seconds = 0;
            const m = Math.floor(seconds / 60);
            const s = Math.floor(seconds % 60);
            const ms = Math.floor((seconds % 1) * 10);
            return String(m).padStart(2, '0') + ':' + String(s).padStart(2, '0') + '.' + ms;
        }}

        function parseTimeToSec(str) {{
            if (!str) return 0;
            str = String(str).trim();
            if (str.includes(':')) {{
                const parts = str.split(':');
                const m = parseFloat(parts[0]) || 0;
                const s = parseFloat(parts[1]) || 0;
                return m * 60 + s;
            }}
            return parseFloat(str) || 0;
        }}

        function openCutterModal(dropId, filename) {{
            document.getElementById('cutterDropId').value = dropId;
            document.getElementById('cutterFilename').innerText = filename || dropId;
            document.getElementById('cutStartTime').value = '00:00.0';
            document.getElementById('cutEndTime').value = '00:00.0';
            document.getElementById('cutterCurrentTime').innerText = '00:00.0';
            document.getElementById('cutterTotalDuration').innerText = '00:00.0';
            document.getElementById('wavePlayText').innerText = 'Ù¾Ø®Ø´';
            document.getElementById('cutterModal').classList.remove('hidden');

            const loading = document.getElementById('waveformLoading');
            if (loading) loading.classList.remove('hidden');

            if (wavesurfer) {{
                try {{ wavesurfer.destroy(); }} catch (e) {{}}
                wavesurfer = null;
            }}

            try {{
                wavesurfer = WaveSurfer.create({{
                    container: '#waveform',
                    waveColor: '#334155',
                    progressColor: '#06b6d4',
                    cursorColor: '#38bdf8',
                    barWidth: 2,
                    barGap: 1,
                    barRadius: 2,
                    height: 80,
                    url: '/dl/' + dropId
                }});

                wavesurfer.on('ready', () => {{
                    if (loading) loading.classList.add('hidden');
                    const dur = wavesurfer.getDuration();
                    document.getElementById('cutterTotalDuration').innerText = formatSecToTime(dur);
                    document.getElementById('cutEndTime').value = formatSecToTime(dur);
                }});

                wavesurfer.on('timeupdate', (currentTime) => {{
                    const curFormatted = formatSecToTime(currentTime);
                    document.getElementById('cutterCurrentTime').innerText = curFormatted;
                    const toggleTime = document.getElementById('waveToggleTime');
                    if (toggleTime) toggleTime.innerText = curFormatted;
                }});

                wavesurfer.on('play', () => {{
                    const icon = document.getElementById('waveToggleIcon');
                    if (icon) icon.innerText = 'âšâš';
                    const btnText = document.getElementById('wavePlayText');
                    if (btnText) btnText.innerText = 'ØªÙˆÙ‚Ù Ù…ÙˆÙ‚Øª';
                }});

                wavesurfer.on('pause', () => {{
                    const icon = document.getElementById('waveToggleIcon');
                    if (icon) icon.innerText = 'â–¶';
                    const btnText = document.getElementById('wavePlayText');
                    if (btnText) btnText.innerText = 'Ù¾Ø®Ø´';
                }});

                wavesurfer.on('finish', () => {{
                    const icon = document.getElementById('waveToggleIcon');
                    if (icon) icon.innerText = 'â–¶';
                    const btnText = document.getElementById('wavePlayText');
                    if (btnText) btnText.innerText = 'Ù¾Ø®Ø´';
                }});

                wavesurfer.on('error', (err) => {{
                    console.error('WaveSurfer error:', err);
                    if (loading) loading.innerText = 'Ø®Ø·Ø§ Ø¯Ø± Ø¨Ø§Ø±Ú¯Ø°Ø§Ø±ÛŒ Ù†Ù…ÙˆØ¯Ø§Ø± Ù…ÙˆØ¬ ØµÙˆØªÛŒ: ' + err;
                }});
            }} catch (err) {{
                console.error('WaveSurfer init error:', err);
                if (loading) loading.innerText = 'Ø®Ø·Ø§ Ø¯Ø± Ø±Ø§Ù‡â€ŒØ§Ù†Ø¯Ø§Ø²ÛŒ Ù¾Ø®Ø´â€ŒÚ©Ù†Ù†Ø¯Ù‡ ØµÙˆØªÛŒ.';
            }}
        }}

        function closeCutterModal() {{
            if (wavesurfer) {{
                try {{ wavesurfer.pause(); }} catch (e) {{}}
            }}
            const icon = document.getElementById('waveToggleIcon');
            if (icon) icon.innerText = 'â–¶';
            document.getElementById('cutterModal').classList.add('hidden');
        }}

        function toggleWavePlayPause() {{
            if (wavesurfer) {{
                wavesurfer.playPause();
            }}
        }}

        function stopWaveSurfer() {{
            if (wavesurfer) {{
                wavesurfer.stop();
                document.getElementById('wavePlayText').innerText = 'Ù¾Ø®Ø´';
            }}
        }}

        function setStartFromCursor() {{
            if (wavesurfer) {{
                const cur = wavesurfer.getCurrentTime();
                document.getElementById('cutStartTime').value = formatSecToTime(cur);
            }}
        }}

        function setEndFromCursor() {{
            if (wavesurfer) {{
                const cur = wavesurfer.getCurrentTime();
                document.getElementById('cutEndTime').value = formatSecToTime(cur);
            }}
        }}

        async function submitAudioCut() {{
            const dropId = document.getElementById('cutterDropId').value;
            const startStr = document.getElementById('cutStartTime').value;
            const endStr = document.getElementById('cutEndTime').value;
            const startSec = parseTimeToSec(startStr);
            const endSec = parseTimeToSec(endStr);

            if (endSec > 0 && endSec <= startSec) {{
                showToast('âŒ Ø²Ù…Ø§Ù† Ù¾Ø§ÛŒØ§Ù† Ø¨Ø§ÛŒØ¯ Ø¨Ø¹Ø¯ Ø§Ø² Ø²Ù…Ø§Ù† Ø´Ø±ÙˆØ¹ Ø¨Ø§Ø´Ø¯.');
                return;
            }}

            const btn = document.getElementById('btnSubmitCut');
            btn.disabled = true;
            btn.innerText = 'â³ Ø¯Ø± Ø­Ø§Ù„ Ø¨Ø±Ø´ ØµÙˆØª Ø¨Ø§ FFmpeg...';

            try {{
                const res = await fetch('/api/studio/cut', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json; charset=utf-8' }},
                    body: JSON.stringify({{
                        drop_id: dropId,
                        start_sec: startSec,
                        end_sec: endSec > 0 ? endSec : null
                    }})
                }});
                const data = await res.json();
                if (data.ok) {{
                    showToast('âœ… ' + (data.message || 'ÙØ§ÛŒÙ„ Ø¨Ø§ Ù…ÙˆÙÙ‚ÛŒØª Ø¨Ø±Ø´ ÛŒØ§ÙØª Ùˆ Ø¨Ù‡ Ø§Ø³ØªÙˆØ¯ÛŒÙˆ Ø§Ø¶Ø§ÙÙ‡ Ø´Ø¯!'));
                    closeCutterModal();
                    refreshStudioList();
                }} else {{
                    showToast('âŒ Ø®Ø·Ø§: ' + (data.error || 'Ø¹Ù…Ù„ÛŒØ§Øª Ø¨Ø±Ø´ Ù†Ø§Ù…ÙˆÙÙ‚ Ø¨ÙˆØ¯.'));
                }}
            }} catch (err) {{
                showToast('âŒ Ø®Ø·Ø§ÛŒ Ø§Ø±ØªØ¨Ø§Ø· Ø¨Ø§ Ø³Ø±ÙˆØ±: ' + err.message);
            }} finally {{
                btn.disabled = false;
                btn.innerHTML = '<span>âœ‚ï¸</span> Ø¨Ø±Ø´ Ùˆ Ø§ÛŒØ¬Ø§Ø¯ ÙØ§ÛŒÙ„ Ø¬Ø¯ÛŒØ¯';
            }}
        }}

        async function deleteStudioDrop(dropId) {{
            if (!confirm('Ø¢ÛŒØ§ Ø§Ø² Ø­Ø°Ù Ø§ÛŒÙ† ÙØ§ÛŒÙ„ Ùˆ Ø³Ø´Ù† Ø±Ø³Ø§Ù†Ù‡ Ø§Ø² Ø¯ÛŒØ³Ú© Ø³Ø±ÙˆØ± Ù…Ø·Ù…Ø¦Ù† Ù‡Ø³ØªÛŒØ¯ØŸ')) return;
            try {{
                const res = await fetch('/api/studio/delete', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json; charset=utf-8' }},
                    body: JSON.stringify({{ drop_id: dropId }})
                }});
                const data = await res.json();
                if (data.ok) {{
                    const row = document.getElementById('row_' + dropId);
                    if (row) {{
                        row.style.transition = 'all 0.4s ease';
                        row.style.opacity = '0';
                        row.style.transform = 'scale(0.95)';
                        setTimeout(() => {{ row.remove(); updateSelectedCount(); }}, 400);
                    }} else {{
                        refreshStudioList();
                    }}
                }} else {{
                    showToast('âŒ Ø®Ø·Ø§: ' + (data.error || 'Ø­Ø°Ù Ø³Ø´Ù† Ù†Ø§Ù…ÙˆÙÙ‚ Ø¨ÙˆØ¯'));
                }}
            }} catch (err) {{
                showToast('âŒ Ø®Ø·Ø§ÛŒ Ø´Ø¨Ú©Ù‡: ' + err.message);
            }}
        }}

        async function batchDeleteStudioDrops() {{
            const ids = getSelectedDropIds();
            if (ids.length === 0) {{
                showToast('âš ï¸ Ù„Ø·ÙØ§Ù‹ Ø­Ø¯Ø§Ù‚Ù„ ÛŒÚ© ÙØ§ÛŒÙ„ Ø±Ø§ Ø¨Ø±Ø§ÛŒ Ø­Ø°Ù Ø§Ù†ØªØ®Ø§Ø¨ ÙØ±Ù…Ø§ÛŒÛŒØ¯.');
                return;
            }}
            if (!confirm(`Ø¢ÛŒØ§ Ø§Ø² Ø­Ø°Ù Ø¯Ø§Ø¦Ù… ${{ids.length}} ÙØ§ÛŒÙ„ Ø§Ù†ØªØ®Ø§Ø¨â€ŒØ´Ø¯Ù‡ Ø§Ø² Ø­Ø§ÙØ¸Ù‡ Ùˆ Ø¯ÛŒØ³Ú© Ø³Ø±ÙˆØ± Ù…Ø·Ù…Ø¦Ù† Ù‡Ø³ØªÛŒØ¯ØŸ`)) return;

            try {{
                const res = await fetch('/api/studio/delete_batch', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json; charset=utf-8' }},
                    body: JSON.stringify({{ drop_ids: ids }})
                }});
                const data = await res.json();
                if (data.ok) {{
                    ids.forEach(id => {{
                        const row = document.getElementById('row_' + id);
                        if (row) {{
                            row.style.transition = 'all 0.4s ease';
                            row.style.opacity = '0';
                            row.style.transform = 'scale(0.95)';
                            setTimeout(() => {{ row.remove(); updateSelectedCount(); }}, 400);
                        }}
                    }});
                    const chkAll = document.getElementById('selectAllDrops');
                    if (chkAll) chkAll.checked = false;
                    setTimeout(() => {{ refreshStudioList(); }}, 450);
                }} else {{
                    showToast('âŒ Ø®Ø·Ø§: ' + (data.error || 'Ø­Ø°Ù Ú¯Ø±ÙˆÙ‡ÛŒ Ù†Ø§Ù…ÙˆÙÙ‚ Ø¨ÙˆØ¯'));
                }}
            }} catch (err) {{
                showToast('âŒ Ø®Ø·Ø§ÛŒ Ø´Ø¨Ú©Ù‡: ' + err.message);
            }}
        }}

        function changeStudioSort(sortVal) {{
            try {{
                localStorage.setItem('unfinit_studio_sort', sortVal);
            }} catch (e) {{}}
            refreshStudioList();
        }}

        async function refreshStudioList() {{
            const tbody = document.getElementById('studioTableBody');
            if (tbody) tbody.style.opacity = '0.5';
            try {{
                let sortVal = 'newest';
                try {{
                    sortVal = localStorage.getItem('unfinit_studio_sort') || 'newest';
                }} catch (e) {{}}
                const sortSelect = document.getElementById('studioSortSelect');
                if (sortSelect && sortSelect.value !== sortVal) {{
                    sortSelect.value = sortVal;
                }}
                const res = await fetch('/api/studio/table_html?sort=' + encodeURIComponent(sortVal));
                const data = await res.json();
                if (data.ok && data.html) {{
                    if (tbody) {{
                        tbody.innerHTML = data.html;
                        tbody.style.opacity = '1';
                        const chkAll = document.getElementById('selectAllDrops');
                        if (chkAll) chkAll.checked = false;
                        updateSelectedCount();
                    }}
                }} else {{
                    console.warn('Refresh studio table returned non-ok:', data);
                    if (tbody) tbody.style.opacity = '1';
                }}
            }} catch (err) {{
                console.error('Failed to refresh studio table:', err);
                if (tbody) tbody.style.opacity = '1';
            }}
        }}

        async function cleanupStudioDrops() {{
            if (!confirm('Ø¢ÛŒØ§ Ù…ÛŒâ€ŒØ®ÙˆØ§Ù‡ÛŒØ¯ ØªÙ…Ø§Ù… Ø³Ø´Ù†â€ŒÙ‡Ø§ÛŒ ØªÚ©Ø±Ø§Ø±ÛŒ Ùˆ ÙØ§ÛŒÙ„â€ŒÙ‡Ø§ÛŒ Ø²Ø§Ø¦Ø¯ Ø¨Ù‡ ØµÙˆØ±Øª Ù‡ÙˆØ´Ù…Ù†Ø¯ Ù¾Ø§Ú©Ø³Ø§Ø²ÛŒ Ø´ÙˆÙ†Ø¯ØŸ')) return;
            const btn = document.getElementById('btnCleanupStudio');
            if (btn) {{
                btn.disabled = true;
                btn.innerText = 'â³ Ø¯Ø± Ø­Ø§Ù„ Ù¾Ø§Ú©Ø³Ø§Ø²ÛŒ...';
            }}
            try {{
                const res = await fetch('/api/studio/cleanup', {{ method: 'POST' }});
                const data = await res.json();
                if (data.ok) {{
                    showToast('âœ… ' + (data.message || 'Ø³Ø´Ù†â€ŒÙ‡Ø§ÛŒ ØªÚ©Ø±Ø§Ø±ÛŒ Ø¨Ø§ Ù…ÙˆÙÙ‚ÛŒØª Ù¾Ø§Ú©Ø³Ø§Ø²ÛŒ Ø´Ø¯Ù†Ø¯!'));
                    refreshStudioList();
                }} else {{
                    showToast('âŒ Ø®Ø·Ø§: ' + (data.error || 'Ù¾Ø§Ú©Ø³Ø§Ø²ÛŒ Ù†Ø§Ù…ÙˆÙÙ‚ Ø¨ÙˆØ¯'));
                }}
            }} catch (err) {{
                showToast('âŒ Ø®Ø·Ø§ÛŒ Ø§Ø±ØªØ¨Ø§Ø·: ' + err.message);
            }} finally {{
                if (btn) {{
                    btn.disabled = false;
                    btn.innerHTML = '<span>ðŸ§¹</span> Ù¾Ø§Ú©Ø³Ø§Ø²ÛŒ Ø³Ø´Ù†â€ŒÙ‡Ø§ÛŒ Ø®Ø§Ù„ÛŒ Ùˆ Ù†Ø§Ù…Ø¹ØªØ¨Ø±';
                }}
            }}
        }}

        /**
         * ØªØ¨Ø¯ÛŒÙ„ Ø§Ø±Ù‚Ø§Ù… Ø§Ù†Ú¯Ù„ÛŒØ³ÛŒ Ø¨Ù‡ ÙØ§Ø±Ø³ÛŒ Ø¬Ù‡Øª ÛŒÚ©Ù¾Ø§Ø±Ú†Ú¯ÛŒ Ø·Ø¨Ù‚ Ø§Ø³ØªØ§Ù†Ø¯Ø§Ø±Ø¯ Ø²Ø¨Ø§Ù† Ø¨ØµØ±ÛŒ
         */
        function toPersianDigits(n) {{
            const farsiDigits = ['Û°', 'Û±', 'Û²', 'Û³', 'Û´', 'Ûµ', 'Û¶', 'Û·', 'Û¸', 'Û¹'];
            return String(n).replace(/[0-9]/g, function(w) {{ return farsiDigits[+w]; }});
        }}
        window.toPersianDigits = toPersianDigits;

        /**
         * Ù…ØªØ¯ ØªØ³Øª Ø§Ø¯Ù…ÛŒÙ† Ø¨Ø±Ø§ÛŒ Ø¯Ø±ÛŒØ§ÙØª Ù†Ø´Ø§Ù†Ù‡ Ø§Ù…Ø±ÙˆØ² Ù…Ù†
         * ÛŒÚ© Ù†Ø´Ø§Ù†Ù‡ ØªØµØ§Ø¯ÙÛŒ Ø§Ø² ØµÙØ­Ø§Øª Ø¯Ø§Ù†Ù„ÙˆØ¯ Ø³Ø§ÛŒØª Ø±Ø§ Ø§Ø³ØªØ¹Ù„Ø§Ù… Ù†Ù…ÙˆØ¯Ù‡ Ùˆ Ø¯Ø± Ø¯ÛŒØ§Ù„ÙˆÚ¯ Ø´ÙØ§Ù Ù†Ù…Ø§ÛŒØ´ Ù…ÛŒâ€ŒØ¯Ù‡Ø¯.
         */
        async function testTodaySign() {{
            const btn = document.getElementById('btnTestTodaySign');
            if (btn) {{
                btn.disabled = true;
                btn.innerHTML = '<svg class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path></svg><span>Ø¯Ø± Ø­Ø§Ù„ Ø¯Ø±ÛŒØ§ÙØª Ù†Ø´Ø§Ù†Ù‡...</span>';
            }}
            try {{
                const res = await fetch('/api/sign/test');
                const data = await res.json();
                if (data.ok && data.sign) {{
                    const s = data.sign;
                    showToast('ðŸ”® Ù†Ø´Ø§Ù†Ù‡ ØªØµØ§Ø¯ÙÛŒ ØªØ³Øª Ø§Ø¯Ù…ÛŒÙ†:\\n\\n' +
                          'Ø¹Ù†ÙˆØ§Ù†: ' + (s.title || 'Ù†Ø´Ø§Ù†Ù‡ Ø§Ù…Ø±ÙˆØ²') + '\\n' +
                          'Ø´Ù…Ø§Ø±Ù‡ ØµÙØ­Ù‡: ' + toPersianDigits(s.page || 1) + '\\n' +
                          'Ù„ÛŒÙ†Ú© ÙØ§ÛŒÙ„ ØµÙˆØªÛŒ: ' + (s.audio_url || 'Ù†Ø¯Ø§Ø±Ø¯') + '\\n' +
                          'Ù„ÛŒÙ†Ú© Ù…Ø³ØªÙ‚ÛŒÙ…: ' + (s.link || 'Ù†Ø¯Ø§Ø±Ø¯'));
                }} else {{
                    showToast('Ø®Ø·Ø§ Ø¯Ø± Ø¯Ø±ÛŒØ§ÙØª Ù†Ø´Ø§Ù†Ù‡: ' + (data.error || 'Ù¾Ø§Ø³Ø® Ù†Ø§Ù…Ø¹ØªØ¨Ø±'));
                }}
            }} catch (err) {{
                showToast('Ø®Ø·Ø§ÛŒ Ø§Ø±ØªØ¨Ø§Ø· Ø¨Ø§ Ø³Ø±ÙˆØ±: ' + err.message);
            }} finally {{
                if (btn) {{
                    btn.disabled = false;
                    btn.innerHTML = '<svg class="w-4 h-4 stroke-[1.75]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456zM16.894 20.567L16.5 21.75l-.394-1.183a2.25 2.25 0 00-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 001.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 001.423 1.423l1.183.394-1.183.394a2.25 2.25 0 00-1.423 1.423z" /></svg><span>Ø¯Ø±ÛŒØ§ÙØª Ù†Ø´Ø§Ù†Ù‡ ØªØµØ§Ø¯ÙÛŒ (ØªØ³Øª Ø§Ø¯Ù…ÛŒÙ†)</span>';
                }}
            }}
        }}
        window.testTodaySign = testTodaySign;

        async function refreshFeedDiskCache() {{
            const btn = document.getElementById('btnRefreshFeedCache');
            if (btn) {{
                btn.disabled = true;
                btn.classList.add('opacity-50');
            }}
            try {{
                const res = await fetch('/api/feed/refresh', {{ method: 'POST' }});
                const data = await res.json();
                if (data.ok) {{
                    showToast('âœ… ' + data.message + '\\nÙ„ÛŒØ³Øª Ø¯Ø± Ú†Ù†Ø¯ Ù„Ø­Ø¸Ù‡ Ø¢ÛŒÙ†Ø¯Ù‡ Ø¨Ù‡â€ŒØ±ÙˆØ²Ø±Ø³Ø§Ù†ÛŒ Ù…ÛŒâ€ŒØ´ÙˆØ¯.');
                    setTimeout(() => {{
                        if (typeof fetchFeedDownloads === 'function') window.fetchFeedDownloads(false);
                    }}, 2500);
                }} else {{
                    showToast('Ø®Ø·Ø§ Ø¯Ø± Ø¨Ù‡â€ŒØ±ÙˆØ²Ø±Ø³Ø§Ù†ÛŒ Ú©Ø´: ' + (data.error || 'Ù†Ø§Ø´Ù†Ø§Ø®ØªÙ‡'));
                }}
            }} catch (e) {{
                showToast('Ø®Ø·Ø§ÛŒ Ø§Ø±ØªØ¨Ø§Ø· Ø¨Ø§ Ø³Ø±ÙˆØ±: ' + e.message);
            }} finally {{
                if (btn) {{
                    btn.disabled = false;
                    btn.classList.remove('opacity-50');
                }}
            }}
        }}
        window.refreshFeedDiskCache = refreshFeedDiskCache;

        async function saveAllCategories() {{
            const btn = document.getElementById('btnSaveCategories');
            if (btn) {{
                btn.disabled = true;
                btn.classList.add('opacity-50');
            }}
            try {{
                const rows = document.querySelectorAll('.category-edit-row');
                const updated = [];
                rows.forEach(r => {{
                    const id = parseInt(r.getAttribute('data-id'));
                    const slug = r.getAttribute('data-slug') || '';
                    const url = r.getAttribute('data-url') || '';
                    const path = r.getAttribute('data-path') || '';
                    const emoji = (r.querySelector('.cat-emoji-input')?.value || '').trim() || 'ðŸ’Ž';
                    const title = (r.querySelector('.cat-title-input')?.value || '').trim();
                    updated.push({{ id, slug, url, path, emoji, title }});
                }});

                const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                const res = await fetch('/api/categories/update', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json; charset=utf-8', 'Authorization': 'Bearer ' + pwd, 'X-Admin-Password': pwd }},
                    body: JSON.stringify({{ categories: updated, admin_password: pwd }})
                }});
                const data = await res.json();
                if (data.ok) {{
                    showToast('âœ… ' + data.message);
                }} else {{
                    showToast('Ø®Ø·Ø§ Ø¯Ø± Ø°Ø®ÛŒØ±Ù‡ Ø¯Ø³ØªÙ‡â€ŒØ¨Ù†Ø¯ÛŒâ€ŒÙ‡Ø§: ' + (data.error || 'Ù†Ø§Ø´Ù†Ø§Ø®ØªÙ‡'));
                }}
            }} catch (e) {{
                showToast('Ø®Ø·Ø§ÛŒ Ø§Ø±ØªØ¨Ø§Ø· Ø¨Ø§ Ø³Ø±ÙˆØ±: ' + e.message);
            }} finally {{
                if (btn) {{
                    btn.disabled = false;
                    btn.classList.remove('opacity-50');
                }}
            }}
        }}
        window.saveAllCategories = saveAllCategories;

        let currentFeedPage = 1;
        let currentFeedCategory = '';
        const totalFeedPages = 39;
        window.currentFeedPage = 1;
        window.currentFeedCategory = '';

        async function loadFeedCategories() {{
            const bar = document.getElementById('feedCategoriesBar');
            if (!bar) return;
            try {{
                const res = await fetch('/api/feed/categories');
                const data = await res.json();
                if (data.ok && Array.isArray(data.categories) && data.categories.length > 0) {{
                    const loadingEl = document.getElementById('feedCategoriesLoading');
                    if (loadingEl) loadingEl.remove();

                    const allBtn = '<button type="button" onclick="selectFeedCategory(\\'\\')" class="feed-cat-btn px-3 py-1.5 rounded-lg text-xs font-bold transition whitespace-nowrap ' + (!currentFeedCategory ? 'theme-accent-btn active' : 'theme-card-btn') + '" data-cat="">' +
                        '<span>ðŸŒ ØªÙ…Ø§Ù… Ø¯Ø§Ù†Ù„ÙˆØ¯Ù‡Ø§</span>' +
                    '</button>';

                    const catBtns = data.categories.filter(function(c) {{
                        return c.id !== 1 && c.slug !== 'all-downloads' && c.title !== 'ØªÙ…Ø§Ù… Ø¯Ø§Ù†Ù„ÙˆØ¯Ù‡Ø§';
                    }}).map(function(c) {{
                        const isActive = currentFeedCategory === c.slug;
                        const btnClass = isActive ? 'theme-accent-btn active' : 'theme-card-btn';
                        const safeTitle = (c.title || '').replace(/'/g, "\\\\'");
                        const catEmoji = c.emoji ? (c.emoji + ' ') : '';
                        return '<button type="button" onclick="selectFeedCategory(\\'' + c.slug + '\\')" class="feed-cat-btn px-3 py-1.5 rounded-lg text-xs font-bold transition whitespace-nowrap ' + btnClass + '" data-cat="' + c.slug + '">' +
                            '<span>' + catEmoji + safeTitle + '</span>' +
                        '</button>';
                    }}).join('');

                    bar.innerHTML = allBtn + catBtns;
                }}
            }} catch (err) {{
                console.debug('loadFeedCategories error', err);
            }}
        }}
        window.loadFeedCategories = loadFeedCategories;

        function selectFeedCategory(slug) {{
            currentFeedCategory = slug || '';
            window.currentFeedCategory = currentFeedCategory;
            currentFeedPage = 1;
            window.currentFeedPage = 1;

            const btns = document.querySelectorAll('.feed-cat-btn');
            btns.forEach(function(b) {{
                if (b.getAttribute('data-cat') === currentFeedCategory) {{
                    b.className = 'feed-cat-btn px-3 py-1.5 rounded-lg text-xs font-bold transition whitespace-nowrap theme-accent-btn active';
                }} else {{
                    b.className = 'feed-cat-btn px-3 py-1.5 rounded-lg text-xs font-bold transition whitespace-nowrap theme-card-btn';
                }}
            }});

            fetchFeedDownloads(false, 1, currentFeedCategory);
        }}
        window.selectFeedCategory = selectFeedCategory;

        async function createCourseFromCurrentCategory() {{
            const slug = currentFeedCategory || 'free-download';
            const catName = prompt('Ø¹Ù†ÙˆØ§Ù† Ø¯ÙˆØ±Ù‡ Ø¬Ø¯ÛŒØ¯ Ø¨Ø±Ø§ÛŒ Ø§ÛŒÙ† Ø¯Ø³ØªÙ‡â€ŒØ¨Ù†Ø¯ÛŒ Ø±Ø§ ÙˆØ§Ø±Ø¯ ÙØ±Ù…Ø§ÛŒÛŒØ¯:', 'Ø¯ÙˆØ±Ù‡ Ø¢Ù…ÙˆØ²Ø´ÛŒ ' + (slug || 'Ù‡Ø¯Ø§ÛŒØ§ÛŒ Ø¯Ø§Ù†Ù„ÙˆØ¯ÛŒ'));
            if (!catName) return;
            const btn = document.getElementById('btnCreateCourseFromCat');
            if (btn) {{
                btn.disabled = true;
                btn.innerHTML = '<svg class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path></svg><span>Ø¯Ø± Ø­Ø§Ù„ Ø³Ø§Ø®Øª Ø¯ÙˆØ±Ù‡...</span>';
            }}
            try {{
                const res = await fetch('/api/courses/create-from-category', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json; charset=utf-8' }},
                    body: JSON.stringify({{ category_id: slug, course_name: catName }})
                }});
                const data = await res.json();
                if (data.ok) {{
                    showToast('âœ… ' + (data.message || 'Ø¯ÙˆØ±Ù‡ Ø¨Ø§ Ù…ÙˆÙÙ‚ÛŒØª Ø³Ø§Ø®ØªÙ‡ Ø´Ø¯!'));
                    switchTab('courses');
                }} else {{
                    showToast('âŒ Ø®Ø·Ø§ Ø¯Ø± Ø³Ø§Ø®Øª Ø¯ÙˆØ±Ù‡: ' + (data.error || 'Ù†Ø§Ø´Ù†Ø§Ø®ØªÙ‡'));
                }}
            }} catch(err) {{
                showToast('âŒ Ø®Ø·Ø§ÛŒ Ø§Ø±ØªØ¨Ø§Ø·ÛŒ: ' + err.message);
            }} finally {{
                if (btn) {{
                    btn.disabled = false;
                    btn.innerHTML = '<svg class="w-4 h-4 stroke-[2]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" /></svg><span>âœ¨ Ø³Ø§Ø®Øª Ø¯ÙˆØ±Ù‡ Ø§Ø² Ø§ÛŒÙ† Ø¯Ø³ØªÙ‡â€ŒØ¨Ù†Ø¯ÛŒ</span>';
                }}
            }}
        }}
        window.createCourseFromCurrentCategory = createCourseFromCurrentCategory;

        async function fetchFeedDownloads(force, page, category) {{
            const container = document.getElementById('feedDownloadsContainer');
            const btn = document.getElementById('btnRefreshFeed');
            if (!container) return;
            if (typeof page === 'number' && page >= 1) {{
                currentFeedPage = page;
                window.currentFeedPage = page;
            }}
            if (category !== undefined) {{
                currentFeedCategory = category;
                window.currentFeedCategory = category;
            }}
            const curPageEl = document.getElementById('feedCurrentPage');
            const curPageBottomEl = document.getElementById('feedCurrentPageBottom');
            if (curPageEl) curPageEl.textContent = toPersianDigits(currentFeedPage);
            if (curPageBottomEl) curPageBottomEl.textContent = toPersianDigits(currentFeedPage);

            if (btn) {{
                btn.disabled = true;
                btn.innerHTML = '<svg class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path></svg><span>Ø¯Ø± Ø­Ø§Ù„ Ø±ØµØ¯ Ø³Ø§ÛŒØª...</span>';
            }}
            const loadingMsg = currentFeedCategory
                ? 'Ø¯Ø± Ø­Ø§Ù„ Ø¯Ø±ÛŒØ§ÙØª ÙØ§ÛŒÙ„â€ŒÙ‡Ø§ÛŒ Ø¯Ø³ØªÙ‡â€ŒØ¨Ù†Ø¯ÛŒ Ø§Ù†ØªØ®Ø§Ø¨ÛŒ...'
                : 'Ø¯Ø± Ø­Ø§Ù„ Ø¯Ø±ÛŒØ§ÙØª Û²Ûµ Ù‡Ø¯ÛŒÙ‡ Ø¯Ø§Ù†Ù„ÙˆØ¯ÛŒ ØµÙØ­Ù‡ ' + toPersianDigits(currentFeedPage) + ' Ø§Ø² Ø³Ø§ÛŒØª...';
            if (force || container.children.length === 0 || container.innerText.includes('Ø¯Ø± Ø­Ø§Ù„ Ø¨Ø§Ø±Ú¯Ø°Ø§Ø±ÛŒ')) {{
                container.innerHTML = '<div class="col-span-full text-center py-6 text-xs text-slate-400 font-medium">' + loadingMsg + '</div>';
            }}
            try {{
                const catParam = currentFeedCategory ? ('&cat=' + encodeURIComponent(currentFeedCategory)) : '';
                const res = await fetch('/api/feed/latest?page=' + currentFeedPage + '&limit=25' + (force ? '&force=1' : '') + catParam);
                const data = await res.json();
                if (data.ok && Array.isArray(data.items) && data.items.length > 0) {{
                    container.innerHTML = data.items.map(function(item) {{
                        const title = (item.title || 'Ù‡Ø¯ÛŒÙ‡ Ø¯Ø§Ù†Ù„ÙˆØ¯ÛŒ Ø³Ø§ÛŒØª').replace(/"/g, '&quot;');
                        const fileNum = item.file_number ? '<span class="absolute top-2.5 right-2.5 px-2.5 py-0.5 rounded-lg bg-black/80 backdrop-blur-md text-cyan-300 border border-white/10 text-[10px] font-bold shadow-md">' + item.file_number + '</span>' : '';
                        let c_url = item.cover_url || '';
                        if (c_url && c_url.startsWith('/')) {{
                            c_url = 'https://abasmanesh.com' + c_url;
                        }}
                        
                        const cover = c_url
                            ? '<div class="relative w-full aspect-video overflow-hidden rounded-t-2xl bg-slate-950/70 border-b border-white/5">' +
                                '<img src="' + c_url + '" alt="' + title + '" referrerpolicy="no-referrer" loading="lazy" class="w-full h-full object-cover transition-transform duration-500 hover:scale-105" onerror="this.onerror=null; this.src=&apos;https://abasmanesh.com/assets/images/logo.png&apos;;">' +
                                fileNum +
                              '</div>'
                            : '<div class="w-full aspect-video overflow-hidden rounded-t-2xl  border-b border-white/5 flex items-center justify-center text-3xl">ðŸŽ§</div>';

                        const audioLink = item.audio_url || '';
                        const videoLink = item.video_url || '';
                        const primaryUrl = audioLink || videoLink || (item.links && item.links[0]) || '';
                        const safeUrl = primaryUrl.replace(/'/g, "\\\\'");
                        const safeTitle = title.replace(/'/g, "\\\\'");
                        const safeAudio = (audioLink || '').replace(/'/g, "\\\\'");
                        const safeVideo = (videoLink || '').replace(/'/g, "\\\\'");
                        const safeSource = (item.source_url || '').replace(/'/g, "\\\\'");
                        
                        let audioBtn = '';
                        if (audioLink) {{
                            audioBtn = '<a href="' + audioLink + '" target="_blank" class="theme-card-btn py-1.5 px-2.5 rounded-lg text-cyan-300 flex items-center justify-center gap-1.5 transition text-xs font-medium border border-slate-700/60 hover:border-cyan-500/50">' +
                                '<svg class="w-3.5 h-3.5 stroke-[2]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M19.114 5.636a9 9 0 010 12.728M16.463 8.288a5.25 5.25 0 010 7.424M6.75 8.25l4.72-4.72a.75.75 0 011.28.53v15.88a.75.75 0 01-1.28.53l-4.72-4.72H4.51c-.88 0-1.704-.507-1.938-1.354A9.01 9.01 0 012.25 12c0-.83.112-1.633.322-2.396C2.806 8.756 3.63 8.25 4.51 8.25H6.75z" /></svg>' +
                                '<span>ØµÙˆØª</span>' +
                            '</a>';
                        }}
                        let videoBtn = '';
                        if (videoLink) {{
                            videoBtn = '<a href="' + videoLink + '" target="_blank" class="theme-card-btn py-1.5 px-2.5 rounded-lg text-purple-300 flex items-center justify-center gap-1.5 transition text-xs font-medium border border-slate-700/60 hover:border-purple-500/50">' +
                                '<svg class="w-3.5 h-3.5 stroke-[2]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /><path stroke-linecap="round" stroke-linejoin="round" d="M15.91 11.672a.375.375 0 010 .656l-5.603 3.113a.375.375 0 01-.557-.328V8.887c0-.286.307-.466.557-.327l5.603 3.112z" /></svg>' +
                                '<span>ÙˆÛŒØ¯ÛŒÙˆ</span>' +
                            '</a>';
                        }}

                        const linksGrid = (audioBtn || videoBtn)
                            ? '<div class="grid grid-cols-2 gap-2">' + (audioBtn || '<div></div>') + (videoBtn || '<div></div>') + '</div>'
                            : '<button type="button" onclick="transferFeedDownload(\\'' + safeUrl + '\\', \\'' + safeTitle + '\\', \\'' + safeAudio + '\\', \\'' + safeVideo + '\\', \\'' + safeSource + '\\')" class="w-full theme-card-btn py-1.5 px-2.5 rounded-lg text-orange-300 flex items-center justify-center gap-1.5 transition text-xs font-medium border border-orange-500/30 hover:border-orange-500/50"><svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg><span>Ø¨Ø±ÙˆØ²Ø±Ø³Ø§Ù†ÛŒ Ù„ÛŒÙ†Ú©â€ŒÙ‡Ø§</span></button>';

                        return '<div class="glass rounded-2xl border border-slate-800/80 hover:border-cyan-500/40 transition-all flex flex-col justify-between overflow-hidden shadow-lg hover:shadow-cyan-950/20 group" style="background: var(--card-bg); border-color: var(--card-border);">' +
                            cover +
                            '<div class="p-4 flex flex-col justify-between flex-1 gap-3">' +
                                '<div class="space-y-2">' +
                                    '<div class="flex items-center justify-between text-[11px] text-slate-400 font-mono">' +
                                        '<span class="text-cyan-400 font-semibold">' + (item.tag || 'Ù‡Ø¯ÛŒÙ‡ Ø¯Ø§Ù†Ù„ÙˆØ¯ÛŒ') + '</span>' +
                                        '<span>' + (item.published_at || '') + '</span>' +
                                    '</div>' +
                                    '<h3 class="text-xs md:text-sm font-bold text-slate-100 line-clamp-2 leading-relaxed group-hover:text-cyan-300 transition-colors" title="' + title + '">' +
                                        title +
                                    '</h3>' +
                                '</div>' +
                                '<div class="flex flex-col gap-2 pt-3 border-t border-white/5">' +
                                    linksGrid +
                                    '<button type="button" onclick="transferFeedDownload(\\'' + safeUrl + '\\', \\'' + safeTitle + '\\', \\'' + safeAudio + '\\', \\'' + safeVideo + '\\', \\'' + safeSource + '\\')" class="w-full theme-accent-btn py-2 px-3 rounded-xl text-xs font-bold transition flex items-center justify-center gap-1.5 shadow-md cursor-pointer">' +
                                        '<svg class="w-4 h-4 stroke-[2]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" /></svg>' +
                                        '<span>Ø§Ù†ØªÙ‚Ø§Ù„ Ø¨Ù‡ Ø±Ø¨Ø§Øª Ø¬Ù‡Øª Ø¯Ø§Ù†Ù„ÙˆØ¯ Ùˆ Ù†Ø´Ø±</span>' +
                                    '</button>' +
                                '</div>' +
                            '</div>' +
                        '</div>';
                    }}).join('');
                }} else {{
                    container.innerHTML = '<div class="col-span-full text-center py-6 text-xs text-rose-400 font-medium">âŒ Ø¯Ø±ÛŒØ§ÙØª Ù‡Ø¯Ø§ÛŒØ§ÛŒ Ø¯Ø§Ù†Ù„ÙˆØ¯ÛŒ Ù†Ø§Ù…ÙˆÙÙ‚ Ø¨ÙˆØ¯ ÛŒØ§ ÙØ§ÛŒÙ„ÛŒ ÛŒØ§ÙØª Ù†Ø´Ø¯.</div>';
                }}
            }} catch (err) {{
                container.innerHTML = '<div class="col-span-full text-center py-6 text-xs text-rose-400 font-medium">âŒ Ø®Ø·Ø§ÛŒ Ø§Ø±ØªØ¨Ø§Ø· Ø¨Ø§ Ø³Ø±ÙˆØ±: ' + err.message + '</div>';
            }} finally {{
                if (btn) {{
                    btn.disabled = false;
                    btn.innerHTML = '<svg class="w-4 h-4 stroke-[1.75]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" /></svg><span>Ø¨Ù‡â€ŒØ±ÙˆØ²Ø±Ø³Ø§Ù†ÛŒ ØµÙØ­Ù‡</span>';
                }}
            }}
        }}

        function changeFeedPage(targetPage) {{
            let target = targetPage;
            if (target === 'prev') target = currentFeedPage - 1;
            else if (target === 'next') target = currentFeedPage + 1;
            else target = parseInt(target, 10);

            if (isNaN(target)) return;
            if (target < 1) target = 1;
            if (target > totalFeedPages) target = totalFeedPages;
            if (target === currentFeedPage && document.getElementById('feedDownloadsContainer')?.children?.length > 1) return;

            currentFeedPage = target;
            window.currentFeedPage = target;
            const curPageEl = document.getElementById('feedCurrentPage');
            const curPageBottomEl = document.getElementById('feedCurrentPageBottom');
            if (curPageEl) curPageEl.textContent = toPersianDigits(currentFeedPage);
            if (curPageBottomEl) curPageBottomEl.textContent = toPersianDigits(currentFeedPage);

            fetchFeedDownloads(false, currentFeedPage);
        }}

        let pendingFeedDispatchUrl = '';
        let pendingFeedDispatchTitle = '';
        let pendingFeedAudioUrl = '';
        let pendingFeedVideoUrl = '';
        let pendingFeedActiveFormat = 'audio';

        function setDispatchFormat(fmt) {{
            pendingFeedActiveFormat = fmt;
            const btnAudio = document.getElementById('btnFormatAudio');
            const btnVideo = document.getElementById('btnFormatVideo');
            if (fmt === 'audio') {{
                if (btnAudio) {{
                    btnAudio.className = 'py-2 px-3 rounded-xl border text-xs font-bold transition flex items-center justify-center gap-1.5 theme-accent-btn';
                }}
                if (btnVideo) {{
                    btnVideo.className = 'py-2 px-3 rounded-xl border border-slate-700 text-slate-300 bg-slate-800/80 hover:bg-slate-700 text-xs font-bold transition flex items-center justify-center gap-1.5';
                }}
                pendingFeedDispatchUrl = pendingFeedAudioUrl || pendingFeedVideoUrl;
            }} else {{
                if (btnVideo) {{
                    btnVideo.className = 'py-2 px-3 rounded-xl border text-xs font-bold transition flex items-center justify-center gap-1.5 theme-accent-btn';
                }}
                if (btnAudio) {{
                    btnAudio.className = 'py-2 px-3 rounded-xl border border-slate-700 text-slate-300 bg-slate-800/80 hover:bg-slate-700 text-xs font-bold transition flex items-center justify-center gap-1.5';
                }}
                pendingFeedDispatchUrl = pendingFeedVideoUrl || pendingFeedAudioUrl;
            }}
        }}

        function openFeedDispatchModal(url, title, audioUrl, videoUrl, sourceUrl) {{
            pendingFeedAudioUrl = audioUrl || (url && url.toLowerCase().endsWith('.mp3') ? url : '');
            pendingFeedVideoUrl = videoUrl || (url && url.toLowerCase().endsWith('.mp4') ? url : '');
            if (!pendingFeedAudioUrl && !pendingFeedVideoUrl) {{
                pendingFeedAudioUrl = url;
            }}
            pendingFeedDispatchUrl = pendingFeedAudioUrl || pendingFeedVideoUrl || url;
            pendingFeedDispatchTitle = title || 'Ù‡Ø¯ÛŒÙ‡ Ø¯Ø§Ù†Ù„ÙˆØ¯ÛŒ';
            const titleEl = document.getElementById('feedDispatchModalTitle');
            if (titleEl) titleEl.textContent = pendingFeedDispatchTitle;

            setDispatchFormat(pendingFeedAudioUrl ? 'audio' : 'video');

            const courseSelect = document.getElementById('feedCourseSelect');
            if (courseSelect) {{
                courseSelect.innerHTML = '';
                const cache = window.COURSES_CACHE || window.coursesData || {{}};
                const pids = Object.keys(cache);
                if (pids.length === 0) {{
                    courseSelect.innerHTML = '<option value="">(Ù‡ÛŒÚ† Ø¯ÙˆØ±Ù‡â€ŒØ§ÛŒ Ø¯Ø± Ø³ÛŒØ³ØªÙ… Ø«Ø¨Øª Ù†Ø´Ø¯Ù‡ Ø§Ø³Øª)</option>';
                }} else {{
                    let defaultPid = '';
                    pids.forEach(function(pid) {{
                        const c = cache[pid];
                        const opt = document.createElement('option');
                        opt.value = c.product_id || pid;
                        const isFree = (c.price === 0 || c.price === '0' || c.is_free || (c.name && c.name.includes('ØªÙˆØ­ÛŒØ¯')));
                        if (isFree && !defaultPid) {{
                            defaultPid = opt.value;
                        }}
                        opt.textContent = (isFree ? 'ðŸŽ ' : 'ðŸŽ“ ') + (c.name || pid);
                        courseSelect.appendChild(opt);
                    }});
                    if (defaultPid) {{
                        courseSelect.value = defaultPid;
                    }}
                }}
            }}

            const modal = document.getElementById('feedDispatchModal');
            if (modal) modal.classList.remove('hidden');
        }}

        function closeFeedDispatchModal() {{
            const modal = document.getElementById('feedDispatchModal');
            if (modal) modal.classList.add('hidden');
            pendingFeedDispatchUrl = '';
            pendingFeedDispatchTitle = '';
            pendingFeedAudioUrl = '';
            pendingFeedVideoUrl = '';
        }}

        async function addFeedToCourseEpisodes() {{
            const courseSelect = document.getElementById('feedCourseSelect');
            const pid = courseSelect ? courseSelect.value : '';
            const url = pendingFeedDispatchUrl || pendingFeedAudioUrl || pendingFeedVideoUrl;
            const title = pendingFeedDispatchTitle;
            if (!pid) {{
                showToast('Ù„Ø·ÙØ§Ù‹ ÛŒÚ© Ø¯ÙˆØ±Ù‡ Ø±Ø§ Ø§Ù†ØªØ®Ø§Ø¨ ÙØ±Ù…Ø§ÛŒÛŒØ¯.');
                return;
            }}
            if (!url) {{
                showToast('Ø¢Ø¯Ø±Ø³ ÙØ§ÛŒÙ„ Ù…Ø¹ØªØ¨Ø± Ù†ÛŒØ³Øª.');
                return;
            }}
            const btn = document.getElementById('btnAddFeedToCourse');
            if (btn) {{
                btn.disabled = true;
                btn.innerText = 'â³ Ø¯Ø± Ø­Ø§Ù„ Ø§ÙØ²ÙˆØ¯Ù†...';
            }}
            try {{
                const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                const res = await fetch('/api/courses/episodes/add', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json; charset=utf-8',
                        'Authorization': 'Bearer ' + pwd,
                        'X-Admin-Password': pwd
                    }},
                    body: JSON.stringify({{
                        product_id: pid,
                        title: title,
                        url: url,
                        filename: title ? (title.replace(/[^\\w\\s\\-\\.\\u0600-\\u06FF]/gi, '') + (pendingFeedActiveFormat === 'video' ? '.mp4' : '.mp3')) : ''
                    }})
                }});
                const data = await res.json();
                if (data.ok) {{
                    showToast('âœ… ' + (data.message || 'ÙØ§ÛŒÙ„ Ø¨Ø§ Ù…ÙˆÙÙ‚ÛŒØª Ø¨Ù‡ Ø³Ø±ÙØµÙ„â€ŒÙ‡Ø§ÛŒ Ø¯ÙˆØ±Ù‡ Ø§ÙØ²ÙˆØ¯Ù‡ Ø´Ø¯!'));
                    closeFeedDispatchModal();
                }} else {{
                    showToast('âŒ Ø®Ø·Ø§ Ø¯Ø± Ø§ÙØ²ÙˆØ¯Ù† Ø¨Ù‡ Ø³Ø±ÙØµÙ„â€ŒÙ‡Ø§: ' + (data.error || 'Ù†Ø§Ù…ÙˆÙÙ‚'));
                }}
            }} catch (err) {{
                showToast('âŒ Ø®Ø·Ø§ÛŒ Ø§Ø±ØªØ¨Ø§Ø· Ø¨Ø§ Ø³Ø±ÙˆØ±: ' + err.message);
            }} finally {{
                if (btn) {{
                    btn.disabled = false;
                    btn.innerHTML = '<span>ðŸ“¦</span> Ø§ÙØ²ÙˆØ¯Ù† Ø¨Ù‡ Ø¹Ù†ÙˆØ§Ù† Ù‚Ø³Ù…Øª Ø¬Ø¯ÛŒØ¯ Ø§ÛŒÙ† Ø¯ÙˆØ±Ù‡';
                }}
            }}
        }}

        async function executeFeedMultiDispatch() {{
            const targets = [];
            if (document.getElementById('chkDispatchTg')?.checked) targets.push('telegram');
            if (document.getElementById('chkDispatchBale')?.checked) targets.push('bale');
            if (document.getElementById('chkDispatchRubika')?.checked) targets.push('rubika_user');
            if (document.getElementById('chkDispatchSoroush')?.checked) targets.push('soroush');

            if (targets.length === 0) {{
                showToast('âŒ Ù„Ø·ÙØ§Ù‹ Ø­Ø¯Ø§Ù‚Ù„ ÛŒÚ© Ù¾Ù„ØªÙØ±Ù… Ù…Ù‚ØµØ¯ Ø±Ø§ Ø§Ù†ØªØ®Ø§Ø¨ ÙØ±Ù…Ø§ÛŒÛŒØ¯.');
                return;
            }}

            const wantAudio = !!document.getElementById('chkFormatAudio')?.checked;
            const wantVideo = !!document.getElementById('chkFormatVideo')?.checked;
            const urlsToDispatch = [];
            if (wantAudio && pendingFeedAudioUrl) {{
                urlsToDispatch.push({{ url: pendingFeedAudioUrl, label: 'ØµÙˆØªÛŒ MP3' }});
            }}
            if (wantVideo && pendingFeedVideoUrl) {{
                urlsToDispatch.push({{ url: pendingFeedVideoUrl, label: 'ØªØµÙˆÛŒØ±ÛŒ MP4' }});
            }}
            if (urlsToDispatch.length === 0) {{
                const fallbackUrl = pendingFeedDispatchUrl || pendingFeedAudioUrl || pendingFeedVideoUrl;
                if (fallbackUrl) urlsToDispatch.push({{ url: fallbackUrl, label: 'Ø±Ø³Ø§Ù†Ù‡' }});
            }}

            const title = pendingFeedDispatchTitle;
            closeFeedDispatchModal();
            if (urlsToDispatch.length === 0) return;

            const resBox = document.getElementById('dispatchResult');
            if (resBox) {{
                resBox.className = 'mt-4 p-3 rounded-xl text-xs font-mono block bg-slate-800 text-slate-300 border border-slate-700';
                resBox.innerText = 'â³ Ø¯Ø± Ø­Ø§Ù„ Ø¯Ø§Ù†Ù„ÙˆØ¯ Ùˆ Ø§Ø±Ø³Ø§Ù„ Ù‡Ù…Ø²Ù…Ø§Ù† Ù‡Ø¯ÛŒÙ‡: ' + title + ' Ø¨Ù‡ Ù¾Ù„ØªÙØ±Ù…â€ŒÙ‡Ø§ÛŒ Ù…Ù†ØªØ®Ø¨...';
            }}
            try {{
                const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                let allSuccess = true;
                for (const item of urlsToDispatch) {{
                    const res = await fetch('/api/dispatch_url', {{
                        method: 'POST',
                        headers: {{
                            'Content-Type': 'application/json; charset=utf-8',
                            'Authorization': 'Bearer ' + pwd,
                            'X-Admin-Password': pwd
                        }},
                        body: JSON.stringify({{ url: item.url, targets: targets, target: targets.join(',') }})
                    }});
                    const data = await res.json();
                    if (!data.ok) allSuccess = false;
                }}
                if (allSuccess) {{
                    showToast('âœ… Ø§Ø±Ø³Ø§Ù„ Ø¨Ø§ Ù…ÙˆÙÙ‚ÛŒØª Ø¨Ù‡ ' + targets.join(' Ùˆ ') + ' Ø§Ù†Ø¬Ø§Ù… Ø´Ø¯!');
                    if (resBox) {{
                        resBox.className = 'mt-4 p-3 rounded-xl text-xs font-mono block bg-emerald-950 text-emerald-300 border border-emerald-700';
                        resBox.innerText = 'âœ… Ù†Ø³Ø®Ù‡(Ù‡Ø§ÛŒ) Ø§Ù†ØªØ®Ø§Ø¨ÛŒ ÙØ§ÛŒÙ„ Ù‡Ø¯ÛŒÙ‡ Ø¨Ø§ Ù…ÙˆÙÙ‚ÛŒØª Ø§Ø±Ø³Ø§Ù„ Ø´Ø¯!';
                    }}
                }} else {{
                    showToast('âš ï¸ Ø§Ø±Ø³Ø§Ù„ ÙØ§ÛŒÙ„â€ŒÙ‡Ø§ Ø¨Ù‡ Ø¨Ø±Ø®ÛŒ Ù…Ù‚Ø§ØµØ¯ Ø§Ù†Ø¬Ø§Ù… Ø´Ø¯.');
                }}
            }} catch (err) {{
                showToast('âŒ Ø®Ø·Ø§ÛŒ Ø§Ø±ØªØ¨Ø§Ø· Ø¨Ø§ Ø³Ø±ÙˆØ±: ' + err.message);
            }}
        }}

        async function executeFeedDispatch(target) {{
            const url = pendingFeedDispatchUrl || pendingFeedAudioUrl || pendingFeedVideoUrl;
            const title = pendingFeedDispatchTitle;
            closeFeedDispatchModal();
            if (!url) return;

            const directInput = document.getElementById('directUrl');
            if (directInput) {{
                directInput.value = url;
            }}
            const resBox = document.getElementById('dispatchResult');
            if (resBox) {{
                resBox.className = 'mt-4 p-3 rounded-xl text-xs font-mono block bg-slate-800 text-slate-300 border border-slate-700';
                resBox.innerText = 'â³ Ø¯Ø± Ø­Ø§Ù„ Ø¯Ø§Ù†Ù„ÙˆØ¯ Ùˆ Ù¾Ø±Ø¯Ø§Ø²Ø´ Ø§Ø³ØªØ±ÛŒÙ… Ù‡Ø¯ÛŒÙ‡: ' + title + ' ... Ù„Ø·ÙØ§Ù‹ Ø´Ú©ÛŒØ¨Ø§ Ø¨Ø§Ø´ÛŒØ¯.';
            }}
            try {{
                const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                const res = await fetch('/api/dispatch_url', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json; charset=utf-8',
                        'Authorization': 'Bearer ' + pwd,
                        'X-Admin-Password': pwd
                    }},
                    body: JSON.stringify({{ url: url, target: target || 'all' }})
                }});
                const data = await res.json();
                if (data.ok) {{
                    showToast('âœ… ÙØ§ÛŒÙ„ Ù‡Ø¯ÛŒÙ‡ Ø¨Ø§ Ù…ÙˆÙÙ‚ÛŒØª Ø¯Ø§Ù†Ù„ÙˆØ¯ Ùˆ Ø¨Ù‡ ' + (data.target || 'Ù¾ÛŒØ§Ù…â€ŒØ±Ø³Ø§Ù†â€ŒÙ‡Ø§') + ' Ù…Ù†ØªÙ‚Ù„ Ø´Ø¯!');
                    if (resBox) {{
                        resBox.className = 'mt-4 p-3 rounded-xl text-xs font-mono block bg-emerald-950 text-emerald-300 border border-emerald-700';
                        resBox.innerText = 'âœ… ' + (data.message || 'ÙØ§ÛŒÙ„ Ù‡Ø¯ÛŒÙ‡ Ø¨Ø§ Ù…ÙˆÙÙ‚ÛŒØª Ø¯Ø§Ù†Ù„ÙˆØ¯ Ùˆ Ø§Ø±Ø³Ø§Ù„ Ø´Ø¯!');
                    }}
                }} else {{
                    showToast('âŒ Ø®Ø·Ø§ Ø¯Ø± Ø¯Ø§Ù†Ù„ÙˆØ¯ Ùˆ Ø§Ø±Ø³Ø§Ù„: ' + (data.error || 'Ø¹Ù…Ù„ÛŒØ§Øª Ù†Ø§Ù…ÙˆÙÙ‚ Ø¨ÙˆØ¯'));
                    if (resBox) {{
                        resBox.className = 'mt-4 p-3 rounded-xl text-xs font-mono block bg-rose-950 text-rose-300 border border-rose-700';
                        resBox.innerText = 'âŒ Ø®Ø·Ø§: ' + (data.error || 'Ù†Ø§Ù…ÙˆÙÙ‚');
                    }}
                }}
            }} catch (err) {{
                showToast('âŒ Ø®Ø·Ø§ÛŒ Ø§Ø±ØªØ¨Ø§Ø· Ø¨Ø§ Ø³Ø±ÙˆØ±: ' + err.message);
            }}
        }}

        async function transferFeedDownload(url, title, audioUrl, videoUrl, sourceUrl, btn) {{
            if (!audioUrl && !videoUrl) {{
                const badge = document.getElementById('crawlerStatusBadge');
                if (badge && badge.innerText.includes('OFFLINE')) {{
                    showToast('Ø´Ù…Ø§ Ø¨Ù‡ Ø­Ø³Ø§Ø¨ Ù…Ø±Ø¬Ø¹ Ù…ØªØµÙ„ Ù†ÛŒØ³ØªÛŒØ¯. Ù„Ø·ÙØ§Ù‹ Ø§Ø¨ØªØ¯Ø§ ÙˆØ§Ø±Ø¯ Ø­Ø³Ø§Ø¨ Ø´ÙˆÛŒØ¯.');
                    const m = document.getElementById('feedAuthModal');
                    if (m) m.classList.remove('hidden');
                    return;
                }}
                if (sourceUrl) {{
                    try {{
                        const loadingToast = document.createElement('div');
                        loadingToast.id = 'rescrapToast';
                        loadingToast.className = 'fixed bottom-4 right-4 bg-slate-800 border border-orange-500 text-white px-4 py-2 rounded-xl text-xs z-50';
                        loadingToast.innerText = 'â³ Ø¯Ø± Ø­Ø§Ù„ Ø¯Ø±ÛŒØ§ÙØª Ù„ÛŒÙ†Ú©â€ŒÙ‡Ø§ÛŒ Ø¯Ø§Ù†Ù„ÙˆØ¯ Ø§Ø² Ø³Ø§ÛŒØª Ø§ØµÙ„ÛŒ...';
                        document.body.appendChild(loadingToast);

                        const res = await fetch('/api/crawler/rescrap-item', {{ method: 'POST', body: JSON.stringify({{ url: sourceUrl }}) }});
                        const data = await res.json();
                        document.body.removeChild(loadingToast);
                        if (data.ok && (data.audio_url || data.video_url || data.url)) {{
                            if (btn && btn.parentElement) {{
                                const safeA = (data.audio_url || '').replace(/'/g, "\\'");
                                const safeV = (data.video_url || '').replace(/'/g, "\\'");
                                let newHtml = '<div class="grid grid-cols-2 gap-2">';
                                if (data.audio_url) {{
                                    newHtml += '<a href="' + data.audio_url + '" target="_blank" class="theme-card-btn py-1.5 px-2.5 rounded-lg text-cyan-300 flex items-center justify-center gap-1.5 transition text-xs font-medium border border-slate-700/60 hover:border-cyan-500/50">' +
                                        '<svg class="w-3.5 h-3.5 stroke-[2]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M19.114 5.636a9 9 0 010 12.728M16.463 8.288a5.25 5.25 0 010 7.424M6.75 8.25l4.72-4.72a.75.75 0 011.28.53v15.88a.75.75 0 01-1.28.53l-4.72-4.72H4.51c-.88 0-1.704-.507-1.938-1.354A9.01 9.01 0 012.25 12c0-.83.112-1.633.322-2.396C2.806 8.756 3.63 8.25 4.51 8.25H6.75z" /></svg>' +
                                        '<span>ØµÙˆØª</span>' +
                                    '</a>';
                                }} else {{
                                    newHtml += '<div></div>';
                                }}
                                if (data.video_url) {{
                                    newHtml += '<a href="' + data.video_url + '" target="_blank" class="theme-card-btn py-1.5 px-2.5 rounded-lg text-purple-300 flex items-center justify-center gap-1.5 transition text-xs font-medium border border-slate-700/60 hover:border-purple-500/50">' +
                                        '<svg class="w-3.5 h-3.5 stroke-[2]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /><path stroke-linecap="round" stroke-linejoin="round" d="M15.91 11.672a.375.375 0 010 .656l-5.603 3.113a.375.375 0 01-.557-.328V8.887c0-.286.307-.466.557-.327l5.603 3.112z" /></svg>' +
                                        '<span>ÙˆÛŒØ¯ÛŒÙˆ</span>' +
                                    '</a>';
                                }} else {{
                                    newHtml += '<div></div>';
                                }}
                                newHtml += '</div>';
                                btn.outerHTML = newHtml;
                            }}
                            openFeedDispatchModal(data.url || data.audio_url || data.video_url, title, data.audio_url, data.video_url, sourceUrl);
                        }} else {{
                            showToast('âŒ Ø¢Ø¯Ø±Ø³ Ø¯Ø§Ù†Ù„ÙˆØ¯ÛŒ Ø¨Ø±Ø§ÛŒ Ø§ÛŒÙ† Ø¢ÛŒØªÙ… Ø¯Ø± Ø³Ø±ÙˆØ± ÛŒØ§ÙØª Ù†Ø´Ø¯.');
                        }}
                    }} catch (e) {{
                        const tb = document.getElementById('rescrapToast');
                        if (tb) tb.remove();
                        showToast('âŒ Ø®Ø·Ø§ÛŒ Ø§Ø±ØªØ¨Ø§Ø· Ø¨Ø§ Ø³Ø±ÙˆØ±: ' + e.message);
                    }}
                }} else {{
                    showToast('âŒ Ø¢Ø¯Ø±Ø³ Ø¯Ø§Ù†Ù„ÙˆØ¯ÛŒ Ø¨Ø±Ø§ÛŒ Ø§ÛŒÙ† Ø¢ÛŒØªÙ… ÛŒØ§ÙØª Ù†Ø´Ø¯.');
                }}
            }} else {{
                openFeedDispatchModal(url, title, audioUrl, videoUrl, sourceUrl);
            }}
        }}

        // Initialize Studio Sort Select and Feed from localStorage / API
        window.addEventListener('DOMContentLoaded', function() {{
            try {{
                const savedSort = localStorage.getItem('unfinit_studio_sort') || 'newest';
                const sortSelect = document.getElementById('studioSortSelect');
                if (sortSelect) {{
                    sortSelect.value = savedSort;
                }}
                const curTab = localStorage.getItem('unfinit_active_tab') || 'dashboard';
                if (curTab === 'downloads' && typeof window.lazyLoadDownloadsFeed === 'function') {{
                    window.lazyLoadDownloadsFeed();
                }}
                if (typeof window.initProductSubtabsDragAndDrop === 'function') {{
                    window.initProductSubtabsDragAndDrop();
                }}
            }} catch (e) {{}}
        }});

                let currentSvgContent = '';
                let currentSvgFilename = 'vector.svg';

                function setSvgColor(hex) {{
                    const picker = document.getElementById('svgRecolorPicker');
                    const input = document.getElementById('svgHexInput');
                    if (picker) picker.value = hex;
                    if (input) input.value = hex;
                }}

                function syncSvgColorPicker(val) {{
                    const input = document.getElementById('svgHexInput');
                    if (input) input.value = val;
                }}

                function syncSvgHexInput(val) {{
                    val = (val || '').trim();
                    if (val && !val.startsWith('#')) val = '#' + val;
                    const picker = document.getElementById('svgRecolorPicker');
                    if (picker && /^#[0-9A-Fa-f]{{6}}$/.test(val)) {{
                        picker.value = val;
                    }}
                }}

                function renderSvgInPreview(svgText) {{
                    currentSvgContent = svgText || '';
                    const previewEl = document.getElementById('svgLivePreview');
                    const badgeEl = document.getElementById('svgDimensionsBadge');
                    if (previewEl) {{
                        if (!svgText) {{
                            previewEl.innerHTML = '<span class="text-xs text-slate-500">ÙØ§ÛŒÙ„ SVG Ø§Ù†ØªØ®Ø§Ø¨ Ø´Ø¯Ù‡ Ø¯Ø± Ø§ÛŒÙ†Ø¬Ø§ Ø±Ø³Ù… Ù…ÛŒâ€ŒØ´ÙˆØ¯</span>';
                            if (badgeEl) badgeEl.textContent = '-';
                            return;
                        }}
                        previewEl.innerHTML = svgText;
                        const svgEl = previewEl.querySelector('svg');
                        if (svgEl) {{
                            svgEl.style.maxWidth = '100%';
                            svgEl.style.maxHeight = '240px';
                            svgEl.style.height = 'auto';
                            svgEl.style.display = 'block';
                            svgEl.style.margin = 'auto';
                            const w = svgEl.getAttribute('width') || '';
                            const h = svgEl.getAttribute('height') || '';
                            const vb = svgEl.getAttribute('viewBox') || '';
                            if (badgeEl) {{
                                badgeEl.textContent = (w && h) ? (w + ' Ã— ' + h) : (vb ? ('viewBox: ' + vb) : 'SVG Vector');
                            }}
                        }}
                    }}
                }}

                function handleSvgFileSelected(files) {{
                    if (!files || files.length === 0) return;
                    const file = files[0];
                    currentSvgFilename = file.name || 'vector.svg';
                    const reader = new FileReader();
                    reader.onload = function(e) {{
                        renderSvgInPreview(e.target.result);
                    }};
                    reader.readAsText(file);
                }}

                async function handleSvgRecolor() {{
                    if (!currentSvgContent) {{
                        showToast('Ù„Ø·ÙØ§Ù‹ Ø§Ø¨ØªØ¯Ø§ ÛŒÚ© ÙØ§ÛŒÙ„ ÙˆÚ©ØªÙˆØ± SVG Ø§Ù†ØªØ®Ø§Ø¨ Ù†Ù…ÙˆØ¯Ù‡ ÛŒØ§ Ù…ØªÙ†ÛŒ ÙˆØ§Ø±Ø¯ Ù†Ù…Ø§ÛŒÛŒØ¯.');
                        return;
                    }}
                    const hexInput = document.getElementById('svgHexInput');
                    const color = (hexInput ? hexInput.value : '#FFFFFF') || '#FFFFFF';
                    const btn = document.getElementById('btnSvgRecolor');
                    if (btn) {{
                        btn.disabled = true;
                        btn.innerHTML = '<span>â³</span> Ø¯Ø± Ø­Ø§Ù„ ØªØºÛŒÛŒØ± Ø±Ù†Ú¯...';
                    }}
                    try {{
                        const res = await fetch('/api/media/recolor-svg', {{
                            method: 'POST',
                            headers: {{
                                'Content-Type': 'application/json; charset=utf-8',
                                'X-Admin-Password': window.currentAdminPassword || ''
                            }},
                            body: JSON.stringify({{
                                svg: currentSvgContent,
                                color: color,
                                filename: currentSvgFilename
                            }})
                        }});
                        const data = await res.json();
                        if (data.ok && data.svg) {{
                            renderSvgInPreview(data.svg);
                            showToast('âœ… Ø±Ù†Ú¯ Ø§Ø¬Ø²Ø§ÛŒ ÙˆÚ©ØªÙˆØ± Ø¨Ø§ Ù…ÙˆÙÙ‚ÛŒØª Ø¨Ù‡ ' + color + ' ØªØºÛŒÛŒØ± ÛŒØ§ÙØª.');
                        }} else {{
                            showToast('âŒ Ø®Ø·Ø§ Ø¯Ø± ØªØºÛŒÛŒØ± Ø±Ù†Ú¯ ÙˆÚ©ØªÙˆØ±: ' + (data.error || 'Ù†Ø§Ù…ÙˆÙÙ‚'));
                        }}
                    }} catch (err) {{
                        showToast('âŒ Ø®Ø·Ø§ÛŒ Ø§Ø±ØªØ¨Ø§Ø· Ø¨Ø§ Ø³Ø±ÙˆØ±: ' + err.message);
                    }} finally {{
                        if (btn) {{
                            btn.disabled = false;
                            btn.innerHTML = '<span>ðŸŽ¨</span> Ø§Ø¹Ù…Ø§Ù„ ØªØºÛŒÛŒØ± Ø±Ù†Ú¯';
                        }}
                    }}
                }}

                function downloadCurrentSvg() {{
                    if (!currentSvgContent) {{
                        showToast('ÙØ§ÛŒÙ„ SVG ÙØ¹Ø§Ù„ÛŒ Ø¨Ø±Ø§ÛŒ Ø¯Ø§Ù†Ù„ÙˆØ¯ ÙˆØ¬ÙˆØ¯ Ù†Ø¯Ø§Ø±Ø¯.');
                        return;
                    }}
                    const blob = new Blob([currentSvgContent], {{ type: 'image/svg+xml;charset=utf-8' }});
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = currentSvgFilename || 'vector.svg';
                    document.body.appendChild(a);
                    a.click();
                    a.remove();
                    setTimeout(function() {{ URL.revokeObjectURL(url); }}, 1000);
                }}

                async function handleGenerateTextSvg() {{
                    const textInput = document.getElementById('svgTextInput');
                    const sizeInput = document.getElementById('svgTextSizeInput');
                    const hexInput = document.getElementById('svgHexInput');
                    const text = (textInput ? textInput.value : '').trim();
                    const fontSize = parseInt(sizeInput ? sizeInput.value : '48') || 48;
                    const fill = (hexInput ? hexInput.value : '#FFFFFF') || '#FFFFFF';

                    if (!text) {{
                        showToast('Ù„Ø·ÙØ§Ù‹ Ø§Ø¨ØªØ¯Ø§ Ù…ØªÙ† Ù…ÙˆØ±Ø¯ Ù†Ø¸Ø± Ø±Ø§ ÙˆØ§Ø±Ø¯ Ù†Ù…Ø§ÛŒÛŒØ¯.');
                        return;
                    }}

                    try {{
                        const res = await fetch('/api/media/text-to-svg', {{
                            method: 'POST',
                            headers: {{
                                'Content-Type': 'application/json; charset=utf-8',
                                'X-Admin-Password': window.currentAdminPassword || ''
                            }},
                            body: JSON.stringify({{
                                text: text,
                                font_size: fontSize,
                                fill: fill
                            }})
                        }});
                        const data = await res.json();
                        if (data.ok && data.svg) {{
                            currentSvgFilename = (text.replace(/[^\\w\\s\\-\\.\\u0600-\\u06FF]/gi, '').slice(0, 20) || 'typography') + '.svg';
                            renderSvgInPreview(data.svg);
                            showToast('âœ… ÙˆÚ©ØªÙˆØ± Ù…ØªÙ†ÛŒ Ø¨Ø§ Ù…ÙˆÙÙ‚ÛŒØª Ø§ÛŒØ¬Ø§Ø¯ Ø´Ø¯.');
                        }} else {{
                            showToast('âŒ Ø®Ø·Ø§ Ø¯Ø± ØªÙˆÙ„ÛŒØ¯ ÙˆÚ©ØªÙˆØ± Ù…ØªÙ†ÛŒ: ' + (data.error || 'Ù†Ø§Ù…ÙˆÙÙ‚'));
                        }}
                    }} catch (err) {{
                        showToast('âŒ Ø®Ø·Ø§ÛŒ Ø§Ø±ØªØ¨Ø§Ø· Ø¨Ø§ Ø³Ø±ÙˆØ±: ' + err.message);
                    }}
                }}

                async function handleSvgConvert(e) {{
                    if (e) e.preventDefault();
                    const fileInput = document.getElementById('svgFileInput');
                    const formatSelect = document.getElementById('svgOutputFormat');
                    const btn = document.getElementById('btnSvgConvert');
                    const resultDiv = document.getElementById('svgConvertResult');

                    const hasFile = fileInput && fileInput.files && fileInput.files.length > 0;
                    if (!hasFile && !currentSvgContent) {{
                        showToast('Ù„Ø·ÙØ§Ù‹ Ø§Ø¨ØªØ¯Ø§ ÛŒÚ© ÙØ§ÛŒÙ„ ÙˆÚ©ØªÙˆØ± SVG Ø§Ù†ØªØ®Ø§Ø¨ ÙØ±Ù…Ø§ÛŒÛŒØ¯ ÛŒØ§ Ø§Ø² Ø¨Ø®Ø´ Ø³Ø§Ø®Øª ÙˆÚ©ØªÙˆØ± Ø§Ø³ØªÙØ§Ø¯Ù‡ Ù†Ù…Ø§ÛŒÛŒØ¯.');
                        return;
                    }}

                    const format = (formatSelect ? formatSelect.value : 'png') || 'png';
                    let fname = hasFile ? fileInput.files[0].name : (currentSvgFilename || 'vector.svg');

                    if (btn) {{
                        btn.disabled = true;
                        btn.innerHTML = '<span>â³</span> Ø¯Ø± Ø­Ø§Ù„ ØªØ¨Ø¯ÛŒÙ„...';
                    }}
                    if (resultDiv) {{
                        resultDiv.classList.remove('hidden');
                        resultDiv.className = 'mt-4 p-3 rounded-xl text-xs font-mono bg-cyan-950/60 border border-cyan-800 text-cyan-300 flex items-center justify-between';
                        resultDiv.innerHTML = '<span>âš¡ï¸ Ø¯Ø± Ø­Ø§Ù„ Ù¾Ø±Ø¯Ø§Ø²Ø´ ÙØ§ÛŒÙ„ ÙˆÚ©ØªÙˆØ± Ùˆ Ø±Ù†Ø¯Ø± ØªØµÙˆÛŒØ±...</span>';
                    }}

                    const sendConvertRequest = async function(b64Data, filename) {{
                        try {{
                            const res = await fetch('/api/media/convert-svg', {{
                                method: 'POST',
                                headers: {{
                                    'Content-Type': 'application/json; charset=utf-8',
                                    'X-Admin-Password': window.currentAdminPassword || ''
                                }},
                                body: JSON.stringify({{
                                    data: b64Data,
                                    format: format,
                                    filename: filename
                                }})
                            }});
                            const data = await res.json();
                            if (data.ok) {{
                                if (resultDiv) {{
                                    resultDiv.className = 'mt-4 p-3 rounded-xl text-xs font-mono bg-emerald-950/60 border border-emerald-800 text-emerald-300 flex items-center justify-between';
                                    resultDiv.innerHTML = '<span>âœ… ØªØ¨Ø¯ÛŒÙ„ Ù…ÙˆÙÙ‚: ' + data.filename + ' (' + Math.round((data.size || 0) / 1024) + ' KB)</span>' +
                                        '<a href="' + data.data + '" download="' + data.filename + '" class="px-3 py-1 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg font-sans font-bold transition">Ø¯Ø±ÛŒØ§ÙØª ÙØ§ÛŒÙ„</a>';
                                }}
                                const a = document.createElement('a');
                                a.href = data.data;
                                a.download = data.filename;
                                document.body.appendChild(a);
                                a.click();
                                a.remove();
                            }} else {{
                                if (resultDiv) {{
                                    resultDiv.className = 'mt-4 p-3 rounded-xl text-xs font-mono bg-rose-950/60 border border-rose-800 text-rose-300';
                                    resultDiv.innerText = 'âŒ Ø®Ø·Ø§ÛŒ ØªØ¨Ø¯ÛŒÙ„: ' + (data.error || 'Ø¹Ù…Ù„ÛŒØ§Øª Ù†Ø§Ù…ÙˆÙÙ‚ Ø¨ÙˆØ¯');
                                }}
                            }}
                        }} catch (err) {{
                            if (resultDiv) {{
                                resultDiv.className = 'mt-4 p-3 rounded-xl text-xs font-mono bg-rose-950/60 border border-rose-800 text-rose-300';
                                resultDiv.innerText = 'âŒ Ø®Ø·Ø§ÛŒ Ø§Ø±ØªØ¨Ø§Ø· Ø¨Ø§ Ø³Ø±ÙˆØ±: ' + err.message;
                            }}
                        }} finally {{
                            if (btn) {{
                                btn.disabled = false;
                                btn.innerHTML = '<span>âš¡ï¸</span> ØªØ¨Ø¯ÛŒÙ„ Ùˆ Ø¯Ø±ÛŒØ§ÙØª ØªØµÙˆÛŒØ±';
                            }}
                        }}
                    }};

                    if (hasFile) {{
                        const reader = new FileReader();
                        reader.onload = function() {{
                            sendConvertRequest(reader.result, fname);
                        }};
                        reader.onerror = function() {{
                            if (resultDiv) {{
                                resultDiv.className = 'mt-4 p-3 rounded-xl text-xs font-mono bg-rose-950/60 border border-rose-800 text-rose-300';
                                resultDiv.innerText = 'âŒ Ø®Ø·Ø§ Ø¯Ø± Ø®ÙˆØ§Ù†Ø¯Ù† ÙØ§ÛŒÙ„ ÙˆÚ©ØªÙˆØ± Ø§Ø² Ø¯Ø³ØªÚ¯Ø§Ù‡.';
                            }}
                            if (btn) {{
                                btn.disabled = false;
                                btn.innerHTML = '<span>âš¡ï¸</span> ØªØ¨Ø¯ÛŒÙ„ Ùˆ Ø¯Ø±ÛŒØ§ÙØª ØªØµÙˆÛŒØ±';
                            }}
                        }};
                        reader.readAsDataURL(fileInput.files[0]);
                    }} else {{
                        try {{
                            const b64 = 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(currentSvgContent)));
                            sendConvertRequest(b64, fname);
                        }} catch (e) {{
                            if (resultDiv) {{
                                resultDiv.className = 'mt-4 p-3 rounded-xl text-xs font-mono bg-rose-950/60 border border-rose-800 text-rose-300';
                                resultDiv.innerText = 'âŒ Ø®Ø·Ø§ Ø¯Ø± Ú©Ø¯Ú¯Ø°Ø§Ø±ÛŒ ÙˆÚ©ØªÙˆØ±: ' + e.message;
                            }}
                            if (btn) {{
                                btn.disabled = false;
                                btn.innerHTML = '<span>âš¡ï¸</span> ØªØ¨Ø¯ÛŒÙ„ Ùˆ Ø¯Ø±ÛŒØ§ÙØª ØªØµÙˆÛŒØ±';
                            }}
                        }}
                    }}
                }}
                window.handleSvgConvert = handleSvgConvert;
                window.setSvgColor = setSvgColor;
                window.syncSvgColorPicker = syncSvgColorPicker;
                window.syncSvgHexInput = syncSvgHexInput;
                window.renderSvgInPreview = renderSvgInPreview;
                window.handleSvgFileSelected = handleSvgFileSelected;
                window.handleSvgRecolor = handleSvgRecolor;
                window.downloadCurrentSvg = downloadCurrentSvg;
                window.handleGenerateTextSvg = handleGenerateTextSvg;

                window.handleStudioFilesSelect = handleStudioFilesSelect;
                window.previewStudioCover = previewStudioCover;
                window.openSpecsModal = openSpecsModal;
                window.closeSpecsModal = closeSpecsModal;
                window.openTagModal = openTagModal;
                window.closeTagModal = closeTagModal;
                window.handleSaveStudioTags = handleSaveStudioTags;
                window.toggleSelectAllDrops = toggleSelectAllDrops;
                window.updateSelectedCount = updateSelectedCount;
                window.getSelectedDropIds = getSelectedDropIds;
                window.openBatchTagModal = openBatchTagModal;
                window.closeBatchTagModal = closeBatchTagModal;
                window.handleSaveBatchTags = handleSaveBatchTags;
                window.dispatchDrop = dispatchDrop;
                window.formatSecToTime = formatSecToTime;
                window.parseTimeToSec = parseTimeToSec;
                window.openCutterModal = openCutterModal;
                window.closeCutterModal = closeCutterModal;
                window.toggleWavePlayPause = toggleWavePlayPause;
                window.stopWaveSurfer = stopWaveSurfer;
                window.setStartFromCursor = setStartFromCursor;
                window.setEndFromCursor = setEndFromCursor;
                window.submitAudioCut = submitAudioCut;
                window.deleteStudioDrop = deleteStudioDrop;
                window.batchDeleteStudioDrops = batchDeleteStudioDrops;
                window.changeStudioSort = changeStudioSort;
                window.refreshStudioList = refreshStudioList;
                window.cleanupStudioDrops = cleanupStudioDrops;
                window.loadFeedCategories = loadFeedCategories;
                window.selectFeedCategory = selectFeedCategory;
                window.fetchFeedDownloads = fetchFeedDownloads;

        async function syncFeedThumbnails(btn) {{
            if (!btn) return;
            const originalHtml = btn.innerHTML;
            btn.innerHTML = '<svg class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path></svg><span>Ø¯Ø± Ø­Ø§Ù„ Ù‡Ù…Ú¯Ø§Ù…â€ŒØ³Ø§Ø²ÛŒ...</span>';
            btn.disabled = true;
            try {{
                const res = await fetch('/api/feed/sync', {{ method: 'POST' }});
                const data = await res.json();
                if (data.ok) {{
                    showToast('âœ… Ø§Ø·Ù„Ø§Ø¹Ø§Øª Ø¨Ø§ Ù…ÙˆÙÙ‚ÛŒØª Ù‡Ù…Ú¯Ø§Ù…â€ŒØ³Ø§Ø²ÛŒ Ø´Ø¯', 'success');
                    window.fetchFeedDownloads(false);
                }} else {{
                    showToast('âŒ Ø®Ø·Ø§ Ø¯Ø± Ù‡Ù…Ú¯Ø§Ù…â€ŒØ³Ø§Ø²ÛŒ: ' + (data.error || ''), 'error');
                }}
            }} catch (err) {{
                showToast('âŒ Ø®Ø·Ø§ÛŒ Ø§Ø±ØªØ¨Ø§Ø· Ø¨Ø§ Ø³Ø±ÙˆØ±', 'error');
            }} finally {{
                btn.innerHTML = originalHtml;
                btn.disabled = false;
            }}
        }}
        window.syncFeedThumbnails = syncFeedThumbnails;
                window.changeFeedPage = changeFeedPage;
                window.openFeedDispatchModal = openFeedDispatchModal;
                window.closeFeedDispatchModal = closeFeedDispatchModal;
                window.executeFeedDispatch = executeFeedDispatch;
                window.transferFeedDownload = transferFeedDownload;
                window.addFeedToCourseEpisodes = addFeedToCourseEpisodes;
                window.executeFeedMultiDispatch = executeFeedMultiDispatch;
                window.setDispatchFormat = setDispatchFormat;
            }} catch (err) {{
                console.error('[UNFINIT Studio Module Error]:', err);
            }}
        }})();

        // =========================================================================
        // MODULE 3: STORE, ORDERS & COUPONS (Sandboxed IIFE)
        // =========================================================================
        (function initStoreOrdersModule() {{
            try {{
        function toggleAddCourseForm() {{
            const card = document.getElementById('addCourseCard');
            card.classList.toggle('hidden');
            if (!card.classList.contains('hidden')) {{
                updateCharCounter('newCName', 'counter_newCName', 32);
                updateCharCounter('newCDesc', 'counter_newCDesc', 255);
            }}
        }}

        function togglePackageInput(prefix) {{
            const selectEl = document.getElementById(prefix + 'DeliveryType');
            const pkgBox = document.getElementById(prefix + 'PackageBox');
            if (selectEl && pkgBox) {{
                if (selectEl.value === 'files_package') {{
                    pkgBox.classList.remove('hidden');
                }} else {{
                    pkgBox.classList.add('hidden');
                }}
            }}
        }}

        function formatPriceInput(el) {{
            if (!el) return;
            const digits = el.value.replace(/[^0-9]/g, '');
            if (digits === '') {{
                el.value = '';
                return;
            }}
            el.value = Number(digits).toLocaleString('en-US');
        }}

        async function handleCreateCourse(e) {{
            e.preventDefault();
            const btn = document.getElementById('btnSubmitCourse');
            btn.disabled = true;
            btn.innerText = 'Ø¯Ø± Ø­Ø§Ù„ Ø«Ø¨Øª...';
            const name = document.getElementById('newCName').value;
            const rawPrice = String(document.getElementById('newCPrice').value || '').replace(/[,ØŒ\\s]/g, '');
            const price = parseInt(rawPrice) || 0;
            const description = document.getElementById('newCDesc').value;
            const download_link = document.getElementById('newCDownload').value;
            const photo_url = document.getElementById('newCPhoto').value;
            const allow_card = document.getElementById('newCAllowCard').checked;
            const allow_bale = document.getElementById('newCAllowBale').checked;
            const requires_referral = document.getElementById('newCRequiresReferral') ? (document.getElementById('newCRequiresReferral').checked ? 1 : 0) : 0;
            const delivery_type = document.getElementById('newCDeliveryType') ? document.getElementById('newCDeliveryType').value : 'channel';
            let files_package = [];
            if (delivery_type === 'files_package' && document.getElementById('newCFilesPackage')) {{
                const rawPkg = document.getElementById('newCFilesPackage').value.trim();
                try {{
                    files_package = rawPkg.startsWith('[') ? JSON.parse(rawPkg) : rawPkg.split('\\n').filter(Boolean).map(l => {{
                        const parts = l.split('|').map(s => s.trim());
                        return {{ title: parts[0] || 'ÙØ§ÛŒÙ„ Ø¢Ù…ÙˆØ²Ø´ÛŒ', file_id: parts[1] || parts[0] }};
                    }});
                }} catch(e) {{
                    files_package = [{{ title: name, file_name: rawPkg }}];
                }}
            }}

            try {{
                const res = await fetch('/api/courses/add', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json; charset=utf-8' }},
                    body: JSON.stringify({{ name, price, description, download_link, photo_url, allow_card, allow_bale, requires_referral, delivery_type, files_package }})
                }});
                const data = await res.json();
                if (data.ok) {{
                    showToast('âœ… Ø¯ÙˆØ±Ù‡ Ø¬Ø¯ÛŒØ¯ Ø¨Ø§ Ù…ÙˆÙÙ‚ÛŒØª Ø«Ø¨Øª Ø´Ø¯!');
                    location.reload();
                }} else {{
                    showToast('âŒ Ø®Ø·Ø§: ' + (data.error || 'Ø«Ø¨Øª Ø¯ÙˆØ±Ù‡ Ù†Ø§Ù…ÙˆÙÙ‚ Ø¨ÙˆØ¯'));
                }}
            }} catch (err) {{
                showToast('âŒ Ø®Ø·Ø§ÛŒ Ø§Ø±ØªØ¨Ø§Ø· Ø¨Ø§ Ø³Ø±ÙˆØ±: ' + err.message);
            }} finally {{
                btn.disabled = false;
                btn.innerText = 'Ø«Ø¨Øª Ø¯ÙˆØ±Ù‡ Ø¯Ø± Ø¯ÛŒØªØ§Ø¨ÛŒØ³';
            }}
        }}

        window._currentPackageLessons = [];

        /**
         * Ø±Ù†Ø¯Ø± Ù…Ø¬Ø¯Ø¯ Ù„ÛŒØ³Øª ØªØ¹Ø§Ù…Ù„ÛŒ Ø¬Ù„Ø³Ø§Øª Ù¾Ú©ÛŒØ¬ Ø¯ÙˆØ±Ù‡ Ø¯Ø± DOM
         * Ø§ÛŒÙ† ØªØ§Ø¨Ø¹ Ø§Ù…Ú©Ø§Ù† ØªØºÛŒÛŒØ± ØªØ±ØªÛŒØ¨ØŒ ÙˆÛŒØ±Ø§ÛŒØ´ Ø¹Ù†Ø§ÙˆÛŒÙ†ØŒ Ùˆ Ø­Ø°Ù Ø¬Ù„Ø³Ø§Øª Ø±Ø§ Ø¨Ø§ Ù‡Ù…Ø§Ù‡Ù†Ú¯ÛŒ Ú©Ø§Ù…Ù„ ÙØ±Ù… ÙØ±Ø§Ù‡Ù… Ù…ÛŒâ€ŒØ³Ø§Ø²Ø¯.
         */
        function renderPackageLessons() {{
            const listEl = document.getElementById('editPackageLessonsList');
            const hiddenTa = document.getElementById('editFilesPackage');
            if (!listEl) return;
            listEl.innerHTML = '';
            const lessons = window._currentPackageLessons || [];
            if (hiddenTa) {{
                hiddenTa.value = lessons.length ? JSON.stringify(lessons, null, 2) : '';
            }}
            if (lessons.length === 0) {{
                listEl.innerHTML = '<div class="text-center py-3 text-xs text-slate-400 font-mono">Ù‡ÛŒÚ† Ø¬Ù„Ø³Ù‡â€ŒØ§ÛŒ Ø¨Ø±Ø§ÛŒ Ø§ÛŒÙ† Ù¾Ú©ÛŒØ¬ Ø«Ø¨Øª Ù†Ø´Ø¯Ù‡ Ø§Ø³Øª. Ø§Ø² ÙØ±Ù… Ø²ÛŒØ± Ø¬Ù„Ø³Ù‡ Ø¬Ø¯ÛŒØ¯ Ø§Ø¶Ø§ÙÙ‡ Ú©Ù†ÛŒØ¯.</div>';
                return;
            }}
            lessons.forEach(function(item, idx) {{
                const row = document.createElement('div');
                row.className = 'flex items-center gap-2 p-2 rounded-xl border text-xs';
                row.style.background = 'var(--input-bg)';
                row.style.borderColor = 'var(--card-border)';
                
                const badge = document.createElement('span');
                badge.className = 'w-6 h-6 rounded-lg bg-cyan-950/80 text-cyan-400 border border-cyan-800 flex items-center justify-center font-mono text-[11px] shrink-0 font-bold';
                badge.textContent = '#' + (idx + 1);
                row.appendChild(badge);

                const titleInp = document.createElement('input');
                titleInp.type = 'text';
                titleInp.value = item.title || '';
                titleInp.placeholder = 'Ø¹Ù†ÙˆØ§Ù† Ø¬Ù„Ø³Ù‡';
                titleInp.className = 'flex-1 px-2 py-1 rounded-lg border text-xs focus:outline-none focus:border-cyan-500';
                titleInp.style.background = 'var(--card-bg)';
                titleInp.style.borderColor = 'var(--card-border)';
                titleInp.style.color = 'var(--text-main)';
                titleInp.oninput = function() {{ updatePackageLesson(idx, 'title', this.value); }};
                row.appendChild(titleInp);

                const fileInp = document.createElement('input');
                fileInp.type = 'text';
                fileInp.value = item.file_name || item.file_id || item.link || '';
                fileInp.placeholder = 'ÙØ§ÛŒÙ„ / Ø´Ù†Ø§Ø³Ù‡';
                fileInp.className = 'w-1/3 px-2 py-1 rounded-lg border text-xs font-mono focus:outline-none focus:border-cyan-500';
                fileInp.style.background = 'var(--card-bg)';
                fileInp.style.borderColor = 'var(--card-border)';
                fileInp.style.color = 'var(--text-main)';
                fileInp.dir = 'ltr';
                fileInp.oninput = function() {{ updatePackageLesson(idx, 'file_name', this.value); }};
                row.appendChild(fileInp);

                const actionsDiv = document.createElement('div');
                actionsDiv.className = 'flex items-center gap-1 shrink-0';

                const upBtn = document.createElement('button');
                upBtn.type = 'button';
                upBtn.title = 'Ø§Ù†ØªÙ‚Ø§Ù„ Ø¨Ù‡ Ø¨Ø§Ù„Ø§';
                upBtn.disabled = (idx === 0);
                upBtn.className = 'p-1 rounded-lg border text-slate-300 hover:text-cyan-400 disabled:opacity-30 disabled:hover:text-slate-300 transition';
                upBtn.style.background = 'var(--card-bg)';
                upBtn.style.borderColor = 'var(--card-border)';
                upBtn.onclick = function() {{ movePackageLesson(idx, -1); }};
                upBtn.innerHTML = '<svg class="w-3.5 h-3.5 stroke-[2]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M4.5 15.75l7.5-7.5 7.5 7.5" /></svg>';
                actionsDiv.appendChild(upBtn);

                const downBtn = document.createElement('button');
                downBtn.type = 'button';
                downBtn.title = 'Ø§Ù†ØªÙ‚Ø§Ù„ Ø¨Ù‡ Ù¾Ø§ÛŒÛŒÙ†';
                downBtn.disabled = (idx === lessons.length - 1);
                downBtn.className = 'p-1 rounded-lg border text-slate-300 hover:text-cyan-400 disabled:opacity-30 disabled:hover:text-slate-300 transition';
                downBtn.style.background = 'var(--card-bg)';
                downBtn.style.borderColor = 'var(--card-border)';
                downBtn.onclick = function() {{ movePackageLesson(idx, 1); }};
                downBtn.innerHTML = '<svg class="w-3.5 h-3.5 stroke-[2]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" /></svg>';
                actionsDiv.appendChild(downBtn);

                const delBtn = document.createElement('button');
                delBtn.type = 'button';
                delBtn.title = 'Ø­Ø°Ù Ø¬Ù„Ø³Ù‡';
                delBtn.className = 'p-1 rounded-lg border text-rose-400 hover:bg-rose-950/50 hover:text-rose-300 transition';
                delBtn.style.background = 'var(--card-bg)';
                delBtn.style.borderColor = 'var(--card-border)';
                delBtn.onclick = function() {{ removePackageLesson(idx); }};
                delBtn.innerHTML = '<svg class="w-3.5 h-3.5 stroke-[2]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>';
                actionsDiv.appendChild(delBtn);

                row.appendChild(actionsDiv);
                listEl.appendChild(row);
            }});
        }}
        window.renderPackageLessons = renderPackageLessons;

        /**
         * Ø§ÙØ²ÙˆØ¯Ù† Ø±Ø¯ÛŒÙ Ø¬Ù„Ø³Ù‡ Ø¬Ø¯ÛŒØ¯ Ø¨Ù‡ Ù¾Ú©ÛŒØ¬ Ø¯ÙˆØ±Ù‡
         */
        function addPackageLessonRow() {{
            const titleInp = document.getElementById('newLessonTitle');
            const fileInp = document.getElementById('newLessonFile');
            const title = titleInp ? titleInp.value.trim() : '';
            const file_name = fileInp ? fileInp.value.trim() : '';
            if (!file_name) {{
                showToast('Ù„Ø·ÙØ§Ù‹ Ø´Ù†Ø§Ø³Ù‡ ÙØ§ÛŒÙ„ ÛŒØ§ Ù†Ø§Ù… ÙØ§ÛŒÙ„ Ø¬Ù„Ø³Ù‡ Ø±Ø§ ÙˆØ§Ø±Ø¯ Ù†Ù…Ø§ÛŒÛŒØ¯.');
                return;
            }}
            const lessons = window._currentPackageLessons || [];
            lessons.push({{
                title: title || ('Ø¬Ù„Ø³Ù‡ ' + (lessons.length + 1)),
                file_name: file_name,
                duration: 0
            }});
            window._currentPackageLessons = lessons;
            if (titleInp) titleInp.value = '';
            if (fileInp) fileInp.value = '';
            renderPackageLessons();
        }}
        window.addPackageLessonRow = addPackageLessonRow;

        /**
         * Ø¨Ù‡â€ŒØ±ÙˆØ²Ø±Ø³Ø§Ù†ÛŒ ÙÛŒÙ„Ø¯Ù‡Ø§ÛŒ ÛŒÚ© Ø¬Ù„Ø³Ù‡ Ù¾Ú©ÛŒØ¬
         */
        function updatePackageLesson(idx, field, val) {{
            if (window._currentPackageLessons && window._currentPackageLessons[idx]) {{
                window._currentPackageLessons[idx][field] = val;
                const hiddenTa = document.getElementById('editFilesPackage');
                if (hiddenTa) hiddenTa.value = JSON.stringify(window._currentPackageLessons, null, 2);
            }}
        }}
        window.updatePackageLesson = updatePackageLesson;

        /**
         * Ø¬Ø§Ø¨Ø¬Ø§ÛŒÛŒ ØªØ±ØªÛŒØ¨ Ø¬Ù„Ø³Ù‡ Ø¨Ø§ Ø¯Ú©Ù…Ù‡â€ŒÙ‡Ø§ÛŒ Ø¨Ø§Ù„Ø§ / Ù¾Ø§ÛŒÛŒÙ†
         */
        function movePackageLesson(idx, dir) {{
            const lessons = window._currentPackageLessons || [];
            const target = idx + dir;
            if (target < 0 || target >= lessons.length) return;
            const temp = lessons[idx];
            lessons[idx] = lessons[target];
            lessons[target] = temp;
            window._currentPackageLessons = lessons;
            renderPackageLessons();
        }}
        window.movePackageLesson = movePackageLesson;

        /**
         * Ø­Ø°Ù ÛŒÚ© Ø¬Ù„Ø³Ù‡ Ø§Ø² Ù¾Ú©ÛŒØ¬ Ø¯ÙˆØ±Ù‡
         */
        function removePackageLesson(idx) {{
            const lessons = window._currentPackageLessons || [];
            if (idx >= 0 && idx < lessons.length) {{
                lessons.splice(idx, 1);
                window._currentPackageLessons = lessons;
                renderPackageLessons();
            }}
        }}
        window.removePackageLesson = removePackageLesson;

        /**
         * Ø¨Ø§Ø² Ú©Ø±Ø¯Ù† Ù…ÙˆØ¯Ø§Ù„ ÙˆÛŒØ±Ø§ÛŒØ´ Ø¯ÙˆØ±Ù‡ Ùˆ Ù…Ù‚Ø¯Ø§Ø±Ø¯Ù‡ÛŒ ÙØ±Ù…â€ŒÙ‡Ø§
         */
        function openEditModal(pid, name, price, desc, dl, photo, allow_card, allow_bale, requires_referral, delivery_type, files_package) {{
            document.getElementById('editProductId').value = pid;
            document.getElementById('modalProdIdBadge').innerText = pid;
            document.getElementById('editName').value = name;
            const rawP = String(price || '0').replace(/[,ØŒ\\s]/g, '');
            document.getElementById('editPrice').value = Number(rawP) ? Number(rawP).toLocaleString('en-US') : '0';
            document.getElementById('editDesc').value = desc;
            document.getElementById('editDl').value = dl;
            document.getElementById('editPhoto').value = photo;
            document.getElementById('editAllowCard').checked = !!allow_card;
            document.getElementById('editAllowBale').checked = !!allow_bale;
            if (document.getElementById('editRequiresReferral')) {{
                document.getElementById('editRequiresReferral').checked = !!requires_referral;
            }}
            if (document.getElementById('editDeliveryType')) {{
                document.getElementById('editDeliveryType').value = delivery_type || 'channel';
                togglePackageInput('edit');
            }}
            
            let pkgList = [];
            if (Array.isArray(files_package)) {{
                pkgList = JSON.parse(JSON.stringify(files_package));
            }} else if (typeof files_package === 'string' && files_package.trim()) {{
                try {{
                    pkgList = JSON.parse(files_package);
                }} catch(e) {{
                    pkgList = files_package.split('\\n').filter(Boolean).map(function(l) {{
                        const parts = l.split('|').map(function(s) {{ return s.trim(); }});
                        return {{ title: parts[0] || 'ÙØ§ÛŒÙ„ Ø¢Ù…ÙˆØ²Ø´ÛŒ', file_name: parts[1] || parts[0] }};
                    }});
                }}
            }}
            window._currentPackageLessons = Array.isArray(pkgList) ? pkgList : [];
            renderPackageLessons();

            if (window._currentPackageLessons && window._currentPackageLessons.length > 0) {{
                const pkgBox = document.getElementById('editPackageBox');
                if (pkgBox) pkgBox.classList.remove('hidden');
            }}

            const statusEl = document.getElementById('bannerUploadStatus_editPhoto');
            if (statusEl) statusEl.innerText = '';
            updateCharCounter('editName', 'counter_editName', 32);
            updateCharCounter('editDesc', 'counter_editDesc', 255);
            document.getElementById('editModal').classList.remove('hidden');
        }}

        function closeEditModal() {{
            const m = document.getElementById('editModal');
            if (m) m.classList.add('hidden');
        }}
        window.closeEditModal = closeEditModal;
        window.closeEditCourseModal = closeEditModal;

        function openEditModalById(pid) {{
            let course = null;
            if (window.coursesData) {{
                course = window.coursesData[pid] || Object.values(window.coursesData).find(c => c && (c.product_id == pid || String(c.product_id) === String(pid)));
            }}
            if (!course && window.COURSES_CACHE) {{
                course = window.COURSES_CACHE[pid] || Object.values(window.COURSES_CACHE).find(c => c && (c.product_id == pid || String(c.product_id) === String(pid)));
            }}
            if (!course) {{
                showToast('Ø§Ø·Ù„Ø§Ø¹Ø§Øª Ø¯ÙˆØ±Ù‡ ÛŒØ§ÙØª Ù†Ø´Ø¯ (' + pid + ').');
                return;
            }}
            openEditModal(
                course.product_id,
                course.name,
                course.price,
                course.description,
                course.download_link,
                course.photo_url,
                course.allow_card,
                course.allow_bale,
                course.requires_referral,
                course.delivery_type,
                course.files_package
            );
        }}
        window.openEditCourseModal = openEditModalById;
        window.openEditModalById = openEditModalById;

        /**
         * Ø°Ø®ÛŒØ±Ù‡ ØªØºÛŒÛŒØ±Ø§Øª Ø¯ÙˆØ±Ù‡ Ø¨Ù‡ ØµÙˆØ±Øª Ø§ÛŒØ¬Ú©Ø³ Ø¨Ø¯ÙˆÙ† Ø±ÙØ±Ø´ ØµÙØ­Ù‡ (Zero Page-Reload)
         */
        async function handleSaveEdit(e) {{
            e.preventDefault();
            const product_id = document.getElementById('editProductId').value;
            const name = document.getElementById('editName').value;
            const rawPrice = String(document.getElementById('editPrice').value || '').replace(/[,ØŒ\\s]/g, '');
            const price = parseInt(rawPrice) || 0;
            const description = document.getElementById('editDesc').value;
            const download_link = document.getElementById('editDl').value;
            const photo_url = document.getElementById('editPhoto').value;
            const allow_card = document.getElementById('editAllowCard').checked ? 1 : 0;
            const allow_bale = document.getElementById('editAllowBale').checked ? 1 : 0;
            const requires_referral = document.getElementById('editRequiresReferral') ? (document.getElementById('editRequiresReferral').checked ? 1 : 0) : 0;
            const delivery_type = document.getElementById('editDeliveryType') ? document.getElementById('editDeliveryType').value : 'channel';
            let files_package = [];
            if (delivery_type === 'files_package') {{
                if (window._currentPackageLessons && window._currentPackageLessons.length > 0) {{
                    files_package = window._currentPackageLessons;
                }} else if (document.getElementById('editFilesPackage')) {{
                    const rawPkg = document.getElementById('editFilesPackage').value.trim();
                    try {{
                        files_package = rawPkg.startsWith('[') ? JSON.parse(rawPkg) : rawPkg.split('\\n').filter(Boolean).map(function(l) {{
                            const parts = l.split('|').map(function(s) {{ return s.trim(); }});
                            return {{ title: parts[0] || 'ÙØ§ÛŒÙ„ Ø¢Ù…ÙˆØ²Ø´ÛŒ', file_id: parts[1] || parts[0] }};
                        }});
                    }} catch(e) {{
                        files_package = [{{ title: name, file_name: rawPkg }}];
                    }}
                }}
            }}

            try {{
                const res = await fetch('/api/courses/update', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json; charset=utf-8' }},
                    body: JSON.stringify({{ product_id, name, price, description, download_link, photo_url, allow_card, allow_bale, requires_referral, delivery_type, files_package }})
                }});
                const data = await res.json();
                if (data.ok) {{
                    // Ø¨Ù‡â€ŒØ±ÙˆØ²Ø±Ø³Ø§Ù†ÛŒ Ú©Ø´ Ø¯Ø±ÙˆÙ† Ø­Ø§ÙØ¸Ù‡ Ú©Ù„Ø§ÛŒÙ†Øª
                    if (window.coursesData && window.coursesData[product_id]) {{
                        Object.assign(window.coursesData[product_id], {{
                            name: name,
                            price: price,
                            description: description,
                            download_link: download_link,
                            photo_url: photo_url,
                            allow_card: allow_card,
                            allow_bale: allow_bale,
                            requires_referral: requires_referral,
                            delivery_type: delivery_type,
                            files_package: files_package
                        }});
                    }}
                    // Ø¨Ù‡â€ŒØ±ÙˆØ²Ø±Ø³Ø§Ù†ÛŒ Ø²Ù†Ø¯Ù‡ Ú©Ø§Ø±Øª Ø¯ÙˆØ±Ù‡ Ø¯Ø± DOM Ø¨Ø¯ÙˆÙ† Ø±ÙØ±Ø´
                    const card = document.getElementById('course_card_' + product_id);
                    if (card) {{
                        const titleEl = card.querySelector('h3');
                        if (titleEl) titleEl.textContent = name;
                        const descEl = card.querySelector('p');
                        if (descEl) descEl.textContent = description || 'ØªÙˆØ¶ÛŒØ­Ø§ØªÛŒ Ø¨Ø±Ø§ÛŒ Ø§ÛŒÙ† Ø¯ÙˆØ±Ù‡ Ø«Ø¨Øª Ù†Ø´Ø¯Ù‡ Ø§Ø³Øª.';
                    }}
                    closeEditModal();
                    showToast('âœ… ØªØºÛŒÛŒØ±Ø§Øª Ø¯ÙˆØ±Ù‡ Ø¨Ø§ Ù…ÙˆÙÙ‚ÛŒØª Ø°Ø®ÛŒØ±Ù‡ Ø´Ø¯!');
                }} else {{
                    showToast('âŒ Ø®Ø·Ø§: ' + (data.error || 'ÙˆÛŒØ±Ø§ÛŒØ´ Ù†Ø§Ù…ÙˆÙÙ‚ Ø¨ÙˆØ¯'));
                }}
            }} catch (err) {{
                showToast('âŒ Ø®Ø·Ø§ÛŒ Ø§Ø±ØªØ¨Ø§Ø·: ' + err.message);
            }}
        }}

        async function saveCourseTermsText() {{
            const btn = document.getElementById('btnSaveTerms');
            const status = document.getElementById('termsSaveStatus');
            const textarea = document.getElementById('courseTermsTextarea');
            if (!textarea) return;
            const terms = textarea.value.trim();
            if (btn) {{
                btn.disabled = true;
                btn.innerText = 'Ø¯Ø± Ø­Ø§Ù„ Ø°Ø®ÛŒØ±Ù‡...';
            }}
            try {{
                const res = await fetch('/api/courses/terms', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json; charset=utf-8' }},
                    body: JSON.stringify({{ terms: terms }})
                }});
                const data = await res.json();
                if (data.ok) {{
                    if (status) {{
                        status.className = 'text-xs font-medium text-emerald-400';
                        status.innerText = 'âœ… ØªØ¹Ù‡Ø¯Ù†Ø§Ù…Ù‡ Ø¨Ø§ Ù…ÙˆÙÙ‚ÛŒØª Ø¯Ø± Ø³ÛŒØ³ØªÙ… Ø°Ø®ÛŒØ±Ù‡ Ø´Ø¯.';
                        setTimeout(() => {{ status.innerText = ''; }}, 4000);
                    }}
                }} else {{
                    if (status) {{
                        status.className = 'text-xs font-medium text-rose-400';
                        status.innerText = 'âŒ Ø®Ø·Ø§: ' + (data.error || 'Ø°Ø®ÛŒØ±Ù‡ Ù†Ø´Ø¯');
                    }}
                }}
            }} catch (err) {{
                if (status) {{
                    status.className = 'text-xs font-medium text-rose-400';
                    status.innerText = 'âŒ Ø®Ø·Ø§ÛŒ Ø´Ø¨Ú©Ù‡: ' + err.message;
                }}
            }} finally {{
                if (btn) {{
                    btn.disabled = false;
                    btn.innerText = 'ðŸ’¾ Ø°Ø®ÛŒØ±Ù‡ Ù…ØªÙ† ØªØ¹Ù‡Ø¯Ù†Ø§Ù…Ù‡';
                }}
            }}
        }}

        async function aiSummarizeDescription(textareaId, counterId) {{
            const textarea = document.getElementById(textareaId);
            if (!textarea) return;
            const text = textarea.value.trim();
            if (!text) {{
                showToast('Ù„Ø·ÙØ§Ù‹ Ø§Ø¨ØªØ¯Ø§ Ù…ØªÙ†ÛŒ Ø¯Ø± Ø¨Ø®Ø´ ØªÙˆØ¶ÛŒØ­Ø§Øª Ø¨Ù†ÙˆÛŒØ³ÛŒØ¯ ØªØ§ Ù‡ÙˆØ´ Ù…ØµÙ†ÙˆØ¹ÛŒ Ø¢Ù† Ø±Ø§ Ø®Ù„Ø§ØµÙ‡ Ú©Ù†Ø¯.');
                return;
            }}
            const prevPlaceholder = textarea.placeholder;
            textarea.disabled = true;
            textarea.placeholder = 'âœ¨ Ø¯Ø± Ø­Ø§Ù„ Ø®Ù„Ø§ØµÙ‡â€ŒØ³Ø§Ø²ÛŒ Ù‡ÙˆØ´Ù…Ù†Ø¯ Ø¨Ø±Ø§ÛŒ Ø¨Ù„Ù‡ (Ø²ÛŒØ± Û²ÛµÛµ Ú©Ø§Ø±Ø§Ú©ØªØ±)...';
            try {{
                const res = await fetch('/api/ai/summarize-course', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json; charset=utf-8' }},
                    body: JSON.stringify({{ text: text }})
                }});
                const data = await res.json();
                if (data.ok && data.summary) {{
                    textarea.value = data.summary;
                    if (counterId) {{
                        updateCharCounter(textareaId, counterId, 255);
                    }}
                }} else {{
                    showToast('âŒ Ø®Ø·Ø§ Ø¯Ø± Ø®Ù„Ø§ØµÙ‡â€ŒØ³Ø§Ø²ÛŒ: ' + (data.error || 'Ù¾Ø§Ø³Ø®ÛŒ Ø¯Ø±ÛŒØ§ÙØª Ù†Ø´Ø¯'));
                }}
            }} catch (err) {{
                showToast('âŒ Ø®Ø·Ø§ÛŒ Ø§Ø±ØªØ¨Ø§Ø· Ø¨Ø§ Ù‡ÙˆØ´ Ù…ØµÙ†ÙˆØ¹ÛŒ: ' + err.message);
            }} finally {{
                textarea.disabled = false;
                textarea.placeholder = prevPlaceholder;
            }}
        }}

        async function toggleCourseActive(pid) {{
            const btn = document.getElementById('toggle_btn_' + pid);
            const badge = document.getElementById('status_badge_' + pid);
            if (btn) {{
                btn.disabled = true;
                btn.innerText = 'Ø¯Ø± Ø­Ø§Ù„ ØªØºÛŒÛŒØ±...';
            }}
            try {{
                const res = await fetch('/api/products/toggle_active', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json; charset=utf-8' }},
                    body: JSON.stringify({{ product_id: pid }})
                }});
                const data = await res.json();
                if (data.ok) {{
                    const isActive = !!data.active;
                    if (badge) {{
                        if (isActive) {{
                            badge.className = 'px-2.5 py-1 rounded-lg text-xs font-bold bg-emerald-950 text-emerald-300 border border-emerald-800 flex items-center gap-1';
                            badge.innerHTML = '<span>ðŸŸ¢</span> ÙØ¹Ø§Ù„';
                        }} else {{
                            badge.className = 'px-2.5 py-1 rounded-lg text-xs font-bold bg-rose-950 text-rose-300 border border-rose-800 flex items-center gap-1';
                            badge.innerHTML = '<span>ðŸ”´</span> ØºÛŒØ±ÙØ¹Ø§Ù„';
                        }}
                    }}
                    if (btn) {{
                        btn.innerHTML = isActive ? 'ðŸ”´ ØºÛŒØ±ÙØ¹Ø§Ù„â€ŒØ³Ø§Ø²ÛŒ' : 'ðŸŸ¢ ÙØ¹Ø§Ù„â€ŒØ³Ø§Ø²ÛŒ';
                    }}
                    if (window.coursesData && window.coursesData[pid]) {{
                        window.coursesData[pid].is_active = isActive ? 1 : 0;
                    }}
                }} else {{
                    showToast('âŒ Ø®Ø·Ø§ Ø¯Ø± ØªØºÛŒÛŒØ± ÙˆØ¶Ø¹ÛŒØª: ' + (data.error || ''));
                }}
            }} catch (err) {{
                showToast('âŒ Ø®Ø·Ø§: ' + err.message);
            }} finally {{
                if (btn) {{
                    btn.disabled = false;
                }}
            }}
        }}

        async function deleteCourse(pid) {{
            if (!confirm('Ø¢ÛŒØ§ Ø§Ø² Ø­Ø°Ù Ø¯Ø§Ø¦Ù… Ùˆ ÙÛŒØ²ÛŒÚ©ÛŒ Ø§ÛŒÙ† Ø¯ÙˆØ±Ù‡ Ø§Ø² Ø³ÛŒØ³ØªÙ… Ùˆ Ù¾Ø§ÛŒÚ¯Ø§Ù‡ Ø¯Ø§Ø¯Ù‡ Ø§Ø·Ù…ÛŒÙ†Ø§Ù† Ø¯Ø§Ø±ÛŒØ¯ØŸ Ø§ÛŒÙ† Ø¹Ù…Ù„ÛŒØ§Øª ØºÛŒØ±Ù‚Ø§Ø¨Ù„ Ø¨Ø§Ø²Ú¯Ø´Øª Ø§Ø³Øª.')) return;
            try {{
                const res = await fetch('/api/products/delete', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json; charset=utf-8' }},
                    body: JSON.stringify({{ product_id: pid }})
                }});
                const data = await res.json();
                if (data.ok) {{
                    const card = document.getElementById('course_card_' + pid);
                    if (card) {{
                        card.style.transition = 'all 0.4s ease';
                        card.style.opacity = '0';
                        card.style.transform = 'scale(0.95)';
                        setTimeout(() => {{ card.remove(); }}, 400);
                    }}
                }} else {{
                    showToast('âŒ Ø®Ø·Ø§: ' + (data.error || ''));
                }}
            }} catch (err) {{
                showToast('âŒ Ø®Ø·Ø§: ' + err.message);
            }}
        }}

        function toggleSelectAllOrders(master) {{
            const chks = document.querySelectorAll('.order-chk');
            chks.forEach(c => c.checked = master.checked);
            updateSelectedOrdersCount();
        }}

        function updateSelectedOrdersCount() {{
            const chks = document.querySelectorAll('.order-chk:checked');
            const cnt = chks.length;
            const btn = document.getElementById('btnDeleteSelectedOrders');
            const cntSpan = document.getElementById('selectedOrdersCount');
            if (cntSpan) cntSpan.innerText = cnt;
            if (btn) {{
                if (cnt > 0) {{
                    btn.classList.remove('hidden');
                }} else {{
                    btn.classList.add('hidden');
                }}
            }}
            const allChks = document.querySelectorAll('.order-chk');
            const master = document.getElementById('selectAllOrders');
            if (master && allChks.length > 0) {{
                master.checked = (cnt === allChks.length);
            }} else if (master && allChks.length === 0) {{
                master.checked = false;
            }}
        }}

        async function deleteSelectedOrders() {{
            const checked = Array.from(document.querySelectorAll('.order-chk:checked')).map(c => c.value);
            if (!checked || checked.length === 0) {{
                showToast('Ù„Ø·ÙØ§Ù‹ Ø­Ø¯Ø§Ù‚Ù„ ÛŒÚ© Ø³ÙØ§Ø±Ø´ Ø±Ø§ Ø¨Ø±Ø§ÛŒ Ø­Ø°Ù Ø§Ù†ØªØ®Ø§Ø¨ Ú©Ù†ÛŒØ¯.');
                return;
            }}
            if (!confirm('Ø¢ÛŒØ§ Ø§Ø² Ø­Ø°Ù Ø¯Ø³ØªÙ‡â€ŒØ¬Ù…Ø¹ÛŒ ' + checked.length + ' Ø³ÙØ§Ø±Ø´ Ø§Ù†ØªØ®Ø§Ø¨â€ŒØ´Ø¯Ù‡ Ø§Ø·Ù…ÛŒÙ†Ø§Ù† Ø¯Ø§Ø±ÛŒØ¯ØŸ Ø§ÛŒÙ† Ø¹Ù…Ù„ÛŒØ§Øª ØºÛŒØ±Ù‚Ø§Ø¨Ù„ Ø¨Ø§Ø²Ú¯Ø´Øª Ø§Ø³Øª.')) return;
            try {{
                const res = await fetch('/api/store/orders/bulk_delete', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json; charset=utf-8' }},
                    body: JSON.stringify({{ order_ids: checked }})
                }});
                const data = await res.json();
                if (data.ok) {{
                    showToast('âœ… ' + (data.message || (checked.length + ' Ø³ÙØ§Ø±Ø´ Ø¨Ø§ Ù…ÙˆÙÙ‚ÛŒØª Ø­Ø°Ù Ø´Ø¯Ù†Ø¯.')));
                    loadStoreOrders();
                }} else {{
                    showToast('âŒ Ø®Ø·Ø§ Ø¯Ø± Ø­Ø°Ù Ø³ÙØ§Ø±Ø´â€ŒÙ‡Ø§: ' + (data.error || ''));
                }}
            }} catch (err) {{
                showToast('âŒ Ø®Ø·Ø§ÛŒ Ø§Ø±ØªØ¨Ø§Ø·: ' + err.message);
            }}
        }}

        async function clearAllOrders() {{
            if (!confirm('âš ï¸ Ù‡Ø´Ø¯Ø§Ø± Ø¬Ø¯ÛŒ!\\nØ¢ÛŒØ§ Ø§Ø² Ù¾Ø§Ú©Ø³Ø§Ø²ÛŒ ØªÙ…Ø§Ù…ÛŒ Ø³ÙØ§Ø±Ø´Ø§Øª Ù…ÙˆØ¬ÙˆØ¯ Ø¯Ø± Ø³ÛŒØ³ØªÙ… Ø§Ø·Ù…ÛŒÙ†Ø§Ù† Ø¯Ø§Ø±ÛŒØ¯ØŸ\\nØ§ÛŒÙ† Ø¹Ù…Ù„ÛŒØ§Øª Ú©Ù„ÛŒÙ‡ Ø³ÙØ§Ø±Ø´Ø§Øª Ø«Ø¨Øªâ€ŒØ´Ø¯Ù‡ (ØªØ³ØªÛŒ Ùˆ ÙˆØ§Ù‚Ø¹ÛŒ) Ø±Ø§ Ø¨Ù‡ Ø·ÙˆØ± Ú©Ø§Ù…Ù„ Ø­Ø°Ù Ù…ÛŒâ€ŒÚ©Ù†Ø¯ Ùˆ ØºÛŒØ±Ù‚Ø§Ø¨Ù„ Ø¨Ø§Ø²Ú¯Ø´Øª Ø§Ø³Øª.')) return;
            try {{
                const res = await fetch('/api/store/orders/clear_all', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json; charset=utf-8' }}
                }});
                const data = await res.json();
                if (data.ok) {{
                    showToast('âœ… ' + (data.message || 'ØªÙ…Ø§Ù…ÛŒ Ø³ÙØ§Ø±Ø´Ø§Øª Ø¨Ø§ Ù…ÙˆÙÙ‚ÛŒØª Ù¾Ø§Ú©Ø³Ø§Ø²ÛŒ Ø´Ø¯Ù†Ø¯.'));
                    loadStoreOrders();
                }} else {{
                    showToast('âŒ Ø®Ø·Ø§ Ø¯Ø± Ù¾Ø§Ú©Ø³Ø§Ø²ÛŒ Ø³ÙØ§Ø±Ø´Ø§Øª: ' + (data.error || ''));
                }}
            }} catch (err) {{
                showToast('âŒ Ø®Ø·Ø§ÛŒ Ø§Ø±ØªØ¨Ø§Ø·: ' + err.message);
            }}
        }}

        async function loadStoreOrders() {{
            const tbody = document.getElementById('storeOrdersTableBody');
            if (!tbody) return;
            const master = document.getElementById('selectAllOrders');
            if (master) master.checked = false;
            updateSelectedOrdersCount();

            try {{
                const res = await fetch('/api/store/orders');
                const data = await res.json();
                if (!data.ok || !data.orders || data.orders.length === 0) {{
                    tbody.innerHTML = '<tr><td colspan="9" class="py-8 text-center text-slate-500">Ù‡ÛŒÚ† Ø³ÙØ§Ø±Ø´ÛŒ Ø¯Ø± Ø³ÛŒØ³ØªÙ… Ø«Ø¨Øª Ù†Ø´Ø¯Ù‡ Ø§Ø³Øª.</td></tr>';
                    return;
                }}
                tbody.innerHTML = data.orders.map(ord => {{
                    let statusBadge = '';
                    if (ord.status === 'completed' || ord.status === 'approved') {{
                        statusBadge = '<span class="px-2.5 py-1 rounded-lg text-xs font-bold bg-emerald-950 text-emerald-300 border border-emerald-800">âœ… ØªØ§ÛŒÛŒØ¯ Ø´Ø¯Ù‡</span>';
                    }} else if (ord.status === 'rejected') {{
                        statusBadge = '<span class="px-2.5 py-1 rounded-lg text-xs font-bold bg-rose-950 text-rose-300 border border-rose-800">âŒ Ø±Ø¯ Ø´Ø¯Ù‡</span>';
                    }} else {{
                        statusBadge = '<span class="px-2.5 py-1 rounded-lg text-xs font-bold bg-amber-950 text-amber-300 border border-amber-800">â³ Ø¯Ø± Ø§Ù†ØªØ¸Ø§Ø± Ø¨Ø±Ø±Ø³ÛŒ</span>';
                    }}

                    let platBadge = '';
                    const p = (ord.platform || '').toLowerCase();
                    if (p === 'telegram' || p === 'tg') {{
                        platBadge = '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-sky-950/70 text-sky-300 border border-sky-800/70 inline-flex items-center gap-1"><span>âœˆï¸</span> ØªÙ„Ú¯Ø±Ø§Ù…</span>';
                    }} else if (p === 'bale') {{
                        platBadge = '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-950/70 text-emerald-300 border border-emerald-800/70 inline-flex items-center gap-1"><span>ðŸŸ¢</span> Ø¨Ù„Ù‡</span>';
                    }} else {{
                        platBadge = '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-purple-950/70 text-purple-300 border border-purple-800/70 inline-flex items-center gap-1"><span>ðŸŒ</span> ÙØ±ÙˆØ´Ú¯Ø§Ù‡ ÙˆØ¨</span>';
                    }}

                    let payMethodBadge = '';
                    const m = (ord.payment_method || '').toLowerCase();
                    if (m === 'bale_online' || m === 'bale') {{
                        payMethodBadge = '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-950/60 text-emerald-300 border border-emerald-800/60 inline-flex items-center gap-1"><span>ðŸ›</span> Ø¯Ø±Ú¯Ø§Ù‡ Ø¨Ù„Ù‡</span>';
                    }} else if (m === 'card_to_card' || m === 'card') {{
                        payMethodBadge = '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-sky-950/60 text-sky-300 border border-sky-800/60 inline-flex items-center gap-1"><span>ðŸ’³</span> Ú©Ø§Ø±Øªâ€ŒØ¨Ù‡â€ŒÚ©Ø§Ø±Øª</span>';
                    }} else if (m === 'zarinpal') {{
                        payMethodBadge = '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-950/60 text-amber-300 border border-amber-800/60 inline-flex items-center gap-1"><span>âš¡ï¸</span> Ø²Ø±ÛŒÙ†â€ŒÙ¾Ø§Ù„</span>';
                    }} else {{
                        payMethodBadge = '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-sky-950/60 text-sky-300 border border-sky-800/60 inline-flex items-center gap-1"><span>ðŸ’³</span> Ú©Ø§Ø±Øªâ€ŒØ¨Ù‡â€ŒÚ©Ø§Ø±Øª</span>';
                    }}

                    let actionBtn = '<div class="flex items-center gap-1.5">';
                    if (ord.status === 'pending_review' || ord.status === 'pending') {{
                        actionBtn += '<button onclick="approveStoreOrder(&quot;' + ord.order_id + '&quot;)" class="px-2.5 py-1 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold transition shadow-sm">âœ… ØªØ§ÛŒÛŒØ¯</button>' +
                                    '<button onclick="rejectStoreOrder(&quot;' + ord.order_id + '&quot;)" class="theme-card-btn px-2.5 py-1 rounded-lg text-xs font-bold transition shadow-sm">âŒ Ø±Ø¯</button>';
                    }}
                    actionBtn += '<button onclick="deleteStoreOrder(&quot;' + ord.order_id + '&quot;)" class="theme-card-btn px-2 py-1 rounded-lg text-xs font-bold transition shadow-sm" title="Ø­Ø°Ù Ø³ÙØ§Ø±Ø´">ðŸ—‘ Ø­Ø°Ù</button></div>';

                    const orderDate = ord.created_at || '-';
                    const amountStr = (ord.amount || 0).toLocaleString() + ' ØªÙˆÙ…Ø§Ù†';

                    return '<tr class="border-b border-slate-800 hover:bg-slate-800/30 transition">' +
                        '<td class="py-3 px-3 text-center"><input type="checkbox" class="order-chk rounded bg-slate-800 border-slate-600 text-cyan-500 focus:ring-0 cursor-pointer" value="' + escapeHtml(ord.order_id) + '" onchange="updateSelectedOrdersCount()"></td>' +
                        '<td class="py-3 px-3 font-mono text-cyan-400 font-bold">' + escapeHtml(ord.order_id) + '</td>' +
                        '<td class="py-3 px-3">' +
                            '<div class="font-bold text-slate-200">' + escapeHtml(ord.customer_name || 'Ú©Ø§Ø±Ø¨Ø±') + '</div>' +
                            '<div class="text-[11px] font-mono text-slate-400">' + escapeHtml(ord.phone || ord.user_id || '-') + '</div>' +
                        '</td>' +
                        '<td class="py-3 px-3">' +
                            '<div class="text-slate-200 font-medium">' + escapeHtml(ord.product_name || ord.product_id) + '</div>' +
                            '<div class="text-[11px] font-mono text-emerald-400 font-bold">' + amountStr + '</div>' +
                        '</td>' +
                        '<td class="py-3 px-3">' + platBadge + '</td>' +
                        '<td class="py-3 px-3">' + payMethodBadge + '</td>' +
                        '<td class="py-3 px-3">' +
                            '<div class="max-w-[200px] truncate text-slate-300 text-[11px]" title="' + escapeHtml(ord.receipt_text || '') + '">' + escapeHtml(ord.receipt_text || '-') + '</div>' +
                            '<div class="text-[10px] text-slate-400 font-mono">' + escapeHtml(orderDate) + '</div>' +
                        '</td>' +
                        '<td class="py-3 px-3">' + statusBadge + '</td>' +
                        '<td class="py-3 px-3 text-left">' + actionBtn + '</td>' +
                    '</tr>';
                }}).join('');
            }} catch (err) {{
                tbody.innerHTML = '<tr><td colspan="9" class="py-6 text-center text-rose-400">Ø®Ø·Ø§ Ø¯Ø± Ø¯Ø±ÛŒØ§ÙØª Ø³ÙØ§Ø±Ø´â€ŒÙ‡Ø§: ' + err.message + '</td></tr>';
            }}
        }}

        async function approveStoreOrder(orderId) {{
            if (!confirm('Ø¢ÛŒØ§ Ø§Ø² ØªØ§ÛŒÛŒØ¯ Ø³ÙØ§Ø±Ø´ ' + orderId + ' Ùˆ ÙØ¹Ø§Ù„â€ŒØ³Ø§Ø²ÛŒ Ù„ÛŒÙ†Ú© Ø¯Ø§Ù†Ù„ÙˆØ¯ Ø¨Ø±Ø§ÛŒ Ù…Ø´ØªØ±ÛŒ Ø§Ø·Ù…ÛŒÙ†Ø§Ù† Ø¯Ø§Ø±ÛŒØ¯ØŸ')) return;
            try {{
                const res = await fetch('/api/store/orders/approve', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json; charset=utf-8' }},
                    body: JSON.stringify({{ order_id: orderId }})
                }});
                const data = await res.json();
                if (data.ok) {{
                    showToast('âœ… Ø³ÙØ§Ø±Ø´ ' + orderId + ' Ø¨Ø§ Ù…ÙˆÙÙ‚ÛŒØª ØªØ§ÛŒÛŒØ¯ Ø´Ø¯!');
                    loadStoreOrders();
                }} else {{
                    showToast('âŒ Ø®Ø·Ø§ Ø¯Ø± ØªØ§ÛŒÛŒØ¯ Ø³ÙØ§Ø±Ø´: ' + (data.error || ''));
                }}
            }} catch (err) {{
                showToast('âŒ Ø®Ø·Ø§ÛŒ Ø§Ø±ØªØ¨Ø§Ø·: ' + err.message);
            }}
        }}

        async function rejectStoreOrder(orderId) {{
            if (!confirm('Ø¢ÛŒØ§ Ø§Ø² Ø±Ø¯ Ø³ÙØ§Ø±Ø´ ' + orderId + ' Ø§Ø·Ù…ÛŒÙ†Ø§Ù† Ø¯Ø§Ø±ÛŒØ¯ØŸ ÙˆØ¶Ø¹ÛŒØª Ø³ÙØ§Ø±Ø´ Ø¨Ù‡ Ø±Ø¯ Ø´Ø¯Ù‡ ØªØºÛŒÛŒØ± Ø®ÙˆØ§Ù‡Ø¯ Ú©Ø±Ø¯.')) return;
            try {{
                const res = await fetch('/api/store/orders/reject', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json; charset=utf-8' }},
                    body: JSON.stringify({{ order_id: orderId }})
                }});
                const data = await res.json();
                if (data.ok) {{
                    showToast('âŒ Ø³ÙØ§Ø±Ø´ ' + orderId + ' Ø¨Ø§ Ù…ÙˆÙÙ‚ÛŒØª Ø±Ø¯ Ø´Ø¯.');
                    loadStoreOrders();
                }} else {{
                    showToast('âŒ Ø®Ø·Ø§ Ø¯Ø± Ø±Ø¯ Ø³ÙØ§Ø±Ø´: ' + (data.error || ''));
                }}
            }} catch (err) {{
                showToast('âŒ Ø®Ø·Ø§ÛŒ Ø§Ø±ØªØ¨Ø§Ø·: ' + err.message);
            }}
        }}

        async function deleteStoreOrder(orderId) {{
            if (!confirm('Ø¢ÛŒØ§ Ø§Ø² Ø­Ø°Ù Ú©Ø§Ù…Ù„ Ø³ÙØ§Ø±Ø´ ' + orderId + ' Ø§Ø² Ø³ÛŒØ³ØªÙ… Ø§Ø·Ù…ÛŒÙ†Ø§Ù† Ø¯Ø§Ø±ÛŒØ¯ØŸ Ø§ÛŒÙ† Ø¹Ù…Ù„ÛŒØ§Øª ØºÛŒØ±Ù‚Ø§Ø¨Ù„ Ø¨Ø§Ø²Ú¯Ø´Øª Ø§Ø³Øª.')) return;
            try {{
                const res = await fetch('/api/store/orders/delete', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json; charset=utf-8' }},
                    body: JSON.stringify({{ order_id: orderId }})
                }});
                const data = await res.json();
                if (data.ok) {{
                    loadStoreOrders();
                }} else {{
                    showToast('âŒ Ø®Ø·Ø§ Ø¯Ø± Ø­Ø°Ù Ø³ÙØ§Ø±Ø´: ' + (data.error || ''));
                }}
            }} catch (err) {{
                showToast('âŒ Ø®Ø·Ø§ÛŒ Ø§Ø±ØªØ¨Ø§Ø·: ' + err.message);
            }}
        }}

        async function cleanupRejectedOrders() {{
            if (!confirm('Ø¢ÛŒØ§ Ø§Ø² Ø­Ø°Ù Ú©Ù„ÛŒÙ‡ Ø³ÙØ§Ø±Ø´â€ŒÙ‡Ø§ÛŒ Ø±Ø¯ Ø´Ø¯Ù‡ Ø§Ø² Ù¾Ø§ÛŒÚ¯Ø§Ù‡ Ø¯Ø§Ø¯Ù‡ Ø§Ø·Ù…ÛŒÙ†Ø§Ù† Ø¯Ø§Ø±ÛŒØ¯ØŸ Ø§ÛŒÙ† Ø¹Ù…Ù„ÛŒØ§Øª ØºÛŒØ±Ù‚Ø§Ø¨Ù„ Ø¨Ø§Ø²Ú¯Ø´Øª Ø§Ø³Øª.')) return;
            try {{
                const res = await fetch('/api/store/orders/cleanup_rejected', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json; charset=utf-8' }}
                }});
                const data = await res.json();
                if (data.ok) {{
                    showToast('âœ… ' + (data.message || 'Ø³ÙØ§Ø±Ø´â€ŒÙ‡Ø§ÛŒ Ø±Ø¯ Ø´Ø¯Ù‡ Ø¨Ø§ Ù…ÙˆÙÙ‚ÛŒØª Ù¾Ø§Ú©Ø³Ø§Ø²ÛŒ Ø´Ø¯Ù†Ø¯.'));
                    loadStoreOrders();
                }} else {{
                    showToast('âŒ Ø®Ø·Ø§ Ø¯Ø± Ù¾Ø§Ú©Ø³Ø§Ø²ÛŒ Ø³ÙØ§Ø±Ø´â€ŒÙ‡Ø§: ' + (data.error || ''));
                }}
            }} catch (err) {{
                showToast('âŒ Ø®Ø·Ø§ÛŒ Ø§Ø±ØªØ¨Ø§Ø·: ' + err.message);
            }}
        }}

        async function loadStoreAnalytics() {{
            try {{
                const res = await fetch('/api/analytics');
                const data = await res.json();
                if (data.ok && data.analytics) {{
                    const a = data.analytics;
                    const totEl = document.getElementById('metricTotalSales');
                    if (totEl) totEl.innerText = (a.total_sales_amount || 0).toLocaleString() + ' ØªÙˆÙ…Ø§Ù†';
                    const ordEl = document.getElementById('metricTotalOrders');
                    if (ordEl) ordEl.innerText = (a.total_sales_count || 0) + ' Ø³ÙØ§Ø±Ø´ Ù…ÙˆÙÙ‚';

                    const todayEl = document.getElementById('metricTodaySales');
                    if (todayEl) todayEl.innerText = (a.today_sales_amount || 0).toLocaleString() + ' ØªÙˆÙ…Ø§Ù†';
                    const todayOrd = document.getElementById('metricTodayOrders');
                    if (todayOrd) todayOrd.innerText = (a.today_sales_count || 0) + ' Ø³ÙØ§Ø±Ø´';

                    const weekEl = document.getElementById('metricWeekSales');
                    if (weekEl) weekEl.innerText = (a.week_sales_amount || 0).toLocaleString() + ' ØªÙˆÙ…Ø§Ù†';
                    const weekOrd = document.getElementById('metricWeekOrders');
                    if (weekOrd) weekOrd.innerText = (a.week_sales_count || 0) + ' Ø³ÙØ§Ø±Ø´';

                    const monthEl = document.getElementById('metricMonthSales');
                    if (monthEl) monthEl.innerText = (a.month_sales_amount || 0).toLocaleString() + ' ØªÙˆÙ…Ø§Ù†';
                    const monthOrd = document.getElementById('metricMonthOrders');
                    if (monthOrd) monthOrd.innerText = (a.month_sales_count || 0) + ' Ø³ÙØ§Ø±Ø´';

                    const pb = a.platform_breakdown || {{}};
                    const tg = pb.telegram || {{ amount: 0, count: 0 }};
                    const bale = pb.bale || {{ amount: 0, count: 0 }};
                    const rub = pb.rubika || {{ amount: 0, count: 0 }};
                    const web = pb.web || {{ amount: 0, count: 0 }};

                    const tgEl = document.getElementById('platSalesTg');
                    if (tgEl) tgEl.innerText = (tg.amount || 0).toLocaleString() + ' ØªÙˆÙ…Ø§Ù† (' + (tg.count || 0) + ')';
                    const baleEl = document.getElementById('platSalesBale');
                    if (baleEl) baleEl.innerText = (bale.amount || 0).toLocaleString() + ' ØªÙˆÙ…Ø§Ù† (' + (bale.count || 0) + ')';
                    const rubEl = document.getElementById('platSalesRubika');
                    if (rubEl) rubEl.innerText = (rub.amount || 0).toLocaleString() + ' ØªÙˆÙ…Ø§Ù† (' + (rub.count || 0) + ')';
                    const webEl = document.getElementById('platSalesWeb');
                    if (webEl) webEl.innerText = (web.amount || 0).toLocaleString() + ' ØªÙˆÙ…Ø§Ù† (' + (web.count || 0) + ')';
                }}
            }} catch (err) {{
                console.error('Error loading analytics:', err);
            }}
        }}

        function toggleAddCouponForm() {{
            const el = document.getElementById('addCouponCard');
            if (el) el.classList.toggle('hidden');
        }}

        async function loadStoreCoupons() {{
            const tbody = document.getElementById('couponsTableBody');
            if (!tbody) return;
            try {{
                const res = await fetch('/api/coupons');
                const data = await res.json();
                if (!data.ok || !data.coupons || data.coupons.length === 0) {{
                    tbody.innerHTML = '<tr><td colspan="6" class="py-4 text-center text-slate-500">Ù‡ÛŒÚ† Ú©Ø¯ ØªØ®ÙÛŒÙÛŒ Ø¯Ø± Ø³ÛŒØ³ØªÙ… Ø«Ø¨Øª Ù†Ø´Ø¯Ù‡ Ø§Ø³Øª.</td></tr>';
                    return;
                }}
                tbody.innerHTML = data.coupons.map(c => {{
                    const valNum = parseInt(c.discount_value) || 0;
                    const typeLabel = c.discount_type === 'percent' ? (valNum + '%') : (valNum.toLocaleString() + ' ØªÙˆÙ…Ø§Ù†');
                    const maxLabel = (c.max_uses && c.max_uses > 0) ? ((c.used_count || 0) + ' / ' + c.max_uses) : ((c.used_count || 0) + ' (Ù†Ø§Ù…Ø­Ø¯ÙˆØ¯)');
                    const minLabel = (c.min_order_amount && c.min_order_amount > 0) ? (parseInt(c.min_order_amount).toLocaleString() + ' ØªÙˆÙ…Ø§Ù†') : 'Ø¨Ø¯ÙˆÙ† Ø´Ø±Ø·';
                    const expLabel = c.expire_date ? c.expire_date : 'Ù‡Ù…ÛŒØ´Ú¯ÛŒ';
                    const statusBadge = c.active ? '<span class="px-2 py-0.5 rounded text-[10px] bg-emerald-950 text-emerald-300 border border-emerald-800">ÙØ¹Ø§Ù„</span>' : '<span class="px-2 py-0.5 rounded text-[10px] bg-slate-800 text-slate-400">ØºÛŒØ±ÙØ¹Ø§Ù„</span>';

                    return '<tr class="border-b border-slate-800/80 hover:bg-slate-800/30 transition">' +
                        '<td class="py-2.5 px-3 font-mono text-emerald-400 font-bold">' + escapeHtml(c.code) + '</td>' +
                        '<td class="py-2.5 px-3 text-slate-200 font-bold">' + typeLabel + '</td>' +
                        '<td class="py-2.5 px-3 font-mono text-slate-300">' + maxLabel + '</td>' +
                        '<td class="py-2.5 px-3 text-slate-400 font-mono">' + minLabel + '</td>' +
                        '<td class="py-2.5 px-3 text-slate-400 font-mono text-[11px]">' + escapeHtml(expLabel) + '</td>' +
                        '<td class="py-2.5 px-3">' + statusBadge + '</td>' +
                    '</tr>';
                }}).join('');
            }} catch (err) {{
                tbody.innerHTML = '<tr><td colspan="6" class="py-4 text-center text-rose-400">Ø®Ø·Ø§ Ø¯Ø± Ø¨Ø§Ø±Ú¯Ø°Ø§Ø±ÛŒ Ú©ÙˆÙ¾Ù†â€ŒÙ‡Ø§: ' + err.message + '</td></tr>';
            }}
        }}

        async function handleCreateCoupon(e) {{
            e.preventDefault();
            const btn = document.getElementById('btnSubmitCoupon');
            if (btn) {{ btn.disabled = true; btn.innerText = 'Ø¯Ø± Ø­Ø§Ù„ Ø«Ø¨Øª...'; }}

            const code = document.getElementById('newCouponCode').value.trim();
            const discount_type = document.getElementById('newCouponType').value;
            const discount_value = parseInt(document.getElementById('newCouponValue').value) || 0;
            const max_uses = parseInt(document.getElementById('newCouponMaxUses').value) || 0;
            const min_order_amount = parseInt(document.getElementById('newCouponMinAmount').value) || 0;
            const expire_date = document.getElementById('newCouponExpire').value.trim();

            try {{
                const res = await fetch('/api/coupons/create', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json; charset=utf-8' }},
                    body: JSON.stringify({{ code, discount_type, discount_value, max_uses, min_order_amount, expire_date }})
                }});
                const data = await res.json();
                if (data.ok) {{
                    showToast('âœ… Ú©Ø¯ ØªØ®ÙÛŒÙ ' + code + ' Ø¨Ø§ Ù…ÙˆÙÙ‚ÛŒØª Ø§ÛŒØ¬Ø§Ø¯ Ø´Ø¯!');
                    document.getElementById('addCouponForm').reset();
                    toggleAddCouponForm();
                    loadStoreCoupons();
                }} else {{
                    showToast('âŒ Ø®Ø·Ø§ Ø¯Ø± Ø«Ø¨Øª Ú©Ø¯ ØªØ®ÙÛŒÙ: ' + (data.error || ''));
                }}
            }} catch (err) {{
                showToast('âŒ Ø®Ø·Ø§ÛŒ Ø§Ø±ØªØ¨Ø§Ø·: ' + err.message);
            }} finally {{
                if (btn) {{ btn.disabled = false; btn.innerText = 'Ø«Ø¨Øª Ú©ÙˆÙ¾Ù† ØªØ®ÙÛŒÙ'; }}
            }}
        }}

        function copyText(txt) {{
            navigator.clipboard.writeText(txt);
            showToast('âœ… Ù„ÛŒÙ†Ú© Ø¨Ø§ Ù…ÙˆÙÙ‚ÛŒØª Ú©Ù¾ÛŒ Ø´Ø¯!');
        }}

        async function handleDispatch(e) {{
            e.preventDefault();
            const btn = document.getElementById('submitBtn');
            const resBox = document.getElementById('dispatchResult');
            const url = document.getElementById('directUrl').value;
            const target = document.getElementById('targetPlatform').value;

            btn.disabled = true;
            btn.innerText = 'â³ Ø¯Ø± Ø­Ø§Ù„ Ø¯Ø§Ù†Ù„ÙˆØ¯ Ùˆ Ù¾Ø±Ø¯Ø§Ø²Ø´ Ø§Ø³ØªØ±ÛŒÙ…...';
            resBox.className = 'mt-4 p-3 rounded-xl text-xs font-mono block bg-slate-800 text-slate-300 border border-slate-700';
            resBox.innerText = 'â³ Ø§Ø±Ø³Ø§Ù„ Ø¯Ø±Ø®ÙˆØ§Ø³Øª Ø¨Ù‡ Ø³Ø±ÙˆØ± Ùˆ Ø¯Ø§Ù†Ù„ÙˆØ¯ Ø§Ø³ØªØ±ÛŒÙ…... Ù„Ø·ÙØ§Ù‹ Ø´Ú©ÛŒØ¨Ø§ Ø¨Ø§Ø´ÛŒØ¯.';

            try {{
                const res = await fetch('/api/dispatch_url', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json; charset=utf-8' }},
                    body: JSON.stringify({{ url, target }})
                }});
                const data = await res.json();
                if (data.ok) {{
                    resBox.className = 'mt-4 p-3 rounded-xl text-xs font-mono block bg-emerald-950 text-emerald-300 border border-emerald-700';
                    resBox.innerText = 'âœ… ' + (data.message || 'ÙØ§ÛŒÙ„ Ø¨Ø§ Ù…ÙˆÙÙ‚ÛŒØª Ø¯Ø§Ù†Ù„ÙˆØ¯ Ùˆ Ø§Ø±Ø³Ø§Ù„ Ø´Ø¯!');
                }} else {{
                    resBox.className = 'mt-4 p-3 rounded-xl text-xs font-mono block bg-rose-950 text-rose-300 border border-rose-700';
                    resBox.innerText = 'âŒ Ø®Ø·Ø§: ' + (data.error || 'Ø¹Ù…Ù„ÛŒØ§Øª Ù†Ø§Ù…ÙˆÙÙ‚ Ø¨ÙˆØ¯');
                }}
            }} catch (err) {{
                resBox.className = 'mt-4 p-3 rounded-xl text-xs font-mono block bg-rose-950 text-rose-300 border border-rose-700';
                resBox.innerText = 'âŒ Ø®Ø·Ø§ÛŒ Ø´Ø¨Ú©Ù‡: ' + err.message;
            }} finally {{
                btn.disabled = false;
                btn.innerText = 'âš¡ï¸ Ø¯Ø§Ù†Ù„ÙˆØ¯ Ùˆ Ø§Ø±Ø³Ø§Ù„ Ø®ÙˆØ¯Ú©Ø§Ø±';
            }}
        }}


                window.togglePackageInput = togglePackageInput;
                window.toggleAddCourseForm = toggleAddCourseForm;
                window.handleCreateCourse = handleCreateCourse;
                window.openEditModal = openEditModal;
                window.openEditModalById = openEditModalById;
                window.openEditCourseModal = openEditModalById;
                window.handleSaveEdit = handleSaveEdit;
                window.renderPackageLessons = renderPackageLessons;
                window.addPackageLessonRow = addPackageLessonRow;
                window.updatePackageLesson = updatePackageLesson;
                window.movePackageLesson = movePackageLesson;
                window.removePackageLesson = removePackageLesson;
                window.toggleCourseActive = toggleCourseActive;
                window.deleteCourse = deleteCourse;
                window.toggleSelectAllOrders = toggleSelectAllOrders;
                window.updateSelectedOrdersCount = updateSelectedOrdersCount;
                window.deleteSelectedOrders = deleteSelectedOrders;
                window.clearAllOrders = clearAllOrders;
                window.loadStoreOrders = loadStoreOrders;
                window.approveStoreOrder = approveStoreOrder;
                window.rejectStoreOrder = rejectStoreOrder;
                window.deleteStoreOrder = deleteStoreOrder;
                window.cleanupRejectedOrders = cleanupRejectedOrders;
                window.loadStoreAnalytics = loadStoreAnalytics;
                window.toggleAddCouponForm = toggleAddCouponForm;
                window.loadStoreCoupons = loadStoreCoupons;
                window.handleCreateCoupon = handleCreateCoupon;
                window.copyText = copyText;
                window.handleDispatch = handleDispatch;
                window.saveCourseTermsText = saveCourseTermsText;
                window.aiSummarizeDescription = aiSummarizeDescription;
                window.formatPriceInput = formatPriceInput;
            }} catch (err) {{
                console.error('[UNFINIT Store & Orders Module Error]:', err);
            }}
        }})();

        // =========================================================================
        // MODULE 4: AI AGENT & SYSTEM SETTINGS (Sandboxed IIFE)
        // =========================================================================
        (function initSettingsModule() {{
            try {{
                let hermesHistory = [];
        function clearHermesChat() {{
            hermesHistory = [];
            const box = document.getElementById('hermesChatBox');
            box.innerHTML = `
                <div class="flex gap-2.5 items-center p-3 rounded-xl  border border-slate-800 text-xs text-slate-300">
                    <div class="w-6 h-6 rounded-lg bg-cyan-600/30 text-cyan-300 flex items-center justify-center font-bold text-xs shrink-0">ðŸ¤–</div>
                    <span>ØªØ§Ø±ÛŒØ®Ú†Ù‡ Ú¯ÙØªÚ¯Ùˆ Ù¾Ø§Ú©Ø³Ø§Ø²ÛŒ Ø´Ø¯. Ø¯Ø³ØªÛŒØ§Ø± Ù‡ÙˆØ´ Ù…ØµÙ†ÙˆØ¹ÛŒ Ø¢Ù…Ø§Ø¯Ù‡ Ø§Ø³Øª.</span>
                </div>
            `;
        }}

        function sendPresetHermesPrompt(prompt) {{
            const input = document.getElementById('hermesInput');
            if (input) {{
                input.value = prompt;
                handleSendHermes(null);
            }}
        }}

        async function handleSendHermes(e) {{
            if (e) e.preventDefault();
            const input = document.getElementById('hermesInput');
            const prompt = (input.value || '').trim();
            if (!prompt) return;

            const box = document.getElementById('hermesChatBox');
            const btn = document.getElementById('btnSendHermes');

            const userBubble = document.createElement('div');
            userBubble.className = 'flex gap-3 items-start justify-end max-w-3xl mr-auto';
            userBubble.innerHTML = `
                <div class="bg-gradient-to-r from-blue-600 to-cyan-600 text-white p-3.5 rounded-2xl rounded-tl-none text-xs leading-relaxed shadow-lg shadow-cyan-900/30">
                    ` + escapeHtml(prompt) + `
                </div>
                <div class="w-8 h-8 rounded-xl bg-slate-700 flex items-center justify-center font-bold text-xs text-white shrink-0 mt-1">ðŸ‘¤</div>
            `;
            box.appendChild(userBubble);
            input.value = '';

            const loadingBubble = document.createElement('div');
            const loadingId = 'hermes_load_' + Date.now();
            loadingBubble.id = loadingId;
            loadingBubble.className = 'flex gap-3 items-start max-w-3xl';
            loadingBubble.innerHTML = `
                <div class="w-8 h-8 rounded-xl bg-gradient-to-tr from-cyan-500 to-blue-600 flex items-center justify-center font-bold text-sm text-white shrink-0 mt-1 animate-pulse">ðŸŽ›</div>
                <div class="bg-slate-800/90 border border-slate-700 p-3.5 rounded-2xl rounded-tr-none text-xs text-slate-300 flex items-center gap-2">
                    <span class="animate-spin text-cyan-400">ðŸŒ€</span>
                    <span>Ø¯Ø³ØªÛŒØ§Ø± Ù‡ÙˆØ´Ù…Ù†Ø¯ Ø¯Ø± Ø­Ø§Ù„ Ù¾Ø±Ø¯Ø§Ø²Ø´ Ùˆ ØªÙˆÙ„ÛŒØ¯ Ù¾Ø§Ø³Ø®...</span>
                </div>
            `;
            box.appendChild(loadingBubble);
            box.scrollTop = box.scrollHeight;

            btn.disabled = true;

            try {{
                const selModel = document.getElementById('hermesModelSelect')?.value || '';
                const res = await fetch('/api/hermes/chat', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json; charset=utf-8' }},
                    body: JSON.stringify({{ message: prompt, history: hermesHistory, model: selModel }})
                }});
                const data = await res.json();
                const loadEl = document.getElementById(loadingId);
                if (loadEl) loadEl.remove();

                const replyText = data.reply || (data.error ? 'âŒ Ø®Ø·Ø§: ' + data.error : 'Ù¾Ø§Ø³Ø®ÛŒ Ø¯Ø±ÛŒØ§ÙØª Ù†Ø´Ø¯.');
                const toolsUsed = data.tools_used || [];

                let toolsHtml = '';
                if (toolsUsed.length > 0) {{
                    toolsHtml = '<div class="flex flex-wrap gap-1.5 mb-2">' + toolsUsed.map(t => '<span class="px-2 py-0.5 rounded-md bg-cyan-950 text-cyan-300 text-[10px] border border-cyan-800 font-mono">ðŸ›  ' + escapeHtml(t) + '</span>').join('') + '</div>';
                }}

                const assistantBubble = document.createElement('div');
                assistantBubble.className = 'flex gap-3 items-start max-w-3xl';
                assistantBubble.innerHTML = `
                    <div class="w-8 h-8 rounded-xl bg-gradient-to-tr from-cyan-500 to-blue-600 flex items-center justify-center font-bold text-sm text-white shrink-0 mt-1">ðŸŽ›</div>
                    <div class="bg-slate-800/95 border border-slate-700 p-4 rounded-2xl rounded-tr-none text-xs leading-relaxed text-slate-100 space-y-2 whitespace-pre-wrap shadow-xl">
                        ` + toolsHtml + `
                        <div>` + escapeHtml(replyText) + `</div>
                    </div>
                `;
                box.appendChild(assistantBubble);

                hermesHistory.push({{ role: 'user', content: prompt }});
                hermesHistory.push({{ role: 'assistant', content: replyText }});
                if (hermesHistory.length > 12) hermesHistory = hermesHistory.slice(-12);
            }} catch (err) {{
                const loadEl = document.getElementById(loadingId);
                if (loadEl) loadEl.remove();
                const errBubble = document.createElement('div');
                errBubble.className = 'flex gap-3 items-start max-w-3xl';
                errBubble.innerHTML = `
                    <div class="w-8 h-8 rounded-xl bg-rose-600 flex items-center justify-center font-bold text-sm text-white shrink-0 mt-1">âš ï¸</div>
                    <div class="bg-rose-950/80 border border-rose-800 p-3 rounded-2xl rounded-tr-none text-xs text-rose-300">
                        Ø®Ø·Ø§ Ø¯Ø± Ø§Ø±ØªØ¨Ø§Ø· Ø¨Ø§ Ø³Ø±ÙˆØ±: ` + escapeHtml(err.message) + `
                    </div>
                `;
                box.appendChild(errBubble);
            }} finally {{
                btn.disabled = false;
                box.scrollTop = box.scrollHeight;
            }}
        }}

        function escapeHtml(text) {{
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }}

        function uploadBannerFile(fileInput, targetInputId) {{
            const file = fileInput.files[0];
            if (!file) return;
            const statusEl = document.getElementById('bannerUploadStatus_' + targetInputId);
            if (statusEl) statusEl.innerText = 'â³ Ø¯Ø± Ø­Ø§Ù„ ÙØ´Ø±Ø¯Ù‡â€ŒØ³Ø§Ø²ÛŒ Ùˆ Ø¨Ø§Ø±Ú¯Ø°Ø§Ø±ÛŒ ØªØµÙˆÛŒØ± Ø¨Ù†Ø±...';

            let prodId = '';
            if (targetInputId === 'editPhoto') {{
                const editIdEl = document.getElementById('editProductId');
                if (editIdEl) prodId = editIdEl.value || '';
            }}

            const reader = new FileReader();
            reader.onload = async function(e) {{
                try {{
                    const res = await fetch('/api/upload/banner', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json; charset=utf-8' }},
                        body: JSON.stringify({{
                            filename: file.name,
                            prod_id: prodId,
                            data: e.target.result
                        }})
                    }});
                    const data = await res.json();
                    if (data.ok && data.url) {{
                        const targetInp = document.getElementById(targetInputId);
                        if (targetInp) {{
                            targetInp.value = data.url;
                            targetInp.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        }}
                        let previewEl = document.getElementById('bannerPreview_' + targetInputId);
                        if (!previewEl && targetInp) {{
                            previewEl = document.createElement('img');
                            previewEl.id = 'bannerPreview_' + targetInputId;
                            previewEl.className = 'w-24 h-24 object-cover rounded-xl mt-2 border border-cyan-500/50 shadow-md';
                            if (statusEl) {{
                                statusEl.parentNode.insertBefore(previewEl, statusEl);
                            }} else {{
                                targetInp.parentNode.parentNode.appendChild(previewEl);
                            }}
                        }}
                        if (previewEl) {{
                            previewEl.src = data.url;
                            previewEl.style.display = 'block';
                        }}
                        if (statusEl) statusEl.innerHTML = 'âœ… ØªØµÙˆÛŒØ± Ø°Ø®ÛŒØ±Ù‡ Ø´Ø¯: <a href="' + data.url + '" target="_blank" class="text-cyan-400 underline font-mono">' + data.url + '</a>';
                    }} else {{
                        if (statusEl) statusEl.innerText = 'âŒ Ø®Ø·Ø§: ' + (data.error || 'Ø¢Ù¾Ù„ÙˆØ¯ Ù†Ø§Ù…ÙˆÙÙ‚ Ø¨ÙˆØ¯');
                    }}
                }} catch (err) {{
                    if (statusEl) statusEl.innerText = 'âŒ Ø®Ø·Ø§ Ø¯Ø± Ø§Ø±Ø³Ø§Ù„ ÙØ§ÛŒÙ„: ' + err.message;
                }}
            }};
            reader.readAsDataURL(file);
        }}

        async function loadSettings() {{
            try {{
                const pwd = currentAdminPassword || sessionStorage.getItem('unfinit_admin_pwd') || '';
                const res = await fetch('/api/settings?password=' + encodeURIComponent(pwd));
                if (res.status === 401) {{
                    console.warn('loadSettings: unauthorized, active admin login session required.');
                    return;
                }}
                const data = await res.json();
                if (data.ok && data.settings) {{
                    populateSettingsForm(data.settings);
                }}
            }} catch (err) {{
                console.error('Failed to load settings:', err);
            }}
        }}

        const AI_PROVIDER_MODELS = {{
            vyceai: [
                {{ id: 'deepseek-v4.1', name: 'deepseek-v4.1 (VyceAI)' }},
                {{ id: 'deepseek-v4-flash', name: 'deepseek-v4-flash (VyceAI)' }},
                {{ id: 'claude-sonnet-4-6', name: 'claude-sonnet-4-6 (VyceAI)' }},
                {{ id: 'agnes-3.0-flash', name: 'agnes-3.0-flash (VyceAI)' }}
            ],
            nara: [
                {{ id: 'stepfun-3.7-flash', name: 'stepfun-3.7-flash (Nara)' }},
                {{ id: 'minimax-0.5-free', name: 'minimax-0.5-free (Nara)' }},
                {{ id: 'qwen2.5-72b', name: 'qwen2.5-72b (Nara)' }}
            ],
            gemini: [
                {{ id: 'gemini-2.0-flash', name: 'gemini-2.0-flash (Gemini)' }},
                {{ id: 'gemini-1.5-flash', name: 'gemini-1.5-flash (Gemini)' }},
                {{ id: 'gemini-1.5-pro', name: 'gemini-1.5-pro (Gemini)' }}
            ]
        }};

        function handleAiProviderChange(prov, currentModelVal) {{
            try {{
                const p = (prov || 'vyceai').toLowerCase();
                const sel = document.getElementById('cfg_AI_PROVIDER');
                if (sel && sel.value !== p) sel.value = p;
                
                const urlInput = document.getElementById('cfg_AI_BASE_URL');
                const modelSelect = document.getElementById('cfg_AI_MODEL');
                const customModelInput = document.getElementById('cfg_AI_MODEL_CUSTOM');
                
                const vyceBox = document.getElementById('box_vyceai_key');
                const naraBox = document.getElementById('box_nara_key');
                const geminiBox = document.getElementById('box_gemini_key');
                
                if (vyceBox) vyceBox.style.opacity = '0.65';
                if (naraBox) naraBox.style.opacity = '0.65';
                if (geminiBox) geminiBox.style.opacity = '0.65';

                const targetModel = currentModelVal || (modelSelect ? modelSelect.value : '') || '';

                if (p === 'custom') {{
                    if (modelSelect) modelSelect.classList.add('hidden');
                    if (customModelInput) {{
                        customModelInput.classList.remove('hidden');
                        if (targetModel) customModelInput.value = targetModel;
                    }}
                    if (vyceBox) vyceBox.style.opacity = '1';
                    if (naraBox) naraBox.style.opacity = '1';
                    if (geminiBox) geminiBox.style.opacity = '1';
                    return;
                }}

                // Standard Providers (vyceai, nara, gemini)
                if (customModelInput) customModelInput.classList.add('hidden');
                if (modelSelect) {{
                    modelSelect.classList.remove('hidden');
                    const models = AI_PROVIDER_MODELS[p] || AI_PROVIDER_MODELS.vyceai;
                    modelSelect.innerHTML = models.map(function(m) {{
                        return '<option value="' + m.id + '">' + m.name + '</option>';
                    }}).join('');
                    
                    const match = models.some(function(m) {{ return m.id === targetModel; }});
                    if (match) {{
                        modelSelect.value = targetModel;
                    }} else {{
                        modelSelect.value = models[0].id;
                    }}
                }}

                if (p === 'vyceai') {{
                    if (urlInput && (!urlInput.value || urlInput.value.includes('bynara') || urlInput.value.includes('googleapis'))) {{
                        urlInput.value = 'https://vyceai.com/v1';
                    }}
                    if (vyceBox) vyceBox.style.opacity = '1';
                }} else if (p === 'nara') {{
                    if (urlInput && (!urlInput.value || urlInput.value.includes('vyceai') || urlInput.value.includes('googleapis'))) {{
                        urlInput.value = 'https://router.bynara.id/v1';
                    }}
                    if (naraBox) naraBox.style.opacity = '1';
                }} else if (p === 'gemini') {{
                    if (urlInput && (!urlInput.value || urlInput.value.includes('vyceai') || urlInput.value.includes('bynara'))) {{
                        urlInput.value = 'https://generativelanguage.googleapis.com/v1beta';
                    }}
                    if (geminiBox) geminiBox.style.opacity = '1';
                }} else {{
                    if (vyceBox) vyceBox.style.opacity = '1';
                    if (naraBox) naraBox.style.opacity = '1';
                    if (geminiBox) geminiBox.style.opacity = '1';
                }}
            }} catch (err) {{
                console.warn('handleAiProviderChange notice:', err);
            }}
        }}

        function updateAiProviderView(provider) {{
            handleAiProviderChange(provider);
        }}

        function populateSettingsForm(s) {{
            try {{
                if (!s || typeof s !== 'object') return;
                const fields = [
                    'STORE_NAME', 'WELCOME_TEXT', 'COURSE_DELIVERY_NOTE',
                    'SUPPORT_CENTER_TEXT', 'INVITE_FRIENDS_TEXT',
                    'TELEGRAM_BOT_TOKEN', 'TELEGRAM_OWNER_ID', 'TELEGRAM_FORUM_GROUP_ID', 'ADMIN_USER_IDS',
                    'BALE_BOT_TOKEN', 'BALE_OWNER_ID', 'BALE_PAYMENT_TOKEN',
                    'RUBIKA_BOT_TOKEN', 'RUBIKA_OWNER_ID',
                    'FORCE_JOIN_CHANNEL_TELEGRAM', 'FORCE_JOIN_CHANNEL_BALE',
                    'CARD_NUMBER', 'CARD_HOLDER',
                    'DEFAULT_ARTIST', 'MAX_SAFE_BALE_SIZE_MB',
                    'COURSE_DESC_MAX_LEN',
                    'AI_BASE_URL', 'AI_API_KEY', 'AI_MODEL',
                    'AI_PROVIDER', 'VYCEAI_API_KEY',
                    'NARA_API_KEY', 'NARA_MODEL',
                    'GEMINI_API_KEY', 'GEMINI_MODEL',
                    'HF_TOKEN', 'HF_SPACE_ID',
                    'CASHBACK_PERCENT', 'FEED_AUTH_EMAIL', 'FEED_AUTH_PASSWORD', 'FEED_AUTH_COOKIE'
                ];
                fields.forEach(f => {{
                    const el = document.getElementById('cfg_' + f);
                    if (el && s[f] !== undefined) {{
                        if (el.tagName === 'SELECT') {{
                            let exists = Array.from(el.options).some(opt => opt.value === s[f]);
                            if (!exists && s[f]) {{
                                const opt = document.createElement('option');
                                opt.value = s[f];
                                opt.textContent = s[f] + ' (Ø³ÙØ§Ø±Ø´ÛŒ)';
                                el.appendChild(opt);
                            }}
                        }}
                        el.value = s[f];
                    }}
                }});
                const artistTagEl = document.getElementById('cfg_APPLY_DEFAULT_ARTIST_TAG');
                if (artistTagEl && s.APPLY_DEFAULT_ARTIST_TAG !== undefined) {{
                    artistTagEl.checked = !!s.APPLY_DEFAULT_ARTIST_TAG;
                }}
                const autoTitleEl = document.getElementById('cfg_AUTO_RENAME_FILE_TO_TITLE');
                if (autoTitleEl && s.AUTO_RENAME_FILE_TO_TITLE !== undefined) {{
                    autoTitleEl.checked = !!s.AUTO_RENAME_FILE_TO_TITLE;
                }}
                const studioArtistEl = document.getElementById('cfg_studio_auto_artist');
                if (studioArtistEl && s.APPLY_DEFAULT_ARTIST_TAG !== undefined) {{
                    studioArtistEl.checked = !!s.APPLY_DEFAULT_ARTIST_TAG;
                }}
                const studioTitleEl = document.getElementById('cfg_studio_auto_title');
                if (studioTitleEl && s.AUTO_RENAME_FILE_TO_TITLE !== undefined) {{
                    studioTitleEl.checked = !!s.AUTO_RENAME_FILE_TO_TITLE;
                }}

        async function toggleStudioMetaSetting(key, val) {{
            try {{
                const payload = {{}};
                payload[key] = val;
                if (key === 'APPLY_DEFAULT_ARTIST_TAG') {{
                    const el1 = document.getElementById('cfg_APPLY_DEFAULT_ARTIST_TAG');
                    if (el1) el1.checked = val;
                    const el2 = document.getElementById('cfg_studio_auto_artist');
                    if (el2) el2.checked = val;
                }} else if (key === 'AUTO_RENAME_FILE_TO_TITLE') {{
                    const el1 = document.getElementById('cfg_AUTO_RENAME_FILE_TO_TITLE');
                    if (el1) el1.checked = val;
                    const el2 = document.getElementById('cfg_studio_auto_title');
                    if (el2) el2.checked = val;
                }}
                let pwd = window.currentAdminPassword || sessionStorage.getItem('unfinit_admin_pwd') || '';
                await fetch('/api/settings/save', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json; charset=utf-8' }},
                    body: JSON.stringify({{
                        password: pwd,
                        settings: payload
                    }})
                }});
                const notice = document.getElementById('studioMetaSyncNotice');
                if (notice) {{
                    notice.classList.remove('hidden');
                    setTimeout(() => notice.classList.add('hidden'), 2500);
                }}
            }} catch (err) {{
                console.warn('toggleStudioMetaSetting error:', err);
            }}
        }}
        window.toggleStudioMetaSetting = toggleStudioMetaSetting;

                if (s.AI_PROVIDER) {{
                    handleAiProviderChange(s.AI_PROVIDER, s.AI_MODEL);
                }} else {{
                    handleAiProviderChange('vyceai', s.AI_MODEL);
                }}

                if (s.CUSTOM_KEYBOARD_LAYOUT && typeof initKeyboardCustomizer === 'function') {{
                    try {{
                        let kbLayout = typeof s.CUSTOM_KEYBOARD_LAYOUT === 'string' ? JSON.parse(s.CUSTOM_KEYBOARD_LAYOUT) : s.CUSTOM_KEYBOARD_LAYOUT;
                        if (Array.isArray(kbLayout) && kbLayout.length > 0) {{
                            initKeyboardCustomizer(kbLayout);
                        }} else {{
                            initKeyboardCustomizer();
                        }}
                    }} catch (e) {{
                        initKeyboardCustomizer();
                    }}
                }} else if (typeof initKeyboardCustomizer === 'function') {{
                    initKeyboardCustomizer();
                }}

                const p1 = document.getElementById('cfg_NEW_ADMIN_PASSWORD');
                const p2 = document.getElementById('cfg_CONFIRM_ADMIN_PASSWORD');
                if (p1) p1.value = '';
                if (p2) p2.value = '';
            }} catch (err) {{
                console.warn('populateSettingsForm notice:', err);
            }}
        }}

        function handleExportSettings() {{
            let pwd = currentAdminPassword || sessionStorage.getItem('unfinit_admin_pwd') || '';
            if (!pwd) {{
                pwd = prompt('Ø¬Ù‡Øª Ø¨Ø±ÙˆÙ†â€ŒØ¨Ø±ÛŒ ØªÙ†Ø¸ÛŒÙ…Ø§ØªØŒ Ù„Ø·ÙØ§Ù‹ Ø±Ù…Ø² Ø¹Ø¨ÙˆØ± Ù…Ø¯ÛŒØ±ÛŒØª Ø±Ø§ ÙˆØ§Ø±Ø¯ Ú©Ù†ÛŒØ¯:') || '';
                if (!pwd) return;
                currentAdminPassword = pwd;
                sessionStorage.setItem('unfinit_admin_pwd', pwd);
            }}
            window.open('/api/settings/export?password=' + encodeURIComponent(pwd), '_blank');
        }}

        function handleExportContactsCSV() {{
            let pwd = currentAdminPassword || sessionStorage.getItem('unfinit_admin_pwd') || '';
            if (!pwd) {{
                pwd = prompt('Ø¬Ù‡Øª Ø¨Ø±ÙˆÙ†â€ŒØ¨Ø±ÛŒ Ù…Ø®Ø§Ø·Ø¨ÛŒÙ†ØŒ Ù„Ø·ÙØ§Ù‹ Ø±Ù…Ø² Ø¹Ø¨ÙˆØ± Ù…Ø¯ÛŒØ±ÛŒØª Ø±Ø§ ÙˆØ§Ø±Ø¯ Ú©Ù†ÛŒØ¯:') || '';
                if (!pwd) return;
                currentAdminPassword = pwd;
                sessionStorage.setItem('unfinit_admin_pwd', pwd);
            }}
            window.open('/api/contacts/export_csv?pwd=' + encodeURIComponent(pwd), '_blank');
        }}

        async function handleImportSettingsFile(input) {{
            const file = input.files && input.files[0];
            if (!file) return;
            const confirmImport = confirm('Ø¢ÛŒØ§ Ø§Ø² Ø¨Ø§Ø²Ù†ÙˆÛŒØ³ÛŒ Ùˆ Ø¯Ø±ÙˆÙ†â€ŒØ±ÛŒØ²ÛŒ ØªÙ†Ø¸ÛŒÙ…Ø§Øª Ø¨Ø§ ÙØ§ÛŒÙ„ Ø§Ù†ØªØ®Ø§Ø¨ÛŒ Ù…Ø·Ù…Ø¦Ù† Ù‡Ø³ØªÛŒØ¯ØŸ');
            if (!confirmImport) {{
                input.value = '';
                return;
            }}

            const reader = new FileReader();
            reader.onload = async (e) => {{
                try {{
                    const importedObj = JSON.parse(e.target.result);
                    let pwd = currentAdminPassword || sessionStorage.getItem('unfinit_admin_pwd') || '';
                    if (!pwd) {{
                        pwd = prompt('Ø¬Ù‡Øª Ø¯Ø±ÙˆÙ†â€ŒØ¨Ø±ÛŒ ØªÙ†Ø¸ÛŒÙ…Ø§ØªØŒ Ù„Ø·ÙØ§Ù‹ Ø±Ù…Ø² Ø¹Ø¨ÙˆØ± Ù…Ø¯ÛŒØ±ÛŒØª Ø±Ø§ ÙˆØ§Ø±Ø¯ Ú©Ù†ÛŒØ¯:') || '';
                        if (!pwd) {{
                            input.value = '';
                            return;
                        }}
                        currentAdminPassword = pwd;
                        sessionStorage.setItem('unfinit_admin_pwd', pwd);
                    }}
                    const res = await fetch('/api/settings/import', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json; charset=utf-8' }},
                        body: JSON.stringify({{
                            password: pwd,
                            settings: importedObj
                        }})
                    }});
                    const data = await res.json();
                    if (data.ok) {{
                        showToast('âœ… ' + (data.message || 'ØªÙ†Ø¸ÛŒÙ…Ø§Øª Ø¨Ø§ Ù…ÙˆÙÙ‚ÛŒØª Ø¨Ø§Ø²ÛŒØ§Ø¨ÛŒ Ø´Ø¯Ù†Ø¯.'));
                        loadSettings();
                    }} else {{
                        showToast('âŒ Ø®Ø·Ø§ Ø¯Ø± Ø¯Ø±ÙˆÙ†â€ŒØ±ÛŒØ²ÛŒ ØªÙ†Ø¸ÛŒÙ…Ø§Øª: ' + (data.error || ''));
                    }}
                }} catch (err) {{
                    showToast('âŒ Ø®Ø·Ø§ Ø¯Ø± Ø®ÙˆØ§Ù†Ø¯Ù† ÛŒØ§ ØªØ­Ù„ÛŒÙ„ ÙØ§ÛŒÙ„ JSON: ' + err.message);
                }} finally {{
                    input.value = '';
                }}
            }};
            reader.readAsText(file, 'utf-8');
        }}

        async function handleSaveSettings(e) {{
            if (e) e.preventDefault();
            const btn = (e && e.submitter) ? e.submitter : (document.getElementById('btnSaveSettings') || document.getElementById('btnSaveTokens'));
            const btn1 = document.getElementById('btnSaveSettings');
            const btn2 = document.getElementById('btnSaveTokens');
            const statusEl = document.getElementById('settingsSaveStatus') || document.getElementById('tokensSaveStatus');
            const status1 = document.getElementById('settingsSaveStatus');
            const status2 = document.getElementById('tokensSaveStatus');
            
            const orig1 = btn1 ? btn1.innerText : 'ðŸ’¾ Ø°Ø®ÛŒØ±Ù‡ Ùˆ Ø§Ø¹Ù…Ø§Ù„ Ø¢Ù†ÛŒ ØªÙ†Ø¸ÛŒÙ…Ø§Øª';
            const orig2 = btn2 ? btn2.innerText : 'ðŸ’¾ Ø°Ø®ÛŒØ±Ù‡ Ø³Ú©Ø±Øªâ€ŒÙ‡Ø§ Ùˆ ØªÙˆÚ©Ù†â€ŒÙ‡Ø§';
            if (btn1) {{ btn1.disabled = true; btn1.innerText = 'Ø¯Ø± Ø­Ø§Ù„ Ø°Ø®ÛŒØ±Ù‡...'; }}
            if (btn2) {{ btn2.disabled = true; btn2.innerText = 'Ø¯Ø± Ø­Ø§Ù„ Ø°Ø®ÛŒØ±Ù‡...'; }}
            if (status1) status1.innerText = '';
            if (status2) status2.innerText = '';

            const p1 = (document.getElementById('cfg_NEW_ADMIN_PASSWORD')?.value || '').trim();
            const p2 = (document.getElementById('cfg_CONFIRM_ADMIN_PASSWORD')?.value || '').trim();
            if (p1) {{
                if (p1 !== p2) {{
                    showToast('âŒ Ø®Ø·Ø§ÛŒ ØªØºÛŒÛŒØ± Ø±Ù…Ø²: ØªÚ©Ø±Ø§Ø± Ø±Ù…Ø² Ø¹Ø¨ÙˆØ± Ø¬Ø¯ÛŒØ¯ Ø¨Ø§ Ø±Ù…Ø² ÙˆØ§Ø±Ø¯ Ø´Ø¯Ù‡ Ù‡Ù…Ø®ÙˆØ§Ù†ÛŒ Ù†Ø¯Ø§Ø±Ø¯.');
                    if (btn1) {{ btn1.disabled = false; btn1.innerText = orig1; }}
                    if (btn2) {{ btn2.disabled = false; btn2.innerText = orig2; }}
                    return;
                }}
            }}

            const settings = {{}};
            const fields = [
                'STORE_NAME', 'WELCOME_TEXT', 'COURSE_DELIVERY_NOTE',
                'SUPPORT_CENTER_TEXT', 'INVITE_FRIENDS_TEXT',
                'TELEGRAM_BOT_TOKEN', 'TELEGRAM_OWNER_ID', 'TELEGRAM_FORUM_GROUP_ID', 'ADMIN_USER_IDS',
                'BALE_BOT_TOKEN', 'BALE_OWNER_ID', 'BALE_PAYMENT_TOKEN',
                'RUBIKA_BOT_TOKEN', 'RUBIKA_OWNER_ID',
                'FORCE_JOIN_CHANNEL_TELEGRAM', 'FORCE_JOIN_CHANNEL_BALE',
                'CARD_NUMBER', 'CARD_HOLDER',
                'DEFAULT_ARTIST', 'MAX_SAFE_BALE_SIZE_MB',
                'COURSE_DESC_MAX_LEN',
                'AI_BASE_URL', 'AI_API_KEY', 'AI_MODEL',
                'AI_PROVIDER', 'VYCEAI_API_KEY',
                'NARA_API_KEY', 'NARA_MODEL',
                'GEMINI_API_KEY', 'GEMINI_MODEL',
                'HF_TOKEN', 'HF_SPACE_ID',
                'CASHBACK_PERCENT', 'FEED_AUTH_EMAIL', 'FEED_AUTH_PASSWORD', 'FEED_AUTH_COOKIE'
            ];
            const sensitiveKeys = [
                'TELEGRAM_BOT_TOKEN', 'BALE_BOT_TOKEN', 'BALE_PAYMENT_TOKEN',
                'RUBIKA_BOT_TOKEN', 'AI_API_KEY', 'VYCEAI_API_KEY', 'NARA_API_KEY',
                'GEMINI_API_KEY', 'HF_TOKEN', 'FEED_AUTH_PASSWORD', 'FEED_AUTH_COOKIE'
            ];
            fields.forEach(f => {{
                const el = document.getElementById('cfg_' + f);
                if (el) {{
                    const val = el.value.trim();
                    if (sensitiveKeys.includes(f)) {{
                        if (val && !val.includes('â€¢â€¢â€¢â€¢') && !val.includes('****')) {{
                            settings[f] = val;
                        }}
                    }} else {{
                        settings[f] = val;
                    }}
                }}
            }});
            const artistTagEl = document.getElementById('cfg_APPLY_DEFAULT_ARTIST_TAG');
            if (artistTagEl) {{
                settings['APPLY_DEFAULT_ARTIST_TAG'] = artistTagEl.checked;
            }}
            const autoTitleEl = document.getElementById('cfg_AUTO_RENAME_FILE_TO_TITLE');
            if (autoTitleEl) {{
                settings['AUTO_RENAME_FILE_TO_TITLE'] = autoTitleEl.checked;
            }}
            const activeProv = (document.getElementById('cfg_AI_PROVIDER')?.value || 'vyceai').toLowerCase();
            if (activeProv === 'custom') {{
                const customModelVal = (document.getElementById('cfg_AI_MODEL_CUSTOM')?.value || '').trim();
                if (customModelVal) {{
                    settings['AI_MODEL'] = customModelVal;
                }}
            }} else {{
                const selModelVal = (document.getElementById('cfg_AI_MODEL')?.value || '').trim();
                if (selModelVal) {{
                    settings['AI_MODEL'] = selModelVal;
                }}
            }}
            if (activeProv === 'vyceai' && settings['VYCEAI_API_KEY']) {{
                settings['AI_API_KEY'] = settings['VYCEAI_API_KEY'];
            }} else if (activeProv === 'nara' && settings['NARA_API_KEY']) {{
                settings['AI_API_KEY'] = settings['NARA_API_KEY'];
            }} else if (activeProv === 'gemini' && settings['GEMINI_API_KEY']) {{
                settings['AI_API_KEY'] = settings['GEMINI_API_KEY'];
            }}
            if (typeof getKeyboardCustomizerLayout === 'function') {{
                const kl = getKeyboardCustomizerLayout();
                settings['CUSTOM_KEYBOARD_LAYOUT'] = kl;
                settings['MAIN_KEYBOARD_LAYOUT'] = kl;
            }}
            if (p1) {{
                settings['NEW_ADMIN_PASSWORD'] = p1;
            }}

            let pwdToSend = currentAdminPassword || sessionStorage.getItem('unfinit_admin_pwd') || localStorage.getItem('unfinit_admin_pwd') || '';
            if (!pwdToSend) {{
                pwdToSend = prompt('Ø¬Ù‡Øª ØªØ§ÛŒÛŒØ¯ Ùˆ Ø°Ø®ÛŒØ±Ù‡ ØªÙ†Ø¸ÛŒÙ…Ø§ØªØŒ Ù„Ø·ÙØ§Ù‹ Ø±Ù…Ø² Ø¹Ø¨ÙˆØ± Ù…Ø¯ÛŒØ±ÛŒØª Ø±Ø§ ÙˆØ§Ø±Ø¯ Ú©Ù†ÛŒØ¯:') || '';
                if (!pwdToSend) {{
                    showToast('âŒ Ø°Ø®ÛŒØ±Ù‡ ØªÙ†Ø¸ÛŒÙ…Ø§Øª Ù„ØºÙˆ Ø´Ø¯: Ø±Ù…Ø² Ø¹Ø¨ÙˆØ± Ù…Ø¯ÛŒØ±ÛŒØª ÙˆØ§Ø±Ø¯ Ù†Ø´Ø¯.');
                    if (btn1) {{ btn1.disabled = false; btn1.innerText = orig1; }}
                    if (btn2) {{ btn2.disabled = false; btn2.innerText = orig2; }}
                    return;
                }}
                currentAdminPassword = pwdToSend;
                sessionStorage.setItem('unfinit_admin_pwd', pwdToSend);
            }}

            try {{
                const res = await fetch('/api/settings', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json; charset=utf-8' }},
                    body: JSON.stringify({{
                        password: pwdToSend,
                        settings: settings
                    }})
                }});
                const data = await res.json();
                if (data.ok) {{
                    if (p1) {{
                        currentAdminPassword = p1;
                        sessionStorage.setItem('unfinit_admin_pwd', p1);
                        localStorage.setItem('unfinit_admin_pwd', p1);
                        const p1El = document.getElementById('cfg_NEW_ADMIN_PASSWORD');
                        const p2El = document.getElementById('cfg_CONFIRM_ADMIN_PASSWORD');
                        if (p1El) p1El.value = '';
                        if (p2El) p2El.value = '';
                    }}
                    const successMsg = 'âœ… ' + (data.message || 'ØªÙ†Ø¸ÛŒÙ…Ø§Øª Ùˆ Ø³Ú©Ø±Øªâ€ŒÙ‡Ø§ÛŒ Ø§Ø¨Ø±ÛŒ Ø¨Ø§ Ù…ÙˆÙÙ‚ÛŒØª Ø°Ø®ÛŒØ±Ù‡ Ùˆ Ø¯Ø± Hugging Face Ø§Ø¹Ù…Ø§Ù„ Ø´Ø¯!');
                    if (status1) status1.innerText = successMsg;
                    if (status2) status2.innerText = successMsg;
                    setTimeout(() => {{
                        if (status1) status1.innerText = '';
                        if (status2) status2.innerText = '';
                    }}, 5000);
                }} else {{
                    showToast('âŒ Ø®Ø·Ø§ Ø¯Ø± Ø°Ø®ÛŒØ±Ù‡ ØªÙ†Ø¸ÛŒÙ…Ø§Øª: ' + (data.error || ''));
                }}
            }} catch (err) {{
                showToast('âŒ Ø®Ø·Ø§ÛŒ Ø§Ø±ØªØ¨Ø§Ø·: ' + err.message);
            }} finally {{
                if (btn1) {{ btn1.disabled = false; btn1.innerText = orig1; }}
                if (btn2) {{ btn2.disabled = false; btn2.innerText = orig2; }}
            }}
        }}

        async function copyAllLogs() {{
            const btnText = document.getElementById('copyBtnText');
            try {{
                const res = await fetch('/api/logs');
                const data = await res.json();
                let textToCopy = '';
                if (data.ok && Array.isArray(data.logs)) {{
                    textToCopy = data.logs.join('\\n');
                }} else {{
                    textToCopy = document.getElementById('logContainer').innerText;
                }}
                await navigator.clipboard.writeText(textToCopy);
                btnText.innerText = 'âœ… Ú©Ù¾ÛŒ Ø´Ø¯!';
                setTimeout(() => {{ btnText.innerText = 'Ú©Ù¾ÛŒ Ú©Ù„ Ù„Ø§Ú¯â€ŒÙ‡Ø§'; }}, 2500);
            }} catch (err) {{
                btnText.innerText = 'âŒ Ø®Ø·Ø§ Ø¯Ø± Ú©Ù¾ÛŒ';
                setTimeout(() => {{ btnText.innerText = 'Ú©Ù¾ÛŒ Ú©Ù„ Ù„Ø§Ú¯â€ŒÙ‡Ø§'; }}, 2000);
            }}
        }}

        async function fetchLogs() {{
            try {{
                const res = await fetch('/api/logs');
                const data = await res.json();
                if (data.ok && Array.isArray(data.logs)) {{
                    const container = document.getElementById('logContainer');
                    if (data.logs.length === 0) {{
                        container.innerHTML = '<div class="text-slate-500">Ù‡ÛŒÚ† Ù„Ø§Ú¯ÛŒ Ù‡Ù†ÙˆØ² Ø«Ø¨Øª Ù†Ø´Ø¯Ù‡ Ø§Ø³Øª.</div>';
                    }} else {{
                        container.innerHTML = data.logs.map(l => {{
                            let color = 'text-slate-300';
                            if (l.includes('[ERROR]')) color = 'text-rose-400 font-bold';
                            else if (l.includes('[WARNING]')) color = 'text-amber-300';
                            else if (l.includes('[INFO]')) color = 'text-cyan-300';
                            return `<div class="${{color}}">${{l.replace(/</g, '&lt;').replace(/>/g, '&gt;')}}</div>`;
                        }}).join('');
                        container.scrollTop = container.scrollHeight;
                    }}
                }}
            }} catch (e) {{}}
        }}
        fetchLogs();
        setInterval(fetchLogs, 4000);
        let selectedLogoBase64 = null;
        function handleLogoFileSelect(input) {{
            try {{
                const file = input.files && input.files[0];
                if (!file) return;
                const reader = new FileReader();
                reader.onload = function(e) {{
                    selectedLogoBase64 = e.target.result;
                    const preview = document.getElementById('panelLogoPreview');
                    if (preview) {{
                        preview.src = selectedLogoBase64;
                        preview.style.display = 'block';
                        if (preview.nextElementSibling) preview.nextElementSibling.style.display = 'none';
                    }}
                    const btn = document.getElementById('btnUploadLogo');
                    if (btn) {{
                        btn.disabled = false;
                        btn.classList.remove('bg-cyan-600/50', 'text-slate-400', 'cursor-not-allowed');
                        btn.classList.add('bg-cyan-600', 'hover:bg-cyan-500', 'text-white', 'shadow-md');
                    }}
                }};
                reader.readAsDataURL(file);
            }} catch (err) {{
                console.error('handleLogoFileSelect error:', err);
            }}
        }}

        async function uploadCustomLogo() {{
            if (!selectedLogoBase64) return;
            const btn = document.getElementById('btnUploadLogo');
            const status = document.getElementById('logoUploadStatus');
            const origText = btn ? btn.innerHTML : '';
            if (btn) {{ btn.disabled = true; btn.innerText = 'Ø¯Ø± Ø­Ø§Ù„ Ø¢Ù¾Ù„ÙˆØ¯...'; }}
            if (status) {{ status.className = 'text-xs text-cyan-400'; status.innerText = 'Ø¯Ø± Ø­Ø§Ù„ Ù¾Ø±Ø¯Ø§Ø²Ø´ Ùˆ Ø°Ø®ÛŒØ±Ù‡ ØªØµÙˆÛŒØ± Ù„ÙˆÚ¯Ùˆ...'; }}

            let pwd = currentAdminPassword || sessionStorage.getItem('unfinit_admin_pwd') || localStorage.getItem('unfinit_admin_pwd') || '';
            try {{
                const res = await fetch('/api/upload/logo', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json; charset=utf-8' }},
                    body: JSON.stringify({{
                        password: pwd,
                        image: selectedLogoBase64
                    }})
                }});
                const data = await res.json();
                if (data.ok) {{
                    const newUrl = data.url || ('/static/logo.png?t=' + Date.now());
                    const headerImg = document.getElementById('headerLogoImg');
                    const loginImg = document.getElementById('loginLogoImg');
                    const previewImg = document.getElementById('panelLogoPreview');
                    [headerImg, loginImg, previewImg].forEach(img => {{
                        if (img) {{
                            img.src = newUrl;
                            img.style.display = 'block';
                            if (img.nextElementSibling) img.nextElementSibling.style.display = 'none';
                        }}
                    }});
                    if (status) {{
                        status.className = 'text-xs text-emerald-400 font-bold';
                        status.innerText = 'âœ… Ù„ÙˆÚ¯Ùˆ Ø¨Ø§ Ù…ÙˆÙÙ‚ÛŒØª Ø°Ø®ÛŒØ±Ù‡ Ùˆ Ø¯Ø± ØªÙ…Ø§Ù… Ø¨Ø®Ø´â€ŒÙ‡Ø§ Ø¨Ù‡â€ŒØ±ÙˆØ²Ø±Ø³Ø§Ù†ÛŒ Ø´Ø¯.';
                    }}
                }} else {{
                    if (status) {{
                        status.className = 'text-xs text-rose-400 font-bold';
                        status.innerText = 'âŒ Ø®Ø·Ø§: ' + (data.error || 'Ø¢Ù¾Ù„ÙˆØ¯ Ù†Ø§Ù…ÙˆÙÙ‚ Ø¨ÙˆØ¯.');
                    }}
                }}
            }} catch (err) {{
                if (status) {{
                    status.className = 'text-xs text-rose-400 font-bold';
                    status.innerText = 'âŒ Ø®Ø·Ø§ÛŒ Ø´Ø¨Ú©Ù‡: ' + err.message;
                }}
            }} finally {{
                if (btn) {{
                    btn.disabled = false;
                    btn.innerHTML = origText || '<span>â¬†ï¸</span> Ø¢Ù¾Ù„ÙˆØ¯ Ùˆ Ø§Ø¹Ù…Ø§Ù„ Ù„ÙˆÚ¯Ùˆ';
                }}
            }}
        }}

        function clearLiveLogs() {{
            const container = document.getElementById('logContainer');
            if (container) {{
                container.innerHTML = '<div class="text-slate-500">ØµÙØ­Ù‡ Ù†Ù…Ø§ÛŒØ´ Ù„Ø§Ú¯â€ŒÙ‡Ø§ Ù¾Ø§Ú©Ø³Ø§Ø²ÛŒ Ø´Ø¯.</div>';
            }}
        }}

        /**
         * Ø¨Ø§Ø±Ú¯Ø°Ø§Ø±ÛŒ ØªÙ†Ø¸ÛŒÙ…Ø§Øª Ù¾Ù„Ù† Ø§Ø´ØªØ±Ø§Ú© Ù¾Ø±ÛŒÙ…ÛŒÙˆÙ… (VIP Club) Ùˆ Ù†Ø´Ø§Ù†Ù‡ Ø±ÙˆØ²Ø§Ù†Ù‡
         */
        async function loadVipSettings() {{
            try {{
                const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                const res = await fetch('/api/vip/settings', {{
                    headers: {{
                        'Authorization': 'Bearer ' + pwd,
                        'X-Admin-Password': pwd
                    }}
                }});
                const data = await res.json();
                if (data.ok) {{
                    const p = document.getElementById('cfgVipMonthlyPrice');
                    if (p) {{
                        const raw = String(data.vip_monthly_price || '111000').replace(/[,ØŒ\\s]/g, '');
                        p.value = Number(raw) ? Number(raw).toLocaleString('en-US') : '111,000';
                    }}
                    const d = document.getElementById('cfgVipDurationDays');
                    if (d) d.value = data.vip_duration_days || '30';
                    const c = document.getElementById('cfgVipCardNumber');
                    if (c) c.value = data.vip_card_number || '';
                    const b = document.getElementById('cfgVipBaleToken');
                    if (b) b.value = data.vip_bale_payment_token || '';
                    const r = document.getElementById('cfgSignReaderTag');
                    if (r) r.value = data.sign_reader_tag || 'abasmanesh365';
                    const ch = document.getElementById('cfgSignExtractChapters');
                    if (ch) ch.checked = !!data.sign_extract_chapters;
                }}
            }} catch (err) {{
                console.debug('loadVipSettings error', err);
            }}
        }}
        window.loadVipSettings = loadVipSettings;

        /**
         * Ø°Ø®ÛŒØ±Ù‡ ØºÛŒØ±Ù‡Ù…Ú¯Ø§Ù… (AJAX) ØªÙ†Ø¸ÛŒÙ…Ø§Øª Ù¾Ù„Ù† Ø§Ø´ØªØ±Ø§Ú© Ù¾Ø±ÛŒÙ…ÛŒÙˆÙ… Ùˆ Ù†Ø´Ø§Ù†Ù‡ Ø±ÙˆØ²Ø§Ù†Ù‡ Ø¨Ø¯ÙˆÙ† Ø±ÙØ±Ø´ ØµÙØ­Ù‡
         */
        async function saveVipSettings(e) {{
            if (e && e.preventDefault) e.preventDefault();
            const btn = document.getElementById('btnSaveVipSettings');
            const toast = document.getElementById('vipSaveToast');
            if (btn) {{
                btn.disabled = true;
                btn.innerText = 'Ø¯Ø± Ø­Ø§Ù„ Ø°Ø®ÛŒØ±Ù‡...';
            }}
            try {{
                const rawPrice = (document.getElementById('cfgVipMonthlyPrice')?.value || '111000').replace(/[,ØŒ\\s]/g, '');
                const payload = {{
                    vip_monthly_price: parseInt(rawPrice) || 111000,
                    vip_duration_days: parseInt(document.getElementById('cfgVipDurationDays')?.value || '30') || 30,
                    vip_card_number: (document.getElementById('cfgVipCardNumber')?.value || '').trim(),
                    vip_bale_payment_token: (document.getElementById('cfgVipBaleToken')?.value || '').trim(),
                    sign_reader_tag: (document.getElementById('cfgSignReaderTag')?.value || 'abasmanesh365').trim(),
                    sign_extract_chapters: !!document.getElementById('cfgSignExtractChapters')?.checked
                }};

                const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                const res = await fetch('/api/vip/settings', {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json; charset=utf-8',
                        'Authorization': 'Bearer ' + pwd,
                        'X-Admin-Password': pwd
                    }},
                    body: JSON.stringify(payload)
                }});
                const data = await res.json();
                if (data.ok) {{
                    if (toast) {{
                        toast.classList.remove('hidden');
                        toast.innerText = 'âœ… ØªÙ†Ø¸ÛŒÙ…Ø§Øª Ø§Ø´ØªØ±Ø§Ú© Ù¾Ø±ÛŒÙ…ÛŒÙˆÙ… Ùˆ Ù†Ø´Ø§Ù†Ù‡ Ø¨Ø§ Ù…ÙˆÙÙ‚ÛŒØª Ø°Ø®ÛŒØ±Ù‡ Ø´Ø¯.';
                        setTimeout(() => {{ toast.classList.add('hidden'); }}, 4000);
                    }}
                }} else {{
                    showToast('âŒ Ø®Ø·Ø§ Ø¯Ø± Ø°Ø®ÛŒØ±Ù‡ ØªÙ†Ø¸ÛŒÙ…Ø§Øª: ' + (data.error || 'Ù†Ø§Ù…ÙˆÙÙ‚'));
                }}
            }} catch (err) {{
                showToast('âŒ Ø®Ø·Ø§ÛŒ Ø§Ø±ØªØ¨Ø§Ø· Ø¨Ø§ Ø³Ø±ÙˆØ±: ' + err.message);
            }} finally {{
                if (btn) {{
                    btn.disabled = false;
                    btn.innerHTML = '<svg class="w-4 h-4 stroke-[2]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" /></svg><span>Ø°Ø®ÛŒØ±Ù‡ ØªÙ†Ø¸ÛŒÙ…Ø§Øª Ø§Ø´ØªØ±Ø§Ú© Ùˆ Ù†Ø´Ø§Ù†Ù‡</span>';
                }}
            }}
        }}
        window.saveVipSettings = saveVipSettings;

        /**
         * Ø¨Ø§Ø±Ú¯Ø°Ø§Ø±ÛŒ Ù„ÛŒØ³Øª Ú©Ø§Ù…Ù„ Ú©Ø§Ø±Øªâ€ŒÙ‡Ø§ÛŒ ÙØ±Ú©Ø§Ù†Ø³ ÙØ±Ø§ÙˆØ§Ù†ÛŒ Ùˆ Ø±Ù†Ø¯Ø± Ø³Ø·Ø±Ù‡Ø§ Ø¨Ù‡ Ù‡Ù…Ø±Ø§Ù‡ Ø¯Ú©Ù…Ù‡â€ŒÙ‡Ø§ÛŒ ÙˆÛŒØ±Ø§ÛŒØ´ Ùˆ Ø­Ø°Ù.
         */
        async function loadFrequenciesTable() {{
            const tbody = document.getElementById('frequencyTableBody');
            if (!tbody) return;
            try {{
                tbody.innerHTML = '<tr><td colspan="5" class="py-6 text-center text-slate-400 animate-pulse">Ø¯Ø± Ø­Ø§Ù„ ÙØ±Ø§Ø®ÙˆØ§Ù†ÛŒ Ø¯Ø§Ø¯Ù‡â€ŒÙ‡Ø§...</td></tr>';
                const res = await fetch('/api/frequencies');
                const data = await res.json();
                if (!data.ok || !Array.isArray(data.frequencies) || data.frequencies.length === 0) {{
                    window.UNFINIT_FREQUENCIES = [];
                    tbody.innerHTML = '<tr><td colspan="5" class="py-6 text-center text-slate-400">Ù‡ÛŒÚ† Ø¹Ø¨Ø§Ø±ØªÛŒ Ø«Ø¨Øª Ù†Ø´Ø¯Ù‡ Ø§Ø³Øª.</td></tr>';
                    return;
                }}
                window.UNFINIT_FREQUENCIES = data.frequencies;
                tbody.innerHTML = data.frequencies.map((item, idx) => {{
                    const isMorning = item.category === 'MORNING';
                    const catBadge = isMorning 
                        ? '<span class="px-2.5 py-1 rounded-full text-[11px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">ØµØ¨Ø­Ú¯Ø§Ù‡ÛŒ</span>'
                        : '<span class="px-2.5 py-1 rounded-full text-[11px] font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">Ø´Ø¨Ø§Ù†Ú¯Ø§Ù‡ÛŒ</span>';
                    return `
                        <tr class="hover:bg-white/[0.02] transition">
                            <td class="py-3 px-4 text-center font-mono text-slate-400">${{idx + 1}}</td>
                            <td class="py-3 px-4 font-bold text-slate-100">${{escapeHtml(item.title || '')}}</td>
                            <td class="py-3 px-4 text-center">${{catBadge}}</td>
                            <td class="py-3 px-4 leading-relaxed" style="color: var(--text-muted);">${{escapeHtml(item.text || '')}}</td>
                            <td class="py-3 px-4 text-center">
                                <div class="flex items-center justify-center gap-1.5">
                                    <button type="button" onclick="openEditFrequencyModal('${{escapeHtml(item.id)}}')" title="ÙˆÛŒØ±Ø§ÛŒØ´ Ø¹Ø¨Ø§Ø±Øª" class="p-1.5 rounded-lg bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-400 transition inline-flex items-center justify-center">
                                        <svg class="w-4 h-4 stroke-[2]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path stroke-linecap="round" stroke-linejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L6.832 19.82a4.5 4.5 0 01-1.897 1.13l-2.685.8.8-2.685a4.5 4.5 0 011.13-1.897L16.863 4.487zm0 0L19.5 7.125" />
                                        </svg>
                                    </button>
                                    <button type="button" onclick="deleteFrequencyItem('${{escapeHtml(item.id)}}')" title="Ø­Ø°Ù Ø¹Ø¨Ø§Ø±Øª" class="p-1.5 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 transition inline-flex items-center justify-center">
                                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                        </svg>
                                    </button>
                                </div>
                            </td>
                        </tr>
                    `;
                }}).join('');
            }} catch (err) {{
                console.error('[loadFrequenciesTable error]:', err);
                tbody.innerHTML = '<tr><td colspan="5" class="py-6 text-center text-rose-400">Ø®Ø·Ø§ Ø¯Ø± Ø¨Ø§Ø±Ú¯Ø°Ø§Ø±ÛŒ Ù„ÛŒØ³Øª ÙØ±Ú©Ø§Ù†Ø³â€ŒÙ‡Ø§.</td></tr>';
            }}
        }}

        /**
         * Ø¨Ø§Ø² Ú©Ø±Ø¯Ù† Ù…ÙˆØ¯Ø§Ù„ ÙˆÛŒØ±Ø§ÛŒØ´ Ú©Ø§Ø±Øª ÙØ±Ú©Ø§Ù†Ø³ ÙØ±Ø§ÙˆØ§Ù†ÛŒ Ùˆ ØªÚ©Ù…ÛŒÙ„ ÙÛŒÙ„Ø¯Ù‡Ø§ Ø¨Ø§ Ø§Ø·Ù„Ø§Ø¹Ø§Øª Ù…ÙˆØ¬ÙˆØ¯.
         * ÙˆØ±ÙˆØ¯ÛŒ: id (Ø´Ù†Ø§Ø³Ù‡ Ù…Ù†Ø­ØµØ±Ø¨Ù‡â€ŒÙØ±Ø¯ Ø¹Ø¨Ø§Ø±Øª)
         */
        function openEditFrequencyModal(id) {{
            if (!id) return;
            const items = window.UNFINIT_FREQUENCIES || [];
            const item = items.find(x => String(x.id) === String(id));
            if (!item) {{
                showToast('Ø¹Ø¨Ø§Ø±Øª Ù…ÙˆØ±Ø¯ Ù†Ø¸Ø± Ø¯Ø± Ø­Ø§ÙØ¸Ù‡ ÛŒØ§ÙØª Ù†Ø´Ø¯.');
                return;
            }}
            const idInput = document.getElementById('freqEditId');
            const catSelect = document.getElementById('freqEditCategory');
            const titleInput = document.getElementById('freqEditTitle');
            const textInput = document.getElementById('freqEditText');

            if (idInput) idInput.value = item.id;
            if (catSelect) catSelect.value = item.category || 'MORNING';
            if (titleInput) titleInput.value = item.title || '';
            if (textInput) textInput.value = item.text || '';

            const m = document.getElementById('modalEditFrequency');
            if (m) m.classList.remove('hidden');
        }}

        /**
         * Ø¨Ø³ØªÙ† Ù…ÙˆØ¯Ø§Ù„ ÙˆÛŒØ±Ø§ÛŒØ´ Ú©Ø§Ø±Øª ÙØ±Ú©Ø§Ù†Ø³ ÙØ±Ø§ÙˆØ§Ù†ÛŒ.
         */
        function closeEditFrequencyModal() {{
            const m = document.getElementById('modalEditFrequency');
            if (m) m.classList.add('hidden');
        }}

        /**
         * Ø§Ø±Ø³Ø§Ù„ Ø¯Ø±Ø®ÙˆØ§Ø³Øª ÙˆÛŒØ±Ø§ÛŒØ´ Ø¹Ø¨Ø§Ø±Øª ÙØ±Ú©Ø§Ù†Ø³ ÙØ±Ø§ÙˆØ§Ù†ÛŒ Ø¨Ù‡ Ø³Ø±ÙˆØ± (/api/frequencies/edit).
         * ÙˆØ±ÙˆØ¯ÛŒ: Ø±ÙˆÛŒØ¯Ø§Ø¯ Ø§Ø±Ø³Ø§Ù„ ÙØ±Ù… (e)
         */
        async function submitEditFrequency(e) {{
            if (e) e.preventDefault();
            const id = (document.getElementById('freqEditId')?.value || '').trim();
            const cat = document.getElementById('freqEditCategory')?.value || 'MORNING';
            const title = (document.getElementById('freqEditTitle')?.value || '').trim();
            const text = (document.getElementById('freqEditText')?.value || '').trim();
            if (!id || !title || !text) {{
                showToast('Ù„Ø·ÙØ§Ù‹ Ø¹Ù†ÙˆØ§Ù† Ùˆ Ù…ØªÙ† Ø¹Ø¨Ø§Ø±Øª Ø±Ø§ ÙˆØ§Ø±Ø¯ Ù†Ù…Ø§ÛŒÛŒØ¯.');
                return;
            }}
            const btn = document.getElementById('btnSubmitEditFrequency');
            if (btn) btn.disabled = true;
            try {{
                const res = await fetch('/api/frequencies/edit', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json; charset=utf-8' }},
                    body: JSON.stringify({{ id: id, category: cat, title: title, text: text }})
                }});
                const data = await res.json();
                if (data.ok) {{
                    closeEditFrequencyModal();
                    loadFrequenciesTable();
                }} else {{
                    showToast('Ø®Ø·Ø§ Ø¯Ø± ÙˆÛŒØ±Ø§ÛŒØ´ Ø¹Ø¨Ø§Ø±Øª: ' + (data.error || 'Ù†Ø§Ø´Ù†Ø§Ø®ØªÙ‡'));
                }}
            }} catch (err) {{
                showToast('Ø®Ø·Ø§ÛŒ Ø§Ø±ØªØ¨Ø§Ø· Ø¨Ø§ Ø³Ø±ÙˆØ±: ' + err.message);
            }} finally {{
                if (btn) btn.disabled = false;
            }}
        }}

        async function submitAddNewFrequency(e) {{
            if (e) e.preventDefault();
            const cat = document.getElementById('freqNewCategory')?.value || 'MORNING';
            const title = (document.getElementById('freqNewTitle')?.value || '').trim();
            const text = (document.getElementById('freqNewText')?.value || '').trim();
            if (!title || !text) {{
                showToast('Ù„Ø·ÙØ§Ù‹ Ø¹Ù†ÙˆØ§Ù† Ùˆ Ù…ØªÙ† Ø¹Ø¨Ø§Ø±Øª Ø±Ø§ ÙˆØ§Ø±Ø¯ Ù†Ù…Ø§ÛŒÛŒØ¯.');
                return;
            }}
            const btn = document.getElementById('btnSubmitFrequency');
            if (btn) btn.disabled = true;
            try {{
                const res = await fetch('/api/frequencies/add', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json; charset=utf-8' }},
                    body: JSON.stringify({{ category: cat, title: title, text: text }})
                }});
                const data = await res.json();
                if (data.ok) {{
                    document.getElementById('freqNewTitle').value = '';
                    document.getElementById('freqNewText').value = '';
                    loadFrequenciesTable();
                }} else {{
                    showToast('Ø®Ø·Ø§ Ø¯Ø± Ø«Ø¨Øª Ø¹Ø¨Ø§Ø±Øª: ' + (data.error || 'Ù†Ø§Ø´Ù†Ø§Ø®ØªÙ‡'));
                }}
            }} catch (err) {{
                showToast('Ø®Ø·Ø§ÛŒ Ø§Ø±ØªØ¨Ø§Ø· Ø¨Ø§ Ø³Ø±ÙˆØ±: ' + err.message);
            }} finally {{
                if (btn) btn.disabled = false;
            }}
        }}

        async function deleteFrequencyItem(id) {{
            if (!id) return;
            if (!confirm('Ø¢ÛŒØ§ Ø§Ø² Ø­Ø°Ù Ø§ÛŒÙ† Ø¹Ø¨Ø§Ø±Øª ÙØ±Ú©Ø§Ù†Ø³ ÙØ±Ø§ÙˆØ§Ù†ÛŒ Ø§Ø·Ù…ÛŒÙ†Ø§Ù† Ø¯Ø§Ø±ÛŒØ¯ØŸ')) return;
            try {{
                const res = await fetch('/api/frequencies/delete', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json; charset=utf-8' }},
                    body: JSON.stringify({{ id: id }})
                }});
                const data = await res.json();
                if (data.ok) {{
                    loadFrequenciesTable();
                }} else {{
                    showToast('Ø®Ø·Ø§ Ø¯Ø± Ø­Ø°Ù Ø¹Ø¨Ø§Ø±Øª: ' + (data.error || 'Ù†Ø§Ø´Ù†Ø§Ø®ØªÙ‡'));
                }}
            }} catch (err) {{
                showToast('Ø®Ø·Ø§ÛŒ Ø§Ø±ØªØ¨Ø§Ø· Ø¨Ø§ Ø³Ø±ÙˆØ±: ' + err.message);
            }}
        }}

        function exportFrequenciesJSON() {{
            const link = document.createElement('a');
            link.href = '/api/frequencies/export';
            link.download = 'frequencies_backup.json';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }}

        async function handleImportFrequenciesFile(input) {{
            if (!input || !input.files || !input.files[0]) return;
            const file = input.files[0];
            try {{
                const text = await file.text();
                let parsed;
                try {{
                    parsed = JSON.parse(text);
                }} catch (e) {{
                    showToast('Ø®Ø·Ø§ Ø¯Ø± ØªØ­Ù„ÛŒÙ„ Ø³Ø§Ø®ØªØ§Ø± ÙØ§ÛŒÙ„ JSON: ' + e.message);
                    input.value = '';
                    return;
                }}
                if (!Array.isArray(parsed)) {{
                    showToast('Ù‚Ø§Ù„Ø¨ ÙØ§ÛŒÙ„ Ù†Ø§Ù…Ø¹ØªØ¨Ø± Ø§Ø³Øª. ÙØ§ÛŒÙ„ JSON Ø¨Ø§ÛŒØ¯ Ø´Ø§Ù…Ù„ Ø¢Ø±Ø§ÛŒÙ‡â€ŒØ§ÛŒ Ø§Ø² Ø§Ø´ÛŒØ§Ø¡ Ú©Ø§Ø±Øªâ€ŒÙ‡Ø§ÛŒ ÙØ±Ú©Ø§Ù†Ø³ Ø¨Ø§Ø´Ø¯.');
                    input.value = '';
                    return;
                }}
                if (!confirm(`Ø¢ÛŒØ§ Ø§Ø² Ø¨Ø§Ø±Ú¯Ø°Ø§Ø±ÛŒ Ùˆ Ø¨Ø§Ø²Ù†ÙˆÛŒØ³ÛŒ ${{parsed.length}} Ø¹Ø¨Ø§Ø±Øª ÙØ±Ú©Ø§Ù†Ø³ ÙØ±Ø§ÙˆØ§Ù†ÛŒ Ø§Ø·Ù…ÛŒÙ†Ø§Ù† Ø¯Ø§Ø±ÛŒØ¯ØŸ`)) {{
                    input.value = '';
                    return;
                }}
                const res = await fetch('/api/frequencies/import', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json; charset=utf-8' }},
                    body: JSON.stringify(parsed)
                }});
                const data = await res.json();
                if (data.ok) {{
                    showToast(`Ø¨Ø§Ù†Ú© ÙØ±Ú©Ø§Ù†Ø³ ÙØ±Ø§ÙˆØ§Ù†ÛŒ Ø¨Ø§ Ù…ÙˆÙÙ‚ÛŒØª Ø¨Ù‡â€ŒØ±ÙˆØ²Ø±Ø³Ø§Ù†ÛŒ Ø´Ø¯ (${{data.count}} Ø¹Ø¨Ø§Ø±Øª ÙØ¹Ø§Ù„).`);
                    loadFrequenciesTable();
                }} else {{
                    showToast('Ø®Ø·Ø§ Ø¯Ø± Ø¨Ø§Ø±Ú¯Ø°Ø§Ø±ÛŒ ÙØ§ÛŒÙ„: ' + (data.error || 'Ù†Ø§Ø´Ù†Ø§Ø®ØªÙ‡'));
                }}
            }} catch (err) {{
                showToast('Ø®Ø·Ø§ Ø¯Ø± Ù¾Ø±Ø¯Ø§Ø²Ø´ ÙØ§ÛŒÙ„: ' + err.message);
            }} finally {{
                input.value = '';
            }}
        }}

        // =========================================================================
        // Ù…Ø§Ú˜ÙˆÙ„ Ù…Ø¯ÛŒØ±ÛŒØª Ùˆ Ø´Ø®ØµÛŒâ€ŒØ³Ø§Ø²ÛŒ Ø¨ØµØ±ÛŒ Ú©ÛŒØ¨ÙˆØ±Ø¯ Ø±Ø¨Ø§Øªâ€ŒÙ‡Ø§ (Visual Keyboard Customizer)
        // Ú†ÛŒØ¯Ù…Ø§Ù† Ù¾ÙˆÛŒØ§ØŒ Ø¬Ø§Ø¨Ø¬Ø§ÛŒÛŒ Ø³Ø·Ø±ÛŒ Ùˆ Ø³ØªÙˆÙ†ÛŒ Ø¯Ú©Ù…Ù‡â€ŒÙ‡Ø§ Ùˆ Ù¾ÛŒØ´â€ŒÙ†Ù…Ø§ÛŒØ´ Ø¯Ø± Ù…ÙˆØ¨Ø§ÛŒÙ„
        // =========================================================================

        const DEFAULT_KEYBOARD_LAYOUT = [
            ["ðŸ›ï¸ Ø¯ÙˆØ±Ù‡â€ŒÙ‡Ø§ Ùˆ Ù…Ø­ØµÙˆÙ„Ø§Øª"],
            ["âœ¨ Ù†Ø´Ø§Ù†Ù‡ Ø§Ù…Ø±ÙˆØ² Ù…Ù†", "ðŸ’Ž Ø§Ø´ØªØ±Ø§Ú© Ù¾Ø±ÛŒÙ…ÛŒÙˆÙ…"],
            ["ðŸ“ Ø¯Ø§Ù†Ù„ÙˆØ¯Ù‡Ø§", "ðŸ‘¤ Ø­Ø³Ø§Ø¨ Ú©Ø§Ø±Ø¨Ø±ÛŒ"]
        ];

        const CANONICAL_KEYBOARD_ACTIONS = [
            {{ text: "âœ¨ Ù†Ø´Ø§Ù†Ù‡ Ø§Ù…Ø±ÙˆØ² Ù…Ù†", desc: "Ø¯Ø±ÛŒØ§ÙØª Ø¢ÛŒÙ‡ Ùˆ Ù†Ø´Ø§Ù†Ù‡ ØªØµØ§Ø¯ÙÛŒ Ø±ÙˆØ²" }},
            {{ text: "ðŸ’Ž Ø§Ø´ØªØ±Ø§Ú© Ù¾Ø±ÛŒÙ…ÛŒÙˆÙ…", desc: "Ø®Ø±ÛŒØ¯ Ùˆ ØªÙ…Ø¯ÛŒØ¯ Ø§Ø´ØªØ±Ø§Ú© Ù¾Ø±ÛŒÙ…ÛŒÙˆÙ… Ù…Ø§Ù‡Ø§Ù†Ù‡" }},
            {{ text: "ðŸ“ Ø¯Ø§Ù†Ù„ÙˆØ¯Ù‡Ø§", desc: "Ø¢Ø±Ø´ÛŒÙˆ Ø¯Ø§Ù†Ù„ÙˆØ¯Ù‡Ø§ÛŒ Ù‡Ø¯Ø§ÛŒØ§ÛŒ Ø³Ø§ÛŒØª" }},
            {{ text: "ðŸ›ï¸ Ø¯ÙˆØ±Ù‡â€ŒÙ‡Ø§ Ùˆ Ù…Ø­ØµÙˆÙ„Ø§Øª", desc: "ÙØ±ÙˆØ´Ú¯Ø§Ù‡ Ø¯ÙˆØ±Ù‡â€ŒÙ‡Ø§ Ùˆ ÙØ§ÛŒÙ„â€ŒÙ‡Ø§ÛŒ Ø¯Ø§Ù†Ù„ÙˆØ¯ÛŒ" }},
            {{ text: "ðŸŒŠ ÙØ±Ú©Ø§Ù†Ø³ ÙØ±Ø§ÙˆØ§Ù†ÛŒ", desc: "ÙˆØ±Ù‚â€ŒØ²Ù† Ø¹Ø¨Ø§Ø±Ø§Øª ØªØ§Ú©ÛŒØ¯ÛŒ Ùˆ ÙØ±Ú©Ø§Ù†Ø³ Ø±ÙˆØ²" }},
            {{ text: "ðŸ‘¤ Ø­Ø³Ø§Ø¨ Ú©Ø§Ø±Ø¨Ø±ÛŒ", desc: "Ù…Ø´Ø§Ù‡Ø¯Ù‡ Ø§Ù…ØªÛŒØ§Ø²Ø§ØªØŒ Ù¾Ù„Ù† Ù¾Ø±ÛŒÙ…ÛŒÙˆÙ… Ùˆ ÙˆØ¶Ø¹ÛŒØª Ø­Ø³Ø§Ø¨" }},
            {{ text: "ðŸ’¬ Ù¾Ø´ØªÛŒØ¨Ø§Ù†ÛŒ Ùˆ ØªÛŒÚ©Øª", desc: "Ø§Ø±ØªØ¨Ø§Ø· Ø¨Ø§ Ø§Ø¯Ù…ÛŒÙ† Ùˆ ØªÛŒÚ©Øª Ù¾Ø´ØªÛŒØ¨Ø§Ù†ÛŒ" }}
        ];

        let activeKeyboardLayout = JSON.parse(JSON.stringify(DEFAULT_KEYBOARD_LAYOUT));

        /**
         * Ø±Ø§Ù‡â€ŒØ§Ù†Ø¯Ø§Ø²ÛŒ Ø§ÙˆÙ„ÛŒÙ‡ Ú©ÛŒØ¨ÙˆØ±Ø¯ Ú©Ø³ØªÙˆÙ…Ø§ÛŒØ²Ø± Ø¨Ø§ Ø¯Ø§Ø¯Ù‡â€ŒÙ‡Ø§ÛŒ Ø°Ø®ÛŒØ±Ù‡â€ŒØ´Ø¯Ù‡ ÛŒØ§ Ù¾ÛŒØ´â€ŒÙØ±Ø¶
         * @param {{Array}} layout Ø¢Ø±Ø§ÛŒÙ‡ Ø¯ÙˆØ¨Ø¹Ø¯ÛŒ Ø­Ø§ÙˆÛŒ Ø³Ø·Ø±Ù‡Ø§ÛŒ Ú©ÛŒØ¨ÙˆØ±Ø¯
         */
        function initKeyboardCustomizer(layout) {{
            try {{
                if (Array.isArray(layout) && layout.length > 0) {{
                    activeKeyboardLayout = JSON.parse(JSON.stringify(layout));
                }} else {{
                    activeKeyboardLayout = JSON.parse(JSON.stringify(DEFAULT_KEYBOARD_LAYOUT));
                }}
                renderKeyboardCustomizer();
            }} catch (err) {{
                console.warn('initKeyboardCustomizer error:', err);
                activeKeyboardLayout = JSON.parse(JSON.stringify(DEFAULT_KEYBOARD_LAYOUT));
                renderKeyboardCustomizer();
            }}
        }}

        /**
         * Ø±Ù†Ø¯Ø± Ú©Ø§Ù…Ù„ ÙˆÛŒØ±Ø§ÛŒØ´Ú¯Ø± Ú©ÛŒØ¨ÙˆØ±Ø¯ Ùˆ Ù¾ÛŒØ´â€ŒÙ†Ù…Ø§ÛŒØ´ Ù…Ø§Ú©â€ŒØ¢Ù¾ Ù…ÙˆØ¨Ø§ÛŒÙ„
         */
        function renderKeyboardCustomizer() {{
            renderKeyboardPool();
            renderKeyboardRows();
            renderKeyboardMockPreview();
        }}

        /**
         * Ø±Ù†Ø¯Ø± Ú†ÛŒÙ¾â€ŒÙ‡Ø§ÛŒ Ø¯Ú©Ù…Ù‡â€ŒÙ‡Ø§ÛŒ Ù…Ø¬Ø§Ø² Ø³ÛŒØ³ØªÙ…
         */
        function renderKeyboardPool() {{
            const poolEl = document.getElementById('keyboardActionsPool');
            if (!poolEl) return;
            poolEl.innerHTML = CANONICAL_KEYBOARD_ACTIONS.map(function(action, idx) {{
                return '<button type="button" data-action-idx="' + idx + '" onclick="handleAddActionFromPool(this)" ' +
                    'class="theme-card-btn px-2.5 py-1 rounded-lg text-[11px] font-medium transition flex items-center gap-1.5 shadow-sm" ' +
                    'title="' + escapeHtml(action.desc) + '">' +
                    '<svg class="w-3 h-3 stroke-[2] text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">' +
                    '<path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" />' +
                    '</svg>' +
                    '<span>' + escapeHtml(action.text) + '</span>' +
                    '</button>';
            }}).join('');
        }}

        function handleAddActionFromPool(btn) {{
            const idx = parseInt(btn.getAttribute('data-action-idx') || '0', 10);
            if (CANONICAL_KEYBOARD_ACTIONS[idx]) {{
                addActionButtonToLayout(CANONICAL_KEYBOARD_ACTIONS[idx].text);
            }}
        }}

        /**
         * Ø±Ù†Ø¯Ø± Ø³Ø·Ø±Ù‡Ø§ÛŒ ÙˆÛŒØ±Ø§ÛŒØ´Ú¯Ø± Ú©ÛŒØ¨ÙˆØ±Ø¯ Ø¨Ø§ Ú©Ù†ØªØ±Ù„â€ŒÙ‡Ø§ÛŒ Ø¬Ø§Ø¨Ø¬Ø§ÛŒÛŒ
         */
        function renderKeyboardRows() {{
            const container = document.getElementById('keyboardRowsContainer');
            if (!container) return;

            if (!activeKeyboardLayout || activeKeyboardLayout.length === 0) {{
                container.innerHTML = '<div class="p-6 text-center rounded-xl border border-dashed text-slate-500 text-xs" style="border-color: var(--card-border);">' +
                    'Ú©ÛŒØ¨ÙˆØ±Ø¯ Ø¯Ø± Ø­Ø§Ù„ Ø­Ø§Ø¶Ø± Ø³Ø·Ø±ÛŒ Ù†Ø¯Ø§Ø±Ø¯. Ø§Ø² Ø¯Ú©Ù…Ù‡ Â«Ø§ÙØ²ÙˆØ¯Ù† Ø³Ø·Ø± Ø¬Ø¯ÛŒØ¯Â» Ø§Ø³ØªÙØ§Ø¯Ù‡ Ú©Ù†ÛŒØ¯.' +
                    '</div>';
                return;
            }}

            container.innerHTML = activeKeyboardLayout.map(function(row, rIdx) {{
                const rowButtonsHtml = row.map(function(btnText, cIdx) {{
                    const isLast = (cIdx === row.length - 1);
                    const isFirst = (cIdx === 0);
                    return '<div class="p-2 rounded-lg border flex items-center justify-between gap-1.5 shadow-sm" style="background: var(--input-bg); border-color: var(--border-color);">' +
                        '<input type="text" value="' + escapeHtml(btnText) + '" onchange="updateButtonText(' + rIdx + ', ' + cIdx + ', this.value)" ' +
                        'class="bg-transparent text-xs text-slate-100 font-medium flex-1 outline-none focus:text-cyan-300 transition">' +
                        '<div class="flex items-center gap-0.5 shrink-0">' +
                        '<button type="button" onclick="shiftKeyboardButton(' + rIdx + ', ' + cIdx + ', 1)" ' + (isLast ? 'disabled ' : '') +
                        'class="p-1 rounded text-slate-400 hover:text-slate-200 disabled:opacity-20 transition" title="Ø§Ù†ØªÙ‚Ø§Ù„ Ø¨Ù‡ Ú†Ù¾">' +
                        '<svg class="w-3 h-3 stroke-[2]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" /></svg>' +
                        '</button>' +
                        '<button type="button" onclick="shiftKeyboardButton(' + rIdx + ', ' + cIdx + ', -1)" ' + (isFirst ? 'disabled ' : '') +
                        'class="p-1 rounded text-slate-400 hover:text-slate-200 disabled:opacity-20 transition" title="Ø§Ù†ØªÙ‚Ø§Ù„ Ø¨Ù‡ Ø±Ø§Ø³Øª">' +
                        '<svg class="w-3 h-3 stroke-[2]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" /></svg>' +
                        '</button>' +
                        '<button type="button" onclick="deleteKeyboardButton(' + rIdx + ', ' + cIdx + ')" ' +
                        'class="p-1 rounded text-rose-400 hover:text-rose-300 transition" title="Ø­Ø°Ù Ø¯Ú©Ù…Ù‡">' +
                        '<svg class="w-3 h-3 stroke-[2]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M19.5 12h-15" /></svg>' +
                        '</button>' +
                        '</div>' +
                        '</div>';
                }}).join('');

                const isFirstRow = (rIdx === 0);
                const isLastRow = (rIdx === activeKeyboardLayout.length - 1);
                const colsClass = row.length === 1 ? 'grid-cols-1' : (row.length === 2 ? 'grid-cols-1 sm:grid-cols-2' : 'grid-cols-1 sm:grid-cols-3');

                return '<div class="p-3.5 rounded-xl border space-y-2.5 transition" style="background: var(--card-bg); border-color: var(--card-border);">' +
                    '<div class="flex items-center justify-between pb-2 border-b border-white/5 text-xs">' +
                    '<div class="flex items-center gap-2">' +
                    '<span class="font-mono text-cyan-400 font-bold">Ø³Ø·Ø± ' + (rIdx + 1) + '</span>' +
                    '<span class="text-[10px] text-slate-400 font-mono">(' + row.length + ' Ø¯Ú©Ù…Ù‡)</span>' +
                    '</div>' +
                    '<div class="flex items-center gap-1">' +
                    '<button type="button" onclick="moveKeyboardRow(' + rIdx + ', -1)" ' + (isFirstRow ? 'disabled ' : '') +
                    'class="p-1 rounded text-slate-400 hover:text-slate-200 disabled:opacity-30 disabled:cursor-not-allowed transition" title="Ø§Ù†ØªÙ‚Ø§Ù„ Ø³Ø·Ø± Ø¨Ù‡ Ø¨Ø§Ù„Ø§">' +
                    '<svg class="w-3.5 h-3.5 stroke-[2]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M4.5 15.75l7.5-7.5 7.5 7.5" /></svg>' +
                    '</button>' +
                    '<button type="button" onclick="moveKeyboardRow(' + rIdx + ', 1)" ' + (isLastRow ? 'disabled ' : '') +
                    'class="p-1 rounded text-slate-400 hover:text-slate-200 disabled:opacity-30 disabled:cursor-not-allowed transition" title="Ø§Ù†ØªÙ‚Ø§Ù„ Ø³Ø·Ø± Ø¨Ù‡ Ù¾Ø§ÛŒÛŒÙ†">' +
                    '<svg class="w-3.5 h-3.5 stroke-[2]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" /></svg>' +
                    '</button>' +
                    '<button type="button" onclick="removeKeyboardRow(' + rIdx + ')" ' +
                    'class="p-1 rounded text-rose-400 hover:text-rose-300 transition" title="Ø­Ø°Ù Ø§ÛŒÙ† Ø³Ø·Ø±">' +
                    '<svg class="w-3.5 h-3.5 stroke-[2]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>' +
                    '</button>' +
                    '</div>' +
                    '</div>' +
                    '<div class="grid ' + colsClass + ' gap-2">' +
                    rowButtonsHtml +
                    '</div>' +
                    '</div>';
            }}).join('');
        }}

        /**
         * Ø±Ù†Ø¯Ø± Ù¾ÛŒØ´â€ŒÙ†Ù…Ø§ÛŒØ´ Ø²Ù†Ø¯Ù‡ Ø¯Ø± Ù‚Ø§Ø¨ Ø´Ø¨ÛŒÙ‡â€ŒØ³Ø§Ø² Ù…ÙˆØ¨Ø§ÛŒÙ„
         */
        function renderKeyboardMockPreview() {{
            const preview = document.getElementById('mockKeyboardPreview');
            if (!preview) return;

            if (!activeKeyboardLayout || activeKeyboardLayout.length === 0) {{
                preview.innerHTML = '<div class="text-[10px] text-center text-slate-500 py-3">Ú©ÛŒØ¨ÙˆØ±Ø¯ Ø®Ø§Ù„ÛŒ Ø§Ø³Øª</div>';
                return;
            }}

            preview.innerHTML = activeKeyboardLayout.map(function(row) {{
                const btns = row.map(function(btn) {{
                    return '<div class="flex-1 py-2 px-1 rounded-xl text-center text-[10px] font-medium border truncate transition select-none shadow-sm" ' +
                        'style="background: var(--input-bg); border-color: var(--card-border); color: var(--text-main);">' +
                        escapeHtml(btn) +
                        '</div>';
                }}).join('');
                return '<div class="flex items-center gap-1.5 w-full">' + btns + '</div>';
            }}).join('');
        }}

        function addKeyboardRow() {{
            activeKeyboardLayout.push([]);
            renderKeyboardCustomizer();
        }}

        function removeKeyboardRow(rIdx) {{
            activeKeyboardLayout.splice(rIdx, 1);
            renderKeyboardCustomizer();
        }}

        function moveKeyboardRow(rIdx, dir) {{
            const targetIdx = rIdx + dir;
            if (targetIdx < 0 || targetIdx >= activeKeyboardLayout.length) return;
            const temp = activeKeyboardLayout[rIdx];
            activeKeyboardLayout[rIdx] = activeKeyboardLayout[targetIdx];
            activeKeyboardLayout[targetIdx] = temp;
            renderKeyboardCustomizer();
        }}

        function addActionButtonToLayout(btnText) {{
            if (activeKeyboardLayout.length === 0) {{
                activeKeyboardLayout.push([]);
            }}
            const lastRow = activeKeyboardLayout[activeKeyboardLayout.length - 1];
            if (lastRow.length >= 2) {{
                activeKeyboardLayout.push([btnText]);
            }} else {{
                lastRow.push(btnText);
            }}
            renderKeyboardCustomizer();
        }}

        function deleteKeyboardButton(rIdx, cIdx) {{
            if (activeKeyboardLayout[rIdx]) {{
                activeKeyboardLayout[rIdx].splice(cIdx, 1);
                if (activeKeyboardLayout[rIdx].length === 0 && activeKeyboardLayout.length > 1) {{
                    activeKeyboardLayout.splice(rIdx, 1);
                }}
                renderKeyboardCustomizer();
            }}
        }}

        function shiftKeyboardButton(rIdx, cIdx, dir) {{
            const row = activeKeyboardLayout[rIdx];
            if (!row) return;
            const targetIdx = cIdx + dir;
            if (targetIdx < 0 || targetIdx >= row.length) return;
            const temp = row[cIdx];
            row[cIdx] = row[targetIdx];
            row[targetIdx] = temp;
            renderKeyboardCustomizer();
        }}

        function updateButtonText(rIdx, cIdx, val) {{
            if (activeKeyboardLayout[rIdx] && activeKeyboardLayout[rIdx][cIdx] !== undefined) {{
                activeKeyboardLayout[rIdx][cIdx] = (val || '').trim();
                renderKeyboardMockPreview();
            }}
        }}

        function resetKeyboardLayoutToDefault() {{
            activeKeyboardLayout = JSON.parse(JSON.stringify(DEFAULT_KEYBOARD_LAYOUT));
            renderKeyboardCustomizer();
        }}

        function getKeyboardCustomizerLayout() {{
            return activeKeyboardLayout
                .map(function(row) {{ return row.filter(function(btn) {{ return btn && btn.trim(); }}); }})
                .filter(function(row) {{ return row.length > 0; }});
        }}

        async function saveKeyboardLayout() {{
            const btn = document.getElementById('btnSaveKeyboardLayout');
            const notice = document.getElementById('keyboardSaveNotice');
            if (btn) {{ btn.disabled = true; btn.innerText = 'Ø¯Ø± Ø­Ø§Ù„ Ø°Ø®ÛŒØ±Ù‡...'; }}
            try {{
                const layout = getKeyboardCustomizerLayout();
                let pwd = window.currentAdminPassword || sessionStorage.getItem('unfinit_admin_pwd') || '';
                const res = await fetch('/api/settings/save', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json; charset=utf-8' }},
                    body: JSON.stringify({{
                        password: pwd,
                        settings: {{
                            CUSTOM_KEYBOARD_LAYOUT: layout,
                            MAIN_KEYBOARD_LAYOUT: layout
                        }}
                    }})
                }});
                const data = await res.json();
                if (data.ok) {{
                    if (notice) {{
                        notice.classList.remove('hidden');
                        setTimeout(function() {{ notice.classList.add('hidden'); }}, 3500);
                    }}
                }} else {{
                    showToast('Ø®Ø·Ø§ Ø¯Ø± Ø°Ø®ÛŒØ±Ù‡ Ú©ÛŒØ¨ÙˆØ±Ø¯: ' + (data.error || 'Ù†Ø§Ø´Ù†Ø§Ø®ØªÙ‡'));
                }}
            }} catch (err) {{
                showToast('Ø®Ø·Ø§ Ø¯Ø± Ø§Ø±ØªØ¨Ø§Ø· Ø¨Ø§ Ø³Ø±ÙˆØ±: ' + err.message);
            }} finally {{
                if (btn) {{
                    btn.disabled = false;
                    btn.innerHTML = '<svg class="w-3.5 h-3.5 stroke-[2]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5" /></svg><span>Ø°Ø®ÛŒØ±Ù‡ Ú©ÛŒØ¨ÙˆØ±Ø¯</span>';
                }}
            }}
        }}

        // =========================================================================

                window.initKeyboardCustomizer = initKeyboardCustomizer;
                window.renderKeyboardCustomizer = renderKeyboardCustomizer;
                window.addKeyboardRow = addKeyboardRow;
                window.removeKeyboardRow = removeKeyboardRow;
                window.moveKeyboardRow = moveKeyboardRow;
                window.addActionButtonToLayout = addActionButtonToLayout;
                window.handleAddActionFromPool = handleAddActionFromPool;
                window.deleteKeyboardButton = deleteKeyboardButton;
                window.shiftKeyboardButton = shiftKeyboardButton;
                window.updateButtonText = updateButtonText;
                window.resetKeyboardLayoutToDefault = resetKeyboardLayoutToDefault;
                window.getKeyboardCustomizerLayout = getKeyboardCustomizerLayout;
                window.saveKeyboardLayout = saveKeyboardLayout;

                try {{ initKeyboardCustomizer(); }} catch (e) {{ console.warn('initKeyboardCustomizer startup notice:', e); }}

                window.clearHermesChat = clearHermesChat;
                window.sendPresetHermesPrompt = sendPresetHermesPrompt;
                window.handleSendHermes = handleSendHermes;
                window.escapeHtml = escapeHtml;
                window.uploadBannerFile = uploadBannerFile;
                window.handleLogoFileSelect = handleLogoFileSelect;
                window.uploadCustomLogo = uploadCustomLogo;
                window.loadSettings = loadSettings;
                window.loadFrequenciesTable = loadFrequenciesTable;
                window.openEditFrequencyModal = openEditFrequencyModal;
                window.closeEditFrequencyModal = closeEditFrequencyModal;
                window.submitEditFrequency = submitEditFrequency;
                window.submitAddNewFrequency = submitAddNewFrequency;
                window.deleteFrequencyItem = deleteFrequencyItem;
                window.exportFrequenciesJSON = exportFrequenciesJSON;
                window.handleImportFrequenciesFile = handleImportFrequenciesFile;
                window.handleAiProviderChange = handleAiProviderChange;
                window.updateAiProviderView = updateAiProviderView;
                window.populateSettingsForm = populateSettingsForm;
                window.handleExportSettings = handleExportSettings;
                window.handleExportContactsCSV = handleExportContactsCSV;
                window.handleImportSettingsFile = handleImportSettingsFile;
                window.handleSaveSettings = handleSaveSettings;
                window.clearLiveLogs = clearLiveLogs;
                window.copyAllLogs = copyAllLogs;
                window.fetchLogs = fetchLogs;
            }} catch (err) {{
                console.error('[UNFINIT AI & Settings Module Error]:', err);
            }}
        }})();
    

