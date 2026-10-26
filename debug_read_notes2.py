import sys
sys.path.insert(0, '.')
from pathlib import Path

notes_dir = Path('data/notes')
target = notes_dir / 'список_покупок.md'

print(f'target exists: {target.exists()}')
print(f'target name: {target.name}')

text = target.read_text(encoding='utf-8')
print(f'text repr: {repr(text)}')

lines = text.splitlines()
print(f'lines[0]: {repr(lines[0])}')

if lines and lines[0].startswith('#'):
    title = lines[0][1:].strip()
    body = '\n'.join(lines[1:])
else:
    title = target.stem
    body = text

print(f'title: {repr(title)}')
print(f'body: {repr(body)}')

query = 'покупки'
search_text = (title + ' ' + target.name + ' ' + body).lower()
print(f'search_text: {repr(search_text)}')

words = query.lower().split()
print(f'words: {words}')

for word in words:
    if len(word) > 1:
        print(f'word={repr(word)} in search_text: {word in search_text}')
