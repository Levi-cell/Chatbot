import re
from dataclasses import dataclass

from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_EMAIL_VALIDO,
)


TIPO_TRATAMENTO_EMAIL_INVALIDO = "email_invalido"

MOTIVO_EMAIL_AUSENTE = "email_ausente"
MOTIVO_MULTIPLOS_EMAILS = "multiplos_emails"
MOTIVO_FORMATO_INVALIDO = "formato_invalido"
MOTIVO_DOMINIO_INVALIDO = "dominio_invalido"

PONTUACAO_FINAL_FRASE = ".,;:!?)]}>\"'”’"
PONTUACAO_INICIAL_FRASE = "([<{\"'“‘"

PADRAO_CANDIDATO_EMAIL = re.compile(
    r"[^\s@]+@[^\s@]+",
    re.UNICODE,
)


@dataclass(frozen=True)
class ResultadoValidacaoEmail:
    valido: bool
    email: str | None = None
    evento: str | None = None
    motivo: str | None = None


def validar_etapa9(texto):
    """
    Extrai um único email usando somente a estrutura mínima da etapa 9.

    O candidato precisa ter conteúdo antes do @ e um ponto no domínio, com
    conteúdo dos dois lados. Provedor, TLD e existência não são verificados.
    """
    texto_original = str(texto or "").strip()

    if not texto_original:
        return _resultado_invalido(MOTIVO_EMAIL_AUSENTE)

    quantidade_arrobas = texto_original.count("@")

    if quantidade_arrobas == 0:
        return _resultado_invalido(MOTIVO_EMAIL_AUSENTE)

    if quantidade_arrobas != 1:
        return _resultado_invalido(MOTIVO_MULTIPLOS_EMAILS)

    candidatos = _extrair_candidatos(texto_original)

    if not candidatos:
        return _resultado_invalido(MOTIVO_EMAIL_AUSENTE)

    if len(candidatos) != 1:
        return _resultado_invalido(MOTIVO_MULTIPLOS_EMAILS)

    email = _normalizar_email(candidatos[0])
    motivo_invalido = _validar_estrutura_email(email)

    if motivo_invalido:
        return _resultado_invalido(motivo_invalido)

    return ResultadoValidacaoEmail(
        valido=True,
        email=email,
        evento=EVENTO_EMAIL_VALIDO,
    )


def _extrair_candidatos(texto):
    candidatos = []

    for correspondencia in PADRAO_CANDIDATO_EMAIL.finditer(texto):
        candidato = correspondencia.group(0)
        candidato = candidato.lstrip(PONTUACAO_INICIAL_FRASE)
        candidato = candidato.rstrip(PONTUACAO_FINAL_FRASE)

        if candidato:
            candidatos.append(candidato)

    return candidatos


def _normalizar_email(email):
    parte_local, separador, dominio = email.rpartition("@")

    if not separador:
        return email

    return f"{parte_local}@{dominio.lower()}"


def _validar_estrutura_email(email):
    parte_local, separador, dominio = email.rpartition("@")

    if not separador or not parte_local or not dominio:
        return MOTIVO_FORMATO_INVALIDO

    dominio_base, ponto, terminacao = dominio.rpartition(".")

    if not ponto or not dominio_base or not terminacao:
        return MOTIVO_DOMINIO_INVALIDO

    return None


def _resultado_invalido(motivo):
    return ResultadoValidacaoEmail(
        valido=False,
        motivo=motivo,
    )
