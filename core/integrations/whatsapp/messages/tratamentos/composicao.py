"""Composição pura, sem decisão de fluxo, envio ou acesso a dados."""


def _concatenar_fragmentos(*partes):
    """Preserva o texto literal; os fragmentos declaram espaços e quebras."""
    return "".join(parte for parte in partes if parte)


def compor_mensagem_inicial(apresentacao, mensagem_repeticao):
    """Monta a entrada na etapa com apresentação e pergunta reutilizável."""
    return _concatenar_fragmentos(apresentacao, mensagem_repeticao)


def compor_tratamento(prefixo, mensagem_repeticao, *, ponte=None):
    """Monta orientação + repetição; contexto inválido usa mensagem própria."""
    return _concatenar_fragmentos(prefixo, ponte, mensagem_repeticao)


def aplicar_prefixo_retorno(texto, prefixo):
    """Aplica o mesmo prefixo uma vez ao envio e ao histórico."""
    if not prefixo or not isinstance(texto, str) or texto.startswith(prefixo):
        return texto
    return f"{prefixo}{texto}"
