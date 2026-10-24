"""Guardas e concorrência do worker com PostgreSQL descartável em loopback."""

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, Mock

import psycopg
from psycopg.types.json import Jsonb

from tests.integration import test_fireads_postgres as base
from tests.unit.test_origem_fireads import resposta
from tests.unit.test_coleta_abertura import ROW
from core.integrations.fireads.atribuicao import CHAVE, CHAVE_VERIFICACAO, ler
from core.integrations.fireads.origem import identificar
from core.repositories.fireads import origens
from core.validacoes.coleta_abertura import criar_contexto
from workers.worker_origem_fireads.origem_worker import executar_ciclo

# A ativação é protegida por trigger; a conversa nasce depois dela.
DESDE = datetime.now(timezone.utc) + timedelta(minutes=1)


@unittest.skipUnless(base.DSN, 'Exige FIREADS_TEST_DSN local e descartável')
class OrigemPostgresTests(unittest.TestCase):
    setUp = base.FireAdsPostgresTests.setUp
    def limpar(self):
        try:
            base.FireAdsPostgresTests.limpar(self)
        finally:
            self.conn.close()

    def preparar(self):
        mensagem = dict(id_mensagem=1, id_hash='origem-teste', tipo_mensagem='text',
                        conteudo_texto='Nome: Ana\nEmail: ana@example.com\nPara quem é: Para mim\nTurno: Tarde')
        coleta = criar_contexto(1, mensagem, coletar_turno=True)
        coleta.update(status='pronto', etapa_inicial=4, fireads_aplicavel=True)
        contexto = dict(id_conversa=1, id_integracao=1, id_consulta=None,
                        concluida=True, motivo='canal_pendente_entrega', origem='organico')
        self.conn.execute('''UPDATE chatbot.conversa SET iniciou_em=%s,id_etapa_atual=4,
            contexto_coleta=%s,contexto_fireads=%s,origem_fireads='organico' WHERE id_conversa=1''',
                          (DESDE, Jsonb(coleta), Jsonb(contexto)))
        self.conn.commit()
        return contexto

    def candidatos(self):
        return origens.listar(self.cursor, DESDE, ate=100)

    def resultado(self, candidato, canal='Google Ads'):
        return identificar(resposta([dict(ROW, WhatsApp=base.NUMERO, Canal=canal, Anuncio='Memória')]),
            numero=candidato['numero'], aba=candidato['aba'], fuso=candidato['fuso'],
            id_conversa=1, id_integracao=1)

    def test_grava_json_sem_alterar_atendimento_e_sem_migracao(self):
        ctx = self.preparar()
        item = self.candidatos()[0]
        self.assertTrue(origens.concluir(self.cursor, item, self.resultado(item), DESDE))
        salvo, etapa, origem, coleta = self.conn.execute('''SELECT contexto_fireads,id_etapa_atual,
            origem_fireads,contexto_coleta FROM chatbot.conversa WHERE id_conversa=1''').fetchone()
        self.assertEqual((etapa, origem, coleta['status']), (4, 'organico', 'pronto'))
        self.assertTrue(all(salvo[k] == v for k, v in ctx.items()))
        self.assertEqual(ler(salvo, 1)['canal'], 'google')
        self.assertFalse(self.candidatos())

    def test_sem_canal_conclui_mas_nao_inventa_atribuicao(self):
        self.preparar()
        item = self.candidatos()[0]
        self.assertTrue(origens.concluir(self.cursor, item, self.resultado(item, ''), DESDE))
        salvo = self.conn.execute('SELECT contexto_fireads FROM chatbot.conversa WHERE id_conversa=1').fetchone()[0]
        self.assertEqual(salvo[CHAVE_VERIFICACAO]['status'], 'concluida')
        self.assertNotIn(CHAVE, salvo)
        self.assertIsNone(ler(salvo, 1))
        self.assertFalse(self.candidatos())

    def test_abertura_pendente_e_consulta_inicial_nao_sao_elegiveis(self):
        self.preparar()
        self.conn.execute('UPDATE chatbot.conversa SET contexto_fireads=NULL,origem_fireads=NULL')
        self.assertFalse(self.candidatos())
        self.conn.rollback()
        self.conn.execute('''UPDATE chatbot.conversa SET contexto_coleta=jsonb_set(
            contexto_coleta,'{status}','"aguardando_consulta"')''')
        self.assertFalse(self.candidatos())
        self.conn.rollback()
        self.conn.execute('''INSERT INTO chatbot.consulta_fireads
            (id_conversa,id_unidade,id_integracao_fireads,entrada) VALUES(1,1,1,'{}')''')
        self.assertFalse(self.candidatos())
        self.conn.execute("""UPDATE chatbot.consulta_fireads SET status='concluida',
            consulta_concluida=TRUE,resultado='erro',dados='{}',consultado_em=clock_timestamp()""")
        self.assertFalse(self.candidatos())

    def test_etapas_com_e_sem_link_e_envios_existentes(self):
        self.preparar()
        for link in ('', 'https://example.com/agendar'):
            for etapa in (4, 18, 19, 20, 21, 24):
                with self.subTest(link=bool(link), etapa=etapa):
                    self.conn.execute('UPDATE chatbot.atendimento_customizado SET link_agendamento=%s', (link,))
                    self.conn.execute('UPDATE chatbot.conversa SET id_etapa_atual=%s', (etapa,))
                    flag = self.conn.execute('SELECT elegivel_funil FROM chatbot.etapa WHERE id_etapa=%s', (etapa,)).fetchone()[0]
                    elegivel = flag and (etapa >= 20 if link else etapa == 19 or etapa >= 21)
                    self.assertEqual(bool(self.candidatos()), not elegivel)
        self.conn.rollback()
        self.conn.execute('INSERT INTO chatbot.funil_envios(id_conversa) VALUES(1)')
        self.assertFalse(self.candidatos())

    def test_inativacao_e_mudanca_de_configuracao_impedem_gravacao(self):
        self.preparar()
        item = self.candidatos()[0]
        for sql in ("UPDATE chatbot.integracao_fireads SET integracao_ativa=FALSE",
                    "UPDATE chatbot.unidade SET status_pagamento=FALSE",
                    "UPDATE chatbot.integracao_fireads SET url_dashbord='https://script.google.com/macros/s/outro/exec'",
                    "UPDATE chatbot.integracao_fireads SET fuso_formularios='UTC'"):
            self.conn.execute(sql)
            self.assertFalse(origens.concluir(self.cursor, item, self.resultado(item), DESDE))
            self.conn.rollback()

    def test_funil_confirmado_em_outra_sessao_prevalece(self):
        self.preparar()
        item = self.candidatos()[0]
        self.conn.commit()
        with psycopg.connect(base.DSN) as outra:
            outra.execute('''UPDATE chatbot.conversa SET contexto_fireads=contexto_fireads || %s
                WHERE id_conversa=1''', (Jsonb(self.resultado(item, 'Chat Fire')),))
        self.assertFalse(origens.concluir(self.cursor, item, self.resultado(item), DESDE))
        salvo = self.conn.execute('SELECT contexto_fireads FROM chatbot.conversa WHERE id_conversa=1').fetchone()[0]
        self.assertEqual(ler(salvo, 1)['canal'], 'chat_fire')

    def test_exclusao_entre_sessoes_e_recuperacao_apos_close(self):
        self.preparar()
        self.assertTrue(origens.adquirir_ciclo(self.cursor))
        self.conn.commit()
        with psycopg.connect(base.DSN) as outra:
            self.assertFalse(origens.adquirir_ciclo(outra.cursor()))
        self.conn.close()
        self.conn = psycopg.connect(base.DSN)
        self.assertTrue(origens.adquirir_ciclo(self.conn.cursor()))
        self.conn.close()
        self.conn = psycopg.connect(base.DSN)

    def test_ciclo_real_erro_retomada_e_ausencia_de_transacao_no_http(self):
        self.preparar()
        def ler_http(_):
            with psycopg.connect(base.DSN) as leitura:
                estados = leitura.execute("SELECT state FROM pg_stat_activity WHERE application_name='worker_origem_fireads'").fetchall()
                self.assertEqual(estados, [('idle',)])
            return resposta([dict(ROW, WhatsApp=base.NUMERO, Canal='Google Ads')])
        http = Mock()
        http.consultar.side_effect = TimeoutError
        with patch('workers.worker_origem_fireads.origem_worker.get_conn',
                   side_effect=lambda **kwargs: psycopg.connect(base.DSN, **kwargs)), \
             patch('workers.worker_origem_fireads.origem_worker.ClienteFireAds', return_value=http):
            self.assertEqual(executar_ciclo(DESDE)['falhas'], 1)
            self.assertEqual(len(self.candidatos()), 1)
            self.conn.commit()
            http.consultar.side_effect = ler_http
            self.assertEqual(executar_ciclo(DESDE)['identificados'], 1)
            self.assertEqual(executar_ciclo(DESDE)['consultas'], 0)
            http.enviar.assert_not_called()

    def test_funil_avanca_durante_http_e_descarta_resultado(self):
        self.preparar()
        def avancar(_):
            with psycopg.connect(base.DSN) as outra:
                outra.execute('UPDATE chatbot.conversa SET id_etapa_atual=19 WHERE id_conversa=1')
            return resposta([dict(ROW, WhatsApp=base.NUMERO)])
        http = Mock()
        http.consultar.side_effect = avancar
        with patch('workers.worker_origem_fireads.origem_worker.get_conn',
                   side_effect=lambda **kwargs: psycopg.connect(base.DSN, **kwargs)), \
             patch('workers.worker_origem_fireads.origem_worker.ClienteFireAds', return_value=http):
            self.assertEqual(executar_ciclo(DESDE)['descartados'], 1)
        salvo = self.conn.execute('SELECT contexto_fireads FROM chatbot.conversa WHERE id_conversa=1').fetchone()[0]
        self.assertNotIn(CHAVE_VERIFICACAO, salvo)
        self.assertNotIn(CHAVE, salvo)

    def test_marco_fixo_e_revalidacao_antes_de_http(self):
        self.preparar()
        itens = self.candidatos()
        self.assertEqual(len(origens.revalidar_grupo(self.cursor, itens, DESDE)), 1)
        self.conn.execute('UPDATE chatbot.conversa SET iniciou_em=%s', (DESDE-timedelta(seconds=1),))
        self.assertFalse(self.candidatos())
        self.assertFalse(origens.revalidar_grupo(self.cursor, itens, DESDE))
        self.conn.rollback()
        self.conn.execute("UPDATE chatbot.integracao_fireads SET aba_destino='Outra aba'")
        self.assertFalse(origens.revalidar_grupo(self.cursor, itens, DESDE))
