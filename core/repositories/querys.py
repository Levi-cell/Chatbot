import logging


logger = logging.getLogger("db.querys")

"""Aqui nÃ£o sÃ³ existe querys de consulta mas tambÃ©m querys que
chama funÃ§Ãµes SQL, na dÃºvida consulte Bankscript.py"""


def pegar_unidades(cursor):
    cursor.execute("""
        SELECT phone_number_id, id_unidade
        FROM chatbot.unidade
        WHERE status_ativo = TRUE
    """)

    resultado = {row[0]: row[1] for row in cursor.fetchall()}

    logger.debug("unidades_consultadas | total=%s", len(resultado))

    return resultado

def pegar_mensagens_da_fila(cursor):
    """Aqui usamos uma funÃ§Ã£o que criamos dentro do nosso script SQL

    a funÃ§Ã£o chatbot.dequeue_message jÃ¡ consulta a fila de mensagens e
    tambÃ©m faz uma validaÃ§Ã£o evitando que vÃ¡rios workers peguem a mesma mensagem,
    entÃ£o o SELECT da funÃ§Ã£o abaixo estÃ¡ pegando os registros validados a partir
    dessa funÃ§Ã£o SQL, pense que a funÃ§Ã£o python faz uma consulta e dentro da consulta o
    SQL executa outra funÃ§Ã£o. Em suma, essa funÃ§Ã£o serve para arquitetura complexas com
    varios workers e arquiteturas simples.

    OBS: dequeue_message Ã© igual a fila de mensagens em inglÃªs, a funÃ§Ã£o mexe diretamente
    com a tabela e suas interligaÃ§Ãµes pelo banco.

    """
    cursor.execute("SELECT * FROM chatbot.dequeue_message();")
    registro = cursor.fetchone()

     ## AQUI PRECISAMOS COMMITAR POIS A FUNÃ‡Ã‚O SQL TRAZ OPERAÃ‡Ã”ES UPDATES


    return registro

def buscar_id_unidade_por_phone_id(phone_number_id, cursor):
    cursor.execute("""
        SELECT id_unidade
        FROM chatbot.unidade
        WHERE phone_number_id = %s
          AND status_ativo = TRUE
    """, (phone_number_id,))

    result = cursor.fetchone()
    return result[0] if result else None


def buscar_last_message_from_conversa(cliente_telefone, id_phone_unidade, cursor):
    """
    Busca o campo last_message_from da conversa ativa do cliente
    para a unidade correspondente.
    """
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
    return resultado[0] if resultado else None

def tentar_lock_conversa(id_conversa, cursor):
    cursor.execute("SELECT chatbot.lock_conversa(%s);", (id_conversa,))
    return cursor.fetchone()[0]


def unlock_conversa(id_conversa, cursor):
    cursor.execute("SELECT chatbot.unlock_conversa(%s);", (id_conversa,))
    return cursor.fetchone()[0]


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

    return cursor.fetchone()


def buscar_finalizou_em_conversa(id_conversa, cursor):
    cursor.execute("""
        SELECT finalizou_em
        FROM chatbot.conversa
        WHERE id_conversa = %s
        LIMIT 1;
    """, (id_conversa,))

    resultado = cursor.fetchone()
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
    return resultado[0] if resultado else None


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
