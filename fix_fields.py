import re
p = 'services/web_panel.py'
text = open(p, encoding='utf-8').read()

# Add FEED_AUTH_COOKIE to fields
text = text.replace("'CASHBACK_PERCENT', 'FEED_AUTH_EMAIL', 'FEED_AUTH_PASSWORD'", "'CASHBACK_PERCENT', 'FEED_AUTH_EMAIL', 'FEED_AUTH_PASSWORD', 'FEED_AUTH_COOKIE'")

# Add FEED_AUTH_COOKIE to sensitiveKeys
text = text.replace("'GEMINI_API_KEY', 'HF_TOKEN', 'CARD_NUMBER', 'FEED_AUTH_PASSWORD'", "'GEMINI_API_KEY', 'HF_TOKEN', 'CARD_NUMBER', 'FEED_AUTH_PASSWORD', 'FEED_AUTH_COOKIE'")

open(p, 'w', encoding='utf-8').write(text)
