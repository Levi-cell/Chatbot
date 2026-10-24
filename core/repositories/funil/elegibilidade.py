"""Predicado compartilhado de etapa e rota; aliases SQL internos c, e, ac."""

ETAPA_ELEGIVEL_SQL = """(
    e.elegivel_funil IS TRUE AND (
        (NULLIF(BTRIM(ac.link_agendamento), '') IS NOT NULL AND c.id_etapa_atual >= 20)
        OR (NULLIF(BTRIM(ac.link_agendamento), '') IS NULL
            AND (c.id_etapa_atual = 19 OR c.id_etapa_atual >= 21))
    )
)"""
