from pathlib import Path
import subprocess
import shutil

BASE = Path(__file__).resolve().parents[2]
ROOT = Path(__file__).parent / 'candidate'
ROOT.mkdir(exist_ok=True)
for nome in subprocess.check_output(['git', 'ls-files'], cwd=BASE, text=True).splitlines():
    origem = BASE / nome
    if origem.is_file():
        destino = ROOT / nome
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origem, destino)
print(ROOT)
