MENSAGEM_ETAPA_1 = (
    "Olá! {saudacao}. Seja bem-vindo ao Assistente de Agendamento do Supera."
)
TITULO_BOTAO_ETAPA_1 = "Aperte em mim"


def montar_mensagem_etapa_1(saudacao):
    return MENSAGEM_ETAPA_1.format(saudacao=saudacao)
