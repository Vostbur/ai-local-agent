from pathlib import Path

path = Path('data/notes/список_покупок.md')
text = path.read_text(encoding='utf-8')
lines = text.splitlines()
title = lines[0][1:].strip()
body = '\n'.join(lines[1:])

query = 'покупки'
search_text_lower = (title + ' ' + path.name + ' ' + body).lower()
word = query.lower()
sublen = max(3, len(word) - 1)
word_sub = word[:sublen]

with open('debug_bytes.txt', 'w', encoding='utf-8') as f:
    f.write(f'title: {title}\n')
    f.write(f'title len: {len(title)}\n')
    f.write(f'title bytes: {title.encode("utf-8")}\n')
    f.write(f'body: {body}\n')
    f.write(f'search_text_lower: {search_text_lower}\n')
    f.write(f'search_text_lower bytes: {search_text_lower.encode("utf-8")}\n')
    f.write(f'word: {word}\n')
    f.write(f'word len: {len(word)}\n')
    f.write(f'word bytes: {word.encode("utf-8")}\n')
    f.write(f'sublen: {sublen}\n')
    f.write(f'word_sub: {word_sub}\n')
    f.write(f'word_sub bytes: {word_sub.encode("utf-8")}\n')
    f.write(f'word_sub in search: {word_sub in search_text_lower}\n')
    
    # Check if "покупк" is in "список покупок"
    f.write(f'\nDirect check:\n')
    f.write(f'"покупк" in "список покупок": {"покупк" in "список покупок"}\n')
    
    # Check char by char
    f.write(f'\nChar codes in title:\n')
    for i, c in enumerate(title):
        f.write(f'  [{i}] {c} = {ord(c)} = {hex(ord(c))}\n')
    
    f.write(f'\nChar codes in word_sub:\n')
    for i, c in enumerate(word_sub):
        f.write(f'  [{i}] {c} = {ord(c)} = {hex(ord(c))}\n')
    
    # Find "п" in search_text_lower
    f.write(f'\nSearching for "п" (U+043F) in search_text_lower:\n')
    target_code = 0x043F
    for i, c in enumerate(search_text_lower):
        if ord(c) == target_code:
            f.write(f'  Found at pos {i}: {repr(search_text_lower[max(0,i-2):i+10])}\n')
