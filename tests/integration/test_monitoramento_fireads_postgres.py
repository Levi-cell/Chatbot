"""Última conversa no período, isolamento de unidade e métricas com SQL real."""
import unittest
from psycopg.types.json import Jsonb

from tests.integration import test_fireads_postgres as base
from tests.unit.test_monitoramento_origens import contexto
from core.integrations.fireads.atribuicao import CHAVE
from core.repositories.monitoramento import painel
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
