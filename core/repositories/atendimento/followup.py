"""Consultas de follow-up e fencing; commit/rollback pertencem ao orquestrador."""


class LockConversaPerdido(RuntimeError):
    """O processamento deixou de possuir a versão válida do lock."""


def proteger_conversa(id_conversa, lock_version, cursor, *, renovar=False):
    cursor.execute(
        """
        SELECT id_conversa FROM chatbot.conversa
        WHERE id_conversa = %s AND processing IS TRUE AND lock_version = %s
          AND processing_started_at > clock_timestamp() - INTERVAL '110 seconds'
        FOR UPDATE;
    """,
        (id_conversa, lock_version),
    )
    if cursor.fetchone() is None:
        raise LockConversaPerdido(
            f"Lock perdido: conversa={id_conversa}, versao={lock_version}"
        )
    if renovar:
        cursor.execute(
            """
            UPDATE chatbot.conversa SET processing_started_at = clock_timestamp()
            WHERE id_conversa = %s AND lock_version = %s AND processing IS TRUE;
        """,
            (id_conversa, lock_version),
        )


def reler_conversa(contexto_banco, lock_version, cursor):
    anterior = contexto_banco["conversa"]
    proteger_conversa(anterior["id_conversa"], lock_version, cursor)
    cursor.execute(
        """
        SELECT id_etapa_atual, status_ativa, status_dependente, last_message_from,
               followup_stage, followup_last_sent_at, lead_no_funil, finalizou_em
        FROM chatbot.conversa
        WHERE id_conversa = %s AND id_cliente = %s AND id_unidade = %s;
    """,
        (
            anterior["id_conversa"],
            contexto_banco["id_cliente"],
            contexto_banco["id_unidade"],
        ),
    )
    row = cursor.fetchone()
    if row is None or row[1] is not True or row[7] is not None:
        raise LockConversaPerdido(
            "Conversa deixou de ser ativa para este cliente/unidade"
        )
    campos = (
        "id_etapa_atual",
        "status_ativa",
        "status_dependente",
        "last_message_from",
        "followup_stage",
        "followup_last_sent_at",
        "lead_no_funil",
        "finalizou_em",
    )
    conversa = dict(anterior, **dict(zip(campos, row)), lock_version=lock_version)
    stage = conversa["followup_stage"] or 0
    if stage < 0:
        raise ValueError("followup_stage negativo; requer saneamento explícito")
    return dict(contexto_banco, conversa=conversa)


def buscar_contexto_repeticao(id_conversa, id_unidade, cursor):
    cursor.execute(
        """
        SELECT cl.nome, d.nome_dependente, d.idade, u.nome_unidade, u.nome_agente,
               u.genero, u.link_agendamento, u.link_instagram,
               c.status_dependente,
               c.turno, cl.idade, u.numero_comercial, e.encerra_automaticamente
        FROM chatbot.conversa c
        JOIN chatbot.cliente cl ON cl.id_cliente = c.id_cliente
        JOIN chatbot.unidade u ON u.id_unidade = c.id_unidade
        JOIN chatbot.etapa e ON e.id_etapa = c.id_etapa_atual
        LEFT JOIN chatbot.dependente d ON d.id_conversa = c.id_conversa
        WHERE c.id_conversa = %s AND c.id_unidade = %s AND c.status_ativa IS TRUE;
    """,
        (id_conversa, id_unidade),
    )
    row = cursor.fetchone()
    if not row or row[-1]:
        raise ValueError("Etapa inexistente, encerrada ou terminal para repetição")
    return dict(
        zip(
            (
                "nome_titular",
                "nome_dependente",
                "idade_dependente",
                "nome_unidade",
                "nome_agente",
                "genero",
                "link_agendamento",
                "link_instagram",
                "status_dependente",
                "turno",
                "idade_cliente",
                "numero_comercial",
                "terminal",
            ),
            row,
        )
    )


def buscar_retomada(id_conversa, mensagem, cursor):
    cursor.execute(
        """
        SELECT id_etapa, stage_anterior, followup_em, concluida_em
        FROM chatbot.followup_retomada
        WHERE id_conversa = %s AND id_mensagem_fila = %s AND id_hash_cliente = %s;
    """,
        (id_conversa, mensagem["id_mensagem"], mensagem["id_hash"]),
    )
    row = cursor.fetchone()
    return (
        dict(zip(("id_etapa", "stage_anterior", "followup_em", "concluida_em"), row))
        if row
        else None
    )


def registrar_retomada(conversa, mensagem, cursor):
    cursor.execute(
        """
        INSERT INTO chatbot.followup_retomada
            (id_conversa, id_mensagem_fila, id_hash_cliente, id_etapa, stage_anterior, followup_em)
        VALUES (%s, %s, %s, %s, %s, %s);
    """,
        (
            conversa["id_conversa"],
            mensagem["id_mensagem"],
            mensagem["id_hash"],
            conversa["id_etapa_atual"],
            conversa["followup_stage"],
            conversa["followup_last_sent_at"],
        ),
    )


def concluir_retomada(contexto, data_bot, cursor, *, id_etapa_resultante=None):
    """Conclui o ciclo após a resposta, na etapa repetida ou no destino autorizado."""
    etapa_esperada = (
        contexto["id_etapa_atual"]
        if id_etapa_resultante is None
        else id_etapa_resultante
    )
    proteger_conversa(contexto["id_conversa"], contexto["lock_version"], cursor)
    cursor.execute(
        """
        UPDATE chatbot.conversa
        SET followup_stage = 0, last_message_from = 'bot', last_interaction_at = %s
        WHERE id_conversa = %s AND lock_version = %s AND processing IS TRUE
          AND status_ativa IS TRUE AND finalizou_em IS NULL AND id_etapa_atual = %s
          AND followup_stage = %s AND followup_last_sent_at IS NOT DISTINCT FROM %s;
    """,
        (
            data_bot,
            contexto["id_conversa"],
            contexto["lock_version"],
            etapa_esperada,
            contexto["stage_anterior"],
            contexto["followup_em"],
        ),
    )
    if cursor.rowcount != 1:
        raise LockConversaPerdido(
            "Ciclo de follow-up mudou antes da confirmação da retomada"
        )
    msg = contexto["mensagem_cliente_atual"]
    cursor.execute(
        """
        UPDATE chatbot.followup_retomada SET concluida_em = %s
        WHERE id_conversa = %s AND id_mensagem_fila = %s AND id_hash_cliente = %s
          AND concluida_em IS NULL;
    """,
        (
            data_bot,
            contexto["id_conversa"],
            msg["id_mensagem_fila"],
            msg["id_hash_msg"],
        ),
    )
    if cursor.rowcount != 1:
        raise ValueError("Registro da retomada ausente ou já concluído")


# O SELECT é reexecutado com a posse do lock imediatamente antes do despacho.
# Pendências são filtradas pelo par cliente/unidade, inclusive sem id_conversa.
CONSULTA_ELEGIVEIS = """
    SELECT c.id_conversa, c.id_cliente, c.id_unidade, c.id_etapa_atual,
           cl.waid_telefone, u.phone_number_id, u.telefone,
           b.id_mensagem AS id_ancora, b.received_data_hora AS ancora_em,
           COALESCE(c.followup_stage, 0), cl.nome, u.nome_agente,
           c.status_dependente, d.nome_dependente
    FROM chatbot.conversa c
    JOIN chatbot.cliente cl ON cl.id_cliente = c.id_cliente
    JOIN chatbot.unidade u ON u.id_unidade = c.id_unidade
    JOIN chatbot.etapa e ON e.id_etapa = c.id_etapa_atual
    LEFT JOIN chatbot.dependente d ON d.id_conversa = c.id_conversa
    JOIN LATERAL (
        SELECT h.id_mensagem, h.received_data_hora
        FROM chatbot.historico_mensagens h
        WHERE h.id_conversa = c.id_conversa AND h.quem_enviou = 'bot' AND h.status_envio = 'sent'
        ORDER BY h.received_data_hora DESC, h.id_mensagem DESC LIMIT 1
    ) b ON TRUE
    WHERE c.status_ativa IS TRUE AND c.finalizou_em IS NULL
      AND (c.id_etapa_atual BETWEEN 1 AND 17 OR
           (c.id_etapa_atual = 18 AND NULLIF(TRIM(u.link_agendamento), '') IS NULL))
      AND e.encerra_automaticamente IS FALSE
      AND COALESCE(c.followup_stage, 0) IN (0, 1) AND c.last_message_from = 'bot'
      AND c.last_interaction_at = b.received_data_hora
      AND b.received_data_hora <= clock_timestamp() - INTERVAL '7 hours'
      AND c.turnos_sem_avanco < 12 AND u.status_pagamento IS TRUE
      AND NULLIF(TRIM(cl.waid_telefone), '') IS NOT NULL
      AND NULLIF(TRIM(u.phone_number_id), '') IS NOT NULL
      AND NULLIF(TRIM(u.telefone), '') IS NOT NULL

      AND NOT EXISTS (
          SELECT 1 FROM chatbot.conversa anterior
          JOIN chatbot.etapa terminal ON terminal.id_etapa = anterior.id_etapa_atual
          WHERE anterior.id_cliente = c.id_cliente AND anterior.id_unidade = c.id_unidade
            AND anterior.status_ativa IS FALSE AND terminal.bloqueio_dias > 0
            AND anterior.finalizou_em > clock_timestamp() - terminal.bloqueio_dias * INTERVAL '1 day'
      )
      AND NOT EXISTS (
          SELECT 1 FROM chatbot.webhook_flood_evento f
          WHERE f.wa_id_cliente = cl.waid_telefone AND f.phone_id_unidade = u.phone_number_id
            AND f.received_at >= clock_timestamp() - INTERVAL '5 seconds'
          GROUP BY f.wa_id_cliente, f.phone_id_unidade HAVING COUNT(*) >= 15
      )
      AND NOT EXISTS (
          SELECT 1 FROM chatbot.cliente_bloqueado_meta x
          WHERE x.wa_id_cliente = cl.waid_telefone AND x.phone_id_unidade = u.phone_number_id
      )
      AND NOT EXISTS (
          SELECT 1 FROM chatbot.fila_mensagens f
          WHERE (f.id_conversa = c.id_conversa OR
                 (f.cliente_telefone = cl.waid_telefone AND f.id_phone_unidade = u.phone_number_id))
            AND f.status IN ('pending', 'processing')
      )
      AND NOT EXISTS (
          SELECT 1 FROM chatbot.historico_mensagens h
          WHERE h.id_conversa = c.id_conversa AND h.quem_enviou = 'cliente'
            AND h.received_data_hora >= b.received_data_hora
      )
      AND EXISTS (
          SELECT 1 FROM chatbot.historico_mensagens h
          WHERE h.id_conversa = c.id_conversa AND h.quem_enviou = 'cliente'
            AND h.received_data_hora > clock_timestamp() - INTERVAL '24 hours' + INTERVAL '1 minute'
      )
      AND NOT EXISTS (
          SELECT 1 FROM chatbot.followup_envio f WHERE f.id_conversa = c.id_conversa
            AND f.id_ancora = b.id_mensagem AND f.ancora_em = b.received_data_hora
      )
      AND (
          (COALESCE(c.followup_stage, 0) = 0 AND NOT EXISTS (
              SELECT 1 FROM chatbot.followup_envio f WHERE f.id_conversa = c.id_conversa
                AND f.id_historico_bot = b.id_mensagem AND f.enviado_em = b.received_data_hora
          ))
          OR (c.followup_stage = 1 AND c.followup_last_sent_at = b.received_data_hora
              AND EXISTS (
                  -- Stage legado sozinho não comprova um primeiro envio.
                  SELECT 1 FROM chatbot.followup_envio primeiro
                  WHERE primeiro.id_conversa = c.id_conversa
                    AND primeiro.id_historico_bot = b.id_mensagem
                    AND primeiro.enviado_em = b.received_data_hora
                    AND NOT EXISTS (
                        SELECT 1 FROM chatbot.followup_envio anterior
                        WHERE anterior.id_conversa = primeiro.id_conversa
                          AND anterior.id_historico_bot = primeiro.id_ancora
                          AND anterior.enviado_em = primeiro.ancora_em
                    )
              ))
      )
      AND NOT EXISTS (
          SELECT 1 FROM chatbot.followup_retomada r
          WHERE r.id_conversa = c.id_conversa AND r.concluida_em IS NULL
            AND EXISTS (SELECT 1 FROM chatbot.fila_mensagens f
                        WHERE f.id_mensagem = r.id_mensagem_fila
                          AND f.id_hash_msg = r.id_hash_cliente
                          AND f.status IN ('pending', 'processing'))
      )
"""

COLUNAS_ELEGIVEL = (
    "id_conversa",
    "id_cliente",
    "id_unidade",
    "id_etapa",
    "cliente_telefone",
    "id_phone_unidade",
    "unidade_telefone",
    "id_ancora",
    "ancora_em",
    "followup_stage",
    "nome_titular",
    "nome_agente",
    "status_dependente",
    "nome_dependente",
)


def listar_elegiveis(cursor, limite=20, depois=None):
    parametros = []
    sql = CONSULTA_ELEGIVEIS
    if depois is not None:
        sql += " AND (b.received_data_hora, c.id_conversa) > (%s, %s)"
        parametros.extend(depois)
    sql += " ORDER BY b.received_data_hora, c.id_conversa LIMIT %s;"
    parametros.append(limite)
    cursor.execute(sql, parametros)
    return [dict(zip(COLUNAS_ELEGIVEL, row)) for row in cursor.fetchall()]


def reler_elegivel(id_conversa, cursor):
    cursor.execute(CONSULTA_ELEGIVEIS + " AND c.id_conversa = %s;", (id_conversa,))
    row = cursor.fetchone()
    return dict(zip(COLUNAS_ELEGIVEL, row)) if row else None


def persistir_followup(dados, envio, lock_version, cursor):
    stage_anterior = dados["followup_stage"]
    if stage_anterior not in (0, 1):
        raise ValueError("Follow-up proativo só pode partir dos stages 0 ou 1")
    stage = stage_anterior + 1
    proteger_conversa(dados["id_conversa"], lock_version, cursor)
    if not envio.get("id_hash_msg_bot") or not envio.get("enviou"):
        raise ValueError("Follow-up sem confirmação da Meta")
    cursor.execute(
        """
        INSERT INTO chatbot.historico_mensagens
            (id_conversa, id_etapa, received_data_hora, cliente_telefone, conteudo_texto,
             tipo_mensagem, id_hash_msg, id_mensagem_fila, id_hash_cliente_origem,
             id_phone_unidade, unidade_telefone, quem_enviou, status_envio)
        VALUES (%s, %s, clock_timestamp(), %s, %s, 'text', %s, NULL, NULL, %s, %s, 'bot', 'sent')
        RETURNING id_mensagem, received_data_hora;
    """,
        (
            dados["id_conversa"],
            dados["id_etapa"],
            dados["cliente_telefone"],
            envio["mensagem_bot"],
            envio["id_hash_msg_bot"],
            dados["id_phone_unidade"],
            dados["unidade_telefone"],
        ),
    )
    id_bot, data_bot = cursor.fetchone()
    cursor.execute(
        """
        INSERT INTO chatbot.followup_envio
            (id_conversa, id_ancora, ancora_em, id_historico_bot, enviado_em, id_hash_msg)
        VALUES (%s, %s, %s, %s, %s, %s);
    """,
        (
            dados["id_conversa"],
            dados["id_ancora"],
            dados["ancora_em"],
            id_bot,
            data_bot,
            envio["id_hash_msg_bot"],
        ),
    )
    # Uma entrada nova na fila após o despacho não invalida a confirmação da Meta.
    # O flow aguardará este lock: stage 1 retoma; stage 2 abre outra conversa.
    # Confirmação, histórico e encerramento pertencem à mesma transação.
    cursor.execute(
        """
        UPDATE chatbot.conversa
        SET followup_stage = %s, followup_last_sent_at = %s,
            last_message_from = 'bot', last_interaction_at = %s,
            status_ativa = CASE WHEN %s = 2 THEN FALSE ELSE status_ativa END,
            finalizou_em = CASE WHEN %s = 2 THEN %s ELSE finalizou_em END,
            motivo_encerramento = CASE WHEN %s = 2 THEN 'followup_sem_resposta'
                                      ELSE motivo_encerramento END
        WHERE id_conversa = %s AND lock_version = %s AND processing IS TRUE
          AND status_ativa IS TRUE AND finalizou_em IS NULL AND id_etapa_atual = %s
          AND COALESCE(followup_stage, 0) = %s AND last_message_from = 'bot'
          AND last_interaction_at = %s;
    """,
        (
            stage,
            data_bot,
            data_bot,
            stage,
            stage,
            data_bot,
            stage,
            dados["id_conversa"],
            lock_version,
            dados["id_etapa"],
            stage_anterior,
            dados["ancora_em"],
        ),
    )
    if cursor.rowcount != 1:
        raise LockConversaPerdido("Contexto mudou depois do despacho do follow-up")
    return id_bot, data_bot


def configurar_consulta_followup(cursor, *, sessao=False):
    if sessao:
        cursor.execute("SET statement_timeout = '15s'")
        cursor.execute("SET lock_timeout = '5s'")
    else:
        cursor.execute("SET LOCAL statement_timeout = '15s'")


def validar_schema_followup(cursor):
    """Recusa despachos antes da migração, sem depender de uma falha pós-Meta."""
    cursor.execute(
        "SELECT to_regclass('chatbot.followup_envio'), to_regclass('chatbot.followup_retomada'), to_regclass('chatbot.followup_legado')"
    )
    if not all(cursor.fetchone()):
        raise ValueError("SCHEMA_FOLLOWUP_AUSENTE")
    cursor.execute("""
        SELECT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conrelid = 'chatbot.conversa'::regclass
              AND conname = 'ck_conversa_motivo_encerramento'
              AND contype = 'c' AND convalidated
              AND POSITION('followup_sem_resposta' IN pg_get_constraintdef(oid)) > 0
        );
    """)
    if not cursor.fetchone()[0]:
        raise ValueError(
            "SCHEMA_SEGUNDO_FOLLOWUP_AUSENTE: aplicar 20260924_segundo_followup.sql"
        )


def consultar_diagnostico(cursor):
    cursor.execute("SET TRANSACTION READ ONLY")
    configurar_consulta_followup(cursor)
    validar_schema_followup(cursor)
    cursor.execute("""
        SELECT COUNT(*) FILTER (WHERE followup_stage > 0 AND status_ativa IS TRUE),
               COUNT(*) FILTER (WHERE followup_stage < 0),
               COUNT(*) FILTER (WHERE followup_stage > 2),
               COUNT(*) FILTER (WHERE last_interaction_at > clock_timestamp()),
               COUNT(*) FILTER (WHERE followup_stage = 2 AND status_ativa IS FALSE
                                 AND motivo_encerramento = 'followup_sem_resposta')
        FROM chatbot.conversa;
    """)
    positivos, negativos, legados, futuros, encerrados = cursor.fetchone()
    cursor.execute("SELECT COUNT(*) FROM chatbot.followup_legado")
    marcadas_na_migracao = cursor.fetchone()[0]
    candidatos = listar_elegiveis(cursor, 10)
    return {
        "ciclos_aguardando_reacao": positivos,
        "conversas_marcadas_na_migracao": marcadas_na_migracao,
        "stages_negativos": negativos,
        "stages_maiores_que_dois": legados,
        "encerradas_no_segundo_followup": encerrados,
        "horarios_futuros": futuros,
        "amostra_elegiveis": [
            {k: item[k] for k in ("id_conversa", "id_unidade", "id_etapa")}
            for item in candidatos
        ],
    }
