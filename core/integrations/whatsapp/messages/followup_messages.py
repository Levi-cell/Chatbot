"""Duas camadas proativas; a saudação de reação fica em retorno_followup."""

from .tratamentos.retorno_followup import montar_saudacao_retomada_followup

MENSAGEM_FOLLOWUP = ( "Olá, gostaria de continuar seu atendimento agora?"
                      )

MENSAGEM_ENCERRAMENTO_FOLLOWUP = (
    "{saudacao}\n\n"
    "Entendo que neste momento você não está preparado(a) para aproveitar todos os benefícios "
    "{beneficios}. Então eu vou liberar {vaga} para a próxima pessoa, tudo bem?\n"
    "Ficamos à disposição 🙂\n\n"
    "Abraços, {nome_agente}. 👋"
)

MENSAGEM_ENCERRAMENTO_FOLLOWUP_DEPENDENTE = (
    "{saudacao}\n\n"
    "Entendo que neste momento você e {nome_dependente} não estão preparados para "
    "aproveitar todos os benefícios que o Supera pode oferecer. Então eu vou liberar "
    "a vaga para a próxima pessoa, tudo bem?\n\n"
    "Ficamos à disposição 🙂\n\n"
    "Abraços, {nome_agente}. 👋"
)

def montar_mensagem_encerramento_followup(
    *, id_etapa, nome_titular, nome_agente, status_dependente=False,
    nome_dependente=None,
):
    # Na etapa 1, um nome do cadastro ainda não foi informado neste atendimento.
    nome = str(nome_titular or "").strip() if id_etapa > 1 else ""
    saudacao = f"Oi {nome}, tudo certo?" if nome else "Oi, tudo certo?"
    # Sem nome coletado, usar o texto do titular, preservando a rota da conversa.
    nome_dependente = str(nome_dependente or "").strip()
    if status_dependente and id_etapa > 1 and nome_dependente:
        return MENSAGEM_ENCERRAMENTO_FOLLOWUP_DEPENDENTE.format(
            saudacao=saudacao, nome_dependente=nome_dependente, nome_agente=nome_agente,
        )
    return MENSAGEM_ENCERRAMENTO_FOLLOWUP.format(
        saudacao=saudacao, beneficios="que o Supera pode te oferecer",
        vaga="sua vaga", nome_agente=nome_agente,
    )


__all__ = [
    "MENSAGEM_FOLLOWUP", "MENSAGEM_ENCERRAMENTO_FOLLOWUP",
    "MENSAGEM_ENCERRAMENTO_FOLLOWUP_DEPENDENTE",
    "montar_mensagem_encerramento_followup",
    "montar_saudacao_retomada_followup",
]
