"""Payload durável de todos os envios ao Funil, inclusive sem FireAds."""

from psycopg.types.json import Jsonb


def buscar(id_conversa, cursor):
    cursor.execute(
        """SELECT f.snapshot, d.snapshot FROM chatbot.funil_envios f
        LEFT JOIN chatbot.envios_dash d USING (id_conversa)
        WHERE f.id_conversa=%s FOR UPDATE OF f""", (id_conversa,),
    )
    row = cursor.fetchone()
    if row is None:
        raise ValueError("Envio ao Funil inexistente")
    if row[0] is not None:
        if row[0].get("versao") != 1:
            raise ValueError("Versão de snapshot Funil desconhecida")
        return row[0]
    if row[1] is not None:
        legado = row[1]
        return salvar(id_conversa, legado["payload_funil"], legado["canal"],
                      legado["url_funil"], cursor)
    return None


def salvar(id_conversa, payload, canal, url, cursor):
    snapshot = {"versao": 1, "payload_funil": payload, "canal": canal, "url_funil": url}
    cursor.execute(
        """UPDATE chatbot.funil_envios SET snapshot=%s
        WHERE id_conversa=%s AND snapshot IS NULL AND status='processing'""",
        (Jsonb(snapshot), id_conversa),
    )
    if cursor.rowcount != 1:
        raise ValueError("Snapshot Funil já existe ou reserva indisponível")
    return snapshot


def conferir(envio, snapshot, cursor, *, lease_segundos=900):
    cursor.execute(
        """SELECT 1 FROM chatbot.funil_envios f
        JOIN chatbot.conversa c USING (id_conversa)
        JOIN chatbot.unidade u ON u.id_unidade=c.id_unidade
        JOIN chatbot.atendimento_customizado ac ON ac.id_unidade=u.id_unidade
        JOIN chatbot.etapa e ON e.id_etapa=c.id_etapa_atual
        JOIN chatbot.integracao_funil_unidade i ON i.id_unidade=u.id_unidade
        WHERE f.id_funil_envio=%s AND f.id_conversa=%s
          AND f.status='processing' AND f.attempt_count=%s
          AND f.processing_started_at>clock_timestamp()-(%s * INTERVAL '1 second')
          AND u.status_pagamento IS TRUE AND i.integracao_ativa AND i.widget_ativo
          AND i.link_api_carrossel=%s AND c.lead_no_funil IS NOT TRUE
          AND e.elegivel_funil AND (
            (NULLIF(BTRIM(ac.link_agendamento),'') IS NOT NULL AND c.id_etapa_atual>=20)
            OR (NULLIF(BTRIM(ac.link_agendamento),'') IS NULL
                AND (c.id_etapa_atual=19 OR c.id_etapa_atual>=21)))
        FOR UPDATE OF f""",
        (envio["id_funil_envio"], envio["id_conversa"], envio["attempt_count"],
         lease_segundos, snapshot["url_funil"]),
    )
    if cursor.fetchone() is None:
        raise ValueError("Envio congelado perdeu elegibilidade, reserva ou configuração")
