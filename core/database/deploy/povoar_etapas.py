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
    (16, "Agendamento após a triagem cognitiva", False, 0, True),
    (17, "Pesquisa de satisfação - nota", False, 0, True),
    (18, "Pesquisa de satisfação - comentário", False, 0, True),
    (19, "Finalização do atendimento", True, 30, True),
)

ETAPA_FINAL_LEGADA = 17
ETAPA_FINAL_ATUAL = 19

SINCRONIZAR_ETAPA_SQL = """
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
        encerra_automaticamente = EXCLUDED.encerra_automaticamente,
        bloqueio_dias = EXCLUDED.bloqueio_dias,
        elegivel_funil = EXCLUDED.elegivel_funil;
"""


def _migrar_finalizacao_legada(cursor):
    """Move a antiga etapa final 17 antes de reutilizar seu identificador."""
    cursor.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM chatbot.etapa
            WHERE id_etapa = %s
              AND encerra_automaticamente IS TRUE
              AND bloqueio_dias = 30
        );
        """,
        (ETAPA_FINAL_LEGADA,),
    )
    finalizacao_legada_existe = cursor.fetchone()[0]

    if finalizacao_legada_existe:
        # Libera o nome unico antes de cadastrar a etapa final com o novo ID.
        cursor.execute(
            """
            UPDATE chatbot.etapa
            SET nome_etapa = 'Finalizacao do atendimento (legada)'
            WHERE id_etapa = %s;
            """,
            (ETAPA_FINAL_LEGADA,),
        )

    etapa_final_atual = next(
        etapa for etapa in ETAPAS if etapa[0] == ETAPA_FINAL_ATUAL
    )
    cursor.execute(SINCRONIZAR_ETAPA_SQL, etapa_final_atual)

    if not finalizacao_legada_existe:
        return 0, 0

    cursor.execute(
        """
        UPDATE chatbot.conversa
        SET id_etapa_atual = %s
        WHERE id_etapa_atual = %s
        """,
        (ETAPA_FINAL_ATUAL, ETAPA_FINAL_LEGADA),
    )
    conversas_migradas = cursor.rowcount

    cursor.execute(
        """
        UPDATE chatbot.historico_mensagens
        SET id_etapa = %s
        WHERE id_etapa = %s
        """,
        (ETAPA_FINAL_ATUAL, ETAPA_FINAL_LEGADA),
    )
    historicos_migrados = cursor.rowcount

    return conversas_migradas, historicos_migrados


def insere_etapa_once():
    with transacao_deploy("sincronizar_etapas", logger) as cursor:
        conversas_migradas, historicos_migrados = (
            _migrar_finalizacao_legada(cursor)
        )
        cursor.executemany(SINCRONIZAR_ETAPA_SQL, ETAPAS)

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
        "banco_seed_ok | acao=sincronizar_etapas quantidade=%s "
        "conversas_finalizacao_migradas=%s historicos_finalizacao_migrados=%s",
        len(ETAPAS),
        conversas_migradas,
        historicos_migrados,
    )
