def t():
    with open('services/web_panel.py', 'r', encoding='utf-8') as f:
        text = f.read().split('\n')
        for i, l in enumerate(text):
            if 'const res = await fetch(\'/api/users\'' in l or 'function loadUsers' in l:
                print(f'{i}: {l}')
t()
