"""Transformações puras dos dados do painel, sem acesso ao banco."""

import re

from core.integrations.whatsapp.messages.etapa2_messages import montar_botoes_etapa2
from core.integrations.whatsapp.messages.etapa3_messages import montar_botoes_etapa3
from core.integrations.whatsapp.messages.etapa7_messages import montar_botoes_etapa7
from core.integrations.whatsapp.messages.etapa9_messages import montar_botoes_etapa9
from core.integrations.whatsapp.messages.etapa11_messages import montar_botoes_etapa11
from core.integrations.whatsapp.messages.etapa18_messages import montar_botoes_etapa18
from core.integrations.whatsapp.messages.etapa19_messages import montar_opcoes_satisfacao_etapa19
from core.integrations.whatsapp.messages.etapa20_messages import montar_botoes_etapa20
from core.integrations.whatsapp.messages.triagem_componentes import montar_botoes_triagem


_BOTOES_POR_ETAPA = {
    2: montar_botoes_etapa2,
    3: montar_botoes_etapa3,
    7: montar_botoes_etapa7,
    9: montar_botoes_etapa9,
    11: montar_botoes_etapa11,
    12: montar_botoes_triagem,
    13: montar_botoes_triagem,
    14: montar_botoes_triagem,
    15: montar_botoes_triagem,
    16: montar_botoes_triagem,
    17: montar_botoes_triagem,
    18: montar_botoes_etapa18,
    19: lambda: [titulo for _, titulo in montar_opcoes_satisfacao_etapa19()],
    20: montar_botoes_etapa20,
}


def botoes_para_mensagem(mensagem):
    tipo = str(mensagem.get('tipo') or '')
    if mensagem.get('quem_enviou') != 'bot' or not tipo.startswith('interactive'):
        return []
    fabrica = _BOTOES_POR_ETAPA.get(mensagem.get('id_etapa'))
    return list(fabrica()) if fabrica else []


def classificar_faixa(idade):
    if type(idade) is not int or idade <= 0 or idade >= 100:
        return None
    if idade < 18:
        return 'menor'
    if idade < 60:
        return 'adulto'
    return 'idoso'


def consolidar_conversas(linhas):
    clientes = {}
    for linha in linhas:
        cliente = clientes.setdefault(linha['id_cliente'], {
            'id_cliente': linha['id_cliente'],
            'nome': linha.get('nome_cliente') or 'Cliente sem nome',
            'contato': linha.get('waid_telefone') or '',
            'email': linha.get('email') or '',
            'profissao': linha.get('profissao_cliente') or linha.get('profissao_conversa') or '',
            'ids_conversa': [], 'perfis': set(), 'dependentes': set(),
            'foi_funil': False, 'avaliada': False,
            'ultima_atividade': None, 'ultima_mensagem': '',
            'ultima_mensagem_id': None,
        })
        cliente['ids_conversa'].append(linha['id_conversa'])
        cliente['foi_funil'] |= bool(linha.get('foi_funil'))
        cliente['avaliada'] |= bool(linha.get('avaliada'))
        status_dependente = linha.get('status_dependente')
        dependente = status_dependente is True
        if dependente:
            cliente['perfis'].add('dependente')
            if linha.get('nome_dependente'):
                cliente['dependentes'].add(str(linha['nome_dependente']))
        idade = (
            linha.get('idade_dependente') if dependente
            else linha.get('idade_titular') if status_dependente is False
            else None
        )
        faixa = classificar_faixa(idade)
        if faixa:
            cliente['perfis'].add(faixa)
        atividade = linha.get('ultima_atividade')
        id_mensagem = linha.get('ultima_mensagem_id') or 0
        if atividade and (
            cliente['ultima_atividade'] is None
            or atividade > cliente['ultima_atividade']
            or (
                atividade == cliente['ultima_atividade']
                and id_mensagem > (cliente['ultima_mensagem_id'] or 0)
            )
        ):
            cliente['ultima_atividade'] = atividade
            cliente['ultima_mensagem'] = linha.get('ultima_mensagem') or ''
            cliente['ultima_mensagem_id'] = linha.get('ultima_mensagem_id')
    ordem = {'dependente': 0, 'menor': 1, 'adulto': 2, 'idoso': 3}
    for cliente in clientes.values():
        cliente['ids_conversa'].sort()
        cliente['perfis'] = sorted(cliente['perfis'], key=lambda item: ordem[item])
        cliente['dependentes'] = sorted(cliente['dependentes'])
    return sorted(clientes.values(), key=lambda item: item['ultima_atividade'] or '', reverse=True)


def normalizar_telefone_google(valor):
    digitos = re.sub(r'\D', '', str(valor or ''))
    if len(digitos) in (10, 11):
        digitos = '55' + digitos
    if not re.fullmatch(r'[1-9]\d{7,14}', digitos):
        return ''
    return '+' + digitos


def separar_nome(valor):
    partes = str(valor or '').strip().split()
    if not partes:
        return '', ''
    return partes[0], ' '.join(partes[1:])


def proteger_celula_csv(valor):
    texto = str(valor or '')
    return "'" + texto if texto.startswith(('=', '+', '-', '@')) else texto


def montar_relatorio(metricas, anteriores, perfis, satisfacao, etapas, atividade):
    def variacao(atual, anterior):
        if atual is None or anterior is None:
            return None
        if anterior == 0:
            return 100.0 if atual else 0.0
        return round((atual - anterior) / anterior * 100, 1)
    tendencias = {}
    for chave in ('leads', 'mensagens', 'funil', 'avaliacoes', 'nota_media'):
        tendencias[chave] = variacao(metricas.get(chave, 0), anteriores.get(chave) if anteriores else None)
    return {
        'metricas': metricas,
        'tendencias': tendencias,
        'perfis': perfis,
        'satisfacao': satisfacao,
        'etapas': etapas,
        'atividade': atividade,
    }
