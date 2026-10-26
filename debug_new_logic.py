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
            if len(word) <= 2:
                continue
            sublen = len(word) // 2 + 1
            for start in range(len(word) - sublen + 1):
                if word[start:start + sublen] in search_text_lower:
                    found = True
                    break
            if found:
                break
        
        if not found:
            continue
    
    results.append({'path': str(path), 'title': title})
    if len(results) >= 50:
        break

print(f'Results: {len(results)}')
for r in results:
    print(f'  {r["title"]}')
