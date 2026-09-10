"""
Fix remaining legacy v25.5.x version assertions in test files.
"""
import glob, re

files = (
    glob.glob('tests/test_v25_5_*.py') +
    glob.glob('tests/test_v25_upgrade.py') +
    glob.glob('tests/test_v25_8_features.py')
)

old_versions = [
    'v25.5.0','v25.5.1','v25.5.2','v25.5.3','v25.5.4',
    'v25.5.5','v25.5.6','v25.5.7','v25.5.8','v25.5.9',
]

for fpath in files:
    try:
        with open(fpath, 'r', encoding='utf-8') as f:
            content = f.read()
        orig = content
        for v in old_versions:
            # assertEqual(config.ENGINE_VERSION, "v25.x.x")
            content = content.replace(
                'self.assertEqual(config.ENGINE_VERSION, "' + v + '")',
                'self.assertIn(config.ENGINE_VERSION, ("v0.1.0",))'
            )
            # assertIn("v25.x.x", ...)
            content = content.replace('assertIn("' + v + '"', 'assertIn("v0.1.0"')
            # assertIn('v25.x.x', ...)
            content = content.replace("assertIn('" + v + "'", "assertIn('v0.1.0'")
        if content != orig:
            with open(fpath, 'w', encoding='utf-8') as f:
                f.write(content)
            print('Updated:', fpath)
        else:
            print('No change:', fpath)
    except Exception as e:
        print('Error:', fpath, e)

print('Done')
