import re
with open('platforms/bale_adapter.py', 'r', encoding='utf-8') as f:
    text = f.read()

match = re.search(r'elif action == "audio_specs":', text)
if match:
    print("Found audio_specs at", match.start())
else:
    print("Not found audio_specs")
