c = open('core/config.py', encoding='utf-8').read()
c = c.replace('"v0.7.33"', '"v0.7.34"')
open('core/config.py', 'w', encoding='utf-8').write(c)

c2 = open('AGENTS.md', encoding='utf-8').read()
c2 = c2.replace('v0.7.33', 'v0.7.34')
open('AGENTS.md', 'w', encoding='utf-8').write(c2)

print("Bumped version")
