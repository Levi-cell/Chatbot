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


# Ordem e grafia do modelo CSV distribuído pelo Google Contacts.
CABECALHO_CSV_GOOGLE_CONTATOS = (
    'Name Prefix',
    'First Name',
    'Middle Name',
    'Last Name',
    'Name Suffix',
    'Phonetic First Name',
    'Phonetic Middle Name',
    'Phonetic Last Name',
    'Nickname',
    'File As',
    'E-mail 1 - Label',
    'E-mail 1 - Value',
    'Phone 1 - Label',
    'Phone 1 - Value',
    'Address 1 - Label',
    'Address 1 - Country',
    'Address 1 - Street',
    'Address 1 - Extended Address',
    'Address 1 - City',
    'Address 1 - Region',
    'Address 1 - Postal Code',
    'Address 1 - PO Box',
    'Organization Name',
    'Organization Title',
    'Organization Department',
    'Birthday',
    'Event 1 - Label',
    'Event 1 - Value',
    'Relation 1 - Label',
    'Relation 1 - Value',
    'Website 1 - Label',
    'Website 1 - Value',
    'Custom Field 1 - Label',
    'Custom Field 1 - Value',
    'Notes',
    'Labels',
)


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


def _perfil_resumido(status_dependente, faixa):
    if status_dependente is True:
        return f'dependente_{faixa}' if faixa else 'dependente'
    if status_dependente is False:
        return faixa
    return None


def consolidar_conversas(linhas):
    clientes = {}
    for linha in linhas:
        cliente = clientes.setdefault(linha['id_cliente'], {
            'id_cliente': linha['id_cliente'],
            'nome': linha.get('nome_cliente') or 'Cliente sem nome',
            'contato': linha.get('waid_telefone') or '',
            'email': linha.get('email') or '',
            'profissao': linha.get('profissao_cliente') or linha.get('profissao_conversa') or '',
            'ids_conversa': [], 'perfis': set(), 'perfis_resumidos': set(),
            'dependentes': set(),
            'foi_funil': False, 'avaliada': False, 'followup_stage': 0,
            'ultima_atividade': None, 'ultima_mensagem': '',
            'ultima_mensagem_id': None,
        })
        cliente['ids_conversa'].append(linha['id_conversa'])
        cliente['foi_funil'] |= bool(linha.get('foi_funil'))
        cliente['avaliada'] |= bool(linha.get('avaliada'))
        # A consulta já exclui o follow-up de atendimentos substituídos por outro.
        cliente['followup_stage'] = max(
            cliente['followup_stage'], linha.get('followup_stage_atual') or 0,
        )
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
        perfil_resumido = _perfil_resumido(status_dependente, faixa)
        if perfil_resumido:
            cliente['perfis_resumidos'].add(perfil_resumido)
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
    ordem_resumida = {
        'dependente_menor': 0,
        'dependente_adulto': 1,
        'dependente_idoso': 2,
        'menor': 3,
        'adulto': 4,
        'idoso': 5,
        'dependente': 6,
    }
    for cliente in clientes.values():
        cliente['ids_conversa'].sort()
        cliente['perfis'] = sorted(cliente['perfis'], key=lambda item: ordem[item])
        cliente['perfis_resumidos'] = sorted(
            cliente['perfis_resumidos'], key=lambda item: ordem_resumida[item]
        )
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


CABECALHO_CSV_ESSENCIAL = ('Nome', 'E-mail', 'Telefone')


def montar_linha_csv_essencial(*, primeiro_nome, sobrenome, email, telefone):
    """Mantém o nome completo em uma coluna, sem acrescentar rótulos comerciais."""
    nome = ' '.join(parte for parte in (primeiro_nome, sobrenome) if parte)
    # O telefone já está normalizado; remove só o código do Brasil, mantendo o DDD.
    telefone_essencial = telefone.removeprefix('+55')
    return [proteger_celula_csv(nome), proteger_celula_csv(email), telefone_essencial]


def montar_linha_csv_google_contatos(
    *,
    primeiro_nome,
    sobrenome,
    email,
    telefone,
    nome_unidade,
):
    """Posiciona os dados nas colunas exatas do modelo do Google Contacts."""
    valores = {
        'First Name': proteger_celula_csv(primeiro_nome),
        'Last Name': proteger_celula_csv(sobrenome),
        'E-mail 1 - Label': 'Work' if email else '',
        'E-mail 1 - Value': proteger_celula_csv(email),
        'Phone 1 - Label': 'Mobile' if telefone else '',
        'Phone 1 - Value': telefone,
        'Notes': 'Contato exportado pelo monitoramento ESL Tech',
        'Labels': proteger_celula_csv(nome_unidade),
    }
    return [valores.get(coluna, '') for coluna in CABECALHO_CSV_GOOGLE_CONTATOS]


def montar_relatorio(
    metricas, anteriores, perfis, satisfacao, etapas, atividade,
):
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
