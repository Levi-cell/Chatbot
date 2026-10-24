"""Pendências de origem por estado, sem fila nova ou transações durante HTTP."""

from psycopg.types.json import Jsonb
from core.repositories.funil.elegibilidade import ETAPA_ELEGIVEL_SQL

CHAVE_LOCK = 'chatbot:worker_origem_fireads:v1'
JOINS = """FROM chatbot.conversa c
    JOIN chatbot.unidade u ON u.id_unidade=c.id_unidade
    JOIN chatbot.cliente cl ON cl.id_cliente=c.id_cliente
    JOIN chatbot.atendimento_customizado ac ON ac.id_unidade=c.id_unidade
    JOIN chatbot.integracao_fireads i ON i.id_unidade=c.id_unidade
    JOIN chatbot.etapa e ON e.id_etapa=c.id_etapa_atual"""
ELEGIVEL = f"""
    c.iniciou_em >= %s AND c.iniciou_em >= i.ativada_em
    AND u.status_pagamento IS TRUE AND i.integracao_ativa AND i.contrato_validado
    AND c.contexto_coleta->>'status'='pronto'
    AND c.contexto_coleta->>'id_conversa'=c.id_conversa::text
    AND c.contexto_fireads->>'id_conversa'=c.id_conversa::text
    AND c.contexto_fireads->>'id_integracao'=i.id_integracao_fireads::text
    AND c.contexto_fireads @> '{{"concluida":true,"id_consulta":null,"motivo":"canal_pendente_entrega"}}'
    AND NOT (c.contexto_fireads ? 'atribuicao_monitoramento')
    AND NOT (c.contexto_fireads ? 'verificacao_origem')
    AND COALESCE(c.contexto_fireads->>'canal_confirmado_entrega','false') <> 'true'
    AND NOT EXISTS (SELECT 1 FROM chatbot.consulta_fireads q WHERE q.id_conversa=c.id_conversa)
    AND NOT ({ETAPA_ELEGIVEL_SQL})
    AND c.lead_no_funil IS NOT TRUE AND c.lead_no_dash IS NOT TRUE
    AND NOT EXISTS (SELECT 1 FROM chatbot.funil_envios f WHERE f.id_conversa=c.id_conversa)
    AND NOT EXISTS (SELECT 1 FROM chatbot.envios_dash d WHERE d.id_conversa=c.id_conversa)
"""
COLUNAS = ('id_conversa', 'id_unidade', 'id_integracao', 'url', 'aba', 'fuso', 'numero')
SELECT = """SELECT c.id_conversa,c.id_unidade,i.id_integracao_fireads,
    i.url_dashbord,i.aba_destino,i.fuso_formularios,cl.waid_telefone """


def adquirir_ciclo(cursor):
    cursor.execute('SELECT pg_try_advisory_lock(hashtextextended(%s,0))', (CHAVE_LOCK,))
    return cursor.fetchone()[0]


def limite_ciclo(cursor):
    cursor.execute('SELECT COALESCE(MAX(id_conversa),0) FROM chatbot.conversa')
    return cursor.fetchone()[0]


def listar(cursor, desde, *, apos=0, ate, limite=100):
    cursor.execute(SELECT + JOINS + f""" WHERE {ELEGIVEL}
        AND c.id_conversa>%s AND c.id_conversa<=%s
        ORDER BY c.id_conversa LIMIT %s""", (desde, apos, ate, limite))
    return [dict(zip(COLUNAS, row)) for row in cursor.fetchall()]


def revalidar_grupo(cursor, candidatos, desde):
    """Releitura sem lock antes do HTTP, após eventuais esperas por outras abas."""
    config = candidatos[0]
    cursor.execute(SELECT + JOINS + f""" WHERE {ELEGIVEL}
        AND c.id_conversa=ANY(%s) AND i.id_integracao_fireads=%s
        AND i.url_dashbord=%s AND i.aba_destino=%s
        AND i.fuso_formularios IS NOT DISTINCT FROM %s ORDER BY c.id_conversa""",
        (desde, [c['id_conversa'] for c in candidatos], config['id_integracao'],
         config['url'], config['aba'], config['fuso']))
    return [dict(zip(COLUNAS, row)) for row in cursor.fetchall()]


def concluir(cursor, candidato, resultado, desde):
    """Revalida sob locks curtos; preserva chaves gravadas pelo atendimento."""
    cursor.execute(SELECT + JOINS + f""" WHERE {ELEGIVEL} AND c.id_conversa=%s
        AND i.id_integracao_fireads=%s AND i.url_dashbord=%s AND i.aba_destino=%s
        AND i.fuso_formularios IS NOT DISTINCT FROM %s AND cl.waid_telefone=%s
        FOR UPDATE OF c,u,i,ac,cl,e""",
        (desde, candidato['id_conversa'], candidato['id_integracao'], candidato['url'],
         candidato['aba'], candidato['fuso'], candidato['numero']))
    if cursor.fetchone() is None:
        return False
    cursor.execute('''UPDATE chatbot.conversa
        SET contexto_fireads=contexto_fireads || %s WHERE id_conversa=%s''',
        (Jsonb(resultado), candidato['id_conversa']))
    return cursor.rowcount == 1
