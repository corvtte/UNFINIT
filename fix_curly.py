import re

def fix_curly():
    with open('services/web_panel.py', 'r', encoding='utf-8') as f:
        text = f.read()

    text = text.replace('function toggleAllUsers(source) {', 'function toggleAllUsers(source) {{')
    text = text.replace('document.querySelectorAll(\'.user-cb\').forEach(cb => {', 'document.querySelectorAll(\'.user-cb\').forEach(cb => {{')
    text = text.replace('if(cb.closest(\'tr\').style.display !== \'none\') {', 'if(cb.closest(\'tr\').style.display !== \'none\') {{')
    text = text.replace('cb.checked = source.checked;', 'cb.checked = source.checked;\n            }}')
    text = text.replace('});', '}});')
    text = text.replace('} // toggleAllUsers', '}} // toggleAllUsers') # wait I didn't add comment
    text = text.replace('async function deleteSelectedUsers() {', 'async function deleteSelectedUsers() {{')
    text = text.replace('for(let uid of selected) {', 'for(let uid of selected) {{')
    text = text.replace('function filterUsersTableOld() {', 'function filterUsersTableOld() {{')
    text = text.replace('function filterUsersTable() {', 'function filterUsersTable() {{')
    text = text.replace('rows.forEach(tr => {', 'rows.forEach(tr => {{')
    
    # Actually just string replace the extra JS block I added
    extra_js_old = '''function toggleAllUsers(source) {
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
    
    function filterUsersTableOld() {'''
    
    extra_js_new = '''function toggleAllUsers(source) {{
        document.querySelectorAll('.user-cb').forEach(cb => {{
            if(cb.closest('tr').style.display !== 'none') {{
                cb.checked = source.checked;
            }}
        }});
    }}
    async function deleteSelectedUsers() {{
        const selected = Array.from(document.querySelectorAll('.user-cb:checked')).map(cb => cb.value);
        if(!selected.length) return alert('کاربری انتخاب نشده است.');
        if(!confirm(`آیا از حذف ${selected.length} کاربر مطمئن هستید؟`)) return;
        
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
    
    function filterUsersTableOld() {{'''
    text = text.replace(extra_js_old, extra_js_new)
    
    filter_js_old = '''function filterUsersTable() {
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
    }'''
    filter_js_new = '''function filterUsersTable() {{
        const val = document.getElementById('usersSearchInput').value.toLowerCase();
        const plat = document.getElementById('userPlatformFilter') ? document.getElementById('userPlatformFilter').value : 'all';
        const rows = document.getElementById('usersTableBody').querySelectorAll('tr.user-row');
        
        rows.forEach(tr => {{
            const text = tr.innerText.toLowerCase();
            const rp = tr.getAttribute('data-platform');
            const matchSearch = text.includes(val);
            const matchPlat = (plat === 'all') || (rp === plat);
            tr.style.display = (matchSearch && matchPlat) ? '' : 'none';
        }});
    }}'''
    text = text.replace(filter_js_old, filter_js_new)

    with open('services/web_panel.py', 'w', encoding='utf-8') as f:
        f.write(text)

fix_curly()
