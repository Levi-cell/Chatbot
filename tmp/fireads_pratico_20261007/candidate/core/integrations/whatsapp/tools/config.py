import re

from core.config_env import env_int, env_optional, env_required


_META_GRAPH_API_VERSION_PATTERN = re.compile(r"^[1-9]\d*\.0$")


TOKEN_USUARIO_META = env_required("META_ACCESS_TOKEN")


def _normalizar_meta_graph_api_version(value):
    version = str(value or "").strip()

    if not _META_GRAPH_API_VERSION_PATTERN.fullmatch(version):
        raise RuntimeError(
            "Valor invalido em META_GRAPH_API_VERSION: use o formato 26.0, "
            "sem o prefixo v"
        )

    return version


META_GRAPH_API_VERSION = _normalizar_meta_graph_api_version(
    env_required("META_GRAPH_API_VERSION")
)
PHONE_REGISTRATION_PIN = env_optional("META_PHONE_REGISTRATION_PIN")

META_HTTP_TIMEOUT = (
    env_int("META_HTTP_CONNECT_TIMEOUT_SECONDS", 30),
    env_int("META_HTTP_READ_TIMEOUT_SECONDS", 35),
)


def get_token_usuario_meta():
    return TOKEN_USUARIO_META


def get_meta_graph_api_version():
    return META_GRAPH_API_VERSION


def construir_url_graph_api(caminho):
    """Monta uma URL versionada sem espalhar a versão pelo projeto."""
    caminho = str(caminho or "").strip().strip("/")

    if not caminho:
        raise ValueError("caminho da Graph API nao informado")

    # O ambiente armazena "26.0"; o prefixo "v" pertence somente à URL.
    return (
        "https://graph.facebook.com/"
        f"v{get_meta_graph_api_version()}/{caminho}"
    )


def get_phone_registration_pin():
    if not PHONE_REGISTRATION_PIN:
        raise RuntimeError(
            "Variavel de ambiente obrigatoria ausente: "
            "META_PHONE_REGISTRATION_PIN"
        )

    return PHONE_REGISTRATION_PIN


def get_meta_http_timeout():
    return META_HTTP_TIMEOUT
