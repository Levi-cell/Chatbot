"""Reconhece endereço por palavra e demais pedidos de localização por contexto."""

import re
import unicodedata


TIPO_TRATAMENTO_ENDERECO = "pedido_endereco"

# Abreviações são aceitas apenas nestas construções de localização; não há
# correção aproximada de palavras da mensagem inteira (fica/faca, por exemplo).
_ONDE = r"(?:a?onde|a?ond)"
# Ligações curtas entre o pedido e o lugar: "qual é o", "onde q", "me diz a".
# A lista explícita evita aceitar qualquer texto entre a pergunta e seu alvo.
_LIGACAO = r"(?:(?:o|a|do|da|de|em|no|na|um|uma|seu|sua|e|eh|que|q)\s+){0,4}"
_UNIDADE = r"(?:unidade|escola|sede|espaco|supera|curso)"
_SUJEITO = rf"(?:voces|vcs|vc|(?:(?:a|o|essa|esse|sua|seu)\s+)?{_UNIDADE})"
_VERBO = r"(?:ficam?|fcam?|estao?|tao?|se localizam?|e|eh|sao|atendem?)"
_LUGAR = r"(?:(?:em\s+)?(?:que|q|qual)\s+(?:rua|bairro|cidade|regiao|local|endereco))"
_CAMPO = r"(?:endereco|localizacao|local|cep|mapa|rua|bairro|cidade|ponto de referencia)"
_LOCALIZACAO_DO_CAMPO = (
    rf"(?:\s+(?:(?:em\s+)?(?:que|q)\s+)?(?:{_SUJEITO}\s+)?{_VERBO}"
    r"(?:\s+localizad[oa]s?)?)?"
)
_PEDIDOS = (
    re.compile(rf"\b(?:{_ONDE}|{_LUGAR})\s+{_LIGACAO}(?:{_SUJEITO}\s+)?{_VERBO}"
               r"(?:\s+localizad[oa]s?)?\b"),
    re.compile(rf"\b(?:{_SUJEITO}\s+)?(?:ficam?|fcam?|estao?|tao?|se localizam?|e|eh)"
               rf"\s+(?:localizad[oa]s?\s+)?(?:{_ONDE}|{_LUGAR})\b"),
    re.compile(r"\bcomo\s+(?:que\s+|q\s+)?(?:eu\s+)?(?:faco\s+(?:para|pra|p)\s+)?(?:chego|chegar)\b"),
    re.compile(rf"\b(?:qual|quero|queria|preciso|gostaria|saber|manda[r]?|mande|"
               rf"envia[r]?|envie|passa[r]?|passe|informa[r]?|informe|diga|diz(?:er)?|{_ONDE})\s+"
               rf"(?:por favor\s+)?{_LIGACAO}{_CAMPO}{_LOCALIZACAO_DO_CAMPO}\b"),
)
_ALVO = re.compile(
    rf"^(?:(?:d[aeo]|n[ao]|em|ate|para|pra|ao)\s+)?{_SUJEITO}\b"
)
_COMPLEMENTO = re.compile(
    r"^(?:(?:ate )?(?:ai|aqui)|mesmo|exatamente|completo|exato|por favor|por gentileza|pfv|pf|obrigad[oa]|"
    r"(?:de|a) (?:onibus|carro|metro|trem|pe|uber)|pelo whatsapp|"
    r"para eu|pra eu|para ir|pra ir|pois|porque|que eu|q eu)\b"
)
_ISOLADO = re.compile(
    rf"(?:(?:o |a )?(?:localizacao|cep|mapa)(?:\s+(?:d[aeo])\s+{_SUJEITO})?"
    rf"|(?:me (?:diz|diga) )?{_ONDE})"
    r"(?:\s+(?:por favor|por gentileza|pfv|pf))?"
)
_OUTRO_ASSUNTO = re.compile(
    r"\b(?:e-?mail|eletronico|site|link|ip|aplicativo|app|botao|pesquisa|"
    r"cadastro|formulario|minha casa|meu trabalho|meu endereco)\b"
)
_DISPENSA = re.compile(
    r"\b(?:ja (?:sei|conheco|tenho|recebi|encontrei|achei)|"
    r"nao (?:me )?(?:quero|preciso|precisa|mande|envie|manda|envia|diga|diz)|"
    r"(?:eu )?(?:moro|trabalho))\b|(?<!nao )\b(?:sei|conheco)\b"
)
_OUTRO_SUJEITO = re.compile(
    r"\b(?:ele|ela|minha casa|meu trabalho|meu filho|minha filha|"
    r"botao|pesquisa|formulario|cadastro|consulta|email|resultado|link|site|teste)\s*$"
)


def _pedido_na_frase(frase):
    frase = frase.strip(" ,:–—-\t")
    # Um pedido curto também pode vir depois de uma saudação.
    frase = re.sub(r"^(?:(?:oi|ola|bom dia|boa tarde|boa noite)[ ,:]*)+", "", frase)
    if _ISOLADO.fullmatch(frase):
        return True
    for padrao in _PEDIDOS:
        for pedido in padrao.finditer(frase):
            antes, depois = frase[:pedido.start()], frase[pedido.end():].strip(" ,:")
            # Verifica a oração do pedido, não bloqueia a mensagem inteira.
            # Assim, mencionar outro local não esconde uma pergunta à unidade.
            contexto = re.split(r",|\b(?:e|mas|porem)\b", antes)[-1]
            if _DISPENSA.search(contexto + pedido.group()) or _OUTRO_SUJEITO.search(contexto):
                continue
            if not depois or _ALVO.match(depois) or _COMPLEMENTO.match(depois):
                # Assuntos digitais após um alvo físico também não são um
                # pedido de endereço: "onde fica a unidade no aplicativo".
                complemento = re.split(r",|\b(?:e|mas|porem)\b", depois)[0]
                if not _OUTRO_ASSUNTO.search(complemento):
                    return True
    return False


def validar_pedido_endereco(texto):
    if not isinstance(texto, str):
        return False
    texto = unicodedata.normalize("NFKD", texto.casefold())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"[^\w\s.,!?;:-]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    # A exceção é por ocorrência, não por mensagem: mencionar endereço de email
    # não oculta outro "endereço" ou uma pergunta física no mesmo texto.
    texto = re.sub(
        r"\bendereco(?:\s*:\s*|\s+)(?:(?:de|do|da)\s+)?(?:e[ -]?mail|eletronico)\b",
        "email", texto,
    )
    # Regra ampla aprovada: toda ocorrência restante da palavra ativa, inclusive
    # endereço já conhecido, informado pelo cliente ou de site/IP. Não exige pedido.
    if re.search(r"\bendereco\b", texto):
        return True
    # Quebras de linha simples dentro de uma pergunta não mudam sua intenção.
    # Pontuação e novas perguntas separam orações para não ocultar pedidos
    # válidos depois de uma informação residencial ou de uma dúvida de email.
    frases = re.split(r"[.!?;]+|\b(?:mas|porem)\b", texto)
    return any(_pedido_na_frase(frase) for frase in frases)
