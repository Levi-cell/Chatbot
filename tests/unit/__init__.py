import os
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
CALLBACK_DIR = ROOT_DIR / "callback"

for path in (str(ROOT_DIR), str(CALLBACK_DIR)):
    while path in sys.path:
        sys.path.remove(path)

sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(1, str(CALLBACK_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "callback.callback.settings")

try:
    import django

    django.setup()
except Exception:
    # Testes unitarios puros nao dependem do Django inicializado.
    # Testes que dependem do Django vao falhar explicitamente se houver erro real.
    pass
