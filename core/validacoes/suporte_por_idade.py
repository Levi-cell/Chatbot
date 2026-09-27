"""Domínio puro da configuração de encaminhamento por idade da unidade."""

IDADES_MINIMAS_SUPORTE = (50, 60, 70, 80)


def validar_idade_minima_suporte(valor):
    """None desativa; booleanos e números fora do domínio são erros."""
    if valor is not None and (
        type(valor) is not int or valor not in IDADES_MINIMAS_SUPORTE
    ):
        raise ValueError(f"Idade mínima de suporte inválida: {valor!r}")
    return valor
