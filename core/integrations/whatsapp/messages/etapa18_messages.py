from core.integrations.whatsapp.messages.componentes_compartilhados import (
    montar_texto_com_rodape,
)
from core.integrations.whatsapp.messages.tratamentos_universais import (
    montar_mensagem_tratamento_financeiro,
    montar_mensagem_tratamento_reforco_escolar,
)


# ETAPA 18 - SUA RESERVA APÓS A TRIAGEM COGNITIVA

TEXTO_BOTAO_JA_AGENDEI_ETAPA18 = "Já reservei"

RODAPE_ETAPA18_AGENDAMENTO = (
    "Depois de concluir sua reserva no link, volte aqui e toque em *Já reservei*."
)

MENSAGEM_ETAPA18 = (
    "Agradeço por responder às perguntas! ☺️\n"
    "\n"
    "Para reservar sua *experiência Supera gratuita*, basta clicar neste link "
    "para escolher o melhor dia e horário:\n"
    "{link_agendamento}"
)

MENSAGEM_MIDIA_ETAPA18 = (
    "Olha, ainda não reconhecemos mensagens com mídia, apenas texto.\n"
    "\n"
    "Para continuar, finalize *sua reserva* pelo link:\n"
    "{link_agendamento}"
)

MENSAGEM_FINANCEIRO_ETAPA18 = montar_mensagem_tratamento_financeiro(
    "Para continuar, conclua *sua reserva* pelo link:\n"
    "{link_agendamento}"
)

MENSAGEM_CONTEXTO_INVALIDO_ETAPA18 = (
    "Não consegui entender sua resposta.\n"
    "\n"
    "Escolha o melhor dia e horário e conclua *sua reserva* pelo link abaixo:\n"
    "{link_agendamento}"
)

MENSAGEM_RETOMADA_ETAPA18 = (
    "Para continuar, finalize *sua reserva* pelo link:\n"
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
