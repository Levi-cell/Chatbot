from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class PoliticaEtapa:
    id_etapa: int
    encerra_automaticamente: bool
    bloqueio_dias: int
    elegivel_funil: bool


@dataclass(frozen=True)
class BloqueioConversa:
    finalizou_em: datetime
    bloqueio_dias: int


def buscar_politica_etapa(id_etapa, cursor):
    cursor.execute(
        """
        SELECT
            id_etapa,
            encerra_automaticamente,
            bloqueio_dias,
            elegivel_funil
        FROM chatbot.etapa
        WHERE id_etapa = %s
        LIMIT 1;
        """,
        (id_etapa,),
    )

    resultado = cursor.fetchone()

    if not resultado:
        raise ValueError(
            f"Política da etapa {id_etapa} não encontrada"
        )

    return PoliticaEtapa(
        id_etapa=resultado[0],
        encerra_automaticamente=bool(resultado[1]),
        bloqueio_dias=int(resultado[2] or 0),
        elegivel_funil=bool(resultado[3]),
    )


def buscar_bloqueio_conversa_por_id(id_conversa, cursor):
    cursor.execute(
        """
        SELECT
            c.finalizou_em,
            e.bloqueio_dias
        FROM chatbot.conversa c
        JOIN chatbot.etapa e
          ON e.id_etapa = c.id_etapa_atual
        WHERE c.id_conversa = %s
          AND c.status_ativa = FALSE
          AND c.finalizou_em IS NOT NULL
          AND e.bloqueio_dias > 0
        LIMIT 1;
        """,
        (id_conversa,),
    )

    return _montar_bloqueio(cursor.fetchone())


def buscar_bloqueio_ativo_por_cliente_unidade(
    cliente_telefone,
    id_phone_unidade,
    cursor,
):
    cursor.execute(
        """
        SELECT
            c.finalizou_em,
            e.bloqueio_dias
        FROM chatbot.conversa c
        JOIN chatbot.cliente cl
          ON cl.id_cliente = c.id_cliente
        JOIN chatbot.unidade u
          ON u.id_unidade = c.id_unidade
        JOIN chatbot.etapa e
          ON e.id_etapa = c.id_etapa_atual
        WHERE cl.waid_telefone = %s
          AND u.phone_number_id = %s
          AND u.status_pagamento = TRUE
          AND c.status_ativa = FALSE
          AND c.finalizou_em IS NOT NULL
          AND e.bloqueio_dias > 0
          AND c.finalizou_em
              > NOW() - (e.bloqueio_dias * INTERVAL '1 day')
        ORDER BY c.finalizou_em DESC
        LIMIT 1;
        """,
        (cliente_telefone, id_phone_unidade),
    )

    return _montar_bloqueio(cursor.fetchone())


def _montar_bloqueio(resultado):
    if not resultado:
        return None

    return BloqueioConversa(
        finalizou_em=resultado[0],
        bloqueio_dias=int(resultado[1]),
    )
