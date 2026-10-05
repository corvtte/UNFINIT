import re

def update_version(file_path, old_ver, new_ver):
    with open(file_path, 'r', encoding='utf-8') as f:
        text = f.read()
    text = text.replace(old_ver, new_ver)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(text)

update_version('AGENTS.md', 'v0.7.41', 'v0.7.42')
update_version('core/config.py', 'v0.7.41', 'v0.7.42')
