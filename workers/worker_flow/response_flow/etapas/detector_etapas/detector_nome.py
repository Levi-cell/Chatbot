import re
from dataclasses import dataclass

from workers.worker_flow.response_flow.etapas.detector_etapas.detector_financeiro import (
    normalizar_texto,
)


TIPO_TRATAMENTO_NOME_INVALIDO = "nome_invalido"

MOTIVO_VAZIO = "vazio"
MOTIVO_TIPO_INVALIDO = "tipo_invalido"
MOTIVO_SEM_LETRAS = "sem_letras"
MOTIVO_MULTIPLAS_PALAVRAS = "multiplas_palavras"
MOTIVO_COMPRIMENTO_INVALIDO = "comprimento_invalido"
MOTIVO_REPETICAO_CARACTERE = "repeticao_caractere"
MOTIVO_TERMO_PEJORATIVO = "termo_pejorativo"
MOTIVO_FORA_CONTEXTO = "fora_contexto"
MOTIVO_ESTRUTURA_IMPROVAVEL = "estrutura_improvavel"

TAMANHO_MINIMO_PRIMEIRO_NOME = 2
TAMANHO_MAXIMO_PRIMEIRO_NOME = 50

PADRAO_BLOCO_LETRAS = re.compile(r"[^\W\d_]+", re.UNICODE)
PADRAO_REPETICAO_CARACTERE = re.compile(
    r"([^\W\d_])\1{2,}",
    re.IGNORECASE,
)
PADRAO_VOGAL = re.compile(r"[aeiouy]", re.IGNORECASE)
PADRAO_CINCO_CONSOANTES = re.compile(
    r"[bcdfghjklmnpqrstvwxz]{5,}",
    re.IGNORECASE,
)
PADRAO_FRASE_COMPACTADA = re.compile(
    r"^(?:"
    r"eumechamo|"
    r"mechamo|"
    r"meunomee|"
    r"meunomeeh|"
    r"omeunomee|"
    r"omeunomeeh"
    r")[a-z]{2,}$",
    re.IGNORECASE,
)

# Somente termos inequívocos entram aqui. Palavras ambíguas permanecem aceitas
# para não bloquear nomes raros ou apelidos reais sem uma base externa.
PALAVRAS_FORA_CONTEXTO = {
    "agendamento",
    "agendar",
    "ajuda",
    "atendente",
    "atendimento",
    "aula",
    "boa",
    "boleto",
    "bom",
    "bot",
    "cancelar",
    "cartao",
    "celular",
    "chatbot",
    "coisa",
    "comecar",
    "como",
    "computador",
    "continuar",
    "conversar",
    "curso",
    "custo",
    "depois",
    "dia",
    "dinheiro",
    "documento",
    "email",
    "endereco",
    "fim",
    "foto",
    "falar",
    "gratis",
    "gratuito",
    "hoje",
    "horario",
    "humano",
    "informacao",
    "iniciar",
    "internet",
    "link",
    "mensagem",
    "meu",
    "minha",
    "nao",
    "noite",
    "nome",
    "obrigada",
    "obrigado",
    "oi",
    "ola",
    "parar",
    "pessoa",
    "pix",
    "porque",
    "preco",
    "qual",
    "quanto",
    "saber",
    "sair",
    "sim",
    "site",
    "sou",
    "supera",
    "sistema",
    "tarde",
    "telefone",
    "teste",
    "testando",
    "texto",
    "valor",
    "video",
    "voce",
    "voces",
    "voltar",
    "whatsapp",
}

PALAVRAS_NOME_PEJORATIVAS = {
    "abestalhada",
    "abestalhado",
    "arrombada",
    "arrombado",
    "babaca",
    "babacas",
    "baitola",
    "besta",
    "bestalhao",
    "biscate",
    "boceta",
    "boiola",
    "bosta",
    "buceta",
    "burra",
    "burro",
    "carai",
    "caralho",
    "canalha",
    "cretina",
    "cretino",
    "cu",
    "cuzinho",
    "debil",
    "desgracada",
    "desgracado",
    "doente",
    "egua",
    "escrota",
    "escroto",
    "estupida",
    "estupido",
    "fdp",
    "filhaodaputa",
    "filhodaputa",
    "foda",
    "fodase",
    "fudida",
    "fudido",
    "gozada",
    "gozado",
    "idiota",
    "idiotas",
    "imbecil",
    "imbecis",
    "inutil",
    "kenga",
    "lazarenta",
    "lazarento",
    "lerda",
    "lerdo",
    "lixo",
    "maldita",
    "maldito",
    "merda",
    "merdinha",
    "meretriz",
    "miseravel",
    "nojenta",
    "nojento",
    "otaria",
    "otario",
    "palhaca",
    "palhaco",
    "panaca",
    "pateta",
    "pau",
    "penis",
    "piranha",
    "piroca",
    "podre",
    "pomba",
    "porra",
    "prostituta",
    "puta",
    "putao",
    "putassa",
    "putaria",
    "puteiro",
    "putinha",
    "puto",
    "rapariga",
    "retardada",
    "retardado",
    "ridicula",
    "ridiculo",
    "rola",
    "sacanagem",
    "safada",
    "safado",
    "siririca",
    "tapada",
    "tapado",
    "tarada",
    "tarado",
    "tesao",
    "tonta",
    "tonto",
    "traste",
    "vaca",
    "vagabunda",
    "vagabundo",
    "vadia",
    "viado",
    "xana",
    "xavasca",
    "xereca",
    "xibiu",
    "xota",
}

# Estas raízes são longas e inequívocas o suficiente para bloquear flexões e
# tentativas como "putinhaa", "vagabundinha" e "PutaMaria". Termos curtos como
# "pau" e "cu" ficam apenas na comparação exata para não bloquear Paulo e Cunha.
RAIZES_PEJORATIVAS_FORTES = (
    "arrombad",
    "bocet",
    "bucet",
    "caralh",
    "escrot",
    "estupid",
    "filhaodaputa",
    "filhodaputa",
    "fudid",
    "idiot",
    "imbecil",
    "merd",
    "meretriz",
    "piranha",
    "piroc",
    "prostitut",
    "puta",
    "putinh",
    "retardad",
    "vagabund",
    "xerec",
)


@dataclass(frozen=True)
class ResultadoValidacaoNome:
    valido: bool
    primeiro_nome: str | None = None
    motivo: str | None = None


def validar_nome_cliente(texto):
    if not isinstance(texto, str):
        return ResultadoValidacaoNome(False, motivo=MOTIVO_TIPO_INVALIDO)

    texto_normalizado = normalizar_texto(texto).strip()

    if not texto_normalizado:
        return ResultadoValidacaoNome(False, motivo=MOTIVO_VAZIO)

    palavras = _extrair_blocos_de_letras(texto_normalizado)

    if not palavras:
        return ResultadoValidacaoNome(False, motivo=MOTIVO_SEM_LETRAS)

    if _tem_palavra_pejorativa(palavras):
        return ResultadoValidacaoNome(False, motivo=MOTIVO_TERMO_PEJORATIVO)

    if len(palavras) != 1:
        return ResultadoValidacaoNome(False, motivo=MOTIVO_MULTIPLAS_PALAVRAS)

    primeiro_nome = palavras[0]

    if not _comprimento_valido(primeiro_nome):
        return ResultadoValidacaoNome(
            False,
            motivo=MOTIVO_COMPRIMENTO_INVALIDO,
        )

    if _tem_tres_letras_repetidas(primeiro_nome):
        return ResultadoValidacaoNome(False, motivo=MOTIVO_REPETICAO_CARACTERE)

    if primeiro_nome in PALAVRAS_FORA_CONTEXTO:
        return ResultadoValidacaoNome(False, motivo=MOTIVO_FORA_CONTEXTO)

    if PADRAO_FRASE_COMPACTADA.fullmatch(primeiro_nome):
        return ResultadoValidacaoNome(False, motivo=MOTIVO_FORA_CONTEXTO)

    if _tem_estrutura_improvavel(primeiro_nome):
        return ResultadoValidacaoNome(
            False,
            motivo=MOTIVO_ESTRUTURA_IMPROVAVEL,
        )

    return ResultadoValidacaoNome(
        True,
        primeiro_nome=_formatar_primeiro_nome(primeiro_nome),
    )


def detecta_nome_invalido(texto):
    return not validar_nome_cliente(texto).valido


def extrair_primeiro_nome_cliente(texto):
    return validar_nome_cliente(texto).primeiro_nome


def _extrair_blocos_de_letras(texto):
    return PADRAO_BLOCO_LETRAS.findall(texto)


def _comprimento_valido(texto):
    return TAMANHO_MINIMO_PRIMEIRO_NOME <= len(
        texto
    ) <= TAMANHO_MAXIMO_PRIMEIRO_NOME


def _tem_tres_letras_repetidas(texto):
    return bool(PADRAO_REPETICAO_CARACTERE.search(texto))


def _tem_palavra_pejorativa(palavras):
    if any(_palavra_e_pejorativa(palavra) for palavra in palavras):
        return True

    # Também reconhece tentativas como "p.u.t.a" e "p#u#t#a", sem usar essa
    # compactação para aceitar nomes ou frases.
    return _palavra_e_pejorativa("".join(palavras))


def _palavra_e_pejorativa(palavra):
    palavra_normalizada = palavra.lower()

    if palavra_normalizada in PALAVRAS_NOME_PEJORATIVAS:
        return True

    return any(
        palavra_normalizada.startswith(raiz)
        or palavra_normalizada.endswith(raiz)
        for raiz in RAIZES_PEJORATIVAS_FORTES
    )


def _tem_estrutura_improvavel(texto):
    if not PADRAO_VOGAL.search(texto):
        return True

    return bool(PADRAO_CINCO_CONSOANTES.search(texto))


def _formatar_primeiro_nome(token):
    return token[:1].upper() + token[1:].lower()
