import re

def bump(filepath, old, new):
    try:
        text = open(filepath, encoding='utf-8').read()
        text = re.sub(old, new, text)
        open(filepath, 'w', encoding='utf-8').write(text)
        print(f'Bumped {filepath}')
    except Exception as e:
        print(e)

bump('AGENTS.md', r'v0\.7\.31', 'v0.7.32')
bump('core/config.py', r'ENGINE_VERSION\s*=\s*"[^"]+"', 'ENGINE_VERSION = "v0.7.32"')
