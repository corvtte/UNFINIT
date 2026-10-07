import re

def fix_ui_noise():
    with open('services/feed_scraper.py', 'r', encoding='utf-8') as f:
        scraper = f.read()

    pattern = re.compile(r'(ui_noise = \[\n.*?)(                \])', re.DOTALL)
    
    def replacer(match):
        old_list = match.group(1)
        new_items = '                    "تغییر عکس", "پروفایل", "اتاق شخصی", "محصولات", "دوره", "خبرنامه", "اخبار", "تازه ترین", "پاسخ دادن", "گزارش دادن", "مورد نیاز"\n'
        return old_list + new_items + match.group(2)

    scraper = pattern.sub(replacer, scraper)
    
    with open('services/feed_scraper.py', 'w', encoding='utf-8') as f:
        f.write(scraper)

fix_ui_noise()
