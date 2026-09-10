import re
import unicodedata

# Arabic to Persian character mapping
CHAR_MAP = {
    'ي': 'ی',
    'ى': 'ی',
    'ك': 'ک',
    'ة': 'ه',
    'ؤ': 'و',
    'إ': 'ا',
    'أ': 'ا',
    'آ': 'ا',
    'ء': '',
    'ئ': 'ی',
    '‌': ' ',  # Zero-width non-joiner (ZWNJ ‌) to space for word boundary consistency
    'ـ': '',   # Tatweel / Kashida
}

# Arabic diacritics regex (harakat, tanwin, tashdid)
DIACRITICS_REGEX = re.compile(r'[ً-ؘٰٟ-ؚ]')

def normalize_persian_text(text: str) -> str:
    """
    Normalizes Persian and Arabic text for robust keyword matching:
    1. Unifies Yeh (ي/ى -> ی) and Kaf (ك -> ک)
    2. Removes Arabic diacritics (harakat/tanwin)
    3. Normalizes ZWNJ and trims duplicate whitespace
    4. Converts English characters to lowercase
    Returns a clean normalized string for matching while raw text is preserved elsewhere.
    """
    if not text:
        return ""

    s = str(text)
    
    # 1. Map characters
    for k, v in CHAR_MAP.items():
        s = s.replace(k, v)

    # 2. Strip diacritics
    s = DIACRITICS_REGEX.sub('', s)

    # 3. Unicode normalization
    s = unicodedata.normalize('NFKD', s)

    # 4. Normalize whitespace and lowercase
    s = re.sub(r'\s+', ' ', s)
    return s.strip().lower()
