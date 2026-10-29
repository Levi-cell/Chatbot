"""Composição pura, sem decisão de fluxo, envio ou acesso a dados."""

import re


# Somente os títulos do catálogo são separáveis; negritos do corpo não são títulos.
_CABECALHO = re.compile(r"^(\*(?:Pesquisa de satisfação|Triagem cognitiva|Pergunta [1-6])\*)[ \t]*\n+")
# Retira apenas a saudação/celebração inicial. Preserva a explicação da oferta,
# agradecimentos por respostas e qualquer texto substantivo da etapa.
_ABERTURA_REDUNDANTE = re.compile(
    r"^(?:(?:Maravilha|Prazer), [^\n!]+![^\w\n]*\n\n[ ]*"
    r"|Que bom ver você aqui novamente, [^\n!]+!\n\n"
    r"|Perfeito![^\w\n]*\n\n)"
)
_SAUDACAO_RETORNO = re.compile(r"^Bom te ver novamente(?:, [^\n]+)? ☺️(?:\n\n|$)")
# Nestes convites do catálogo, “Certo” é só uma abertura. Confirmações de
# encaminhamento e a despedida preservam o sentido da resposta recebida.
_CONVITES_SEM_CONCORDANCIA = {
    "Certo, qual é o *nome* do dependente?": "Qual é o *nome* do dependente?",
    "Certo, para fazer *sua reserva*": "Para fazer *sua reserva*",
    "Certo, antes de prosseguirmos com sua reserva": "Antes de prosseguirmos com sua reserva",
}


def _concatenar_fragmentos(*partes):
    """Preserva o texto literal; os fragmentos declaram espaços e quebras."""
    return "".join(parte for parte in partes if parte)


def compor_mensagem_inicial(apresentacao, mensagem_repeticao):
    """Monta a entrada na etapa com apresentação e pergunta reutilizável."""
    return _concatenar_fragmentos(apresentacao, mensagem_repeticao)


def unir_blocos_mensagem(*partes):
    """Separa blocos presentes com uma linha vazia; preserva seu texto interno."""
    return "\n\n".join(parte.strip() for parte in partes if parte and parte.strip())


def compor_tratamento(prefixo, mensagem_repeticao, *, ponte=None):
    """Monta orientação + repetição; contexto inválido usa mensagem própria."""
    return unir_blocos_mensagem(prefixo, ponte, mensagem_repeticao)


def aplicar_prefixo_retorno(texto, prefixo):
    """Aplica o mesmo prefixo uma vez ao envio e ao histórico."""
    if not prefixo or not isinstance(texto, str):
        return texto
    prefixo = prefixo.strip()
    if not prefixo:
        return texto
    titulo = _CABECALHO.match(texto)
    cabecalho = titulo.group(1) if titulo else ""
    corpo = texto[titulo.end():].strip() if titulo else texto.strip()
    if corpo == prefixo or corpo.startswith(prefixo + "\n\n"):
        return unir_blocos_mensagem(cabecalho, corpo)
    corpo = _ABERTURA_REDUNDANTE.sub("", corpo, count=1)
    if _SAUDACAO_RETORNO.match(prefixo):
        for abertura, alternativa in _CONVITES_SEM_CONCORDANCIA.items():
            if corpo.startswith(abertura):
                corpo = alternativa + corpo[len(abertura):]
                break
    return unir_blocos_mensagem(cabecalho, prefixo, corpo)
