# O texto de ambos os formatos interativos é extraído pelo webhook.
TIPOS_MENSAGEM_SUPORTADOS = {"text", "interactive", "interactive_button"}
TIPO_TRATAMENTO_TIPO_NAO_SUPORTADO = "tipo_mensagem_nao_suportado"


def validar_midia(tipo_mensagem):
    return tipo_mensagem not in TIPOS_MENSAGEM_SUPORTADOS
