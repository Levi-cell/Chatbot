from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa20 import (
    RESPOSTAS_COMENTARIO_ACEITO,
    RESPOSTAS_COMENTARIO_RECUSADO,
    TIPOS_MENSAGEM_ACEITOS_ETAPA20,
    normalizar_resposta_comentario,
)


RESPOSTAS_GENERICAS_SEM_COMENTARIO = {
    "ok",
    "okay",
    "certo",
    "beleza",
    *RESPOSTAS_COMENTARIO_ACEITO,
}


def normalizar_comentario_etapa21(conteudo_texto, tipo_mensagem):
    """Preserva o comentário livre e rejeita confirmações sem conteúdo."""
    if tipo_mensagem != "text":
        return None

    if not isinstance(conteudo_texto, str):
        return None

    comentario = conteudo_texto.strip()

    if not comentario:
        return None

    resposta_normalizada = normalizar_resposta_comentario(comentario)

    if (
        not resposta_normalizada
        or resposta_normalizada in RESPOSTAS_GENERICAS_SEM_COMENTARIO
        or resposta_normalizada in RESPOSTAS_COMENTARIO_RECUSADO
    ):
        return None

    return comentario


def recusou_comentario_etapa21(conteudo_texto, tipo_mensagem):
    """Permite desistência explícita, inclusive por botão antigo já exibido."""
    if tipo_mensagem not in TIPOS_MENSAGEM_ACEITOS_ETAPA20:
        return False

    if not isinstance(conteudo_texto, str):
        return False

    return (
        normalizar_resposta_comentario(conteudo_texto)
        in RESPOSTAS_COMENTARIO_RECUSADO
    )
