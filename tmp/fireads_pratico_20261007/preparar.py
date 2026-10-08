"""Constrói uma cópia isolada para escrever e validar o plano, sem aplicar runtime."""
from pathlib import Path
import shutil
import json
import subprocess

ROOT = Path(r'C:\Chatbot\Projeto\Chatbot')
WORK = ROOT / 'tmp/fireads_pratico_20261007'
CANDIDATE = WORK / 'candidate'
WORK.mkdir(parents=True, exist_ok=True)
CANDIDATE.mkdir(exist_ok=True)
tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
for rel in tracked:
    if not rel or not rel.startswith(('core/', 'workers/', 'callback/', 'tests/', 'deploy/')):
        continue
    src = ROOT / rel
    if not src.is_file() or '__pycache__' in src.parts or src.suffix in {'.pyc', '.sqlite3'}:
        continue
    dst = CANDIDATE / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists():
        shutil.copyfile(src, dst)
(WORK / 'base.json').write_text(json.dumps({'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip()},indent=2),encoding='utf-8')
print('Cópia isolada:', CANDIDATE)
