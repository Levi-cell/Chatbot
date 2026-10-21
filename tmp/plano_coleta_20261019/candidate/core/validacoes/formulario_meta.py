"""Excecoes textuais do formulario; nao extrai dados nem identifica a origem."""

import re


_ENUNCIADO_INVESTIMENTO = re.compile(
    r"\bo\s+investimento\s+fica\s+na\s+faixa\s+de\s+um\s+curso\s+de\s+ingles\b"
    r"(?:\s*[.!]?\s*quem\s+decide\s+a\s+matricula\s*\?*\s*:)?"
)


def remover_enunciado_investimento(texto_normalizado):
    """Recebe texto sem acentos e em minusculas, preservando o restante.

    A pergunta sobre o decisor so e removida quando acompanha a comparacao
    e termina em dois-pontos, como rotulo de resposta no formulario.
    Nao descarta a resposta nem perguntas adicionais do cliente.
    """
    return _ENUNCIADO_INVESTIMENTO.sub(" ", texto_normalizado)
