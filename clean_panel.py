import re

def clean_web_panel():
    with open('services/web_panel.py', 'r', encoding='utf-8') as f:
        text = f.read()

    # 1. Remove font-mono
    text = text.replace('font-mono ', '').replace(' font-mono', '').replace('font-mono', '')

    # 2. Fix orange badge "نشست فعال"
    pattern = re.compile(r'<span class="([^"]*?orange[^"]*?|[^"]*?amber[^"]*?)"[^>]*>نشست فعال \(ONLINE\)</span>')
    def replacer(m): return m.group(0).replace(m.group(1), re.sub(r'orange|amber', 'emerald', m.group(1)))
    text = pattern.sub(replacer, text)
    
    pattern2 = re.compile(r'<span class="([^"]*?orange[^"]*?|[^"]*?amber[^"]*?)"[^>]*>.*?نشست فعال.*?</span>')
    def replacer2(m): return m.group(0).replace(m.group(1), re.sub(r'orange|amber|text-white/80', 'emerald', m.group(1)).replace('text-white/80', 'text-emerald-50'))
    text = pattern2.sub(replacer2, text)
    text = re.sub(r'bg-orange-\d+ text-[^\s"]+', 'bg-emerald-500 text-white', text)

    # 3. Emojis
    tg_svg = '<svg class="w-4 h-4 text-cyan-400 inline" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.75"><path stroke-linecap="round" stroke-linejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" /></svg>'
    bale_svg = '<svg class="w-4 h-4 text-emerald-400 inline" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.75"><path stroke-linecap="round" stroke-linejoin="round" d="M12 2.25c-5.385 0-9.75 4.365-9.75 9.75s4.365 9.75 9.75 9.75 9.75-4.365 9.75-9.75S17.385 2.25 12 2.25z" /></svg>'
    text = text.replace('✈️', tg_svg).replace('🟢', bale_svg).replace('🟣', '') # remove rubika emoji

    # 4. Users Tab Checkboxes & "Delete Selected"
    btn_purge_test_old = '<button type="button" onclick="purgeTestUsers()" class="px-3 py-1.5 rounded-xl bg-rose-950/60 hover:bg-rose-900 text-rose-300 border border-rose-800 text-xs transition flex items-center gap-1.5" title="پاک‌سازی کاربران تست">'
    # Wait, the exact string might be different. Let's find purgeTestUsers() in text
    
    # We will just replace `purgeTestUsers()` with `deleteSelectedUsers()`, and `پاک‌سازی تست` with `حذف انتخاب‌شده`
    text = text.replace('onclick="purgeTestUsers()"', 'onclick="deleteSelectedUsers()"')
    text = text.replace('پاک‌سازی تست', 'حذف انتخاب‌شده')
    
    # Next to this button, we insert the platform filter
    search_input = '<input type="text" id="usersSearchInput" oninput="filterUsersTable()"'
    filter_select = '<select id="userPlatformFilter" onchange="filterUsersTable()" class=" border border-slate-700 rounded-xl px-2 py-1.5 text-xs text-slate-100 focus:outline-none focus:border-cyan-500" style="background: var(--input-bg); border-color: var(--card-border);"><option value="all">همه پلتفرم‌ها</option><option value="telegram">تلگرام</option><option value="bale">بله</option></select>\n                            '
    text = text.replace(search_input, filter_select + search_input)

    # 5. Add checkbox header
    text = text.replace('<th class="p-3 text-right">پلتفرم</th>', '<th class="p-3 text-right w-8"><input type="checkbox" id="selectAllUsers" onclick="toggleAllUsers(this)" class="rounded text-cyan-600 border-slate-700 bg-slate-800 cursor-pointer form-checkbox accent-cyan-500 w-4 h-4" style="background:var(--input-bg);"></th><th class="p-3 text-right">پلتفرم</th>')
    
    # 6. Add join date header
    text = text.replace('<th class="p-3 text-right w-16 text-center">عملیات</th>', '<th class="p-3 text-right text-xs">تاریخ عضویت</th><th class="p-3 text-right w-16 text-center">عملیات</th>')
    
    # 7. Hide Rubika in JS
    text = text.replace('window.USERS_CACHE = data.users || [];', "window.USERS_CACHE = (data.users || []).filter(u => u.platform !== 'rubika');")

    # 8. Add checkboxes to JS rows, data-platform, and joinDate
    text = text.replace("return '<tr class=\"hover:bg-white/[0.03] transition\">' +", "return '<tr class=\"hover:bg-white/[0.03] transition user-row\" data-platform=\"' + escapeHtml(u.platform||'') + '\">' + '<td class=\"p-3\"><input type=\"checkbox\" class=\"user-cb rounded text-cyan-600 border-slate-700 bg-slate-800 cursor-pointer form-checkbox accent-cyan-500 w-4 h-4\" value=\"' + userIdClean + '\" style=\"background:var(--input-bg);\"></td>' +")
    
    text = text.replace("const name = escapeHtml(u.username", "const joinDate = u.created_at ? new Date(u.created_at * 1000).toLocaleDateString('fa-IR') : 'نامشخص';\n                            const name = escapeHtml(u.username")
    
    actions_td = "'<td class=\"p-3 text-center\">' +"
    text = text.replace(actions_td, "'<td class=\"p-3 text-xs text-slate-400\">' + joinDate + '</td>' + " + actions_td)

    # 9. Consolidate VIP buttons
    vipBtn_new = "const vipBtn = isUserVip ? '<button type=\"button\" data-user-action=\"revoke_vip\" data-user-id=\"' + userIdClean + '\" class=\"px-2 py-1 rounded-lg border border-amber-500/40 text-amber-400 hover:bg-amber-500/20 font-sans text-xs font-bold transition\">لغو پریمیوم</button>' : '<button type=\"button\" data-user-action=\"grant_vip\" data-user-id=\"' + userIdClean + '\" class=\"px-2 py-1 rounded-lg border border-cyan-500/40 text-cyan-400 hover:bg-cyan-500/20 font-sans text-xs font-bold transition\">پریمیوم</button>';\n// "
    text = re.sub(r'const vipBtn = isUserVip.*?\'</div>\';', vipBtn_new, text, flags=re.DOTALL)

    # 10. Add extra JS functions at the end of the script block
    extra_js = """
    function toggleAllUsers(source) {{
        document.querySelectorAll('.user-cb').forEach(cb => {{
            if(cb.closest('tr').style.display !== 'none') {{
                cb.checked = source.checked;
            }}
        }});
    }}
    async function deleteSelectedUsers() {{
        const selected = Array.from(document.querySelectorAll('.user-cb:checked')).map(cb => cb.value);
        if(!selected.length) return alert('کاربری انتخاب نشده است.');
        if(!confirm(`آیا از حذف ${{selected.length}} کاربر مطمئن هستید؟`)) return;
        
        for(let uid of selected) {{
            await fetch('/api/users/delete', {{
                method: 'POST',
                headers: {{'Content-Type':'application/json'}},
                body: JSON.stringify({{user_id: uid}})
            }});
        }}
        alert('کاربران انتخاب‌شده حذف شدند.');
        loadUsersData();
    }}
    
    function filterUsersTable() {{
        const val = document.getElementById('usersSearchInput').value.toLowerCase();
        const platElem = document.getElementById('userPlatformFilter');
        const plat = platElem ? platElem.value : 'all';
        const rows = document.getElementById('usersTableBody').querySelectorAll('tr.user-row');
        
        rows.forEach(tr => {{
            const text = tr.innerText.toLowerCase();
            const rp = tr.getAttribute('data-platform');
            const matchSearch = text.includes(val);
            const matchPlat = (plat === 'all') || (rp === plat);
            tr.style.display = (matchSearch && matchPlat) ? '' : 'none';
        }});
    }}
    """
    
    # We will inject this right before the FINAL </script> in render_dashboard_html
    # To be safe, we replace `function filterUsersTable() { ... }` with our escaped one
    filter_js_old = re.search(r'function filterUsersTable\(\) \{.*?\}\s*\}', text, re.DOTALL)
    if filter_js_old:
        text = text.replace(filter_js_old.group(0), extra_js)
    else:
        print("COULD NOT FIND filterUsersTable JS!")

    with open('services/web_panel.py', 'w', encoding='utf-8') as f:
        f.write(text)

clean_web_panel()
