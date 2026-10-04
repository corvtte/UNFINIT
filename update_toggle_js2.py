import re

c = open('services/web_panel.py', encoding='utf-8').read()

# Replace the test-auth call inside toggleCrawlerAuth
old_line = r"const res = await fetch\('/api/crawler/test-auth', \{ method: 'POST', body: '\{\}', headers: \{'Authorization': 'Bearer ' \+ pwd\} \}\);"
new_line = '''const res = await fetch('/api/crawler/test-auth', { method: 'POST', body: JSON.stringify({force_login: true}), headers: {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + pwd} });
                                const data = await res.json();
                                if (data.cookie) {
                                    document.getElementById('quick_FEED_AUTH_COOKIE').value = data.cookie;
                                    
                                    // Make sure it saves to backend settings
                                    await fetch('/api/crawler/save-auth', { 
                                        method: 'POST', 
                                        headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + pwd }, 
                                        body: JSON.stringify({cookie: data.cookie, email: document.getElementById('quick_FEED_AUTH_EMAIL').value, password: document.getElementById('quick_FEED_AUTH_PASSWORD').value}) 
                                    });
                                }'''

# Let's just find and replace manually
idx = c.find("const res = await fetch('/api/crawler/test-auth', { method: 'POST', body: '{}', headers: {'Authorization': 'Bearer ' + pwd} });")
if idx != -1:
    idx2 = c.find("const data = await res.json();", idx) + len("const data = await res.json();")
    c = c[:idx] + new_line + c[idx2:]
    
    
# Now, let's also update the button to say "خروج از حساب مرجع" upon SUCCESS!
find_success = "btn.className = 'flex-1 py-2 rounded-xl text-[13px] font-bold bg-rose-600 hover:bg-rose-500 text-white transition flex justify-center items-center gap-1.5 shadow-sm shadow-rose-900/30 border border-rose-500/50';"
if find_success in c:
    pass # It's already doing it!

# Now let's fix saveQuickFeedAuth (the modal save button) to also use force_login: true ? No, saveQuickFeedAuth just calls /api/crawler/save-auth.

open('services/web_panel.py', 'w', encoding='utf-8').write(c)
print('Updated web_panel.py toggle JS logic!')
