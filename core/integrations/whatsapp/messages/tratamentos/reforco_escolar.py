"""Explicação sobre estimulação cognitiva, seguida da pergunta da etapa."""

from .composicao import compor_tratamento


MENSAGEM_TRATAMENTO_REFORCO_ESCOLAR = (
    "Olha, o Supera não é reforço escolar.\n"
    "Nós trabalhamos a raiz da aprendizagem, desenvolvendo habilidades como "
    "atenção, concentração, memória e raciocínio — o alicerce necessário "
    "para aprender melhor em qualquer matéria. 🧠✨"
)


def montar_mensagem_tratamento_reforco_escolar(mensagem_repeticao):
    return compor_tratamento(
        MENSAGEM_TRATAMENTO_REFORCO_ESCOLAR,
        mensagem_repeticao,
        ponte="Mas bora lá:",
    )
