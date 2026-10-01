import re
p = 'services/web_panel.py'
text = open(p, encoding='utf-8').read()

js_save = r"""                window.saveQuickFeedAuth = async function(btn) {{
                    const orig = btn.innerHTML;
                    btn.innerHTML = 'در حال بررسی...';
                    btn.disabled = true;
                    const resDiv = document.getElementById('quickFeedAuthResult');
                    if (resDiv) resDiv.classList.add('hidden');
                    try {{
                        const cookie = document.getElementById('quick_FEED_AUTH_COOKIE').value;
                        const email = document.getElementById('quick_FEED_AUTH_EMAIL').value;
                        const pass = document.getElementById('quick_FEED_AUTH_PASSWORD').value;
                        const cfgC = document.getElementById('cfg_FEED_AUTH_COOKIE');
                        const cfgE = document.getElementById('cfg_FEED_AUTH_EMAIL');
                        const cfgP = document.getElementById('cfg_FEED_AUTH_PASSWORD');
                        if (cfgC) cfgC.value = cookie;
                        if (cfgE) cfgE.value = email;
                        if (cfgP) cfgP.value = pass;
                        
                        const btnSave = document.getElementById('btnSaveSettings');
                        if (btnSave && window.handleSaveSettings) {{
                            await window.handleSaveSettings();
                        }}
                        
                        const res = await fetch('/api/crawler/test-auth', {{ method: 'POST', body: '{{}}' }});
                        const data = await res.json();
                        
                        if (data.success) {{
                            alert('✅ ' + (data.message || 'ورود موفقیت‌آمیز بود و نشست معتبر دریافت شد.'));
                            window.closeFeedAuthModal();
                            const b = document.getElementById('crawlerStatusBadge');
                            if (b) {{
                                b.className = 'text-[10px] px-2 py-0.5 rounded-full bg-emerald-600 text-white shadow-sm';
                                b.innerText = 'نشست فعال (ONLINE)';
                            }}
                        }} else {{
                            if (resDiv) {{
                                resDiv.classList.remove('hidden');
                                resDiv.className = 'mt-3 p-3 rounded-xl text-[10px] font-mono border text-left whitespace-pre-wrap break-all bg-rose-950/40 border-rose-900/50 text-rose-300';
                                resDiv.innerHTML = '<strong>❌ خطا:</strong><br>' + (data.message || 'پاسخی دریافت نشد');
                            }} else {{
                                alert('❌ خطا: ' + (data.message || 'پاسخی دریافت نشد'));
                            }}
                        }}
                    }} catch (e) {{
                        if (resDiv) {{
                            resDiv.classList.remove('hidden');
                            resDiv.className = 'mt-3 p-3 rounded-xl text-[10px] font-mono border text-left whitespace-pre-wrap break-all bg-rose-950/40 border-rose-900/50 text-rose-300';
                            resDiv.innerHTML = '<strong>❌ خطای شبکه:</strong><br>' + e.message;
                        }} else {{
                            alert('❌ خطای شبکه: ' + e.message);
                        }}
                    }} finally {{
                        btn.innerHTML = orig;
                        btn.disabled = false;
                    }}
                }};"""

js_test = r"""                window.testCrawlerConnection = async function(btn) {{
                    const origHtml = btn.innerHTML;
                    btn.disabled = true;
                    btn.innerHTML = '<span class="flex items-center gap-2"><svg class="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg> در حال بررسی...</span>';
                    try {{
                        const res = await fetch('/api/crawler/test-auth', {{ method: 'POST', body: '{{}}' }});
                        const data = await res.json();
                        var msg = (data.success ? '✅ ' : '❌ ') + (data.message || 'پاسخی دریافت نشد');
                        if (data.success) {{
                            alert(msg);
                            const b = document.getElementById('crawlerStatusBadge');
                            if (b) {{
                                b.className = 'text-[10px] px-2 py-0.5 rounded-full bg-emerald-600 text-white shadow-sm';
                                b.innerText = 'نشست فعال (ONLINE)';
                            }}
                        }} else {{
                            alert(msg);
                        }}
                    }} catch (e) {{
                        alert('❌ خطای شبکه: ' + e.message);
                    }} finally {{
                        btn.disabled = false;
                        btn.innerHTML = origHtml;
                    }}
                }};"""

text = re.sub(r'window\.saveQuickFeedAuth = async function.*?\n\s+}};\n', js_save + '\n', text, flags=re.DOTALL)
text = re.sub(r'window\.testCrawlerConnection = async function.*?\n\s+}};\n', js_test + '\n', text, flags=re.DOTALL)

# Add `cfg = settings` right before the template to avoid the NameError if the user expects `cfg.get`.
text = text.replace('premium_categories_html = ""', 'cfg = settings\n    premium_categories_html = ""')
text = text.replace("{settings.get('FEED_AUTH_COOKIE', '')}", "{cfg.get('FEED_AUTH_COOKIE', '')}")

open(p, 'w', encoding='utf-8').write(text)
