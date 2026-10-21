"""Validação e classificação da resposta de e-mail na etapa 10."""

from core.validacoes.email import (
    CLASSIFICACAO_EMAIL_AUSENTE,
    CLASSIFICACAO_EMAIL_NAO_INFORMADO,
    CLASSIFICACAO_EMAIL_VALIDO,
    MOTIVO_DOMINIO_INVALIDO,
    MOTIVO_EMAIL_AUSENTE,
    MOTIVO_FORMATO_INVALIDO,
    MOTIVO_MULTIPLOS_EMAILS,
    ResultadoColetaEmail,
    ResultadoValidacaoEmail,
    calcular_email_obrigatorio_efetivo,
    classificar_resposta_email,
    classificar_resposta_email_aceita,
    eh_ausencia_email_explicita,
    validar_email_estrutural,
)


TIPO_TRATAMENTO_EMAIL_INVALIDO = "email_invalido"


def validar_etapa10(texto):
    """Preserva o contrato histórico da validação estrutural da etapa 10."""
    return validar_email_estrutural(texto)


__all__ = [
    "CLASSIFICACAO_EMAIL_AUSENTE",
    "CLASSIFICACAO_EMAIL_NAO_INFORMADO",
    "CLASSIFICACAO_EMAIL_VALIDO",
    "MOTIVO_DOMINIO_INVALIDO",
    "MOTIVO_EMAIL_AUSENTE",
    "MOTIVO_FORMATO_INVALIDO",
    "MOTIVO_MULTIPLOS_EMAILS",
    "ResultadoColetaEmail",
    "ResultadoValidacaoEmail",
    "TIPO_TRATAMENTO_EMAIL_INVALIDO",
    "calcular_email_obrigatorio_efetivo",
    "classificar_resposta_email",
    "classificar_resposta_email_aceita",
    "eh_ausencia_email_explicita",
    "validar_etapa10",
]
