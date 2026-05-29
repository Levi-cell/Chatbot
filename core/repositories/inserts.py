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
