"""Apresentação dos motivos históricos e da tabela da configuração atual."""

from core.integrations.whatsapp.messages.etapa6_messages import reconhecer_encerramento_etapa6
from core.validacoes.encerramento_por_idade import (
    MOTIVO_IDADE_LEGADO,
    MOTIVO_SUPORTE_LEGADO,
    MOTIVO_TITULAR_MENOR,
    MOTIVO_UNIVERSAL,
    descrever_motivo_idade,
    motivo_dependente,
    motivo_suporte,
)
from core.validacoes.suporte_por_idade import validar_idade_minima_suporte


def apresentar_encerramento(linha):
    """O motivo salvo prevalece; textos conhecidos só esclarecem motivos legados."""
    motivo = linha['motivo_encerramento']
    informacao = descrever_motivo_idade(motivo)
    if informacao is None:
        return None
    reconhecida = reconhecer_encerramento_etapa6(linha['resposta_bot'], linha['tipo_bot'])
    if motivo == MOTIVO_IDADE_LEGADO:
        if not reconhecida or reconhecida['categoria'] == 'suporte':
            return None
        categoria = reconhecida['categoria']
        if categoria == 'titular_menor':
            informacao = descrever_motivo_idade(MOTIVO_TITULAR_MENOR)
        elif categoria == 'dependente_menor':
            informacao = descrever_motivo_idade(motivo_dependente(reconhecida['idade_minima']))
        else:
            informacao = {
                'tag': 'Idade avançada',
                'descricao': 'Encaminhamento universal anterior à identificação do limite no registro.',
                'contato_enviado': True,
            }
    elif motivo == MOTIVO_SUPORTE_LEGADO:
        # O registro prova suporte, mas não permite atribuir uma faixa histórica.
        informacao['descricao'] += ' Limite histórico não registrado.'
    return {
        **informacao,
        'id_conversa': linha['id_conversa'],
        'motivo': motivo,
        'participante': 'Dependente' if linha['status_dependente'] else 'Titular',
        'resposta_idade': linha.get('resposta_idade') or 'Não registrada',
        'nome_dependente': (reconhecida or {}).get('nome_dependente'),
    }


def montar_tabela_encerramentos(contagens, *, idade_minima_suporte, bpa_ativo):
    """Configuração atual filtra o relatório, sem alterar as tags dos chats.

    Registros genéricos não provam o limite aplicado e não entram nesta tabela.
    A mesma opção selecionada novamente inclui todos os motivos iguais no período.
    """
    suporte = validar_idade_minima_suporte(idade_minima_suporte)
    minimo = 4 if bpa_ativo else 5
    for item in contagens:
        if type(item['conversas']) is not int or item['conversas'] < 0:
            raise ValueError('Quantidade de conversas inválida')
    totais = {
        (item['motivo_encerramento'], bool(item['status_dependente'])): int(item['conversas'])
        for item in contagens if item['status_dependente'] is not None
    }
    linhas = []

    def adicionar(motivo, dependente, rotulo, encaminhado):
        linhas.append({
            'motivo': motivo,
            'rotulo': rotulo,
            'contato_enviado': encaminhado,
            'destino': 'Contato comercial enviado' if encaminhado else 'Encerrado sem encaminhamento',
            'conversas': totais.get((motivo, dependente), 0),
        })

    if suporte is not None:
        adicionar(motivo_suporte(suporte), False, f'Titulares · suporte {suporte}+ (até 89 anos)', True)
    adicionar(MOTIVO_UNIVERSAL, False, 'Titulares · 90+ (regra universal)', True)
    adicionar(MOTIVO_UNIVERSAL, True, 'Dependentes · 90+ (regra universal)', True)
    adicionar(MOTIVO_TITULAR_MENOR, False, 'Titulares · menos de 18 anos', False)
    adicionar(motivo_dependente(minimo), True, f'Dependentes · menos de {minimo} anos', False)
    return {
        'linhas': linhas,
        'total_encaminhadas': sum(l['conversas'] for l in linhas if l['contato_enviado']),
        'total_sem_encaminhamento': sum(l['conversas'] for l in linhas if not l['contato_enviado']),
        'idade_minima_suporte': suporte,
        'idade_minima_dependente': minimo,
    }
