"""Textos de tratamento compartilhados por diferentes etapas do fluxo."""


MENSAGEM_TRATAMENTO_FINANCEIRO = (
    "Olha, os valores de investimento são definidos após a "
    "*experiência Supera gratuita* na unidade. Assim, nossa equipe poderá "
    "orientar você sobre a opção mais adequada."
)


def montar_mensagem_tratamento_financeiro(mensagem_retomada):
    """Explica o investimento e retoma a pergunta sem mudar o participante."""
    return (
        f"{MENSAGEM_TRATAMENTO_FINANCEIRO}\n\n"
        f"Mas bora lá:\n\n"
        f"{mensagem_retomada}"
    )


MENSAGEM_TRATAMENTO_REFORCO_ESCOLAR = (
    "Olha, o Supera não é reforço escolar.\n"
    "Nós trabalhamos a raiz da aprendizagem, desenvolvendo habilidades como "
    "atenção, concentração, memória e raciocínio — o alicerce necessário "
    "para aprender melhor em qualquer matéria. 🧠✨"
)


def montar_mensagem_tratamento_reforco_escolar(mensagem_retomada):
    """Acrescenta ao tratamento a retomada neutra da etapa atual."""
    return (
        f"{MENSAGEM_TRATAMENTO_REFORCO_ESCOLAR}\n\n"
        f"Mas bora lá:\n\n"
        f"{mensagem_retomada}"
    )
