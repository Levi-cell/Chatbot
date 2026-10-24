"""Indicadores por atendimento e anúncio, usando somente evidência salva."""

from core.integrations.fireads.atribuicao import ler, ROTULOS, CANAIS_ANUNCIO
from .apresentacao import classificar_faixa


def _perfil(linha, minimo):
    dependente = linha.get('status_dependente')
    if type(dependente) is not bool:
        return 'nao_informado', 'Perfil não informado'
    tipo, rotulo = ('dependente', 'Dependente') if dependente else ('titular', 'Titular')
    idade = linha.get('idade_dependente' if dependente else 'idade_titular')
    faixa = classificar_faixa(idade)
    if faixa not in ('menor', 'adulto', 'idoso'):
        return tipo + '_sem_idade', rotulo + ' · idade não informada'
    if dependente and idade < minimo:
        faixa, descricao = 'abaixo_minimo', f'Abaixo de {minimo} anos'
    else:
        descricao = {'menor': f'{minimo}–17 anos' if dependente else 'Menor de 18 anos',
                     'adulto': '18–59 anos', 'idoso': '60 anos ou mais'}[faixa]
    return tipo + '_' + faixa, rotulo + ' · ' + descricao


def _incrementar(alvo, perfil, enviado):
    alvo['atendimentos'] += 1
    alvo['funil'] += enviado
    chave, rotulo = perfil
    item = alvo['perfis'].setdefault(chave, dict(chave=chave, rotulo=rotulo, atendimentos=0, funil=0))
    item['atendimentos'] += 1
    item['funil'] += enviado


def _finalizar(alvos):
    ordem = {chave: i for i, chave in enumerate(
        f'{tipo}_{faixa}' for tipo in ('titular', 'dependente')
        for faixa in ('abaixo_minimo', 'menor', 'adulto', 'idoso', 'sem_idade'))}
    for alvo in alvos:
        alvo['perfis'] = sorted(alvo['perfis'].values(), key=lambda p: ordem.get(p['chave'], 99))
    return alvos


def montar_origens(linhas, *, bpa_ativo=True):
    canais = {c: {'canal': c, 'rotulo': r, 'atendimentos': 0, 'funil': 0, 'perfis': {}}
              for c, r in ROTULOS.items()}
    anuncios, vistos, contatos = {c: {} for c in CANAIS_ANUNCIO}, set(), set()
    desconhecidos = 0
    for linha in linhas:
        cid = linha['id_conversa']
        if cid in vistos:
            continue
        vistos.add(cid)
        contatos.add(linha['id_cliente'])
        origem = ler(linha.get('contexto_fireads'), cid, linha.get('dados_consulta'))
        if origem is None:
            desconhecidos += 1
            continue
        canal = canais[origem['canal']]
        enviado = int(bool(linha.get('foi_funil')))
        perfil = _perfil(linha, 4 if bpa_ativo else 5)
        _incrementar(canal, perfil, enviado)
        if origem['canal'] in CANAIS_ANUNCIO:
            nome = origem['anuncio']
            item = anuncios[origem['canal']].setdefault(nome, {
                'anuncio': nome, 'atendimentos': 0, 'funil': 0, 'perfis': {}})
            _incrementar(item, perfil, enviado)
    grupos = {c: _finalizar(sorted(itens.values(), key=lambda x: (-x['atendimentos'], x['anuncio'] or '')))
              for c, itens in anuncios.items()}
    return {'canais': _finalizar(list(canais.values())),
            'anuncios': grupos['meta'], 'anuncios_google': grupos['google'],
            'atendimentos': len(vistos), 'contatos_unicos': len(contatos),
            'sem_origem': desconhecidos, 'identificados': len(vistos) - desconhecidos}
