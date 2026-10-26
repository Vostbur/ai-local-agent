import sys
sys.path.insert(0, '.')
from pathlib import Path

notes_dir = Path('data/notes')

# Try to find the file with "shop" in name
for f in notes_dir.iterdir():
    if f.suffix == '.md' and f.is_file():
        text = f.read_text(encoding='utf-8')
        lines = text.splitlines()
        if lines and lines[0].startswith('#'):
            title = lines[0][1:].strip()
        else:
            title = f.stem
        # search for 'покуп' in title, filename, body
        search_text = (title + ' ' + f.name + ' ' + text).lower()
        if 'покуп' in search_text:
            print(f'FOUND: {f.name}')
            print(f'  title: {title}')
            print(f'  search_text sample: {search_text[:80]}')
            print(f'  body sample: {text[:100]}')
            break
else:
    print('NOT FOUND')
