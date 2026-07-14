"""Fila transacional e idempotência local dos envios ao Funil."""


STATUS_PENDING = "pending"
STATUS_PROCESSING = "processing"
STATUS_SENT = "sent"


def sincronizar_envios_elegiveis(cursor, *, limite=100):
    """Materializa conversas elegíveis ainda não enviadas na fila local."""
    _validar_inteiro_positivo(limite, "limite")

    cursor.execute(
        """
        INSERT INTO chatbot.funil_envios (id_conversa)
        SELECT elegiveis.id_conversa
        FROM (
            SELECT c.id_conversa
            FROM chatbot.conversa c
            JOIN chatbot.etapa e
              ON e.id_etapa = c.id_etapa_atual
            JOIN chatbot.integracao_funil_unidade integracao
              ON integracao.id_unidade = c.id_unidade
            WHERE e.elegivel_funil = TRUE
              AND c.lead_no_funil IS NOT TRUE
              AND integracao.integracao_ativa = TRUE
              AND integracao.widget_ativo = TRUE
            ORDER BY c.id_conversa ASC
            LIMIT %s
        ) AS elegiveis
        ON CONFLICT (id_conversa) DO NOTHING
        RETURNING id_funil_envio;
        """,
        (limite,),
    )

    return len(cursor.fetchall())


def reivindicar_proximo_envio(cursor, *, lease_segundos=900):
    """Reserva um lead com SKIP LOCKED e recupera leases abandonados."""
    _validar_inteiro_positivo(lease_segundos, "lease_segundos")

    cursor.execute(
        """
        WITH proximo AS (
            SELECT fe.id_funil_envio
            FROM chatbot.funil_envios fe
            JOIN chatbot.conversa c
              ON c.id_conversa = fe.id_conversa
            JOIN chatbot.etapa e
              ON e.id_etapa = c.id_etapa_atual
            JOIN chatbot.integracao_funil_unidade integracao
              ON integracao.id_unidade = c.id_unidade
            WHERE (
                    (
                        fe.status = 'pending'
                        AND fe.next_attempt_at <= NOW()
                    )
                    OR
                    (
                        fe.status = 'processing'
                        AND fe.processing_started_at
                            < NOW() - (%s * INTERVAL '1 second')
                    )
                  )
              AND e.elegivel_funil = TRUE
              AND c.lead_no_funil IS NOT TRUE
              AND integracao.integracao_ativa = TRUE
              AND integracao.widget_ativo = TRUE
            ORDER BY
                COALESCE(fe.next_attempt_at, fe.processing_started_at),
                fe.id_funil_envio
            FOR UPDATE OF fe SKIP LOCKED
            LIMIT 1
        )
        UPDATE chatbot.funil_envios fe
        SET
            status = 'processing',
            retry_count = fe.retry_count + 1,
            processing_started_at = NOW(),
            ultimo_erro = NULL,
            atualizado_em = NOW()
        FROM proximo
        WHERE fe.id_funil_envio = proximo.id_funil_envio
        RETURNING
            fe.id_funil_envio,
            fe.id_conversa,
            fe.retry_count;
        """,
        (lease_segundos,),
    )

    resultado = cursor.fetchone()
    if resultado is None:
        return None

    return {
        "id_funil_envio": resultado[0],
        "id_conversa": resultado[1],
        "retry_count": resultado[2],
    }


def registrar_falha_envio(
    id_funil_envio,
    erro,
    cursor,
    *,
    retry_segundos=3600,
):
    """Libera o lead para nova tentativa sem marcá-lo como enviado."""
    _validar_inteiro_positivo(retry_segundos, "retry_segundos")
    erro_resumido = str(erro)[:4000]

    cursor.execute(
        """
        UPDATE chatbot.funil_envios
        SET
            status = 'pending',
            next_attempt_at = NOW() + (%s * INTERVAL '1 second'),
            processing_started_at = NULL,
            ultimo_erro = %s,
            atualizado_em = NOW()
        WHERE id_funil_envio = %s
          AND status = 'processing'
        RETURNING id_funil_envio;
        """,
        (retry_segundos, erro_resumido, id_funil_envio),
    )

    return cursor.fetchone() is not None


def marcar_envio_como_concluido(
    id_funil_envio,
    id_conversa,
    resposta_funil,
    cursor,
):
    """Confirma conversa e fila no mesmo commit controlado pelo worker."""
    cursor.execute(
        """
        UPDATE chatbot.conversa c
        SET lead_no_funil = TRUE
        FROM chatbot.etapa e
        WHERE c.id_conversa = %s
          AND e.id_etapa = c.id_etapa_atual
          AND e.elegivel_funil = TRUE
          AND c.lead_no_funil IS NOT TRUE
        RETURNING c.id_conversa;
        """,
        (id_conversa,),
    )
    if cursor.fetchone() is None:
        raise RuntimeError(
            "Conversa não permaneceu elegível durante a confirmação do Funil"
        )

    cursor.execute(
        """
        UPDATE chatbot.funil_envios
        SET
            status = 'sent',
            processing_started_at = NULL,
            enviado_em = NOW(),
            resposta_funil = %s,
            ultimo_erro = NULL,
            atualizado_em = NOW()
        WHERE id_funil_envio = %s
          AND id_conversa = %s
          AND status = 'processing'
        RETURNING id_funil_envio;
        """,
        (resposta_funil, id_funil_envio, id_conversa),
    )
    if cursor.fetchone() is None:
        raise RuntimeError("Fila do Funil perdeu a reserva antes da confirmação")

    return True


def _validar_inteiro_positivo(valor, nome):
    if not isinstance(valor, int) or valor <= 0:
        raise ValueError(f"{nome} deve ser um inteiro positivo")
