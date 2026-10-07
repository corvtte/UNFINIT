import re

def fix_orange_badge():
    with open('services/web_panel.py', 'r', encoding='utf-8') as f:
        text = f.read()

    # Find the badge with "نشست فعال (ONLINE)"
    # It might be bg-orange-600 or something. Let's find "نشست فعال (ONLINE)" and see its surrounding tags.
    pattern = re.compile(r'<span class="([^"]*?orange[^"]*?|[^"]*?amber[^"]*?)"[^>]*>نشست فعال \(ONLINE\)</span>')
    
    def replacer(match):
        old_classes = match.group(1)
        # replace orange/amber with emerald
        new_classes = re.sub(r'orange|amber', 'emerald', old_classes)
        return match.group(0).replace(old_classes, new_classes)

    new_text = pattern.sub(replacer, text)
    
    # Also find "نشست فعال"
    pattern2 = re.compile(r'<span class="([^"]*?orange[^"]*?|[^"]*?amber[^"]*?)"[^>]*>.*?نشست فعال.*?</span>')
    def replacer2(match):
        old_classes = match.group(1)
        new_classes = re.sub(r'orange|amber|text-white/80', 'emerald', old_classes) # text-white/80 is the faded white user mentioned
        new_classes = new_classes.replace("text-white/80", "text-emerald-50")
        return match.group(0).replace(old_classes, new_classes)
        
    new_text = pattern2.sub(replacer2, new_text)

    # User said: "دومن توش اومده با یه سفید کمرنگی که اصلا به این تم سبز ما نمیخوره داره یه چیزی میکنه"
    # This might mean `text-white/80` or `text-slate-100`. Let's just make it `bg-emerald-500 text-white`.
    new_text = re.sub(r'bg-orange-\d+ text-[^\s"]+', 'bg-emerald-500 text-white', new_text)

    with open('services/web_panel.py', 'w', encoding='utf-8') as f:
        f.write(new_text)

fix_orange_badge()
