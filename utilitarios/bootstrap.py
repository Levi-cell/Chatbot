"""Seleciona explicitamente a configuração usada pelos utilitários."""

import os
from pathlib import Path

from dotenv import dotenv_values


PROJECT_ROOT = Path(__file__).resolve().parent.parent
APPLICATION_ENV_PREFIXES = (
    "DB_",
    "DJANGO_",
    "FUNIL_",
    "META_",
    "REDIS_",
    "WEBHOOK_",
)
APPLICATION_ENV_NAMES = {"PGSSLCERTMODE"}


def _limpar_ambiente_da_aplicacao():
    """Remove configuração herdada antes de instalar a fonte escolhida."""
    for nome in tuple(os.environ):
        if (
            nome in APPLICATION_ENV_NAMES
            or nome.startswith(APPLICATION_ENV_PREFIXES)
        ):
            os.environ.pop(nome, None)


def _validar_configuracao(configuracao, origem):
    invalidas = [
        nome
        for nome, valor in configuracao.items()
        if valor is None
    ]
    if invalidas:
        raise RuntimeError(
            f"Variáveis sem valor em {origem}: "
            + ", ".join(sorted(invalidas))
        )


def _instalar_configuracao(configuracao):
    _limpar_ambiente_da_aplicacao()
    os.environ.update(
        {
            nome: str(valor)
            for nome, valor in configuracao.items()
        }
    )
    # Impede que core.config_env acrescente outra fonte após esta seleção.
    os.environ["PYTHON_DOTENV_DISABLED"] = "1"


def configurar_ambiente_local():
    """Carrega o ``.env`` local e aplica os overrides privados do Windows."""
    try:
        from utilitarios.local_settings import LOCAL_ENV
    except ImportError as exc:
        raise RuntimeError(
            "Arquivo utilitarios/local_settings.py não encontrado"
        ) from exc

    arquivo_env = PROJECT_ROOT / ".env"
    configuracao = {}
    if arquivo_env.is_file():
        configuracao.update(
            dotenv_values(arquivo_env, interpolate=False)
        )
    configuracao.update(LOCAL_ENV)

    _validar_configuracao(configuracao, "configuração local")
    _instalar_configuracao(configuracao)
    return "local_settings"


def configurar_ambiente_utilitario(env_file=None):
    """Usa o arquivo informado ou o ``local_settings.py`` da máquina local.

    A seleção precisa acontecer antes de importar módulos de ``core`` que
    congelam variáveis de ambiente durante o import.
    """
    if env_file is None:
        return configurar_ambiente_local()

    caminho = Path(env_file).expanduser()
    if not caminho.is_file():
        raise RuntimeError(f"Arquivo de ambiente não encontrado: {caminho}")

    configuracao = dotenv_values(caminho, interpolate=False)
    _validar_configuracao(configuracao, caminho)
    _instalar_configuracao(configuracao)
    return str(caminho)
