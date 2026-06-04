import logging

from core.logging_config import short_value


logger = logging.getLogger("db.inserts")


def inserindo_em_cliente_caso_seja_novo(waid_telefone, cursor):
    try:
        cursor.execute("""
            INSERT INTO chatbot.cliente (waid_telefone)
            VALUES (%s)
            ON CONFLICT (waid_telefone) DO NOTHING;
        """, (waid_telefone,))

        inserido = cursor.rowcount == 1


        cursor.execute("""
            SELECT id_cliente 
            FROM chatbot.cliente 
            WHERE waid_telefone = %s;
        """, (waid_telefone,))
        result = cursor.fetchone()

        if result:
            logger.debug(
                "cliente_insert_resultado | acao=obter_cliente telefone=%s id_cliente=%s inserido=%s",
                short_value(waid_telefone),
                result[0],
                inserido,
            )
            return result[0], inserido

        raise ValueError(f"Anomalia Crítica: Cliente do telefone {waid_telefone} desapareceu da base durante a verificação!")

    except Exception:
        logger.exception(
            "cliente_insert_erro | acao=rollback telefone=%s",
            short_value(waid_telefone),
        )
        raise

def inserindo_em_conversa_caso_seja_nova(id_cliente, id_unidade, cursor):
    try:
        cursor.execute("""
            INSERT INTO chatbot.conversa (
                id_cliente,
                id_unidade,
                last_interaction_at,
                last_message_from
            )
            VALUES (%s, %s, NOW(), 'cliente')
            RETURNING id_conversa;
        """, (id_cliente, id_unidade))

        result = cursor.fetchone()

        if result:
            logger.debug(
                "conversa_insert_resultado | acao=criar_conversa id_cliente=%s id_unidade=%s id_conversa=%s",
                id_cliente,
                id_unidade,
                result[0],
            )
            return result[0]

        raise ValueError(
            f"Anomalia Crítica: conversa do cliente {id_cliente} "
            f"e unidade {id_unidade} não foi criada!"
        )

    except Exception:
        logger.exception(
            "conversa_insert_erro | acao=rollback id_cliente=%s id_unidade=%s",
            id_cliente,
            id_unidade,
        )
        raise


def inserir_historico_mensagem_cliente(
    mensagem,
    id_conversa,
    id_etapa,
    cursor,
):
    cursor.execute("""
        WITH existente AS (
            SELECT id_mensagem, received_data_hora
            FROM chatbot.historico_mensagens
            WHERE id_conversa = %s
              AND quem_enviou = 'cliente'
              AND id_mensagem_fila = %s
              AND id_hash_msg = %s
            ORDER BY received_data_hora DESC, id_mensagem DESC
            LIMIT 1
        ),
        inserido AS (
            INSERT INTO chatbot.historico_mensagens (
                id_conversa,
                id_etapa,
                received_data_hora,
                cliente_telefone,
                conteudo_texto,
                tipo_mensagem,
                id_hash_msg,
                id_mensagem_fila,
                id_hash_cliente_origem,
                id_phone_unidade,
                unidade_telefone,
                quem_enviou,
                status_envio
            )
            SELECT
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                NULL,
                %s,
                %s,
                'cliente',
                NULL
            WHERE NOT EXISTS (SELECT 1 FROM existente)
            RETURNING id_mensagem, received_data_hora
        )
        SELECT id_mensagem, received_data_hora, TRUE AS inserido
        FROM inserido

        UNION ALL

        SELECT id_mensagem, received_data_hora, FALSE AS inserido
        FROM existente

        LIMIT 1;
    """, (
        id_conversa,
        mensagem["id_mensagem"],
        mensagem["id_hash"],
        id_conversa,
        id_etapa,
        mensagem["data_recebimento"],
        mensagem["cliente_telefone"],
        mensagem["conteudo_texto"],
        mensagem["tipo_mensagem"],
        mensagem["id_hash"],
        mensagem["id_mensagem"],
        mensagem["id_phone_unidade"],
        mensagem["unidade_telefone"],
    ))

    resultado = cursor.fetchone()

    if not resultado:
        raise ValueError(
            "Historico do cliente nao foi inserido nem encontrado "
            f"(id_conversa={id_conversa}, id_mensagem={mensagem['id_mensagem']})"
        )

    logger.debug(
        "historico_cliente_insert_resultado | acao=registrar_cliente id_conversa=%s id_mensagem_fila=%s id_historico=%s inserido=%s",
        id_conversa,
        mensagem["id_mensagem"],
        resultado[0],
        bool(resultado[2]),
    )
    return resultado[0], resultado[1], bool(resultado[2])
