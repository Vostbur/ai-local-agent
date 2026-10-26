import sys
sys.path.insert(0, '.')
from pathlib import Path

notes_dir = Path('data/notes')
print(f'exists: {notes_dir.exists()}')
print(f'is_dir: {notes_dir.is_dir()}')

md_files = sorted(p for p in notes_dir.iterdir() if p.suffix == '.md' and p.is_file())
print(f'md files count: {len(md_files)}')
if md_files:
    print(f'first file: {md_files[0]}')
    text = md_files[0].read_text(encoding='utf-8')
    print(f'first file content: {repr(text[:100])}')
    
    lines = text.splitlines()
    print(f'lines[0]: {repr(lines[0])}')
    print(f'starts with #: {lines[0].startswith("#")}')
    
    # Test the search logic
    title = lines[0][1:].strip() if lines[0].startswith('#') else md_files[0].stem
    body = '\n'.join(lines[1:])
    print(f'title: {repr(title)}')
    print(f'body: {repr(body)}')
    
    query = 'покупки'
    search_text_lower = (title + ' ' + md_files[0].name + ' ' + body).lower()
    words = query.lower().split()
    print(f'search_text_lower: {repr(search_text_lower[:100])}')
    print(f'words: {words}')
    print(f'match: {any(word in search_text_lower for word in words if len(word) > 1)}')
