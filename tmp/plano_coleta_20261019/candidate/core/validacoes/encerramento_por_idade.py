"""Catálogo dos encerramentos por idade, sem consultas ou efeitos externos."""

from core.validacoes.suporte_por_idade import validar_idade_minima_suporte


IDADE_UNIVERSAL = 90
MOTIVO_TITULAR_MENOR = 'titular_menor_18'
MOTIVO_UNIVERSAL = 'idade_universal_90'
MOTIVO_SUPORTE_LEGADO = 'encaminhado_suporte_idoso'
MOTIVO_IDADE_LEGADO = 'idade_invalida'
MOTIVOS_SUPORTE = {idade: f'suporte_idoso_{idade}' for idade in (50, 60, 70, 80)}
MOTIVOS_DEPENDENTE = {idade: f'dependente_menor_{idade}' for idade in (4, 5)}

ROTULOS_MOTIVOS = {
    MOTIVO_TITULAR_MENOR: 'Titular menor de 18 anos',
    **{motivo: f'Dependente abaixo de {idade} anos'
       for idade, motivo in MOTIVOS_DEPENDENTE.items()},
    **{motivo: f'Titular encaminhado por suporte {idade}+'
       for idade, motivo in MOTIVOS_SUPORTE.items()},
    MOTIVO_UNIVERSAL: 'Encaminhamento universal: 90 anos ou mais',
    MOTIVO_SUPORTE_LEGADO: 'Suporte por idade: limite histórico não registrado',
    MOTIVO_IDADE_LEGADO: 'Restrição de idade: registro legado',
}
MOTIVOS_IDADE = frozenset(ROTULOS_MOTIVOS)


def motivo_suporte(idade_minima):
    """Converte o limite aplicado em código persistente; None não encaminha."""
    validar_idade_minima_suporte(idade_minima)
    if idade_minima not in MOTIVOS_SUPORTE:
        raise ValueError('Encerramento de suporte sem limite habilitado')
    return MOTIVOS_SUPORTE[idade_minima]


def motivo_dependente(idade_minima):
    if type(idade_minima) is not int or idade_minima not in MOTIVOS_DEPENDENTE:
        raise ValueError('Mínimo de dependente deve ser 4 ou 5 anos')
    return MOTIVOS_DEPENDENTE[idade_minima]


def reconstruir_limite_suporte(idade_informada, limite_atual):
    """Faixa compatível apenas para retry com encaminhamento já comprovado.

    Não descobre a configuração antiga. O chamador comprova o envio antes de
    chamar; a idade vem da entrada vinculada ao retry, nunca de cliente.idade.
    O legado 90–99 permanece genérico para não virar a nova regra universal.
    """
    validar_idade_minima_suporte(limite_atual)
    if type(idade_informada) is not int or not 50 <= idade_informada < IDADE_UNIVERSAL:
        return None
    if limite_atual is not None and idade_informada >= limite_atual:
        return limite_atual
    return max(limite for limite in MOTIVOS_SUPORTE if limite <= idade_informada)


def descrever_motivo_idade(motivo):
    """Metadados estáveis do motivo salvo; não lê a configuração da unidade."""
    if motivo not in MOTIVOS_IDADE:
        return None
    descricao = ROTULOS_MOTIVOS[motivo]
    if motivo in MOTIVOS_SUPORTE.values():
        limite = next(idade for idade, codigo in MOTIVOS_SUPORTE.items() if codigo == motivo)
        return {'tag': f'{limite}+', 'descricao': descricao, 'contato_enviado': True}
    if motivo in MOTIVOS_DEPENDENTE.values():
        return {'tag': 'Limite mínimo', 'descricao': descricao, 'contato_enviado': False}
    if motivo == MOTIVO_TITULAR_MENOR:
        return {'tag': 'Menor', 'descricao': descricao, 'contato_enviado': False}
    if motivo == MOTIVO_UNIVERSAL:
        return {'tag': '90+', 'descricao': descricao, 'contato_enviado': True}
    if motivo == MOTIVO_SUPORTE_LEGADO:
        return {'tag': 'Suporte por idade', 'descricao': descricao, 'contato_enviado': True}
    return {'tag': 'Restrição de idade', 'descricao': descricao, 'contato_enviado': None}
