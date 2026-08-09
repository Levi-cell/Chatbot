import logging

from core.database.deploy_database.transacao_deploy import transacao_deploy


logger = logging.getLogger("db.seed")


ETAPAS = (
    (1, "Saudação e nome do cliente", False, 0, False),
    (2, "Destino do atendimento", False, 0, False),
    (3, "Confirmação do destino do atendimento", False, 0, False),
    (4, "Profissão do cliente", False, 0, False),
    (5, "Nome do dependente", False, 0, False),
    (6, "Idade do aluno", False, 0, False),
    (7, "Oferta de aula experimental e avaliação cognitiva", False, 0, False),
    (8, "Oferta adiada e Instagram", False, 0, False),
    (9, "Confirmação de retorno ao atendimento", False, 0, False),
    (10, "Email", False, 0, False),
    (11, "Introdução à triagem cognitiva", False, 0, False),
    (12, "Triagem cognitiva - pergunta 1", False, 0, False),
    (13, "Triagem cognitiva - pergunta 2", False, 0, False),
    (14, "Triagem cognitiva - pergunta 3", False, 0, False),
    (15, "Triagem cognitiva - pergunta 4", False, 0, False),
    (16, "Triagem cognitiva - pergunta 5", False, 0, False),
    (17, "Triagem cognitiva - pergunta 6", False, 0, False),
    (18, "Agendamento após a triagem cognitiva", False, 0, True),
    (19, "Pesquisa de satisfação - nota", False, 0, True),
    (20, "Pesquisa de satisfação - opção de comentário", False, 0, True),
    (21, "Pesquisa de satisfação - comentário", False, 0, True),
    (22, "Finalização do atendimento", True, 30, True),
)

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


def _recusar_catalogo_legado(cursor):
    """Exige a migração incremental antes de sincronizar IDs em uso."""
    cursor.execute(
        """
        SELECT
            id_etapa,
            nome_etapa,
            encerra_automaticamente,
            bloqueio_dias,
            elegivel_funil
        FROM chatbot.etapa
        WHERE id_etapa BETWEEN 3 AND 22
        ORDER BY id_etapa;
        """
    )
    etapas_existentes = cursor.fetchall()

    if not etapas_existentes:
        return

    etapas_esperadas = {
        etapa[0]: etapa
        for etapa in ETAPAS
    }
    divergencias = [
        id_etapa
        for (
            id_etapa,
            nome_etapa,
            encerra_automaticamente,
            bloqueio_dias,
            elegivel_funil,
        ) in etapas_existentes
        if etapas_esperadas.get(id_etapa) != (
            id_etapa,
            nome_etapa,
            encerra_automaticamente,
            bloqueio_dias,
            elegivel_funil,
        )
    ]

    if divergencias:
        raise RuntimeError(
            "Catalogo de etapas legado detectado. Aplique primeiro a "
            "migracao SQL que insere a confirmacao como etapa 3 e "
            "renumera as antigas etapas 3 a 21 para 4 a 22 "
            f"(etapas_divergentes={divergencias})"
        )


def insere_etapa_once():
    with transacao_deploy("sincronizar_etapas", logger) as cursor:
        _recusar_catalogo_legado(cursor)
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
        "banco_seed_ok | acao=sincronizar_etapas quantidade=%s",
        len(ETAPAS),
    )
