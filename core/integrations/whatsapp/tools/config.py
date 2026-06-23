from core.config_env import env_optional, env_required


TOKEN_USUARIO_META = env_required("META_ACCESS_TOKEN")
WABA_ID = env_optional("META_WABA_ID")
PHONE_NUMBER_ID_DEV = env_optional("META_PHONE_NUMBER_ID_DEV")


def get_token_usuario_meta():
    return TOKEN_USUARIO_META
