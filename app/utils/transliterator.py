"""
Wave - Indic to English (Romanized/Tanglish) Transliterator
Converts Telugu (and other Indic script) lyrics into natural English spelling.
"""

import re


def transliterate_indic_to_english(text: str) -> str:
    """
    Transliterate Telugu, Tamil, and Devanagari Unicode script into
    natural, readable English phonetic spelling (Latin/Roman script).
    """
    if not text:
        return ""

    # Check if text contains Indic Unicode characters (0x0900 to 0x0D7F)
    has_indic = any('\u0900' <= ch <= '\u0D7F' for ch in text)
    if not has_indic:
        return text

    # --- TELUGU MAPPINGS ---
    vowels_te = {
        '\u0C05': 'a', '\u0C06': 'aa', '\u0C07': 'i', '\u0C08': 'ee', '\u0C09': 'u',
        '\u0C0A': 'oo', '\u0C0B': 'ru', '\u0C0E': 'e', '\u0C0F': 'e', '\u0C10': 'ai',
        '\u0C12': 'o', '\u0C13': 'o', '\u0C14': 'au'
    }
    matras_te = {
        '\u0C3E': 'aa', '\u0C3F': 'i', '\u0C40': 'ee', '\u0C41': 'u', '\u0C42': 'oo',
        '\u0C43': 'ru', '\u0C46': 'e', '\u0C47': 'e', '\u0C48': 'ai', '\u0C4A': 'o',
        '\u0C4B': 'o', '\u0C4C': 'au'
    }
    consonants_te = {
        '\u0C15': 'k', '\u0C16': 'kh', '\u0C17': 'g', '\u0C18': 'gh', '\u0C19': 'ng',
        '\u0C1A': 'ch', '\u0C1B': 'chh', '\u0C1C': 'j', '\u0C1D': 'jh', '\u0C1E': 'ny',
        '\u0C1F': 't', '\u0C20': 'th', '\u0C21': 'd', '\u0C22': 'dh', '\u0C23': 'n',
        '\u0C24': 'th', '\u0C25': 'th', '\u0C26': 'd', '\u0C27': 'dh', '\u0C28': 'n',
        '\u0C2A': 'p', '\u0C2B': 'ph', '\u0C2C': 'b', '\u0C2D': 'bh', '\u0C2E': 'm',
        '\u0C2F': 'y', '\u0C30': 'r', '\u0C31': 'r', '\u0C32': 'l', '\u0C33': 'l',
        '\u0C35': 'v', '\u0C36': 'sh', '\u0C37': 'sh', '\u0C38': 's', '\u0C39': 'h',
        '\u0C58': 'ts', '\u0C59': 'dz'
    }

    # --- TAMIL MAPPINGS ---
    vowels_ta = {
        '\u0B85': 'a', '\u0B86': 'aa', '\u0B87': 'i', '\u0B88': 'ee', '\u0B89': 'u',
        '\u0B8A': 'oo', '\u0B8E': 'e', '\u0B8F': 'e', '\u0B90': 'ai', '\u0B92': 'o',
        '\u0B93': 'o', '\u0B94': 'au'
    }
    matras_ta = {
        '\u0BBE': 'aa', '\u0BBF': 'i', '\u0BC0': 'ee', '\u0BC1': 'u', '\u0BC2': 'oo',
        '\u0BC6': 'e', '\u0BC7': 'e', '\u0BC8': 'ai', '\u0BCA': 'o', '\u0BCB': 'o',
        '\u0BCC': 'au'
    }
    consonants_ta = {
        '\u0B95': 'k', '\u0B99': 'ng', '\u0B9A': 'ch', '\u0B9E': 'ny', '\u0B9F': 't',
        '\u0BA3': 'n', '\u0BA4': 'th', '\u0BA8': 'n', '\u0BA9': 'n', '\u0BAA': 'p',
        '\u0BAE': 'm', '\u0BAF': 'y', '\u0BB0': 'r', '\u0BB1': 'r', '\u0BB2': 'l',
        '\u0BB3': 'l', '\u0BB4': 'zh', '\u0BB5': 'v', '\u0BB6': 'sh', '\u0BB7': 'sh',
        '\u0BB8': 's', '\u0BB9': 'h'
    }

    # --- DEVANAGARI (HINDI) MAPPINGS ---
    vowels_hi = {
        '\u0905': 'a', '\u0906': 'aa', '\u0907': 'i', '\u0908': 'ee', '\u0909': 'u',
        '\u090A': 'oo', '\u090B': 'ri', '\u090F': 'e', '\u0910': 'ai', '\u0913': 'o',
        '\u0914': 'au'
    }
    matras_hi = {
        '\u093E': 'aa', '\u093F': 'i', '\u0940': 'ee', '\u0941': 'u', '\u0942': 'oo',
        '\u0943': 'ri', '\u0947': 'e', '\u0948': 'ai', '\u094B': 'o', '\u094C': 'au'
    }
    consonants_hi = {
        '\u0915': 'k', '\u0916': 'kh', '\u0917': 'g', '\u0918': 'gh', '\u0919': 'ng',
        '\u091A': 'ch', '\u091B': 'chh', '\u091C': 'j', '\u091D': 'jh', '\u091E': 'ny',
        '\u091F': 't', '\u0920': 'th', '\u0921': 'd', '\u0922': 'dh', '\u0923': 'n',
        '\u0924': 't', '\u0925': 'th', '\u0926': 'd', '\u0927': 'dh', '\u0928': 'n',
        '\u092A': 'p', '\u092B': 'ph', '\u092C': 'b', '\u092D': 'bh', '\u092E': 'm',
        '\u092F': 'y', '\u0930': 'r', '\u0932': 'l', '\u0935': 'v', '\u0936': 'sh',
        '\u0937': 'sh', '\u0938': 's', '\u0939': 'h'
    }

    # --- KANNADA MAPPINGS ---
    vowels_kn = {
        '\u0C85': 'a', '\u0C86': 'aa', '\u0C87': 'i', '\u0C88': 'ee', '\u0C89': 'u',
        '\u0C8A': 'oo', '\u0C8E': 'e', '\u0C8F': 'e', '\u0C90': 'ai', '\u0C92': 'o',
        '\u0C93': 'o', '\u0C94': 'au'
    }
    matras_kn = {
        '\u0CBE': 'aa', '\u0CBF': 'i', '\u0CC0': 'ee', '\u0CC1': 'u', '\u0CC2': 'oo',
        '\u0CC6': 'e', '\u0CC7': 'e', '\u0CC8': 'ai', '\u0CCA': 'o', '\u0CCB': 'o',
        '\u0CCC': 'au'
    }
    consonants_kn = {
        '\u0C95': 'k', '\u0C96': 'kh', '\u0C97': 'g', '\u0C98': 'gh', '\u0C99': 'ng',
        '\u0C9A': 'ch', '\u0C9B': 'chh', '\u0C9C': 'j', '\u0C9D': 'jh', '\u0C9E': 'ny',
        '\u0C9F': 't', '\u0CA0': 'th', '\u0CA1': 'd', '\u0CA2': 'dh', '\u0CA3': 'n',
        '\u0CA4': 'th', '\u0CA5': 'th', '\u0CA6': 'd', '\u0CA7': 'dh', '\u0CA8': 'n',
        '\u0CAA': 'p', '\u0CAB': 'ph', '\u0CAC': 'b', '\u0CAD': 'bh', '\u0CAE': 'm',
        '\u0CAF': 'y', '\u0CB0': 'r', '\u0CB2': 'l', '\u0CB3': 'l', '\u0CB5': 'v',
        '\u0CB6': 'sh', '\u0CB7': 'sh', '\u0CB8': 's', '\u0CB9': 'h'
    }

    all_vowels = {**vowels_te, **vowels_ta, **vowels_hi, **vowels_kn}
    all_matras = {**matras_te, **matras_ta, **matras_hi, **matras_kn}
    all_consonants = {**consonants_te, **consonants_ta, **consonants_hi, **consonants_kn}

    viramas = {'\u0C4D', '\u0BCD', '\u094D', '\u0CCD', '\u0D4D'}
    anusvaras = {'\u0C02', '\u0B82', '\u0902', '\u0C82', '\u0D02'}
    visargas = {'\u0C03', '\u0B83', '\u0903', '\u0C83', '\u0D03'}

    n = len(text)
    res = []
    i = 0
    while i < n:
        ch = text[i]
        if ch in all_vowels:
            res.append(all_vowels[ch])
            i += 1
        elif ch in all_consonants:
            c = all_consonants[ch]
            if i + 1 < n:
                nxt = text[i+1]
                if nxt in viramas:
                    res.append(c)
                    i += 2
                elif nxt in all_matras:
                    res.append(c + all_matras[nxt])
                    i += 2
                else:
                    res.append(c + 'a')
                    i += 1
            else:
                res.append(c + 'a')
                i += 1
        elif ch in anusvaras:
            # Smart nasalization: 'n' before dental/alveolar/palatal/velar, 'm' elsewhere
            following_consonant = ''
            for j in range(i + 1, min(i + 4, n)):
                if text[j] in all_consonants:
                    following_consonant = all_consonants[text[j]]
                    break
                elif text[j] in [' ', '\n', ',', '.', '!', '?', '-', '"', "'"]:
                    break
            
            if following_consonant in ['t', 'th', 'd', 'dh', 'n', 'ch', 'chh', 'j', 'jh', 's', 'sh', 'k', 'g']:
                res.append('n')
            else:
                res.append('m')
            i += 1
        elif ch in visargas:
            res.append('h')
            i += 1
        elif ch in viramas:
            i += 1
        else:
            res.append(ch)
            i += 1

    out = ''.join(res)
    # Polish formatting
    out = re.sub(r'chch', 'ch', out)
    out = re.sub(r'thth', 'tth', out)
    
    # Capitalize first character of each line
    lines = out.split('\n')
    formatted = []
    for l in lines:
        stripped = l.strip()
        if stripped:
            first_letter_idx = None
            for idx, c in enumerate(stripped):
                if c.isalpha():
                    first_letter_idx = idx
                    break
            if first_letter_idx is not None:
                stripped = (
                    stripped[:first_letter_idx]
                    + stripped[first_letter_idx].upper()
                    + stripped[first_letter_idx+1:]
                )
        formatted.append(stripped)

    return '\n'.join(formatted)
