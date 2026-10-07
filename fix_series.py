import re

def fix_sign_logic():
    # 1. core/sign_service.py
    with open('core/sign_service.py', 'r', encoding='utf-8') as f:
        core = f.read()
    
    old_code = '''        audio_url = (sign_data.get("audio_url") or "").strip()
        video_url = (sign_data.get("video_url") or "").strip()
        page_url = sign_data.get("page_url") or "https://abasmanesh.com/fa/articles/"
        is_video_only = bool(video_url and not audio_url)'''

    new_code = '''        audio_url = (sign_data.get("audio_url") or "").strip()
        video_url = (sign_data.get("video_url") or "").strip()
        page_url = sign_data.get("page_url") or "https://abasmanesh.com/fa/articles/"
        
        # O_O O UO O_O O U+O'O U+U U.OO"U^O U_ O"U O3OUOO OU, O O3O (U.O'U+U+O_ O_U+O_OrUO O_O O"UO_O  UOO  O3U?O O"U O_U^O OU.OUOUcO )O U?O U,O U^UOO_UOU^ O_O OO_ U^ OU^O O_UOO_U_O O_O_O_
        title_tag = sign_data.get("title", "")
        if "O_U+O_OrUO O_O O"UO_O " in title_tag or "O3U?O O"U O_U^O OU.OUOUcO " in title_tag or "O3OUOO OU," in title_tag:
            audio_url = ""
            
        is_video_only = bool(video_url and not audio_url)'''
    # I'll just use exact string replacement
    # wait, my Persian might get mangled. Let's use English comments.
    new_code = '''        audio_url = (sign_data.get("audio_url") or "").strip()
        video_url = (sign_data.get("video_url") or "").strip()
        page_url = sign_data.get("page_url") or "https://abasmanesh.com/fa/articles/"
        
        title_tag = sign_data.get("title", "")
        if "زندگی در بهشت" in title_tag or "سفر به دور آمریکا" in title_tag or "سریال" in title_tag:
            audio_url = ""
            
        is_video_only = bool(video_url and not audio_url)'''
        
    core = core.replace(old_code, new_code)
    with open('core/sign_service.py', 'w', encoding='utf-8') as f:
        f.write(core)


    # 2. telegram_adapter.py (customer_sign_handler)
    with open('platforms/telegram_adapter.py', 'r', encoding='utf-8') as f:
        tg = f.read()

    old_tg = '''            audio_url = (sign.get("audio_url") or "").strip()
            video_url = (sign.get("video_url") or "").strip()
            page_url = sign.get("page_url") or "https://abasmanesh.com/fa/articles/"'''

    new_tg = '''            audio_url = (sign.get("audio_url") or "").strip()
            video_url = (sign.get("video_url") or "").strip()
            page_url = sign.get("page_url") or "https://abasmanesh.com/fa/articles/"
            
            title_tag = sign.get("title", "")
            if "زندگی در بهشت" in title_tag or "سفر به دور آمریکا" in title_tag or "سریال" in title_tag:
                audio_url = ""'''

    tg = tg.replace(old_tg, new_tg)
    with open('platforms/telegram_adapter.py', 'w', encoding='utf-8') as f:
        f.write(tg)


    # 3. bale_adapter.py (customer_sign_handler)
    with open('platforms/bale_adapter.py', 'r', encoding='utf-8') as f:
        bale = f.read()

    old_bale = '''                                        audio_url = (sign.get("audio_url") or "").strip()
                                        video_url = (sign.get("video_url") or "").strip()
                                        page_url = sign.get("page_url") or "https://abasmanesh.com/fa/articles/"'''

    new_bale = '''                                        audio_url = (sign.get("audio_url") or "").strip()
                                        video_url = (sign.get("video_url") or "").strip()
                                        page_url = sign.get("page_url") or "https://abasmanesh.com/fa/articles/"
                                        
                                        title_tag = sign.get("title", "")
                                        if "زندگی در بهشت" in title_tag or "سفر به دور آمریکا" in title_tag or "سریال" in title_tag:
                                            audio_url = ""'''

    bale = bale.replace(old_bale, new_bale)
    with open('platforms/bale_adapter.py', 'w', encoding='utf-8') as f:
        f.write(bale)


fix_sign_logic()
