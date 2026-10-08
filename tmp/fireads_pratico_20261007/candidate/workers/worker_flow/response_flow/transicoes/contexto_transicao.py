def montar_contexto_transicao(
    id_etapa_origem,
    transicoes_permitidas,
):
    """
    Converte o resultado da consulta em uma fotografia explícita do mapa.

    O contexto guarda somente as arestas que partem da etapa atual. A decisão
    de qual evento ocorreu continua pertencendo ao resolver da etapa.
    """
    return {
        "id_etapa_origem_transicao": id_etapa_origem,
        "transicoes_permitidas": dict(transicoes_permitidas),
    }


def prever_etapa_resposta(
    id_etapa_atual,
    transicoes_permitidas,
    *,
    etapa_inicial,
):
    """
    Mantém o campo legado id_etapa_resposta apenas para observabilidade.

    Quando existem vários destinos, nenhuma previsão é feita. A transição real
    só será escolhida depois que o resolver identificar o evento da resposta.
    """
    if id_etapa_atual is None:
        return etapa_inicial

    destinos = set(transicoes_permitidas.values())

    if len(destinos) == 1:
        return destinos.pop()

    return None
