import sys
sys.path.insert(0, '.')
from pathlib import Path
from src.agent.tools.read_notes import read_notes

result = read_notes('покупки', Path('data/notes'))
with open('debug_result.txt', 'w', encoding='utf-8') as f:
    f.write(f'result count: {len(result)}\n')
    for r in result:
        f.write(f'  title: {r["title"]}\n')
        f.write(f'  path: {r["path"]}\n')
        f.write(f'  preview: {r["preview"][:100]}\n')
