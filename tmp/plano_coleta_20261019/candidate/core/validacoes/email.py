import re
import unicodedata
from dataclasses import dataclass


EVENTO_EMAIL_VALIDO = "email_valido"

CLASSIFICACAO_EMAIL_VALIDO = "email_valido"
CLASSIFICACAO_EMAIL_AUSENTE = "email_ausente"
CLASSIFICACAO_EMAIL_NAO_INFORMADO = "email_nao_informado"

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

EXPRESSOES_AUSENCIA_EMAIL = {
    "nao tenho",
    "nao tenho email",
    "nao tenho e mail",
    "nao tenho um email",
    "nao tenho um e mail",
    "nao possuo",
    "nao possuo email",
    "nao possuo e mail",
    "nao possuo um email",
    "nao possuo um e mail",
    "nao uso email",
    "nao uso e mail",
    "estou sem email",
    "estou sem e mail",
    "sem email",
    "sem e mail",
}


@dataclass(frozen=True)
class ResultadoValidacaoEmail:
    valido: bool
    email: str | None = None
    evento: str | None = None
    motivo: str | None = None


@dataclass(frozen=True)
class ResultadoColetaEmail:
    aceita: bool
    classificacao: str | None = None
    email: str | None = None
    evento: str | None = None
    motivo: str | None = None


def validar_email_estrutural(texto):
    """Extrai um único e-mail com a estrutura mínima aceita pelo fluxo."""
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


def classificar_resposta_email(texto, *, email_obrigatorio):
    """Classifica a resposta sem ultrapassar a política efetiva da etapa."""
    if not isinstance(email_obrigatorio, bool):
        raise ValueError(
            "email_obrigatorio deve ser booleano "
            f"(valor={email_obrigatorio!r})"
        )

    validacao = validar_email_estrutural(texto)

    if validacao.valido:
        return ResultadoColetaEmail(
            aceita=True,
            classificacao=CLASSIFICACAO_EMAIL_VALIDO,
            email=validacao.email,
            evento=validacao.evento,
        )

    if email_obrigatorio:
        return ResultadoColetaEmail(
            aceita=False,
            motivo=validacao.motivo,
        )

    return classificar_resposta_email_aceita(texto)


def classificar_resposta_email_aceita(texto):
    """Reconstrói o resultado de uma resposta que comprovadamente avançou."""
    validacao = validar_email_estrutural(texto)

    if validacao.valido:
        return ResultadoColetaEmail(
            aceita=True,
            classificacao=CLASSIFICACAO_EMAIL_VALIDO,
            email=validacao.email,
            evento=validacao.evento,
        )

    classificacao = (
        CLASSIFICACAO_EMAIL_AUSENTE
        if eh_ausencia_email_explicita(texto)
        else CLASSIFICACAO_EMAIL_NAO_INFORMADO
    )
    return ResultadoColetaEmail(
        aceita=True,
        classificacao=classificacao,
        email=None,
        evento=EVENTO_EMAIL_VALIDO,
        motivo=validacao.motivo,
    )


def calcular_email_obrigatorio_efetivo(
    email_obrigatorio_unidade,
    status_dependente,
    idade_cliente,
):
    """Aplica a exceção universal somente ao titular com 60 anos ou mais."""
    if not isinstance(email_obrigatorio_unidade, bool):
        raise ValueError("Configuração email_obrigatorio inválida")

    if not isinstance(status_dependente, bool):
        raise ValueError("Destino do atendimento não definido")

    if status_dependente:
        return email_obrigatorio_unidade

    if (
        isinstance(idade_cliente, bool)
        or not isinstance(idade_cliente, int)
        or idade_cliente < 18
        or idade_cliente >= 100
    ):
        # Em contexto legado sem as novas leituras, o fallback seguro mantém
        # a exigência antiga. Uma unidade opcional nunca pode avançar sem a
        # idade necessária para avaliar a exceção do titular.
        if email_obrigatorio_unidade and idade_cliente is None:
            return True

        raise ValueError(
            "Idade do titular inválida para calcular a política de e-mail "
            f"(idade={idade_cliente!r})"
        )

    return email_obrigatorio_unidade and idade_cliente < 60


def eh_ausencia_email_explicita(texto):
    return _normalizar_expressao(texto) in EXPRESSOES_AUSENCIA_EMAIL


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


def _normalizar_expressao(texto):
    decomposto = unicodedata.normalize("NFD", str(texto or "").casefold())
    sem_acentos = "".join(
        caractere
        for caractere in decomposto
        if unicodedata.category(caractere) != "Mn"
    )
    palavras = re.sub(r"[^a-z0-9]+", " ", sem_acentos)
    return " ".join(palavras.split())


def _resultado_invalido(motivo):
    return ResultadoValidacaoEmail(
        valido=False,
        motivo=motivo,
    )
