import sys
sys.path.insert(0, '.')
from pathlib import Path
from src.agent.tools.read_notes import read_notes

# Test with real path
result = read_notes('покупки', Path('data/notes'))
with open('debug_result.txt', 'w', encoding='utf-8') as f:
    f.write(f'result count: {len(result)}\n')
    f.write(f'result: {result}\n')
    if result:
        f.write(f'title: {result[0].get("title")}\n')
