
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

                function toggleAdminLoginPwd() {
                    var inp = document.getElementById('adminPasswordInput');
                    if (inp) {
                        inp.type = (inp.type === 'password') ? 'text' : 'password';
                    }
                }

                async function executeAdminLogin() {
                    var btn = document.getElementById('loginBtn');
                    var errMsg = document.getElementById('loginErrorMsg');
                    var pwdInput = document.getElementById('adminPasswordInput');
                    var pwd = pwdInput ? pwdInput.value.trim() : '';

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
                        var res = await fetch('/api/login', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json; charset=utf-8' },
                            body: JSON.stringify({ password: pwd })
                        });
                        var data = await res.json();
                        if (data && data.ok) {
                            applySuccessfulLogin(pwd);
                            return;
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

                function applySuccessfulLogin(pwd) {
                    try {
                        localStorage.setItem('unfinit_auth', 'true');
                        localStorage.setItem('unfinit_auth_token', 'authenticated');
                        localStorage.setItem('unfinit_admin_pwd', pwd);
                        sessionStorage.setItem('unfinit_auth', 'true');
                        sessionStorage.setItem('unfinit_auth_token', 'authenticated');
                        sessionStorage.setItem('unfinit_admin_pwd', pwd);
                    } catch (e) {}
                    window.currentAdminPassword = pwd;

                    var gate = document.getElementById('loginGate');
                    var app = document.getElementById('appMain');
                    if (gate) {
                        gate.style.setProperty('display', 'none', 'important');
                        gate.classList.add('hidden');
                    }
                    if (app) {
                        app.style.setProperty('display', 'block', 'important');
                        app.classList.remove('hidden');
                    }

                    try {
                        var savedTab = localStorage.getItem('unfinit_active_tab') || 'tab-studio';
                        if (typeof switchTab === 'function') {
                            switchTab(savedTab);
                        }
                    } catch (e) {
                        console.warn('Tab switch notice:', e);
                    }
                }

                function checkAdminLoginOnLoad() {
                    var token = localStorage.getItem('unfinit_auth_token') || sessionStorage.getItem('unfinit_auth_token') || localStorage.getItem('unfinit_auth');
                    var pwd = localStorage.getItem('unfinit_admin_pwd') || sessionStorage.getItem('unfinit_admin_pwd');
                    var gate = document.getElementById('loginGate');
                    var app = document.getElementById('appMain');

                    if ((token === 'authenticated' || token === 'true') && pwd) {
                        window.currentAdminPassword = pwd;
                        if (gate) {
                            gate.style.setProperty('display', 'none', 'important');
                            gate.classList.add('hidden');
                        }
                        if (app) {
                            app.style.setProperty('display', 'block', 'important');
                            app.classList.remove('hidden');
                        }
                    }
                }

                
        // ================= ANTIGRAVITY OFFICIAL THEMES (Single Source of Truth) =================
        window.UNFINIT_THEMES = {themes_data_json};
        function applyAntigravityTheme(themeKey, syncServer) {
            var themes = window.UNFINIT_THEMES || {};
            if (!themes[themeKey]) themeKey = 'default-dark';
            var themeObj = themes[themeKey] || {};
            var vars = themeObj.variables || {};

            try {
                document.documentElement.setAttribute('data-theme', themeKey);
                Object.keys(themes).forEach(function(t) {
                    document.body.classList.remove('theme-' + t);
                });
                document.body.classList.add('theme-' + themeKey);

                // Apply CSS variables to :root directly
                Object.keys(vars).forEach(function(k) {
                    document.documentElement.style.setProperty(k, vars[k]);
                });
                localStorage.setItem('unfinit_theme', themeKey);
            } catch(e) {}

            var sel = document.getElementById('themeSwitcherSelect');
            if (sel && sel.value !== themeKey) {
                sel.value = themeKey;
            }
            if (syncServer !== false) {
                try {
                    fetch('/api/settings/theme', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json; charset=utf-8' },
                        body: JSON.stringify({ theme: themeKey })
                    }).catch(function(e) {});
                } catch(e) {}
            }
        }
        window.changeTheme = applyAntigravityTheme;
        window.applyAntigravityTheme = applyAntigravityTheme;
        try {
            var initTheme = localStorage.getItem('unfinit_theme') || '{saved_theme}';
            applyAntigravityTheme(initTheme, false);
        } catch(e) {}

                window.toggleAdminLoginPwd = toggleAdminLoginPwd;
                window.executeAdminLogin = executeAdminLogin;
                window.handleLoginSubmit = executeAdminLogin;

                checkAdminLoginOnLoad();
                document.addEventListener('DOMContentLoaded', checkAdminLoginOnLoad);
            