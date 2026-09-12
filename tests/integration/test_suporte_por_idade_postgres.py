"""Migração real somente em PostgreSQL local descartável explicitamente indicado."""

from contextlib import contextmanager
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import unittest
from unittest.mock import patch

import psycopg
from psycopg.conninfo import conninfo_to_dict

from core.database.deploy_database import bank_script
from core.repositories.fluxo.contextos.etapa6 import buscar_contexto_etapa6
from core.repositories.monitoramento import painel


DSN = os.environ.get('SUPORTE_IDADE_TEST_DSN')
MIGRACAO = Path(__file__).resolve().parents[2] / 'deploy/migrations/20260911_idade_minima_suporte.sql'
REVERSAO = Path(__file__).resolve().parents[2] / 'deploy/rollback/20260911_idade_minima_suporte.sql'


@unittest.skipUnless(DSN, 'Defina SUPORTE_IDADE_TEST_DSN para banco local vazio test_chatbot_suporte_idade')
class SuporteIdadePostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        params = conninfo_to_dict(DSN)
        locais = {'127.0.0.1', '::1', 'localhost'}
        if (params.get('host') not in locais
                or params.get('dbname') != 'test_chatbot_suporte_idade'
                or (params.get('hostaddr') and params['hostaddr'] not in locais)
                or params.get('service')):
            raise RuntimeError('Exige host loopback explícito e dbname=test_chatbot_suporte_idade')
        cls.conn = psycopg.connect(DSN, connect_timeout=5, autocommit=True)
        if cls.conn.info.host not in locais or cls.conn.info.dbname != 'test_chatbot_suporte_idade':
            cls.conn.close()
            raise RuntimeError('Conexão efetiva não corresponde ao banco descartável')
        if cls.conn.execute("SELECT to_regnamespace('chatbot')").fetchone()[0] is not None:
            cls.conn.close()
            raise RuntimeError('Schema chatbot já existe: use um banco de teste vazio')

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def setUp(self):
        self.conn.execute('CREATE SCHEMA chatbot')
        self.addCleanup(self.limpar_schema)
        self.conn.execute('''CREATE TABLE chatbot.unidade (
            id_unidade SERIAL PRIMARY KEY, nome_unidade TEXT NOT NULL,
            suporte_idoso BOOLEAN NOT NULL DEFAULT FALSE,
            email_obrigatorio BOOLEAN NOT NULL DEFAULT TRUE,
            bpa_ativo BOOLEAN NOT NULL DEFAULT FALSE,
            numero_comercial TEXT
        );
        INSERT INTO chatbot.unidade(nome_unidade, suporte_idoso, email_obrigatorio, numero_comercial)
        VALUES ('Ativa', TRUE, FALSE, '5571999999999'), ('Desativada', FALSE, TRUE, NULL);
        CREATE TABLE chatbot.conversa (id_conversa INTEGER, followup_stage INTEGER, status_ativa BOOLEAN);
        INSERT INTO chatbot.conversa VALUES (1, 1, TRUE), (2, 0, FALSE);
        ''')

    def limpar_schema(self):
        self.conn.execute('ROLLBACK')
        # Este schema foi criado pelo próprio teste após recusar um preexistente.
        self.conn.execute('DROP SCHEMA chatbot CASCADE')

    def migrar(self, sql=None):
        self.conn.execute(sql or MIGRACAO.read_text(encoding='utf-8'))

    def assert_dominio(self):
        for idade in (None, 50, 60, 70, 80, 90):
            self.conn.execute('UPDATE chatbot.unidade SET idade_minima_suporte=%s WHERE id_unidade=1', (idade,))
        for idade in (0, -1, 49, 55, 100):
            with self.assertRaises(psycopg.errors.CheckViolation):
                self.conn.execute('UPDATE chatbot.unidade SET idade_minima_suporte=%s WHERE id_unidade=1', (idade,))

    def test_conversao_preserva_unidades_conversas_e_dominio(self):
        self.migrar()
        self.assertEqual(self.conn.execute('''SELECT idade_minima_suporte, email_obrigatorio,
            bpa_ativo, numero_comercial FROM chatbot.unidade ORDER BY id_unidade''').fetchall(),
            [(60, False, False, '5571999999999'), (None, True, False, None)])
        self.assertEqual(self.conn.execute('SELECT * FROM chatbot.conversa ORDER BY id_conversa').fetchall(),
                         [(1, 1, True), (2, 0, False)])
        self.assert_dominio()
        self.conn.execute("INSERT INTO chatbot.unidade(nome_unidade) VALUES ('Nova')")
        self.assertIsNone(self.conn.execute("SELECT idade_minima_suporte FROM chatbot.unidade WHERE nome_unidade='Nova'").fetchone()[0])

    def test_reaplicacao_recusada_sem_perder_configuracao_nova(self):
        self.migrar()
        self.conn.execute('UPDATE chatbot.unidade SET idade_minima_suporte=70 WHERE id_unidade=1')
        with self.assertRaisesRegex(psycopg.Error, 'já aplicada ou schema parcial'):
            self.migrar()
        self.conn.execute('ROLLBACK')
        self.assertEqual(self.conn.execute('SELECT idade_minima_suporte FROM chatbot.unidade WHERE id_unidade=1').fetchone()[0], 70)

    def test_schema_parcial_recusado(self):
        self.conn.execute('ALTER TABLE chatbot.unidade ADD COLUMN idade_minima_suporte INTEGER')
        with self.assertRaisesRegex(psycopg.Error, 'schema parcial'):
            self.migrar()
        self.conn.execute('ROLLBACK')
        self.assertEqual(self.conn.execute('SELECT suporte_idoso FROM chatbot.unidade ORDER BY id_unidade').fetchall(), [(True,), (False,)])

    def test_falha_pos_conversao_reverte_toda_a_transacao(self):
        sql = MIGRACAO.read_text(encoding='utf-8').replace(
            'DO $poscondicoes$\nBEGIN',
            "DO $poscondicoes$\nBEGIN\n    RAISE EXCEPTION 'Falha injetada de teste';",
        )
        with self.assertRaisesRegex(psycopg.Error, 'Falha injetada'):
            self.migrar(sql)
        self.conn.execute('ROLLBACK')
        self.assertEqual(self.conn.execute('SELECT suporte_idoso FROM chatbot.unidade ORDER BY id_unidade').fetchall(), [(True,), (False,)])
        self.assertEqual(self.conn.execute("""SELECT COUNT(*) FROM information_schema.columns
            WHERE table_schema='chatbot' AND table_name='unidade' AND column_name='idade_minima_suporte'""").fetchone()[0], 0)

    def test_instalacao_limpa_usa_o_mesmo_dominio(self):
        comandos = []

        class CapturaDDL:
            def execute(self, sql, *args): comandos.append(sql)

        @contextmanager
        def capturar(*args): yield CapturaDDL()

        with patch.object(bank_script, 'transacao_deploy', capturar):
            bank_script.criar_tabelas()
        ddl_unidade = re.search(
            r'CREATE TABLE IF NOT EXISTS chatbot\.unidade\s*\(.*?\n\s*\);',
            '\n'.join(comandos), re.S,
        ).group(0)
        self.conn.execute('DROP TABLE chatbot.unidade; CREATE TABLE chatbot.auth_user (id SERIAL PRIMARY KEY)')
        self.conn.execute(ddl_unidade)
        self.conn.execute('''INSERT INTO chatbot.unidade
            (id_unidade, nome_unidade, nome_agente, genero, cnpj, email_responsavel, telefone,
             waba_id, phone_number_id, link_agendamento)
            VALUES (1, 'Nova', 'Suh', 'feminino', 'teste', 'teste@example.com', '5571999999999',
                    'waba', 'phone', 'https://example.com')''')
        self.assertIsNone(self.conn.execute('SELECT idade_minima_suporte FROM chatbot.unidade').fetchone()[0])
        self.assert_dominio()

    def test_reversao_preserva_politica_null_60(self):
        self.migrar()
        self.conn.execute(REVERSAO.read_text(encoding='utf-8'))
        self.assertEqual(self.conn.execute(
            'SELECT suporte_idoso, email_obrigatorio FROM chatbot.unidade ORDER BY id_unidade'
        ).fetchall(), [(True, False), (False, True)])

    def test_reversao_recusa_faixas_novas(self):
        self.migrar()
        for limite in (50, 70, 80, 90):
            self.conn.execute('UPDATE chatbot.unidade SET idade_minima_suporte=%s WHERE id_unidade=1', (limite,))
            with self.assertRaisesRegex(psycopg.Error, 'Há faixas novas configuradas'):
                self.conn.execute(REVERSAO.read_text(encoding='utf-8'))
            self.conn.execute('ROLLBACK')
            self.assertEqual(self.conn.execute('SELECT idade_minima_suporte FROM chatbot.unidade WHERE id_unidade=1').fetchone()[0], limite)

    def test_lock_ocupado_aborta_sem_converter_a_coluna(self):
        with psycopg.connect(DSN, connect_timeout=5) as concorrente:
            concorrente.execute('SELECT * FROM chatbot.unidade')
            with self.assertRaises(psycopg.errors.LockNotAvailable):
                self.migrar()
            self.conn.execute('ROLLBACK')
        self.assertEqual(self.conn.execute(
            'SELECT suporte_idoso FROM chatbot.unidade ORDER BY id_unidade'
        ).fetchall(), [(True,), (False,)])

    def test_falha_na_reversao_preserva_schema_e_valores_novos(self):
        self.migrar()
        sql = REVERSAO.read_text(encoding='utf-8').replace(
            'DO $conferencia$\nBEGIN',
            "DO $conferencia$\nBEGIN\n    RAISE EXCEPTION 'Falha na reversão';",
        )
        with self.assertRaisesRegex(psycopg.Error, 'Falha na reversão'):
            self.conn.execute(sql)
        self.conn.execute('ROLLBACK')
        self.assertEqual(self.conn.execute(
            'SELECT idade_minima_suporte FROM chatbot.unidade ORDER BY id_unidade'
        ).fetchall(), [(60,), (None,)])
        self.assert_dominio()

    def test_contexto_e_relatorio_no_schema_completo_migrado(self):
        # Usa o DDL real e a reversão para montar a estrutura anterior completa.
        self.conn.execute('''
            DROP TABLE chatbot.conversa, chatbot.unidade;
            CREATE TABLE chatbot.auth_user (id SERIAL PRIMARY KEY);
        ''')

        @contextmanager
        def transacao_local(*_):
            with self.conn.cursor() as cursor:
                yield cursor

        with patch.object(bank_script, 'transacao_deploy', transacao_local):
            bank_script.criar_tabelas()
        self.conn.execute(REVERSAO.read_text(encoding='utf-8'))
        self.conn.execute('''
            INSERT INTO chatbot.unidade
                (id_unidade, nome_unidade, nome_agente, genero, cnpj,
                 email_responsavel, telefone, waba_id, phone_number_id,
                 link_agendamento, numero_comercial, suporte_idoso)
            SELECT n, 'Teste ' || n, 'Suh', 'feminino', 'cnpj-' || n,
                   'teste' || n || '@example.com', '557199999999' || n,
                   'waba-' || n, 'phone-' || n,
                   'https://example.com/agendar/' || n, '5571999999999', TRUE
              FROM generate_series(1, 2) AS n;
            INSERT INTO chatbot.etapa (id_etapa, nome_etapa)
            VALUES (6, 'Idade');
            INSERT INTO chatbot.cliente (id_cliente, waid_telefone, nome)
            VALUES (1, '5571999999901', 'Cliente Um'),
                   (2, '5571999999902', 'Cliente Dois');
            INSERT INTO chatbot.conversa
                (id_conversa, id_unidade, id_cliente, id_etapa_atual,
                 status_ativa, motivo_encerramento, finalizou_em)
            VALUES (1, 1, 1, 6, FALSE, 'encaminhado_suporte_idoso', '2026-09-01T00:00:00Z'),
                   (2, 1, 1, 6, FALSE, 'encaminhado_suporte_idoso', '2026-09-02T00:00:00Z'),
                   (3, 2, 1, 6, FALSE, 'encaminhado_suporte_idoso', '2026-09-02T00:00:00Z'),
                   (4, 1, 2, 6, FALSE, 'encaminhado_suporte_idoso', '2026-10-01T00:00:00Z'),
                   (5, 1, 1, 6, TRUE, NULL, NULL);
        ''')
        conversas_antes = self.conn.execute(
            'SELECT to_jsonb(c) FROM chatbot.conversa c ORDER BY id_conversa'
        ).fetchall()
        self.migrar()
        self.assertEqual(self.conn.execute(
            'SELECT to_jsonb(c) FROM chatbot.conversa c ORDER BY id_conversa'
        ).fetchall(), conversas_antes)
        inicio = datetime(2026, 9, 1, tzinfo=timezone.utc)
        fim = datetime(2026, 10, 1, tzinfo=timezone.utc)
        with self.conn.cursor() as cursor:
            for limite in (None, 50, 60, 70, 80, 90):
                cursor.execute(
                    'UPDATE chatbot.unidade SET idade_minima_suporte=%s WHERE id_unidade=1',
                    (limite,),
                )
                self.assertEqual(
                    buscar_contexto_etapa6(5, 1, cursor)['idade_minima_suporte'],
                    limite,
                )
                self.assertEqual(
                    painel.buscar_unidade(1, cursor)['idade_minima_suporte'], limite,
                )
                self.assertEqual(
                    painel.contar_encaminhados_comercial_por_idade(1, inicio, fim, cursor),
                    1,
                )
            with self.assertRaisesRegex(ValueError, 'não encontrado'):
                buscar_contexto_etapa6(5, 2, cursor)
            self.assertEqual(
                painel.contar_encaminhados_comercial_por_idade(2, inicio, fim, cursor), 1,
            )


if __name__ == '__main__':
    unittest.main()
