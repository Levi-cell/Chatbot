"""Última conversa no período, isolamento de unidade e métricas com SQL real."""
import unittest
from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
from django.db import connections
from django.db.backends.postgresql.base import DatabaseWrapper
from psycopg.conninfo import conninfo_to_dict
from psycopg.types.json import Jsonb

from tests.integration import test_fireads_postgres as base
from tests.unit.test_monitoramento_origens import contexto, ROW
from core.integrations.fireads.atribuicao import CHAVE, capturar
from core.integrations.fireads.contrato import ABA_DESTINO
from core.repositories.monitoramento import painel
from callback.monitoramento import services
from callback.monitoramento.periodos import resolver_periodo
from callback.monitoramento.apresentacao import consolidar_conversas
from callback.monitoramento.origens import montar_origens


@unittest.skipUnless(base.DSN, 'Exige PostgreSQL descartável em loopback')
class PainelFireAdsPostgresTests(unittest.TestCase):
    setUp = base.FireAdsPostgresTests.setUp
    limpar = base.FireAdsPostgresTests.limpar

    def conversa(self, data, canal, etapa=4, dependente=False):
        cid = self.conn.execute('''INSERT INTO chatbot.conversa
            (id_cliente,id_unidade,id_chat,status_ativa,iniciou_em,id_etapa_atual,status_dependente)
            VALUES (1,1,(SELECT id_chat FROM chatbot.chat WHERE id_cliente=1 AND id_unidade=1),FALSE,%s,%s,%s)
            RETURNING id_conversa''', (data, etapa, dependente)).fetchone()[0]
        ctx = contexto(cid, canal, 'QR001')
        origem = ctx[CHAVE]['canal']
        ctx.update(origem=origem, id_conversa=cid, concluida=True)
        self.conn.execute('UPDATE chatbot.conversa SET origem_fireads=%s,contexto_fireads=%s WHERE id_conversa=%s',
                          (origem, Jsonb(ctx), cid))
        self.conn.execute('''INSERT INTO chatbot.historico_mensagens
            (id_conversa,received_data_hora,cliente_telefone,tipo_mensagem,id_hash_msg,
             id_phone_unidade,unidade_telefone,quem_enviou,conteudo_texto)
            VALUES (%s,%s,'5511999990002','text',%s,'phone-teste','5511999990000','cliente','Olá')''',
                          (cid, data, f'wamid.test.{cid}'))
        return cid

    def test_perfil_por_origem_usa_idade_do_participante_e_conversa_no_periodo(self):
        dep = self.conversa('2026-10-01', 'Google Ads', dependente=True)
        self.conversa('2026-10-02', 'Google Ads')
        self.conversa('2026-10-03', 'Meta Ads', etapa=1)
        self.conn.execute('UPDATE chatbot.cliente SET idade=65 WHERE id_cliente=1')
        self.conn.execute('INSERT INTO chatbot.dependente(id_cliente,id_conversa,nome_dependente,idade) VALUES(1,%s,%s,%s)',
                          (dep, 'Dependente fictício', 13))
        self.conn.execute("INSERT INTO chatbot.funil_envios(id_conversa,status,enviado_em) VALUES(%s,'sent','2026-10-01 12:00')", (dep,))
        r = montar_origens(painel.buscar_origens(1, '2026-10-01', '2026-10-04', self.cursor))
        google = next(c for c in r['canais'] if c['canal']=='google')
        self.assertEqual((google['atendimentos'], google['funil']), (2, 1))
        self.assertEqual({p['chave']: (p['atendimentos'], p['funil']) for p in google['perfis']},
                         {'dependente_menor': (1, 1), 'titular_idoso': (1, 0)})
        self.assertEqual(r['anuncios_google'][0]['perfis'], google['perfis'])
        self.assertEqual(r['anuncios'][0]['perfis'][0]['chave'], 'nao_informado')

    def test_filtra_periodo_antes_de_escolher_sem_herdar_tags(self):
        a = self.conversa('2026-10-01', 'Meta Ads', dependente=True)
        b = self.conversa('2026-10-02', 'Chat Fire')
        c = self.conversa('2026-10-04', None, etapa=1)
        self.conn.execute("INSERT INTO chatbot.funil_envios(id_conversa,status,enviado_em) VALUES(%s,'sent','2026-10-01 12:00')", (a,))
        self.conn.execute("INSERT INTO chatbot.pesquisa_satisfacao(id_conversa,nota,criado_em) VALUES(%s,5,'2026-10-01 13:00')", (a,))
        self.conn.execute('UPDATE chatbot.conversa SET followup_stage=2 WHERE id_conversa=%s', (a,))
        r = consolidar_conversas(painel.listar_conversas(1, '2026-10-01', '2026-10-03', self.cursor))[0]
        self.assertEqual(r['id_conversa_atual'], b)
        self.assertEqual(r['ids_conversa'], [a, b])
        self.assertFalse(r['avaliada'])
        self.assertFalse(r['foi_funil'])
        self.assertEqual(r['destinatario'], 'titular')
        self.assertEqual(r['origem']['canal'], 'chat_fire')
        antigo = consolidar_conversas(painel.listar_conversas(1, '2026-10-01', '2026-10-02', self.cursor))[0]
        self.assertEqual(antigo['id_conversa_atual'], a)
        self.assertTrue(antigo['avaliada'])
        self.assertTrue(antigo['foi_funil'])
        self.assertEqual(antigo['followup_stage'], 2)
        ultimo = consolidar_conversas(painel.listar_conversas(1, None, '2026-10-05', self.cursor))[0]
        self.assertEqual(ultimo['id_conversa_atual'], c)
        self.assertIsNone(ultimo['destinatario'])
        self.assertEqual(painel.listar_conversas(2, None, '2026-10-05', self.cursor), [])
        r = montar_origens(painel.buscar_origens(1, '2026-10-01', '2026-10-03', self.cursor))
        self.assertEqual((r['atendimentos'], r['contatos_unicos']), (2, 1))
        self.assertEqual(sum(x['funil'] for x in r['canais']), 1)
        self.assertEqual(r['anuncios'][0]['anuncio'], 'QR001')
        self.assertEqual(sum(e['quantidade'] for e in painel.buscar_etapas(1, '2026-10-01', '2026-10-03', self.cursor)), 2)
        self.assertEqual(painel.buscar_origens(2, None, '2026-10-05', self.cursor), [])
        self.assertTrue(painel.buscar_unidade(1, self.cursor)['fireads_habilitada'])
        self.conn.execute('UPDATE chatbot.integracao_fireads SET integracao_ativa=FALSE')
        self.assertFalse(painel.buscar_unidade(1, self.cursor)['fireads_habilitada'])

    def test_cursor_django_carrega_conversas_e_relatorios_com_jsonb_novo_e_legado(self):
        # O teste acima usa psycopg direto. Produção usa o cursor do Django,
        # cuja configuração de JSONB devolve texto para as consultas SQL brutas.
        self.conversa('2026-10-01', 'Meta Ads')
        legado_id = self.conversa('2026-10-02', 'Meta Ads')
        row = dict(ROW, Canal='Meta Ads', Anuncio='QR001 legado')
        contexto_legado = {
            'origem': 'meta', 'id_conversa': legado_id, 'concluida': True,
            'referencia': capturar(row, ABA_DESTINO)['referencia'],
        }
        self.conn.execute(
            'UPDATE chatbot.conversa SET contexto_fireads=%s WHERE id_conversa=%s',
            (Jsonb(contexto_legado), legado_id),
        )
        self.conn.execute('''INSERT INTO chatbot.consulta_fireads
            (id_conversa,id_unidade,id_integracao_fireads,entrada,status,
             consulta_concluida,resultado,dados,consultado_em)
            VALUES (%s,1,1,'{}','concluida',TRUE,'importado',%s,now())''',
            (legado_id, Jsonb({'fontes': {'geral': [row]}})),
        )
        self.conn.commit()

        # setUp já conferiu que o DSN é o PostgreSQL local descartável.
        params = conninfo_to_dict(base.DSN)
        config = deepcopy(connections['default'].settings_dict)
        config.update(
            NAME=params['dbname'], USER=params.get('user', ''),
            PASSWORD=params.get('password', ''), HOST=params['host'],
            PORT=params.get('port', '5432'),
            OPTIONS={'options': '-c search_path=chatbot', 'connect_timeout': 5},
        )
        banco = DatabaseWrapper(config, alias='teste_monitoramento_fireads')
        self.addCleanup(banco.close)
        with banco.cursor() as cursor:
            cursor.execute('''SELECT c.contexto_fireads,q.dados
                FROM chatbot.conversa c JOIN chatbot.consulta_fireads q USING(id_conversa)
                WHERE c.id_conversa=%s''', (legado_id,))
            self.assertTrue(all(isinstance(valor, str) for valor in cursor.fetchone()))

        periodo = resolver_periodo('total', agora=datetime(2026, 10, 3, tzinfo=timezone.utc))
        with patch.object(services, 'connection', banco):
            conversas = services.carregar_conversas(SimpleNamespace(id_unidade=1), periodo)
            relatorio = services.carregar_relatorio(SimpleNamespace(id_unidade=1), periodo)
        self.assertTrue(conversas['unidade']['fireads_habilitada'])
        self.assertEqual(len(conversas['conversas']), 1)
        self.assertEqual(conversas['conversas'][0]['origem']['anuncio'], 'QR001 legado')
        meta = next(c for c in relatorio['origens']['canais'] if c['canal'] == 'meta')
        self.assertEqual(meta['atendimentos'], 2)
        self.assertEqual(relatorio['origens']['sem_origem'], 0)
        self.assertEqual({a['anuncio'] for a in relatorio['origens']['anuncios']},
                         {'QR001', 'QR001 legado'})
