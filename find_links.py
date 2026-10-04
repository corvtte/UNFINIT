import re
with open(r'C:\Users\Sajjad\.gemini\antigravity\brain\5dfbbf1c-c00e-435e-bac1-5efba380215f\.system_generated\steps\3692\content.md', encoding='utf-8') as f:
    text = f.read()
    links = re.findall(r'(https?://[^\s\"\'\)]+(?:mp3|mp4|zip|download|dl)[^\s\"\'\)]*)', text)
    for l in set(links): print(l)
