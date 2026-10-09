"""Consulta o diagnóstico gravado da abertura FireAds, sem alterar o atendimento."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('numero')
    parser.add_argument('--dashboard', action='store_true',
                        help='Confere o telefone nas abas configuradas, somente por GET.')
    args = parser.parse_args()
    from utilitarios.bootstrap import configurar_ambiente_utilitario
    from utilitarios.maintenance.remover_contato import formatos

    configurar_ambiente_utilitario()
    from core.database.connection_aws import get_conn
    from psycopg.rows import dict_row

    with get_conn(application_name='diagnostico_abertura_fireads', connect_timeout=8) as conn:
        with conn.transaction():
            conn.execute('SET TRANSACTION READ ONLY')
            conn.execute("SET LOCAL statement_timeout = '15s'")
            with conn.cursor(row_factory=dict_row) as cursor:
                cursor.execute("""
                    SELECT c.id_conversa, u.nome_unidade, cl.waid_telefone,
                           c.iniciou_em, c.id_etapa_atual, c.origem_fireads,
                           c.contexto_fireads->>'resultado' AS resultado_contexto,
                           c.contexto_fireads->>'motivo' AS motivo_contexto,
                           q.consulta_concluida, q.resultado, q.consultado_em,
                           q.dados->>'motivo' AS motivo_consulta,
                           i.integracao_ativa, i.contrato_validado, i.ativada_em,
                           i.aba_google, i.aba_meta, i.aba_destino, i.url_dashbord,
                           i.fuso_formularios
                    FROM chatbot.cliente cl
                    JOIN chatbot.conversa c ON c.id_cliente=cl.id_cliente
                    JOIN chatbot.unidade u ON u.id_unidade=c.id_unidade
                    LEFT JOIN chatbot.consulta_fireads q
                        ON q.id_conversa_referencia=c.id_conversa
                    LEFT JOIN chatbot.integracao_fireads i ON i.id_unidade=c.id_unidade
                    WHERE regexp_replace(cl.waid_telefone,'[^0-9]','','g')=ANY(%s)
                    ORDER BY c.id_conversa DESC LIMIT 5
                """, (formatos(args.numero),))
                registros = cursor.fetchall()
                print(json.dumps([{k: v for k, v in r.items() if k != 'url_dashbord'}
                                  for r in registros], ensure_ascii=False, default=str, indent=2), flush=True)
    if args.dashboard and registros:
        import requests
        from concurrent.futures import ThreadPoolExecutor
        from core.integrations.fireads.contrato import telefone, localizar
        from utilitarios.fireAds.test_Dash import limpar_numero

        registro = next((r for r in registros if r.get('url_dashbord')), None)
        if not registro:
            raise ValueError('Não há configuração FireAds para estas conversas.')
        alvos = set(formatos(args.numero))
        fontes = {}

        def consultar(aba):
            try:
                resposta = requests.get(registro['url_dashbord'],
                                        params={'sheet': aba, 'abas': '0'}, timeout=(5, 25))
                resposta.raise_for_status()
                corpo = resposta.json()
                dados = corpo.get('data', {})
                if corpo.get('success') is not True or dados.get('aba') != aba:
                    return {'aba': aba, 'erro': 'Resposta recusada ou aba divergente'}
                fontes[aba] = dados
                campos = [h for h in dados['headers'] if any(
                    p in str(h).lower() for p in ('phone', 'telefone', 'whatsapp', 'celular'))]
                encontrados = []
                for row in dados['rows']:
                    if not any(limpar_numero(row.get(c)) in alvos for c in campos):
                        continue
                    resumo = {k: row.get(k) for k in ('_row', 'Nome', 'full_name',
                              'Perfil/Faixa', 'para_quem', 'Canal', 'Data/Hora', 'created_time') if k in row}
                    resumo.update({c: row.get(c) for c in campos})
                    resumo['corresponde_telefone_exato_worker'] = any(
                        telefone(row.get(c)) == telefone(registro['waid_telefone']) for c in campos)
                    resumo['corresponde_busca_local_com_variantes'] = any(
                        localizar([row], registro['waid_telefone'], c) for c in campos)
                    encontrados.append(resumo)
                return {'aba': aba, 'encontrados': encontrados}
            except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
                return {'aba': aba, 'erro': type(exc).__name__}

        abas = list(dict.fromkeys(registro[k] for k in ('aba_google', 'aba_meta', 'aba_destino')))
        with ThreadPoolExecutor(max_workers=3) as pool:
            for resultado in pool.map(consultar, abas):
                print(json.dumps(resultado, ensure_ascii=False, indent=2), flush=True)
        if registro['aba_google'] in fontes and registro['aba_meta'] in fontes:
            from workers.worker_flow.fireads import interpretar

            decisao = interpretar(fontes[registro['aba_google']]['rows'],
                                  fontes[registro['aba_meta']]['rows'],
                                  registro['waid_telefone'], registro['fuso_formularios'])
            print(json.dumps({'simulacao_local_sem_gravacao': {
                k: decisao.get(k) for k in ('resultado', 'origem', 'motivo', 'status_dependente')
            }}, ensure_ascii=False, indent=2), flush=True)


if __name__ == '__main__':
    main()
