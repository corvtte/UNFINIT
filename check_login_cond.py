lines = open('services/feed_crawler.py', encoding='utf-8').read()
if 'if "login" not in loc.lower():' in lines:
    print('login condition is already correct')
else:
    print('login condition is WRONG')
