import sys
filepath = 'services/web_panel.py'
text = open(filepath, encoding='utf-8').read()

js_func = '''                window.testCrawlerConnection = async function(btn) {'''

new_js = '''                window.logoutCrawlerConnection = async function(btn) {
                    const origHtml = btn.innerHTML;
                    btn.disabled = true;
                    btn.innerHTML = '<span class="flex items-center gap-2"><svg class="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg> در حال خروج...</span>';
                    try {
                        const pwd = window.currentAdminPassword || localStorage.getItem('unfinit_admin_pwd') || '';
                        const res = await fetch('/api/crawler/logout', { method: 'POST', headers: { 'Authorization': 'Bearer ' + pwd } });
                        const data = await res.json();
                        if (data.success) {
                            showToast('✅ ' + data.message);
                            document.getElementById('quick_FEED_AUTH_COOKIE').value = '';
                            document.getElementById('quick_FEED_AUTH_EMAIL').value = '';
                            document.getElementById('quick_FEED_AUTH_PASSWORD').value = '';
                            const b = document.getElementById('crawlerStatusBadge');
                            if (b) {
                                b.className = 'text-[10px] px-2 py-0.5 rounded-full bg-amber-600 text-white shadow-sm';
                                b.innerText = 'نیاز به لاگین (REQUIRE_AUTH)';
                            }
                            const resDiv = document.getElementById('quickFeedAuthResult');
                            if (resDiv) {
                                resDiv.classList.remove('hidden');
                                resDiv.innerHTML = '<span class="text-rose-500 font-bold">✅ خروج موفق:</span> نشست مرجع لغو شد.';
                            }
                        }
                    } catch (e) {
                        showToast('خطا در خروج از حساب', 'error');
                    } finally {
                        btn.innerHTML = origHtml;
                        btn.disabled = false;
                    }
                };

                window.testCrawlerConnection = async function(btn) {'''

if js_func in text:
    text = text.replace(js_func, new_js)
    open(filepath, 'w', encoding='utf-8').write(text)
    print("Logout JS added")
else:
    print("JS pattern not found")
