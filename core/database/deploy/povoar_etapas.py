import logging

from core.database.deploy.transacao_deploy import transacao_deploy


logger = logging.getLogger("db.seed")


ETAPAS = (
    (1, "Saudação e nome do cliente", False, 0, False),
    (2, "Destino do atendimento", False, 0, False),
    (3, "Nome do dependente", False, 0, False),
    (4, "Idade do aluno", False, 0, False),
    (5, "Oferta de aula experimental e avaliação cognitiva", False, 0, False),
    (6, "Oferta adiada e Instagram", False, 0, False),
    (7, "Confirmação de retorno ao atendimento", False, 0, False),
    (8, "Email", False, 0, False),
    (9, "Introdução à triagem cognitiva", False, 0, False),
    (10, "Triagem cognitiva - pergunta 1", False, 0, False),
    (11, "Triagem cognitiva - pergunta 2", False, 0, False),
    (12, "Triagem cognitiva - pergunta 3", False, 0, False),
    (13, "Triagem cognitiva - pergunta 4", False, 0, False),
    (14, "Triagem cognitiva - pergunta 5", False, 0, False),
    (15, "Triagem cognitiva - pergunta 6", False, 0, False),
    (16, "Agendamento após a triagem cognitiva", False, 0, False),
)


def insere_etapa_once():
    with transacao_deploy("sincronizar_etapas", logger) as cursor:
        cursor.executemany(
            """
            INSERT INTO chatbot.etapa (
                id_etapa,
                nome_etapa,
                encerra_automaticamente,
                bloqueio_dias,
                elegivel_funil
            )
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (id_etapa)
            DO UPDATE SET
                nome_etapa = EXCLUDED.nome_etapa,
                encerra_automaticamente =
                    EXCLUDED.encerra_automaticamente,
                bloqueio_dias = EXCLUDED.bloqueio_dias,
                elegivel_funil = EXCLUDED.elegivel_funil;
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

    logger.info(
        "banco_seed_ok | acao=sincronizar_etapas quantidade=%s",
        len(ETAPAS),
    )
