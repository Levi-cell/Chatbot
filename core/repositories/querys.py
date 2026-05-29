import logging


logger = logging.getLogger("db.querys")

"""Aqui nao so existe querys de consulta mas tambem querys que
chama funcoes SQL, na duvida consulte Bankscript.py"""


def pegar_unidades(cursor):
    cursor.execute("""
        SELECT phone_number_id, id_unidade
        FROM chatbot.unidade
        WHERE status_ativo = TRUE
    """)

    resultado = {row[0]: row[1] for row in cursor.fetchall()}

    logger.debug("unidades_consultadas | total=%s", len(resultado))

    return resultado


def buscar_unidades_para_listagem_bloqueios(cursor):
    cursor.execute("""
        SELECT id_unidade, nome, phone_number_id
        FROM chatbot.unidade
        WHERE phone_number_id IS NOT NULL
          AND phone_number_id <> ''
        ORDER BY id_unidade;
    """)

    return cursor.fetchall()


def pegar_mensagens_da_fila(cursor):
    cursor.execute("SELECT * FROM chatbot.dequeue_message();")
    registro = cursor.fetchone()
    if registro:
        logger.debug("fila_dequeue | acao=reservar id_mensagem=%s", registro[0])
    return registro


def buscar_id_unidade_por_phone_id(phone_number_id, cursor):
    cursor.execute("""
        SELECT id_unidade
        FROM chatbot.unidade
        WHERE phone_number_id = %s
          AND status_ativo = TRUE
    """, (phone_number_id,))

    result = cursor.fetchone()
    logger.debug(
        "unidade_consulta | acao=buscar_por_phone phone_number_id=%s encontrada=%s",
        phone_number_id,
        bool(result),
    )
    return result[0] if result else None


def buscar_last_message_from_conversa(cliente_telefone, id_phone_unidade, cursor):
    cursor.execute("""
        SELECT c.last_message_from
        FROM chatbot.conversa c
        JOIN chatbot.cliente cl ON cl.id_cliente = c.id_cliente
        JOIN chatbot.unidade u ON u.id_unidade = c.id_unidade
        WHERE cl.waid_telefone = %s
          AND u.phone_number_id = %s
          AND c.status_ativa = TRUE
        LIMIT 1;
    """, (cliente_telefone, id_phone_unidade))

    resultado = cursor.fetchone()
    logger.debug(
        "conversa_consulta | acao=last_message_from cliente=%s phone_number_id=%s encontrada=%s",
        cliente_telefone,
        id_phone_unidade,
        bool(resultado),
    )
    return resultado[0] if resultado else None


def tentar_lock_conversa(id_conversa, cursor):
    cursor.execute("SELECT lock_ok, lock_version_atual FROM chatbot.lock_conversa(%s);", (id_conversa,))
    resultado = cursor.fetchone()

    if not resultado:
        logger.warning(
            "conversa_lock_sem_retorno | acao=negar_lock id_conversa=%s",
            id_conversa,
        )
        return False, None

    logger.debug(
        "conversa_lock_resultado | acao=lock id_conversa=%s lock_ok=%s lock_version=%s",
        id_conversa,
        bool(resultado[0]),
        resultado[1],
    )
    return bool(resultado[0]), resultado[1]


def unlock_conversa(id_conversa, lock_version, cursor):
    if lock_version is None:
        return False

    cursor.execute("SELECT chatbot.unlock_conversa(%s, %s);", (id_conversa, lock_version))
    resultado = cursor.fetchone()
    logger.debug(
        "conversa_unlock_resultado | acao=unlock id_conversa=%s lock_version=%s liberada=%s",
        id_conversa,
        lock_version,
        bool(resultado[0]) if resultado else False,
    )
    return bool(resultado[0]) if resultado else False


def buscar_estado_conversa(id_cliente, id_unidade, cursor):
    cursor.execute("""
        WITH conversa_ativa AS (
            SELECT
                id_conversa,
                id_etapa_atual,
                status_ativa,
                finalizou_em,
                'ativa' AS estado
            FROM chatbot.conversa
            WHERE id_cliente = %s
              AND id_unidade = %s
              AND status_ativa = TRUE
            LIMIT 1
        ),
        ultima_conversa AS (
            SELECT
                id_conversa,
                id_etapa_atual,
                status_ativa,
                finalizou_em,
                CASE
                    WHEN id_etapa_atual = 7
                     AND finalizou_em > NOW() - INTERVAL '30 days'
                    THEN 'bloqueada'
                    ELSE 'liberada'
                END AS estado
            FROM chatbot.conversa
            WHERE id_cliente = %s
              AND id_unidade = %s
              AND status_ativa = FALSE
            ORDER BY finalizou_em DESC
            LIMIT 1
        )
        SELECT
            id_conversa,
            id_etapa_atual,
            status_ativa,
            finalizou_em,
            estado
        FROM conversa_ativa

        UNION ALL

        SELECT
            id_conversa,
            id_etapa_atual,
            status_ativa,
            finalizou_em,
            estado
        FROM ultima_conversa
        WHERE NOT EXISTS (SELECT 1 FROM conversa_ativa)

        LIMIT 1;
    """, (id_cliente, id_unidade, id_cliente, id_unidade))

    resultado = cursor.fetchone()
    logger.debug(
        "conversa_estado_consultado | acao=buscar_estado id_cliente=%s id_unidade=%s encontrada=%s estado=%s",
        id_cliente,
        id_unidade,
        bool(resultado),
        resultado[4] if resultado else None,
    )
    return resultado


def buscar_finalizou_em_conversa(id_conversa, cursor):
    cursor.execute("""
        SELECT finalizou_em
        FROM chatbot.conversa
        WHERE id_conversa = %s
        LIMIT 1;
    """, (id_conversa,))

    resultado = cursor.fetchone()
    logger.debug(
        "conversa_finalizacao_consultada | acao=buscar_finalizou_em id_conversa=%s encontrada=%s",
        id_conversa,
        bool(resultado),
    )
    return resultado[0] if resultado else None


def buscar_conversa_bloqueada_por_cliente_unidade(
    cliente_telefone,
    id_phone_unidade,
    cursor,
):
    cursor.execute("""
        SELECT c.finalizou_em
        FROM chatbot.conversa c
        JOIN chatbot.cliente cl ON cl.id_cliente = c.id_cliente
        JOIN chatbot.unidade u ON u.id_unidade = c.id_unidade
        WHERE cl.waid_telefone = %s
          AND u.phone_number_id = %s
          AND u.status_ativo = TRUE
          AND c.status_ativa = FALSE
          AND c.id_etapa_atual = 7
          AND c.finalizou_em > NOW() - INTERVAL '30 days'
        ORDER BY c.finalizou_em DESC
        LIMIT 1;
    """, (cliente_telefone, id_phone_unidade))

    resultado = cursor.fetchone()
    logger.debug(
        "conversa_bloqueada_consultada | acao=buscar_bloqueio cliente=%s phone_number_id=%s bloqueada=%s",
        cliente_telefone,
        id_phone_unidade,
        bool(resultado),
    )
    return resultado[0] if resultado else None


def existe_mensagem_anterior_aberta_conversa(
    id_conversa,
    id_mensagem_atual,
    received_data_hora,
    cursor,
):
    if id_conversa is None:
        return False

    cursor.execute("""
        SELECT EXISTS (
            SELECT 1
            FROM chatbot.fila_mensagens
            WHERE id_conversa = %s
              AND id_mensagem <> %s
              AND status IN ('pending', 'processing')
              AND (
                  received_data_hora < %s
                  OR (
                      received_data_hora = %s
                      AND id_mensagem < %s
                  )
              )
            LIMIT 1
        );
    """, (
        id_conversa,
        id_mensagem_atual,
        received_data_hora,
        received_data_hora,
        id_mensagem_atual,
    ))

    resultado = bool(cursor.fetchone()[0])
    logger.debug(
        "fila_ordem_consultada | acao=verificar_anterior id_conversa=%s id_mensagem=%s existe_anterior=%s",
        id_conversa,
        id_mensagem_atual,
        resultado,
    )
    return resultado


# def buscar_conversa_ativa(id_cliente, id_unidade, cursor):
#     """
#     Busca a conversa ativa pelo cliente e unidade correspondentes.
#     Retorna todos os campos da tabela conversa.
#     """
#     cursor.execute("""
#         SELECT c.*
#         FROM chatbot.conversa c
#         WHERE c.id_cliente = %s
#           AND c.id_unidade = %s
#           AND c.status_ativa = TRUE
#         LIMIT 1;
#     """, (id_cliente, id_unidade))
#
#     return cursor.fetchone()
