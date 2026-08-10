"""Textos de tratamento compartilhados por diferentes etapas do fluxo."""


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
