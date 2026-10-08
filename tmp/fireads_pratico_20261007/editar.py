from pathlib import Path
import ast
import shutil

ROOT = Path(r'C:\Chatbot\Projeto\Chatbot')
DEST = ROOT / 'tmp/fireads_pratico_20261007/candidate'

def read(path):
    return (DEST / path).read_text(encoding='utf-8-sig')

def write(path, content):
    target = DEST / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding='utf-8')

def replace(path, old, new, count=1):
    text = read(path)
    assert text.count(old) >= count, (path, old[:150], text.count(old))
    write(path, text.replace(old, new, count))

def fresh(path):
    target = DEST / path
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / path, target)

def validate():
    for path in DEST.rglob('*.py'):
        ast.parse(path.read_text(encoding='utf-8-sig'), filename=str(path))
