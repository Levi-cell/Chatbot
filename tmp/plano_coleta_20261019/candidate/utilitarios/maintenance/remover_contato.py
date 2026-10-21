"""Consulta e remoção pontual do contato, sem reset global de banco/cache."""

import argparse
import json
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def normalizar(valor):
    numero = re.sub(r'[^0-9]', '', str(valor or ''))
    return numero[2:] if len(numero) in (12, 13) and numero.startswith('55') else numero


def formatos(numero):
    from utilitarios.fireAds.test_Dash import gerar_formatos_dashboard
    internacionais = gerar_formatos_dashboard(numero)
    return sorted(set(internacionais + [n[2:] for n in internacionais]))


def auditar_banco(conn, numero):
    from psycopg import sql

    dados = {}
    with conn.transaction():
        conn.execute('SET TRANSACTION READ ONLY')
        conn.execute("SET LOCAL statement_timeout = '25s'")
        colunas = conn.execute("""
            SELECT c.table_name, c.column_name FROM information_schema.columns c
            JOIN information_schema.tables t USING (table_schema, table_name)
            WHERE c.table_schema='chatbot' AND t.table_type='BASE TABLE'
              AND (c.column_name IN ('waid_telefone','cliente_telefone','wa_id_cliente')
                   OR c.column_name IN ('id_cliente','id_conversa','id_chat'))
              AND NOT EXISTS (SELECT 1 FROM pg_inherits i
                  WHERE i.inhrelid=to_regclass('chatbot.' || quote_ident(c.table_name)))
            ORDER BY c.table_name, c.ordinal_position
        """).fetchall()
        dados['colunas'] = colunas
        dados['clientes'] = conn.execute("""
            SELECT id_cliente,waid_telefone FROM chatbot.cliente
            WHERE regexp_replace(waid_telefone,'[^0-9]','','g')=ANY(%s)
        """, (formatos(numero),)).fetchall()
        ids = [r[0] for r in dados['clientes']]
        dados['conversas'] = conn.execute("""
            SELECT id_conversa,id_unidade,id_etapa_atual,status_ativa,processing
            FROM chatbot.conversa WHERE id_cliente=ANY(%s) ORDER BY id_conversa
        """, (ids,)).fetchall()
        dados['unidades'] = conn.execute(
            'SELECT id_unidade,phone_number_id FROM chatbot.unidade ORDER BY id_unidade'
        ).fetchall()
        dados['fks'] = conn.execute("""
            SELECT conrelid::regclass::text, confrelid::regclass::text,
                   pg_get_constraintdef(oid)
            FROM pg_constraint WHERE contype='f' AND connamespace='chatbot'::regnamespace
              AND confrelid IN ('chatbot.cliente'::regclass,'chatbot.conversa'::regclass,
                  'chatbot.chat'::regclass,'chatbot.fila_mensagens'::regclass,
                  'chatbot.historico_mensagens'::regclass)
              AND conparentid=0 ORDER BY 1,2
        """).fetchall()
        contagens = {}
        for tabela, coluna in colunas:
            if coluna in ('waid_telefone','cliente_telefone','wa_id_cliente'):
                query = sql.SQL("SELECT count(*) FROM chatbot.{} WHERE regexp_replace({}::text,'[^0-9]','','g')=ANY(%s)").format(
                    sql.Identifier(tabela), sql.Identifier(coluna))
                contagens[tabela + '.' + coluna] = conn.execute(query, (formatos(numero),)).fetchone()[0]
        dados['contagens_telefone'] = contagens
    return dados


def auditar_cache(numero, unidades, hashes_mensagens=()):
    from core.cache.redis_client import get_redis_safe
    redis = get_redis_safe(retries=1, delay=0)
    chaves = set()
    for telefone in formatos(numero):
        chave = 'cliente_cache:' + telefone
        if redis.exists(chave):
            chaves.add(chave)
        for _, phone_id in unidades:
            digest = hashlib.sha256(f'{phone_id}:{telefone}'.encode()).hexdigest()
            chave = 'conversa_bloqueada:' + digest
            if redis.exists(chave):
                chaves.add(chave)
            chaves.update(redis.scan_iter(match=f'webhook_flood_rate:{{{digest}}}:*', count=200))
    for hash_mensagem in hashes_mensagens:
        digest = hashlib.sha256(str(hash_mensagem).strip().encode()).hexdigest()
        chave = 'webhook_erro_inesperado:' + digest
        if redis.exists(chave):
            chaves.add(chave)
    return redis, sorted(chaves)


def limpar_residuos(conn, numero, dados):
    """Limpa fila órfã e Redis após a exclusão manual do cliente no banco.

    Não remove clientes/conversas ainda existentes nem mensagens em processamento.
    Os identificadores das mensagens são coletados antes da exclusão para localizar
    eventuais contadores do webhook no Redis sem limpar caches de outros contatos.
    """
    if dados['clientes'] or dados['conversas']:
        raise ValueError('O cliente ainda existe. Esta opção limpa apenas resíduos.')
    variantes = formatos(numero)
    hashes = set()
    with conn.transaction():
        conn.execute("SET LOCAL lock_timeout = '5s'")
        conn.execute("SET LOCAL statement_timeout = '25s'")
        if conn.execute("""
            SELECT 1 FROM chatbot.cliente
            WHERE regexp_replace(waid_telefone,'[^0-9]','','g')=ANY(%s)
        """, (variantes,)).fetchone():
            raise ValueError('Cliente recriado durante a conferência; nenhuma exclusão.')
        mensagens = conn.execute("""
            SELECT id_mensagem, id_conversa, status, id_hash_msg
            FROM chatbot.fila_mensagens
            WHERE regexp_replace(cliente_telefone,'[^0-9]','','g')=ANY(%s)
            FOR UPDATE
        """, (variantes,)).fetchall()
        if any(row[1] is not None or row[2] == 'processing' for row in mensagens):
            raise ValueError('Há mensagem vinculada ou em processamento; exclusão cancelada.')
        hashes.update(row[3] for row in mensagens if row[3])
        redis, chaves = auditar_cache(numero, dados['unidades'], hashes)
        removidos = conn.execute("""
            DELETE FROM chatbot.fila_mensagens
            WHERE id_mensagem=ANY(%s)
              AND regexp_replace(cliente_telefone,'[^0-9]','','g')=ANY(%s)
              AND id_conversa IS NULL AND status IS DISTINCT FROM 'processing'
        """, ([row[0] for row in mensagens], variantes)).rowcount
        if removidos != len(mensagens):
            raise RuntimeError('Contagem divergente; exclusão revertida.')

    # Redis só é alterado após a confirmação da transação do banco.
    removidas_cache = sum(redis.delete(chave) for chave in chaves)
    _, restantes_cache = auditar_cache(numero, dados['unidades'], hashes)
    depois = auditar_banco(conn, numero)
    resultado = {
        'mensagens_orfas_removidas': removidos,
        'chaves_redis_removidas': removidas_cache,
        'chaves_redis_restantes': restantes_cache,
        'registros_restantes_banco': depois['contagens_telefone'],
    }
    print(json.dumps(resultado, ensure_ascii=False, indent=2), flush=True)
    if restantes_cache or any(depois['contagens_telefone'].values()):
        raise RuntimeError('A verificação encontrou resíduos; conferir o resultado acima.')


def contar_vinculos(conn, dados, variantes, clientes, conversas, chats):
    """Conta os registros pelo telefone e pelos vínculos antes/depois da exclusão."""
    from psycopg import sql

    tabelas = {}
    for tabela, coluna in dados['colunas']:
        tabelas.setdefault(tabela, []).append(coluna)
    contagens = {}
    for tabela, colunas in tabelas.items():
        filtros, parametros = [], []
        for coluna in colunas:
            identificador = sql.Identifier(coluna)
            if coluna in ('waid_telefone', 'cliente_telefone', 'wa_id_cliente'):
                filtros.append(sql.SQL("regexp_replace({}::text,'[^0-9]','','g')=ANY(%s)").format(identificador))
                parametros.append(variantes)
            elif coluna in ('id_cliente', 'id_conversa', 'id_chat'):
                filtros.append(sql.SQL('{}=ANY(%s)').format(identificador))
                parametros.append({'id_cliente': clientes, 'id_conversa': conversas, 'id_chat': chats}[coluna])
        query = sql.SQL('SELECT count(*) FROM chatbot.{} WHERE {}').format(
            sql.Identifier(tabela), sql.SQL(' OR ').join(filtros))
        contagens[tabela] = conn.execute(query, parametros).fetchone()[0]
    return contagens


def excluir_contato(conn, numero, dados):
    """Exclui somente este contato; as FKs removem seus registros dependentes.

    A fila e os bloqueios exigem exclusão explícita porque suas FKs usam SET NULL.
    Uma operação em andamento cancela a transação, evitando disputar com workers.
    Nenhuma integração externa é chamada.
    """
    from psycopg import sql

    variantes = formatos(numero)
    hashes = set()
    with conn.transaction():
        conn.execute("SET LOCAL lock_timeout = '5s'")
        conn.execute("SET LOCAL statement_timeout = '30s'")
        clientes = [r[0] for r in conn.execute("""
            SELECT id_cliente FROM chatbot.cliente
            WHERE regexp_replace(waid_telefone,'[^0-9]','','g')=ANY(%s)
            ORDER BY id_cliente FOR UPDATE
        """, (variantes,)).fetchall()]
        chats = [r[0] for r in conn.execute("""
            SELECT id_chat FROM chatbot.chat WHERE id_cliente=ANY(%s)
            ORDER BY id_chat FOR UPDATE
        """, (clientes,)).fetchall()]
        registros = conn.execute("""
            SELECT id_conversa, processing FROM chatbot.conversa
            WHERE id_cliente=ANY(%s) ORDER BY id_conversa FOR UPDATE
        """, (clientes,)).fetchall()
        if any(r[1] for r in registros):
            raise RuntimeError('Conversa em processamento; nenhuma exclusão confirmada.')
        conversas = [r[0] for r in registros]
        for tabela in ('funil_envios', 'envios_dash'):
            estados = conn.execute(sql.SQL("""
                SELECT status FROM chatbot.{} WHERE id_conversa=ANY(%s) FOR UPDATE
            """).format(sql.Identifier(tabela)), (conversas,)).fetchall()
            if any(r[0] == 'processing' for r in estados):
                raise RuntimeError(f'Envio em processamento em {tabela}; exclusão cancelada.')
        mensagens = conn.execute("""
            SELECT id_mensagem, status, id_hash_msg, id_conversa
            FROM chatbot.fila_mensagens
            WHERE regexp_replace(cliente_telefone,'[^0-9]','','g')=ANY(%s)
               OR id_conversa=ANY(%s)
            ORDER BY id_mensagem FOR UPDATE
        """, (variantes, conversas)).fetchall()
        if any(r[1] == 'processing' or (r[3] is not None and r[3] not in conversas)
               for r in mensagens):
            raise RuntimeError('Mensagem ocupada ou vinculada a outro contato; exclusão cancelada.')
        hashes.update(r[2] for r in mensagens if r[2])
        hashes.update(r[0] for r in conn.execute("""
            SELECT id_hash_msg FROM chatbot.historico_mensagens
            WHERE regexp_replace(cliente_telefone,'[^0-9]','','g')=ANY(%s)
               OR id_conversa=ANY(%s)
            UNION
            SELECT id_hash_msg FROM chatbot.webhook_flood_evento
            WHERE regexp_replace(wa_id_cliente,'[^0-9]','','g')=ANY(%s)
        """, (variantes, conversas, variantes)).fetchall() if r[0])
        antes = contar_vinculos(conn, dados, variantes, clientes, conversas, chats)
        redis, chaves = auditar_cache(numero, dados['unidades'], hashes)

        conn.execute('DELETE FROM chatbot.fila_mensagens WHERE id_mensagem=ANY(%s)',
                     ([r[0] for r in mensagens],))
        conn.execute("""
            DELETE FROM chatbot.cliente_bloqueado_meta
            WHERE id_cliente=ANY(%s)
               OR regexp_replace(wa_id_cliente,'[^0-9]','','g')=ANY(%s)
        """, (clientes, variantes))
        conn.execute("""
            DELETE FROM chatbot.webhook_flood_evento
            WHERE regexp_replace(wa_id_cliente,'[^0-9]','','g')=ANY(%s)
        """, (variantes,))
        conn.execute("""
            DELETE FROM chatbot.historico_mensagens
            WHERE regexp_replace(cliente_telefone,'[^0-9]','','g')=ANY(%s)
        """, (variantes,))
        conn.execute('DELETE FROM chatbot.cliente WHERE id_cliente=ANY(%s)', (clientes,))
        restantes = contar_vinculos(conn, dados, variantes, clientes, conversas, chats)
        if any(restantes.values()):
            raise RuntimeError('Restaram vínculos; a exclusão do banco será revertida.')

    removidas_cache = sum(redis.delete(chave) for chave in chaves)
    _, restantes_cache = auditar_cache(numero, dados['unidades'], hashes)
    depois = auditar_banco(conn, numero)
    resultado = {
        'numero': numero,
        'registros_removidos': {k: v for k, v in antes.items() if v},
        'chaves_redis_removidas': removidas_cache,
        'registros_restantes_banco': depois['contagens_telefone'],
        'vinculos_restantes': restantes,
        'chaves_redis_restantes': restantes_cache,
    }
    print(json.dumps(resultado, ensure_ascii=False, indent=2), flush=True)
    if restantes_cache or any(depois['contagens_telefone'].values()):
        raise RuntimeError('A conferência após o commit encontrou registros; conferir o resultado.')


def auditar_dashboard(numero):
    import requests
    from concurrent.futures import ThreadPoolExecutor
    from utilitarios.fireAds.config_teste import URL_DASHBOARD
    from core.integrations.fireads.cliente import ClienteFireAds

    resposta = requests.get(URL_DASHBOARD, params={'list':'sheets'}, timeout=(5,30))
    resposta.raise_for_status()
    body = resposta.json()
    if body.get('success') is not True or not isinstance(body.get('data', {}).get('sheets'), list):
        raise ValueError('Inventário do dashboard inválido')
    abas = body['data']['sheets']

    def consultar(aba):
        cliente = ClienteFireAds(URL_DASHBOARD, segundos=40)
        try:
            dados = cliente.consultar(aba['nome'])
            campos = [h for h in dados['headers'] if any(p in str(h).lower() for p in ('phone','telefone','whatsapp','celular'))]
            alvo = set(formatos(numero))
            encontrados = [r for r in dados['rows'] if any(
                re.sub(r'[^0-9]', '', str(r.get(c, '') or '')) in alvo for c in campos)]
            return {'aba': aba['nome'], 'total':len(dados['rows']), 'campos_telefone':campos,
                    'encontrados': [{k:v for k,v in r.items() if k in ('_row','Nome','full_name','Data/Hora','created_time') or k in campos} for r in encontrados]}
        except Exception as exc:
            return {'aba':aba['nome'], 'erro':type(exc).__name__}
        finally:
            cliente.close()

    with ThreadPoolExecutor(max_workers=3) as pool:
        resultados = list(pool.map(consultar, [a for a in abas if a.get('disponivel')]))
    return {'inventario': abas, 'resultados':resultados}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('numero', nargs='+')
    parser.add_argument('--env-file')
    parser.add_argument('--dashboard', action='store_true')
    operacao = parser.add_mutually_exclusive_group()
    operacao.add_argument('--limpar-residuos', action='store_true',
                         help='Remove fila órfã e Redis se o cliente já foi excluído.')
    operacao.add_argument('--excluir', action='store_true',
                         help='Exclui o contato e seus vínculos no banco e no Redis.')
    parser.add_argument('--resumo', action='store_true', help='Exibe somente alvos e contagens.')
    args = parser.parse_args()
    numeros = list(dict.fromkeys(normalizar(n) for n in args.numero))
    if any(len(n) not in (10, 11) for n in numeros):
        parser.error('Informe celulares brasileiros completos, com DDD.')
    from utilitarios.bootstrap import configurar_ambiente_utilitario
    configurar_ambiente_utilitario(args.env_file)
    from core.database.connection_aws import get_conn
    for numero in numeros:
        with get_conn(application_name='utilitario_remover_contato', connect_timeout=8) as conn:
            dados = auditar_banco(conn, numero)
            if args.excluir:
                excluir_contato(conn, numero, dados)
                continue
            if args.limpar_residuos:
                limpar_residuos(conn, numero, dados)
                continue
            _, chaves = auditar_cache(numero, dados['unidades'])
            exibicao = dados if not args.resumo else {
                k: dados[k] for k in ('clientes', 'conversas', 'contagens_telefone')
            }
            print(json.dumps({'numero': numero, 'formatos': formatos(numero),
                              **exibicao, 'cache': chaves},
                             ensure_ascii=False, default=str, indent=2), flush=True)
        if args.dashboard:
            print(json.dumps(auditar_dashboard(numero), ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    main()
