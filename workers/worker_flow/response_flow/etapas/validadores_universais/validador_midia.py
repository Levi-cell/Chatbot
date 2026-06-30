TIPOS_MENSAGEM_SUPORTADOS = {"text", "interactive"}
TIPO_TRATAMENTO_TIPO_NAO_SUPORTADO = "tipo_mensagem_nao_suportado"


def validar_midia(tipo_mensagem):
    return tipo_mensagem not in TIPOS_MENSAGEM_SUPORTADOS
