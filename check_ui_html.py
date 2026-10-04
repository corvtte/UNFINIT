import sys; sys.stdout.reconfigure(encoding='utf-8')
lines = open('services/web_panel.py', encoding='utf-8').read()
idx = lines.find('onclick="loginAndTestConnection(this)"')
print(lines[max(0, idx-200):idx+800])
