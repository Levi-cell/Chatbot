"""Duas camadas proativas; a saudação de reação fica em retorno_followup."""

from .componentes_compartilhados import montar_texto_com_rodape
from .tratamentos.retorno_followup import montar_saudacao_retomada_followup

MENSAGEM_LEMBRETE_FOLLOWUP = (
    "{saudacao}\n\n"
    "Queremos muito continuar te ajudando! Será um prazer receber "
    "{participantes} na nossa unidade para {artigo_experiencia} "
    "*experiência Supera gratuita*! 🧡\n\n"
    "Podemos continuar seu atendimento por aqui?"
)
RODAPE_LEMBRETE_FOLLOWUP = "Estaremos te esperando!"
RODAPE_ENCERRAMENTO_FOLLOWUP = "Abraços, {nome_agente}. 🧡"

MENSAGEM_ENCERRAMENTO_FOLLOWUP = (
    "{saudacao}\n\n"
    "Entendo que neste momento você não está preparado(a) para aproveitar todos os benefícios "
    "{beneficios}. Então eu vou liberar a vaga para a próxima pessoa "
    "e encerrar o seu atendimento, tudo bem?\n\n"
    "Fico à disposição caso precise falar comigo novamente! ☺️👋"
)

MENSAGEM_ENCERRAMENTO_FOLLOWUP_DEPENDENTE = (
    "{saudacao}\n\n"
    "Entendo que neste momento você e {nome_dependente} não estão preparados para "
    "aproveitar todos os benefícios que o Supera pode oferecer. Então eu vou liberar "
    "a vaga para a próxima pessoa e encerrar o seu atendimento, tudo bem?\n\n"
    "Fico à disposição caso precise falar comigo novamente! ☺️👋"
)


def montar_mensagem_followup(
    *, id_etapa, nome_titular, status_dependente=False, nome_dependente=None,
):
    # Na etapa 1, ainda não aproveitar nomes ou rota de um atendimento anterior.
    nome_titular = str(nome_titular or "").strip() if id_etapa > 1 else ""
    saudacao = f"Olá, {nome_titular}! ☺️" if nome_titular else "Olá! ☺️"
    participantes = "você"
    artigo_experiencia = "sua"
    if status_dependente and id_etapa > 1:
        nome_dependente = str(nome_dependente or "").strip()
        # A rota já é conhecida, mesmo que o nome do dependente ainda falte.
        participantes = f"você e {nome_dependente}" if nome_dependente else "vocês"
        artigo_experiencia = "a"
    mensagem = MENSAGEM_LEMBRETE_FOLLOWUP.format(
        saudacao=saudacao, participantes=participantes,
        artigo_experiencia=artigo_experiencia,
    )
    return montar_texto_com_rodape(mensagem, RODAPE_LEMBRETE_FOLLOWUP)


# Texto completo sem nomes para consumidores que não recebem o contexto da conversa.
MENSAGEM_FOLLOWUP = montar_mensagem_followup(id_etapa=1, nome_titular=None)


def montar_mensagem_encerramento_followup(
    *, id_etapa, nome_titular, nome_agente, status_dependente=False,
    nome_dependente=None,
):
    # Na etapa 1, um nome do cadastro ainda não foi informado neste atendimento.
    nome = str(nome_titular or "").strip() if id_etapa > 1 else ""
    saudacao = f"Oi {nome}, tudo bem? ☺️" if nome else "Oi, tudo bem? ☺️"
    # Sem nome coletado, usar o texto do titular, preservando a rota da conversa.
    nome_dependente = str(nome_dependente or "").strip()
    if status_dependente and id_etapa > 1 and nome_dependente:
        mensagem = MENSAGEM_ENCERRAMENTO_FOLLOWUP_DEPENDENTE.format(
            saudacao=saudacao, nome_dependente=nome_dependente,
        )
    else:
        mensagem = MENSAGEM_ENCERRAMENTO_FOLLOWUP.format(
            saudacao=saudacao, beneficios="que o Supera pode te oferecer",
        )
    return montar_texto_com_rodape(
        mensagem, RODAPE_ENCERRAMENTO_FOLLOWUP.format(nome_agente=nome_agente),
    )


__all__ = [
    "MENSAGEM_FOLLOWUP", "MENSAGEM_ENCERRAMENTO_FOLLOWUP",
    "MENSAGEM_ENCERRAMENTO_FOLLOWUP_DEPENDENTE",
    "montar_mensagem_followup",
    "montar_mensagem_encerramento_followup",
    "montar_saudacao_retomada_followup",
]
