from workers.worker_flow.response_flow.etapas.validadores_universais.validador_financeiro import (
    normalizar_texto,
)


RESPOSTA_SEM_COMENTARIO_ETAPA18 = "prefiro nao comentar"


def normalizar_comentario_etapa18(conteudo_texto, tipo_mensagem):
    """Retorna texto util ou None para midia e recusa explicita em comentar."""
    if tipo_mensagem not in {"text", "interactive", "button"}:
        return None

    if not isinstance(conteudo_texto, str):
        return None

    comentario = conteudo_texto.strip()

    if not comentario:
        return None

    if normalizar_texto(comentario) == RESPOSTA_SEM_COMENTARIO_ETAPA18:
        return None

    return comentario
