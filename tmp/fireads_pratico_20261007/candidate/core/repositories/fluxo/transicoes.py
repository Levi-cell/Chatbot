import logging


logger = logging.getLogger("db.transicoes_etapa")


def listar_transicoes_permitidas(id_etapa_origem, cursor):
    if id_etapa_origem is None:
        return {}

    cursor.execute(
        """
        SELECT
            evento,
            id_etapa_destino
        FROM chatbot.etapa_transicao
        WHERE id_etapa_origem = %s
        ORDER BY evento;
        """,
        (id_etapa_origem,),
    )

    transicoes = {
        evento: id_etapa_destino
        for evento, id_etapa_destino in cursor.fetchall()
    }

    logger.debug(
        "transicoes_etapa_consultadas | acao=carregar_mapa etapa_origem=%s quantidade=%s",
        id_etapa_origem,
        len(transicoes),
    )
    return transicoes
