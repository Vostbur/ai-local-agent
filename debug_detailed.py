import sys
sys.path.insert(0, '.')
from pathlib import Path

notes_dir = Path('data/notes')
query = 'покупки'

# Step 1: Check if dir exists
exists = notes_dir.exists()
with open('debug_result.txt', 'w', encoding='utf-8') as f:
    f.write(f'1. exists: {exists}\n')
    
    # Step 2: Get md files
    md_files = sorted(p for p in notes_dir.iterdir() if p.suffix == '.md' and p.is_file())
    f.write(f'2. md files count: {len(md_files)}\n')
    
    # Step 3: Check specific file
    target = notes_dir / 'список_покупок.md'
    f.write(f'3. target exists: {target.exists()}\n')
    f.write(f'3. target in md_files: {target in md_files}\n')
    
    # Step 4: Read target file
    if target.exists():
        text = target.read_text(encoding='utf-8')
        f.write(f'4. text repr: {repr(text)}\n')
        
        lines = text.splitlines()
        f.write(f'5. lines count: {len(lines)}\n')
        f.write(f'5. lines[0] repr: {repr(lines[0])}\n')
        
        if lines and lines[0].startswith('#'):
            title = lines[0][1:].strip()
            body = '\n'.join(lines[1:])
        else:
            title = target.stem
            body = text
            
        f.write(f'6. title repr: {repr(title)}\n')
        f.write(f'6. body repr: {repr(body)}\n')
        
        # Step 5: Search logic
        search_text_lower = (title + ' ' + target.name + ' ' + body).lower()
        words = query.lower().split()
        f.write(f'7. search_text_lower repr: {repr(search_text_lower)}\n')
        f.write(f'7. words: {words}\n')
        
        match = any(word in search_text_lower for word in words if len(word) > 1)
        f.write(f'8. MATCH: {match}\n')
        
        # Step 6: Check each word
        for word in words:
            if len(word) > 1:
                f.write(f'9. word={repr(word)} in search: {word in search_text_lower}\n')
                f.write(f'9. word bytes: {word.encode("utf-8")}\n')
                f.write(f'9. search contains "покупки": {"покупки" in search_text_lower}\n')
