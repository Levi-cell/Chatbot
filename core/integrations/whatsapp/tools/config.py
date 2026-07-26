from core.config_env import env_int, env_optional, env_required


TOKEN_USUARIO_META = env_required("META_ACCESS_TOKEN")
PHONE_REGISTRATION_PIN = env_optional("META_PHONE_REGISTRATION_PIN")

META_HTTP_TIMEOUT = (
    env_int("META_HTTP_CONNECT_TIMEOUT_SECONDS", 30),
    env_int("META_HTTP_READ_TIMEOUT_SECONDS", 35),
)


def get_token_usuario_meta():
    return TOKEN_USUARIO_META


def get_phone_registration_pin():
    if not PHONE_REGISTRATION_PIN:
        raise RuntimeError(
            "Variavel de ambiente obrigatoria ausente: "
            "META_PHONE_REGISTRATION_PIN"
        )

    return PHONE_REGISTRATION_PIN


def get_meta_http_timeout():
    return META_HTTP_TIMEOUT
