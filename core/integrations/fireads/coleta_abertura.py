"""Completa campos a partir de uma única inscrição compatível da aba geral."""

from copy import deepcopy
from core.validacoes.coleta_abertura import CAMPOS, campo, aceito, completo, normalizar
from core.integrations.fireads.aba_geral import ORIGENS, mais_recente, referencia_registro
from core.integrations.fireads.contrato import localizar
from core.integrations.fireads.extratores import extrair_nome, extrair_email

COLUNAS = {'nome': 'Nome', 'email': 'Email', 'destinatario': 'Para quem é'}


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


def interpretar_parcial(rows, numero, fuso, aba, estado):
    resultado = deepcopy(estado)
    encontrados = localizar(rows, numero, 'WhatsApp', incluir_equivalentes=True)
    candidatos = [r for r in encontrados if normalizar(r.get('Canal')) in ORIGENS
                  and compativel(estado['campos'], campos_registro(r))]
    row = mais_recente(candidatos, fuso)
    if row is not None:
        for c, recebido in campos_registro(row).items():
            if not aceito(resultado, c) and recebido['status'] == 'aceito':
                resultado['campos'][c] = recebido
        resultado['formulario_identificado'] = True
    return {'resultado': 'importado' if completo(resultado) else ('incompleto' if row else 'ausente'),
            'origem': ORIGENS[normalizar(row.get('Canal'))] if row else (
                'meta' if estado['rota_formulario_chat'] else 'organico'),
            'referencia': referencia_registro(row, aba, fuso), 'coleta': resultado,
            'motivo': None if row else 'sem_registro_compativel', 'dados_titular': {}}
