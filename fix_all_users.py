import re

def fix_all_user_stuff():
    with open('services/web_panel.py', 'r', encoding='utf-8') as f:
        text = f.read()

    # Add select all checkbox in table header
    # and "Delete Selected" button
    
    # 1. Update the buttons next to Search input
    btn_purge_test_old = '''<button type="button" onclick="purgeTestUsers()" class="px-3 py-1.5 rounded-xl bg-rose-950/60 hover:bg-rose-900 text-rose-300 border border-rose-800 text-xs transition flex items-center gap-1.5" title="پاک‌سازی کاربران تست">
                                <svg class="w-3.5 h-3.5 stroke-[1.75]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path stroke-linecap="round" stroke-linejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                                </svg>
                                پاک‌سازی تست
                            </button>'''
                            
    btn_delete_selected = '''<select id="userPlatformFilter" onchange="filterUsersTable()" class="border border-slate-700 rounded-xl px-2 py-1.5 text-xs text-slate-100 focus:outline-none focus:border-cyan-500" style="background: var(--input-bg); border-color: var(--card-border);">
                                <option value="all">همه پلتفرم‌ها</option>
                                <option value="telegram">تلگرام</option>
                                <option value="bale">بله</option>
                            </select>
                            <button type="button" onclick="deleteSelectedUsers()" class="px-3 py-1.5 rounded-xl bg-rose-950/60 hover:bg-rose-900 text-rose-300 border border-rose-800 text-xs transition flex items-center gap-1.5" title="حذف کاربران انتخاب‌شده">
                                <svg class="w-3.5 h-3.5 stroke-[1.75]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0"/></svg>
                                حذف انتخاب‌شده
                            </button>'''
                            
    text = text.replace(btn_purge_test_old, btn_delete_selected)
    
    # 2. Add checkbox header
    th_old = '<th class="p-3 text-right">پلتفرم</th>'
    th_new = '<th class="p-3 text-right w-8"><input type="checkbox" id="selectAllUsers" onclick="toggleAllUsers(this)" class="rounded text-cyan-600 border-slate-700 bg-slate-800 cursor-pointer"></th><th class="p-3 text-right">پلتفرم</th>'
    text = text.replace(th_old, th_new)

    # 3. Add join date header
    # '<th class="p-3 text-right w-16 text-center">عملیات</th>'
    # we add '<th class="p-3 text-right text-xs">تاریخ عضویت</th>' before 'عملیات'
    text = text.replace('<th class="p-3 text-right w-16 text-center">عملیات</th>', '<th class="p-3 text-right text-xs">تاریخ عضویت</th><th class="p-3 text-right w-16 text-center">عملیات</th>')
    
    # 4. JS: remove rubika entirely from display
    js_rubika_old = "if (u.platform === 'rubika') {"
    text = re.sub(r'if \(u\.platform === \'rubika\'\) \{.*?(?=else if|else \{|return \')', '', text, flags=re.DOTALL)
    
    # Wait, the best way to remove rubika is to filter it in `loadUsersData()` at the start:
    # `window.USERS_CACHE = data.users || [];`
    # -> `window.USERS_CACHE = (data.users || []).filter(u => u.platform !== 'rubika');`
    text = text.replace('window.USERS_CACHE = data.users || [];', "window.USERS_CACHE = (data.users || []).filter(u => u.platform !== 'rubika');")
    
    # 5. Add checkbox to row and Date
    # `return '<tr class="hover:bg-white/[0.03] transition">' +`
    # `<td class="p-3">' + platformBadge + '</td>' +`
    row_start_old = "return '<tr class=\"hover:bg-white/[0.03] transition\" data-platform=\"' + escapeHtml(u.platform||'') + '\">' +"
    
    # wait, data-platform isn't there. I'll add it.
    text = text.replace("return '<tr class=\"hover:bg-white/[0.03] transition\">' +", "return '<tr class=\"hover:bg-white/[0.03] transition user-row\" data-platform=\"' + escapeHtml(u.platform||'') + '\">' + '<td class=\"p-3\"><input type=\"checkbox\" class=\"user-cb rounded text-cyan-600 border-slate-700 bg-slate-800 cursor-pointer\" value=\"' + userIdClean + '\"></td>' +")
    
    # 6. Insert date td:
    # `<td class="p-3 text-center">` is the actions td.
    actions_td = "'<td class=\"p-3 text-center\">' +"
    # get join date (u.joined_at might not exist, but let's see. we can put a placeholder or format it)
    date_code = "const joinDate = u.joined_at ? new Date(u.joined_at * 1000).toLocaleDateString('fa-IR') : 'نامشخص';"
    
    # I'll replace `const name = escapeHtml` to insert date_code
    text = text.replace("const name = escapeHtml", date_code + "\n                            const name = escapeHtml")
    text = text.replace(actions_td, "'<td class=\"p-3 text-xs text-slate-400\">' + joinDate + '</td>' + " + actions_td)
    
    # 7. JS for select all, delete selected, filter
    # Add script block at end or before `</script>`
    extra_js = '''
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
        const plat = document.getElementById('userPlatformFilter') ? document.getElementById('userPlatformFilter').value : 'all';
        const rows = document.getElementById('usersTableBody').querySelectorAll('tr.user-row');
        
        rows.forEach(tr => {
            const text = tr.innerText.toLowerCase();
            const rp = tr.getAttribute('data-platform');
            const matchSearch = text.includes(val);
            const matchPlat = (plat === 'all') || (rp === plat);
            tr.style.display = (matchSearch && matchPlat) ? '' : 'none';
        });
    }
    '''
    text = text.replace('function filterUsersTable() {', 'function filterUsersTableOld() {')
    text = text.replace('</script>', extra_js + '\n</script>')
    
    # 8. Premium Button consolidation
    # instead of +10, +30 buttons, just show "پریمیوم" which acts like +30 or opens a prompt
    vipBtn_old = "const vipBtn = isUserVip"
    vipBtn_new = "const vipBtn = isUserVip ? '<button type=\"button\" data-user-action=\"revoke_vip\" data-user-id=\"' + userIdClean + '\" class=\"px-2 py-1 rounded-lg border border-amber-500/40 text-amber-400 hover:bg-amber-500/20 font-sans text-xs font-bold transition\">لغو پریمیوم</button>' : '<button type=\"button\" data-user-action=\"grant_vip\" data-user-id=\"' + userIdClean + '\" class=\"px-2 py-1 rounded-lg border border-cyan-500/40 text-cyan-400 hover:bg-cyan-500/20 font-sans text-xs font-bold transition\">ارتقا به پریمیوم</button>';\n// "
    text = re.sub(r'const vipBtn = isUserVip.*?\'</div>\';', vipBtn_new, text, flags=re.DOTALL)
    
    with open('services/web_panel.py', 'w', encoding='utf-8') as f:
        f.write(text)

fix_all_user_stuff()
