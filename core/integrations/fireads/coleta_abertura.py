"""Completa ausências a partir do registro mais recente do mesmo telefone."""

from copy import deepcopy
from core.validacoes.coleta_abertura import CAMPOS, campo, aceito, completo, normalizar
from core.integrations.fireads.aba_geral import ORIGENS, selecionar_entrega, referencia_registro, mais_recente
from core.integrations.fireads.atribuicao import CHAVE, capturar
from core.integrations.fireads.contrato import localizar
from core.integrations.fireads.extratores import extrair_nome, extrair_email

COLUNAS = {'nome': 'Nome', 'email': 'Email', 'destinatario': 'Para quem é', 'turno': 'Período preferido'}


def campos_registro(row):
    campos = {c: campo([row.get(coluna) or ''], c, 'dashboard') for c, coluna in COLUNAS.items()}
    # Campos estruturados preservam os extratores FireAds existentes. A validação
    # de texto livre do WhatsApp não é imposta novamente ao formulário externo.
    for tipo, extrator in (('nome', extrair_nome), ('email', extrair_email)):
        bruto = str(row.get(COLUNAS[tipo]) or '').strip()
        valor = extrator(bruto)
        if valor:
            identidade = normalizar(bruto.split('|', 1)[0]) if tipo == 'nome' else valor.casefold()
            campos[tipo].update(status='aceito', valor=valor, identidade=identidade, bruto=bruto)
    return campos


def compativel(conhecidos, candidatos, *, campos=CAMPOS):
    for c in campos:
        a, b = conhecidos[c], candidatos[c]
        if a['status'] != 'aceito':
            continue
        if b['status'] != 'aceito':
            return False
        if c == 'nome':
            # Mesmo nome extraído, mas sobrenomes explícitos divergentes bloqueiam.
            ca, cb = a['identidade'].split(), b['identidade'].split()
            somente_nome = a['identidade'] == normalizar(a['valor'])
            if ca != cb and not (somente_nome and cb[:len(ca)] == ca):
                return False
        elif c == 'destinatario' and a['identidade'] == 'dependente' and b['valor']['dependente']:
            continue
        elif a['identidade'] != b['identidade']:
            return False
    return True


def selecionar_para_complementacao(rows, estado, fuso=None):
    """Recebe somente linhas elegíveis do telefone; outros campos não filtram."""
    return mais_recente(rows, fuso)


def interpretar_parcial(rows, numero, fuso, aba, estado):
    resultado = deepcopy(estado)
    row = selecionar_entrega(rows, numero, fuso)
    if row is not None:
        for c, recebido in campos_registro(row).items():
            if c == 'turno' and not resultado.get('coletar_turno'):
                continue
            if not aceito(resultado, c) and recebido['status'] == 'aceito':
                resultado['campos'][c] = recebido
        resultado['formulario_identificado'] = True
    return {'resultado': 'importado' if completo(resultado) else ('incompleto' if row else 'ausente'),
            'origem': ORIGENS[normalizar(row.get('Canal'))] if row else 'organico',
            'referencia': referencia_registro(row, aba, fuso), 'coleta': resultado,
            CHAVE: capturar(row, aba, fuso),
            'motivo': None if row else 'sem_registro_elegivel', 'dados_titular': {}}
