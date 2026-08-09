import re
import unicodedata
from dataclasses import dataclass


TAMANHO_MAXIMO_PROFISSAO = 100

MOTIVO_PROFISSAO_AUSENTE = "profissao_ausente"
MOTIVO_PROFISSAO_LONGA = "profissao_acima_limite"
MOTIVO_PROFISSAO_SEM_TEXTO = "profissao_sem_texto"
MOTIVO_PROFISSAO_TIPO_INVALIDO = "profissao_tipo_mensagem_invalido"
MOTIVO_PROFISSAO_GENERICA = "profissao_generica"
MOTIVO_RECUSA_EXPLICITA = "recusa_explicita"

_RESPOSTAS_GENERICAS = {
    "aham",
    "beleza",
    "blz",
    "boa",
    "bom",
    "certo",
    "entendi",
    "isso",
    "isso mesmo",
    "nao",
    "negativo",
    "oi",
    "ok",
    "okay",
    "ola",
    "positivo",
    "show",
    "sim",
    "ta",
    "talvez",
    "tudo bem",
}

_RECUSAS_EXPLICITAS = {
    "assunto pessoal",
    "nao gosto de falar",
    "nao interessa",
    "nao quero dizer",
    "nao quero falar",
    "nao quero informar",
    "nao quero responder",
    "nao sei",
    "nao vou dizer",
    "nao vou falar",
    "nao vou informar",
    "nao vou responder",
    "prefiro nao dizer",
    "prefiro nao falar",
    "prefiro nao informar",
    "prefiro nao responder",
    "segredo",
}


@dataclass(frozen=True)
class ResultadoValidacaoProfissao:
    valida: bool
    profissao: str | None = None
    motivo: str | None = None


def validar_profissao_etapa4(conteudo_texto, tipo_mensagem="text"):
    if tipo_mensagem != "text":
        return _resultado_invalido(MOTIVO_PROFISSAO_TIPO_INVALIDO)

    if not isinstance(conteudo_texto, str):
        return _resultado_invalido(MOTIVO_PROFISSAO_AUSENTE)

    conteudo_sem_bordas = conteudo_texto.strip()

    if not conteudo_sem_bordas:
        return _resultado_invalido(MOTIVO_PROFISSAO_AUSENTE)

    if len(conteudo_sem_bordas) > TAMANHO_MAXIMO_PROFISSAO:
        return _resultado_invalido(MOTIVO_PROFISSAO_LONGA)

    profissao = " ".join(conteudo_sem_bordas.split())

    if not any(caractere.isalpha() for caractere in profissao):
        return _resultado_invalido(MOTIVO_PROFISSAO_SEM_TEXTO)

    texto_normalizado = _normalizar_texto(profissao)

    if texto_normalizado in _RESPOSTAS_GENERICAS:
        return _resultado_invalido(MOTIVO_PROFISSAO_GENERICA)

    if texto_normalizado in _RECUSAS_EXPLICITAS:
        return _resultado_invalido(MOTIVO_RECUSA_EXPLICITA)

    return ResultadoValidacaoProfissao(
        valida=True,
        profissao=profissao,
    )


def _normalizar_texto(texto):
    texto_decomposto = unicodedata.normalize("NFD", texto.casefold())
    texto_sem_acentos = "".join(
        caractere
        for caractere in texto_decomposto
        if unicodedata.category(caractere) != "Mn"
    )
    texto_sem_simbolos = re.sub(
        r"[^\w\s]",
        " ",
        texto_sem_acentos,
        flags=re.UNICODE,
    ).replace("_", " ")
    return " ".join(texto_sem_simbolos.split())


def _resultado_invalido(motivo):
    return ResultadoValidacaoProfissao(
        valida=False,
        motivo=motivo,
    )
