from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa20 import (
    RESPOSTAS_COMENTARIO_RECUSADO,
    TIPOS_MENSAGEM_ACEITOS_ETAPA20,
    normalizar_resposta_comentario,
)


def normalizar_comentario_etapa21(conteudo_texto, tipo_mensagem):
    """Prepara o texto para persistência, sem julgar se é um bom comentário.

    Texto curto, emoji e pontuação são comentários válidos. Ausência de texto,
    botão antigo ou recusa explícita resultam em NULL, sem impedir o encerramento.
    """
    if tipo_mensagem != "text":
        return None

    if not isinstance(conteudo_texto, str):
        return None

    comentario = conteudo_texto.strip()

    if not comentario:
        return None

    if recusou_comentario_etapa21(comentario, tipo_mensagem):
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
