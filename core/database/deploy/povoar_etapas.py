import logging

from core.database.connection_aws import get_conn


logger = logging.getLogger("db.seed")


ETAPAS = (
    (1, "Saudação e nome do cliente"),
    (2, "Destino do atendimento"),
    (3, "Nome do dependente"),
    (4, "Idade do aluno"),
    (5, "Oferta de aula experimental e avaliação cognitiva"),
    (6, "Email"),
    (7, "Link de agendamento e entrada no funil"),
)


def insere_etapa_once():
    conn = None

    try:
        conn = get_conn(application_name="script_chatbot")
        cursor = conn.cursor()

        cursor.executemany(
            """
            INSERT INTO chatbot.etapa (id_etapa, nome_etapa)
            VALUES (%s, %s)
            ON CONFLICT (id_etapa)
            DO UPDATE SET nome_etapa = EXCLUDED.nome_etapa;
            """,
            ETAPAS,
        )

        cursor.execute(
            """
            SELECT setval(
                pg_get_serial_sequence('chatbot.etapa', 'id_etapa'),
                (SELECT MAX(id_etapa) FROM chatbot.etapa),
                TRUE
            );
            """
        )

        conn.commit()
        logger.info(
            "banco_seed_ok | acao=sincronizar_etapas quantidade=%s",
            len(ETAPAS),
        )

    except Exception as erro:
        if conn:
            conn.rollback()
        logger.exception(
            "banco_seed_erro | acao=sincronizar_etapas erro=%s",
            erro,
        )
        raise

    finally:
        if conn:
            conn.close()

