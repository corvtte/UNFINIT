import re

def fix_metadata():
    with open('core/sign_service.py', 'r', encoding='utf-8') as f:
        text = f.read()

    mutagen_block_old = '''from mutagen.easyid3 import EasyID3
                            from mutagen.mp3 import MP3
                            audio = MP3(str(dest_file), ID3=EasyID3)
                            if reader_tag:
                                audio["artist"] = str(reader_tag)
                                audio["albumartist"] = str(reader_tag)
                            if sign_data.get("title"):
                                audio["title"] = str(sign_data["title"])
                            audio.save()'''
                            
    mutagen_block_new = '''from mutagen.easyid3 import EasyID3
                            from mutagen.mp3 import MP3
                            from mutagen.id3 import ID3
                            
                            # 1. Wipe all existing ID3 tags completely (v1 and v2)
                            try:
                                tags = ID3(str(dest_file))
                                tags.delete()
                            except Exception:
                                pass
                                
                            # 2. Apply clean tags
                            audio = MP3(str(dest_file), ID3=EasyID3)
                            try:
                                audio.add_tags()
                            except Exception:
                                pass # Tags might already exist if delete failed, just overwrite
                                
                            if reader_tag:
                                audio["artist"] = str(reader_tag)
                                audio["performer"] = str(reader_tag)
                                audio["albumartist"] = str(reader_tag)
                            if sign_data.get("title"):
                                audio["title"] = str(sign_data["title"])
                            audio.save(v2_version=3)'''
                            
    if mutagen_block_old in text:
        text = text.replace(mutagen_block_old, mutagen_block_new)
        with open('core/sign_service.py', 'w', encoding='utf-8') as f:
            f.write(text)
        print("Replaced metadata block.")
    else:
        # Regex fallback
        match = re.search(r'from mutagen\.easyid3 import EasyID3.*?audio\.save\(\)', text, re.DOTALL)
        if match:
            text = text.replace(match.group(0), mutagen_block_new)
            with open('core/sign_service.py', 'w', encoding='utf-8') as f:
                f.write(text)
            print("Replaced metadata block via regex.")
        else:
            print("Could not find mutagen block!")

fix_metadata()
