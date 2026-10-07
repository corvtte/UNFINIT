window.showToast = function(msg, type='info') {
            const container = document.getElementById('toast-container') || (function() {
                const c = document.createElement('div');
                c.id = 'toast-container';
                c.className = 'fixed bottom-4 right-4 z-[9999] flex flex-col gap-2';
                document.body.appendChild(c);
                return c;
            })();
            
            const cleanMsg = msg.replace(/^[❌✅]/, '').trim();
            for (const el of container.children) {
                if (el.dataset.msg === cleanMsg) {
                    clearTimeout(el.toastTimer);
                    el.toastTimer = setTimeout(() => {
                        el.classList.add('translate-x-full', 'opacity-0');
                        setTimeout(() => el.remove(), 300);
                    }, 3500);
                    return;
                }
            }
            
            const t = document.createElement('div');
            t.dataset.msg = cleanMsg;
            const isErr = type === 'error' || msg.includes('❌') || msg.includes('خطا');
            const isOk = type === 'success' || msg.includes('✅') || msg.includes('موفق');
            const bg = isErr ? 'bg-rose-950/90 border-rose-800 text-rose-200' : (isOk ? 'bg-emerald-950/90 border-emerald-800 text-emerald-200' : 'bg-slate-800/90 border-slate-700 text-slate-200');
            const icon = isErr ? '<svg class="w-5 h-5 text-rose-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>' : 
                         (isOk ? '<svg class="w-5 h-5 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>' : 
                         '<svg class="w-5 h-5 text-sky-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>');
            t.className = `flex items-center gap-3 px-4 py-3 rounded-xl border backdrop-blur-md shadow-lg transform transition-all duration-300 translate-x-full opacity-0 ${bg}`;
            t.innerHTML = `${icon} <span class="text-sm font-bold font-sans" style="font-family: 'IRANSans', 'Vazirmatn', sans-serif;">${cleanMsg}</span>`;
            container.appendChild(t);
            requestAnimationFrame(() => {
                t.classList.remove('translate-x-full', 'opacity-0');
            });
            t.toastTimer = setTimeout(() => {
                t.classList.add('translate-x-full', 'opacity-0');
                setTimeout(() => t.remove(), 300);
            }, 3500);
        };

        window.COURSES_CACHE = {};
        window.coursesData = window.COURSES_CACHE;

        // Global Auth & State Access
        window.currentAdminPassword = window.currentAdminPassword || sessionStorage.getItem('unfinit_admin_pwd') || localStorage.getItem('unfinit_admin_pwd') || '';

        // =========================================================================
        // MODULE 1: NAVIGATION & TAB SWITCHING (Sandboxed IIFE)
        // =========================================================================
        (function initNavModule() {
            try {
                function updateCharCounter(inputId, counterId, maxLen) {
                    const input = document.getElementById(inputId);
                    const counter = document.getElementById(counterId);
                    if (!input || !counter) return;
                    const len = input.value.length;
                    if (len > maxLen) {
                        const diff = maxLen - len;
                        counter.innerText = diff + ' (بیش از سقف مجاز فاکتور بله)';
                        counter.className = 'text-[11px] text-rose-500 font-bold';
                    } else if (len === maxLen) {
                        counter.innerText = len + ' / ' + maxLen;
                        counter.className = 'text-[11px] text-rose-400 font-bold';
                    } else if (len >= maxLen * 0.85) {
                        counter.innerText = len + ' / ' + maxLen;
                        counter.className = 'text-[11px] text-amber-400 font-bold';
                    } else {
                        counter.innerText = len + ' / ' + maxLen;
                        counter.className = 'text-[11px] text-slate-400';
                    }
                }
                window.updateCharCounter = updateCharCounter;

                async function testCrawlerConnection(btn) {
                    const origHtml = btn.innerHTML;
                    btn.disabled = true;
                    btn.innerHTML = '<span class="flex items-center gap-2"><svg class="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg> در حال بررسی...</span>';
                    try {
                        const res = await fetch('/api/crawler/test-auth', { method: 'POST', body: '{}' });
                        const data = await res.json();
                        if (data.success) {
                            showToast('✅ ' + data.message);
                        } else {
                            showToast('❌ ' + data.message);
                        }
                    } catch (e) {
                        showToast('❌ خطای شبکه: ' + e.message);
                    } finally {
                        btn.disabled = false;
                        btn.innerHTML = origHtml;
                    }
                }

                function togglePasswordVisibility(inputId, btn) {
                    const inp = document.getElementById(inputId);
                    if (!inp) return;
                    const isMasked = (inp.type === 'password' || inp.style.webkitTextSecurity === 'disc');
                    const iconEye = '<svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/><path stroke-linecap="round" stroke-linejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/></svg>';
                    const iconEyeOff = '<svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21"/></svg>';
                    if (isMasked) {
                        inp.type = 'text';
                        inp.style.webkitTextSecurity = 'none';
                        btn.innerHTML = iconEyeOff;
                    } else {
                        if (inp.hasAttribute('data-token-field')) {
                            inp.type = 'text';
                            inp.style.webkitTextSecurity = 'disc';
                        } else {
                            inp.type = 'password';
                        }
                        btn.innerHTML = iconEye;
                    }
                }
                window.togglePasswordVisibility = togglePasswordVisibility;

                                window.openFeedAuthModal = function() {
                    const m = document.getElementById('feedAuthModal');
                    if (m) {
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
                    const resDiv = document.getElementById('quickFeedAuthResult');
                    if (resDiv) resDiv.classList.add('hidden');
                    try {
                        const cookie = document.getElementById('quick_FEED_AUTH_COOKIE').value;
                        const email = document.getElementById('quick_FEED_AUTH_EMAIL').value;
                        const pass = document.getElementById('quick_FEED_AUTH_PASSWORD').value;
                        
                        const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                        
                        const res = await fetch('/api/crawler/save-auth', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                'Authorization': 'Bearer ' + pwd,
                                'X-Admin-Password': pwd
                            },
                            body: JSON.stringify({ cookie: cookie, email: email, password: pass })
                        });
                        
                        const data = await res.json();
                        
                        if (data.success) {
                            showToast('✅ ' + (data.message || 'ورود موفقیت‌آمیز بود و نشست معتبر دریافت شد.'), 'success');
                            if (window.closeFeedAuthModal) window.closeFeedAuthModal();
                            const b = document.getElementById('crawlerStatusBadge');
                            if (b) {
                                b.className = 'px-2 py-1 rounded text-xs bg-emerald-950 text-emerald-400 border border-emerald-800 flex items-center gap-1.5 shadow-sm';
                                b.innerHTML = '<span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span> نشست فعال (ONLINE)';
                            }
                        } else {
                            if (resDiv) {
                                resDiv.classList.remove('hidden');
                                resDiv.innerHTML = '<span class="text-rose-500 font-bold">❌ خطا:</span> ' + (data.message || data.error || 'مشکلی رخ داد.');
                            }
                            showToast('خطا در ذخیره نشست', 'error');
                        }
                    } catch (err) {
                        console.error(err);
                        showToast('خطای شبکه در ارتباط با سرور', 'error');
                    } finally {
                        btn.innerHTML = orig;
                        btn.disabled = false;
                    }
                };

                                                window.toggleCrawlerAuth = async function(btn) {
                    const origHtml = btn.innerHTML;
                    const isLogout = origHtml.includes('خروج از حساب');
                    btn.disabled = true;
                    btn.innerHTML = '<span class="flex items-center gap-2"><svg class="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg> لطفا کمی صبر کنید...</span>';
                    
                    try {
                        if (isLogout) {
                            const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                            const res = await fetch('/api/crawler/logout', { method: 'POST', body: '{}', headers: {'Authorization': 'Bearer ' + pwd} });
                            const data = await res.json();
                            showToast('✅ خروج از حساب مرجع با موفقیت انجام شد.');
                            btn.className = 'flex-1 py-2 rounded-xl text-[13px] font-bold bg-emerald-600 hover:bg-emerald-500 text-white transition flex justify-center items-center gap-1.5';
                            btn.innerHTML = '<svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 16l-4-4m0 0l4-4m-4 4h14m-5 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h7a3 3 0 013 3v1"></path></svg><span>ورود به حساب مرجع</span>';
                            const b = document.getElementById('crawlerStatusBadge');
                            if (b) {
                                b.className = 'text-[10px] px-2 py-0.5 rounded-full bg-rose-600 text-white shadow-sm';
                                b.innerText = 'نشست مرجع قطع است (OFFLINE)';
                            }
                            const resDiv = document.getElementById('quickFeedAuthResult');
                            if (resDiv) resDiv.classList.add('hidden');
                        } else {
                            const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                            const payload = {
                                cookie: document.getElementById('quick_FEED_AUTH_COOKIE').value,
                                email: document.getElementById('quick_FEED_AUTH_EMAIL').value,
                                password: document.getElementById('quick_FEED_AUTH_PASSWORD').value
                            };
                            const saveRes = await fetch('/api/crawler/save-auth', { method: 'POST', headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + pwd }, body: JSON.stringify(payload) });
                            const saveData = await saveRes.json();
                            
                            if (saveData.success) {
                                const res = await fetch('/api/crawler/test-auth', { method: 'POST', body: JSON.stringify({force_login: true}), headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + pwd} });
                                const data = await res.json();
                                if (data.cookie) {
                                    document.getElementById('quick_FEED_AUTH_COOKIE').value = data.cookie;
                                    
                                    await fetch('/api/crawler/save-auth', { 
                                        method: 'POST', 
                                        headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + pwd }, 
                                        body: JSON.stringify({cookie: data.cookie, email: document.getElementById('quick_FEED_AUTH_EMAIL').value, password: document.getElementById('quick_FEED_AUTH_PASSWORD').value}) 
                                    });
                                }
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
                                        btn.className = 'flex-1 py-2 rounded-xl text-[13px] font-bold bg-rose-600 hover:bg-rose-500 text-white transition flex justify-center items-center gap-1.5';
                                        btn.innerHTML = '<svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"></path></svg><span>خروج از حساب</span>';
                                    } else {
                                        resDiv.innerHTML = '<span class="text-rose-500 font-bold">❌ ورود ناموفق:</span> ' + (data.message || data.error || 'بررسی کنید.');
                                        showToast('❌ ' + data.message, 'error');
                                        btn.innerHTML = origHtml;
                                    }
                                }
                            } else {
                                showToast('خطا در ذخیره فرم', 'error');
                                btn.innerHTML = origHtml;
                            }
                        }
                    } catch (e) {
                        showToast('❌ خطای شبکه: ' + e.message, 'error');
                        btn.innerHTML = origHtml;
                    } finally {
                        btn.disabled = false;
                    }
                };
                
                window.testCrawlerConnection = async function(btn) {
                    const origHtml = btn.innerHTML;
                    btn.disabled = true;
                    btn.innerHTML = '<span class="flex items-center gap-2"><svg class="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg> در حال بررسی...</span>';
                    try {
                        const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                        const res = await fetch('/api/crawler/test-auth', { method: 'POST', body: JSON.stringify({force_login: true}), headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + pwd} });
                                const data = await res.json();
                                if (data.cookie) {
                                    document.getElementById('quick_FEED_AUTH_COOKIE').value = data.cookie;
                                    
                                    await fetch('/api/crawler/save-auth', { 
                                        method: 'POST', 
                                        headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + pwd }, 
                                        body: JSON.stringify({cookie: data.cookie, email: document.getElementById('quick_FEED_AUTH_EMAIL').value, password: document.getElementById('quick_FEED_AUTH_PASSWORD').value}) 
                                    });
                                }
                        
                        const resDiv = document.getElementById('quickFeedAuthResult');
                        const toggleBtn = document.getElementById('btn_toggle_login_logout');
                        if (resDiv) resDiv.classList.remove('hidden');
                        
                        if (data.success) {
                            showToast('✅ ' + data.message);
                            if (resDiv) resDiv.innerHTML = '<span class="text-emerald-500 font-bold">✅ وضعیت:</span> ' + data.message;
                            const b = document.getElementById('crawlerStatusBadge');
                            if (b) {
                                b.className = 'text-[10px] px-2 py-0.5 rounded-full bg-emerald-600 text-white shadow-sm';
                                b.innerText = 'متصل به حساب مرجع (ONLINE)';
                            }
                            if (toggleBtn) {
                                toggleBtn.className = 'flex-1 py-2 rounded-xl text-[13px] font-bold bg-rose-600 hover:bg-rose-500 text-white transition flex justify-center items-center gap-1.5';
                                toggleBtn.innerHTML = '<svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"></path></svg><span>خروج از حساب</span>';
                            }
                        } else {
                            showToast('❌ ' + data.message, 'error');
                            if (resDiv) resDiv.innerHTML = '<span class="text-rose-500 font-bold">❌ خطا:</span> ' + data.message;
                            const b = document.getElementById('crawlerStatusBadge');
                            if (b) {
                                b.className = 'text-[10px] px-2 py-0.5 rounded-full bg-rose-600 text-white shadow-sm';
                                b.innerText = 'نشست مرجع قطع است (OFFLINE)';
                            }
                            if (toggleBtn) {
                                toggleBtn.className = 'flex-1 py-2 rounded-xl text-[13px] font-bold bg-emerald-600 hover:bg-emerald-500 text-white transition flex justify-center items-center gap-1.5';
                                toggleBtn.innerHTML = '<svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 16l-4-4m0 0l4-4m-4 4h14m-5 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h7a3 3 0 013 3v1"></path></svg><span>ورود به حساب مرجع</span>';
                            }
                        }
                    } catch (e) {
                        showToast('❌ خطای شبکه: ' + e.message, 'error');
                    } finally {
                        btn.innerHTML = origHtml;
                        btn.disabled = false;
                    }
                };
                
                async function handleLoginSubmit() {
                    const btn = document.getElementById('loginBtn');
                    const errMsg = document.getElementById('loginErrorMsg');
                    const pwd = document.getElementById('adminPasswordInput').value.trim();

                    if (errMsg) {
                        errMsg.style.display = 'none';
                        errMsg.innerText = '';
                    }

                    if (!pwd) {
                        if (errMsg) {
                            errMsg.innerText = '❌ لطفاً رمز عبور را وارد کنید.';
                            errMsg.style.display = 'block';
                        }
                        return;
                    }

                    if (btn) {
                        btn.disabled = true;
                        btn.innerHTML = '⏳ در حال بررسی...';
                    }

                    try {
                        const res = await fetch('/api/login', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json; charset=utf-8' },
                            body: JSON.stringify({ password: pwd })
                        });
                        const data = await res.json();
                        if (data && data.ok) {
                            localStorage.setItem('unfinit_auth_token', 'authenticated');
                            localStorage.setItem('unfinit_admin_pwd', pwd);
                            sessionStorage.setItem('unfinit_auth_token', 'authenticated');
                            sessionStorage.setItem('unfinit_admin_pwd', pwd);
                            window.currentAdminPassword = pwd;

                            const gate = document.getElementById('loginGate');
                            const app = document.getElementById('appMain');
                            if (gate) {
                                gate.style.display = 'none';
                                gate.classList.add('hidden');
                            }
                            if (app) {
                                app.style.removeProperty('display');
                                app.style.display = 'block';
                                app.classList.remove('hidden');
                            }
                            try {
                                const savedTab = localStorage.getItem('unfinit_active_tab') || 'studio';
                                if (typeof window.switchTab === 'function') {
                                    window.switchTab(savedTab);
                                }
                            } catch (e) {
                                console.warn('[Navigation] Tab switch notice:', e);
                            }
                        } else {
                            if (errMsg) {
                                errMsg.innerText = '❌ رمز عبور اشتباه است.';
                                errMsg.style.display = 'block';
                            }
                        }
                    } catch (err) {
                        if (errMsg) {
                            errMsg.innerText = '❌ خطای ارتباط با سرور: ' + (err.message || 'نامشخص');
                            errMsg.style.display = 'block';
                        }
                    } finally {
                        if (btn) {
                            btn.disabled = false;
                            btn.innerHTML = '<span>➔</span> ورود به پنل';
                        }
                    }
                }
                window.handleLoginSubmit = handleLoginSubmit;
                window.handleMainLogin = handleLoginSubmit;

                function handleLogout() {
                    sessionStorage.removeItem('unfinit_auth');
                    sessionStorage.removeItem('unfinit_auth_token');
                    sessionStorage.removeItem('unfinit_admin_pwd');
                    localStorage.removeItem('unfinit_auth');
                    localStorage.removeItem('unfinit_auth_token');
                    localStorage.removeItem('unfinit_admin_pwd');
                    location.reload();
                }
                window.handleLogout = handleLogout;

                function toggleSidebar(forceState) {
                    const sidebar = document.getElementById('mainSidebar');
                    const content = document.getElementById('contentWrapper');
                    const overlay = document.getElementById('drawerOverlay');
                    const isMobile = window.innerWidth < 768;

                    if (isMobile) {
                        if (!overlay || !sidebar) return;
                        const isClosed = sidebar.classList.contains('translate-x-full');
                        const shouldOpen = (typeof forceState === 'boolean') ? forceState : isClosed;
                        if (shouldOpen) {
                            overlay.classList.remove('hidden');
                            sidebar.classList.remove('translate-x-full');
                            sidebar.classList.add('translate-x-0');
                        } else {
                            overlay.classList.add('hidden');
                            sidebar.classList.remove('translate-x-0');
                            sidebar.classList.add('translate-x-full');
                        }
                    } else {
                        if (!sidebar) return;
                        const isCollapsed = sidebar.classList.contains('sidebar-collapsed');
                        const shouldCollapse = (typeof forceState === 'boolean') ? !forceState : !isCollapsed;
                        if (shouldCollapse) {
                            sidebar.classList.add('sidebar-collapsed');
                            if (content) content.classList.add('sidebar-collapsed');
                            try { localStorage.setItem('unfinit_sidebar_collapsed', 'true'); } catch (_) {}
                        } else {
                            sidebar.classList.remove('sidebar-collapsed');
                            if (content) content.classList.remove('sidebar-collapsed');
                            try { localStorage.setItem('unfinit_sidebar_collapsed', 'false'); } catch (_) {}
                        }
                    }
                }
                window.toggleSidebar = toggleSidebar;
                window.toggleMobileDrawer = toggleSidebar;
                window.toggleMobileMenu = toggleSidebar;

                function initSidebarState() {
                    try {
                        const isCollapsed = localStorage.getItem('unfinit_sidebar_collapsed') === 'true';
                        if (isCollapsed && window.innerWidth >= 768) {
                            const sidebar = document.getElementById('mainSidebar');
                            const content = document.getElementById('contentWrapper');
                            if (sidebar) sidebar.classList.add('sidebar-collapsed');
                            if (content) content.classList.add('sidebar-collapsed');
                        }
                    } catch (_) {}
                }
                window.initSidebarState = initSidebarState;

                const tabMeta = {
                    'dashboard': {
                        title: 'داشبورد و وضعیت زنده موتور UNFINIT',
                        desc: 'پایش لحظه‌ای اتصالات، آمار فایل‌ها، سقف ایمن بله و لاگ‌های زنده'
                    },
                    'downloads': {
                        title: 'فایل‌های دانلودی رایگان سایت',
                        desc: 'پایش خودکار صفحات سایت مرجع و پکیج‌بندی سرفصل‌های دوره‌ها'
                    },
                    'studio': {
                        title: 'استودیوی پیشرفته رسانه و متادیتا',
                        desc: 'ویرایشگر تگ صوتی ID3، پخش‌کننده ویوفرم صوتی و استودیوی وکتور SVG'
                    },
                    'courses': {
                        title: 'مدیریت دوره‌های آموزشی و درگاه پرداخت',
                        desc: 'تنظیم قیمت، فایل‌ها، سرفصل‌ها و درگاه مستقیم کارت به کارت بله'
                    },
                    'orders': {
                        title: 'سفارشات، تراکنش‌ها و کوپن‌های تخفیف',
                        desc: 'مدیریت فیش‌های بانکی، تأیید خودکار/دستی سفارشات و کدهای تخفیف'
                    },
                    'users': {
                        title: 'باشگاه مشتریان و شبکه وایرال رفرال',
                        desc: 'کاربران ثبت‌نام‌شده، موجودی کیف پول، سیستم دعوت دوستان و خروجی CSV مخاطبین'
                    },
                    'tokens': {
                        title: 'هاب هوش مصنوعی و مدیریت سکرت‌ها',
                        desc: 'پیکربندی هوش چندمدله (VyceAI, Nara, Gemini) و توکن‌های پلتفرم‌ها'
                    },
                    'frequencies': {
                        title: 'اشتراک پریمیوم و مدیریت محتوا',
                        desc: 'تنظیمات اشتراک ماهانه پریمیوم، شخصی‌سازی نشانه روزانه و کارت‌های فرکانس فراوانی'
                    },
                    'settings': {
                        title: 'تنظیمات سیستمی، دیتابیس و لاگ‌ها',
                        desc: 'پیکربندی سقف بله، پایگاه داده رمزنگاری‌شده AES-256 و کنسول لاگ'
                    }
                };

                function switchTab(tabId) {
                    try {
                        if (!tabId) tabId = 'dashboard';
                        let rawTab = tabId.startsWith('tab-') ? tabId.replace('tab-', '') : tabId;
                        const validTabs = ['dashboard', 'downloads', 'studio', 'courses', 'orders', 'users', 'tokens', 'frequencies', 'settings'];
                        if (!validTabs.includes(rawTab)) {
                            rawTab = 'dashboard';
                        }
                        const fullTabId = 'tab-' + rawTab;
                        try {
                            localStorage.setItem('unfinit_active_tab', rawTab);
                        } catch (_) {}

                        validTabs.forEach(id => {
                            const el = document.getElementById('tab-' + id);
                            if (el) el.classList.add('hidden');
                        });

                        // Update sidebar buttons
                        document.querySelectorAll('.sidebar-nav-btn').forEach(btn => {
                            btn.classList.remove('active');
                        });
                        const activeSidebarBtn = document.getElementById('s-btn-tab-' + rawTab);
                        if (activeSidebarBtn) {
                            activeSidebarBtn.classList.add('active');
                        }

                        // Update legacy tab-btn for compatibility
                        document.querySelectorAll('.tab-btn').forEach(btn => {
                            btn.classList.remove('active');
                            btn.classList.add('bg-slate-800/80', 'text-slate-300');
                        });
                        const targetBtn = document.getElementById('btn-tab-' + rawTab);
                        if (targetBtn) {
                            targetBtn.classList.add('active');
                            targetBtn.classList.remove('bg-slate-800/80', 'text-slate-300');
                        }
                        const mobileBtn = document.getElementById('m-btn-tab-' + rawTab);
                        if (mobileBtn) {
                            mobileBtn.classList.add('active');
                            mobileBtn.classList.remove('bg-slate-800/80', 'text-slate-300');
                        }

                        // Update Mobile Bottom Nav Active State
                        const bottomNav = document.getElementById('mobileBottomNav');
                        if (bottomNav) {
                            bottomNav.querySelectorAll('[data-tab]').forEach(btn => {
                                btn.classList.remove('active', 'text-cyan-400');
                                btn.classList.add('text-slate-400');
                            });
                            const activeBottomBtn = bottomNav.querySelector(`[data-tab="${rawTab}"]`);
                            if (activeBottomBtn) {
                                activeBottomBtn.classList.add('active', 'text-cyan-400');
                                activeBottomBtn.classList.remove('text-slate-400');
                            }
                        }

                        const targetTab = document.getElementById(fullTabId);
                        if (targetTab) {
                            targetTab.classList.remove('hidden');
                        }

                        const titleEl = document.getElementById('currentTabTitle');
                        const descEl = document.getElementById('currentTabDesc');
                        if (titleEl && tabMeta[rawTab]) titleEl.innerText = tabMeta[rawTab].title;
                        if (descEl && tabMeta[rawTab]) descEl.innerText = tabMeta[rawTab].desc;

                        if (rawTab === 'dashboard') {
                            if (typeof window.loadDashboardData === 'function') window.loadDashboardData();
                        }
                        if (rawTab === 'users') {
                            if (typeof window.loadUsersData === 'function') window.loadUsersData();
                        }
                        if (rawTab === 'frequencies') {
                            if (typeof window.loadVipSettings === 'function') window.loadVipSettings();
                            if (typeof window.loadFrequenciesTable === 'function') window.loadFrequenciesTable();
                        }
                        if (rawTab === 'settings' || rawTab === 'tokens') {
                            if (typeof window.loadSettings === 'function') window.loadSettings();
                            if (typeof window.loadFrequenciesTable === 'function') window.loadFrequenciesTable();
                        }
                        if (rawTab === 'courses') {
                            if (typeof window.loadStoreAnalytics === 'function') window.loadStoreAnalytics();
                        }
                        if (rawTab === 'orders') {
                            if (typeof window.loadStoreOrders === 'function') window.loadStoreOrders();
                            if (typeof window.loadStoreCoupons === 'function') window.loadStoreCoupons();
                            if (typeof window.loadStoreAnalytics === 'function') window.loadStoreAnalytics();
                        }
                        if (rawTab === 'downloads') {
                            if (typeof window.lazyLoadDownloadsFeed === 'function') window.lazyLoadDownloadsFeed();
                        }
                    } catch (err) {
                        console.error('[UNFINIT Navigation Module Error] switchTab error:', err);
                    }
                }
                window.switchTab = switchTab;

                window.downloadsFeedLoaded = false;
                window.lazyLoadDownloadsFeed = function() {
                    if (!window.downloadsFeedLoaded) {
                        window.downloadsFeedLoaded = true;
                        if (typeof window.fetchFeedDownloads === 'function') window.fetchFeedDownloads(false);
                        if (typeof window.loadFeedCategories === 'function') window.loadFeedCategories();
                    }
                };

                let drawerAllLines = [];

                function filterDrawerLogs() {
                    const q = (document.getElementById('drawerLogSearch')?.value || '').toLowerCase().trim();
                    const streamBox = document.getElementById('dashboardRecentLogs');
                    if (!streamBox) return;
                    if (!q) {
                        streamBox.innerText = drawerAllLines.slice(-30).join('\n') || '// لاگی برای نمایش موجود نیست.';
                    } else {
                        const filtered = drawerAllLines.filter(l => l.toLowerCase().includes(q));
                        streamBox.innerText = filtered.join('\n') || '// موردی یافت نشد.';
                    }
                    const autoScroll = document.getElementById('drawerAutoScroll');
                    if (!autoScroll || autoScroll.checked) {
                        streamBox.scrollTop = streamBox.scrollHeight;
                    }
                }
                window.filterDrawerLogs = filterDrawerLogs;

                async function copyDrawerLogs() {
                    const streamBox = document.getElementById('dashboardRecentLogs');
                    if (!streamBox) return;
                    try {
                        await navigator.clipboard.writeText(streamBox.innerText);
                        const btn = document.getElementById('drawerCopyBtn');
                        if (btn) {
                            const orig = btn.innerHTML;
                            btn.innerHTML = '<span class="text-emerald-400 font-sans text-xs">کپی شد ✓</span>';
                            setTimeout(() => { btn.innerHTML = orig; }, 2000);
                        }
                    } catch (e) {
                        showToast('خطا در کپی لاگ‌ها: ' + e.message);
                    }
                }
                window.copyDrawerLogs = copyDrawerLogs;

                async function loadDashboardData() {
                    try {
                        const streamBox = document.getElementById('dashboardRecentLogs');
                        const mainLogs = document.getElementById('logContainer');
                        if (streamBox && mainLogs && mainLogs.innerText.trim()) {
                            const lines = mainLogs.innerText.trim().split('\n').filter(Boolean);
                            drawerAllLines = lines;
                            const q = (document.getElementById('drawerLogSearch')?.value || '').trim();
                            if (!q) {
                                const recent = lines.slice(-30).join('\n');
                                if (recent) streamBox.innerText = recent;
                            }
                            const autoScroll = document.getElementById('drawerAutoScroll');
                            if (!autoScroll || autoScroll.checked) {
                                streamBox.scrollTop = streamBox.scrollHeight;
                            }
                            const prev = document.getElementById('dashboardLatestLogPreview');
                            if (prev && lines.length > 0) {
                                prev.textContent = lines[lines.length - 1];
                            }
                        }
                        const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                        const res = await fetch('/api/store/analytics', {
                            headers: { 'Authorization': 'Bearer ' + pwd, 'X-Admin-Password': pwd }
                        });
                        if (res.ok) {
                            const data = await res.json();
                            if (data.active_drops !== undefined) {
                                const el = document.getElementById('dashTotalDrops');
                                if (el) el.innerText = data.active_drops;
                            }
                        }
                    } catch (e) {
                        console.warn('loadDashboardData error:', e);
                    }
                }
                window.loadDashboardData = loadDashboardData;

                function toggleLogsDrawer(show) {
                    const drawer = document.getElementById('logsDrawer');
                    const overlay = document.getElementById('logsDrawerOverlay');
                    if (!drawer) return;
                    const isHidden = drawer.classList.contains('-translate-x-full');
                    const shouldShow = (typeof show === 'boolean') ? show : isHidden;
                    if (shouldShow) {
                        drawer.classList.remove('-translate-x-full');
                        if (overlay) overlay.classList.remove('hidden');
                        if (typeof loadDashboardData === 'function') loadDashboardData();
                    } else {
                        drawer.classList.add('-translate-x-full');
                        if (overlay) overlay.classList.add('hidden');
                    }
                }
                window.toggleLogsDrawer = toggleLogsDrawer;

                function openBaleCapModal() {
                    const m = document.getElementById('modalBaleCapSettings');
                    if (m) m.classList.remove('hidden');
                    calcEffectiveCap();
                }
                window.openBaleCapModal = openBaleCapModal;

                function closeBaleCapModal() {
                    const m = document.getElementById('modalBaleCapSettings');
                    if (m) m.classList.add('hidden');
                }
                window.closeBaleCapModal = closeBaleCapModal;

                function calcEffectiveCap() {
                    const cInput = document.getElementById('baleCapInput');
                    const bInput = document.getElementById('baleBufferInput');
                    const c = parseFloat(cInput ? cInput.value : 50.0) || 50.0;
                    const b = parseFloat(bInput ? bInput.value : 3.0) || 3.0;
                    const eff = (c * (1.0 - (b / 100.0))).toFixed(2);
                    const el = document.getElementById('previewEffectiveCap');
                    if (el) el.textContent = eff;
                }
                window.calcEffectiveCap = calcEffectiveCap;

                async function submitBaleCapSettings(e) {
                    e.preventDefault();
                    const cInput = document.getElementById('baleCapInput');
                    const bInput = document.getElementById('baleBufferInput');
                    const c = parseFloat(cInput ? cInput.value : 50.0);
                    const b = parseFloat(bInput ? bInput.value : 3.0);
                    if (isNaN(c) || c <= 0 || c > 50) {
                        showToast('سقف مجاز باید عددی بین ۱ تا ۵۰ مگابایت باشد.');
                        return;
                    }
                    if (isNaN(b) || b < 0 || b > 15) {
                        showToast('بافر امنیتی باید بین ۰ تا ۱۵ درصد باشد.');
                        return;
                    }
                    const eff = (c * (1.0 - (b / 100.0))).toFixed(2);
                    const btn = document.getElementById('btnSaveBaleCap');
                    if (btn) {
                        btn.disabled = true;
                        btn.innerHTML = '<span>در حال ذخیره...</span>';
                    }
                    try {
                        const pwd = window.currentAdminPassword || sessionStorage.getItem('unfinit_admin_pwd') || localStorage.getItem('unfinit_admin_pwd') || '';
                        const res = await fetch('/api/settings/save', {
                            method: 'POST',
                            credentials: 'same-origin',
                            headers: {
                                'Content-Type': 'application/json; charset=utf-8',
                                'Authorization': 'Bearer ' + pwd,
                                'X-Admin-Password': pwd
                            },
                            body: JSON.stringify({
                                password: pwd,
                                settings: {
                                    bale_max_file_size_mb: c,
                                    bale_safety_buffer_percent: b,
                                    MAX_SAFE_BALE_SIZE_MB: c
                                },
                                bale_max_file_size_mb: c,
                                bale_safety_buffer_percent: b
                            })
                        });
                        const data = await res.json();
                        if (data.ok) {
                            const d1 = document.getElementById('baleCardSafeSize');
                            const d2 = document.getElementById('baleCardBuffer');
                            const d3 = document.getElementById('baleCardEffective');
                            const d4 = document.getElementById('dashBaleSafeSize');
                            if (d1) d1.textContent = c.toFixed(1) + ' MB';
                            if (d2) d2.textContent = b.toFixed(1) + '%';
                            if (d3) d3.textContent = eff + ' MB';
                            if (d4) d4.textContent = c.toFixed(1) + ' MB';
                            closeBaleCapModal();
                        } else {
                            showToast('خطا در ذخیره تنظیمات: ' + (data.error || 'عملیات ناموفق بود'));
                        }
                    } catch (err) {
                        showToast('خطا در برقراری ارتباط: ' + err.message);
                    } finally {
                        if (btn) {
                            btn.disabled = false;
                            btn.innerHTML = '<span>ذخیره تنظیمات</span>';
                        }
                    }
                }
                window.submitBaleCapSettings = submitBaleCapSettings;
                window.editBaleSafeLimit = openBaleCapModal;

                /**
                 * تابع قطع ارتباط و حذف نشست پلتفرم‌ها به صورت غیرهمگام (AJAX)
                 * طبق قانون اکشن‌های بدون رفرش (Zero Page-Reload Principle)، المان‌های DOM را بدون بارگذاری مجدد صفحه به‌روزرسانی می‌کند.
                 * @param {string} platform - نام پلتفرم ('soroush' یا 'rubika')
                 */
                async function disconnectSession(platform) {
                    const platName = (platform === 'soroush' ? 'سروش‌پلاس' : 'روبیکا');
                    if (!confirm('آیا از قطع اتصال و حذف امن سشن ' + platName + ' اطمینان دارید؟')) return;
                    try {
                        const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                        const res = await fetch('/api/sessions/disconnect', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json; charset=utf-8',
                                'Authorization': 'Bearer ' + pwd,
                                'X-Admin-Password': pwd
                            },
                            body: JSON.stringify({ platform: platform })
                        });
                        const data = await res.json();
                        if (data.ok) {
                            if (platform === 'soroush') {
                                const b = document.getElementById('soroushStatusBadge');
                                if (b) {
                                    b.className = 'px-2 py-0.5 rounded text-xs font-bold bg-amber-950 text-amber-400 border border-amber-800';
                                    b.textContent = 'نیازمند راه‌اندازی';
                                }
                                const pEl = document.getElementById('soroushPhoneDisplay');
                                if (pEl) pEl.textContent = 'عدم اتصال';
                                const btnBox = document.getElementById('soroushBtnContainer');
                                if (btnBox) {
                                    btnBox.innerHTML = '<button type="button" onclick="openSoroushLoginModal()" class="w-full py-1.5 px-2 rounded-lg theme-accent-btn text-[11px] font-bold transition flex items-center justify-center gap-1.5"><svg class="w-3.5 h-3.5 stroke-[1.75]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M15.75 5.25a3 3 0 013 3m3 0a6 6 0 01-7.029 5.912c-.563-.097-1.159.026-1.563.43L10.5 17.25H8.25v2.25H6v2.25H2.25v-2.818c0-.597.237-1.17.659-1.591l6.499-6.499c.404-.404.527-1 .43-1.563A6 6 0 1121.75 8.25z" /></svg><span>ورود به حساب سروش‌پلاس</span></button>';
                                }
                            } else if (platform === 'rubika') {
                                const b = document.getElementById('rubikaStatusBadge');
                                if (b) {
                                    b.className = 'px-2 py-0.5 rounded text-xs font-bold bg-amber-950 text-amber-400 border border-amber-800';
                                    b.textContent = 'REQUIRE_AUTH';
                                }
                                const pEl = document.getElementById('rubikaPhoneDisplay');
                                if (pEl) pEl.textContent = 'بدون شماره';
                                const btnBox = document.getElementById('rubikaBtnContainer');
                                if (btnBox) {
                                    btnBox.innerHTML = '<p class="text-[11px] text-amber-400 text-center py-1">سشن غیرفعال است</p>';
                                }
                            }
                            showToast('✅ سشن ' + platName + ' با موفقیت قطع و از سرور پاکسازی شد.');
                        } else {
                            showToast('❌ خطا: ' + (data.error || 'عملیات ناموفق بود'));
                        }
                    } catch (e) {
                        showToast('❌ خطای ارتباط با سرور: ' + e.message);
                    }
                }
                window.disconnectSession = disconnectSession;

                function switchUserSubTab(subTab) {
                    const listSec = document.getElementById('userSubTabContentList');
                    const refSec = document.getElementById('userSubTabContentRef');
                    const btnList = document.getElementById('btnUserSubTabList');
                    const btnRef = document.getElementById('btnUserSubTabRef');
                    if (subTab === 'referrals') {
                        if (listSec) listSec.classList.add('hidden');
                        if (refSec) refSec.classList.remove('hidden');
                        if (btnRef) {
                            btnRef.className = 'px-4 py-2 rounded-xl text-xs font-bold transition flex items-center gap-2 theme-accent-btn';
                        }
                        if (btnList) {
                            btnList.className = 'px-4 py-2 rounded-xl text-xs font-bold transition flex items-center gap-2 theme-card-btn text-slate-300';
                        }
                    } else {
                        if (refSec) refSec.classList.add('hidden');
                        if (listSec) listSec.classList.remove('hidden');
                        if (btnList) {
                            btnList.className = 'px-4 py-2 rounded-xl text-xs font-bold transition flex items-center gap-2 theme-accent-btn';
                        }
                        if (btnRef) {
                            btnRef.className = 'px-4 py-2 rounded-xl text-xs font-bold transition flex items-center gap-2 theme-card-btn text-slate-300';
                        }
                    }
                }
                window.switchUserSubTab = switchUserSubTab;

                let pendingSoroushPhone = '';

                function openSoroushLoginModal() {
                    const modal = document.getElementById('soroushLoginModal');
                    if (modal) {
                        modal.classList.remove('hidden');
                        resetSoroushLoginForm();
                    }
                }
                function closeSoroushLoginModal() {
                    const modal = document.getElementById('soroushLoginModal');
                    if (modal) modal.classList.add('hidden');
                }
                function switchSoroushTab(tab) {
                    const smsPhone = document.getElementById('soroushStepPhone');
                    const smsCode = document.getElementById('soroushStepCode');
                    const manStep = document.getElementById('soroushStepManual');
                    const btnSms = document.getElementById('tabBtnSoroushSms');
                    const btnMan = document.getElementById('tabBtnSoroushManual');
                    const errBox = document.getElementById('soroushLoginError');
                    if (errBox) errBox.classList.add('hidden');
                    if (tab === 'manual') {
                        if (smsPhone) smsPhone.classList.add('hidden');
                        if (smsCode) smsCode.classList.add('hidden');
                        if (manStep) manStep.classList.remove('hidden');
                        if (btnMan) { btnMan.className = 'flex-1 py-1.5 rounded-lg text-xs font-bold transition theme-card-btn'; }
                        if (btnSms) { btnSms.className = 'flex-1 py-1.5 rounded-lg text-xs font-bold text-slate-400 hover:text-white transition'; }
                    } else {
                        if (manStep) manStep.classList.add('hidden');
                        if (smsPhone) smsPhone.classList.remove('hidden');
                        if (smsCode) smsCode.classList.add('hidden');
                        if (btnSms) { btnSms.className = 'flex-1 py-1.5 rounded-lg text-xs font-bold transition theme-card-btn'; }
                        if (btnMan) { btnMan.className = 'flex-1 py-1.5 rounded-lg text-xs font-bold text-slate-400 hover:text-white transition'; }
                    }
                }
                function resetSoroushLoginForm() {
                    switchSoroushTab('sms');
                    const errBox = document.getElementById('soroushLoginError');
                    if (errBox) { errBox.classList.add('hidden'); errBox.textContent = ''; }
                    const phoneInput = document.getElementById('soroushPhoneInput');
                    if (phoneInput) phoneInput.value = '';
                    const codeInput = document.getElementById('soroushCodeInput');
                    if (codeInput) codeInput.value = '';
                    const manTokInput = document.getElementById('soroushManualTokenInput');
                    if (manTokInput) manTokInput.value = '';
                    const manPhInput = document.getElementById('soroushManualPhoneInput');
                    if (manPhInput) manPhInput.value = '';
                }
                async function submitSoroushPhone() {
                    const phoneInput = document.getElementById('soroushPhoneInput');
                    const phone = phoneInput ? phoneInput.value.trim() : '';
                    if (!phone || phone.length < 10) {
                        showToast('شماره تلفن نامعتبر است.');
                        return;
                    }
                    const btn = document.getElementById('btnSoroushSendCode');
                    const errBox = document.getElementById('soroushLoginError');
                    if (btn) { btn.disabled = true; btn.textContent = 'در حال ارسال درخواست...'; }
                    if (errBox) errBox.classList.add('hidden');
                    try {
                        const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                        const res = await fetch('/api/soroush/login/request', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json; charset=utf-8',
                                'Authorization': 'Bearer ' + pwd,
                                'X-Admin-Password': pwd
                            },
                            body: JSON.stringify({ phone: phone })
                        });
                        const data = await res.json();
                        if (data.ok) {
                            pendingSoroushPhone = phone;
                            const disp = document.getElementById('soroushTargetPhoneDisplay');
                            if (disp) disp.textContent = phone;
                            const pStep = document.getElementById('soroushStepPhone');
                            const cStep = document.getElementById('soroushStepCode');
                            if (pStep) pStep.classList.add('hidden');
                            if (cStep) cStep.classList.remove('hidden');
                        } else {
                            if (errBox) {
                                errBox.textContent = data.error || 'خطا در ارسال کد';
                                errBox.classList.remove('hidden');
                            } else {
                                showToast(data.error || 'خطا در ارسال کد');
                            }
                        }
                    } catch (e) {
                        showToast('خطا: ' + e.message);
                    } finally {
                        if (btn) { btn.disabled = false; btn.textContent = 'دریافت کد تایید پیامکی'; }
                    }
                }
                /**
                 * ارسال کد تایید پیامکی و تایید نهایی سشن سروش‌پلاس
                 * المان‌های کارت داشبورد را بدون بارگذاری مجدد صفحه به‌روزرسانی می‌کند.
                 */
                async function submitSoroushCode() {
                    const codeInput = document.getElementById('soroushCodeInput');
                    const code = codeInput ? codeInput.value.trim() : '';
                    if (!code) {
                        showToast('لطفاً کد تایید را وارد نمایید.');
                        return;
                    }
                    const btn = document.getElementById('btnSoroushVerifyCode');
                    const errBox = document.getElementById('soroushLoginError');
                    if (btn) { btn.disabled = true; btn.textContent = 'در حال تایید...'; }
                    if (errBox) errBox.classList.add('hidden');
                    try {
                        const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                        const res = await fetch('/api/soroush/login/verify', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json; charset=utf-8',
                                'Authorization': 'Bearer ' + pwd,
                                'X-Admin-Password': pwd
                            },
                            body: JSON.stringify({ phone: pendingSoroushPhone, code: code })
                        });
                        const data = await res.json();
                        if (data.ok) {
                            const b = document.getElementById('soroushStatusBadge');
                            if (b) {
                                b.className = 'px-2 py-0.5 rounded text-xs font-bold bg-emerald-950 text-emerald-400 border border-emerald-800';
                                b.textContent = 'ONLINE';
                            }
                            const pEl = document.getElementById('soroushPhoneDisplay');
                            if (pEl) pEl.textContent = data.masked_phone || pendingSoroushPhone || 'متصل';
                            const btnBox = document.getElementById('soroushBtnContainer');
                            if (btnBox) {
                                const dcBtn = document.createElement('button');
                                dcBtn.type = 'button';
                                dcBtn.onclick = function() { disconnectSession('soroush'); };
                                dcBtn.className = 'w-full py-1.5 px-2 rounded-lg bg-rose-950/60 hover:bg-rose-900/80 text-rose-300 border border-rose-800 text-[11px] font-bold transition flex items-center justify-center gap-1.5';
                                dcBtn.innerHTML = '<svg class="w-3.5 h-3.5 stroke-[1.75]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M5.636 5.636a9 9 0 1012.728 0M12 3v9" /></svg><span>قطع اتصال / خروج</span>';
                                btnBox.innerHTML = '';
                                btnBox.appendChild(dcBtn);
                            }
                            showToast('ورود با موفقیت انجام شد و سشن سروش‌پلاس با استاندارد AES-256 رمزنگاری و فعال گردید.');
                            closeSoroushLoginModal();
                        } else {
                            if (errBox) {
                                errBox.textContent = data.error || 'کد تایید اشتباه است.';
                                errBox.classList.remove('hidden');
                            } else {
                                showToast(data.error || 'کد تایید اشتباه است.');
                            }
                        }
                    } catch (e) {
                        showToast('خطا: ' + e.message);
                    } finally {
                        if (btn) { btn.disabled = false; btn.textContent = 'تایید و فعال‌سازی سشن امن'; }
                    }
                }

                /**
                 * ثبت دستی سشن سروش‌پلاس (توکن یا آبجکت JSON کامل account1)
                 * پس از رمزنگاری و اعتبارسنجی سرور، کارت را در DOM بدون رفرش به‌روز می‌کند.
                 */
                async function submitSoroushManualToken() {
                    const tokInput = document.getElementById('soroushManualTokenInput');
                    const phInput = document.getElementById('soroushManualPhoneInput');
                    const token = tokInput ? tokInput.value.trim() : '';
                    const phone = phInput ? phInput.value.trim() : '';
                    if (!token) {
                        showToast('توکن نشست الزامی است.');
                        return;
                    }
                    const btn = document.getElementById('btnSoroushManualSubmit');
                    const errBox = document.getElementById('soroushLoginError');
                    if (btn) { btn.disabled = true; btn.textContent = 'در حال ذخیره‌سازی...'; }
                    if (errBox) errBox.classList.add('hidden');
                    try {
                        const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                        const res = await fetch('/api/soroush/login/manual', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json; charset=utf-8',
                                'Authorization': 'Bearer ' + pwd,
                                'X-Admin-Password': pwd
                            },
                            body: JSON.stringify({ token: token, phone: phone })
                        });
                        const data = await res.json();
                        if (data.ok) {
                            const b = document.getElementById('soroushStatusBadge');
                            if (b) {
                                b.className = 'px-2 py-0.5 rounded text-xs font-bold bg-emerald-950 text-emerald-400 border border-emerald-800';
                                b.textContent = 'ONLINE';
                            }
                            const pEl = document.getElementById('soroushPhoneDisplay');
                            if (pEl) pEl.textContent = data.masked_phone || phone || 'متصل';
                            const btnBox = document.getElementById('soroushBtnContainer');
                            if (btnBox) {
                                const dcBtn = document.createElement('button');
                                dcBtn.type = 'button';
                                dcBtn.onclick = function() { disconnectSession('soroush'); };
                                dcBtn.className = 'w-full py-1.5 px-2 rounded-lg bg-rose-950/60 hover:bg-rose-900/80 text-rose-300 border border-rose-800 text-[11px] font-bold transition flex items-center justify-center gap-1.5';
                                dcBtn.innerHTML = '<svg class="w-3.5 h-3.5 stroke-[1.75]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M5.636 5.636a9 9 0 1012.728 0M12 3v9" /></svg><span>قطع اتصال / خروج</span>';
                                btnBox.innerHTML = '';
                                btnBox.appendChild(dcBtn);
                            }
                            showToast('سشن سروش‌پلاس با موفقیت ثبت و فعال شد.');
                            closeSoroushLoginModal();
                        } else {
                            if (errBox) {
                                errBox.textContent = data.error || 'خطا در ثبت توکن';
                                errBox.classList.remove('hidden');
                            } else {
                                showToast(data.error || 'خطا در ثبت توکن');
                            }
                        }
                    } catch (e) {
                        showToast('خطا: ' + e.message);
                    } finally {
                        if (btn) { btn.disabled = false; btn.textContent = 'ذخیره مستقیم توکن و فعال‌سازی سشن'; }
                    }
                }

                window.openSoroushLoginModal = openSoroushLoginModal;
                window.closeSoroushLoginModal = closeSoroushLoginModal;
                window.switchSoroushTab = switchSoroushTab;
                window.resetSoroushLoginForm = resetSoroushLoginForm;
                window.submitSoroushPhone = submitSoroushPhone;
                window.submitSoroushCode = submitSoroushCode;
                window.submitSoroushManualToken = submitSoroushManualToken;

                let allLoadedUsers = [];

                async function loadUsersData() {
                    const tbody = document.getElementById('usersTableBody');
                    if (!tbody) return;
                    tbody.innerHTML = '<tr><td colspan="8" class="p-6 text-center text-slate-400 font-sans">در حال دریافت فهرست اعضا و خریداران...</td></tr>';
                    try {
                        const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                        const res = await fetch('/api/users', {
                            headers: { 'Authorization': 'Bearer ' + pwd, 'X-Admin-Password': pwd }
                        });
                        const data = await res.json();
                        const users = data.users || [];
                        const customers = data.customers || [];
                        const rawList = (users && users.length) ? users : customers;
                        allLoadedUsers = rawList.map(c => {
                            const p = (c.platform || 'bale').toLowerCase();
                            const uid = c.user_id || c.id || c.chat_id || '';
                            let uname = c.username || c.customer_name || c.name || c.full_name || '';
                            if (!uname || uname === 'undefined' || uname === 'None') {
                                if (p.includes('tele')) uname = 'کاربر تلگرام';
                                else if (p.includes('soroush')) uname = 'کاربر سروش‌پلاس';
                                else if (p.includes('rubika')) uname = 'کاربر روبیکا';
                                else uname = 'کاربر بله';
                            }
                            return {
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
                            };
                        });

                        const statTotal = document.getElementById('statTotalUsers');
                        if (statTotal) statTotal.innerText = allLoadedUsers.length;

                        const refUsersCount = allLoadedUsers.filter(u => u.referred_by).length;
                        const statRef = document.getElementById('statRefUsers');
                        if (statRef) statRef.innerText = refUsersCount;

                        const totalWallet = allLoadedUsers.reduce((acc, u) => acc + (Number(u.wallet_balance) || 0), 0);
                        const statWallet = document.getElementById('statTotalWallet');
                        if (statWallet) statWallet.innerText = totalWallet.toLocaleString('fa-IR') + ' تومان';

                        renderUsersTable(allLoadedUsers);
                    } catch (err) {
                        console.error('loadUsersData error:', err);
                        tbody.innerHTML = '<tr><td colspan="9" class="p-6 text-center text-rose-400 font-sans">خطا در بارگذاری فهرست کاربران</td></tr>';
                    }
                }
                window.loadUsersData = loadUsersData;

                async function saveVipHubSettings() {
                    const priceInput = document.getElementById('viphub_price');
                    const daysInput = document.getElementById('viphub_days');
                    const cardInput = document.getElementById('viphub_card');
                    const promoInput = document.getElementById('viphub_promo');
                    const btn = document.getElementById('btnSaveVipHub');
                    
                    const price = priceInput ? priceInput.value.replace(/[,،\s]/g, '') : '111000';
                    const days = daysInput ? daysInput.value.trim() : '30';
                    const card = cardInput ? cardInput.value.trim() : '';
                    const promo = promoInput ? promoInput.value.trim() : '';

                    if (btn) btn.innerHTML = '<span>⏳</span> در حال ذخیره...';
                    try {
                        const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                        const res = await fetch('/api/settings/save', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json; charset=utf-8', 'Authorization': 'Bearer ' + pwd, 'X-Admin-Password': pwd },
                            body: JSON.stringify({
                                vip_monthly_price: parseInt(price) || 111000,
                                vip_duration_days: parseInt(days) || 30,
                                vip_card_number: card,
                                vip_promo_text: promo,
                                admin_password: pwd
                            })
                        });
                        const data = await res.json();
                        if (data.ok) {
                            showToast('تنظیمات پلن پریمیوم با موفقیت ذخیره شد.');
                        } else {
                            showToast('خطا در ذخیره تنظیمات: ' + (data.error || 'نامشخص'));
                        }
                    } catch (e) {
                        showToast('خطای ارتباط: ' + e.message);
                    } finally {
                        if (btn) btn.innerHTML = '<svg class="w-4 h-4 stroke-[2]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5"/></svg><span>ذخیره فوری تنظیمات پریمیوم</span>';
                    }
                }
                window.saveVipHubSettings = saveVipHubSettings;

                function renderUsersTable(users) {
                    const tbody = document.getElementById('usersTableBody');
                    if (!tbody) return;
                    if (!users || users.length === 0) {
                        tbody.innerHTML = '<tr><td colspan="9" class="p-6 text-center text-slate-500 font-sans">هیچ کاربری ثبت نشده است.</td></tr>';
                        return;
                    }
                    tbody.innerHTML = users.map(u => {
                        try {
                            if (!u) return '';
                            const p = (u.platform || 'bale').toLowerCase();
                            let platformBadge = '';
                            if (p.includes('tele')) {
                                platformBadge = '<span class="px-2 py-0.5 rounded text-[10px] bg-cyan-950 text-cyan-400 border border-cyan-800 font-sans inline-flex items-center gap-1"><svg class="w-3 h-3 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"/></svg> تلگرام</span>';
                            } else if (p.includes('soroush')) {
                                platformBadge = '<span class="px-2 py-0.5 rounded text-[10px] bg-sky-950 text-sky-400 border border-sky-800 font-sans inline-flex items-center gap-1"><svg class="w-3 h-3 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/></svg> سروش‌پلاس</span>';
                            } else if (p.includes('rubika')) {
                                platformBadge = '<span class="px-2 py-0.5 rounded text-[10px] bg-purple-950 text-purple-400 border border-purple-800 font-sans inline-flex items-center gap-1"><svg class="w-3 h-3 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"/></svg> روبیکا</span>';
                            } else {
                                platformBadge = '<span class="px-2 py-0.5 rounded text-[10px] bg-emerald-950 text-emerald-400 border border-emerald-800 font-sans inline-flex items-center gap-1"><svg class="w-3 h-3 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg> بله</span>';
                            }
                            const isUserVip = Boolean(u.is_vip || (u.vip_until && new Date(u.vip_until) > new Date()));
                            let vipBadge = '<span class="px-2 py-0.5 rounded text-[10px] bg-slate-800 text-slate-400 border border-slate-700 font-sans">عادی</span>';
                            if (isUserVip) {
                                const expDate = u.vip_until_jalali ? u.vip_until_jalali : ((u.vip_until || '').slice(0, 10));
                                vipBadge = '<span class="px-2 py-0.5 rounded text-[10px] bg-amber-500/10 text-amber-300 border border-amber-500/30 font-sans inline-flex items-center gap-1" title="انقضا: ' + escapeHtml(u.vip_until || '') + '">' +
                                    '<svg class="w-3 h-3 text-amber-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z"/></svg>' +
                                    ' پریمیوم (' + escapeHtml(expDate) + ')' +
                                '</span>';
                            }
                            const phone = u.phone ? ('<span dir="ltr">' + escapeHtml(u.phone) + '</span>') : '<span class="text-slate-600 font-sans">-</span>';
                            const joinDate = u.created_at ? new Date(u.created_at * 1000).toLocaleDateString('fa-IR') : 'نامشخص';
                            const name = escapeHtml(u.username || ('کاربر ' + (u.user_id || '')));
                            const ref = u.referred_by ? ('<span class="text-indigo-400" dir="ltr">' + escapeHtml(String(u.referred_by)) + '</span>') : '<span class="text-slate-600 font-sans">مستقیم</span>';
                            const wallet = (Number(u.wallet_balance) || 0).toLocaleString('fa-IR') + ' ت';
                            const commitment = u.commitment_signed 
                                ? '<span class="text-emerald-400 font-sans">امضا شده ✓</span>'
                                : '<span class="text-slate-500 font-sans">در انتظار</span>';
                            const userIdClean = escapeHtml(String(u.user_id || '-'));
                            
                            const vipBtn = isUserVip ? '<button type="button" data-user-action="revoke_vip" data-user-id="' + userIdClean + '" class="px-2 py-1 rounded-lg border border-amber-500/40 text-amber-400 hover:bg-amber-500/20 font-sans text-xs font-bold transition">لغو پریمیوم</button>' : '<button type="button" data-user-action="grant_vip" data-user-id="' + userIdClean + '" class="px-2 py-1 rounded-lg border border-cyan-500/40 text-cyan-400 hover:bg-cyan-500/20 font-sans text-xs font-bold transition">پریمیوم</button>';
// 

                            return '<tr class="hover:bg-white/[0.03] transition user-row" data-platform="' + escapeHtml(u.platform||'') + '">' + '<td class="p-3"><input type="checkbox" class="user-cb rounded text-cyan-600 border-slate-700 bg-slate-800 cursor-pointer form-checkbox accent-cyan-500 w-4 h-4" value="' + userIdClean + '" style="background:var(--input-bg);"></td>' +
                                '<td class="p-3">' + platformBadge + '</td>' +
                                '<td class="p-3 text-cyan-300" dir="ltr">' + userIdClean + '</td>' +
                                '<td class="p-3 text-slate-200 font-sans font-medium">' + name + '</td>' +
                                '<td class="p-3 text-slate-300">' + phone + '</td>' +
                                '<td class="p-3">' + vipBadge + '</td>' +
                                '<td class="p-3">' + ref + '</td>' +
                                '<td class="p-3 text-amber-400 font-bold">' + wallet + '</td>' +
                                '<td class="p-3 text-xs">' + commitment + '</td>' +
                                '<td class="p-3 text-xs text-slate-400">' + joinDate + '</td>' + '<td class="p-3 text-center">' +
                                    '<div class="inline-flex items-center gap-1.5">' +
                                        '<button type="button" data-user-action="view_profile" data-user-id="' + userIdClean + '" title="مشاهده پروفایل و دوره‌ها" class="p-1.5 rounded-lg border border-slate-700 text-slate-300 hover:bg-slate-800 transition-all font-sans text-xs inline-flex items-center gap-1 cursor-pointer">' +
                                            '<svg class="w-3.5 h-3.5 pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/></svg>' +
                                        '</button>' +
                                        vipBtn +
                                        '<button type="button" data-user-action="delete_user" data-user-id="' + userIdClean + '" title="حذف دائم کاربر" class="p-1.5 rounded-lg border border-rose-500/40 text-rose-400 hover:bg-rose-500/20 transition-all font-sans text-xs inline-flex items-center gap-1 cursor-pointer">' +
                                            '<svg class="w-3.5 h-3.5 pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>' +
                                        '</button>' +
                                    '</div>' +
                                '</td>' +
                            '</tr>';
                        } catch (rowErr) {
                            console.warn('Error rendering user row:', rowErr, u);
                            return '';
                        }
                    }).join('');

                    if (!tbody._delegated) {
                        tbody._delegated = true;
                        tbody.addEventListener('click', function(e) {
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
                        });
                    }
                }
                window.renderUsersTable = renderUsersTable;

                async function toggleUserVip(userId, action) {
                    if (!userId || userId === '-') return;
                    let actName = 'تمدید ۳۰ روزه';
                    let reqDays = 30;
                    if (action === 'revoke') actName = 'لغو';
                    else if (action === 'grant_10') { actName = 'اعطا / تمدید ۱۰ روزه'; reqDays = 10; }
                    else if (action === 'grant_30') { actName = 'اعطا / تمدید ۳۰ روزه'; reqDays = 30; }

                    if (!confirm('آیا از ' + actName + ' اشتراک پریمیوم برای کاربر ' + userId + ' اطمینان دارید؟')) return;
                    try {
                        const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                        const res = await fetch('/api/users/toggle_vip', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json; charset=utf-8', 'Authorization': 'Bearer ' + pwd, 'X-Admin-Password': pwd },
                            body: JSON.stringify({ user_id: userId, action: action, days: reqDays, admin_password: pwd })
                        });
                        const data = await res.json();
                        if (data.ok) {
                            const uIdx = allLoadedUsers.findIndex(u => String(u.user_id) === String(userId) || String(u.phone) === String(userId));
                            if (uIdx !== -1) {
                                allLoadedUsers[uIdx].is_vip = data.is_vip;
                                allLoadedUsers[uIdx].vip_until = data.vip_until;
                                if (data.vip_until_jalali) allLoadedUsers[uIdx].vip_until_jalali = data.vip_until_jalali;
                            }
                            renderUsersTable(allLoadedUsers);
                        } else {
                            showToast('خطا: ' + (data.error || 'عملیات ناموفق بود'));
                        }
                    } catch (e) {
                        showToast('خطای ارتباط: ' + e.message);
                    }
                }
                window.toggleUserVip = toggleUserVip;

                async function viewUserProfile(userId) {
                    if (!userId || userId === '-') return;
                    const modal = document.getElementById('userProfileModal');
                    const content = document.getElementById('userProfileModalContent');
                    if (!modal || !content) return;
                    content.innerHTML = '<div class="p-8 text-center text-slate-400">در حال دریافت اطلاعات جامع کاربر...</div>';
                    modal.classList.remove('hidden');
                    try {
                        const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                        const res = await fetch('/api/users/profile', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json; charset=utf-8', 'Authorization': 'Bearer ' + pwd, 'X-Admin-Password': pwd },
                            body: JSON.stringify({ user_id: userId, admin_password: pwd })
                        });
                        const data = await res.json();
                        if (data.ok && data.user) {
                            const u = data.user;
                            const isVip = Boolean(u.is_vip || (u.vip_until && new Date(u.vip_until) > new Date()));
                            const expDate = (u.vip_until || '').slice(0, 10);
                            const vipText = isVip ? ('<span class="text-amber-400 font-bold">💎 اشتراک پریمیوم تا ' + escapeHtml(expDate) + '</span>') : '<span class="text-slate-500">عادی (فاقد اشتراک)</span>';
                            const coursesCount = (u.purchased_courses || []).length;
                            const coursesList = (u.purchased_courses && u.purchased_courses.length) ? u.purchased_courses.map(escapeHtml).join('، ') : 'هنوز دوره‌ای خریداری نشده است.';
                            const avatarLetter = escapeHtml((u.full_name || u.username || 'U')[0].toUpperCase());
                            const userName = escapeHtml(u.full_name || u.username || 'کاربر');
                            const userPlatform = escapeHtml(u.platform || 'bale');
                            const userUid = escapeHtml(u.user_id || '-');
                            const userPhone = escapeHtml(u.phone || 'فاقد شماره');
                            const userWallet = Number(u.wallet_balance || 0).toLocaleString('fa-IR') + ' تومان';
                            const userInvites = (u.successful_invites || 0) + ' نفر';

                            content.innerHTML = 
                                '<div class="space-y-4 text-xs font-sans">' +
                                    '<div class="flex items-center justify-between pb-3 border-b border-slate-700/60">' +
                                        '<div class="flex items-center gap-3">' +
                                            '<div class="w-10 h-10 rounded-xl bg-cyan-500/10 text-cyan-400 flex items-center justify-center font-bold text-sm">' +
                                                avatarLetter +
                                            '</div>' +
                                            '<div>' +
                                                '<h4 class="font-bold text-sm text-white">' + userName + '</h4>' +
                                                '<span class="text-slate-400 text-[11px]">' + userPlatform + ' | ' + userUid + '</span>' +
                                            '</div>' +
                                        '</div>' +
                                        '<div class="text-left">' + vipText + '</div>' +
                                    '</div>' +
                                    '<div class="grid grid-cols-2 gap-3 text-right">' +
                                        '<div class="p-3 rounded-xl  border border-slate-800">' +
                                            '<span class="text-slate-500 block text-[11px]">شماره تماس:</span>' +
                                            '<span class="text-slate-200" dir="ltr">' + userPhone + '</span>' +
                                        '</div>' +
                                        '<div class="p-3 rounded-xl  border border-slate-800">' +
                                            '<span class="text-slate-500 block text-[11px]">موجودی کیف پول:</span>' +
                                            '<span class="text-amber-400 font-bold">' + userWallet + '</span>' +
                                        '</div>' +
                                        '<div class="p-3 rounded-xl  border border-slate-800">' +
                                            '<span class="text-slate-500 block text-[11px]">دوره‌های ثبت‌شده:</span>' +
                                            '<span class="font-bold text-emerald-400">' + coursesCount + ' دوره</span>' +
                                        '</div>' +
                                        '<div class="p-3 rounded-xl  border border-slate-800">' +
                                            '<span class="text-slate-500 block text-[11px]">دعوت‌های موفق رفرال:</span>' +
                                            '<span class="font-bold text-cyan-400">' + userInvites + '</span>' +
                                        '</div>' +
                                    '</div>' +
                                    '<div class="p-3 rounded-xl  border border-slate-800">' +
                                        '<span class="text-slate-500 block text-[11px] mb-1">دوره‌های خریداری‌شده:</span>' +
                                        '<span class="text-slate-300 font-sans">' + coursesList + '</span>' +
                                    '</div>' +
                                    '<div class="flex justify-end gap-2 pt-2">' +
                                        '<button type="button" onclick="closeUserProfileModal()" class="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-bold transition cursor-pointer">بستن</button>' +
                                    '</div>' +
                                '</div>';
                        } else {
                            content.innerHTML = '<div class="p-6 text-center text-rose-400">اطلاعات کاربر یافت نشد.</div>';
                        }
                    } catch (err) {
                        content.innerHTML = '<div class="p-6 text-center text-rose-400">خطا: ' + escapeHtml(err.message) + '</div>';
                    }
                }
                window.viewUserProfile = viewUserProfile;

                function closeUserProfileModal() {
                    const modal = document.getElementById('userProfileModal');
                    if (modal) modal.classList.add('hidden');
                }
                window.closeUserProfileModal = closeUserProfileModal;

                function switchProductSubTab(subTabId) {
                    ['courses', 'audiobooks', 'vip'].forEach(id => {
                        const contentEl = document.getElementById('subtab-prods-' + id + '-content');
                        const btnEl = document.getElementById('btn-subtab-prods-' + id);
                        if (contentEl) {
                            if (id === subTabId) contentEl.classList.remove('hidden');
                            else contentEl.classList.add('hidden');
                        }
                        if (btnEl) {
                            if (id === subTabId) {
                                btnEl.style.background = 'var(--accent-color)';
                                btnEl.style.color = '#fff';
                                btnEl.classList.add('font-bold');
                                btnEl.classList.remove('text-slate-400');
                            } else {
                                btnEl.style.background = 'transparent';
                                btnEl.style.color = '';
                                btnEl.classList.remove('font-bold');
                                btnEl.classList.add('text-slate-400');
                            }
                        }
                    });
                }
                window.switchProductSubTab = switchProductSubTab;

                /**
                 * مدیریت کشیدن و رها کردن (Drag & Drop) ۳ ساب‌تب محصولات و ماندگاری چیدمان در localStorage
                 * ورودی: ندارد
                 * خروجی: ندارد (به‌روزرسانی DOM و رویدادها)
                 */
                function initProductSubtabsDragAndDrop() {
                    const container = document.getElementById('productSubtabsContainer');
                    if (!container) return;

                    try {
                        const savedOrder = JSON.parse(localStorage.getItem('unfinit_products_subtabs_order') || '[]');
                        if (Array.isArray(savedOrder) && savedOrder.length > 0) {
                            const btnMap = {};
                            const buttons = Array.from(container.querySelectorAll('.prod-subtab-btn'));
                            buttons.forEach(btn => {
                                const subtab = btn.getAttribute('data-subtab');
                                if (subtab) btnMap[subtab] = btn;
                            });
                            savedOrder.forEach(subtab => {
                                if (btnMap[subtab]) {
                                    container.appendChild(btnMap[subtab]);
                                }
                            });
                        }
                    } catch (e) {
                        console.warn('Error loading product subtabs order:', e);
                    }

                    let draggedBtn = null;

                    container.addEventListener('dragstart', (e) => {
                        const target = e.target.closest('.prod-subtab-btn');
                        if (!target) return;
                        draggedBtn = target;
                        e.dataTransfer.effectAllowed = 'move';
                        e.dataTransfer.setData('text/plain', target.getAttribute('data-subtab') || '');
                        target.classList.add('opacity-40', 'scale-95');
                    });

                    container.addEventListener('dragend', (e) => {
                        const target = e.target.closest('.prod-subtab-btn');
                        if (target) target.classList.remove('opacity-40', 'scale-95');
                        draggedBtn = null;
                        saveProductSubtabsOrder();
                    });

                    container.addEventListener('dragover', (e) => {
                        e.preventDefault();
                        e.dataTransfer.dropEffect = 'move';
                        const target = e.target.closest('.prod-subtab-btn');
                        if (target && target !== draggedBtn) {
                            const rect = target.getBoundingClientRect();
                            const next = (e.clientX - rect.left) / (rect.right - rect.left) > 0.5;
                            container.insertBefore(draggedBtn, next ? target.nextSibling : target);
                        }
                    });

                    function saveProductSubtabsOrder() {
                        const buttons = Array.from(container.querySelectorAll('.prod-subtab-btn'));
                        const order = buttons.map(b => b.getAttribute('data-subtab')).filter(Boolean);
                        localStorage.setItem('unfinit_products_subtabs_order', JSON.stringify(order));
                    }
                }
                window.initProductSubtabsDragAndDrop = initProductSubtabsDragAndDrop;

                function inlineRenameTab(element, tabId) {
                    const currentText = element.textContent.trim();
                    const input = document.createElement('input');
                    input.type = 'text';
                    input.value = currentText;
                    input.className = 'w-full  text-white text-xs px-2 py-1 rounded border border-cyan-500 focus:outline-none';
                    
                    const saveRename = async () => {
                        const newTitle = input.value.trim();
                        if (newTitle && newTitle !== currentText) {
                            element.textContent = newTitle;
                            try {
                                const renames = JSON.parse(localStorage.getItem('unfinit_tab_renames') || '{}');
                                renames[tabId] = newTitle;
                                localStorage.setItem('unfinit_tab_renames', JSON.stringify(renames));
                            } catch (e) {}
                            try {
                                const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                                await fetch('/api/settings/rename', {
                                    method: 'POST',
                                    headers: { 'Content-Type': 'application/json; charset=utf-8', 'Authorization': 'Bearer ' + pwd, 'X-Admin-Password': pwd },
                                    body: JSON.stringify({ tab_id: tabId, title: newTitle, admin_password: pwd })
                                });
                            } catch (e) {
                                console.warn('Failed to save tab rename:', e);
                            }
                        } else {
                            element.textContent = currentText;
                        }
                    };

                    input.onblur = saveRename;
                    input.onkeydown = (e) => {
                        if (e.key === 'Enter') {
                            input.blur();
                        } else if (e.key === 'Escape') {
                            element.textContent = currentText;
                        }
                    };

                    element.textContent = '';
                    element.appendChild(input);
                    input.focus();
                    input.select();
                }
                window.inlineRenameTab = inlineRenameTab;

                function restoreTabRenames() {
                    try {
                        const renames = JSON.parse(localStorage.getItem('unfinit_tab_renames') || '{}');
                        for (const [tabId, title] of Object.entries(renames)) {
                            const btn = document.querySelector(`.sidebar-nav-btn[data-tab="${tabId}"] span.text-right`) ||
                                        document.querySelector(`.sidebar-nav-btn[data-tab="${tabId}"] span`);
                            if (btn && title) {
                                btn.textContent = title;
                            }
                        }
                    } catch (e) {}
                }
                window.restoreTabRenames = restoreTabRenames;

                async function deleteUserRow(userId) {
                    if (!userId || userId === '-' || userId === 'undefined') return;
                    if (!confirm(`آیا از حذف کامل کاربر با شناسه ${userId} از پایگاه داده اطمینان دارید؟`)) return;
                    try {
                        const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                        const res = await fetch('/api/users/delete', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json; charset=utf-8', 'Authorization': 'Bearer ' + pwd, 'X-Admin-Password': pwd },
                            body: JSON.stringify({ user_id: userId, admin_password: pwd })
                        });
                        const data = await res.json();
                        if (data.ok) {
                            allLoadedUsers = allLoadedUsers.filter(u => String(u.user_id) !== String(userId));
                            renderUsersTable(allLoadedUsers);
                            const statTotal = document.getElementById('statTotalUsers');
                            if (statTotal) statTotal.innerText = allLoadedUsers.length;
                        } else {
                            showToast('خطا در حذف کاربر: ' + (data.error || 'نامشخص'));
                        }
                    } catch (e) {
                        showToast('خطای ارتباط: ' + e.message);
                    }
                }
                window.deleteUserRow = deleteUserRow;

                async function purgeTestUsers() {
                    if (!confirm('هشدار: آیا مطمئن هستید که می‌خواهید تمام کاربران آزمایشی و ساختگی را پاکسازی کنید؟')) return;
                    try {
                        const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                        const res = await fetch('/api/users/purge_test', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json; charset=utf-8', 'Authorization': 'Bearer ' + pwd, 'X-Admin-Password': pwd },
                            body: JSON.stringify({ admin_password: pwd })
                        });
                        const data = await res.json();
                        if (data.ok) {
                            showToast(`پاکسازی انجام شد. ${data.deleted_count || 0} کاربر آزمایشی حذف شدند.`);
                            loadUsersData();
                        } else {
                            showToast('خطا در پاکسازی: ' + (data.error || 'نامشخص'));
                        }
                    } catch (e) {
                        showToast('خطای ارتباط: ' + e.message);
                    }
                }
                window.purgeTestUsers = purgeTestUsers;

                
    function toggleAllUsers(source) {
        document.querySelectorAll('.user-cb').forEach(cb => {
            if(cb.closest('tr').style.display !== 'none') {
                cb.checked = source.checked;
            }
        });
    }
    async function deleteSelectedUsers() {
        const selected = Array.from(document.querySelectorAll('.user-cb:checked')).map(cb => cb.value);
        if(!selected.length) return alert('کاربری انتخاب نشده است.');
        if(!confirm(`آیا از حذف ${selected.length} کاربر مطمئن هستید؟`)) return;
        
        for(let uid of selected) {
            await fetch('/api/users/delete', {
                method: 'POST',
                headers: {'Content-Type':'application/json'},
                body: JSON.stringify({user_id: uid})
            });
        }
        alert('کاربران انتخاب‌شده حذف شدند.');
        loadUsersData();
    }
    
    function filterUsersTable() {
        const val = document.getElementById('usersSearchInput').value.toLowerCase();
        const platElem = document.getElementById('userPlatformFilter');
        const plat = platElem ? platElem.value : 'all';
        const rows = document.getElementById('usersTableBody').querySelectorAll('tr.user-row');
        
        rows.forEach(tr => {
            const text = tr.innerText.toLowerCase();
            const rp = tr.getAttribute('data-platform');
            const matchSearch = text.includes(val);
            const matchPlat = (plat === 'all') || (rp === plat);
            tr.style.display = (matchSearch && matchPlat) ? '' : 'none';
        });
    }
    

                window.filterUsersTable = filterUsersTable; window.toggleAllUsers = toggleAllUsers; window.deleteSelectedUsers = deleteSelectedUsers;

                function exportUsersCsv() {
                    if (!allLoadedUsers || allLoadedUsers.length === 0) {
                        showToast('کاربری برای خروجی موجود نیست.');
                        return;
                    }
                    const header = ['پلتفرم', 'شناسه', 'نام', 'شماره تماس', 'معرف', 'کیف پول', 'تعهدنامه'];
                    const rows = allLoadedUsers.map(u => [
                        u.platform || '',
                        u.user_id || '',
                        u.username || u.name || '',
                        u.phone || '',
                        u.referred_by || '',
                        u.wallet_balance || 0,
                        u.commitment_signed ? 'امضا شده' : 'خیر'
                    ]);
                    const csvContent = "\uFEFF" + [header.join(','), ...rows.map(r => r.map(c => `"${String(c).replace(/"/g, '""')}"`).join(','))].join('\n');
                    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
                    const url = URL.createObjectURL(blob);
                    const link = document.createElement('a');
                    link.href = url;
                    link.download = `unfinit_users_${new Date().toISOString().slice(0,10)}.csv`;
                    link.click();
                    URL.revokeObjectURL(url);
                }
                window.exportUsersCsv = exportUsersCsv;

                function checkAuthOnLoad() {
                    const token = localStorage.getItem('unfinit_auth_token') || sessionStorage.getItem('unfinit_auth_token');
                    const pwd = localStorage.getItem('unfinit_admin_pwd') || sessionStorage.getItem('unfinit_admin_pwd');
                    const gate = document.getElementById('loginGate');
                    const app = document.getElementById('appMain');
                    if (token === 'authenticated' && pwd) {
                        window.currentAdminPassword = pwd;
                        if (gate) {
                            gate.style.display = 'none';
                            gate.classList.add('hidden');
                        }
                        if (app) {
                            app.style.removeProperty('display');
                            app.style.display = 'block';
                            app.classList.remove('hidden');
                        }
                        try {
                            const savedTab = localStorage.getItem('unfinit_active_tab') || 'dashboard';
                            window.switchTab(savedTab);
                        } catch (e) {
                            console.warn('[Navigation] Tab switch notice:', e);
                        }
                    } else {
                        if (gate) {
                            gate.style.removeProperty('display');
                            gate.classList.remove('hidden');
                        }
                        if (app) {
                            app.classList.add('hidden');
                            app.style.display = 'none';
                        }
                    }
                }

                function bindNavDelegation() {
                    const sidebarNav = document.getElementById('sidebarNavList');
                    if (sidebarNav) {
                        sidebarNav.addEventListener('click', function(e) {
                            const btn = e.target.closest('[data-tab]');
                            if (btn) {
                                const tab = btn.getAttribute('data-tab');
                                if (tab && window.switchTab) window.switchTab(tab);
                            }
                        });
                    }
                    const desktopNav = document.getElementById('desktopNavTabs');
                    if (desktopNav) {
                        desktopNav.addEventListener('click', function(e) {
                            const btn = e.target.closest('[data-tab]');
                            if (btn) {
                                const tab = btn.getAttribute('data-tab');
                                if (tab && window.switchTab) window.switchTab(tab);
                            }
                        });
                    }
                    const mobileNav = document.getElementById('mobileNavMenu');
                    if (mobileNav) {
                        mobileNav.addEventListener('click', function(e) {
                            const btn = e.target.closest('[data-tab]');
                            if (btn) {
                                const tab = btn.getAttribute('data-tab');
                                if (tab && window.switchTab) {
                                    window.switchTab(tab);
                                    if (typeof window.toggleMobileMenu === 'function') {
                                        window.toggleMobileMenu(false);
                                    }
                                }
                            }
                        });
                    }
                }

                function persistTabsOrder() {
                    const sidebarNav = document.getElementById('sidebarNavList');
                    const desktopNav = document.getElementById('desktopNavTabs');
                    let currentOrder = [];
                    if (sidebarNav) {
                        currentOrder = Array.from(sidebarNav.querySelectorAll('[data-tab]')).map(b => b.getAttribute('data-tab')).filter(Boolean);
                    }
                    if (currentOrder.length === 0 && desktopNav) {
                        currentOrder = Array.from(desktopNav.querySelectorAll('[data-tab]')).map(b => b.getAttribute('data-tab')).filter(Boolean);
                    }
                    if (currentOrder.length === 0) return;
                    // تضمین قطعی قرار گرفتن تب داشبورد در نخستین جایگاه سایدبار (index: 0)
                    currentOrder = ['dashboard', ...currentOrder.filter(t => t !== 'dashboard')];
                    localStorage.setItem('unfinit_nav_order', JSON.stringify(currentOrder));
                    localStorage.setItem('unfinit_tabs_order', JSON.stringify(currentOrder));
                    try {
                        const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                        if (pwd) {
                            fetch('/api/settings/save', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json; charset=utf-8' },
                                body: JSON.stringify({
                                    password: pwd,
                                    settings: { NAV_TABS_ORDER: currentOrder }
                                })
                            }).catch(e => console.warn('[DragDrop] Cloud save failed:', e));
                        }
                    } catch (e) {}
                }

                function initTabsDragAndDrop() {
                    const sidebarNav = document.getElementById('sidebarNavList');
                    const desktopNav = document.getElementById('desktopNavTabs');

                    try {
                        let savedOrder = JSON.parse(localStorage.getItem('unfinit_nav_order') || localStorage.getItem('unfinit_tabs_order') || '[]');
                        if (Array.isArray(savedOrder) && savedOrder.length > 0) {
                            // تثبیت رتبه اول برای داشبورد در هنگام بارگذاری
                            savedOrder = ['dashboard', ...savedOrder.filter(t => t !== 'dashboard')];
                            if (sidebarNav) {
                                savedOrder.forEach(tabId => {
                                    const btn = sidebarNav.querySelector(`[data-tab="${tabId}"]`);
                                    if (btn) sidebarNav.appendChild(btn);
                                });
                            }
                            if (desktopNav) {
                                savedOrder.forEach(tabId => {
                                    const btn = desktopNav.querySelector(`[data-tab="${tabId}"]`);
                                    if (btn) desktopNav.appendChild(btn);
                                });
                            }
                        }
                    } catch (e) {
                        console.warn('[DragDrop] Error loading saved tab order:', e);
                    }

                    function setupDragForContainer(container, isVertical) {
                        if (!container) return;
                        let draggedItem = null;

                        // Set draggable="false" on all tab items while preserving cursor: pointer
                        container.querySelectorAll('[data-tab]').forEach(b => {
                            b.setAttribute('draggable', 'false');
                            b.style.cursor = 'pointer';
                        });

                        // Mouse Drag & Drop (Native HTML5: Clicks fire instantly, dragging initiates reorder)
                        container.addEventListener('dragstart', function(e) {
                            const btn = e.target.closest('[data-tab]');
                            if (!btn) return;
                            draggedItem = btn;
                            e.dataTransfer.effectAllowed = 'move';
                            e.dataTransfer.setData('text/plain', btn.getAttribute('data-tab'));
                            btn.classList.add('opacity-40');
                        });

                        container.addEventListener('dragend', function(e) {
                            const btn = e.target.closest('[data-tab]');
                            if (btn) {
                                btn.classList.remove('opacity-40');
                            }
                            container.querySelectorAll('[data-tab]').forEach(b => {
                                b.classList.remove('opacity-40');
                                b.setAttribute('draggable', 'false');
                                b.style.cursor = 'pointer';
                            });
                            draggedItem = null;
                            persistTabsOrder();
                        });

                        container.addEventListener('dragover', function(e) {
                            e.preventDefault();
                            e.dataTransfer.dropEffect = 'move';
                            const targetBtn = e.target.closest('[data-tab]');
                            if (targetBtn && targetBtn !== draggedItem && targetBtn.parentElement === container) {
                                const rect = targetBtn.getBoundingClientRect();
                                const midpoint = isVertical ? (rect.y + rect.height / 2) : (rect.x + rect.width / 2);
                                const coord = isVertical ? e.clientY : e.clientX;
                                if (coord < midpoint) {
                                    container.insertBefore(draggedItem, targetBtn);
                                } else {
                                    container.insertBefore(draggedItem, targetBtn.nextSibling);
                                }
                            }
                        });

                        container.addEventListener('drop', function(e) {
                            e.preventDefault();
                            persistTabsOrder();
                        });

                        // Mobile Touch with 500ms long-press
                        let touchTimer = null;
                        let touchDraggedItem = null;

                        container.addEventListener('touchstart', function(e) {
                            const btn = e.target.closest('[data-tab]');
                            if (!btn) return;
                            touchTimer = setTimeout(function() {
                                touchDraggedItem = btn;
                                btn.classList.add('opacity-40', 'scale-95');
                                if (navigator.vibrate) navigator.vibrate(50);
                            }, 500);
                        }, { passive: true });

                        container.addEventListener('touchmove', function(e) {
                            if (!touchDraggedItem) {
                                if (touchTimer) { clearTimeout(touchTimer); touchTimer = null; }
                                return;
                            }
                            e.preventDefault();
                            const touch = e.touches[0];
                            const targetEl = document.elementFromPoint(touch.clientX, touch.clientY);
                            if (!targetEl) return;
                            const targetBtn = targetEl.closest('[data-tab]');
                            if (targetBtn && targetBtn !== touchDraggedItem && targetBtn.parentElement === container) {
                                const rect = targetBtn.getBoundingClientRect();
                                const midpoint = isVertical ? (rect.y + rect.height / 2) : (rect.x + rect.width / 2);
                                const coord = isVertical ? touch.clientY : touch.clientX;
                                if (coord < midpoint) {
                                    container.insertBefore(touchDraggedItem, targetBtn);
                                } else {
                                    container.insertBefore(touchDraggedItem, targetBtn.nextSibling);
                                }
                            }
                        }, { passive: false });

                        function endTouchDrag() {
                            if (touchTimer) { clearTimeout(touchTimer); touchTimer = null; }
                            if (touchDraggedItem) {
                                touchDraggedItem.classList.remove('opacity-40', 'scale-95');
                                container.querySelectorAll('[data-tab]').forEach(b => b.classList.remove('opacity-40', 'scale-95'));
                                touchDraggedItem = null;
                                persistTabsOrder();
                            }
                        }
                        container.addEventListener('touchend', endTouchDrag);
                        container.addEventListener('touchcancel', endTouchDrag);
                    }

                    setupDragForContainer(sidebarNav, true);
                    setupDragForContainer(desktopNav, false);
                }

                function initUptimeTicker() {
                    const el = document.getElementById('uptimeDisplay');
                    if (!el) return;
                    const startSec = parseInt(el.getAttribute('data-start')) || 0;
                    if (!startSec) return;
                    function updateUptime() {
                        const now = Math.floor(Date.now() / 1000);
                        let diff = Math.max(0, now - startSec);
                        const h = Math.floor(diff / 3600);
                        const m = Math.floor((diff % 3600) / 60);
                        const s = diff % 60;
                        el.textContent = `${h}h ${m}m ${s}s`;
                    }
                    setInterval(updateUptime, 1000);
                }

                if (document.readyState === 'loading') {
                    document.addEventListener('DOMContentLoaded', function() {
                        bindNavDelegation();
                        initTabsDragAndDrop();
                        initSidebarState();
                        initUptimeTicker();
                        checkAuthOnLoad();
                        restoreTabRenames();
                    });
                } else {
                    bindNavDelegation();
                    initTabsDragAndDrop();
                    initSidebarState();
                    initUptimeTicker();
                    checkAuthOnLoad();
                    restoreTabRenames();
                }
            } catch (err) {
                console.error('[UNFINIT Navigation Module Error]:', err);
            }
        })();

        // =========================================================================
        // MODULE 2: STUDIO & MEDIA HUB (Sandboxed IIFE)
        // =========================================================================
        (function initStudioModule() {
            try {
        // WEB MP3TAG STUDIO CLIENT LOGIC
        // =========================================================================

        const studioDropzone = document.getElementById('studioDropzone');
        if (studioDropzone) {
            ['dragenter', 'dragover'].forEach(name => {
                studioDropzone.addEventListener(name, (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    studioDropzone.classList.add('dragover');
                });
            });
            ['dragleave', 'drop'].forEach(name => {
                studioDropzone.addEventListener(name, (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    studioDropzone.classList.remove('dragover');
                });
            });
            studioDropzone.addEventListener('drop', (e) => {
                e.preventDefault();
                e.stopPropagation();
                studioDropzone.classList.remove('dragover');
                const dt = e.dataTransfer;
                if (dt && dt.files && dt.files.length > 0) {
                    handleStudioFilesSelect(dt.files);
                }
            });
        }

        async function handleStudioFilesSelect(fileList) {
            if (!fileList || fileList.length === 0) return;
            const progressEl = document.getElementById('studioUploadProgress');
            if (progressEl) {
                progressEl.classList.remove('hidden');
                progressEl.innerText = `⏳ در حال آماده‌سازی و بارگذاری ${fileList.length} فایل...`;
            }

            let successCount = 0;
            for (let i = 0; i < fileList.length; i++) {
                const file = fileList[i];
                if (progressEl) progressEl.innerText = `⏳ در حال آپلود (${i+1}/${fileList.length}): ${file.name}...`;
                try {
                    const b64 = await readFileAsBase64(file);
                    const res = await fetch('/api/studio/upload', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json; charset=utf-8' },
                        body: JSON.stringify({ filename: file.name, data: b64 })
                    });
                    const data = await res.json();
                    if (data.ok) successCount++;
                } catch (err) {
                    console.error('Upload error:', err);
                }
            }

            if (progressEl) {
                progressEl.innerText = `✅ تعداد ${successCount} فایل با موفقیت بارگذاری و در استودیو ثبت گردید!`;
            }
            setTimeout(() => {
                if (progressEl) progressEl.classList.add('hidden');
                refreshStudioList();
            }, 800);
        }

        function readFileAsBase64(file) {
            return new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = () => resolve(reader.result);
                reader.onerror = error => reject(error);
                reader.readAsDataURL(file);
            });
        }

        function previewStudioCover(input, previewImgId, b64InputId) {
            const file = input.files[0];
            if (!file) return;
            const reader = new FileReader();
            reader.onload = function(e) {
                const img = document.getElementById(previewImgId);
                if (img) img.src = e.target.result;
                const b64 = document.getElementById(b64InputId);
                if (b64) b64.value = e.target.result;
            };
            reader.readAsDataURL(file);
        }

        // Specs Modal
        async function openSpecsModal(dropId) {
            const modal = document.getElementById('specsModal');
            const loading = document.getElementById('specsLoading');
            const body = document.getElementById('specsBody');
            modal.classList.remove('hidden');
            loading.classList.remove('hidden');
            body.classList.add('hidden');

            try {
                const res = await fetch('/api/studio/specs/' + dropId);
                const data = await res.json();
                if (data.ok) {
                    document.getElementById('specFilename').innerText = data.filename || '-';
                    document.getElementById('specBitrate').innerText = (data.bitrate_kbps ? data.bitrate_kbps + ' kbps' : 'نامشخص');
                    document.getElementById('specSampleRate').innerText = (data.sample_rate ? data.sample_rate + ' Hz' : 'نامشخص');
                    document.getElementById('specChannels').innerText = data.channels || 'نامشخص';
                    document.getElementById('specCodec').innerText = data.codec || '-';
                    document.getElementById('specDuration').innerText = data.duration_str || '-';
                    document.getElementById('specSize').innerText = data.size_str || '-';
                    const covEl = document.getElementById('specCoverStatus');
                    covEl.innerText = data.has_cover ? '✅ موجود' : '❌ فاقد کاور';
                    covEl.className = data.has_cover ? 'text-emerald-400 font-bold' : 'text-slate-500 font-bold';

                    loading.classList.add('hidden');
                    body.classList.remove('hidden');
                } else {
                    showToast('❌ خطا در دریافت مشخصات فنی: ' + (data.error || ''));
                    closeSpecsModal();
                }
            } catch (err) {
                showToast('❌ خطای شبکه: ' + err.message);
                closeSpecsModal();
            }
        }

        function closeSpecsModal() {
            document.getElementById('specsModal').classList.add('hidden');
        }

        // Single Tag Modal
        function openTagModal(dropId, title, artist, album, filename) {
            document.getElementById('tagDropId').value = dropId;
            document.getElementById('tagTitle').value = title || '';
            document.getElementById('tagArtist').value = artist || '';
            document.getElementById('tagAlbum').value = album || '';
            document.getElementById('tagFilename').value = filename || '';
            document.getElementById('tagCoverB64').value = '';
            document.getElementById('tagRemoveCover').checked = false;
            
            const prev = document.getElementById('tagCoverPreview');
            prev.src = '/api/studio/cover/' + dropId + '?t=' + Date.now();
            prev.onerror = () => {
                prev.src = 'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="%2364748b"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3"/></svg>';
            };

            document.getElementById('tagModal').classList.remove('hidden');
        }

        function closeTagModal() {
            document.getElementById('tagModal').classList.add('hidden');
        }

        async function handleSaveStudioTags(e) {
            e.preventDefault();
            const btn = document.getElementById('btnSaveTag');
            if (btn) {
                btn.disabled = true;
                btn.innerText = '⏳ در حال ذخیره آنی متادیتا...';
            }

            const payload = {
                drop_id: document.getElementById('tagDropId').value,
                title: document.getElementById('tagTitle').value,
                artist: document.getElementById('tagArtist').value,
                album: document.getElementById('tagAlbum').value,
                new_filename: document.getElementById('tagFilename').value,
                cover_data: document.getElementById('tagCoverB64').value,
                remove_cover: document.getElementById('tagRemoveCover').checked
            };

            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 60000);

            try {
                const res = await fetch('/api/studio/edit_tags', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json; charset=utf-8' },
                    body: JSON.stringify(payload),
                    signal: controller.signal
                });
                clearTimeout(timeoutId);
                const data = await res.json();
                if (data.ok) {
                    showToast('✅ ' + (data.message || 'متادیتا با موفقیت ذخیره شد!'));
                    closeTagModal();
                    refreshStudioList();
                } else {
                    showToast('❌ خطا: ' + (data.error || 'ذخیره متادیتا ناموفق بود'));
                }
            } catch (err) {
                clearTimeout(timeoutId);
                showToast('❌ خطای ارتباط یا زمان‌بندی: ' + err.message);
            } finally {
                if (btn) {
                    btn.disabled = false;
                    btn.innerText = '💾 ذخیره آنی متادیتا';
                }
            }
        }

        // Selection and Batch Edit
        function toggleSelectAllDrops(masterChk) {
            document.querySelectorAll('.drop-chk').forEach(c => c.checked = masterChk.checked);
            updateSelectedCount();
        }

        function updateSelectedCount() {
            const checked = document.querySelectorAll('.drop-chk:checked');
            const badge = document.getElementById('selectedCountBadge');
            if (badge) badge.innerText = checked.length + ' فایل انتخاب شده';
        }

        function getSelectedDropIds() {
            const checked = document.querySelectorAll('.drop-chk:checked');
            return Array.from(checked).map(c => c.getAttribute('data-drop-id'));
        }

        function openBatchTagModal() {
            const ids = getSelectedDropIds();
            if (ids.length === 0) {
                showToast('⚠️ لطفاً حداقل یک فایل را برای ویرایش گروهی انتخاب فرمایید.');
                return;
            }
            document.getElementById('batchCountBadge').innerText = ids.length;
            document.getElementById('batchCoverB64').value = '';
            document.getElementById('batchRemoveCover').checked = false;
            document.getElementById('batchCoverPreview').src = '';
            document.getElementById('batchTagModal').classList.remove('hidden');
        }

        function closeBatchTagModal() {
            document.getElementById('batchTagModal').classList.add('hidden');
        }

        async function handleSaveBatchTags(e) {
            e.preventDefault();
            const ids = getSelectedDropIds();
            if (ids.length === 0) return;

            const btn = document.getElementById('btnSaveBatch');
            btn.disabled = true;
            btn.innerText = '⏳ در حال اعمال تغییرات گروهی...';

            const payload = {
                drop_ids: ids,
                album: document.getElementById('batchAlbum').value,
                artist: document.getElementById('batchArtist').value,
                auto_number: document.getElementById('batchAutoNumber').checked,
                title_pattern: document.getElementById('batchTitlePattern').value,
                cover_data: document.getElementById('batchCoverB64').value,
                remove_cover: document.getElementById('batchRemoveCover').checked
            };

            try {
                const res = await fetch('/api/studio/batch_edit', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json; charset=utf-8' },
                    body: JSON.stringify(payload)
                });
                const data = await res.json();
                if (data.ok) {
                    showToast('✅ ' + (data.message || 'ویرایش گروهی با موفقیت اعمال گردید!'));
                    closeBatchTagModal();
                    refreshStudioList();
                } else {
                    showToast('❌ خطا: ' + (data.error || 'عملیات گروهی ناموفق بود'));
                }
            } catch (err) {
                showToast('❌ خطای ارتباط: ' + err.message);
            } finally {
                btn.disabled = false;
                btn.innerText = '🚀 اعمال روی تمام فایل‌ها';
            }
        }

        /**
         * ارسال مستقیم یک فایل از استودیوی رسانه به پلتفرم‌های پیام‌رسان (تلگرام، بله، روبیکا، سروش‌پلاس).
         * ورودی‌ها: dropId (شناسه دراپ فیزیکی)، target (نام پلتفرم مقصد)
         */
        async function dispatchDrop(dropId, target) {
            const names = { telegram: 'تلگرام', bale: 'بله', rubika: 'روبیکا', soroush: 'سروش‌پلاس', splus: 'سروش‌پلاس' };
            const targetName = names[target] || target;
            if (!confirm(`آیا می‌خواهید این فایل مستقیماً به ${targetName} ارسال شود؟`)) return;

            try {
                const res = await fetch('/api/studio/dispatch', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json; charset=utf-8' },
                    body: JSON.stringify({ drop_id: dropId, target: target })
                });
                const data = await res.json();
                if (data.ok) {
                    showToast('✅ ' + (data.message || `فایل با موفقیت به ${targetName} ارسال شد!`));
                } else {
                    showToast('❌ خطا: ' + (data.error || 'ارسال فایل ناموفق بود'));
                }
            } catch (err) {
                showToast('❌ خطای ارتباط با سرور: ' + err.message);
            }
        }

        // =========================================================================
        // WAVESURFER AUDIO CUTTER & STUDIO ACTION LOGIC
        // =========================================================================
        let wavesurfer = null;

        function formatSecToTime(seconds) {
            if (isNaN(seconds) || seconds < 0) seconds = 0;
            const m = Math.floor(seconds / 60);
            const s = Math.floor(seconds % 60);
            const ms = Math.floor((seconds % 1) * 10);
            return String(m).padStart(2, '0') + ':' + String(s).padStart(2, '0') + '.' + ms;
        }

        function parseTimeToSec(str) {
            if (!str) return 0;
            str = String(str).trim();
            if (str.includes(':')) {
                const parts = str.split(':');
                const m = parseFloat(parts[0]) || 0;
                const s = parseFloat(parts[1]) || 0;
                return m * 60 + s;
            }
            return parseFloat(str) || 0;
        }

        function openCutterModal(dropId, filename) {
            document.getElementById('cutterDropId').value = dropId;
            document.getElementById('cutterFilename').innerText = filename || dropId;
            document.getElementById('cutStartTime').value = '00:00.0';
            document.getElementById('cutEndTime').value = '00:00.0';
            document.getElementById('cutterCurrentTime').innerText = '00:00.0';
            document.getElementById('cutterTotalDuration').innerText = '00:00.0';
            document.getElementById('wavePlayText').innerText = 'پخش';
            document.getElementById('cutterModal').classList.remove('hidden');

            const loading = document.getElementById('waveformLoading');
            if (loading) loading.classList.remove('hidden');

            if (wavesurfer) {
                try { wavesurfer.destroy(); } catch (e) {}
                wavesurfer = null;
            }

            try {
                wavesurfer = WaveSurfer.create({
                    container: '#waveform',
                    waveColor: '#334155',
                    progressColor: '#06b6d4',
                    cursorColor: '#38bdf8',
                    barWidth: 2,
                    barGap: 1,
                    barRadius: 2,
                    height: 80,
                    url: '/dl/' + dropId
                });

                wavesurfer.on('ready', () => {
                    if (loading) loading.classList.add('hidden');
                    const dur = wavesurfer.getDuration();
                    document.getElementById('cutterTotalDuration').innerText = formatSecToTime(dur);
                    document.getElementById('cutEndTime').value = formatSecToTime(dur);
                });

                wavesurfer.on('timeupdate', (currentTime) => {
                    const curFormatted = formatSecToTime(currentTime);
                    document.getElementById('cutterCurrentTime').innerText = curFormatted;
                    const toggleTime = document.getElementById('waveToggleTime');
                    if (toggleTime) toggleTime.innerText = curFormatted;
                });

                wavesurfer.on('play', () => {
                    const icon = document.getElementById('waveToggleIcon');
                    if (icon) icon.innerText = '❚❚';
                    const btnText = document.getElementById('wavePlayText');
                    if (btnText) btnText.innerText = 'توقف موقت';
                });

                wavesurfer.on('pause', () => {
                    const icon = document.getElementById('waveToggleIcon');
                    if (icon) icon.innerText = '▶';
                    const btnText = document.getElementById('wavePlayText');
                    if (btnText) btnText.innerText = 'پخش';
                });

                wavesurfer.on('finish', () => {
                    const icon = document.getElementById('waveToggleIcon');
                    if (icon) icon.innerText = '▶';
                    const btnText = document.getElementById('wavePlayText');
                    if (btnText) btnText.innerText = 'پخش';
                });

                wavesurfer.on('error', (err) => {
                    console.error('WaveSurfer error:', err);
                    if (loading) loading.innerText = 'خطا در بارگذاری نمودار موج صوتی: ' + err;
                });
            } catch (err) {
                console.error('WaveSurfer init error:', err);
                if (loading) loading.innerText = 'خطا در راه‌اندازی پخش‌کننده صوتی.';
            }
        }

        function closeCutterModal() {
            if (wavesurfer) {
                try { wavesurfer.pause(); } catch (e) {}
            }
            const icon = document.getElementById('waveToggleIcon');
            if (icon) icon.innerText = '▶';
            document.getElementById('cutterModal').classList.add('hidden');
        }

        function toggleWavePlayPause() {
            if (wavesurfer) {
                wavesurfer.playPause();
            }
        }

        function stopWaveSurfer() {
            if (wavesurfer) {
                wavesurfer.stop();
                document.getElementById('wavePlayText').innerText = 'پخش';
            }
        }

        function setStartFromCursor() {
            if (wavesurfer) {
                const cur = wavesurfer.getCurrentTime();
                document.getElementById('cutStartTime').value = formatSecToTime(cur);
            }
        }

        function setEndFromCursor() {
            if (wavesurfer) {
                const cur = wavesurfer.getCurrentTime();
                document.getElementById('cutEndTime').value = formatSecToTime(cur);
            }
        }

        async function submitAudioCut() {
            const dropId = document.getElementById('cutterDropId').value;
            const startStr = document.getElementById('cutStartTime').value;
            const endStr = document.getElementById('cutEndTime').value;
            const startSec = parseTimeToSec(startStr);
            const endSec = parseTimeToSec(endStr);

            if (endSec > 0 && endSec <= startSec) {
                showToast('❌ زمان پایان باید بعد از زمان شروع باشد.');
                return;
            }

            const btn = document.getElementById('btnSubmitCut');
            btn.disabled = true;
            btn.innerText = '⏳ در حال برش صوت با FFmpeg...';

            try {
                const res = await fetch('/api/studio/cut', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json; charset=utf-8' },
                    body: JSON.stringify({
                        drop_id: dropId,
                        start_sec: startSec,
                        end_sec: endSec > 0 ? endSec : null
                    })
                });
                const data = await res.json();
                if (data.ok) {
                    showToast('✅ ' + (data.message || 'فایل با موفقیت برش یافت و به استودیو اضافه شد!'));
                    closeCutterModal();
                    refreshStudioList();
                } else {
                    showToast('❌ خطا: ' + (data.error || 'عملیات برش ناموفق بود.'));
                }
            } catch (err) {
                showToast('❌ خطای ارتباط با سرور: ' + err.message);
            } finally {
                btn.disabled = false;
                btn.innerHTML = '<span>✂️</span> برش و ایجاد فایل جدید';
            }
        }

        async function deleteStudioDrop(dropId) {
            if (!confirm('آیا از حذف این فایل و سشن رسانه از دیسک سرور مطمئن هستید؟')) return;
            try {
                const res = await fetch('/api/studio/delete', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json; charset=utf-8' },
                    body: JSON.stringify({ drop_id: dropId })
                });
                const data = await res.json();
                if (data.ok) {
                    const row = document.getElementById('row_' + dropId);
                    if (row) {
                        row.style.transition = 'all 0.4s ease';
                        row.style.opacity = '0';
                        row.style.transform = 'scale(0.95)';
                        setTimeout(() => { row.remove(); updateSelectedCount(); }, 400);
                    } else {
                        refreshStudioList();
                    }
                } else {
                    showToast('❌ خطا: ' + (data.error || 'حذف سشن ناموفق بود'));
                }
            } catch (err) {
                showToast('❌ خطای شبکه: ' + err.message);
            }
        }

        async function batchDeleteStudioDrops() {
            const ids = getSelectedDropIds();
            if (ids.length === 0) {
                showToast('⚠️ لطفاً حداقل یک فایل را برای حذف انتخاب فرمایید.');
                return;
            }
            if (!confirm(`آیا از حذف دائم ${ids.length} فایل انتخاب‌شده از حافظه و دیسک سرور مطمئن هستید؟`)) return;

            try {
                const res = await fetch('/api/studio/delete_batch', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json; charset=utf-8' },
                    body: JSON.stringify({ drop_ids: ids })
                });
                const data = await res.json();
                if (data.ok) {
                    ids.forEach(id => {
                        const row = document.getElementById('row_' + id);
                        if (row) {
                            row.style.transition = 'all 0.4s ease';
                            row.style.opacity = '0';
                            row.style.transform = 'scale(0.95)';
                            setTimeout(() => { row.remove(); updateSelectedCount(); }, 400);
                        }
                    });
                    const chkAll = document.getElementById('selectAllDrops');
                    if (chkAll) chkAll.checked = false;
                    setTimeout(() => { refreshStudioList(); }, 450);
                } else {
                    showToast('❌ خطا: ' + (data.error || 'حذف گروهی ناموفق بود'));
                }
            } catch (err) {
                showToast('❌ خطای شبکه: ' + err.message);
            }
        }

        function changeStudioSort(sortVal) {
            try {
                localStorage.setItem('unfinit_studio_sort', sortVal);
            } catch (e) {}
            refreshStudioList();
        }

        async function refreshStudioList() {
            const tbody = document.getElementById('studioTableBody');
            if (tbody) tbody.style.opacity = '0.5';
            try {
                let sortVal = 'newest';
                try {
                    sortVal = localStorage.getItem('unfinit_studio_sort') || 'newest';
                } catch (e) {}
                const sortSelect = document.getElementById('studioSortSelect');
                if (sortSelect && sortSelect.value !== sortVal) {
                    sortSelect.value = sortVal;
                }
                const res = await fetch('/api/studio/table_html?sort=' + encodeURIComponent(sortVal));
                const data = await res.json();
                if (data.ok && data.html) {
                    if (tbody) {
                        tbody.innerHTML = data.html;
                        tbody.style.opacity = '1';
                        const chkAll = document.getElementById('selectAllDrops');
                        if (chkAll) chkAll.checked = false;
                        updateSelectedCount();
                    }
                } else {
                    console.warn('Refresh studio table returned non-ok:', data);
                    if (tbody) tbody.style.opacity = '1';
                }
            } catch (err) {
                console.error('Failed to refresh studio table:', err);
                if (tbody) tbody.style.opacity = '1';
            }
        }

        async function cleanupStudioDrops() {
            if (!confirm('آیا می‌خواهید تمام سشن‌های تکراری و فایل‌های زائد به صورت هوشمند پاکسازی شوند؟')) return;
            const btn = document.getElementById('btnCleanupStudio');
            if (btn) {
                btn.disabled = true;
                btn.innerText = '⏳ در حال پاکسازی...';
            }
            try {
                const res = await fetch('/api/studio/cleanup', { method: 'POST' });
                const data = await res.json();
                if (data.ok) {
                    showToast('✅ ' + (data.message || 'سشن‌های تکراری با موفقیت پاکسازی شدند!'));
                    refreshStudioList();
                } else {
                    showToast('❌ خطا: ' + (data.error || 'پاکسازی ناموفق بود'));
                }
            } catch (err) {
                showToast('❌ خطای ارتباط: ' + err.message);
            } finally {
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = '<span>🧹</span> پاکسازی سشن‌های خالی و نامعتبر';
                }
            }
        }

        /**
         * تبدیل ارقام انگلیسی به فارسی جهت یکپارچگی طبق استاندارد زبان بصری
         */
        function toPersianDigits(n) {
            const farsiDigits = ['۰', '۱', '۲', '۳', '۴', '۵', '۶', '۷', '۸', '۹'];
            return String(n).replace(/[0-9]/g, function(w) { return farsiDigits[+w]; });
        }
        window.toPersianDigits = toPersianDigits;

        /**
         * متد تست ادمین برای دریافت نشانه امروز من
         * یک نشانه تصادفی از صفحات دانلود سایت را استعلام نموده و در دیالوگ شفاف نمایش می‌دهد.
         */
        async function testTodaySign() {
            const btn = document.getElementById('btnTestTodaySign');
            if (btn) {
                btn.disabled = true;
                btn.innerHTML = '<svg class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path></svg><span>در حال دریافت نشانه...</span>';
            }
            try {
                const res = await fetch('/api/sign/test');
                const data = await res.json();
                if (data.ok && data.sign) {
                    const s = data.sign;
                    showToast('🔮 نشانه تصادفی تست ادمین:\n\n' +
                          'عنوان: ' + (s.title || 'نشانه امروز') + '\n' +
                          'شماره صفحه: ' + toPersianDigits(s.page || 1) + '\n' +
                          'لینک فایل صوتی: ' + (s.audio_url || 'ندارد') + '\n' +
                          'لینک مستقیم: ' + (s.link || 'ندارد'));
                } else {
                    showToast('خطا در دریافت نشانه: ' + (data.error || 'پاسخ نامعتبر'));
                }
            } catch (err) {
                showToast('خطای ارتباط با سرور: ' + err.message);
            } finally {
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = '<svg class="w-4 h-4 stroke-[1.75]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456zM16.894 20.567L16.5 21.75l-.394-1.183a2.25 2.25 0 00-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 001.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 001.423 1.423l1.183.394-1.183.394a2.25 2.25 0 00-1.423 1.423z" /></svg><span>دریافت نشانه تصادفی (تست ادمین)</span>';
                }
            }
        }
        window.testTodaySign = testTodaySign;

        async function refreshFeedDiskCache() {
            const btn = document.getElementById('btnRefreshFeedCache');
            if (btn) {
                btn.disabled = true;
                btn.classList.add('opacity-50');
            }
            try {
                const res = await fetch('/api/feed/refresh', { method: 'POST' });
                const data = await res.json();
                if (data.ok) {
                    showToast('✅ ' + data.message + '\nلیست در چند لحظه آینده به‌روزرسانی می‌شود.');
                    setTimeout(() => {
                        if (typeof fetchFeedDownloads === 'function') window.fetchFeedDownloads(false);
                    }, 2500);
                } else {
                    showToast('خطا در به‌روزرسانی کش: ' + (data.error || 'ناشناخته'));
                }
            } catch (e) {
                showToast('خطای ارتباط با سرور: ' + e.message);
            } finally {
                if (btn) {
                    btn.disabled = false;
                    btn.classList.remove('opacity-50');
                }
            }
        }
        window.refreshFeedDiskCache = refreshFeedDiskCache;

        async function saveAllCategories() {
            const btn = document.getElementById('btnSaveCategories');
            if (btn) {
                btn.disabled = true;
                btn.classList.add('opacity-50');
            }
            try {
                const rows = document.querySelectorAll('.category-edit-row');
                const updated = [];
                rows.forEach(r => {
                    const id = parseInt(r.getAttribute('data-id'));
                    const slug = r.getAttribute('data-slug') || '';
                    const url = r.getAttribute('data-url') || '';
                    const path = r.getAttribute('data-path') || '';
                    const emoji = (r.querySelector('.cat-emoji-input')?.value || '').trim() || '💎';
                    const title = (r.querySelector('.cat-title-input')?.value || '').trim();
                    updated.push({ id, slug, url, path, emoji, title });
                });

                const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                const res = await fetch('/api/categories/update', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json; charset=utf-8', 'Authorization': 'Bearer ' + pwd, 'X-Admin-Password': pwd },
                    body: JSON.stringify({ categories: updated, admin_password: pwd })
                });
                const data = await res.json();
                if (data.ok) {
                    showToast('✅ ' + data.message);
                } else {
                    showToast('خطا در ذخیره دسته‌بندی‌ها: ' + (data.error || 'ناشناخته'));
                }
            } catch (e) {
                showToast('خطای ارتباط با سرور: ' + e.message);
            } finally {
                if (btn) {
                    btn.disabled = false;
                    btn.classList.remove('opacity-50');
                }
            }
        }
        window.saveAllCategories = saveAllCategories;

        let currentFeedPage = 1;
        let currentFeedCategory = '';
        const totalFeedPages = 39;
        window.currentFeedPage = 1;
        window.currentFeedCategory = '';

        async function loadFeedCategories() {
            const bar = document.getElementById('feedCategoriesBar');
            if (!bar) return;
            try {
                const res = await fetch('/api/feed/categories');
                const data = await res.json();
                if (data.ok && Array.isArray(data.categories) && data.categories.length > 0) {
                    const loadingEl = document.getElementById('feedCategoriesLoading');
                    if (loadingEl) loadingEl.remove();

                    const allBtn = '<button type="button" onclick="selectFeedCategory(\'\')" class="feed-cat-btn px-3 py-1.5 rounded-lg text-xs font-bold transition whitespace-nowrap ' + (!currentFeedCategory ? 'theme-accent-btn active' : 'theme-card-btn') + '" data-cat="">' +
                        '<span>🌐 تمام دانلودها</span>' +
                    '</button>';

                    const catBtns = data.categories.filter(function(c) {
                        return c.id !== 1 && c.slug !== 'all-downloads' && c.title !== 'تمام دانلودها';
                    }).map(function(c) {
                        const isActive = currentFeedCategory === c.slug;
                        const btnClass = isActive ? 'theme-accent-btn active' : 'theme-card-btn';
                        const safeTitle = (c.title || '').replace(/'/g, "\\'");
                        const catEmoji = c.emoji ? (c.emoji + ' ') : '';
                        return '<button type="button" onclick="selectFeedCategory(\'' + c.slug + '\')" class="feed-cat-btn px-3 py-1.5 rounded-lg text-xs font-bold transition whitespace-nowrap ' + btnClass + '" data-cat="' + c.slug + '">' +
                            '<span>' + catEmoji + safeTitle + '</span>' +
                        '</button>';
                    }).join('');

                    bar.innerHTML = allBtn + catBtns;
                }
            } catch (err) {
                console.debug('loadFeedCategories error', err);
            }
        }
        window.loadFeedCategories = loadFeedCategories;

        function selectFeedCategory(slug) {
            currentFeedCategory = slug || '';
            window.currentFeedCategory = currentFeedCategory;
            currentFeedPage = 1;
            window.currentFeedPage = 1;

            const btns = document.querySelectorAll('.feed-cat-btn');
            btns.forEach(function(b) {
                if (b.getAttribute('data-cat') === currentFeedCategory) {
                    b.className = 'feed-cat-btn px-3 py-1.5 rounded-lg text-xs font-bold transition whitespace-nowrap theme-accent-btn active';
                } else {
                    b.className = 'feed-cat-btn px-3 py-1.5 rounded-lg text-xs font-bold transition whitespace-nowrap theme-card-btn';
                }
            });

            fetchFeedDownloads(false, 1, currentFeedCategory);
        }
        window.selectFeedCategory = selectFeedCategory;

        async function createCourseFromCurrentCategory() {
            const slug = currentFeedCategory || 'free-download';
            const catName = prompt('عنوان دوره جدید برای این دسته‌بندی را وارد فرمایید:', 'دوره آموزشی ' + (slug || 'هدایای دانلودی'));
            if (!catName) return;
            const btn = document.getElementById('btnCreateCourseFromCat');
            if (btn) {
                btn.disabled = true;
                btn.innerHTML = '<svg class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path></svg><span>در حال ساخت دوره...</span>';
            }
            try {
                const res = await fetch('/api/courses/create-from-category', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json; charset=utf-8' },
                    body: JSON.stringify({ category_id: slug, course_name: catName })
                });
                const data = await res.json();
                if (data.ok) {
                    showToast('✅ ' + (data.message || 'دوره با موفقیت ساخته شد!'));
                    switchTab('courses');
                } else {
                    showToast('❌ خطا در ساخت دوره: ' + (data.error || 'ناشناخته'));
                }
            } catch(err) {
                showToast('❌ خطای ارتباطی: ' + err.message);
            } finally {
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = '<svg class="w-4 h-4 stroke-[2]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" /></svg><span>✨ ساخت دوره از این دسته‌بندی</span>';
                }
            }
        }
        window.createCourseFromCurrentCategory = createCourseFromCurrentCategory;

        async function fetchFeedDownloads(force, page, category) {
            const container = document.getElementById('feedDownloadsContainer');
            const btn = document.getElementById('btnRefreshFeed');
            if (!container) return;
            if (typeof page === 'number' && page >= 1) {
                currentFeedPage = page;
                window.currentFeedPage = page;
            }
            if (category !== undefined) {
                currentFeedCategory = category;
                window.currentFeedCategory = category;
            }
            const curPageEl = document.getElementById('feedCurrentPage');
            const curPageBottomEl = document.getElementById('feedCurrentPageBottom');
            if (curPageEl) curPageEl.textContent = toPersianDigits(currentFeedPage);
            if (curPageBottomEl) curPageBottomEl.textContent = toPersianDigits(currentFeedPage);

            if (btn) {
                btn.disabled = true;
                btn.innerHTML = '<svg class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path></svg><span>در حال رصد سایت...</span>';
            }
            const loadingMsg = currentFeedCategory
                ? 'در حال دریافت فایل‌های دسته‌بندی انتخابی...'
                : 'در حال دریافت ۲۵ هدیه دانلودی صفحه ' + toPersianDigits(currentFeedPage) + ' از سایت...';
            if (force || container.children.length === 0 || container.innerText.includes('در حال بارگذاری')) {
                container.innerHTML = '<div class="col-span-full text-center py-6 text-xs text-slate-400 font-medium">' + loadingMsg + '</div>';
            }
            try {
                const catParam = currentFeedCategory ? ('&cat=' + encodeURIComponent(currentFeedCategory)) : '';
                const res = await fetch('/api/feed/latest?page=' + currentFeedPage + '&limit=25' + (force ? '&force=1' : '') + catParam);
                const data = await res.json();
                if (data.ok && Array.isArray(data.items) && data.items.length > 0) {
                    container.innerHTML = data.items.map(function(item) {
                        const title = (item.title || 'هدیه دانلودی سایت').replace(/"/g, '&quot;');
                        const fileNum = item.file_number ? '<span class="absolute top-2.5 right-2.5 px-2.5 py-0.5 rounded-lg bg-black/80 backdrop-blur-md text-cyan-300 border border-white/10 text-[10px] font-bold shadow-md">' + item.file_number + '</span>' : '';
                        let c_url = item.cover_url || '';
                        if (c_url && c_url.startsWith('/')) {
                            c_url = 'https://abasmanesh.com' + c_url;
                        }
                        
                        const cover = c_url
                            ? '<div class="relative w-full aspect-video overflow-hidden rounded-t-2xl bg-slate-950/70 border-b border-white/5">' +
                                '<img src="' + c_url + '" alt="' + title + '" referrerpolicy="no-referrer" loading="lazy" class="w-full h-full object-cover transition-transform duration-500 hover:scale-105" onerror="this.onerror=null; this.src=&apos;https://abasmanesh.com/assets/images/logo.png&apos;;">' +
                                fileNum +
                              '</div>'
                            : '<div class="w-full aspect-video overflow-hidden rounded-t-2xl  border-b border-white/5 flex items-center justify-center text-3xl">🎧</div>';

                        const audioLink = item.audio_url || '';
                        const videoLink = item.video_url || '';
                        const primaryUrl = audioLink || videoLink || (item.links && item.links[0]) || '';
                        const safeUrl = primaryUrl.replace(/'/g, "\\'");
                        const safeTitle = title.replace(/'/g, "\\'");
                        const safeAudio = (audioLink || '').replace(/'/g, "\\'");
                        const safeVideo = (videoLink || '').replace(/'/g, "\\'");
                        const safeSource = (item.source_url || '').replace(/'/g, "\\'");
                        
                        let audioBtn = '';
                        if (audioLink) {
                            audioBtn = '<a href="' + audioLink + '" target="_blank" class="theme-card-btn py-1.5 px-2.5 rounded-lg text-cyan-300 flex items-center justify-center gap-1.5 transition text-xs font-medium border border-slate-700/60 hover:border-cyan-500/50">' +
                                '<svg class="w-3.5 h-3.5 stroke-[2]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M19.114 5.636a9 9 0 010 12.728M16.463 8.288a5.25 5.25 0 010 7.424M6.75 8.25l4.72-4.72a.75.75 0 011.28.53v15.88a.75.75 0 01-1.28.53l-4.72-4.72H4.51c-.88 0-1.704-.507-1.938-1.354A9.01 9.01 0 012.25 12c0-.83.112-1.633.322-2.396C2.806 8.756 3.63 8.25 4.51 8.25H6.75z" /></svg>' +
                                '<span>صوت</span>' +
                            '</a>';
                        }
                        let videoBtn = '';
                        if (videoLink) {
                            videoBtn = '<a href="' + videoLink + '" target="_blank" class="theme-card-btn py-1.5 px-2.5 rounded-lg text-purple-300 flex items-center justify-center gap-1.5 transition text-xs font-medium border border-slate-700/60 hover:border-purple-500/50">' +
                                '<svg class="w-3.5 h-3.5 stroke-[2]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /><path stroke-linecap="round" stroke-linejoin="round" d="M15.91 11.672a.375.375 0 010 .656l-5.603 3.113a.375.375 0 01-.557-.328V8.887c0-.286.307-.466.557-.327l5.603 3.112z" /></svg>' +
                                '<span>ویدیو</span>' +
                            '</a>';
                        }

                        const linksGrid = (audioBtn || videoBtn)
                            ? '<div class="grid grid-cols-2 gap-2">' + (audioBtn || '<div></div>') + (videoBtn || '<div></div>') + '</div>'
                            : '<button type="button" onclick="transferFeedDownload(\'' + safeUrl + '\', \'' + safeTitle + '\', \'' + safeAudio + '\', \'' + safeVideo + '\', \'' + safeSource + '\')" class="w-full theme-card-btn py-1.5 px-2.5 rounded-lg text-orange-300 flex items-center justify-center gap-1.5 transition text-xs font-medium border border-orange-500/30 hover:border-orange-500/50"><svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg><span>بروزرسانی لینک‌ها</span></button>';

                        return '<div class="glass rounded-2xl border border-slate-800/80 hover:border-cyan-500/40 transition-all flex flex-col justify-between overflow-hidden shadow-lg hover:shadow-cyan-950/20 group" style="background: var(--card-bg); border-color: var(--card-border);">' +
                            cover +
                            '<div class="p-4 flex flex-col justify-between flex-1 gap-3">' +
                                '<div class="space-y-2">' +
                                    '<div class="flex items-center justify-between text-[11px] text-slate-400">' +
                                        '<span class="text-cyan-400 font-semibold">' + (item.tag || 'هدیه دانلودی') + '</span>' +
                                        '<span>' + (item.published_at || '') + '</span>' +
                                    '</div>' +
                                    '<h3 class="text-xs md:text-sm font-bold text-slate-100 line-clamp-2 leading-relaxed group-hover:text-cyan-300 transition-colors" title="' + title + '">' +
                                        title +
                                    '</h3>' +
                                '</div>' +
                                '<div class="flex flex-col gap-2 pt-3 border-t border-white/5">' +
                                    linksGrid +
                                    '<button type="button" onclick="transferFeedDownload(\'' + safeUrl + '\', \'' + safeTitle + '\', \'' + safeAudio + '\', \'' + safeVideo + '\', \'' + safeSource + '\')" class="w-full theme-accent-btn py-2 px-3 rounded-xl text-xs font-bold transition flex items-center justify-center gap-1.5 shadow-md cursor-pointer">' +
                                        '<svg class="w-4 h-4 stroke-[2]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" /></svg>' +
                                        '<span>انتقال به ربات</span>' +
                                    '</button>' +
                                '</div>' +
                            '</div>' +
                        '</div>';
                    }).join('');
                } else {
                    container.innerHTML = '<div class="col-span-full text-center py-6 text-xs text-rose-400 font-medium">❌ دریافت هدایای دانلودی ناموفق بود یا فایلی یافت نشد.</div>';
                }
            } catch (err) {
                container.innerHTML = '<div class="col-span-full text-center py-6 text-xs text-rose-400 font-medium">❌ خطای ارتباط با سرور: ' + err.message + '</div>';
            } finally {
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = '<svg class="w-4 h-4 stroke-[1.75]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" /></svg><span>به‌روزرسانی صفحه</span>';
                }
            }
        }

        function changeFeedPage(targetPage) {
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
        }

        let pendingFeedDispatchUrl = '';
        let pendingFeedDispatchTitle = '';
        let pendingFeedAudioUrl = '';
        let pendingFeedVideoUrl = '';
        let pendingFeedActiveFormat = 'audio';

        function setDispatchFormat(fmt) {
            pendingFeedActiveFormat = fmt;
            const btnAudio = document.getElementById('btnFormatAudio');
            const btnVideo = document.getElementById('btnFormatVideo');
            if (fmt === 'audio') {
                if (btnAudio) {
                    btnAudio.className = 'py-2 px-3 rounded-xl border text-xs font-bold transition flex items-center justify-center gap-1.5 theme-accent-btn';
                }
                if (btnVideo) {
                    btnVideo.className = 'py-2 px-3 rounded-xl border border-slate-700 text-slate-300 bg-slate-800/80 hover:bg-slate-700 text-xs font-bold transition flex items-center justify-center gap-1.5';
                }
                pendingFeedDispatchUrl = pendingFeedAudioUrl || pendingFeedVideoUrl;
            } else {
                if (btnVideo) {
                    btnVideo.className = 'py-2 px-3 rounded-xl border text-xs font-bold transition flex items-center justify-center gap-1.5 theme-accent-btn';
                }
                if (btnAudio) {
                    btnAudio.className = 'py-2 px-3 rounded-xl border border-slate-700 text-slate-300 bg-slate-800/80 hover:bg-slate-700 text-xs font-bold transition flex items-center justify-center gap-1.5';
                }
                pendingFeedDispatchUrl = pendingFeedVideoUrl || pendingFeedAudioUrl;
            }
        }

        function openFeedDispatchModal(url, title, audioUrl, videoUrl, sourceUrl) {
            pendingFeedAudioUrl = audioUrl || (url && url.toLowerCase().endsWith('.mp3') ? url : '');
            pendingFeedVideoUrl = videoUrl || (url && url.toLowerCase().endsWith('.mp4') ? url : '');
            if (!pendingFeedAudioUrl && !pendingFeedVideoUrl) {
                pendingFeedAudioUrl = url;
            }
            pendingFeedDispatchUrl = pendingFeedAudioUrl || pendingFeedVideoUrl || url;
            pendingFeedDispatchTitle = title || 'هدیه دانلودی';
            const titleEl = document.getElementById('feedDispatchModalTitle');
            if (titleEl) titleEl.textContent = pendingFeedDispatchTitle;

            setDispatchFormat(pendingFeedAudioUrl ? 'audio' : 'video');

            const courseSelect = document.getElementById('feedCourseSelect');
            if (courseSelect) {
                courseSelect.innerHTML = '';
                const cache = window.COURSES_CACHE || window.coursesData || {};
                const pids = Object.keys(cache);
                if (pids.length === 0) {
                    courseSelect.innerHTML = '<option value="">(هیچ دوره‌ای در سیستم ثبت نشده است)</option>';
                } else {
                    let defaultPid = '';
                    pids.forEach(function(pid) {
                        const c = cache[pid];
                        const opt = document.createElement('option');
                        opt.value = c.product_id || pid;
                        const isFree = (c.price === 0 || c.price === '0' || c.is_free || (c.name && c.name.includes('توحید')));
                        if (isFree && !defaultPid) {
                            defaultPid = opt.value;
                        }
                        opt.textContent = (isFree ? '🎁 ' : '🎓 ') + (c.name || pid);
                        courseSelect.appendChild(opt);
                    });
                    if (defaultPid) {
                        courseSelect.value = defaultPid;
                    }
                }
            }

            const modal = document.getElementById('feedDispatchModal');
            if (modal) modal.classList.remove('hidden');
        }

        function closeFeedDispatchModal() {
            const modal = document.getElementById('feedDispatchModal');
            if (modal) modal.classList.add('hidden');
            pendingFeedDispatchUrl = '';
            pendingFeedDispatchTitle = '';
            pendingFeedAudioUrl = '';
            pendingFeedVideoUrl = '';
        }

        async function addFeedToCourseEpisodes() {
            const courseSelect = document.getElementById('feedCourseSelect');
            const pid = courseSelect ? courseSelect.value : '';
            const url = pendingFeedDispatchUrl || pendingFeedAudioUrl || pendingFeedVideoUrl;
                        const title = pendingFeedDispatchTitle;
            const meta_override = !!document.getElementById('chkOverrideMeta')?.checked;
            const meta_title = document.getElementById('metaTitleInput')?.value || title;
            const meta_artist = document.getElementById('metaArtistInput')?.value || '@abasmanesh365';

            if (!pid) {
                showToast('لطفاً یک دوره را انتخاب فرمایید.');
                return;
            }
            if (!url) {
                showToast('آدرس فایل معتبر نیست.');
                return;
            }
            const btn = document.getElementById('btnAddFeedToCourse');
            if (btn) {
                btn.disabled = true;
                btn.innerText = '⏳ در حال افزودن...';
            }
            try {
                const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                const res = await fetch('/api/courses/episodes/add', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json; charset=utf-8',
                        'Authorization': 'Bearer ' + pwd,
                        'X-Admin-Password': pwd
                    },
                    body: JSON.stringify({
                        product_id: pid,
                        title: title,
                        url: url,
                        filename: title ? (title.replace(/[^\w\s\-\.\u0600-\u06FF]/gi, '') + (pendingFeedActiveFormat === 'video' ? '.mp4' : '.mp3')) : ''
                    })
                });
                const data = await res.json();
                if (data.ok) {
                    showToast('✅ ' + (data.message || 'فایل با موفقیت به سرفصل‌های دوره افزوده شد!'));
                    closeFeedDispatchModal();
                } else {
                    showToast('❌ خطا در افزودن به سرفصل‌ها: ' + (data.error || 'ناموفق'));
                }
            } catch (err) {
                showToast('❌ خطای ارتباط با سرور: ' + err.message);
            } finally {
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = '<span>📦</span> افزودن به عنوان قسمت جدید این دوره';
                }
            }
        }

        async function executeFeedMultiDispatch() {
            const targets = [];
            if (document.getElementById('chkDispatchTg')?.checked) targets.push('telegram');
            if (document.getElementById('chkDispatchBale')?.checked) targets.push('bale');
            if (document.getElementById('chkDispatchRubika')?.checked) targets.push('rubika_user');
            if (document.getElementById('chkDispatchSoroush')?.checked) targets.push('soroush');

            if (targets.length === 0) {
                showToast('❌ لطفاً حداقل یک پلتفرم مقصد را انتخاب فرمایید.');
                return;
            }

            const wantAudio = !!document.getElementById('chkFormatAudio')?.checked;
            const wantVideo = !!document.getElementById('chkFormatVideo')?.checked;
            const urlsToDispatch = [];
            if (wantAudio && pendingFeedAudioUrl) {
                urlsToDispatch.push({ url: pendingFeedAudioUrl, label: 'صوتی MP3' });
            }
            if (wantVideo && pendingFeedVideoUrl) {
                urlsToDispatch.push({ url: pendingFeedVideoUrl, label: 'تصویری MP4' });
            }
            if (urlsToDispatch.length === 0) {
                const fallbackUrl = pendingFeedDispatchUrl || pendingFeedAudioUrl || pendingFeedVideoUrl;
                if (fallbackUrl) urlsToDispatch.push({ url: fallbackUrl, label: 'رسانه' });
            }

                        const title = pendingFeedDispatchTitle;
            const meta_override = !!document.getElementById('chkOverrideMeta')?.checked;
            const meta_title = document.getElementById('metaTitleInput')?.value || title;
            const meta_artist = document.getElementById('metaArtistInput')?.value || '@abasmanesh365';

            closeFeedDispatchModal();
            if (urlsToDispatch.length === 0) return;

            const resBox = document.getElementById('dispatchResult');
            if (resBox) {
                resBox.className = 'mt-4 p-3 rounded-xl text-xs block bg-slate-800 text-slate-300 border border-slate-700';
                resBox.innerText = '⏳ در حال دانلود و ارسال همزمان هدیه: ' + title + ' به پلتفرم‌های منتخب...';
            }
            try {
                const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                let allSuccess = true;
                for (const item of urlsToDispatch) {
                    const res = await fetch('/api/dispatch_url', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json; charset=utf-8',
                            'Authorization': 'Bearer ' + pwd,
                            'X-Admin-Password': pwd
                        },
                        body: JSON.stringify({ url: item.url, targets: targets, target: targets.join(','), meta_override: meta_override, meta_title: meta_title, meta_artist: meta_artist })
                    });
                    const data = await res.json();
                    if (!data.ok) allSuccess = false;
                }
                if (allSuccess) {
                    showToast('✅ ارسال با موفقیت به ' + targets.join(' و ') + ' انجام شد!');
                    if (resBox) {
                        resBox.className = 'mt-4 p-3 rounded-xl text-xs block bg-emerald-950 text-emerald-300 border border-emerald-700';
                        resBox.innerText = '✅ نسخه(های) انتخابی فایل هدیه با موفقیت ارسال شد!';
                    }
                } else {
                    showToast('⚠️ ارسال فایل‌ها به برخی مقاصد انجام شد.');
                }
            } catch (err) {
                showToast('❌ خطای ارتباط با سرور: ' + err.message);
            }
        }

        async function executeFeedDispatch(target) {
            const url = pendingFeedDispatchUrl || pendingFeedAudioUrl || pendingFeedVideoUrl;
                        const title = pendingFeedDispatchTitle;
            const meta_override = !!document.getElementById('chkOverrideMeta')?.checked;
            const meta_title = document.getElementById('metaTitleInput')?.value || title;
            const meta_artist = document.getElementById('metaArtistInput')?.value || '@abasmanesh365';

            closeFeedDispatchModal();
            if (!url) return;

            const directInput = document.getElementById('directUrl');
            if (directInput) {
                directInput.value = url;
            }
            const resBox = document.getElementById('dispatchResult');
            if (resBox) {
                resBox.className = 'mt-4 p-3 rounded-xl text-xs block bg-slate-800 text-slate-300 border border-slate-700';
                resBox.innerText = '⏳ در حال دانلود و پردازش استریم هدیه: ' + title + ' ... لطفاً شکیبا باشید.';
            }
            try {
                const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                const res = await fetch('/api/dispatch_url', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json; charset=utf-8',
                        'Authorization': 'Bearer ' + pwd,
                        'X-Admin-Password': pwd
                    },
                    body: JSON.stringify({ url: url, target: target || 'all', meta_override: meta_override, meta_title: meta_title, meta_artist: meta_artist })
                });
                const data = await res.json();
                if (data.ok) {
                    showToast('✅ فایل هدیه با موفقیت دانلود و به ' + (data.target || 'پیام‌رسان‌ها') + ' منتقل شد!');
                    if (resBox) {
                        resBox.className = 'mt-4 p-3 rounded-xl text-xs block bg-emerald-950 text-emerald-300 border border-emerald-700';
                        resBox.innerText = '✅ ' + (data.message || 'فایل هدیه با موفقیت دانلود و ارسال شد!');
                    }
                } else {
                    showToast('❌ خطا در دانلود و ارسال: ' + (data.error || 'عملیات ناموفق بود'));
                    if (resBox) {
                        resBox.className = 'mt-4 p-3 rounded-xl text-xs block bg-rose-950 text-rose-300 border border-rose-700';
                        resBox.innerText = '❌ خطا: ' + (data.error || 'ناموفق');
                    }
                }
            } catch (err) {
                showToast('❌ خطای ارتباط با سرور: ' + err.message);
            }
        }

        async function transferFeedDownload(url, title, audioUrl, videoUrl, sourceUrl, btn) {
            if (!audioUrl && !videoUrl) {
                const badge = document.getElementById('crawlerStatusBadge');
                if (badge && badge.innerText.includes('OFFLINE')) {
                    showToast('شما به حساب مرجع متصل نیستید. لطفاً ابتدا وارد حساب شوید.');
                    const m = document.getElementById('feedAuthModal');
                    if (m) m.classList.remove('hidden');
                    return;
                }
                if (sourceUrl) {
                    try {
                        const loadingToast = document.createElement('div');
                        loadingToast.id = 'rescrapToast';
                        loadingToast.className = 'fixed bottom-4 right-4 bg-slate-800 border border-orange-500 text-white px-4 py-2 rounded-xl text-xs z-50';
                        loadingToast.innerText = '⏳ در حال دریافت لینک‌های دانلود از سایت اصلی...';
                        document.body.appendChild(loadingToast);

                        const res = await fetch('/api/crawler/rescrap-item', { method: 'POST', body: JSON.stringify({ url: sourceUrl }) });
                        const data = await res.json();
                        document.body.removeChild(loadingToast);
                        if (data.ok && (data.audio_url || data.video_url || data.url)) {
                            if (btn && btn.parentElement) {
                                const safeA = (data.audio_url || '').replace(/'/g, "\'");
                                const safeV = (data.video_url || '').replace(/'/g, "\'");
                                let newHtml = '<div class="grid grid-cols-2 gap-2">';
                                if (data.audio_url) {
                                    newHtml += '<a href="' + data.audio_url + '" target="_blank" class="theme-card-btn py-1.5 px-2.5 rounded-lg text-cyan-300 flex items-center justify-center gap-1.5 transition text-xs font-medium border border-slate-700/60 hover:border-cyan-500/50">' +
                                        '<svg class="w-3.5 h-3.5 stroke-[2]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M19.114 5.636a9 9 0 010 12.728M16.463 8.288a5.25 5.25 0 010 7.424M6.75 8.25l4.72-4.72a.75.75 0 011.28.53v15.88a.75.75 0 01-1.28.53l-4.72-4.72H4.51c-.88 0-1.704-.507-1.938-1.354A9.01 9.01 0 012.25 12c0-.83.112-1.633.322-2.396C2.806 8.756 3.63 8.25 4.51 8.25H6.75z" /></svg>' +
                                        '<span>صوت</span>' +
                                    '</a>';
                                } else {
                                    newHtml += '<div></div>';
                                }
                                if (data.video_url) {
                                    newHtml += '<a href="' + data.video_url + '" target="_blank" class="theme-card-btn py-1.5 px-2.5 rounded-lg text-purple-300 flex items-center justify-center gap-1.5 transition text-xs font-medium border border-slate-700/60 hover:border-purple-500/50">' +
                                        '<svg class="w-3.5 h-3.5 stroke-[2]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /><path stroke-linecap="round" stroke-linejoin="round" d="M15.91 11.672a.375.375 0 010 .656l-5.603 3.113a.375.375 0 01-.557-.328V8.887c0-.286.307-.466.557-.327l5.603 3.112z" /></svg>' +
                                        '<span>ویدیو</span>' +
                                    '</a>';
                                } else {
                                    newHtml += '<div></div>';
                                }
                                newHtml += '</div>';
                                btn.outerHTML = newHtml;
                            }
                            openFeedDispatchModal(data.url || data.audio_url || data.video_url, title, data.audio_url, data.video_url, sourceUrl);
                        } else {
                            showToast('❌ آدرس دانلودی برای این آیتم در سرور یافت نشد.');
                        }
                    } catch (e) {
                        const tb = document.getElementById('rescrapToast');
                        if (tb) tb.remove();
                        showToast('❌ خطای ارتباط با سرور: ' + e.message);
                    }
                } else {
                    showToast('❌ آدرس دانلودی برای این آیتم یافت نشد.');
                }
            } else {
                openFeedDispatchModal(url, title, audioUrl, videoUrl, sourceUrl);
            }
        }

        // Initialize Studio Sort Select and Feed from localStorage / API
        window.addEventListener('DOMContentLoaded', function() {
            try {
                const savedSort = localStorage.getItem('unfinit_studio_sort') || 'newest';
                const sortSelect = document.getElementById('studioSortSelect');
                if (sortSelect) {
                    sortSelect.value = savedSort;
                }
                const curTab = localStorage.getItem('unfinit_active_tab') || 'dashboard';
                if (curTab === 'downloads' && typeof window.lazyLoadDownloadsFeed === 'function') {
                    window.lazyLoadDownloadsFeed();
                }
                if (typeof window.initProductSubtabsDragAndDrop === 'function') {
                    window.initProductSubtabsDragAndDrop();
                }
            } catch (e) {}
        });

                let currentSvgContent = '';
                let currentSvgFilename = 'vector.svg';

                function setSvgColor(hex) {
                    const picker = document.getElementById('svgRecolorPicker');
                    const input = document.getElementById('svgHexInput');
                    if (picker) picker.value = hex;
                    if (input) input.value = hex;
                }

                function syncSvgColorPicker(val) {
                    const input = document.getElementById('svgHexInput');
                    if (input) input.value = val;
                }

                function syncSvgHexInput(val) {
                    val = (val || '').trim();
                    if (val && !val.startsWith('#')) val = '#' + val;
                    const picker = document.getElementById('svgRecolorPicker');
                    if (picker && /^#[0-9A-Fa-f]{6}$/.test(val)) {
                        picker.value = val;
                    }
                }

                function renderSvgInPreview(svgText) {
                    currentSvgContent = svgText || '';
                    const previewEl = document.getElementById('svgLivePreview');
                    const badgeEl = document.getElementById('svgDimensionsBadge');
                    if (previewEl) {
                        if (!svgText) {
                            previewEl.innerHTML = '<span class="text-xs text-slate-500">فایل SVG انتخاب شده در اینجا رسم می‌شود</span>';
                            if (badgeEl) badgeEl.textContent = '-';
                            return;
                        }
                        previewEl.innerHTML = svgText;
                        const svgEl = previewEl.querySelector('svg');
                        if (svgEl) {
                            svgEl.style.maxWidth = '100%';
                            svgEl.style.maxHeight = '240px';
                            svgEl.style.height = 'auto';
                            svgEl.style.display = 'block';
                            svgEl.style.margin = 'auto';
                            const w = svgEl.getAttribute('width') || '';
                            const h = svgEl.getAttribute('height') || '';
                            const vb = svgEl.getAttribute('viewBox') || '';
                            if (badgeEl) {
                                badgeEl.textContent = (w && h) ? (w + ' × ' + h) : (vb ? ('viewBox: ' + vb) : 'SVG Vector');
                            }
                        }
                    }
                }

                function handleSvgFileSelected(files) {
                    if (!files || files.length === 0) return;
                    const file = files[0];
                    currentSvgFilename = file.name || 'vector.svg';
                    const reader = new FileReader();
                    reader.onload = function(e) {
                        renderSvgInPreview(e.target.result);
                    };
                    reader.readAsText(file);
                }

                async function handleSvgRecolor() {
                    if (!currentSvgContent) {
                        showToast('لطفاً ابتدا یک فایل وکتور SVG انتخاب نموده یا متنی وارد نمایید.');
                        return;
                    }
                    const hexInput = document.getElementById('svgHexInput');
                    const color = (hexInput ? hexInput.value : '#FFFFFF') || '#FFFFFF';
                    const btn = document.getElementById('btnSvgRecolor');
                    if (btn) {
                        btn.disabled = true;
                        btn.innerHTML = '<span>⏳</span> در حال تغییر رنگ...';
                    }
                    try {
                        const res = await fetch('/api/media/recolor-svg', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json; charset=utf-8',
                                'X-Admin-Password': window.currentAdminPassword || ''
                            },
                            body: JSON.stringify({
                                svg: currentSvgContent,
                                color: color,
                                filename: currentSvgFilename
                            })
                        });
                        const data = await res.json();
                        if (data.ok && data.svg) {
                            renderSvgInPreview(data.svg);
                            showToast('✅ رنگ اجزای وکتور با موفقیت به ' + color + ' تغییر یافت.');
                        } else {
                            showToast('❌ خطا در تغییر رنگ وکتور: ' + (data.error || 'ناموفق'));
                        }
                    } catch (err) {
                        showToast('❌ خطای ارتباط با سرور: ' + err.message);
                    } finally {
                        if (btn) {
                            btn.disabled = false;
                            btn.innerHTML = '<span>🎨</span> اعمال تغییر رنگ';
                        }
                    }
                }

                function downloadCurrentSvg() {
                    if (!currentSvgContent) {
                        showToast('فایل SVG فعالی برای دانلود وجود ندارد.');
                        return;
                    }
                    const blob = new Blob([currentSvgContent], { type: 'image/svg+xml;charset=utf-8' });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = currentSvgFilename || 'vector.svg';
                    document.body.appendChild(a);
                    a.click();
                    a.remove();
                    setTimeout(function() { URL.revokeObjectURL(url); }, 1000);
                }

                async function handleGenerateTextSvg() {
                    const textInput = document.getElementById('svgTextInput');
                    const sizeInput = document.getElementById('svgTextSizeInput');
                    const hexInput = document.getElementById('svgHexInput');
                    const text = (textInput ? textInput.value : '').trim();
                    const fontSize = parseInt(sizeInput ? sizeInput.value : '48') || 48;
                    const fill = (hexInput ? hexInput.value : '#FFFFFF') || '#FFFFFF';

                    if (!text) {
                        showToast('لطفاً ابتدا متن مورد نظر را وارد نمایید.');
                        return;
                    }

                    try {
                        const res = await fetch('/api/media/text-to-svg', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json; charset=utf-8',
                                'X-Admin-Password': window.currentAdminPassword || ''
                            },
                            body: JSON.stringify({
                                text: text,
                                font_size: fontSize,
                                fill: fill
                            })
                        });
                        const data = await res.json();
                        if (data.ok && data.svg) {
                            currentSvgFilename = (text.replace(/[^\w\s\-\.\u0600-\u06FF]/gi, '').slice(0, 20) || 'typography') + '.svg';
                            renderSvgInPreview(data.svg);
                            showToast('✅ وکتور متنی با موفقیت ایجاد شد.');
                        } else {
                            showToast('❌ خطا در تولید وکتور متنی: ' + (data.error || 'ناموفق'));
                        }
                    } catch (err) {
                        showToast('❌ خطای ارتباط با سرور: ' + err.message);
                    }
                }

                async function handleSvgConvert(e) {
                    if (e) e.preventDefault();
                    const fileInput = document.getElementById('svgFileInput');
                    const formatSelect = document.getElementById('svgOutputFormat');
                    const btn = document.getElementById('btnSvgConvert');
                    const resultDiv = document.getElementById('svgConvertResult');

                    const hasFile = fileInput && fileInput.files && fileInput.files.length > 0;
                    if (!hasFile && !currentSvgContent) {
                        showToast('لطفاً ابتدا یک فایل وکتور SVG انتخاب فرمایید یا از بخش ساخت وکتور استفاده نمایید.');
                        return;
                    }

                    const format = (formatSelect ? formatSelect.value : 'png') || 'png';
                    let fname = hasFile ? fileInput.files[0].name : (currentSvgFilename || 'vector.svg');

                    if (btn) {
                        btn.disabled = true;
                        btn.innerHTML = '<span>⏳</span> در حال تبدیل...';
                    }
                    if (resultDiv) {
                        resultDiv.classList.remove('hidden');
                        resultDiv.className = 'mt-4 p-3 rounded-xl text-xs bg-cyan-950/60 border border-cyan-800 text-cyan-300 flex items-center justify-between';
                        resultDiv.innerHTML = '<span>⚡️ در حال پردازش فایل وکتور و رندر تصویر...</span>';
                    }

                    const sendConvertRequest = async function(b64Data, filename) {
                        try {
                            const res = await fetch('/api/media/convert-svg', {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json; charset=utf-8',
                                    'X-Admin-Password': window.currentAdminPassword || ''
                                },
                                body: JSON.stringify({
                                    data: b64Data,
                                    format: format,
                                    filename: filename
                                })
                            });
                            const data = await res.json();
                            if (data.ok) {
                                if (resultDiv) {
                                    resultDiv.className = 'mt-4 p-3 rounded-xl text-xs bg-emerald-950/60 border border-emerald-800 text-emerald-300 flex items-center justify-between';
                                    resultDiv.innerHTML = '<span>✅ تبدیل موفق: ' + data.filename + ' (' + Math.round((data.size || 0) / 1024) + ' KB)</span>' +
                                        '<a href="' + data.data + '" download="' + data.filename + '" class="px-3 py-1 bg-emerald-600 hover:bg-emerald-500 text-white rounded-lg font-sans font-bold transition">دریافت فایل</a>';
                                }
                                const a = document.createElement('a');
                                a.href = data.data;
                                a.download = data.filename;
                                document.body.appendChild(a);
                                a.click();
                                a.remove();
                            } else {
                                if (resultDiv) {
                                    resultDiv.className = 'mt-4 p-3 rounded-xl text-xs bg-rose-950/60 border border-rose-800 text-rose-300';
                                    resultDiv.innerText = '❌ خطای تبدیل: ' + (data.error || 'عملیات ناموفق بود');
                                }
                            }
                        } catch (err) {
                            if (resultDiv) {
                                resultDiv.className = 'mt-4 p-3 rounded-xl text-xs bg-rose-950/60 border border-rose-800 text-rose-300';
                                resultDiv.innerText = '❌ خطای ارتباط با سرور: ' + err.message;
                            }
                        } finally {
                            if (btn) {
                                btn.disabled = false;
                                btn.innerHTML = '<span>⚡️</span> تبدیل و دریافت تصویر';
                            }
                        }
                    };

                    if (hasFile) {
                        const reader = new FileReader();
                        reader.onload = function() {
                            sendConvertRequest(reader.result, fname);
                        };
                        reader.onerror = function() {
                            if (resultDiv) {
                                resultDiv.className = 'mt-4 p-3 rounded-xl text-xs bg-rose-950/60 border border-rose-800 text-rose-300';
                                resultDiv.innerText = '❌ خطا در خواندن فایل وکتور از دستگاه.';
                            }
                            if (btn) {
                                btn.disabled = false;
                                btn.innerHTML = '<span>⚡️</span> تبدیل و دریافت تصویر';
                            }
                        };
                        reader.readAsDataURL(fileInput.files[0]);
                    } else {
                        try {
                            const b64 = 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(currentSvgContent)));
                            sendConvertRequest(b64, fname);
                        } catch (e) {
                            if (resultDiv) {
                                resultDiv.className = 'mt-4 p-3 rounded-xl text-xs bg-rose-950/60 border border-rose-800 text-rose-300';
                                resultDiv.innerText = '❌ خطا در کدگذاری وکتور: ' + e.message;
                            }
                            if (btn) {
                                btn.disabled = false;
                                btn.innerHTML = '<span>⚡️</span> تبدیل و دریافت تصویر';
                            }
                        }
                    }
                }
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

        async function syncFeedThumbnails(btn) {
            if (!btn) return;
            const originalHtml = btn.innerHTML;
            btn.innerHTML = '<svg class="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"></path></svg><span>در حال همگام‌سازی...</span>';
            btn.disabled = true;
            try {
                const res = await fetch('/api/feed/sync', { method: 'POST' });
                const data = await res.json();
                if (data.ok) {
                    showToast('✅ اطلاعات با موفقیت همگام‌سازی شد', 'success');
                    window.fetchFeedDownloads(false);
                } else {
                    showToast('❌ خطا در همگام‌سازی: ' + (data.error || ''), 'error');
                }
            } catch (err) {
                showToast('❌ خطای ارتباط با سرور', 'error');
            } finally {
                btn.innerHTML = originalHtml;
                btn.disabled = false;
            }
        }
        window.syncFeedThumbnails = syncFeedThumbnails;
                window.changeFeedPage = changeFeedPage;
                window.openFeedDispatchModal = openFeedDispatchModal;
                window.closeFeedDispatchModal = closeFeedDispatchModal;
                window.executeFeedDispatch = executeFeedDispatch;
                window.transferFeedDownload = transferFeedDownload;
                window.addFeedToCourseEpisodes = addFeedToCourseEpisodes;
                window.executeFeedMultiDispatch = executeFeedMultiDispatch;
                window.setDispatchFormat = setDispatchFormat;
            } catch (err) {
                console.error('[UNFINIT Studio Module Error]:', err);
            }
        })();

        // =========================================================================
        // MODULE 3: STORE, ORDERS & COUPONS (Sandboxed IIFE)
        // =========================================================================
        (function initStoreOrdersModule() {
            try {
        function toggleAddCourseForm() {
            const card = document.getElementById('addCourseCard');
            card.classList.toggle('hidden');
            if (!card.classList.contains('hidden')) {
                updateCharCounter('newCName', 'counter_newCName', 32);
                updateCharCounter('newCDesc', 'counter_newCDesc', 255);
            }
        }

        function togglePackageInput(prefix) {
            const selectEl = document.getElementById(prefix + 'DeliveryType');
            const pkgBox = document.getElementById(prefix + 'PackageBox');
            if (selectEl && pkgBox) {
                if (selectEl.value === 'files_package') {
                    pkgBox.classList.remove('hidden');
                } else {
                    pkgBox.classList.add('hidden');
                }
            }
        }

        function formatPriceInput(el) {
            if (!el) return;
            const digits = el.value.replace(/[^0-9]/g, '');
            if (digits === '') {
                el.value = '';
                return;
            }
            el.value = Number(digits).toLocaleString('en-US');
        }

        async function handleCreateCourse(e) {
            e.preventDefault();
            const btn = document.getElementById('btnSubmitCourse');
            btn.disabled = true;
            btn.innerText = 'در حال ثبت...';
            const name = document.getElementById('newCName').value;
            const rawPrice = String(document.getElementById('newCPrice').value || '').replace(/[,،\s]/g, '');
            const price = parseInt(rawPrice) || 0;
            const description = document.getElementById('newCDesc').value;
            const download_link = document.getElementById('newCDownload').value;
            const photo_url = document.getElementById('newCPhoto').value;
            const allow_card = document.getElementById('newCAllowCard').checked;
            const allow_bale = document.getElementById('newCAllowBale').checked;
            const requires_referral = document.getElementById('newCRequiresReferral') ? (document.getElementById('newCRequiresReferral').checked ? 1 : 0) : 0;
            const delivery_type = document.getElementById('newCDeliveryType') ? document.getElementById('newCDeliveryType').value : 'channel';
            let files_package = [];
            if (delivery_type === 'files_package' && document.getElementById('newCFilesPackage')) {
                const rawPkg = document.getElementById('newCFilesPackage').value.trim();
                try {
                    files_package = rawPkg.startsWith('[') ? JSON.parse(rawPkg) : rawPkg.split('\n').filter(Boolean).map(l => {
                        const parts = l.split('|').map(s => s.trim());
                        return { title: parts[0] || 'فایل آموزشی', file_id: parts[1] || parts[0] };
                    });
                } catch(e) {
                    files_package = [{ title: name, file_name: rawPkg }];
                }
            }

            try {
                const res = await fetch('/api/courses/add', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json; charset=utf-8' },
                    body: JSON.stringify({ name, price, description, download_link, photo_url, allow_card, allow_bale, requires_referral, delivery_type, files_package })
                });
                const data = await res.json();
                if (data.ok) {
                    showToast('✅ دوره جدید با موفقیت ثبت شد!');
                    location.reload();
                } else {
                    showToast('❌ خطا: ' + (data.error || 'ثبت دوره ناموفق بود'));
                }
            } catch (err) {
                showToast('❌ خطای ارتباط با سرور: ' + err.message);
            } finally {
                btn.disabled = false;
                btn.innerText = 'ثبت دوره در دیتابیس';
            }
        }

        window._currentPackageLessons = [];

        /**
         * رندر مجدد لیست تعاملی جلسات پکیج دوره در DOM
         * این تابع امکان تغییر ترتیب، ویرایش عناوین، و حذف جلسات را با هماهنگی کامل فرم فراهم می‌سازد.
         */
        function renderPackageLessons() {
            const listEl = document.getElementById('editPackageLessonsList');
            const hiddenTa = document.getElementById('editFilesPackage');
            if (!listEl) return;
            listEl.innerHTML = '';
            const lessons = window._currentPackageLessons || [];
            if (hiddenTa) {
                hiddenTa.value = lessons.length ? JSON.stringify(lessons, null, 2) : '';
            }
            if (lessons.length === 0) {
                listEl.innerHTML = '<div class="text-center py-3 text-xs text-slate-400">هیچ جلسه‌ای برای این پکیج ثبت نشده است. از فرم زیر جلسه جدید اضافه کنید.</div>';
                return;
            }
            lessons.forEach(function(item, idx) {
                const row = document.createElement('div');
                row.className = 'flex items-center gap-2 p-2 rounded-xl border text-xs';
                row.style.background = 'var(--input-bg)';
                row.style.borderColor = 'var(--card-border)';
                
                const badge = document.createElement('span');
                badge.className = 'w-6 h-6 rounded-lg bg-cyan-950/80 text-cyan-400 border border-cyan-800 flex items-center justify-center text-[11px] shrink-0 font-bold';
                badge.textContent = '#' + (idx + 1);
                row.appendChild(badge);

                const titleInp = document.createElement('input');
                titleInp.type = 'text';
                titleInp.value = item.title || '';
                titleInp.placeholder = 'عنوان جلسه';
                titleInp.className = 'flex-1 px-2 py-1 rounded-lg border text-xs focus:outline-none focus:border-cyan-500';
                titleInp.style.background = 'var(--card-bg)';
                titleInp.style.borderColor = 'var(--card-border)';
                titleInp.style.color = 'var(--text-main)';
                titleInp.oninput = function() { updatePackageLesson(idx, 'title', this.value); };
                row.appendChild(titleInp);

                const fileInp = document.createElement('input');
                fileInp.type = 'text';
                fileInp.value = item.file_name || item.file_id || item.link || '';
                fileInp.placeholder = 'فایل / شناسه';
                fileInp.className = 'w-1/3 px-2 py-1 rounded-lg border text-xs focus:outline-none focus:border-cyan-500';
                fileInp.style.background = 'var(--card-bg)';
                fileInp.style.borderColor = 'var(--card-border)';
                fileInp.style.color = 'var(--text-main)';
                fileInp.dir = 'ltr';
                fileInp.oninput = function() { updatePackageLesson(idx, 'file_name', this.value); };
                row.appendChild(fileInp);

                const actionsDiv = document.createElement('div');
                actionsDiv.className = 'flex items-center gap-1 shrink-0';

                const upBtn = document.createElement('button');
                upBtn.type = 'button';
                upBtn.title = 'انتقال به بالا';
                upBtn.disabled = (idx === 0);
                upBtn.className = 'p-1 rounded-lg border text-slate-300 hover:text-cyan-400 disabled:opacity-30 disabled:hover:text-slate-300 transition';
                upBtn.style.background = 'var(--card-bg)';
                upBtn.style.borderColor = 'var(--card-border)';
                upBtn.onclick = function() { movePackageLesson(idx, -1); };
                upBtn.innerHTML = '<svg class="w-3.5 h-3.5 stroke-[2]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M4.5 15.75l7.5-7.5 7.5 7.5" /></svg>';
                actionsDiv.appendChild(upBtn);

                const downBtn = document.createElement('button');
                downBtn.type = 'button';
                downBtn.title = 'انتقال به پایین';
                downBtn.disabled = (idx === lessons.length - 1);
                downBtn.className = 'p-1 rounded-lg border text-slate-300 hover:text-cyan-400 disabled:opacity-30 disabled:hover:text-slate-300 transition';
                downBtn.style.background = 'var(--card-bg)';
                downBtn.style.borderColor = 'var(--card-border)';
                downBtn.onclick = function() { movePackageLesson(idx, 1); };
                downBtn.innerHTML = '<svg class="w-3.5 h-3.5 stroke-[2]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" /></svg>';
                actionsDiv.appendChild(downBtn);

                const delBtn = document.createElement('button');
                delBtn.type = 'button';
                delBtn.title = 'حذف جلسه';
                delBtn.className = 'p-1 rounded-lg border text-rose-400 hover:bg-rose-950/50 hover:text-rose-300 transition';
                delBtn.style.background = 'var(--card-bg)';
                delBtn.style.borderColor = 'var(--card-border)';
                delBtn.onclick = function() { removePackageLesson(idx); };
                delBtn.innerHTML = '<svg class="w-3.5 h-3.5 stroke-[2]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>';
                actionsDiv.appendChild(delBtn);

                row.appendChild(actionsDiv);
                listEl.appendChild(row);
            });
        }
        window.renderPackageLessons = renderPackageLessons;

        /**
         * افزودن ردیف جلسه جدید به پکیج دوره
         */
        function addPackageLessonRow() {
            const titleInp = document.getElementById('newLessonTitle');
            const fileInp = document.getElementById('newLessonFile');
            const title = titleInp ? titleInp.value.trim() : '';
            const file_name = fileInp ? fileInp.value.trim() : '';
            if (!file_name) {
                showToast('لطفاً شناسه فایل یا نام فایل جلسه را وارد نمایید.');
                return;
            }
            const lessons = window._currentPackageLessons || [];
            lessons.push({
                title: title || ('جلسه ' + (lessons.length + 1)),
                file_name: file_name,
                duration: 0
            });
            window._currentPackageLessons = lessons;
            if (titleInp) titleInp.value = '';
            if (fileInp) fileInp.value = '';
            renderPackageLessons();
        }
        window.addPackageLessonRow = addPackageLessonRow;

        /**
         * به‌روزرسانی فیلدهای یک جلسه پکیج
         */
        function updatePackageLesson(idx, field, val) {
            if (window._currentPackageLessons && window._currentPackageLessons[idx]) {
                window._currentPackageLessons[idx][field] = val;
                const hiddenTa = document.getElementById('editFilesPackage');
                if (hiddenTa) hiddenTa.value = JSON.stringify(window._currentPackageLessons, null, 2);
            }
        }
        window.updatePackageLesson = updatePackageLesson;

        /**
         * جابجایی ترتیب جلسه با دکمه‌های بالا / پایین
         */
        function movePackageLesson(idx, dir) {
            const lessons = window._currentPackageLessons || [];
            const target = idx + dir;
            if (target < 0 || target >= lessons.length) return;
            const temp = lessons[idx];
            lessons[idx] = lessons[target];
            lessons[target] = temp;
            window._currentPackageLessons = lessons;
            renderPackageLessons();
        }
        window.movePackageLesson = movePackageLesson;

        /**
         * حذف یک جلسه از پکیج دوره
         */
        function removePackageLesson(idx) {
            const lessons = window._currentPackageLessons || [];
            if (idx >= 0 && idx < lessons.length) {
                lessons.splice(idx, 1);
                window._currentPackageLessons = lessons;
                renderPackageLessons();
            }
        }
        window.removePackageLesson = removePackageLesson;

        /**
         * باز کردن مودال ویرایش دوره و مقداردهی فرم‌ها
         */
        function openEditModal(pid, name, price, desc, dl, photo, allow_card, allow_bale, requires_referral, delivery_type, files_package) {
            document.getElementById('editProductId').value = pid;
            document.getElementById('modalProdIdBadge').innerText = pid;
            document.getElementById('editName').value = name;
            const rawP = String(price || '0').replace(/[,،\s]/g, '');
            document.getElementById('editPrice').value = Number(rawP) ? Number(rawP).toLocaleString('en-US') : '0';
            document.getElementById('editDesc').value = desc;
            document.getElementById('editDl').value = dl;
            document.getElementById('editPhoto').value = photo;
            document.getElementById('editAllowCard').checked = !!allow_card;
            document.getElementById('editAllowBale').checked = !!allow_bale;
            if (document.getElementById('editRequiresReferral')) {
                document.getElementById('editRequiresReferral').checked = !!requires_referral;
            }
            if (document.getElementById('editDeliveryType')) {
                document.getElementById('editDeliveryType').value = delivery_type || 'channel';
                togglePackageInput('edit');
            }
            
            let pkgList = [];
            if (Array.isArray(files_package)) {
                pkgList = JSON.parse(JSON.stringify(files_package));
            } else if (typeof files_package === 'string' && files_package.trim()) {
                try {
                    pkgList = JSON.parse(files_package);
                } catch(e) {
                    pkgList = files_package.split('\n').filter(Boolean).map(function(l) {
                        const parts = l.split('|').map(function(s) { return s.trim(); });
                        return { title: parts[0] || 'فایل آموزشی', file_name: parts[1] || parts[0] };
                    });
                }
            }
            window._currentPackageLessons = Array.isArray(pkgList) ? pkgList : [];
            renderPackageLessons();

            if (window._currentPackageLessons && window._currentPackageLessons.length > 0) {
                const pkgBox = document.getElementById('editPackageBox');
                if (pkgBox) pkgBox.classList.remove('hidden');
            }

            const statusEl = document.getElementById('bannerUploadStatus_editPhoto');
            if (statusEl) statusEl.innerText = '';
            updateCharCounter('editName', 'counter_editName', 32);
            updateCharCounter('editDesc', 'counter_editDesc', 255);
            document.getElementById('editModal').classList.remove('hidden');
        }

        function closeEditModal() {
            const m = document.getElementById('editModal');
            if (m) m.classList.add('hidden');
        }
        window.closeEditModal = closeEditModal;
        window.closeEditCourseModal = closeEditModal;

        function openEditModalById(pid) {
            let course = null;
            if (window.coursesData) {
                course = window.coursesData[pid] || Object.values(window.coursesData).find(c => c && (c.product_id == pid || String(c.product_id) === String(pid)));
            }
            if (!course && window.COURSES_CACHE) {
                course = window.COURSES_CACHE[pid] || Object.values(window.COURSES_CACHE).find(c => c && (c.product_id == pid || String(c.product_id) === String(pid)));
            }
            if (!course) {
                showToast('اطلاعات دوره یافت نشد (' + pid + ').');
                return;
            }
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
        }
        window.openEditCourseModal = openEditModalById;
        window.openEditModalById = openEditModalById;

        /**
         * ذخیره تغییرات دوره به صورت ایجکس بدون رفرش صفحه (Zero Page-Reload)
         */
        async function handleSaveEdit(e) {
            e.preventDefault();
            const product_id = document.getElementById('editProductId').value;
            const name = document.getElementById('editName').value;
            const rawPrice = String(document.getElementById('editPrice').value || '').replace(/[,،\s]/g, '');
            const price = parseInt(rawPrice) || 0;
            const description = document.getElementById('editDesc').value;
            const download_link = document.getElementById('editDl').value;
            const photo_url = document.getElementById('editPhoto').value;
            const allow_card = document.getElementById('editAllowCard').checked ? 1 : 0;
            const allow_bale = document.getElementById('editAllowBale').checked ? 1 : 0;
            const requires_referral = document.getElementById('editRequiresReferral') ? (document.getElementById('editRequiresReferral').checked ? 1 : 0) : 0;
            const delivery_type = document.getElementById('editDeliveryType') ? document.getElementById('editDeliveryType').value : 'channel';
            let files_package = [];
            if (delivery_type === 'files_package') {
                if (window._currentPackageLessons && window._currentPackageLessons.length > 0) {
                    files_package = window._currentPackageLessons;
                } else if (document.getElementById('editFilesPackage')) {
                    const rawPkg = document.getElementById('editFilesPackage').value.trim();
                    try {
                        files_package = rawPkg.startsWith('[') ? JSON.parse(rawPkg) : rawPkg.split('\n').filter(Boolean).map(function(l) {
                            const parts = l.split('|').map(function(s) { return s.trim(); });
                            return { title: parts[0] || 'فایل آموزشی', file_id: parts[1] || parts[0] };
                        });
                    } catch(e) {
                        files_package = [{ title: name, file_name: rawPkg }];
                    }
                }
            }

            try {
                const res = await fetch('/api/courses/update', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json; charset=utf-8' },
                    body: JSON.stringify({ product_id, name, price, description, download_link, photo_url, allow_card, allow_bale, requires_referral, delivery_type, files_package })
                });
                const data = await res.json();
                if (data.ok) {
                    // به‌روزرسانی کش درون حافظه کلاینت
                    if (window.coursesData && window.coursesData[product_id]) {
                        Object.assign(window.coursesData[product_id], {
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
                        });
                    }
                    // به‌روزرسانی زنده کارت دوره در DOM بدون رفرش
                    const card = document.getElementById('course_card_' + product_id);
                    if (card) {
                        const titleEl = card.querySelector('h3');
                        if (titleEl) titleEl.textContent = name;
                        const descEl = card.querySelector('p');
                        if (descEl) descEl.textContent = description || 'توضیحاتی برای این دوره ثبت نشده است.';
                    }
                    closeEditModal();
                    showToast('✅ تغییرات دوره با موفقیت ذخیره شد!');
                } else {
                    showToast('❌ خطا: ' + (data.error || 'ویرایش ناموفق بود'));
                }
            } catch (err) {
                showToast('❌ خطای ارتباط: ' + err.message);
            }
        }

        async function saveCourseTermsText() {
            const btn = document.getElementById('btnSaveTerms');
            const status = document.getElementById('termsSaveStatus');
            const textarea = document.getElementById('courseTermsTextarea');
            if (!textarea) return;
            const terms = textarea.value.trim();
            if (btn) {
                btn.disabled = true;
                btn.innerText = 'در حال ذخیره...';
            }
            try {
                const res = await fetch('/api/courses/terms', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json; charset=utf-8' },
                    body: JSON.stringify({ terms: terms })
                });
                const data = await res.json();
                if (data.ok) {
                    if (status) {
                        status.className = 'text-xs font-medium text-emerald-400';
                        status.innerText = '✅ تعهدنامه با موفقیت در سیستم ذخیره شد.';
                        setTimeout(() => { status.innerText = ''; }, 4000);
                    }
                } else {
                    if (status) {
                        status.className = 'text-xs font-medium text-rose-400';
                        status.innerText = '❌ خطا: ' + (data.error || 'ذخیره نشد');
                    }
                }
            } catch (err) {
                if (status) {
                    status.className = 'text-xs font-medium text-rose-400';
                    status.innerText = '❌ خطای شبکه: ' + err.message;
                }
            } finally {
                if (btn) {
                    btn.disabled = false;
                    btn.innerText = '💾 ذخیره متن تعهدنامه';
                }
            }
        }

        async function aiSummarizeDescription(textareaId, counterId) {
            const textarea = document.getElementById(textareaId);
            if (!textarea) return;
            const text = textarea.value.trim();
            if (!text) {
                showToast('لطفاً ابتدا متنی در بخش توضیحات بنویسید تا هوش مصنوعی آن را خلاصه کند.');
                return;
            }
            const prevPlaceholder = textarea.placeholder;
            textarea.disabled = true;
            textarea.placeholder = '✨ در حال خلاصه‌سازی هوشمند برای بله (زیر ۲۵۵ کاراکتر)...';
            try {
                const res = await fetch('/api/ai/summarize-course', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json; charset=utf-8' },
                    body: JSON.stringify({ text: text })
                });
                const data = await res.json();
                if (data.ok && data.summary) {
                    textarea.value = data.summary;
                    if (counterId) {
                        updateCharCounter(textareaId, counterId, 255);
                    }
                } else {
                    showToast('❌ خطا در خلاصه‌سازی: ' + (data.error || 'پاسخی دریافت نشد'));
                }
            } catch (err) {
                showToast('❌ خطای ارتباط با هوش مصنوعی: ' + err.message);
            } finally {
                textarea.disabled = false;
                textarea.placeholder = prevPlaceholder;
            }
        }

        async function toggleCourseActive(pid) {
            const btn = document.getElementById('toggle_btn_' + pid);
            const badge = document.getElementById('status_badge_' + pid);
            if (btn) {
                btn.disabled = true;
                btn.innerText = 'در حال تغییر...';
            }
            try {
                const res = await fetch('/api/products/toggle_active', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json; charset=utf-8' },
                    body: JSON.stringify({ product_id: pid })
                });
                const data = await res.json();
                if (data.ok) {
                    const isActive = !!data.active;
                    if (badge) {
                        if (isActive) {
                            badge.className = 'px-2.5 py-1 rounded-lg text-xs font-bold bg-emerald-950 text-emerald-300 border border-emerald-800 flex items-center gap-1';
                            badge.innerHTML = '<span><svg class="w-4 h-4 text-emerald-400 inline" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.75"><path stroke-linecap="round" stroke-linejoin="round" d="M12 2.25c-5.385 0-9.75 4.365-9.75 9.75s4.365 9.75 9.75 9.75 9.75-4.365 9.75-9.75S17.385 2.25 12 2.25z" /></svg></span> فعال';
                        } else {
                            badge.className = 'px-2.5 py-1 rounded-lg text-xs font-bold bg-rose-950 text-rose-300 border border-rose-800 flex items-center gap-1';
                            badge.innerHTML = '<span>🔴</span> غیرفعال';
                        }
                    }
                    if (btn) {
                        btn.innerHTML = isActive ? '🔴 غیرفعال‌سازی' : '<svg class="w-4 h-4 text-emerald-400 inline" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.75"><path stroke-linecap="round" stroke-linejoin="round" d="M12 2.25c-5.385 0-9.75 4.365-9.75 9.75s4.365 9.75 9.75 9.75 9.75-4.365 9.75-9.75S17.385 2.25 12 2.25z" /></svg> فعال‌سازی';
                    }
                    if (window.coursesData && window.coursesData[pid]) {
                        window.coursesData[pid].is_active = isActive ? 1 : 0;
                    }
                } else {
                    showToast('❌ خطا در تغییر وضعیت: ' + (data.error || ''));
                }
            } catch (err) {
                showToast('❌ خطا: ' + err.message);
            } finally {
                if (btn) {
                    btn.disabled = false;
                }
            }
        }

        async function deleteCourse(pid) {
            if (!confirm('آیا از حذف دائم و فیزیکی این دوره از سیستم و پایگاه داده اطمینان دارید؟ این عملیات غیرقابل بازگشت است.')) return;
            try {
                const res = await fetch('/api/products/delete', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json; charset=utf-8' },
                    body: JSON.stringify({ product_id: pid })
                });
                const data = await res.json();
                if (data.ok) {
                    const card = document.getElementById('course_card_' + pid);
                    if (card) {
                        card.style.transition = 'all 0.4s ease';
                        card.style.opacity = '0';
                        card.style.transform = 'scale(0.95)';
                        setTimeout(() => { card.remove(); }, 400);
                    }
                } else {
                    showToast('❌ خطا: ' + (data.error || ''));
                }
            } catch (err) {
                showToast('❌ خطا: ' + err.message);
            }
        }

        function toggleSelectAllOrders(master) {
            const chks = document.querySelectorAll('.order-chk');
            chks.forEach(c => c.checked = master.checked);
            updateSelectedOrdersCount();
        }

        function updateSelectedOrdersCount() {
            const chks = document.querySelectorAll('.order-chk:checked');
            const cnt = chks.length;
            const btn = document.getElementById('btnDeleteSelectedOrders');
            const cntSpan = document.getElementById('selectedOrdersCount');
            if (cntSpan) cntSpan.innerText = cnt;
            if (btn) {
                if (cnt > 0) {
                    btn.classList.remove('hidden');
                } else {
                    btn.classList.add('hidden');
                }
            }
            const allChks = document.querySelectorAll('.order-chk');
            const master = document.getElementById('selectAllOrders');
            if (master && allChks.length > 0) {
                master.checked = (cnt === allChks.length);
            } else if (master && allChks.length === 0) {
                master.checked = false;
            }
        }

        async function deleteSelectedOrders() {
            const checked = Array.from(document.querySelectorAll('.order-chk:checked')).map(c => c.value);
            if (!checked || checked.length === 0) {
                showToast('لطفاً حداقل یک سفارش را برای حذف انتخاب کنید.');
                return;
            }
            if (!confirm('آیا از حذف دسته‌جمعی ' + checked.length + ' سفارش انتخاب‌شده اطمینان دارید؟ این عملیات غیرقابل بازگشت است.')) return;
            try {
                const res = await fetch('/api/store/orders/bulk_delete', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json; charset=utf-8' },
                    body: JSON.stringify({ order_ids: checked })
                });
                const data = await res.json();
                if (data.ok) {
                    showToast('✅ ' + (data.message || (checked.length + ' سفارش با موفقیت حذف شدند.')));
                    loadStoreOrders();
                } else {
                    showToast('❌ خطا در حذف سفارش‌ها: ' + (data.error || ''));
                }
            } catch (err) {
                showToast('❌ خطای ارتباط: ' + err.message);
            }
        }

        async function clearAllOrders() {
            if (!confirm('⚠️ هشدار جدی!\nآیا از پاکسازی تمامی سفارشات موجود در سیستم اطمینان دارید؟\nاین عملیات کلیه سفارشات ثبت‌شده (تستی و واقعی) را به طور کامل حذف می‌کند و غیرقابل بازگشت است.')) return;
            try {
                const res = await fetch('/api/store/orders/clear_all', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json; charset=utf-8' }
                });
                const data = await res.json();
                if (data.ok) {
                    showToast('✅ ' + (data.message || 'تمامی سفارشات با موفقیت پاکسازی شدند.'));
                    loadStoreOrders();
                } else {
                    showToast('❌ خطا در پاکسازی سفارشات: ' + (data.error || ''));
                }
            } catch (err) {
                showToast('❌ خطای ارتباط: ' + err.message);
            }
        }

        async function loadStoreOrders() {
            const tbody = document.getElementById('storeOrdersTableBody');
            if (!tbody) return;
            const master = document.getElementById('selectAllOrders');
            if (master) master.checked = false;
            updateSelectedOrdersCount();

            try {
                const res = await fetch('/api/store/orders');
                const data = await res.json();
                if (!data.ok || !data.orders || data.orders.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="9" class="py-8 text-center text-slate-500">هیچ سفارشی در سیستم ثبت نشده است.</td></tr>';
                    return;
                }
                tbody.innerHTML = data.orders.map(ord => {
                    let statusBadge = '';
                    if (ord.status === 'completed' || ord.status === 'approved') {
                        statusBadge = '<span class="px-2.5 py-1 rounded-lg text-xs font-bold bg-emerald-950 text-emerald-300 border border-emerald-800">✅ تایید شده</span>';
                    } else if (ord.status === 'rejected') {
                        statusBadge = '<span class="px-2.5 py-1 rounded-lg text-xs font-bold bg-rose-950 text-rose-300 border border-rose-800">❌ رد شده</span>';
                    } else {
                        statusBadge = '<span class="px-2.5 py-1 rounded-lg text-xs font-bold bg-amber-950 text-amber-300 border border-amber-800">⏳ در انتظار بررسی</span>';
                    }

                    let platBadge = '';
                    const p = (ord.platform || '').toLowerCase();
                    if (p === 'telegram' || p === 'tg') {
                        platBadge = '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-sky-950/70 text-sky-300 border border-sky-800/70 inline-flex items-center gap-1"><span><svg class="w-4 h-4 text-cyan-400 inline" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.75"><path stroke-linecap="round" stroke-linejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" /></svg></span> تلگرام</span>';
                    } else if (p === 'bale') {
                        platBadge = '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-950/70 text-emerald-300 border border-emerald-800/70 inline-flex items-center gap-1"><span><svg class="w-4 h-4 text-emerald-400 inline" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.75"><path stroke-linecap="round" stroke-linejoin="round" d="M12 2.25c-5.385 0-9.75 4.365-9.75 9.75s4.365 9.75 9.75 9.75 9.75-4.365 9.75-9.75S17.385 2.25 12 2.25z" /></svg></span> بله</span>';
                    } else {
                        platBadge = '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-purple-950/70 text-purple-300 border border-purple-800/70 inline-flex items-center gap-1"><span>🌐</span> فروشگاه وب</span>';
                    }

                    let payMethodBadge = '';
                    const m = (ord.payment_method || '').toLowerCase();
                    if (m === 'bale_online' || m === 'bale') {
                        payMethodBadge = '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-950/60 text-emerald-300 border border-emerald-800/60 inline-flex items-center gap-1"><span>🛍</span> درگاه بله</span>';
                    } else if (m === 'card_to_card' || m === 'card') {
                        payMethodBadge = '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-sky-950/60 text-sky-300 border border-sky-800/60 inline-flex items-center gap-1"><span>💳</span> کارت‌به‌کارت</span>';
                    } else if (m === 'zarinpal') {
                        payMethodBadge = '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-950/60 text-amber-300 border border-amber-800/60 inline-flex items-center gap-1"><span>⚡️</span> زرین‌پال</span>';
                    } else {
                        payMethodBadge = '<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-sky-950/60 text-sky-300 border border-sky-800/60 inline-flex items-center gap-1"><span>💳</span> کارت‌به‌کارت</span>';
                    }

                    let actionBtn = '<div class="flex items-center gap-1.5">';
                    if (ord.status === 'pending_review' || ord.status === 'pending') {
                        actionBtn += '<button onclick="approveStoreOrder(&quot;' + ord.order_id + '&quot;)" class="px-2.5 py-1 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold transition shadow-sm">✅ تایید</button>' +
                                    '<button onclick="rejectStoreOrder(&quot;' + ord.order_id + '&quot;)" class="theme-card-btn px-2.5 py-1 rounded-lg text-xs font-bold transition shadow-sm">❌ رد</button>';
                    }
                    actionBtn += '<button onclick="deleteStoreOrder(&quot;' + ord.order_id + '&quot;)" class="theme-card-btn px-2 py-1 rounded-lg text-xs font-bold transition shadow-sm" title="حذف سفارش">🗑 حذف</button></div>';

                    const orderDate = ord.created_at || '-';
                    const amountStr = (ord.amount || 0).toLocaleString() + ' تومان';

                    return '<tr class="border-b border-slate-800 hover:bg-slate-800/30 transition">' +
                        '<td class="py-3 px-3 text-center"><input type="checkbox" class="order-chk rounded bg-slate-800 border-slate-600 text-cyan-500 focus:ring-0 cursor-pointer" value="' + escapeHtml(ord.order_id) + '" onchange="updateSelectedOrdersCount()"></td>' +
                        '<td class="py-3 px-3 text-cyan-400 font-bold">' + escapeHtml(ord.order_id) + '</td>' +
                        '<td class="py-3 px-3">' +
                            '<div class="font-bold text-slate-200">' + escapeHtml(ord.customer_name || 'کاربر') + '</div>' +
                            '<div class="text-[11px] text-slate-400">' + escapeHtml(ord.phone || ord.user_id || '-') + '</div>' +
                        '</td>' +
                        '<td class="py-3 px-3">' +
                            '<div class="text-slate-200 font-medium">' + escapeHtml(ord.product_name || ord.product_id) + '</div>' +
                            '<div class="text-[11px] text-emerald-400 font-bold">' + amountStr + '</div>' +
                        '</td>' +
                        '<td class="py-3 px-3">' + platBadge + '</td>' +
                        '<td class="py-3 px-3">' + payMethodBadge + '</td>' +
                        '<td class="py-3 px-3">' +
                            '<div class="max-w-[200px] truncate text-slate-300 text-[11px]" title="' + escapeHtml(ord.receipt_text || '') + '">' + escapeHtml(ord.receipt_text || '-') + '</div>' +
                            '<div class="text-[10px] text-slate-400">' + escapeHtml(orderDate) + '</div>' +
                        '</td>' +
                        '<td class="py-3 px-3">' + statusBadge + '</td>' +
                        '<td class="py-3 px-3 text-left">' + actionBtn + '</td>' +
                    '</tr>';
                }).join('');
            } catch (err) {
                tbody.innerHTML = '<tr><td colspan="9" class="py-6 text-center text-rose-400">خطا در دریافت سفارش‌ها: ' + err.message + '</td></tr>';
            }
        }

        async function approveStoreOrder(orderId) {
            if (!confirm('آیا از تایید سفارش ' + orderId + ' و فعال‌سازی لینک دانلود برای مشتری اطمینان دارید؟')) return;
            try {
                const res = await fetch('/api/store/orders/approve', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json; charset=utf-8' },
                    body: JSON.stringify({ order_id: orderId })
                });
                const data = await res.json();
                if (data.ok) {
                    showToast('✅ سفارش ' + orderId + ' با موفقیت تایید شد!');
                    loadStoreOrders();
                } else {
                    showToast('❌ خطا در تایید سفارش: ' + (data.error || ''));
                }
            } catch (err) {
                showToast('❌ خطای ارتباط: ' + err.message);
            }
        }

        async function rejectStoreOrder(orderId) {
            if (!confirm('آیا از رد سفارش ' + orderId + ' اطمینان دارید؟ وضعیت سفارش به رد شده تغییر خواهد کرد.')) return;
            try {
                const res = await fetch('/api/store/orders/reject', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json; charset=utf-8' },
                    body: JSON.stringify({ order_id: orderId })
                });
                const data = await res.json();
                if (data.ok) {
                    showToast('❌ سفارش ' + orderId + ' با موفقیت رد شد.');
                    loadStoreOrders();
                } else {
                    showToast('❌ خطا در رد سفارش: ' + (data.error || ''));
                }
            } catch (err) {
                showToast('❌ خطای ارتباط: ' + err.message);
            }
        }

        async function deleteStoreOrder(orderId) {
            if (!confirm('آیا از حذف کامل سفارش ' + orderId + ' از سیستم اطمینان دارید؟ این عملیات غیرقابل بازگشت است.')) return;
            try {
                const res = await fetch('/api/store/orders/delete', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json; charset=utf-8' },
                    body: JSON.stringify({ order_id: orderId })
                });
                const data = await res.json();
                if (data.ok) {
                    loadStoreOrders();
                } else {
                    showToast('❌ خطا در حذف سفارش: ' + (data.error || ''));
                }
            } catch (err) {
                showToast('❌ خطای ارتباط: ' + err.message);
            }
        }

        async function cleanupRejectedOrders() {
            if (!confirm('آیا از حذف کلیه سفارش‌های رد شده از پایگاه داده اطمینان دارید؟ این عملیات غیرقابل بازگشت است.')) return;
            try {
                const res = await fetch('/api/store/orders/cleanup_rejected', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json; charset=utf-8' }
                });
                const data = await res.json();
                if (data.ok) {
                    showToast('✅ ' + (data.message || 'سفارش‌های رد شده با موفقیت پاکسازی شدند.'));
                    loadStoreOrders();
                } else {
                    showToast('❌ خطا در پاکسازی سفارش‌ها: ' + (data.error || ''));
                }
            } catch (err) {
                showToast('❌ خطای ارتباط: ' + err.message);
            }
        }

        async function loadStoreAnalytics() {
            try {
                const res = await fetch('/api/analytics');
                const data = await res.json();
                if (data.ok && data.analytics) {
                    const a = data.analytics;
                    const totEl = document.getElementById('metricTotalSales');
                    if (totEl) totEl.innerText = (a.total_sales_amount || 0).toLocaleString() + ' تومان';
                    const ordEl = document.getElementById('metricTotalOrders');
                    if (ordEl) ordEl.innerText = (a.total_sales_count || 0) + ' سفارش موفق';

                    const todayEl = document.getElementById('metricTodaySales');
                    if (todayEl) todayEl.innerText = (a.today_sales_amount || 0).toLocaleString() + ' تومان';
                    const todayOrd = document.getElementById('metricTodayOrders');
                    if (todayOrd) todayOrd.innerText = (a.today_sales_count || 0) + ' سفارش';

                    const weekEl = document.getElementById('metricWeekSales');
                    if (weekEl) weekEl.innerText = (a.week_sales_amount || 0).toLocaleString() + ' تومان';
                    const weekOrd = document.getElementById('metricWeekOrders');
                    if (weekOrd) weekOrd.innerText = (a.week_sales_count || 0) + ' سفارش';

                    const monthEl = document.getElementById('metricMonthSales');
                    if (monthEl) monthEl.innerText = (a.month_sales_amount || 0).toLocaleString() + ' تومان';
                    const monthOrd = document.getElementById('metricMonthOrders');
                    if (monthOrd) monthOrd.innerText = (a.month_sales_count || 0) + ' سفارش';

                    const pb = a.platform_breakdown || {};
                    const tg = pb.telegram || { amount: 0, count: 0 };
                    const bale = pb.bale || { amount: 0, count: 0 };
                    const rub = pb.rubika || { amount: 0, count: 0 };
                    const web = pb.web || { amount: 0, count: 0 };

                    const tgEl = document.getElementById('platSalesTg');
                    if (tgEl) tgEl.innerText = (tg.amount || 0).toLocaleString() + ' تومان (' + (tg.count || 0) + ')';
                    const baleEl = document.getElementById('platSalesBale');
                    if (baleEl) baleEl.innerText = (bale.amount || 0).toLocaleString() + ' تومان (' + (bale.count || 0) + ')';
                    const rubEl = document.getElementById('platSalesRubika');
                    if (rubEl) rubEl.innerText = (rub.amount || 0).toLocaleString() + ' تومان (' + (rub.count || 0) + ')';
                    const webEl = document.getElementById('platSalesWeb');
                    if (webEl) webEl.innerText = (web.amount || 0).toLocaleString() + ' تومان (' + (web.count || 0) + ')';
                }
            } catch (err) {
                console.error('Error loading analytics:', err);
            }
        }

        function toggleAddCouponForm() {
            const el = document.getElementById('addCouponCard');
            if (el) el.classList.toggle('hidden');
        }

        async function loadStoreCoupons() {
            const tbody = document.getElementById('couponsTableBody');
            if (!tbody) return;
            try {
                const res = await fetch('/api/coupons');
                const data = await res.json();
                if (!data.ok || !data.coupons || data.coupons.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="6" class="py-4 text-center text-slate-500">هیچ کد تخفیفی در سیستم ثبت نشده است.</td></tr>';
                    return;
                }
                tbody.innerHTML = data.coupons.map(c => {
                    const valNum = parseInt(c.discount_value) || 0;
                    const typeLabel = c.discount_type === 'percent' ? (valNum + '%') : (valNum.toLocaleString() + ' تومان');
                    const maxLabel = (c.max_uses && c.max_uses > 0) ? ((c.used_count || 0) + ' / ' + c.max_uses) : ((c.used_count || 0) + ' (نامحدود)');
                    const minLabel = (c.min_order_amount && c.min_order_amount > 0) ? (parseInt(c.min_order_amount).toLocaleString() + ' تومان') : 'بدون شرط';
                    const expLabel = c.expire_date ? c.expire_date : 'همیشگی';
                    const statusBadge = c.active ? '<span class="px-2 py-0.5 rounded text-[10px] bg-emerald-950 text-emerald-300 border border-emerald-800">فعال</span>' : '<span class="px-2 py-0.5 rounded text-[10px] bg-slate-800 text-slate-400">غیرفعال</span>';

                    return '<tr class="border-b border-slate-800/80 hover:bg-slate-800/30 transition">' +
                        '<td class="py-2.5 px-3 text-emerald-400 font-bold">' + escapeHtml(c.code) + '</td>' +
                        '<td class="py-2.5 px-3 text-slate-200 font-bold">' + typeLabel + '</td>' +
                        '<td class="py-2.5 px-3 text-slate-300">' + maxLabel + '</td>' +
                        '<td class="py-2.5 px-3 text-slate-400">' + minLabel + '</td>' +
                        '<td class="py-2.5 px-3 text-slate-400 text-[11px]">' + escapeHtml(expLabel) + '</td>' +
                        '<td class="py-2.5 px-3">' + statusBadge + '</td>' +
                    '</tr>';
                }).join('');
            } catch (err) {
                tbody.innerHTML = '<tr><td colspan="6" class="py-4 text-center text-rose-400">خطا در بارگذاری کوپن‌ها: ' + err.message + '</td></tr>';
            }
        }

        async function handleCreateCoupon(e) {
            e.preventDefault();
            const btn = document.getElementById('btnSubmitCoupon');
            if (btn) { btn.disabled = true; btn.innerText = 'در حال ثبت...'; }

            const code = document.getElementById('newCouponCode').value.trim();
            const discount_type = document.getElementById('newCouponType').value;
            const discount_value = parseInt(document.getElementById('newCouponValue').value) || 0;
            const max_uses = parseInt(document.getElementById('newCouponMaxUses').value) || 0;
            const min_order_amount = parseInt(document.getElementById('newCouponMinAmount').value) || 0;
            const expire_date = document.getElementById('newCouponExpire').value.trim();

            try {
                const res = await fetch('/api/coupons/create', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json; charset=utf-8' },
                    body: JSON.stringify({ code, discount_type, discount_value, max_uses, min_order_amount, expire_date })
                });
                const data = await res.json();
                if (data.ok) {
                    showToast('✅ کد تخفیف ' + code + ' با موفقیت ایجاد شد!');
                    document.getElementById('addCouponForm').reset();
                    toggleAddCouponForm();
                    loadStoreCoupons();
                } else {
                    showToast('❌ خطا در ثبت کد تخفیف: ' + (data.error || ''));
                }
            } catch (err) {
                showToast('❌ خطای ارتباط: ' + err.message);
            } finally {
                if (btn) { btn.disabled = false; btn.innerText = 'ثبت کوپن تخفیف'; }
            }
        }

        function copyText(txt) {
            navigator.clipboard.writeText(txt);
            showToast('✅ لینک با موفقیت کپی شد!');
        }

        async function handleDispatch(e) {
            e.preventDefault();
            const btn = document.getElementById('submitBtn');
            const resBox = document.getElementById('dispatchResult');
            const url = document.getElementById('directUrl').value;
            const target = document.getElementById('targetPlatform').value;

            btn.disabled = true;
            btn.innerText = '⏳ در حال دانلود و پردازش استریم...';
            resBox.className = 'mt-4 p-3 rounded-xl text-xs block bg-slate-800 text-slate-300 border border-slate-700';
            resBox.innerText = '⏳ ارسال درخواست به سرور و دانلود استریم... لطفاً شکیبا باشید.';

            try {
                const res = await fetch('/api/dispatch_url', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json; charset=utf-8' },
                    body: JSON.stringify({ url, target })
                });
                const data = await res.json();
                if (data.ok) {
                    resBox.className = 'mt-4 p-3 rounded-xl text-xs block bg-emerald-950 text-emerald-300 border border-emerald-700';
                    resBox.innerText = '✅ ' + (data.message || 'فایل با موفقیت دانلود و ارسال شد!');
                } else {
                    resBox.className = 'mt-4 p-3 rounded-xl text-xs block bg-rose-950 text-rose-300 border border-rose-700';
                    resBox.innerText = '❌ خطا: ' + (data.error || 'عملیات ناموفق بود');
                }
            } catch (err) {
                resBox.className = 'mt-4 p-3 rounded-xl text-xs block bg-rose-950 text-rose-300 border border-rose-700';
                resBox.innerText = '❌ خطای شبکه: ' + err.message;
            } finally {
                btn.disabled = false;
                btn.innerText = '⚡️ دانلود و ارسال خودکار';
            }
        }


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
            } catch (err) {
                console.error('[UNFINIT Store & Orders Module Error]:', err);
            }
        })();

        // =========================================================================
        // MODULE 4: AI AGENT & SYSTEM SETTINGS (Sandboxed IIFE)
        // =========================================================================
        (function initSettingsModule() {
            try {
                let hermesHistory = [];
        function clearHermesChat() {
            hermesHistory = [];
            const box = document.getElementById('hermesChatBox');
            box.innerHTML = `
                <div class="flex gap-2.5 items-center p-3 rounded-xl  border border-slate-800 text-xs text-slate-300">
                    <div class="w-6 h-6 rounded-lg bg-cyan-600/30 text-cyan-300 flex items-center justify-center font-bold text-xs shrink-0">🤖</div>
                    <span>تاریخچه گفتگو پاکسازی شد. دستیار هوش مصنوعی آماده است.</span>
                </div>
            `;
        }

        function sendPresetHermesPrompt(prompt) {
            const input = document.getElementById('hermesInput');
            if (input) {
                input.value = prompt;
                handleSendHermes(null);
            }
        }

        async function handleSendHermes(e) {
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
                <div class="w-8 h-8 rounded-xl bg-slate-700 flex items-center justify-center font-bold text-xs text-white shrink-0 mt-1">👤</div>
            `;
            box.appendChild(userBubble);
            input.value = '';

            const loadingBubble = document.createElement('div');
            const loadingId = 'hermes_load_' + Date.now();
            loadingBubble.id = loadingId;
            loadingBubble.className = 'flex gap-3 items-start max-w-3xl';
            loadingBubble.innerHTML = `
                <div class="w-8 h-8 rounded-xl bg-gradient-to-tr from-cyan-500 to-blue-600 flex items-center justify-center font-bold text-sm text-white shrink-0 mt-1 animate-pulse">🎛</div>
                <div class="bg-slate-800/90 border border-slate-700 p-3.5 rounded-2xl rounded-tr-none text-xs text-slate-300 flex items-center gap-2">
                    <span class="animate-spin text-cyan-400">🌀</span>
                    <span>دستیار هوشمند در حال پردازش و تولید پاسخ...</span>
                </div>
            `;
            box.appendChild(loadingBubble);
            box.scrollTop = box.scrollHeight;

            btn.disabled = true;

            try {
                const selModel = document.getElementById('hermesModelSelect')?.value || '';
                const res = await fetch('/api/hermes/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json; charset=utf-8' },
                    body: JSON.stringify({ message: prompt, history: hermesHistory, model: selModel })
                });
                const data = await res.json();
                const loadEl = document.getElementById(loadingId);
                if (loadEl) loadEl.remove();

                const replyText = data.reply || (data.error ? '❌ خطا: ' + data.error : 'پاسخی دریافت نشد.');
                const toolsUsed = data.tools_used || [];

                let toolsHtml = '';
                if (toolsUsed.length > 0) {
                    toolsHtml = '<div class="flex flex-wrap gap-1.5 mb-2">' + toolsUsed.map(t => '<span class="px-2 py-0.5 rounded-md bg-cyan-950 text-cyan-300 text-[10px] border border-cyan-800">🛠 ' + escapeHtml(t) + '</span>').join('') + '</div>';
                }

                const assistantBubble = document.createElement('div');
                assistantBubble.className = 'flex gap-3 items-start max-w-3xl';
                assistantBubble.innerHTML = `
                    <div class="w-8 h-8 rounded-xl bg-gradient-to-tr from-cyan-500 to-blue-600 flex items-center justify-center font-bold text-sm text-white shrink-0 mt-1">🎛</div>
                    <div class="bg-slate-800/95 border border-slate-700 p-4 rounded-2xl rounded-tr-none text-xs leading-relaxed text-slate-100 space-y-2 whitespace-pre-wrap shadow-xl">
                        ` + toolsHtml + `
                        <div>` + escapeHtml(replyText) + `</div>
                    </div>
                `;
                box.appendChild(assistantBubble);

                hermesHistory.push({ role: 'user', content: prompt });
                hermesHistory.push({ role: 'assistant', content: replyText });
                if (hermesHistory.length > 12) hermesHistory = hermesHistory.slice(-12);
            } catch (err) {
                const loadEl = document.getElementById(loadingId);
                if (loadEl) loadEl.remove();
                const errBubble = document.createElement('div');
                errBubble.className = 'flex gap-3 items-start max-w-3xl';
                errBubble.innerHTML = `
                    <div class="w-8 h-8 rounded-xl bg-rose-600 flex items-center justify-center font-bold text-sm text-white shrink-0 mt-1">⚠️</div>
                    <div class="bg-rose-950/80 border border-rose-800 p-3 rounded-2xl rounded-tr-none text-xs text-rose-300">
                        خطا در ارتباط با سرور: ` + escapeHtml(err.message) + `
                    </div>
                `;
                box.appendChild(errBubble);
            } finally {
                btn.disabled = false;
                box.scrollTop = box.scrollHeight;
            }
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        function uploadBannerFile(fileInput, targetInputId) {
            const file = fileInput.files[0];
            if (!file) return;
            const statusEl = document.getElementById('bannerUploadStatus_' + targetInputId);
            if (statusEl) statusEl.innerText = '⏳ در حال فشرده‌سازی و بارگذاری تصویر بنر...';

            let prodId = '';
            if (targetInputId === 'editPhoto') {
                const editIdEl = document.getElementById('editProductId');
                if (editIdEl) prodId = editIdEl.value || '';
            }

            const reader = new FileReader();
            reader.onload = async function(e) {
                try {
                    const res = await fetch('/api/upload/banner', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json; charset=utf-8' },
                        body: JSON.stringify({
                            filename: file.name,
                            prod_id: prodId,
                            data: e.target.result
                        })
                    });
                    const data = await res.json();
                    if (data.ok && data.url) {
                        const targetInp = document.getElementById(targetInputId);
                        if (targetInp) {
                            targetInp.value = data.url;
                            targetInp.dispatchEvent(new Event('input', { bubbles: true }));
                        }
                        let previewEl = document.getElementById('bannerPreview_' + targetInputId);
                        if (!previewEl && targetInp) {
                            previewEl = document.createElement('img');
                            previewEl.id = 'bannerPreview_' + targetInputId;
                            previewEl.className = 'w-24 h-24 object-cover rounded-xl mt-2 border border-cyan-500/50 shadow-md';
                            if (statusEl) {
                                statusEl.parentNode.insertBefore(previewEl, statusEl);
                            } else {
                                targetInp.parentNode.parentNode.appendChild(previewEl);
                            }
                        }
                        if (previewEl) {
                            previewEl.src = data.url;
                            previewEl.style.display = 'block';
                        }
                        if (statusEl) statusEl.innerHTML = '✅ تصویر ذخیره شد: <a href="' + data.url + '" target="_blank" class="text-cyan-400 underline">' + data.url + '</a>';
                    } else {
                        if (statusEl) statusEl.innerText = '❌ خطا: ' + (data.error || 'آپلود ناموفق بود');
                    }
                } catch (err) {
                    if (statusEl) statusEl.innerText = '❌ خطا در ارسال فایل: ' + err.message;
                }
            };
            reader.readAsDataURL(file);
        }

        async function loadSettings() {
            try {
                const pwd = currentAdminPassword || sessionStorage.getItem('unfinit_admin_pwd') || '';
                const res = await fetch('/api/settings?password=' + encodeURIComponent(pwd));
                if (res.status === 401) {
                    console.warn('loadSettings: unauthorized, active admin login session required.');
                    return;
                }
                const data = await res.json();
                if (data.ok && data.settings) {
                    populateSettingsForm(data.settings);
                }
            } catch (err) {
                console.error('Failed to load settings:', err);
            }
        }

        const AI_PROVIDER_MODELS = {
            vyceai: [
                { id: 'deepseek-v4.1', name: 'deepseek-v4.1 (VyceAI)' },
                { id: 'deepseek-v4-flash', name: 'deepseek-v4-flash (VyceAI)' },
                { id: 'claude-sonnet-4-6', name: 'claude-sonnet-4-6 (VyceAI)' },
                { id: 'agnes-3.0-flash', name: 'agnes-3.0-flash (VyceAI)' }
            ],
            nara: [
                { id: 'stepfun-3.7-flash', name: 'stepfun-3.7-flash (Nara)' },
                { id: 'minimax-0.5-free', name: 'minimax-0.5-free (Nara)' },
                { id: 'qwen2.5-72b', name: 'qwen2.5-72b (Nara)' }
            ],
            gemini: [
                { id: 'gemini-2.0-flash', name: 'gemini-2.0-flash (Gemini)' },
                { id: 'gemini-1.5-flash', name: 'gemini-1.5-flash (Gemini)' },
                { id: 'gemini-1.5-pro', name: 'gemini-1.5-pro (Gemini)' }
            ]
        };

        function handleAiProviderChange(prov, currentModelVal) {
            try {
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

                if (p === 'custom') {
                    if (modelSelect) modelSelect.classList.add('hidden');
                    if (customModelInput) {
                        customModelInput.classList.remove('hidden');
                        if (targetModel) customModelInput.value = targetModel;
                    }
                    if (vyceBox) vyceBox.style.opacity = '1';
                    if (naraBox) naraBox.style.opacity = '1';
                    if (geminiBox) geminiBox.style.opacity = '1';
                    return;
                }

                // Standard Providers (vyceai, nara, gemini)
                if (customModelInput) customModelInput.classList.add('hidden');
                if (modelSelect) {
                    modelSelect.classList.remove('hidden');
                    const models = AI_PROVIDER_MODELS[p] || AI_PROVIDER_MODELS.vyceai;
                    modelSelect.innerHTML = models.map(function(m) {
                        return '<option value="' + m.id + '">' + m.name + '</option>';
                    }).join('');
                    
                    const match = models.some(function(m) { return m.id === targetModel; });
                    if (match) {
                        modelSelect.value = targetModel;
                    } else {
                        modelSelect.value = models[0].id;
                    }
                }

                if (p === 'vyceai') {
                    if (urlInput && (!urlInput.value || urlInput.value.includes('bynara') || urlInput.value.includes('googleapis'))) {
                        urlInput.value = 'https://vyceai.com/v1';
                    }
                    if (vyceBox) vyceBox.style.opacity = '1';
                } else if (p === 'nara') {
                    if (urlInput && (!urlInput.value || urlInput.value.includes('vyceai') || urlInput.value.includes('googleapis'))) {
                        urlInput.value = 'https://router.bynara.id/v1';
                    }
                    if (naraBox) naraBox.style.opacity = '1';
                } else if (p === 'gemini') {
                    if (urlInput && (!urlInput.value || urlInput.value.includes('vyceai') || urlInput.value.includes('bynara'))) {
                        urlInput.value = 'https://generativelanguage.googleapis.com/v1beta';
                    }
                    if (geminiBox) geminiBox.style.opacity = '1';
                } else {
                    if (vyceBox) vyceBox.style.opacity = '1';
                    if (naraBox) naraBox.style.opacity = '1';
                    if (geminiBox) geminiBox.style.opacity = '1';
                }
            } catch (err) {
                console.warn('handleAiProviderChange notice:', err);
            }
        }

        function updateAiProviderView(provider) {
            handleAiProviderChange(provider);
        }

        function populateSettingsForm(s) {
            try {
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
                fields.forEach(f => {
                    const el = document.getElementById('cfg_' + f);
                    if (el && s[f] !== undefined) {
                        if (el.tagName === 'SELECT') {
                            let exists = Array.from(el.options).some(opt => opt.value === s[f]);
                            if (!exists && s[f]) {
                                const opt = document.createElement('option');
                                opt.value = s[f];
                                opt.textContent = s[f] + ' (سفارشی)';
                                el.appendChild(opt);
                            }
                        }
                        el.value = s[f];
                    }
                });
                const artistTagEl = document.getElementById('cfg_APPLY_DEFAULT_ARTIST_TAG');
                if (artistTagEl && s.APPLY_DEFAULT_ARTIST_TAG !== undefined) {
                    artistTagEl.checked = !!s.APPLY_DEFAULT_ARTIST_TAG;
                }
                const autoTitleEl = document.getElementById('cfg_AUTO_RENAME_FILE_TO_TITLE');
                if (autoTitleEl && s.AUTO_RENAME_FILE_TO_TITLE !== undefined) {
                    autoTitleEl.checked = !!s.AUTO_RENAME_FILE_TO_TITLE;
                }
                const studioArtistEl = document.getElementById('cfg_studio_auto_artist');
                if (studioArtistEl && s.APPLY_DEFAULT_ARTIST_TAG !== undefined) {
                    studioArtistEl.checked = !!s.APPLY_DEFAULT_ARTIST_TAG;
                }
                const studioTitleEl = document.getElementById('cfg_studio_auto_title');
                if (studioTitleEl && s.AUTO_RENAME_FILE_TO_TITLE !== undefined) {
                    studioTitleEl.checked = !!s.AUTO_RENAME_FILE_TO_TITLE;
                }

        async function toggleStudioMetaSetting(key, val) {
            try {
                const payload = {};
                payload[key] = val;
                if (key === 'APPLY_DEFAULT_ARTIST_TAG') {
                    const el1 = document.getElementById('cfg_APPLY_DEFAULT_ARTIST_TAG');
                    if (el1) el1.checked = val;
                    const el2 = document.getElementById('cfg_studio_auto_artist');
                    if (el2) el2.checked = val;
                } else if (key === 'AUTO_RENAME_FILE_TO_TITLE') {
                    const el1 = document.getElementById('cfg_AUTO_RENAME_FILE_TO_TITLE');
                    if (el1) el1.checked = val;
                    const el2 = document.getElementById('cfg_studio_auto_title');
                    if (el2) el2.checked = val;
                }
                let pwd = window.currentAdminPassword || sessionStorage.getItem('unfinit_admin_pwd') || '';
                await fetch('/api/settings/save', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json; charset=utf-8' },
                    body: JSON.stringify({
                        password: pwd,
                        settings: payload
                    })
                });
                const notice = document.getElementById('studioMetaSyncNotice');
                if (notice) {
                    notice.classList.remove('hidden');
                    setTimeout(() => notice.classList.add('hidden'), 2500);
                }
            } catch (err) {
                console.warn('toggleStudioMetaSetting error:', err);
            }
        }
        window.toggleStudioMetaSetting = toggleStudioMetaSetting;

                if (s.AI_PROVIDER) {
                    handleAiProviderChange(s.AI_PROVIDER, s.AI_MODEL);
                } else {
                    handleAiProviderChange('vyceai', s.AI_MODEL);
                }

                if (s.CUSTOM_KEYBOARD_LAYOUT && typeof initKeyboardCustomizer === 'function') {
                    try {
                        let kbLayout = typeof s.CUSTOM_KEYBOARD_LAYOUT === 'string' ? JSON.parse(s.CUSTOM_KEYBOARD_LAYOUT) : s.CUSTOM_KEYBOARD_LAYOUT;
                        if (Array.isArray(kbLayout) && kbLayout.length > 0) {
                            initKeyboardCustomizer(kbLayout);
                        } else {
                            initKeyboardCustomizer();
                        }
                    } catch (e) {
                        initKeyboardCustomizer();
                    }
                } else if (typeof initKeyboardCustomizer === 'function') {
                    initKeyboardCustomizer();
                }

                const p1 = document.getElementById('cfg_NEW_ADMIN_PASSWORD');
                const p2 = document.getElementById('cfg_CONFIRM_ADMIN_PASSWORD');
                if (p1) p1.value = '';
                if (p2) p2.value = '';
            } catch (err) {
                console.warn('populateSettingsForm notice:', err);
            }
        }

        function handleExportSettings() {
            let pwd = currentAdminPassword || sessionStorage.getItem('unfinit_admin_pwd') || '';
            if (!pwd) {
                pwd = prompt('جهت برون‌بری تنظیمات، لطفاً رمز عبور مدیریت را وارد کنید:') || '';
                if (!pwd) return;
                currentAdminPassword = pwd;
                sessionStorage.setItem('unfinit_admin_pwd', pwd);
            }
            window.open('/api/settings/export?password=' + encodeURIComponent(pwd), '_blank');
        }

        function handleExportContactsCSV() {
            let pwd = currentAdminPassword || sessionStorage.getItem('unfinit_admin_pwd') || '';
            if (!pwd) {
                pwd = prompt('جهت برون‌بری مخاطبین، لطفاً رمز عبور مدیریت را وارد کنید:') || '';
                if (!pwd) return;
                currentAdminPassword = pwd;
                sessionStorage.setItem('unfinit_admin_pwd', pwd);
            }
            window.open('/api/contacts/export_csv?pwd=' + encodeURIComponent(pwd), '_blank');
        }

        async function handleImportSettingsFile(input) {
            const file = input.files && input.files[0];
            if (!file) return;
            const confirmImport = confirm('آیا از بازنویسی و درون‌ریزی تنظیمات با فایل انتخابی مطمئن هستید؟');
            if (!confirmImport) {
                input.value = '';
                return;
            }

            const reader = new FileReader();
            reader.onload = async (e) => {
                try {
                    const importedObj = JSON.parse(e.target.result);
                    let pwd = currentAdminPassword || sessionStorage.getItem('unfinit_admin_pwd') || '';
                    if (!pwd) {
                        pwd = prompt('جهت درون‌بری تنظیمات، لطفاً رمز عبور مدیریت را وارد کنید:') || '';
                        if (!pwd) {
                            input.value = '';
                            return;
                        }
                        currentAdminPassword = pwd;
                        sessionStorage.setItem('unfinit_admin_pwd', pwd);
                    }
                    const res = await fetch('/api/settings/import', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json; charset=utf-8' },
                        body: JSON.stringify({
                            password: pwd,
                            settings: importedObj
                        })
                    });
                    const data = await res.json();
                    if (data.ok) {
                        showToast('✅ ' + (data.message || 'تنظیمات با موفقیت بازیابی شدند.'));
                        loadSettings();
                    } else {
                        showToast('❌ خطا در درون‌ریزی تنظیمات: ' + (data.error || ''));
                    }
                } catch (err) {
                    showToast('❌ خطا در خواندن یا تحلیل فایل JSON: ' + err.message);
                } finally {
                    input.value = '';
                }
            };
            reader.readAsText(file, 'utf-8');
        }

        async function handleSaveSettings(e) {
            if (e) e.preventDefault();
            const btn = (e && e.submitter) ? e.submitter : (document.getElementById('btnSaveSettings') || document.getElementById('btnSaveTokens'));
            const btn1 = document.getElementById('btnSaveSettings');
            const btn2 = document.getElementById('btnSaveTokens');
            const statusEl = document.getElementById('settingsSaveStatus') || document.getElementById('tokensSaveStatus');
            const status1 = document.getElementById('settingsSaveStatus');
            const status2 = document.getElementById('tokensSaveStatus');
            
            const orig1 = btn1 ? btn1.innerText : '💾 ذخیره و اعمال آنی تنظیمات';
            const orig2 = btn2 ? btn2.innerText : '💾 ذخیره سکرت‌ها و توکن‌ها';
            if (btn1) { btn1.disabled = true; btn1.innerText = 'در حال ذخیره...'; }
            if (btn2) { btn2.disabled = true; btn2.innerText = 'در حال ذخیره...'; }
            if (status1) status1.innerText = '';
            if (status2) status2.innerText = '';

            const p1 = (document.getElementById('cfg_NEW_ADMIN_PASSWORD')?.value || '').trim();
            const p2 = (document.getElementById('cfg_CONFIRM_ADMIN_PASSWORD')?.value || '').trim();
            if (p1) {
                if (p1 !== p2) {
                    showToast('❌ خطای تغییر رمز: تکرار رمز عبور جدید با رمز وارد شده همخوانی ندارد.');
                    if (btn1) { btn1.disabled = false; btn1.innerText = orig1; }
                    if (btn2) { btn2.disabled = false; btn2.innerText = orig2; }
                    return;
                }
            }

            const settings = {};
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
            fields.forEach(f => {
                const el = document.getElementById('cfg_' + f);
                if (el) {
                    const val = el.value.trim();
                    if (sensitiveKeys.includes(f)) {
                        if (val && !val.includes('••••') && !val.includes('****')) {
                            settings[f] = val;
                        }
                    } else {
                        settings[f] = val;
                    }
                }
            });
            const artistTagEl = document.getElementById('cfg_APPLY_DEFAULT_ARTIST_TAG');
            if (artistTagEl) {
                settings['APPLY_DEFAULT_ARTIST_TAG'] = artistTagEl.checked;
            }
            const autoTitleEl = document.getElementById('cfg_AUTO_RENAME_FILE_TO_TITLE');
            if (autoTitleEl) {
                settings['AUTO_RENAME_FILE_TO_TITLE'] = autoTitleEl.checked;
            }
            const activeProv = (document.getElementById('cfg_AI_PROVIDER')?.value || 'vyceai').toLowerCase();
            if (activeProv === 'custom') {
                const customModelVal = (document.getElementById('cfg_AI_MODEL_CUSTOM')?.value || '').trim();
                if (customModelVal) {
                    settings['AI_MODEL'] = customModelVal;
                }
            } else {
                const selModelVal = (document.getElementById('cfg_AI_MODEL')?.value || '').trim();
                if (selModelVal) {
                    settings['AI_MODEL'] = selModelVal;
                }
            }
            if (activeProv === 'vyceai' && settings['VYCEAI_API_KEY']) {
                settings['AI_API_KEY'] = settings['VYCEAI_API_KEY'];
            } else if (activeProv === 'nara' && settings['NARA_API_KEY']) {
                settings['AI_API_KEY'] = settings['NARA_API_KEY'];
            } else if (activeProv === 'gemini' && settings['GEMINI_API_KEY']) {
                settings['AI_API_KEY'] = settings['GEMINI_API_KEY'];
            }
            if (typeof getKeyboardCustomizerLayout === 'function') {
                const kl = getKeyboardCustomizerLayout();
                settings['CUSTOM_KEYBOARD_LAYOUT'] = kl;
                settings['MAIN_KEYBOARD_LAYOUT'] = kl;
            }
            if (p1) {
                settings['NEW_ADMIN_PASSWORD'] = p1;
            }

            let pwdToSend = currentAdminPassword || sessionStorage.getItem('unfinit_admin_pwd') || localStorage.getItem('unfinit_admin_pwd') || '';
            if (!pwdToSend) {
                pwdToSend = prompt('جهت تایید و ذخیره تنظیمات، لطفاً رمز عبور مدیریت را وارد کنید:') || '';
                if (!pwdToSend) {
                    showToast('❌ ذخیره تنظیمات لغو شد: رمز عبور مدیریت وارد نشد.');
                    if (btn1) { btn1.disabled = false; btn1.innerText = orig1; }
                    if (btn2) { btn2.disabled = false; btn2.innerText = orig2; }
                    return;
                }
                currentAdminPassword = pwdToSend;
                sessionStorage.setItem('unfinit_admin_pwd', pwdToSend);
            }

            try {
                const res = await fetch('/api/settings', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json; charset=utf-8' },
                    body: JSON.stringify({
                        password: pwdToSend,
                        settings: settings
                    })
                });
                const data = await res.json();
                if (data.ok) {
                    if (p1) {
                        currentAdminPassword = p1;
                        sessionStorage.setItem('unfinit_admin_pwd', p1);
                        localStorage.setItem('unfinit_admin_pwd', p1);
                        const p1El = document.getElementById('cfg_NEW_ADMIN_PASSWORD');
                        const p2El = document.getElementById('cfg_CONFIRM_ADMIN_PASSWORD');
                        if (p1El) p1El.value = '';
                        if (p2El) p2El.value = '';
                    }
                    const successMsg = '✅ ' + (data.message || 'تنظیمات و سکرت‌های ابری با موفقیت ذخیره و در Hugging Face اعمال شد!');
                    if (status1) status1.innerText = successMsg;
                    if (status2) status2.innerText = successMsg;
                    setTimeout(() => {
                        if (status1) status1.innerText = '';
                        if (status2) status2.innerText = '';
                    }, 5000);
                } else {
                    showToast('❌ خطا در ذخیره تنظیمات: ' + (data.error || ''));
                }
            } catch (err) {
                showToast('❌ خطای ارتباط: ' + err.message);
            } finally {
                if (btn1) { btn1.disabled = false; btn1.innerText = orig1; }
                if (btn2) { btn2.disabled = false; btn2.innerText = orig2; }
            }
        }

        async function copyAllLogs() {
            const btnText = document.getElementById('copyBtnText');
            try {
                const res = await fetch('/api/logs');
                const data = await res.json();
                let textToCopy = '';
                if (data.ok && Array.isArray(data.logs)) {
                    textToCopy = data.logs.join('\n');
                } else {
                    textToCopy = document.getElementById('logContainer').innerText;
                }
                await navigator.clipboard.writeText(textToCopy);
                btnText.innerText = '✅ کپی شد!';
                setTimeout(() => { btnText.innerText = 'کپی کل لاگ‌ها'; }, 2500);
            } catch (err) {
                btnText.innerText = '❌ خطا در کپی';
                setTimeout(() => { btnText.innerText = 'کپی کل لاگ‌ها'; }, 2000);
            }
        }

        async function fetchLogs() {
            try {
                const res = await fetch('/api/logs');
                const data = await res.json();
                if (data.ok && Array.isArray(data.logs)) {
                    const container = document.getElementById('logContainer');
                    if (data.logs.length === 0) {
                        container.innerHTML = '<div class="text-slate-500">هیچ لاگی هنوز ثبت نشده است.</div>';
                    } else {
                        container.innerHTML = data.logs.map(l => {
                            let color = 'text-slate-300';
                            if (l.includes('[ERROR]')) color = 'text-rose-400 font-bold';
                            else if (l.includes('[WARNING]')) color = 'text-amber-300';
                            else if (l.includes('[INFO]')) color = 'text-cyan-300';
                            return `<div class="${color}">${l.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</div>`;
                        }).join('');
                        container.scrollTop = container.scrollHeight;
                    }
                }
            } catch (e) {}
        }
        fetchLogs();
        setInterval(fetchLogs, 4000);
        let selectedLogoBase64 = null;
        function handleLogoFileSelect(input) {
            try {
                const file = input.files && input.files[0];
                if (!file) return;
                const reader = new FileReader();
                reader.onload = function(e) {
                    selectedLogoBase64 = e.target.result;
                    const preview = document.getElementById('panelLogoPreview');
                    if (preview) {
                        preview.src = selectedLogoBase64;
                        preview.style.display = 'block';
                        if (preview.nextElementSibling) preview.nextElementSibling.style.display = 'none';
                    }
                    const btn = document.getElementById('btnUploadLogo');
                    if (btn) {
                        btn.disabled = false;
                        btn.classList.remove('bg-cyan-600/50', 'text-slate-400', 'cursor-not-allowed');
                        btn.classList.add('bg-cyan-600', 'hover:bg-cyan-500', 'text-white', 'shadow-md');
                    }
                };
                reader.readAsDataURL(file);
            } catch (err) {
                console.error('handleLogoFileSelect error:', err);
            }
        }

        async function uploadCustomLogo() {
            if (!selectedLogoBase64) return;
            const btn = document.getElementById('btnUploadLogo');
            const status = document.getElementById('logoUploadStatus');
            const origText = btn ? btn.innerHTML : '';
            if (btn) { btn.disabled = true; btn.innerText = 'در حال آپلود...'; }
            if (status) { status.className = 'text-xs text-cyan-400'; status.innerText = 'در حال پردازش و ذخیره تصویر لوگو...'; }

            let pwd = currentAdminPassword || sessionStorage.getItem('unfinit_admin_pwd') || localStorage.getItem('unfinit_admin_pwd') || '';
            try {
                const res = await fetch('/api/upload/logo', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json; charset=utf-8' },
                    body: JSON.stringify({
                        password: pwd,
                        image: selectedLogoBase64
                    })
                });
                const data = await res.json();
                if (data.ok) {
                    const newUrl = data.url || ('/static/logo.png?t=' + Date.now());
                    const headerImg = document.getElementById('headerLogoImg');
                    const loginImg = document.getElementById('loginLogoImg');
                    const previewImg = document.getElementById('panelLogoPreview');
                    [headerImg, loginImg, previewImg].forEach(img => {
                        if (img) {
                            img.src = newUrl;
                            img.style.display = 'block';
                            if (img.nextElementSibling) img.nextElementSibling.style.display = 'none';
                        }
                    });
                    if (status) {
                        status.className = 'text-xs text-emerald-400 font-bold';
                        status.innerText = '✅ لوگو با موفقیت ذخیره و در تمام بخش‌ها به‌روزرسانی شد.';
                    }
                } else {
                    if (status) {
                        status.className = 'text-xs text-rose-400 font-bold';
                        status.innerText = '❌ خطا: ' + (data.error || 'آپلود ناموفق بود.');
                    }
                }
            } catch (err) {
                if (status) {
                    status.className = 'text-xs text-rose-400 font-bold';
                    status.innerText = '❌ خطای شبکه: ' + err.message;
                }
            } finally {
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = origText || '<span>⬆️</span> آپلود و اعمال لوگو';
                }
            }
        }

        function clearLiveLogs() {
            const container = document.getElementById('logContainer');
            if (container) {
                container.innerHTML = '<div class="text-slate-500">صفحه نمایش لاگ‌ها پاکسازی شد.</div>';
            }
        }

        /**
         * بارگذاری تنظیمات پلن اشتراک پریمیوم (VIP Club) و نشانه روزانه
         */
        async function loadVipSettings() {
            try {
                const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                const res = await fetch('/api/vip/settings', {
                    headers: {
                        'Authorization': 'Bearer ' + pwd,
                        'X-Admin-Password': pwd
                    }
                });
                const data = await res.json();
                if (data.ok) {
                    const p = document.getElementById('cfgVipMonthlyPrice');
                    if (p) {
                        const raw = String(data.vip_monthly_price || '111000').replace(/[,،\s]/g, '');
                        p.value = Number(raw) ? Number(raw).toLocaleString('en-US') : '111,000';
                    }
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
                }
            } catch (err) {
                console.debug('loadVipSettings error', err);
            }
        }
        window.loadVipSettings = loadVipSettings;

        /**
         * ذخیره غیرهمگام (AJAX) تنظیمات پلن اشتراک پریمیوم و نشانه روزانه بدون رفرش صفحه
         */
        async function saveVipSettings(e) {
            if (e && e.preventDefault) e.preventDefault();
            const btn = document.getElementById('btnSaveVipSettings');
            const toast = document.getElementById('vipSaveToast');
            if (btn) {
                btn.disabled = true;
                btn.innerText = 'در حال ذخیره...';
            }
            try {
                const rawPrice = (document.getElementById('cfgVipMonthlyPrice')?.value || '111000').replace(/[,،\s]/g, '');
                const payload = {
                    vip_monthly_price: parseInt(rawPrice) || 111000,
                    vip_duration_days: parseInt(document.getElementById('cfgVipDurationDays')?.value || '30') || 30,
                    vip_card_number: (document.getElementById('cfgVipCardNumber')?.value || '').trim(),
                    vip_bale_payment_token: (document.getElementById('cfgVipBaleToken')?.value || '').trim(),
                    sign_reader_tag: (document.getElementById('cfgSignReaderTag')?.value || 'abasmanesh365').trim(),
                    sign_extract_chapters: !!document.getElementById('cfgSignExtractChapters')?.checked
                };

                const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                const res = await fetch('/api/vip/settings', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json; charset=utf-8',
                        'Authorization': 'Bearer ' + pwd,
                        'X-Admin-Password': pwd
                    },
                    body: JSON.stringify(payload)
                });
                const data = await res.json();
                if (data.ok) {
                    if (toast) {
                        toast.classList.remove('hidden');
                        toast.innerText = '✅ تنظیمات اشتراک پریمیوم و نشانه با موفقیت ذخیره شد.';
                        setTimeout(() => { toast.classList.add('hidden'); }, 4000);
                    }
                } else {
                    showToast('❌ خطا در ذخیره تنظیمات: ' + (data.error || 'ناموفق'));
                }
            } catch (err) {
                showToast('❌ خطای ارتباط با سرور: ' + err.message);
            } finally {
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = '<svg class="w-4 h-4 stroke-[2]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" /></svg><span>ذخیره تنظیمات اشتراک و نشانه</span>';
                }
            }
        }
        window.saveVipSettings = saveVipSettings;

        /**
         * بارگذاری لیست کامل کارت‌های فرکانس فراوانی و رندر سطرها به همراه دکمه‌های ویرایش و حذف.
         */
        async function loadFrequenciesTable() {
            const tbody = document.getElementById('frequencyTableBody');
            if (!tbody) return;
            try {
                tbody.innerHTML = '<tr><td colspan="5" class="py-6 text-center text-slate-400 animate-pulse">در حال فراخوانی داده‌ها...</td></tr>';
                const res = await fetch('/api/frequencies');
                const data = await res.json();
                if (!data.ok || !Array.isArray(data.frequencies) || data.frequencies.length === 0) {
                    window.UNFINIT_FREQUENCIES = [];
                    tbody.innerHTML = '<tr><td colspan="5" class="py-6 text-center text-slate-400">هیچ عبارتی ثبت نشده است.</td></tr>';
                    return;
                }
                window.UNFINIT_FREQUENCIES = data.frequencies;
                tbody.innerHTML = data.frequencies.map((item, idx) => {
                    const isMorning = item.category === 'MORNING';
                    const catBadge = isMorning 
                        ? '<span class="px-2.5 py-1 rounded-full text-[11px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">صبحگاهی</span>'
                        : '<span class="px-2.5 py-1 rounded-full text-[11px] font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">شبانگاهی</span>';
                    return `
                        <tr class="hover:bg-white/[0.02] transition">
                            <td class="py-3 px-4 text-center text-slate-400">${idx + 1}</td>
                            <td class="py-3 px-4 font-bold text-slate-100">${escapeHtml(item.title || '')}</td>
                            <td class="py-3 px-4 text-center">${catBadge}</td>
                            <td class="py-3 px-4 leading-relaxed" style="color: var(--text-muted);">${escapeHtml(item.text || '')}</td>
                            <td class="py-3 px-4 text-center">
                                <div class="flex items-center justify-center gap-1.5">
                                    <button type="button" onclick="openEditFrequencyModal('${escapeHtml(item.id)}')" title="ویرایش عبارت" class="p-1.5 rounded-lg bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-400 transition inline-flex items-center justify-center">
                                        <svg class="w-4 h-4 stroke-[2]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                            <path stroke-linecap="round" stroke-linejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L6.832 19.82a4.5 4.5 0 01-1.897 1.13l-2.685.8.8-2.685a4.5 4.5 0 011.13-1.897L16.863 4.487zm0 0L19.5 7.125" />
                                        </svg>
                                    </button>
                                    <button type="button" onclick="deleteFrequencyItem('${escapeHtml(item.id)}')" title="حذف عبارت" class="p-1.5 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 transition inline-flex items-center justify-center">
                                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                        </svg>
                                    </button>
                                </div>
                            </td>
                        </tr>
                    `;
                }).join('');
            } catch (err) {
                console.error('[loadFrequenciesTable error]:', err);
                tbody.innerHTML = '<tr><td colspan="5" class="py-6 text-center text-rose-400">خطا در بارگذاری لیست فرکانس‌ها.</td></tr>';
            }
        }

        /**
         * باز کردن مودال ویرایش کارت فرکانس فراوانی و تکمیل فیلدها با اطلاعات موجود.
         * ورودی: id (شناسه منحصربه‌فرد عبارت)
         */
        function openEditFrequencyModal(id) {
            if (!id) return;
            const items = window.UNFINIT_FREQUENCIES || [];
            const item = items.find(x => String(x.id) === String(id));
            if (!item) {
                showToast('عبارت مورد نظر در حافظه یافت نشد.');
                return;
            }
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
        }

        /**
         * بستن مودال ویرایش کارت فرکانس فراوانی.
         */
        function closeEditFrequencyModal() {
            const m = document.getElementById('modalEditFrequency');
            if (m) m.classList.add('hidden');
        }

        /**
         * ارسال درخواست ویرایش عبارت فرکانس فراوانی به سرور (/api/frequencies/edit).
         * ورودی: رویداد ارسال فرم (e)
         */
        async function submitEditFrequency(e) {
            if (e) e.preventDefault();
            const id = (document.getElementById('freqEditId')?.value || '').trim();
            const cat = document.getElementById('freqEditCategory')?.value || 'MORNING';
            const title = (document.getElementById('freqEditTitle')?.value || '').trim();
            const text = (document.getElementById('freqEditText')?.value || '').trim();
            if (!id || !title || !text) {
                showToast('لطفاً عنوان و متن عبارت را وارد نمایید.');
                return;
            }
            const btn = document.getElementById('btnSubmitEditFrequency');
            if (btn) btn.disabled = true;
            try {
                const res = await fetch('/api/frequencies/edit', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json; charset=utf-8' },
                    body: JSON.stringify({ id: id, category: cat, title: title, text: text })
                });
                const data = await res.json();
                if (data.ok) {
                    closeEditFrequencyModal();
                    loadFrequenciesTable();
                } else {
                    showToast('خطا در ویرایش عبارت: ' + (data.error || 'ناشناخته'));
                }
            } catch (err) {
                showToast('خطای ارتباط با سرور: ' + err.message);
            } finally {
                if (btn) btn.disabled = false;
            }
        }

        async function submitAddNewFrequency(e) {
            if (e) e.preventDefault();
            const cat = document.getElementById('freqNewCategory')?.value || 'MORNING';
            const title = (document.getElementById('freqNewTitle')?.value || '').trim();
            const text = (document.getElementById('freqNewText')?.value || '').trim();
            if (!title || !text) {
                showToast('لطفاً عنوان و متن عبارت را وارد نمایید.');
                return;
            }
            const btn = document.getElementById('btnSubmitFrequency');
            if (btn) btn.disabled = true;
            try {
                const res = await fetch('/api/frequencies/add', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json; charset=utf-8' },
                    body: JSON.stringify({ category: cat, title: title, text: text })
                });
                const data = await res.json();
                if (data.ok) {
                    document.getElementById('freqNewTitle').value = '';
                    document.getElementById('freqNewText').value = '';
                    loadFrequenciesTable();
                } else {
                    showToast('خطا در ثبت عبارت: ' + (data.error || 'ناشناخته'));
                }
            } catch (err) {
                showToast('خطای ارتباط با سرور: ' + err.message);
            } finally {
                if (btn) btn.disabled = false;
            }
        }

        async function deleteFrequencyItem(id) {
            if (!id) return;
            if (!confirm('آیا از حذف این عبارت فرکانس فراوانی اطمینان دارید؟')) return;
            try {
                const res = await fetch('/api/frequencies/delete', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json; charset=utf-8' },
                    body: JSON.stringify({ id: id })
                });
                const data = await res.json();
                if (data.ok) {
                    loadFrequenciesTable();
                } else {
                    showToast('خطا در حذف عبارت: ' + (data.error || 'ناشناخته'));
                }
            } catch (err) {
                showToast('خطای ارتباط با سرور: ' + err.message);
            }
        }

        function exportFrequenciesJSON() {
            const link = document.createElement('a');
            link.href = '/api/frequencies/export';
            link.download = 'frequencies_backup.json';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }

        async function handleImportFrequenciesFile(input) {
            if (!input || !input.files || !input.files[0]) return;
            const file = input.files[0];
            try {
                const text = await file.text();
                let parsed;
                try {
                    parsed = JSON.parse(text);
                } catch (e) {
                    showToast('خطا در تحلیل ساختار فایل JSON: ' + e.message);
                    input.value = '';
                    return;
                }
                if (!Array.isArray(parsed)) {
                    showToast('قالب فایل نامعتبر است. فایل JSON باید شامل آرایه‌ای از اشیاء کارت‌های فرکانس باشد.');
                    input.value = '';
                    return;
                }
                if (!confirm(`آیا از بارگذاری و بازنویسی ${parsed.length} عبارت فرکانس فراوانی اطمینان دارید؟`)) {
                    input.value = '';
                    return;
                }
                const res = await fetch('/api/frequencies/import', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json; charset=utf-8' },
                    body: JSON.stringify(parsed)
                });
                const data = await res.json();
                if (data.ok) {
                    showToast(`بانک فرکانس فراوانی با موفقیت به‌روزرسانی شد (${data.count} عبارت فعال).`);
                    loadFrequenciesTable();
                } else {
                    showToast('خطا در بارگذاری فایل: ' + (data.error || 'ناشناخته'));
                }
            } catch (err) {
                showToast('خطا در پردازش فایل: ' + err.message);
            } finally {
                input.value = '';
            }
        }

        // =========================================================================
        // ماژول مدیریت و شخصی‌سازی بصری کیبورد ربات‌ها (Visual Keyboard Customizer)
        // چیدمان پویا، جابجایی سطری و ستونی دکمه‌ها و پیش‌نمایش در موبایل
        // =========================================================================

        const DEFAULT_KEYBOARD_LAYOUT = [
            ["🛍️ دوره‌ها و محصولات"],
            ["✨ نشانه امروز من", "💎 اشتراک پریمیوم"],
            ["📁 دانلودها", "👤 حساب کاربری"]
        ];

        const CANONICAL_KEYBOARD_ACTIONS = [
            { text: "✨ نشانه امروز من", desc: "دریافت آیه و نشانه تصادفی روز" },
            { text: "💎 اشتراک پریمیوم", desc: "خرید و تمدید اشتراک پریمیوم ماهانه" },
            { text: "📁 دانلودها", desc: "آرشیو دانلودهای هدایای سایت" },
            { text: "🛍️ دوره‌ها و محصولات", desc: "فروشگاه دوره‌ها و فایل‌های دانلودی" },
            { text: "🌊 فرکانس فراوانی", desc: "ورق‌زن عبارات تاکیدی و فرکانس روز" },
            { text: "👤 حساب کاربری", desc: "مشاهده امتیازات، پلن پریمیوم و وضعیت حساب" },
            { text: "💬 پشتیبانی و تیکت", desc: "ارتباط با ادمین و تیکت پشتیبانی" }
        ];

        let activeKeyboardLayout = JSON.parse(JSON.stringify(DEFAULT_KEYBOARD_LAYOUT));

        /**
         * راه‌اندازی اولیه کیبورد کستومایزر با داده‌های ذخیره‌شده یا پیش‌فرض
         * @param {Array} layout آرایه دوبعدی حاوی سطرهای کیبورد
         */
        function initKeyboardCustomizer(layout) {
            try {
                if (Array.isArray(layout) && layout.length > 0) {
                    activeKeyboardLayout = JSON.parse(JSON.stringify(layout));
                } else {
                    activeKeyboardLayout = JSON.parse(JSON.stringify(DEFAULT_KEYBOARD_LAYOUT));
                }
                renderKeyboardCustomizer();
            } catch (err) {
                console.warn('initKeyboardCustomizer error:', err);
                activeKeyboardLayout = JSON.parse(JSON.stringify(DEFAULT_KEYBOARD_LAYOUT));
                renderKeyboardCustomizer();
            }
        }

        /**
         * رندر کامل ویرایشگر کیبورد و پیش‌نمایش ماک‌آپ موبایل
         */
        function renderKeyboardCustomizer() {
            renderKeyboardPool();
            renderKeyboardRows();
            renderKeyboardMockPreview();
        }

        /**
         * رندر چیپ‌های دکمه‌های مجاز سیستم
         */
        function renderKeyboardPool() {
            const poolEl = document.getElementById('keyboardActionsPool');
            if (!poolEl) return;
            poolEl.innerHTML = CANONICAL_KEYBOARD_ACTIONS.map(function(action, idx) {
                return '<button type="button" data-action-idx="' + idx + '" onclick="handleAddActionFromPool(this)" ' +
                    'class="theme-card-btn px-2.5 py-1 rounded-lg text-[11px] font-medium transition flex items-center gap-1.5 shadow-sm" ' +
                    'title="' + escapeHtml(action.desc) + '">' +
                    '<svg class="w-3 h-3 stroke-[2] text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">' +
                    '<path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" />' +
                    '</svg>' +
                    '<span>' + escapeHtml(action.text) + '</span>' +
                    '</button>';
            }).join('');
        }

        function handleAddActionFromPool(btn) {
            const idx = parseInt(btn.getAttribute('data-action-idx') || '0', 10);
            if (CANONICAL_KEYBOARD_ACTIONS[idx]) {
                addActionButtonToLayout(CANONICAL_KEYBOARD_ACTIONS[idx].text);
            }
        }

        /**
         * رندر سطرهای ویرایشگر کیبورد با کنترل‌های جابجایی
         */
        function renderKeyboardRows() {
            const container = document.getElementById('keyboardRowsContainer');
            if (!container) return;

            if (!activeKeyboardLayout || activeKeyboardLayout.length === 0) {
                container.innerHTML = '<div class="p-6 text-center rounded-xl border border-dashed text-slate-500 text-xs" style="border-color: var(--card-border);">' +
                    'کیبورد در حال حاضر سطری ندارد. از دکمه «افزودن سطر جدید» استفاده کنید.' +
                    '</div>';
                return;
            }

            container.innerHTML = activeKeyboardLayout.map(function(row, rIdx) {
                const rowButtonsHtml = row.map(function(btnText, cIdx) {
                    const isLast = (cIdx === row.length - 1);
                    const isFirst = (cIdx === 0);
                    return '<div class="p-2 rounded-lg border flex items-center justify-between gap-1.5 shadow-sm" style="background: var(--input-bg); border-color: var(--border-color);">' +
                        '<input type="text" value="' + escapeHtml(btnText) + '" onchange="updateButtonText(' + rIdx + ', ' + cIdx + ', this.value)" ' +
                        'class="bg-transparent text-xs text-slate-100 font-medium flex-1 outline-none focus:text-cyan-300 transition">' +
                        '<div class="flex items-center gap-0.5 shrink-0">' +
                        '<button type="button" onclick="shiftKeyboardButton(' + rIdx + ', ' + cIdx + ', 1)" ' + (isLast ? 'disabled ' : '') +
                        'class="p-1 rounded text-slate-400 hover:text-slate-200 disabled:opacity-20 transition" title="انتقال به چپ">' +
                        '<svg class="w-3 h-3 stroke-[2]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" /></svg>' +
                        '</button>' +
                        '<button type="button" onclick="shiftKeyboardButton(' + rIdx + ', ' + cIdx + ', -1)" ' + (isFirst ? 'disabled ' : '') +
                        'class="p-1 rounded text-slate-400 hover:text-slate-200 disabled:opacity-20 transition" title="انتقال به راست">' +
                        '<svg class="w-3 h-3 stroke-[2]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" /></svg>' +
                        '</button>' +
                        '<button type="button" onclick="deleteKeyboardButton(' + rIdx + ', ' + cIdx + ')" ' +
                        'class="p-1 rounded text-rose-400 hover:text-rose-300 transition" title="حذف دکمه">' +
                        '<svg class="w-3 h-3 stroke-[2]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M19.5 12h-15" /></svg>' +
                        '</button>' +
                        '</div>' +
                        '</div>';
                }).join('');

                const isFirstRow = (rIdx === 0);
                const isLastRow = (rIdx === activeKeyboardLayout.length - 1);
                const colsClass = row.length === 1 ? 'grid-cols-1' : (row.length === 2 ? 'grid-cols-1 sm:grid-cols-2' : 'grid-cols-1 sm:grid-cols-3');

                return '<div class="p-3.5 rounded-xl border space-y-2.5 transition" style="background: var(--card-bg); border-color: var(--card-border);">' +
                    '<div class="flex items-center justify-between pb-2 border-b border-white/5 text-xs">' +
                    '<div class="flex items-center gap-2">' +
                    '<span class="text-cyan-400 font-bold">سطر ' + (rIdx + 1) + '</span>' +
                    '<span class="text-[10px] text-slate-400">(' + row.length + ' دکمه)</span>' +
                    '</div>' +
                    '<div class="flex items-center gap-1">' +
                    '<button type="button" onclick="moveKeyboardRow(' + rIdx + ', -1)" ' + (isFirstRow ? 'disabled ' : '') +
                    'class="p-1 rounded text-slate-400 hover:text-slate-200 disabled:opacity-30 disabled:cursor-not-allowed transition" title="انتقال سطر به بالا">' +
                    '<svg class="w-3.5 h-3.5 stroke-[2]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M4.5 15.75l7.5-7.5 7.5 7.5" /></svg>' +
                    '</button>' +
                    '<button type="button" onclick="moveKeyboardRow(' + rIdx + ', 1)" ' + (isLastRow ? 'disabled ' : '') +
                    'class="p-1 rounded text-slate-400 hover:text-slate-200 disabled:opacity-30 disabled:cursor-not-allowed transition" title="انتقال سطر به پایین">' +
                    '<svg class="w-3.5 h-3.5 stroke-[2]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" /></svg>' +
                    '</button>' +
                    '<button type="button" onclick="removeKeyboardRow(' + rIdx + ')" ' +
                    'class="p-1 rounded text-rose-400 hover:text-rose-300 transition" title="حذف این سطر">' +
                    '<svg class="w-3.5 h-3.5 stroke-[2]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>' +
                    '</button>' +
                    '</div>' +
                    '</div>' +
                    '<div class="grid ' + colsClass + ' gap-2">' +
                    rowButtonsHtml +
                    '</div>' +
                    '</div>';
            }).join('');
        }

        /**
         * رندر پیش‌نمایش زنده در قاب شبیه‌ساز موبایل
         */
        function renderKeyboardMockPreview() {
            const preview = document.getElementById('mockKeyboardPreview');
            if (!preview) return;

            if (!activeKeyboardLayout || activeKeyboardLayout.length === 0) {
                preview.innerHTML = '<div class="text-[10px] text-center text-slate-500 py-3">کیبورد خالی است</div>';
                return;
            }

            preview.innerHTML = activeKeyboardLayout.map(function(row) {
                const btns = row.map(function(btn) {
                    return '<div class="flex-1 py-2 px-1 rounded-xl text-center text-[10px] font-medium border truncate transition select-none shadow-sm" ' +
                        'style="background: var(--input-bg); border-color: var(--card-border); color: var(--text-main);">' +
                        escapeHtml(btn) +
                        '</div>';
                }).join('');
                return '<div class="flex items-center gap-1.5 w-full">' + btns + '</div>';
            }).join('');
        }

        function addKeyboardRow() {
            activeKeyboardLayout.push([]);
            renderKeyboardCustomizer();
        }

        function removeKeyboardRow(rIdx) {
            activeKeyboardLayout.splice(rIdx, 1);
            renderKeyboardCustomizer();
        }

        function moveKeyboardRow(rIdx, dir) {
            const targetIdx = rIdx + dir;
            if (targetIdx < 0 || targetIdx >= activeKeyboardLayout.length) return;
            const temp = activeKeyboardLayout[rIdx];
            activeKeyboardLayout[rIdx] = activeKeyboardLayout[targetIdx];
            activeKeyboardLayout[targetIdx] = temp;
            renderKeyboardCustomizer();
        }

        function addActionButtonToLayout(btnText) {
            if (activeKeyboardLayout.length === 0) {
                activeKeyboardLayout.push([]);
            }
            const lastRow = activeKeyboardLayout[activeKeyboardLayout.length - 1];
            if (lastRow.length >= 2) {
                activeKeyboardLayout.push([btnText]);
            } else {
                lastRow.push(btnText);
            }
            renderKeyboardCustomizer();
        }

        function deleteKeyboardButton(rIdx, cIdx) {
            if (activeKeyboardLayout[rIdx]) {
                activeKeyboardLayout[rIdx].splice(cIdx, 1);
                if (activeKeyboardLayout[rIdx].length === 0 && activeKeyboardLayout.length > 1) {
                    activeKeyboardLayout.splice(rIdx, 1);
                }
                renderKeyboardCustomizer();
            }
        }

        function shiftKeyboardButton(rIdx, cIdx, dir) {
            const row = activeKeyboardLayout[rIdx];
            if (!row) return;
            const targetIdx = cIdx + dir;
            if (targetIdx < 0 || targetIdx >= row.length) return;
            const temp = row[cIdx];
            row[cIdx] = row[targetIdx];
            row[targetIdx] = temp;
            renderKeyboardCustomizer();
        }

        function updateButtonText(rIdx, cIdx, val) {
            if (activeKeyboardLayout[rIdx] && activeKeyboardLayout[rIdx][cIdx] !== undefined) {
                activeKeyboardLayout[rIdx][cIdx] = (val || '').trim();
                renderKeyboardMockPreview();
            }
        }

        function resetKeyboardLayoutToDefault() {
            activeKeyboardLayout = JSON.parse(JSON.stringify(DEFAULT_KEYBOARD_LAYOUT));
            renderKeyboardCustomizer();
        }

        function getKeyboardCustomizerLayout() {
            return activeKeyboardLayout
                .map(function(row) { return row.filter(function(btn) { return btn && btn.trim(); }); })
                .filter(function(row) { return row.length > 0; });
        }

        async function saveKeyboardLayout() {
            const btn = document.getElementById('btnSaveKeyboardLayout');
            const notice = document.getElementById('keyboardSaveNotice');
            if (btn) { btn.disabled = true; btn.innerText = 'در حال ذخیره...'; }
            try {
                const layout = getKeyboardCustomizerLayout();
                let pwd = window.currentAdminPassword || sessionStorage.getItem('unfinit_admin_pwd') || '';
                const res = await fetch('/api/settings/save', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json; charset=utf-8' },
                    body: JSON.stringify({
                        password: pwd,
                        settings: {
                            CUSTOM_KEYBOARD_LAYOUT: layout,
                            MAIN_KEYBOARD_LAYOUT: layout
                        }
                    })
                });
                const data = await res.json();
                if (data.ok) {
                    if (notice) {
                        notice.classList.remove('hidden');
                        setTimeout(function() { notice.classList.add('hidden'); }, 3500);
                    }
                } else {
                    showToast('خطا در ذخیره کیبورد: ' + (data.error || 'ناشناخته'));
                }
            } catch (err) {
                showToast('خطا در ارتباط با سرور: ' + err.message);
            } finally {
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = '<svg class="w-3.5 h-3.5 stroke-[2]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5" /></svg><span>ذخیره کیبورد</span>';
                }
            }
        }

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

                try { initKeyboardCustomizer(); } catch (e) { console.warn('initKeyboardCustomizer startup notice:', e); }

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
            } catch (err) {
                console.error('[UNFINIT AI & Settings Module Error]:', err);
            }
        })();