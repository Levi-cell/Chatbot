"""Congela a decisão de update/create sob a mesma reserva do envio."""

from psycopg.types.json import Jsonb
from core.repositories.fireads.envios import conferir_posse


def salvar_destino(envio, destino, cursor):
    conferir_posse(envio, cursor)
    cursor.execute("""UPDATE chatbot.envios_dash SET snapshot=jsonb_set(snapshot,'{destino}',%s),
                      atualizado_em=clock_timestamp()
                      WHERE id_envio_dash=%s AND status='processing' AND attempt_count=%s
                        AND (snapshot->'destino' IS NULL OR snapshot->'destino'='null'::jsonb)
                      RETURNING snapshot""", (Jsonb(destino), envio['id'], envio['tentativa']))
    row = cursor.fetchone()
    if row is None:
        raise ValueError('Destino já congelado ou reserva perdida')
    return row[0]
