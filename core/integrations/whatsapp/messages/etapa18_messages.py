from core.integrations.whatsapp.messages.componentes_compartilhados import (
    montar_texto_com_rodape,
)
from core.integrations.whatsapp.messages.tratamentos_universais import (
    montar_mensagem_tratamento_reforco_escolar,
)


# ETAPA 18 - AGENDAMENTO APÓS A TRIAGEM COGNITIVA

TEXTO_BOTAO_JA_AGENDEI_ETAPA18 = "Já agendei"

RODAPE_ETAPA18_AGENDAMENTO = (
    "Após finalizar, volta aqui e nos avisa no botão abaixo"
)

MENSAGEM_ETAPA18 = (
    "Obrigada por responder as perguntas! ☺️\n\n"
    "Para escolher o melhor dia e horário para sua avaliação cognitiva + "
    "aula experimental *gratuita*, basta clicar no link:\n"
    "{link_agendamento}"
)

MENSAGEM_MIDIA_ETAPA18 = (
    "Olha, ainda não reconhecemos mensagens com mídia, apenas texto.\n\n"
    "Para continuar, finalize seu agendamento pelo link:\n"
    "{link_agendamento}"
)

MENSAGEM_FINANCEIRO_ETAPA18 = (
    "Olha, demais informações, como valores de investimento, são apresentadas no atendimento "
    "presencial após sua aula *gratuita*.\n\n"
    "Para continuar, finalize seu agendamento pelo link:\n"
    "{link_agendamento}"
)

MENSAGEM_CONTEXTO_INVALIDO_ETAPA18 = (
    "Não consegui entender sua resposta.\n\n"
    "Depois de finalizar seu agendamento pelo link abaixo, selecione "
    "*Já agendei*.\n"
    "{link_agendamento}"
)

MENSAGEM_RETOMADA_ETAPA18 = (
    "Para continuar, finalize seu agendamento pelo link:\n"
    "{link_agendamento}"
)


def montar_mensagem_etapa18(link_agendamento):
    return _montar_mensagem_com_link_e_rodape(
        MENSAGEM_ETAPA18,
        link_agendamento,
    )


def montar_mensagem_midia_etapa18(link_agendamento):
    return _montar_mensagem_com_link_e_rodape(
        MENSAGEM_MIDIA_ETAPA18,
        link_agendamento,
    )


def montar_mensagem_financeiro_etapa18(link_agendamento):
    return _montar_mensagem_com_link_e_rodape(
        MENSAGEM_FINANCEIRO_ETAPA18,
        link_agendamento,
    )


def montar_mensagem_reforco_escolar_etapa18(link_agendamento):
    return _montar_mensagem_com_link_e_rodape(
        montar_mensagem_tratamento_reforco_escolar(
            MENSAGEM_RETOMADA_ETAPA18,
        ),
        link_agendamento,
    )


def montar_mensagem_contexto_invalido_etapa18(link_agendamento):
    return _montar_mensagem_com_link_e_rodape(
        MENSAGEM_CONTEXTO_INVALIDO_ETAPA18,
        link_agendamento,
    )


def montar_botoes_etapa18():
    return (TEXTO_BOTAO_JA_AGENDEI_ETAPA18,)


def _montar_mensagem_com_link_e_rodape(mensagem, link_agendamento):
    link = _normalizar_link_agendamento(link_agendamento)
    texto = mensagem.format(link_agendamento=link)
    return montar_texto_com_rodape(
        texto,
        RODAPE_ETAPA18_AGENDAMENTO,
    )


def _normalizar_link_agendamento(link_agendamento):
    link = str(link_agendamento or "").strip()

    if not link:
        raise ValueError("Link de agendamento da unidade não configurado")

    if not link.startswith(("https://", "http://")):
        raise ValueError("Link de agendamento da unidade é inválido")

    return link
