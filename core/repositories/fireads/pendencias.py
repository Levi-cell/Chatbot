"""Fila durável de consultas; SQL sem HTTP e sem controle de transações."""

from psycopg.types.json import Jsonb
from core.integrations.fireads.aba_geral import VERSAO_CONSULTA


def solicitar(abertura, id_conversa, numero, cursor):
    """Uma conversa recebe uma solicitação; retry não altera entrada nem prazo."""
    entrada = {
        "url": abertura["url"],
        "aba": abertura["aba"],
        "versao": VERSAO_CONSULTA,
        "fuso": abertura["fuso"],
        "numero": numero,
    }
    cursor.execute(
        """INSERT INTO chatbot.consulta_fireads
        (id_unidade,id_integracao_fireads,id_conversa,entrada)
        VALUES (%s,%s,%s,%s) ON CONFLICT (id_conversa) DO NOTHING""",
        (
            abertura["id_unidade"],
            abertura["id_integracao"],
            id_conversa,
            Jsonb(entrada),
        ),
    )


def buscar(id_conversa, cursor):
    """O fluxo segura esta linha somente durante a decisão local, nunca no HTTP."""
    cursor.execute(
        """SELECT id_consulta,id_integracao_fireads,status,dados,entrada,
                  prazo_final <= clock_timestamp(),aplicacao
        FROM chatbot.consulta_fireads WHERE id_conversa=%s FOR UPDATE""",
        (id_conversa,),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    return dict(
        zip(
            (
                "id_consulta",
                "id_integracao",
                "status",
                "dados",
                "entrada",
                "expirada",
                "aplicacao",
            ),
            row,
        )
    )


def concluir_sem_http(id_consulta, decisao, cursor):
    """Timeout ou cancelamento vence só pendências; resultado concluído é imutável."""
    cursor.execute(
        """UPDATE chatbot.consulta_fireads SET status='concluida',
          consulta_concluida=TRUE,resultado=%s,dados=%s,
          consultado_em=clock_timestamp(),atualizado_em=clock_timestamp(),
          reserva_ate=NULL,processing_started_at=NULL,
          versao_reserva=versao_reserva+1,ultimo_erro=%s
        WHERE id_consulta=%s AND status<>'concluida'""",
        (
            decisao["resultado"],
            Jsonb({"decisao": decisao, "fontes": {}}),
            decisao.get("motivo"),
            id_consulta,
        ),
    )
    return cursor.rowcount == 1


def marcar_aplicada(id_consulta, id_conversa, decisao, cursor):
    cursor.execute(
        """UPDATE chatbot.consulta_fireads SET aplicacao=%s,
        aplicado_em=clock_timestamp(),atualizado_em=clock_timestamp()
        WHERE id_consulta=%s AND id_conversa=%s AND status='concluida'
          AND aplicado_em IS NULL""",
        (Jsonb(decisao), id_consulta, id_conversa),
    )
    if cursor.rowcount != 1:
        raise ValueError("Consulta já aplicada ou não pertence à conversa")


def expirar(cursor):
    """Também limpa pendências abandonadas; unidades suspensas ficam preservadas."""
    cursor.execute("""UPDATE chatbot.consulta_fireads q SET status='concluida',
          consulta_concluida=TRUE,resultado='erro',
          dados=jsonb_build_object('decisao',jsonb_build_object(
            'resultado','erro','origem','organico','motivo','tempo_limite_300s',
            'dados_titular','{}'::jsonb),'fontes','{}'::jsonb),
          consultado_em=clock_timestamp(),atualizado_em=clock_timestamp(),
          reserva_ate=NULL,processing_started_at=NULL,
          versao_reserva=versao_reserva+1,ultimo_erro='tempo_limite_300s'
        FROM chatbot.unidade u WHERE u.id_unidade=q.id_unidade
          AND u.status_pagamento IS TRUE AND q.status<>'concluida'
          AND q.prazo_final<=clock_timestamp()""")
    return cursor.rowcount


def _chave(id_consulta):
    return f"chatbot:consulta_fireads:{id_consulta}"


def liberar_reserva(id_consulta, cursor):
    """A sessão mantém o advisory lock durante HTTP; close também o libera."""
    cursor.execute(
        "SELECT pg_advisory_unlock(hashtextextended(%s,0))", (_chave(id_consulta),)
    )
    return cursor.fetchone()[0]


def reservar(cursor):
    """Reserva entre processos e recupera queda sem esperar o prazo de 300s.

    A consulta de candidatos não adquire advisory locks. Cada lock é solicitado
    explicitamente para um único ID, evitando locks extras por avaliação do SQL.
    O orquestrador confirma a reserva antes de HTTP e mantém a conexão ociosa.
    """
    cursor.execute("""SELECT q.id_consulta FROM chatbot.consulta_fireads q
        JOIN chatbot.conversa c ON c.id_conversa=q.id_conversa
        JOIN chatbot.unidade u ON u.id_unidade=q.id_unidade
        JOIN chatbot.integracao_fireads i ON i.id_integracao_fireads=q.id_integracao_fireads
        WHERE q.status IN ('pendente','processando') AND q.prazo_final>clock_timestamp()
          AND c.status_ativa AND c.finalizou_em IS NULL AND c.id_etapa_atual IS NULL
          AND c.contexto_fireads IS NULL AND u.status_pagamento IS TRUE
          AND i.integracao_ativa AND i.contrato_validado
        ORDER BY q.solicitado_em,q.id_consulta LIMIT 100""")
    candidatos = [row[0] for row in cursor.fetchall()]
    for ident in candidatos:
        cursor.execute(
            "SELECT pg_try_advisory_lock(hashtextextended(%s,0))", (_chave(ident),)
        )
        if not cursor.fetchone()[0]:
            continue
        cursor.execute(
            """UPDATE chatbot.consulta_fireads q SET status='processando',
              tentativas=tentativas+1,versao_reserva=versao_reserva+1,
              processing_started_at=clock_timestamp(),reserva_ate=prazo_final,
              atualizado_em=clock_timestamp()
            FROM chatbot.conversa c,chatbot.unidade u,chatbot.integracao_fireads i
            WHERE q.id_consulta=%s AND q.status IN ('pendente','processando')
              AND q.prazo_final>clock_timestamp() AND c.id_conversa=q.id_conversa
              AND c.status_ativa AND c.finalizou_em IS NULL AND c.id_etapa_atual IS NULL
              AND c.contexto_fireads IS NULL AND u.id_unidade=q.id_unidade
              AND u.status_pagamento IS TRUE AND i.id_integracao_fireads=q.id_integracao_fireads
              AND i.integracao_ativa AND i.contrato_validado
              AND i.url_dashbord=q.entrada->>'url'
              AND i.aba_destino=q.entrada->>'aba' AND q.entrada->>'versao'='2'
              AND i.fuso_formularios IS NOT DISTINCT FROM q.entrada->>'fuso'
            RETURNING q.id_consulta,q.id_conversa,q.versao_reserva,q.entrada,
                      EXTRACT(EPOCH FROM q.prazo_final-clock_timestamp())""",
            (ident,),
        )
        row = cursor.fetchone()
        if row is not None:
            return dict(
                zip(
                    ("id_consulta", "id_conversa", "versao", "entrada", "restante"), row
                )
            )
        liberar_reserva(ident, cursor)
    return None


def concluir(reserva, resultado, cursor):
    """A gravação única inclui os registros e a decisão, sem resultados parciais."""
    decisao = resultado["decisao"]
    cursor.execute(
        """UPDATE chatbot.consulta_fireads q SET status='concluida',
          consulta_concluida=TRUE,resultado=%s,dados=%s,
          consultado_em=clock_timestamp(),atualizado_em=clock_timestamp(),
          reserva_ate=NULL,processing_started_at=NULL,ultimo_erro=%s
        FROM chatbot.conversa c,chatbot.unidade u,chatbot.integracao_fireads i
        WHERE q.id_consulta=%s AND q.versao_reserva=%s AND q.status='processando'
          AND q.reserva_ate>clock_timestamp() AND q.prazo_final>clock_timestamp()
          AND c.id_conversa=q.id_conversa AND c.status_ativa AND c.finalizou_em IS NULL
          AND c.id_etapa_atual IS NULL AND c.contexto_fireads IS NULL
          AND u.id_unidade=q.id_unidade AND u.status_pagamento IS TRUE
          AND i.id_integracao_fireads=q.id_integracao_fireads AND i.integracao_ativa
          AND i.url_dashbord=q.entrada->>'url'
          AND i.aba_destino=q.entrada->>'aba' AND q.entrada->>'versao'='2'
          AND i.contrato_validado
          AND i.fuso_formularios IS NOT DISTINCT FROM q.entrada->>'fuso'""",
        (
            decisao["resultado"],
            Jsonb(resultado),
            decisao.get("motivo") if decisao["resultado"] == "erro" else None,
            reserva["id_consulta"],
            reserva["versao"],
        ),
    )
    return cursor.rowcount == 1
