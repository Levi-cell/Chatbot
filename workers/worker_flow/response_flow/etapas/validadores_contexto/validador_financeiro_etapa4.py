import re
import unicodedata

from workers.worker_flow.response_flow.etapas.validadores_universais.validador_financeiro import (
    validar_duvida_gratuidade_experiencia,
)


_TERMOS_FINANCEIROS_ISOLADOS = {
    "custo",
    "custos",
    "mensalidade",
    "preco",
    "precos",
    "valor",
    "valores",
}

# Na profissão, a intenção de pedir preços precisa acompanhar o assunto.
# Apenas mencionar valores/custos/investimentos também pode descrever trabalho.
_ASSUNTO_FINANCEIRO = (
    r"(?:custos?|precos?|valor(?:es)?|mensalidades?|investimentos?|orcamentos?)"
)
_PEDIDO_INFORMACAO = (
    r"(?:"
    r"(?:quero|queria|gostaria|preciso) (?:so |apenas )?(?:de )?"
    r"(?:saber|conhecer|consultar|entender|informacoes)|"
    r"(?:me|nos) (?:diz|diga|fala|fale|informe|manda|mande|envia|envie|passa|passe)|"
    r"(?:pode|podem|poderia|poderiam|consegue|conseguem) (?:(?:me|nos) )?"
    r"(?:informar|dizer|falar|passar|enviar|mostrar)"
    r")"
)

_PADROES_PERGUNTA_FINANCEIRA = (
    re.compile(
        rf"\b(?:qual|quais)(?: e| sao| seria| seriam)? (?:(?:os?|as?) )?"
        rf"{_ASSUNTO_FINANCEIRO}\b"
    ),
    re.compile(
        rf"\b{_PEDIDO_INFORMACAO} "
        rf"(?:(?:sobre|de|do|dos|da|das|o|os|a|as|qual|quais|e|sao|seria|seriam) ){{0,5}}"
        rf"{_ASSUNTO_FINANCEIRO}\b"
    ),
    re.compile(
        r"\bquanto "
        r"(?:"
        r"custam?|custariam?|e|fica|sai|pago|"
        r"eu pago|vou pagar|tenho que pagar|"
        r"vou investir|preciso investir|vai ser"
        r")\b"
    ),
    re.compile(
        r"\b(?:tem|possui|ha) (?:algum )?"
        r"(?:custo|preco|valor|mensalidade|taxa|investimento)\b"
    ),
    re.compile(
        r"\b(?:custo|preco|valor) "
        r"(?:da|das|de|do|dos) "
        r"(?:aula|avaliacao|curso|matricula|mensalidade)\b"
    ),
    re.compile(r"\b(?:matricula|mensalidade) (?:custa|e|fica|valor)\b"),
    re.compile(
        r"\b(?:aceita|aceitam|recebe|recebem) "
        r"(?:pix|boleto|cartao|credito|debito)\b"
    ),
    re.compile(
        r"\b(?:pagar|pagamento) "
        r"(?:com|no|por|via) "
        r"(?:pix|boleto|cartao|credito|debito)\b"
    ),
    re.compile(r"\b\d+(?:[.,]\d{1,2})? reais?\b"),
)


def validar_pergunta_financeira_etapa4(conteudo_texto):
    if not isinstance(conteudo_texto, str):
        return False

    if validar_duvida_gratuidade_experiencia(conteudo_texto):
        return True

    if re.search(r"(?:r\s*\$|\$)", conteudo_texto, flags=re.IGNORECASE):
        return True

    texto_normalizado = _normalizar_texto(conteudo_texto)

    if not texto_normalizado:
        return False

    if texto_normalizado in _TERMOS_FINANCEIROS_ISOLADOS:
        return True

    return any(
        padrao.search(texto_normalizado)
        for padrao in _PADROES_PERGUNTA_FINANCEIRA
    )


def _normalizar_texto(texto):
    texto_decomposto = unicodedata.normalize("NFD", texto.casefold())
    texto_sem_acentos = "".join(
        caractere
        for caractere in texto_decomposto
        if unicodedata.category(caractere) != "Mn"
    )
    texto_sem_pontuacao = re.sub(r"[^\w\s]", " ", texto_sem_acentos)
    return " ".join(texto_sem_pontuacao.split())
