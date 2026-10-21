"""Escolha persistível do alvo de entrega para a coleta por campo."""

from copy import deepcopy
from core.validacoes.coleta_abertura import aceito, campo
from core.integrations.fireads.coleta_abertura import campos_registro, compativel
from core.integrations.fireads.aba_geral import mais_recente, referencia_registro, relocalizar, numero_linha
from core.integrations.fireads.contrato import CANAIS, ErroFireAds, telefone, localizar, acrescentar_observacoes
from core.integrations.fireads.destino_dashboard import linhas_com_bloco


def identidade_entrega(estado):
    # Conhecidos no formulário não são substituídos por correções posteriores.
    campos = deepcopy(estado['mensagem_original'])
    for tipo in ('email', 'nome', 'destinatario'):
        if campos[tipo]['status'] != 'aceito':
            campos[tipo] = deepcopy(estado['campos'][tipo])
    return campos


def escolher(rows, snapshot):
    if snapshot.get('referencia') is not None:
        # Exclusão/edição de um registro já vinculado exige conferência.
        relocalizar(rows, snapshot['referencia'], snapshot['aba'])
        return {'tipo': 'update', 'referencia': snapshot['referencia']}
    encontrados = localizar(rows, snapshot['telefone'], 'WhatsApp', incluir_equivalentes=True)
    candidatos = encontrados
    if snapshot['rota_formulario_chat']:
        identidade = snapshot['identidade_coleta']
        # Sem confirmação final de e-mail/destinatário não inventar equivalência.
        candidatos = [r for r in encontrados if all(identidade[c]['status'] == 'aceito' for c in ('email', 'destinatario'))
                       and compativel(identidade, campos_registro(r), campos=('email', 'destinatario'))]
    row = mais_recente(candidatos, snapshot.get('fuso'))
    if row:
        return {'tipo': 'update', 'referencia': referencia_registro(row, snapshot['aba'], snapshot.get('fuso'))}
    email = str(snapshot.get('email') or '').strip().casefold()
    outros = [r for r in rows if r not in encontrados]
    if email and any(str(r.get('Email') or '').strip().casefold() == email for r in outros):
        raise ErroFireAds('Email já presente em outro telefone; conferir identidade')
    return {'tipo': 'create'}


def preparar(rows, snapshot, bloco):
    acrescentar_observacoes(None, bloco)
    encontrados = localizar(rows, snapshot['telefone'], 'WhatsApp', incluir_equivalentes=True)
    if linhas_com_bloco(encontrados, bloco):
        return None
    alvo = snapshot.get('destino')
    if not alvo:
        raise ErroFireAds('Destino da coleta ainda não foi persistido')
    if alvo['tipo'] == 'update':
        row = relocalizar(rows, alvo['referencia'], snapshot['aba'])
        if 'Observação' not in row:
            raise ErroFireAds('Observação ausente; não sobrescrever')
        obs, mudou = acrescentar_observacoes(row.get('Observação'), bloco)
        return {'row': numero_linha(row), 'observacoes': obs} if mudou else None
    if alvo['tipo'] != 'create':
        raise ErroFireAds('Tipo de destino desconhecido')
    # Rechecar identidade cruzada também em retries de um create planejado.
    email = str(snapshot.get('email') or '').strip().casefold()
    if email and any(r not in encontrados and str(r.get('Email') or '').strip().casefold() == email for r in rows):
        raise ErroFireAds('Email já presente em outro telefone; conferir identidade')
    return {'dados': {'Nome': snapshot['nome'], 'Email': snapshot['email'],
                       'WhatsApp': telefone(snapshot['telefone']), 'Perfil/Faixa': snapshot['perfil'],
                       'Para quem é': snapshot['para_quem'], 'Canal': CANAIS[snapshot['origem']][0], 'Observação': bloco}}
