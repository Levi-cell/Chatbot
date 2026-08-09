import re

from workers.worker_flow.response_flow.etapas.validadores_universais.validador_financeiro import (
    normalizar_texto,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_COMENTARIO_SATISFACAO_ACEITO,
    EVENTO_COMENTARIO_SATISFACAO_RECUSADO,
)


TIPOS_MENSAGEM_ACEITOS_ETAPA20 = {
    "text",
    "interactive",
    "button",
}

RESPOSTAS_COMENTARIO_ACEITO = {
    "sim",
    "sim quero comentar",
    "sim quero sugerir",
    "quero comentar",
    "quero sugerir",
    "quero deixar um comentario",
    "quero deixar uma sugestao",
    "eu quero comentar",
    "eu quero sugerir",
    "gostaria de comentar",
    "gostaria de sugerir",
}

RESPOSTAS_COMENTARIO_RECUSADO = {
    "nao",
    "nao quero comentar",
    "nao quero sugerir",
    "prefiro nao comentar",
    "prefiro nao sugerir",
}


def validar_decisao_comentario_etapa20(
    conteudo_texto,
    tipo_mensagem,
):
    """Traduz somente intenções inequívocas em eventos da etapa 20."""
    if tipo_mensagem not in TIPOS_MENSAGEM_ACEITOS_ETAPA20:
        return None

    if not isinstance(conteudo_texto, str):
        return None

    resposta = normalizar_resposta_comentario(conteudo_texto)

    if resposta in RESPOSTAS_COMENTARIO_ACEITO:
        return EVENTO_COMENTARIO_SATISFACAO_ACEITO

    if resposta in RESPOSTAS_COMENTARIO_RECUSADO:
        return EVENTO_COMENTARIO_SATISFACAO_RECUSADO

    return None


def normalizar_resposta_comentario(texto):
    texto_sem_acento = normalizar_texto(texto)
    texto_sem_pontuacao = re.sub(
        r"[^a-z0-9\s]",
        " ",
        texto_sem_acento,
    )
    return " ".join(texto_sem_pontuacao.split())
