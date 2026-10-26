from pathlib import Path

notes_dir = Path('data/notes')
query = 'покупки'

md_files = sorted(p for p in notes_dir.iterdir() if p.suffix == '.md' and p.is_file())
results = []

for path in md_files:
    text = path.read_text(encoding='utf-8')
    lines = text.splitlines()
    
    if lines and lines[0].startswith('#'):
        title = lines[0][1:].strip()
        body = '\n'.join(lines[1:])
    else:
        title = path.stem
        body = text
    
    stripped_query = query.strip()
    if stripped_query:
        search_text_lower = (title + ' ' + path.name + ' ' + body).lower()
        words = stripped_query.lower().split()
        found = False
        for word in words:
            if len(word) <= 1:
                continue
            sublen = max(3, len(word) - 1)
            word_sub = word[:sublen]
            is_in = word_sub in search_text_lower
            if is_in:
                found = True
                break
            # debug first file
            if 'список' in path.name:
                print(f'path: {path.name}')
                print(f'title: {title}')
                print(f'search_text_lower: {search_text_lower}')
                print(f'word: {word}')
                print(f'sublen: {sublen}')
                print(f'word[:sublen]: {word_sub}')
                print(f'found: {is_in}')
        
        if not found:
            continue
    
    results.append({'path': str(path), 'title': title, 'preview': body[:200]})
    if len(results) >= 50:
        break

print(f'Results: {len(results)}')
for r in results:
    print(f'  {r["title"]}')
