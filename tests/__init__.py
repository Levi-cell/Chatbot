import logging
import os
import sys
from pathlib import Path


logging.disable(logging.CRITICAL)


ROOT_DIR = Path(__file__).resolve().parents[1]
CALLBACK_DIR = ROOT_DIR / "callback"

TEST_ENV = {
    "DJANGO_SECRET_KEY": "test-secret-key-not-for-production",
    "DJANGO_DEBUG": "False",
    "DJANGO_ALLOWED_HOSTS": "testserver,localhost",
    "DB_HOST": "localhost",
    "DB_NAME": "test_chatbot",
    "DB_USER": "test_user",
    "DB_PASSWORD": "test_password",
    "DB_PORT": "5432",
    "REDIS_HOST": "localhost",
    "REDIS_PORT": "6379",
    "REDIS_USERNAME": "",
    "REDIS_PASSWORD": "",
    "REDIS_SSL": "False",
    "META_ACCESS_TOKEN": "test-meta-token",
    "META_WEBHOOK_VERIFY_TOKEN": "test-verify-token",
    "META_WEBHOOK_SIGNATURE_REQUIRED": "False",
}

for name, value in TEST_ENV.items():
    os.environ[name] = value

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
    # Alguns testes unitarios puros nao dependem do Django inicializado.
    # Quando um teste precisar do Django, a propria falha apontara a configuracao.
    pass
