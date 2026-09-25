"""Duas camadas proativas; a saudação de reação fica em retorno_followup."""

from .tratamentos.retorno_followup import montar_saudacao_retomada_followup

MENSAGEM_FOLLOWUP = ( "Olá, gostaria de continuar seu atendimento agora?"
                      )

MENSAGEM_ENCERRAMENTO_FOLLOWUP = (
    "{saudacao}\n"
    "Entendo que neste momento você não está preparado(a) para todos os benefícios "
    "{beneficios}. Então eu vou liberar {vaga} para a próxima pessoa, tudo bem?\n"
    "Abraços, {nome_agente}."
)

def montar_mensagem_encerramento_followup(
    *, id_etapa, nome_titular, nome_agente, status_dependente=False,
    nome_dependente=None,
):
    # Na etapa 1, um nome do cadastro ainda não foi informado neste atendimento.
    nome = str(nome_titular or "").strip() if id_etapa > 1 else ""
    saudacao = f"Oi {nome}, tudo certo?" if nome else "Oi, tudo certo?"
    if status_dependente and id_etapa > 1:
        # A rota pode estar definida antes da coleta do nome do dependente.
        destinatario = str(nome_dependente or "").strip() or "a outra pessoa"
        beneficios = f"que o Supera pode oferecer para {destinatario}"
        vaga = "a vaga"
    else:
        beneficios = "que o Supera pode te oferecer"
        vaga = "sua vaga"
    return MENSAGEM_ENCERRAMENTO_FOLLOWUP.format(
        saudacao=saudacao, beneficios=beneficios, vaga=vaga, nome_agente=nome_agente,
    )


__all__ = [
    "MENSAGEM_FOLLOWUP", "MENSAGEM_ENCERRAMENTO_FOLLOWUP",
    "montar_mensagem_encerramento_followup",
    "montar_saudacao_retomada_followup",
]
