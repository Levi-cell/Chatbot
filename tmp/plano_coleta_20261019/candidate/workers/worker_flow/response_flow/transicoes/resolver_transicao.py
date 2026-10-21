import logging


logger = logging.getLogger("worker.transicao")


class TransicaoEtapaInvalida(ValueError):
    pass


def resolver_destino_transicao(
    contexto_historico,
    evento,
    *,
    destinos_esperados=None,
):
    origem = contexto_historico.get("id_etapa_origem_transicao")
    transicoes = contexto_historico.get("transicoes_permitidas")

    if origem is None:
        raise TransicaoEtapaInvalida(
            "Transicao solicitada sem etapa de origem persistida"
        )

    if not isinstance(transicoes, dict):
        raise TransicaoEtapaInvalida(
            "Mapa de transicoes nao foi carregado no contexto historico"
        )

    destino = transicoes.get(evento)

    if destino is None:
        logger.error(
            "transicao_recusada | motivo=evento_sem_destino etapa_origem=%s evento=%s eventos_disponiveis=%s",
            origem,
            evento,
            sorted(transicoes),
        )
        raise TransicaoEtapaInvalida(
            "Evento nao autorizado para a etapa atual "
            f"(origem={origem}, evento={evento})"
        )

    if destinos_esperados is not None and destino not in set(destinos_esperados):
        logger.critical(
            "transicao_mapa_inconsistente | motivo=destino_incompativel etapa_origem=%s evento=%s destino=%s destinos_esperados=%s",
            origem,
            evento,
            destino,
            sorted(set(destinos_esperados)),
        )
        raise TransicaoEtapaInvalida(
            "Mapa de transicoes possui destino incompativel com o evento "
            f"(origem={origem}, evento={evento}, destino={destino})"
        )

    logger.debug(
        "transicao_resolvida | acao=autorizar_pre_envio etapa_origem=%s evento=%s etapa_destino=%s",
        origem,
        evento,
        destino,
    )
    return destino


def anexar_transicao_ao_contexto_envio(
    contexto_historico,
    contexto_envio,
    evento,
    destino,
):
    origem = contexto_historico.get("id_etapa_origem_transicao")

    if contexto_envio.get("tratamento"):
        raise TransicaoEtapaInvalida(
            "Resposta de tratamento nao pode carregar evento de transicao"
        )

    if contexto_envio.get("id_etapa_resultante") != destino:
        raise TransicaoEtapaInvalida(
            "Sender retornou etapa diferente da transicao autorizada "
            f"(origem={origem}, evento={evento}, destino={destino}, "
            f"sender={contexto_envio.get('id_etapa_resultante')})"
        )

    contexto_com_transicao = dict(contexto_envio)
    contexto_com_transicao.update(
        {
            "id_etapa_origem_transicao": origem,
            "evento_transicao": evento,
            "id_etapa_resultante": destino,
        }
    )
    return contexto_com_transicao


def identificar_evento_por_destino(contexto_historico, destino):
    transicoes = contexto_historico.get("transicoes_permitidas") or {}
    eventos = [
        evento
        for evento, id_destino in transicoes.items()
        if id_destino == destino
    ]

    if not eventos:
        return None

    if len(eventos) != 1:
        raise TransicaoEtapaInvalida(
            "Mais de um evento encontrado para a mesma origem e destino "
            f"(origem={contexto_historico.get('id_etapa_origem_transicao')}, "
            f"destino={destino}, eventos={eventos})"
        )

    return eventos[0]
