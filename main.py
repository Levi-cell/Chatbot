import logging
import os
import subprocess
import sys
import time
from pathlib import Path

from core.cache.cache_unidade import REDIS_KEY, carregar_cache_redis
from core.database.connection_aws import get_conn
from core.cache.redis_client import get_redis_safe
from core.logging_config import setup_logging
from workers.worker_funil.config import FUNIL_WORKER_ENABLED


PROJECT_ROOT = Path(__file__).resolve().parent
CALLBACK_DIR = PROJECT_ROOT / "callback"
CREATE_NEW_CONSOLE = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)

setup_logging()
logger = logging.getLogger("dev.main")


def carregar_cache_inicial():
    conn = None

    try:
        logger.info("cache_inicial_carregando | acao=validar_unidades")
        conn = get_conn(application_name="script_chatbot")
        cursor = conn.cursor()

        total_banco = carregar_cache_redis(cursor)
        total_redis = get_redis_safe().hlen(REDIS_KEY)

        if total_redis != total_banco:
            raise RuntimeError(
                f"Cache inconsistente: banco={total_banco}, redis={total_redis}"
            )

        logger.info("cache_inicial_ok | unidades=%s", total_redis)

    finally:
        if conn:
            conn.close()


def abrir_terminal(nome, comando, pasta, env):
    comando_cmd = f"title {nome} && {subprocess.list2cmdline(comando)}"
    logger.info(
        "terminal_abrindo | acao=start_process nome=%s pasta=%s comando=%s",
        nome,
        pasta,
        subprocess.list2cmdline(comando),
    )

    return subprocess.Popen(
        ["cmd", "/k", comando_cmd],
        cwd=pasta,
        env=env,
        creationflags=CREATE_NEW_CONSOLE,
    )


def montar_ambiente():
    env = os.environ.copy()
    pythonpath = env.get("PYTHONPATH")

    if pythonpath:
        env["PYTHONPATH"] = f"{PROJECT_ROOT}{os.pathsep}{pythonpath}"
    else:
        env["PYTHONPATH"] = str(PROJECT_ROOT)

    logger.debug(
        "ambiente_montado | acao=definir_pythonpath project_root=%s",
        PROJECT_ROOT,
    )
    return env


def main():
    logger.info("ambiente_dev_iniciando | acao=bootstrap")
    carregar_cache_inicial()

    env = montar_ambiente()

    abrir_terminal(
        "Chatbot Webhook",
        [sys.executable, "manage.py", "runserver", *sys.argv[1:]],
        CALLBACK_DIR,
        env,
    )

    time.sleep(2)

    abrir_terminal(
        "Chatbot Worker",
        [sys.executable, "-m", "workers.worker_flow.main_worker"],
        PROJECT_ROOT,
        env,
    )

    if FUNIL_WORKER_ENABLED:
        time.sleep(2)
        abrir_terminal(
            "Chatbot Worker Funil",
            [sys.executable, "-m", "workers.worker_funil.main_worker"],
            PROJECT_ROOT,
            env,
        )

    logger.info(
        "ambiente_dev_iniciado | webhook=terminal worker=terminal "
        "worker_funil=%s",
        "terminal" if FUNIL_WORKER_ENABLED else "desativado",
    )


if __name__ == "__main__":
    main()



