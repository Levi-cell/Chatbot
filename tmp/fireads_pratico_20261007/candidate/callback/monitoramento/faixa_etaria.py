"""Contagens por participante, sem confundir contatos, conversas e dependentes."""

from collections import Counter
import re


PUBLICOS = ('titulares', 'dependentes', 'todos')


def validar_consulta_faixa_etaria(parametros):
    """Recusa escolhas múltiplas inclusive quando a URL é montada manualmente."""
    if any(len(parametros.getlist(campo)) != 1 for campo in ('idade_minima', 'publico')):
        raise ValueError('Informe uma idade mínima e selecione apenas um público.')
    idade = parametros.get('idade_minima', '').strip()
    if not re.fullmatch(r'[0-9]{1,3}', idade) or int(idade) < 1:
        raise ValueError('Informe uma idade inteira entre 1 e 999 anos.')
    publico = parametros.get('publico')
    if publico not in PUBLICOS:
        raise ValueError('Selecione apenas titulares, apenas dependentes ou todos.')
    return int(idade), publico


def _idade_informada(idade):
    return type(idade) is int and idade > 0


def _participantes(linhas):
    """Titular único; dependentes por cadastro, conforme o contrato do relatório.

    Recebe somente conversas da unidade com contato no período. O sinal de
    funil já está limitado a envios confirmados no mesmo período e conversa.
    Não transfere o envio entre o titular e seus dependentes.
    """
    participantes = {}
    for linha in linhas:
        rota = linha.get('status_dependente')
        if type(rota) is not bool:
            continue
        id_cliente = linha['id_cliente']
        if rota:
            id_dependente = linha.get('id_dependente')
            idade = linha.get('idade_dependente')
            nome = str(linha.get('nome_dependente') or '').strip()
            # A escolha da rota cria um placeholder; ainda não é um dependente identificado.
            if id_dependente is None or (not nome and not _idade_informada(idade)):
                continue
            chave = ('dependentes', id_cliente, id_dependente)
        else:
            idade = linha.get('idade_titular')
            chave = ('titulares', id_cliente)
        participante = participantes.setdefault(chave, {
            'publico': chave[0], 'id_cliente': id_cliente,
            'idade': idade, 'foi_funil': False,
        })
        participante['foi_funil'] |= bool(linha.get('foi_funil'))
    return list(participantes.values())


def consultar_faixa_etaria(linhas, idade_minima, publico):
    grupos = {
        'titulares': {'leads': 0, 'funil': 0},
        'dependentes': {'leads': 0, 'funil': 0},
    }
    contatos = set()
    for participante in _participantes(linhas):
        if publico != 'todos' and participante['publico'] != publico:
            continue
        idade = participante['idade']
        if not _idade_informada(idade) or idade < idade_minima:
            continue
        grupo = grupos[participante['publico']]
        grupo['leads'] += 1
        grupo['funil'] += int(participante['foi_funil'])
        contatos.add(participante['id_cliente'])
    return {
        'idade_minima': idade_minima, 'publico': publico,
        'total': sum(grupo['leads'] for grupo in grupos.values()),
        'contatos': len(contatos), **grupos,
    }


def distribuir_dependentes_por_titular(linhas):
    por_titular = Counter(
        participante['id_cliente'] for participante in _participantes(linhas)
        if participante['publico'] == 'dependentes'
    )
    distribuicao = Counter(por_titular.values())
    return {
        'titulares': len(por_titular),
        'dependentes': sum(por_titular.values()),
        'grupos': [
            {'dependentes_por_titular': quantidade, 'titulares': titulares}
            for quantidade, titulares in sorted(distribuicao.items())
        ],
    }
