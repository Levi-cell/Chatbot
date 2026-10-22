"""Entrega dos dados coletados, com destino e valores congelados (contrato 4)."""

from copy import deepcopy

from core.integrations.fireads.aba_geral import (
    CAMPOS_IDENTIDADE, ORIGENS, mais_recente, numero_linha, referencia_registro,
)
from core.integrations.fireads.coleta_abertura import selecionar_para_complementacao
from core.integrations.fireads.contrato import (
    CANAIS, ErroFireAds, acrescentar_observacoes, localizar, normalizar, telefone,
)
from core.integrations.fireads.destino_dashboard import linhas_com_bloco

COLUNAS = {'nome': 'Nome', 'email': 'Email', 'destinatario': 'Para quem é',
           'turno': 'Período preferido'}
TURNOS = {'manha': 'Manhã', 'tarde': 'Tarde', 'noite': 'Noite', 'sabado': 'Sábado'}


def valor_planilha(tipo, campo):
    if tipo == 'nome':
        # A saudação usa o primeiro nome; a planilha conserva o nome informado.
        return str(campo.get('bruto') or campo['valor']).split('|', 1)[0].strip()
    if tipo == 'destinatario':
        return campo['valor']['texto']
    if tipo == 'turno':
        return TURNOS[campo['valor']]
    return campo['valor']


def dados_sincronizacao(coleta, *, com_link=False):
    """Correções aceitas no atendimento prevalecem sobre a abertura original."""
    campos = deepcopy(coleta['campos'])
    turno_atendimento = (campos.get('turno') or {}).get('fonte') == 'atendimento'
    coletar_turno = bool((coleta.get('coletar_turno') or turno_atendimento) and not com_link)
    if not coletar_turno:
        campos.pop('turno', None)
    alteracoes = {}
    for tipo, coluna in COLUNAS.items():
        c = campos.get(tipo) or {}
        if c.get('status') == 'aceito' and c.get('fonte') in {'mensagem', 'atendimento'}:
            valor = valor_planilha(tipo, c)
            if valor:
                alteracoes[coluna] = valor
    return {'identidade_coleta': campos, 'campos_dashboard': alteracoes,
            'coletar_turno': coletar_turno}


def _por_telefone(rows, snapshot):
    return localizar(rows, snapshot['telefone'], 'WhatsApp', incluir_equivalentes=True)


def _email_cruzado(rows, snapshot):
    encontrados = _por_telefone(rows, snapshot)
    email = str(snapshot.get('email') or '').strip().casefold()
    if email and any(r not in encontrados and str(r.get('Email') or '').strip().casefold() == email
                     for r in rows):
        raise ErroFireAds('Email já presente em outro telefone; conferir identidade')


def _registro_marcado(rows, snapshot, bloco):
    encontrados = _por_telefone(rows, snapshot)
    linhas = linhas_com_bloco(encontrados, bloco)
    if len(linhas) > 1:
        raise ErroFireAds('Bloco da conversa presente em mais de um registro')
    return next((r for r in encontrados if numero_linha(r) in linhas), None)


def _relocalizar(rows, referencia, snapshot, marcado=None):
    """Reconhece a mesma inscrição antes, durante e depois da nossa escrita.

    Data, canal, telefone e campos não escritos continuam identificando o alvo.
    O número da linha sozinho nunca autoriza alterar outro contato.
    """
    if referencia.get('aba') != snapshot['aba']:
        raise ErroFireAds('Aba do registro selecionado diverge do envio')
    antes = referencia.get('campos')
    if not isinstance(antes, dict) or set(antes) != set(CAMPOS_IDENTIDADE):
        raise ErroFireAds('Referência do formulário incompleta')
    updates = snapshot['campos_dashboard']
    fixos = set(CAMPOS_IDENTIDADE) - set(updates)
    candidatos = [r for r in _por_telefone(rows, snapshot)
                  if all(r.get(c) == antes[c] for c in fixos)]
    if marcado is not None:
        if marcado not in candidatos:
            raise ErroFireAds('Bloco da conversa não pertence ao destino congelado')
        return marcado
    # Uma escrita pode ter sido aplicada só em parte antes da queda do Web App.
    reconhecidos = [r for r in candidatos if all(
        r.get(c) == antes[c] or (c in updates and r.get(c) == updates[c])
        for c in CAMPOS_IDENTIDADE)]
    if reconhecidos:
        candidatos = reconhecidos
    if len(candidatos) == 1:
        return candidatos[0]
    original = [r for r in candidatos if numero_linha(r) == referencia.get('linha')]
    if len(original) == 1:
        return original[0]
    raise ErroFireAds('Registro selecionado ausente ou deslocado sem identidade única')


def escolher(rows, snapshot):
    if snapshot.get('referencia') is not None:
        row = _relocalizar(rows, snapshot['referencia'], snapshot)
    else:
        elegiveis = [r for r in _por_telefone(rows, snapshot)
                    if normalizar(r.get('Canal')) in ORIGENS]
        estado = {'campos': snapshot['identidade_coleta'],
                  'coletar_turno': snapshot['coletar_turno']}
        row = selecionar_para_complementacao(elegiveis, estado, snapshot.get('fuso'))
        # Divergência não descarta os dados do chat nem cria outra inscrição.
        if row is None:
            row = mais_recente(elegiveis, snapshot.get('fuso'))
    if row is not None:
        return {'tipo': 'update', 'referencia': referencia_registro(row, snapshot['aba'], snapshot.get('fuso'))}
    _email_cruzado(rows, snapshot)
    return {'tipo': 'create'}


def _atualizar(row, snapshot, bloco):
    if 'Observação' not in row or not set(snapshot['campos_dashboard']) <= set(row):
        raise ErroFireAds('Colunas de sincronização ausentes; não sobrescrever')
    obs, mudou = acrescentar_observacoes(row['Observação'], bloco)
    updates = snapshot['campos_dashboard']
    if not mudou and all(row[c] == v for c, v in updates.items()):
        return None
    # Observação por último: um erro anterior não pode atestar entrega completa.
    return {'row': numero_linha(row), 'observacoes': obs, 'campos': dict(updates)}


def preparar(rows, snapshot, bloco):
    acrescentar_observacoes(None, bloco)
    alvo = snapshot.get('destino')
    if not alvo:
        raise ErroFireAds('Destino da coleta ainda não foi persistido')
    marcado = _registro_marcado(rows, snapshot, bloco)
    if alvo['tipo'] == 'update':
        row = _relocalizar(rows, alvo['referencia'], snapshot, marcado)
        return _atualizar(row, snapshot, bloco)
    if alvo['tipo'] != 'create':
        raise ErroFireAds('Tipo de destino desconhecido')
    if marcado is not None:
        # Append já aplicado: corrigir eventual escrita parcial, nunca duplicar.
        return _atualizar(marcado, snapshot, bloco)
    _email_cruzado(rows, snapshot)
    dados = {'Nome': snapshot['nome'], 'Email': snapshot['email'],
             'WhatsApp': telefone(snapshot['telefone']), 'Perfil/Faixa': snapshot['perfil'],
             'Para quem é': snapshot['para_quem'], 'Canal': CANAIS[snapshot['origem']][0]}
    for tipo, coluna in COLUNAS.items():
        c = snapshot['identidade_coleta'].get(tipo) or {}
        if c.get('status') == 'aceito':
            dados[coluna] = valor_planilha(tipo, c)
    dados['Observação'] = bloco
    return {'dados': dados}
