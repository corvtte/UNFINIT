c = open('services/web_panel.py', encoding='utf-8').read()

old_js = '''const payload = {
                                cookie: document.getElementById('quick_FEED_AUTH_COOKIE').value,
                                email: document.getElementById('quick_FEED_AUTH_EMAIL').value,
                                password: document.getElementById('quick_FEED_AUTH_PASSWORD').value
                            };
                            const saveRes = await fetch('/api/crawler/save-auth', { method: 'POST', headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + pwd }, body: JSON.stringify(payload) });
                            const saveData = await saveRes.json();
                            
                            if (saveData.success) {
                                const res = await fetch('/api/crawler/test-auth', { method: 'POST', body: '{}', headers: {'Authorization': 'Bearer ' + pwd} });
                                const data = await res.json();
                                const resDiv = document.getElementById('quickFeedAuthResult');
                                if (resDiv) {
                                    resDiv.classList.remove('hidden');
                                    if (data.success) {
                                        resDiv.innerHTML = '<span class="text-emerald-500 font-bold">✅ ورود موفق:</span> ' + data.message;
                                        showToast('✅ ورود موفقیت‌آمیز بود');'''

new_js = '''const payload = {
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
                                }
                                const resDiv = document.getElementById('quickFeedAuthResult');
                                if (resDiv) {
                                    resDiv.classList.remove('hidden');
                                    if (data.success) {
                                        resDiv.innerHTML = '<span class="text-emerald-500 font-bold">✅ ورود موفق:</span> ' + data.message;
                                        showToast('✅ ورود موفقیت‌آمیز بود');'''

c = c.replace(old_js, new_js)
open('services/web_panel.py', 'w', encoding='utf-8').write(c)
print('Updated toggleCrawlerAuth JS block!')
