"""Indicadores por atendimento e anúncio, usando somente evidência salva."""

from core.integrations.fireads.atribuicao import ler, ROTULOS


def montar_origens(linhas):
    canais = {c: {'canal': c, 'rotulo': r, 'atendimentos': 0, 'funil': 0}
              for c, r in ROTULOS.items()}
    anuncios, vistos, contatos = {}, set(), set()
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
        canal['atendimentos'] += 1
        canal['funil'] += enviado
        if origem['canal'] == 'meta':
            nome = origem['anuncio']
            item = anuncios.setdefault(nome, {'anuncio': nome, 'atendimentos': 0, 'funil': 0})
            item['atendimentos'] += 1
            item['funil'] += enviado
    return {'canais': list(canais.values()),
            'anuncios': sorted(anuncios.values(), key=lambda x: (-x['atendimentos'], x['anuncio'] or '')),
            'atendimentos': len(vistos), 'contatos_unicos': len(contatos),
            'sem_origem': desconhecidos, 'identificados': len(vistos) - desconhecidos}
