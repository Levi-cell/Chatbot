"""Composição pura, sem decisão de fluxo, envio ou acesso a dados."""


def _unir_paragrafos(*partes):
    """Compartilha a formatação sem atribuir significado aos fragmentos."""
    return "\n\n".join(parte for parte in partes if parte)


def compor_mensagem_inicial(apresentacao, mensagem_repeticao):
    """Monta a entrada na etapa com apresentação e pergunta reutilizável."""
    return _unir_paragrafos(apresentacao, mensagem_repeticao)


def compor_tratamento(prefixo, mensagem_repeticao, *, ponte=None):
    """Monta orientação + repetição; contexto inválido usa mensagem própria."""
    return _unir_paragrafos(prefixo, ponte, mensagem_repeticao)


def montar_prefixo_retorno(saudacao):
    """Reserva o parágrafo que será aplicado à fala escolhida pelo worker."""
    return f"{saudacao}\n\n"


def aplicar_prefixo_retorno(texto, prefixo):
    """Aplica o mesmo prefixo uma vez ao envio e ao histórico."""
    if not prefixo or not isinstance(texto, str) or texto.startswith(prefixo):
        return texto
    return f"{prefixo}{texto}"
