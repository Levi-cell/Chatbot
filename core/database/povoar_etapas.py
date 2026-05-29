import logging

from core.database.connection_aws import get_conn


logger = logging.getLogger("db.seed")


def insere_etapa_once():

    conn = None

    try:
        conn = get_conn()
        cursor = conn.cursor()

        etapa_1 = "Saudação e introdução ao supera"
        etapa_2 = "Para quem é"
        etapa_3 = "Qual o motivo"
        etapa_4 = "O nome "
        etapa_5 = "O telefone"
        etapa_6 = "Email"
        etapa_7 = "Link de agendamento, aviso no funil"

        cursor.execute(
            """
            INSERT INTO chatbot.etapa (nome_etapa)
            VALUES
                (%s),
                (%s),
                (%s),
                (%s),
                (%s),
                (%s),
                (%s)
            ON CONFLICT (nome_etapa) DO NOTHING;
            """,
            (
                etapa_1,
                etapa_2,
                etapa_3,
                etapa_4,
                etapa_5,
                etapa_6,
                etapa_7,
            )
        )

        conn.commit()
        logger.info(
            "banco_seed_ok | acao=inserir_etapas linhas=%s",
            cursor.rowcount,
        )

    except Exception as erro:
        if conn:
            conn.rollback()
        logger.exception("banco_seed_erro | acao=inserir_etapas erro=%s", erro)

    finally:
        if conn:
            conn.close()


