"""Orquestra leituras do painel a partir da unidade resolvida pelo guard."""

from zoneinfo import ZoneInfo

from core.validacoes.suporte_por_idade import validar_idade_minima_suporte

from django.db import connection

from core.repositories.monitoramento import painel as repositorio

from .apresentacao import (
    botoes_para_mensagem,
    classificar_faixa,
    consolidar_conversas,
    montar_relatorio,
)
from .faixa_etaria import consultar_faixa_etaria, distribuir_dependentes_por_titular


FUSO_PAINEL = ZoneInfo('America/Sao_Paulo')


def _iso(valor):
    return valor.isoformat() if hasattr(valor, 'isoformat') else valor


def _no_fuso_painel(valor):
    if valor is None:
        return None
    if valor.tzinfo is None:
        return valor.replace(tzinfo=FUSO_PAINEL)
    return valor.astimezone(FUSO_PAINEL)


def _periodo_payload(periodo, unidade):
    inicio = periodo.inicio or unidade.get('inicio_historico')
    return {
        'chave': periodo.chave,
        'rotulo': periodo.rotulo,
        'inicio': _iso(inicio),
        'fim': _iso(periodo.fim),
        'texto': (
            f"{_no_fuso_painel(inicio).strftime('%d/%m/%Y %H:%M')} até agora"
            if inicio else 'Nenhuma conversa registrada até agora'
        ),
    }


def carregar_conversas(acesso, periodo):
    with connection.cursor() as cursor:
        unidade = repositorio.buscar_unidade(acesso.id_unidade, cursor)
        linhas = repositorio.listar_conversas(
            acesso.id_unidade, periodo.inicio, periodo.fim, cursor
        )
        metricas = repositorio.buscar_metricas(
            acesso.id_unidade, periodo.inicio, periodo.fim, cursor
        )
    conversas = consolidar_conversas(linhas)
    for item in conversas:
        item['ultima_atividade'] = _iso(item['ultima_atividade'])
    metricas['nota_media'] = float(metricas['nota_media']) if metricas.get('nota_media') is not None else None
    return {
        'unidade': {
            'nome': unidade['nome_unidade'],
            'agente': unidade['nome_agente'],
            'regras': {
                'idade_minima_suporte': validar_idade_minima_suporte(unidade['idade_minima_suporte']),
                'email_obrigatorio': bool(unidade['email_obrigatorio']),
                'bpa_ativo': bool(unidade['bpa_ativo']),
            },
        },
        'periodo': _periodo_payload(periodo, unidade),
        'metricas': metricas,
        'conversas': conversas,
        'atualizado_em': _iso(periodo.fim),
    }


def carregar_mensagens(acesso, id_cliente, periodo):
    with connection.cursor() as cursor:
        linhas = repositorio.buscar_mensagens(
            acesso.id_unidade, id_cliente, periodo.inicio, periodo.fim, cursor
        )
    mensagens = []
    for linha in linhas:
        item = {
            'id_mensagem': linha['id_mensagem'],
            'id_conversa': linha['id_conversa'],
            'id_etapa': linha['id_etapa'],
            'data': _iso(linha['data']),
            'quem_enviou': linha['quem_enviou'],
            'tipo': linha['tipo'],
            'texto': linha['texto'] or f"[{linha['tipo'] or 'mensagem sem texto'}]",
        }
        item['botoes'] = botoes_para_mensagem(item)
        mensagens.append(item)
    return {'id_cliente': id_cliente, 'mensagens': mensagens}


def _agrupar_perfis(linhas, *, bpa_ativo):
    minimo = 4 if bpa_ativo else 5
    chaves = ('dependente_menor', 'dependente_adulto', 'dependente_idoso', 'titular_adulto', 'titular_idoso')
    acumulado = {chave: {'clientes': set(), 'conversas': 0, 'funil': set()} for chave in chaves}
    todos_clientes = set()
    clientes_classificados = set()
    for linha in linhas:
        id_cliente = linha['id_cliente']
        todos_clientes.add(id_cliente)
        status_dependente = linha.get('status_dependente')
        if status_dependente not in (True, False) or type(status_dependente) is not bool:
            continue
        dependente = status_dependente is True
        idade = linha.get('idade_dependente') if dependente else linha.get('idade_titular')
        faixa = classificar_faixa(idade)
        if dependente and faixa == 'menor' and idade >= minimo:
            chave = 'dependente_menor'
        elif dependente and faixa in ('adulto', 'idoso'):
            chave = 'dependente_' + faixa
        elif not dependente and faixa in ('adulto', 'idoso'):
            chave = 'titular_' + faixa
        else:
            continue
        alvo = acumulado[chave]
        alvo['clientes'].add(id_cliente)
        alvo['conversas'] += 1
        clientes_classificados.add(id_cliente)
        if linha.get('foi_funil'):
            alvo['funil'].add(id_cliente)
    rotulos = {
        'dependente_menor': f'Dependentes de {minimo} a 17 anos',
        'dependente_adulto': 'Dependentes de 18 a 59 anos',
        'dependente_idoso': 'Dependentes com 60 anos ou mais',
        'titular_adulto': 'Titulares de 18 a 59 anos',
        'titular_idoso': 'Titulares com 60 anos ou mais',
    }
    resposta = []
    for chave in chaves:
        item = acumulado[chave]
        leads = len(item['clientes'])
        funil = len(item['funil'])
        resposta.append({
            'chave': chave, 'rotulo': rotulos[chave], 'leads': leads,
            'conversas': item['conversas'], 'funil': funil,
            'taxa_funil': round(funil / leads * 100, 1) if leads else 0,
            'funil_nao_aplicavel': False,
        })
    return {
        'linhas': resposta,
        'sem_classificacao': len(todos_clientes - clientes_classificados),
        'idade_minima_dependente': minimo,
    }


def _granularidade(periodo, unidade):
    inicio = periodo.inicio or unidade.get('inicio_historico')
    if not inicio:
        return 'dia'
    dias = (periodo.fim - inicio).days
    return 'mes' if dias > 180 else 'semana' if dias > 60 else 'dia'


def carregar_relatorio(acesso, periodo):
    with connection.cursor() as cursor:
        unidade = repositorio.buscar_unidade(acesso.id_unidade, cursor)
        metricas = repositorio.buscar_metricas(acesso.id_unidade, periodo.inicio, periodo.fim, cursor)
        encaminhados = repositorio.contar_encaminhados_comercial_por_idade(
            acesso.id_unidade, periodo.inicio, periodo.fim, cursor
        )
        anteriores = None
        if periodo.inicio_anterior is not None:
            anteriores = repositorio.buscar_metricas(
                acesso.id_unidade, periodo.inicio_anterior, periodo.fim_anterior, cursor
            )
        perfis_brutos = repositorio.buscar_perfis(acesso.id_unidade, periodo.inicio, periodo.fim, cursor)
        satisfacao_bruta = repositorio.buscar_satisfacao(acesso.id_unidade, periodo.inicio, periodo.fim, cursor)
        etapas = repositorio.buscar_etapas(acesso.id_unidade, periodo.inicio, periodo.fim, cursor)
        atividade = repositorio.buscar_atividade(
            acesso.id_unidade, periodo.inicio, periodo.fim, cursor,
            _granularidade(periodo, unidade),
        )
    for grupo in (metricas, anteriores or {}):
        if grupo.get('nota_media') is not None:
            grupo['nota_media'] = float(grupo['nota_media'])
    satisfacao = {str(nota): 0 for nota in range(1, 6)}
    for linha in satisfacao_bruta:
        satisfacao[str(linha['nota'])] = linha['quantidade']
    for linha in etapas:
        linha['quantidade'] = int(linha['quantidade'])
    for linha in atividade:
        # DATE_TRUNC sobre AT TIME ZONE devolve timestamp sem fuso. O offset
        # explícito impede o navegador de interpretar o agrupamento como UTC.
        linha['periodo'] = _iso(_no_fuso_painel(linha['periodo']))
    relatorio = montar_relatorio(
        metricas, anteriores,
        _agrupar_perfis(
            perfis_brutos,
            bpa_ativo=bool(unidade['bpa_ativo']),
        ),
        satisfacao, etapas, atividade,
        encaminhados_comercial_por_idade=encaminhados,
    )
    relatorio.update({
        'dependentes_por_titular': distribuir_dependentes_por_titular(perfis_brutos),
        'unidade': {
            'nome': unidade['nome_unidade'],
            'idade_minima_suporte': validar_idade_minima_suporte(unidade['idade_minima_suporte']),
        },
        'periodo': _periodo_payload(periodo, unidade),
        'atualizado_em': _iso(periodo.fim),
    })
    return relatorio


def carregar_faixa_etaria(acesso, periodo, idade_minima, publico):
    with connection.cursor() as cursor:
        linhas = repositorio.buscar_perfis(
            acesso.id_unidade, periodo.inicio, periodo.fim, cursor,
        )
    resultado = consultar_faixa_etaria(linhas, idade_minima, publico)
    resultado['periodo'] = {
        'chave': periodo.chave, 'rotulo': periodo.rotulo,
        'inicio': _iso(periodo.inicio), 'fim': _iso(periodo.fim),
    }
    return resultado


def carregar_contatos(acesso, periodo):
    with connection.cursor() as cursor:
        return repositorio.listar_contatos(
            acesso.id_unidade, periodo.inicio, periodo.fim, cursor
        )
