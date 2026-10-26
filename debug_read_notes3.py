import sys
sys.path.insert(0, '.')
from pathlib import Path

notes_dir = Path('data/notes')
target = notes_dir / 'список_покупок.md'

result = []
result.append(f'target exists: {target.exists()}')
result.append(f'target name: {target.name}')

text = target.read_text(encoding='utf-8')
result.append(f'text repr: {repr(text)}')

lines = text.splitlines()
result.append(f'lines[0]: {repr(lines[0])}')

if lines and lines[0].startswith('#'):
    title = lines[0][1:].strip()
    body = '\n'.join(lines[1:])
else:
    title = target.stem
    body = text

result.append(f'title: {repr(title)}')
result.append(f'body: {repr(body)}')

query = 'покупки'
search_text = (title + ' ' + target.name + ' ' + body).lower()
result.append(f'search_text: {repr(search_text)}')

words = query.lower().split()
result.append(f'words: {words}')

match = False
for word in words:
    if len(word) > 1:
        found = word in search_text
        result.append(f'word={repr(word)} in search_text: {found}')
        if found:
            match = True

result.append(f'MATCH: {match}')

with open('debug_output.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(result))
