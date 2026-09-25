# ETAPA 22 - MENSAGEM TERMINAL DO ATENDIMENTO

### ENCERRAMENTO DO TITULAR: QUEM CONVERSA TAMBÉM FARÁ A EXPERIÊNCIA
MENSAGEM_ETAPA22_TITULAR = (
    "Perfeito, foi um prazer falar com você, estamos ansiosos para te receber na nossa unidade! 🥰🧡\n\n"
    "No próximo dia útil, nossa equipe entrará em contato.\n "
    "Até breve! 👋🏼😉"
)


### ENCERRAMENTO DO DEPENDENTE: ACOLHER O CLIENTE E O PARTICIPANTE PELO NOME
MENSAGEM_ETAPA22_DEPENDENTE = (
    "Perfeito, foi um prazer falar com você, estamos ansiosos para receber você e {nome_dependente} na nossa unidade!  🥰🧡\n\n"
    "No próximo dia útil, nossa equipe entrará em contato.\n "
    "Até breve! 👋🏼😉"
)


def montar_mensagem_etapa22(*, status_dependente=False, nome_dependente=None):
    """A despedida mantém o participante definido ao longo do atendimento."""
    if type(status_dependente) is not bool:
        raise ValueError("Rota do atendimento inválida para a finalização")
    if not status_dependente:
        return MENSAGEM_ETAPA22_TITULAR
    if not isinstance(nome_dependente, str) or not nome_dependente.strip():
        raise ValueError("Nome do dependente ausente para a finalização")
    return MENSAGEM_ETAPA22_DEPENDENTE.format(nome_dependente=nome_dependente.strip())
