import sys
c = open('services/web_panel.py', encoding='utf-8').read()

old_call = "onclick=\"transferFeedDownload(\\'' + safeUrl + '\\', \\'' + safeTitle + '\\', \\'' + safeAudio + '\\', \\'' + safeVideo + '\\', \\'' + safeSource + '\\')\""
new_call = "onclick=\"transferFeedDownload(\\'' + safeUrl + '\\', \\'' + safeTitle + '\\', \\'' + safeAudio + '\\', \\'' + safeVideo + '\\', \\'' + safeSource + '\\', this)\""

c = c.replace(old_call, new_call)
open('services/web_panel.py', 'w', encoding='utf-8').write(c)
print('Updated transferFeedDownload call')
