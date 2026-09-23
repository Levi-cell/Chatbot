"""Etapa 18: sua reserva pelo link, apresentação e repetição."""

from core.integrations.whatsapp.messages.componentes_compartilhados import (
    montar_texto_com_rodape,
)

from core.integrations.whatsapp.messages.tratamentos.composicao import (
    compor_mensagem_inicial,
)
from core.integrations.whatsapp.messages.tratamentos.financeiro import (
    montar_mensagem_tratamento_financeiro,
)
from core.integrations.whatsapp.messages.tratamentos.midia import (
    montar_mensagem_tratamento_midia,
)
from core.integrations.whatsapp.messages.tratamentos.reforco_escolar import (
    montar_mensagem_tratamento_reforco_escolar,
)


TEXTO_BOTAO_JA_AGENDEI_ETAPA18 = "Já reservei"

RODAPE_ETAPA18_AGENDAMENTO = (
    "Quando finalizar nos avisa aqui ☺️"
)

### TRECHO COM O LINK, REUTILIZADO NA INICIAL E NOS TRATAMENTOS
MENSAGEM_REPETICAO_ETAPA18 = (
    "Para reservar {experiencia}, basta clicar neste link e escolher o melhor "
    "dia e horário:\n"
    "{link_agendamento}"
)


### MENSAGEM INICIAL: AGRADECIMENTO + TRECHO DA RESERVA
# A repetição mantém o link e o rodapé, sem agradecer novamente pelas perguntas.
def montar_mensagem_etapa18(link_agendamento, nome_dependente=None, *, repeticao=False):
    mensagem = _montar_repeticao(link_agendamento, nome_dependente)
    if not repeticao:
        mensagem = compor_mensagem_inicial(
            "Obrigado por responder às perguntas! ☺️", mensagem
        )
    return _com_rodape(mensagem)


### TRATAMENTOS: ORIENTAÇÃO + REPETIÇÃO COM O PARTICIPANTE CORRETO
def montar_mensagem_midia_etapa18(link_agendamento, nome_dependente=None):
    mensagem = montar_mensagem_tratamento_midia(
        _montar_repeticao(link_agendamento, nome_dependente),
        aceita_botoes=True,
    )
    return _com_rodape(mensagem)


def montar_mensagem_financeiro_etapa18(link_agendamento, nome_dependente=None):
    mensagem = montar_mensagem_tratamento_financeiro(
        _montar_repeticao(link_agendamento, nome_dependente),
    )
    return _com_rodape(mensagem)


def montar_mensagem_reforco_escolar_etapa18(link_agendamento, nome_dependente=None):
    mensagem = montar_mensagem_tratamento_reforco_escolar(
        _montar_repeticao(link_agendamento, nome_dependente),
    )
    return _com_rodape(mensagem)


### CONTEXTO INVÁLIDO: MENSAGEM PRÓPRIA, SEM CONCATENAR A REPETIÇÃO
def montar_mensagem_contexto_invalido_etapa18(link_agendamento, nome_dependente=None):
    experiencia = _descrever_experiencia(nome_dependente)
    link = _normalizar_link_agendamento(link_agendamento)
    return _com_rodape(
        f"Olha, não consegui entender. "
        f"Se ainda não escolheu o dia e horário para {experiencia}, use o link abaixo:\n"
        f"{link}"
    )


def montar_botoes_etapa18():
    return (TEXTO_BOTAO_JA_AGENDEI_ETAPA18,)


# Apenas formata titular/dependente e link; o contexto fornece os dados da rota.
def _descrever_experiencia(nome_dependente):
    experiencia = "sua *experiência Supera gratuita*"
    if nome_dependente is not None:
        if not isinstance(nome_dependente, str) or not nome_dependente.strip():
            raise ValueError("Nome do dependente inválido para apresentar sua reserva")
        experiencia = f"a *experiência Supera gratuita* de {nome_dependente.strip()}"
    return experiencia


def _montar_repeticao(link_agendamento, nome_dependente):
    return MENSAGEM_REPETICAO_ETAPA18.format(
        experiencia=_descrever_experiencia(nome_dependente),
        link_agendamento=_normalizar_link_agendamento(link_agendamento),
    )


def _com_rodape(mensagem):
    return montar_texto_com_rodape(mensagem, RODAPE_ETAPA18_AGENDAMENTO)


def _normalizar_link_agendamento(link_agendamento):
    link = str(link_agendamento or "").strip()

    if not link:
        raise ValueError("Link de agendamento da unidade não configurado")

    if not link.startswith(("https://", "http://")):
        raise ValueError("Link de agendamento da unidade é inválido")

    return link
