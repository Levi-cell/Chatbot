"""Migração e atomicidade em PostgreSQL local vazio explicitamente autorizado."""

import os
from pathlib import Path
import unittest

import psycopg
from psycopg.conninfo import conninfo_to_dict

from core.repositories.monitoramento.encerramentos import contar_encerramentos_por_motivo
from core.validacoes.encerramento_por_idade import MOTIVOS_IDADE
from workers.worker_flow.transacoes.finalizacao_fila import finalizar_mensagem_processada

DSN = os.environ.get('COMERCIAL_IDADE_TEST_DSN')
SQL = Path(__file__).resolve().parents[2] / 'deploy/migrations/20260926_filtro_comercial_regras_idade.sql'


@unittest.skipUnless(DSN, 'Exige COMERCIAL_IDADE_TEST_DSN local em test_chatbot_comercial vazio')
class EncerramentosPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parametros = conninfo_to_dict(DSN)
        locais = {'localhost', '127.0.0.1', '::1'}
        if (parametros.get('host') not in locais
                or parametros.get('dbname') != 'test_chatbot_comercial'
                or parametros.get('service')
                or (parametros.get('hostaddr') and parametros['hostaddr'] not in locais)):
            raise RuntimeError('Recusado: exige loopback e banco test_chatbot_comercial')
        cls.conn = psycopg.connect(DSN, autocommit=True, connect_timeout=5)
        if (cls.conn.info.host not in locais or cls.conn.info.dbname != 'test_chatbot_comercial'
                or cls.conn.execute("SELECT to_regnamespace('chatbot')").fetchone()[0] is not None):
            cls.conn.close()
            raise RuntimeError('Recusado: conexão incompatível ou schema já existente')

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def setUp(self):
        self.conn.execute('CREATE SCHEMA chatbot')
        self.addCleanup(self.limpar)
        self.conn.execute('''
            CREATE TABLE chatbot.unidade (
                id_unidade INTEGER PRIMARY KEY, nome_unidade TEXT,
                numero_comercial VARCHAR(30), idade_minima_suporte INTEGER,
                CONSTRAINT ck_unidade_idade_minima_suporte
                CHECK (idade_minima_suporte IS NULL OR idade_minima_suporte IN (50,60,70,80,90))
            );
            INSERT INTO chatbot.unidade VALUES
                (1,'Teste','5571999999999',90),(2,'Teste 2','(71) 99999-9999',60);
            CREATE TABLE chatbot.conversa (
                id_conversa INTEGER PRIMARY KEY, id_cliente INTEGER, id_unidade INTEGER,
                id_etapa_atual INTEGER, status_dependente BOOLEAN DEFAULT FALSE,
                status_ativa BOOLEAN, finalizou_em TIMESTAMPTZ, motivo_encerramento VARCHAR(30),
                processing BOOLEAN DEFAULT FALSE, processing_started_at TIMESTAMPTZ,
                CONSTRAINT ck_conversa_motivo_encerramento CHECK (motivo_encerramento IS NULL OR
                    motivo_encerramento IN ('idade_invalida','encaminhado_suporte_idoso',
                                           'foi_agendado','followup_sem_resposta'))
            );
            INSERT INTO chatbot.conversa (id_conversa,id_cliente,id_unidade,id_etapa_atual,status_ativa,motivo_encerramento)
                VALUES (1,1,1,6,FALSE,'idade_invalida'),(2,1,1,6,TRUE,NULL);
            CREATE TABLE chatbot.fila_mensagens (
                id_mensagem INTEGER PRIMARY KEY, status TEXT,
                processing_started_at TIMESTAMPTZ, last_error TEXT
            );
            INSERT INTO chatbot.fila_mensagens VALUES(1,'processing',NULL,NULL);
            CREATE TABLE chatbot.cache_controle (nome TEXT PRIMARY KEY,versao INTEGER,atualizado_em TIMESTAMPTZ);
            INSERT INTO chatbot.cache_controle VALUES('unidades',3,NOW());
        ''')

    def limpar(self):
        self.conn.execute('ROLLBACK')
        # Somente o schema criado pelo próprio teste, após a verificação de vazio.
        self.conn.execute('DROP SCHEMA chatbot CASCADE')

    def migrar(self):
        self.conn.execute(SQL.read_text(encoding='utf-8'))

    def test_migracao_preserva_historico_e_normaliza_sem_ampliar_faixa(self):
        antes = self.conn.execute('SELECT to_jsonb(c) FROM chatbot.conversa c ORDER BY id_conversa').fetchall()
        self.migrar()
        self.assertEqual(self.conn.execute('SELECT idade_minima_suporte FROM chatbot.unidade ORDER BY id_unidade').fetchall(), [(None,), (60,)])
        self.assertEqual(self.conn.execute('SELECT to_jsonb(c) FROM chatbot.conversa c ORDER BY id_conversa').fetchall(), antes)
        self.assertEqual(self.conn.execute("SELECT versao FROM chatbot.cache_controle WHERE nome='unidades'").fetchone()[0], 4)
        for motivo in MOTIVOS_IDADE | {'foi_agendado', 'followup_sem_resposta'}:
            self.conn.execute('UPDATE chatbot.conversa SET motivo_encerramento=%s WHERE id_conversa=1', (motivo,))
        for limite in (None,50,60,70,80):
            self.conn.execute('UPDATE chatbot.unidade SET idade_minima_suporte=%s WHERE id_unidade=1', (limite,))
        with self.assertRaises(psycopg.errors.CheckViolation):
            self.conn.execute('UPDATE chatbot.unidade SET idade_minima_suporte=90 WHERE id_unidade=1')

    def test_telefone_invalido_aborta_toda_migracao(self):
        self.conn.execute('UPDATE chatbot.unidade SET numero_comercial=NULL WHERE id_unidade=2')
        with self.assertRaisesRegex(psycopg.Error, 'Regularize'):
            self.migrar()
        self.conn.execute('ROLLBACK')
        self.assertEqual(self.conn.execute('SELECT idade_minima_suporte FROM chatbot.unidade WHERE id_unidade=1').fetchone()[0], 90)
        self.assertEqual(self.conn.execute("SELECT versao FROM chatbot.cache_controle WHERE nome='unidades'").fetchone()[0], 3)

    def test_encerramento_e_sent_confirmam_ou_desfazem_juntos(self):
        self.migrar()
        mensagem = {'id_mensagem': 1, 'cliente_telefone': '5571999999999', 'id_phone_unidade': 'teste'}
        contexto = {'id_unidade': 1, 'conversa': {'id_conversa': 2, 'estado': 'ativa'}}
        final = {'intencao_encerramento': {
            'motivo': 'encaminhado_suporte_idoso', 'motivo_encerramento': 'suporte_idoso_60',
            'excluir_dependente': False, 'bloqueio_dias': 0,
        }}
        with self.assertRaisesRegex(RuntimeError, 'queda simulada'):
            with self.conn.transaction(), self.conn.cursor() as cursor:
                finalizar_mensagem_processada(mensagem, contexto, 1, cursor, final)
                raise RuntimeError('queda simulada')
        self.assertEqual(self.conn.execute('SELECT status_ativa,motivo_encerramento FROM chatbot.conversa WHERE id_conversa=2').fetchone(), (True,None))
        self.assertEqual(self.conn.execute('SELECT status FROM chatbot.fila_mensagens').fetchone()[0], 'processing')
        with self.conn.transaction(), self.conn.cursor() as cursor:
            finalizar_mensagem_processada(mensagem, contexto, 1, cursor, final)
        with self.conn.cursor() as cursor:
            linhas = contar_encerramentos_por_motivo(1, None, '2099-01-01', cursor)
        self.assertEqual(linhas, [{'motivo_encerramento':'suporte_idoso_60','status_dependente':False,'conversas':1}])


if __name__ == '__main__':
    unittest.main()
