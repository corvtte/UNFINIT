def fix():
    with open('services/web_panel.py', 'r', encoding='utf-8') as f:
        lines = f.read().split('\n')
        for i, l in enumerate(lines):
            if '/api/users' in l and 'fetch(' not in l:
                print(f'{i}: {l.strip()}')

fix()
