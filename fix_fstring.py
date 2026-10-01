p = 'services/feed_crawler.py'
t = open(p, encoding='utf-8').read()

t = t.replace('msg = f"اتصال و نشست با موفقیت تأیید شد.\nآدرس نهایی: {redirect_url}\nوضعیت: {status}"',
              'msg = f"اتصال و نشست با موفقیت تأیید شد.\\nآدرس نهایی: {redirect_url}\\nوضعیت: {status}"')

t = t.replace('msg = f"پاسخ خام (کد {status}):\n{body_preview}..."',
              'msg = f"پاسخ خام (کد {status}):\\n{body_preview}..."')

open(p, 'w', encoding='utf-8').write(t)
