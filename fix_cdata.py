import re

with open('platforms/telegram_adapter.py', 'r', encoding='utf-8') as f:
    text = f.read()

find_str = 'ok, final_audio = MediaService.convert_audio_format(c_data["working_path"], target_fmt)'
replace_str = 'ok, final_audio = MediaService.convert_audio_format(drop["working_path"], target_fmt)'

if find_str in text:
    text = text.replace(find_str, replace_str)
    
    # Also fix c_data in the rest of the block
    find_block = '''title = c_data.get("api_meta", {}).get("title") or "Unknown"
                        artist = c_data.get("api_meta", {}).get("artist") or "Unknown"
                        duration = c_data.get("api_meta", {}).get("duration_sec") or 0
                        thumb_p = c_data.get("thumb_path")'''
    replace_block = '''title = drop.get("api_meta", {}).get("title") or "Unknown"
                        artist = drop.get("api_meta", {}).get("artist") or "Unknown"
                        duration = drop.get("api_meta", {}).get("duration_sec") or 0
                        thumb_p = drop.get("thumb_path")'''
    
    text = text.replace(find_block, replace_block)
    
    with open('platforms/telegram_adapter.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print("Replaced c_data with drop in telegram_adapter.py!")
else:
    print("find_str not found!")
