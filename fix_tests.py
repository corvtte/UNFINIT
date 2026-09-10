"""
Update all legacy v25.x version assertions in test files to use v0.1.0.
"""
import os, re, glob

test_files = glob.glob('tests/test_v25_*.py')
old_versions = [
    'v25.5.3','v25.5.7','v25.6.3','v25.6.4','v25.6.5','v25.6.6',
    'v25.7.0','v25.7.1','v25.7.2','v25.7.3','v25.7.4','v25.7.5',
]

for fpath in test_files:
    with open(fpath, 'r', encoding='utf-8') as f:
        content = f.read()
    orig = content

    # Fix assertEqual(config.ENGINE_VERSION, "v25.x.x") patterns
    for v in old_versions:
        content = content.replace(
            f'self.assertEqual(config.ENGINE_VERSION, "{v}")',
            'self.assertIn(config.ENGINE_VERSION, ("v0.1.0",))'
        )
        content = content.replace(
            "self.assertEqual(config.ENGINE_VERSION, '" + v + "')",
            "self.assertIn(config.ENGINE_VERSION, ('v0.1.0',))"
        )

    # Fix assertIn("v25.x.x", ...) and assertIn('v25.x.x', ...) patterns
    for v in old_versions:
        content = content.replace('assertIn("' + v + '"', 'assertIn("v0.1.0"')
        content = content.replace("assertIn('" + v + "'", "assertIn('v0.1.0'")

    # Fix assertIn(config.ENGINE_VERSION, ("v25.x.x", ...)) -> assertIn(config.ENGINE_VERSION, ("v0.1.0",))
    content = re.sub(
        r'self\.assertIn\(config\.ENGINE_VERSION,\s*\([^)]*"v25\.[^"]*"[^)]*\)\)',
        'self.assertIn(config.ENGINE_VERSION, ("v0.1.0",))',
        content
    )

    # Fix assertTrue(any(v in X for v in ("v25...", ...))) patterns
    content = re.sub(
        r'self\.assertTrue\(any\(v in ([^\n]+?) for v in \((?:[^)]*?"v25\.[^"]*?"[^)]*?)+\)\)\)',
        lambda m: 'self.assertIn("v0.1.0", ' + m.group(1).strip() + ')',
        content
    )
    # Also handle list form [...]
    content = re.sub(
        r'self\.assertTrue\(any\(v in ([^\n]+?) for v in \[(?:[^\]]*?"v25\.[^"]*?"[^\]]*?)+\]\)\)',
        lambda m: 'self.assertIn("v0.1.0", ' + m.group(1).strip() + ')',
        content
    )
    # Handle f-string form: any(f"UNFINIT Store Engine {v}" in X for v in ...)
    content = re.sub(
        r'self\.assertTrue\(any\(f"[^"]*\{v\}[^"]*" in ([^\s,\)]+) for v in \((?:[^)]*?"v25\.[^"]*?"[^)]*?)+\)\)\)',
        lambda m: 'self.assertIn("v0.1.0", ' + m.group(1).strip() + ')',
        content
    )

    if content != orig:
        with open(fpath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'Updated: {fpath}')
    else:
        print(f'No change: {fpath}')

print('Done.')
