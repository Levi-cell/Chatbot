import logging


logger = logging.getLogger("db.atendimento.conversas")

ETAPA_INICIAL = 1

MOTIVOS_ENCERRAMENTO_VALIDOS = {
    "idade_invalida",
    "foi_agendado",
    "encaminhado_suporte_idoso",
    "followup_sem_resposta",
}


def inserindo_em_conversa_caso_seja_nova(id_cliente, id_unidade, cursor):
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

    resultado = cursor.fetchone()

    if resultado:
        logger.debug(
            "conversa_insert_resultado | acao=criar_conversa id_cliente=%s id_unidade=%s id_conversa=%s",
            id_cliente,
            id_unidade,
            resultado[0],
        )
        return resultado[0]

    raise ValueError(
        f"Anomalia Crítica: conversa do cliente {id_cliente} "
        f"e unidade {id_unidade} não foi criada!"
    )


def tentar_lock_conversa(id_conversa, cursor):
    cursor.execute(
        "SELECT lock_ok, lock_version_atual "
        "FROM chatbot.lock_conversa(%s);",
        (id_conversa,),
    )
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

    cursor.execute(
        "SELECT chatbot.unlock_conversa(%s, %s);",
        (id_conversa, lock_version),
    )
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
                'ativa' AS estado,
                status_dependente,
                last_message_from,
                followup_stage,
                followup_last_sent_at,
                lead_no_funil
            FROM chatbot.conversa
            WHERE id_cliente = %s
              AND id_unidade = %s
              AND status_ativa = TRUE
            LIMIT 1
        ),
        ultima_conversa AS (
            SELECT
                c.id_conversa,
                c.id_etapa_atual,
                c.status_ativa,
                c.finalizou_em,
                CASE
                    WHEN COALESCE(e.bloqueio_dias, 0) > 0
                     AND c.finalizou_em
                         > NOW() - (
                             COALESCE(e.bloqueio_dias, 0)
                             * INTERVAL '1 day'
                         )
                    THEN 'bloqueada'
                    ELSE 'liberada'
                END AS estado,
                c.status_dependente,
                c.last_message_from,
                c.followup_stage,
                c.followup_last_sent_at,
                c.lead_no_funil
            FROM chatbot.conversa c
            LEFT JOIN chatbot.etapa e
              ON e.id_etapa = c.id_etapa_atual
            WHERE c.id_cliente = %s
              AND c.id_unidade = %s
              AND c.status_ativa = FALSE
            ORDER BY c.finalizou_em DESC
            LIMIT 1
        )
        SELECT
            id_conversa,
            id_etapa_atual,
            status_ativa,
            finalizou_em,
            estado,
            status_dependente,
            last_message_from,
            followup_stage,
            followup_last_sent_at,
            lead_no_funil
        FROM conversa_ativa

        UNION ALL

        SELECT
            id_conversa,
            id_etapa_atual,
            status_ativa,
            finalizou_em,
            estado,
            status_dependente,
            last_message_from,
            followup_stage,
            followup_last_sent_at,
            lead_no_funil
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


def atualizar_conversa_mensagem_cliente(
    id_conversa,
    data_interacao,
    cursor,
):
    if data_interacao is None:
        raise ValueError(
            "data_interacao nao informada para registrar mensagem do cliente"
        )

    cursor.execute("""
        UPDATE chatbot.conversa
        SET
            last_message_from = 'cliente',
            last_interaction_at = %s
        WHERE id_conversa = %s;
    """, (data_interacao, id_conversa))

    logger.debug(
        "conversa_update | acao=registrar_mensagem_cliente id_conversa=%s data_interacao=%s linhas=%s",
        id_conversa,
        data_interacao,
        cursor.rowcount,
    )

    if cursor.rowcount != 1:
        raise ValueError(
            "Conversa nao foi atualizada com mensagem do cliente "
            f"(id_conversa={id_conversa}, linhas={cursor.rowcount})"
        )

    return cursor.rowcount


def inicializar_conversa_resposta_bot(
    id_conversa,
    id_etapa_resultante,
    data_interacao,
    cursor,
):
    if id_etapa_resultante != ETAPA_INICIAL:
        raise ValueError(
            "Inicializacao da conversa so pode persistir a etapa 1"
        )

    _validar_data_interacao_bot(data_interacao)

    cursor.execute("""
        UPDATE chatbot.conversa
        SET
            id_etapa_atual = %s,
            last_message_from = 'bot',
            last_interaction_at = %s
        WHERE id_conversa = %s
          AND id_etapa_atual IS NULL;
    """, (
        id_etapa_resultante,
        data_interacao,
        id_conversa,
    ))

    logger.debug(
        "conversa_update | acao=inicializar_etapa id_conversa=%s etapa=%s linhas=%s",
        id_conversa,
        id_etapa_resultante,
        cursor.rowcount,
    )

    if cursor.rowcount != 1:
        raise ValueError(
            "Conversa nao foi inicializada na etapa 1 "
            f"(id_conversa={id_conversa}, linhas={cursor.rowcount})"
        )

    return cursor.rowcount


def atualizar_conversa_por_transicao(
    id_conversa,
    id_etapa_origem,
    evento_transicao,
    id_etapa_destino,
    data_interacao,
    cursor,
    *,
    permitir_reaplicacao=False,
):
    if id_etapa_origem is None:
        raise ValueError("Etapa de origem nao informada para transicao")

    if not evento_transicao:
        raise ValueError("Evento nao informado para transicao")

    if id_etapa_destino is None:
        raise ValueError("Etapa de destino nao informada para transicao")

    _validar_data_interacao_bot(data_interacao)

    cursor.execute(
        """
        UPDATE chatbot.conversa AS conversa
        SET
            id_etapa_atual = CASE
                WHEN conversa.id_etapa_atual = %s THEN %s
                ELSE conversa.id_etapa_atual
            END,
            last_message_from = 'bot',
            last_interaction_at = %s
        WHERE conversa.id_conversa = %s
          AND EXISTS (
              SELECT 1
              FROM chatbot.etapa_transicao AS transicao
              WHERE transicao.id_etapa_origem = %s
                AND transicao.evento = %s
                AND transicao.id_etapa_destino = %s
          )
          AND (
              conversa.id_etapa_atual = %s
              OR (
                  %s = TRUE
                  AND conversa.id_etapa_atual = %s
              )
          );
        """,
        (
            id_etapa_origem,
            id_etapa_destino,
            data_interacao,
            id_conversa,
            id_etapa_origem,
            evento_transicao,
            id_etapa_destino,
            id_etapa_origem,
            bool(permitir_reaplicacao),
            id_etapa_destino,
        ),
    )

    logger.debug(
        "conversa_update | acao=aplicar_transicao id_conversa=%s etapa_origem=%s evento=%s etapa_destino=%s reaplicacao=%s linhas=%s",
        id_conversa,
        id_etapa_origem,
        evento_transicao,
        id_etapa_destino,
        bool(permitir_reaplicacao),
        cursor.rowcount,
    )

    if cursor.rowcount != 1:
        raise ValueError(
            "Conversa nao foi atualizada; transicao inexistente, origem "
            "incompativel ou conversa ausente "
            f"(id_conversa={id_conversa}, origem={id_etapa_origem}, "
            f"evento={evento_transicao}, destino={id_etapa_destino}, "
            f"reaplicacao={bool(permitir_reaplicacao)}, "
            f"linhas={cursor.rowcount})"
        )

    return cursor.rowcount


def atualizar_conversa_resposta_bot_sem_avancar(
    id_conversa,
    data_interacao,
    cursor,
):
    _validar_data_interacao_bot(data_interacao)

    cursor.execute("""
        UPDATE chatbot.conversa
        SET
            last_message_from = 'bot',
            last_interaction_at = %s
        WHERE id_conversa = %s;
    """, (data_interacao, id_conversa))

    logger.debug(
        "conversa_update | acao=registrar_resposta_bot_sem_avancar id_conversa=%s data_interacao=%s linhas=%s",
        id_conversa,
        data_interacao,
        cursor.rowcount,
    )

    if cursor.rowcount != 1:
        raise ValueError(
            "Conversa nao foi atualizada com resposta do bot sem avancar etapa "
            f"(id_conversa={id_conversa}, linhas={cursor.rowcount})"
        )

    return cursor.rowcount


def atualizar_status_dependente_conversa(
    id_conversa,
    status_dependente,
    cursor,
):
    cursor.execute("""
        UPDATE chatbot.conversa
        SET status_dependente = %s
        WHERE id_conversa = %s;
    """, (bool(status_dependente), id_conversa))

    logger.debug(
        "conversa_update | acao=atualizar_status_dependente id_conversa=%s status_dependente=%s linhas=%s",
        id_conversa,
        bool(status_dependente),
        cursor.rowcount,
    )

    if cursor.rowcount != 1:
        raise ValueError(
            "Conversa nao foi atualizada com status_dependente "
            f"(id_conversa={id_conversa}, linhas={cursor.rowcount})"
        )

    return cursor.rowcount


def atualizar_profissao_conversa(id_conversa, profissao, cursor):
    if not id_conversa:
        raise ValueError(
            "id_conversa nao informado para atualizar profissao"
        )

    if not isinstance(profissao, str):
        raise ValueError("profissao deve ser um texto")

    profissao_normalizada = profissao.strip()

    if (
        not profissao_normalizada
        or len(profissao_normalizada) > 100
        or "\n" in profissao_normalizada
        or "\r" in profissao_normalizada
    ):
        raise ValueError(
            "profissao deve conter uma unica linha entre 1 e 100 caracteres"
        )

    cursor.execute(
        """
        UPDATE chatbot.conversa
        SET profissao = %s
        WHERE id_conversa = %s;
        """,
        (profissao_normalizada, id_conversa),
    )

    logger.debug(
        "conversa_update | acao=atualizar_profissao id_conversa=%s linhas=%s",
        id_conversa,
        cursor.rowcount,
    )

    if cursor.rowcount != 1:
        raise ValueError(
            "Conversa nao foi atualizada com profissao "
            f"(id_conversa={id_conversa}, linhas={cursor.rowcount})"
        )

    return cursor.rowcount


def encerrar_conversa(id_conversa, motivo_encerramento, cursor):
    if motivo_encerramento not in MOTIVOS_ENCERRAMENTO_VALIDOS:
        raise ValueError(
            "Motivo de encerramento invalido "
            f"(motivo={motivo_encerramento!r})"
        )

    cursor.execute(
        """
        UPDATE chatbot.conversa
        SET
            status_ativa = FALSE,
            finalizou_em = NOW(),
            motivo_encerramento = %s,
            processing = FALSE,
            processing_started_at = NULL
        WHERE id_conversa = %s
          AND status_ativa = TRUE
        RETURNING finalizou_em;
        """,
        (motivo_encerramento, id_conversa),
    )

    resultado = cursor.fetchone()

    if not resultado:
        raise RuntimeError(
            "Conversa não encerrada "
            f"(id_conversa={id_conversa}, linhas={cursor.rowcount})"
        )

    return resultado[0]


def _validar_data_interacao_bot(data_interacao):
    if data_interacao is None:
        raise ValueError(
            "data_interacao nao informada para registrar resposta do bot"
        )
