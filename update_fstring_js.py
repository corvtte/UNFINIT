import re

c = open('services/web_panel.py', encoding='utf-8').read()

old_str = "fetch('/api/crawler/test-auth', {{ method: 'POST', body: '{{}}', headers: {{'Authorization': 'Bearer ' + pwd}} }});"

# Notice the doubled braces for JS objects because the Python code uses an f-string!
new_str = """fetch('/api/crawler/test-auth', {{ method: 'POST', body: JSON.stringify({{force_login: true}}), headers: {{'Content-Type': 'application/json', 'Authorization': 'Bearer ' + pwd}} }});
                                const data = await res.json();
                                if (data.cookie) {{
                                    document.getElementById('quick_FEED_AUTH_COOKIE').value = data.cookie;
                                    
                                    await fetch('/api/crawler/save-auth', {{ 
                                        method: 'POST', 
                                        headers: {{ 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + pwd }}, 
                                        body: JSON.stringify({{cookie: data.cookie, email: document.getElementById('quick_FEED_AUTH_EMAIL').value, password: document.getElementById('quick_FEED_AUTH_PASSWORD').value}}) 
                                    }});
                                }}"""

# Replace ONLY inside toggleCrawlerAuth. Let's find it.
idx = c.find("window.toggleCrawlerAuth")
if idx != -1:
    idx_end = c.find("window.closeFeedAuthModal", idx)
    block = c[idx:idx_end]
    new_block = block.replace(old_str, new_str)
    
    # Also fix the success button change:
    old_btn_success = "btn.className = 'flex-1 py-2 rounded-xl text-[13px] font-bold bg-rose-600 hover:bg-rose-500 text-white transition flex justify-center items-center gap-1.5 shadow-sm shadow-rose-900/30 border border-rose-500/50';"
    # Let's ensure it is there:
    if "bg-rose-600" not in block:
        # We need to change the button text to 'خروج از حساب مرجع'
        old_btn_update = "btn.innerHTML = '<span class=\"text-emerald-500 font-bold\">✅ ورود موفق:</span> ' + data.message;"
        new_btn_update = """btn.innerHTML = '<svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 16l-4-4m0 0l4-4m-4 4h14m-5 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h7a3 3 0 013 3v1"></path></svg><span>خروج از حساب مرجع</span>';
                                        btn.className = 'flex-1 py-2 rounded-xl text-[13px] font-bold bg-rose-600 hover:bg-rose-500 text-white transition flex justify-center items-center gap-1.5 shadow-sm shadow-rose-900/30 border border-rose-500/50';"""
        new_block = new_block.replace(old_btn_update, new_btn_update)
    
    c = c[:idx] + new_block + c[idx_end:]

open('services/web_panel.py', 'w', encoding='utf-8').write(c)
print('Updated web_panel.py successfully with doubled braces!')
