"""Adapta a resposta da etapa ao extrator puro de preferência de turno."""

from core.validacoes.preferencia_turno import extrair_preferencia_turno

TIPOS_MENSAGEM_ACEITOS_ETAPA18 = {"text", "interactive", "interactive_button"}


def validar_etapa18(texto, tipo_mensagem="text"):
    if tipo_mensagem not in TIPOS_MENSAGEM_ACEITOS_ETAPA18:
        return None
    return extrair_preferencia_turno(texto)
