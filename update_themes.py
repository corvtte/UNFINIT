import json

def update_themes():
    with open('data/themes.json', 'r', encoding='utf-8') as f:
        themes = json.load(f)

    allowed = ['pure-dark', 'default-dark', 'one-dark-pro', 'tokyo-night', 'catppuccin']
    new_themes = {}
    for k in allowed:
        if k in themes:
            new_themes[k] = themes[k]

    # Update labels based on the prompt
    if 'pure-dark' in new_themes:
        new_themes['pure-dark']['label'] = 'Pure AMOLED Dark (Primary)'
    if 'default-dark' in new_themes:
        new_themes['default-dark']['label'] = 'UNFINIT Classic (Default)'
    if 'one-dark-pro' in new_themes:
        new_themes['one-dark-pro']['label'] = 'One Dark Pro'
    if 'tokyo-night' in new_themes:
        new_themes['tokyo-night']['label'] = 'Tokyo Night'
    if 'catppuccin' in new_themes:
        new_themes['catppuccin']['label'] = 'Cappuccino Mocha'

    with open('data/themes.json', 'w', encoding='utf-8') as f:
        json.dumps(new_themes, ensure_ascii=False) # Wait this is just a return value
        f.write(json.dumps(new_themes, indent=4, ensure_ascii=False))

update_themes()
