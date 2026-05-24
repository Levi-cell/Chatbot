import os
import sys
from pathlib import Path

from django.core.asgi import get_asgi_application

# Permite que o ASGI importe pacotes que ficam na raiz do repositorio,
# como database e repositories, do mesmo jeito que o manage.py ja faz.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'callback.settings')

application = get_asgi_application()
