"""Migração real, reversão e retomada; somente PostgreSQL local descartável."""

from copy import deepcopy
from pathlib import Path
import json
import os
import unittest
from unittest.mock import patch

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict

from core.database.deploy_database.etapa_transicao_script import TRANSICOES_INICIAIS
from core.database.deploy_database.povoar_etapas import ETAPAS
from core.repositories.atendimento.conversas import tentar_lock_conversa, unlock_conversa
from tests.fixtures.reserva_migracao import criar_base_legada
from workers.worker_flow.response_flow.flow_sender import flow_sender
from workers.worker_flow.valida_historico import valida_historico


DSN = os.environ.get('MIGRACAO_RESERVA_TEST_DSN')
ROOT = Path(__file__).resolve().parents[2]
MIGRACAO = ROOT / 'deploy/migrations/20261003_reserva_com_sem_link.sql'
REVERSAO = ROOT / 'deploy/rollback/20261003_reserva_com_sem_link.sql'
REFERENCIAS = {
    'conversa': 'id_etapa_atual',
    'historico_mensagens': 'id_etapa',
    'respostas_desafios': 'id_etapa',
    'followup_retomada': 'id_etapa',
}
TABELAS = tuple(REFERENCIAS) + (
    'cliente', 'dependente', 'unidade', 'fila_mensagens', 'pesquisa_satisfacao',
    'funil_envios', 'followup_envio', 'followup_legado', 'consumo_mensal_meta',
    'consumo_meta_coletas',
)


@unittest.skipUnless(DSN, 'Exige MIGRACAO_RESERVA_TEST_DSN local em test_chatbot_migracao_reserva vazio')
class MigracaoReservaLinkPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parametros = conninfo_to_dict(DSN)
        locais = {'127.0.0.1', '::1', 'localhost'}
        if (parametros.get('host') not in locais
                or parametros.get('dbname') != 'test_chatbot_migracao_reserva'
                or parametros.get('service')
                or (parametros.get('hostaddr') and parametros['hostaddr'] not in locais)):
            raise RuntimeError('Exige banco descartável test_chatbot_migracao_reserva em loopback')
        cls.conn = psycopg.connect(DSN, autocommit=True, connect_timeout=5)
        if (cls.conn.info.host not in locais
                or cls.conn.info.dbname != 'test_chatbot_migracao_reserva'
                or cls.conn.execute("SELECT to_regnamespace('chatbot')").fetchone()[0] is not None):
            cls.conn.close()
            raise RuntimeError('Banco de teste não está vazio ou não é o destino permitido')

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def setUp(self):
        self.addCleanup(self.limpar)
        criar_base_legada(self.conn)

    def limpar(self):
        self.conn.execute('ROLLBACK')
        # Apenas o schema criado por este teste, no destino validado acima.
        self.conn.execute('DROP SCHEMA chatbot CASCADE')

    def executar(self, caminho=MIGRACAO):
        self.conn.execute(caminho.read_text(encoding='utf-8'), prepare=False)

    def fotografia(self):
        return {
            tabela: [row[0] for row in self.conn.execute(sql.SQL(
                'SELECT to_jsonb(t) FROM chatbot.{} t ORDER BY to_jsonb(t)'
            ).format(sql.Identifier(tabela))).fetchall()]
            for tabela in TABELAS
        }

    def assert_fotografia(self, esperado):
        atual = self.fotografia()
        for tabela in TABELAS:
            with self.subTest(tabela=tabela):
                ordenar = lambda row: json.dumps(row, sort_keys=True)
                self.assertEqual(
                    sorted(atual[tabela], key=ordenar),
                    sorted(esperado[tabela], key=ordenar),
                )

    def test_preserva_dados_particoes_e_ids_e_mapeia_os_significados(self):
        esperado = deepcopy(self.fotografia())
        transicoes_antes = self.conn.execute(
            'SELECT id_transicao,id_etapa_origem,evento,id_etapa_destino FROM chatbot.etapa_transicao ORDER BY id_transicao'
        ).fetchall()
        for tabela, coluna in REFERENCIAS.items():
            for row in esperado[tabela]:
                if row[coluna] is not None and 18 <= row[coluna] <= 22:
                    row[coluna] += 2
                if tabela == 'conversa':
                    row['turno'] = None
        self.executar()
        self.assert_fotografia(esperado)
        self.assertEqual(self.conn.execute('SELECT * FROM chatbot.etapa ORDER BY id_etapa').fetchall(), list(ETAPAS))
        mapa = self.conn.execute(
            'SELECT id_etapa_origem,evento,id_etapa_destino FROM chatbot.etapa_transicao ORDER BY id_etapa_origem,evento'
        ).fetchall()
        self.assertEqual(mapa, sorted(TRANSICOES_INICIAIS))
        for id_transicao, origem, evento, destino in transicoes_antes:
            self.assertEqual(self.conn.execute(
                'SELECT id_etapa_origem,evento,id_etapa_destino FROM chatbot.etapa_transicao WHERE id_transicao=%s',
                (id_transicao,),
            ).fetchone(), (origem + (2 if origem >= 18 else 0), evento, destino + (2 if destino >= 18 else 0)))
        self.assertEqual(self.conn.execute(
            'SELECT tableoid::regclass::text,COUNT(*) FROM chatbot.historico_mensagens GROUP BY tableoid ORDER BY 1'
        ).fetchall(), [('chatbot.historico_mensagens_202610', 5), ('chatbot.historico_mensagens_default', 5)])
        with self.assertRaises(psycopg.errors.CheckViolation):
            self.conn.execute("UPDATE chatbot.conversa SET turno='dia' WHERE id_conversa=18")

    def test_reexecucao_nao_desloca_novamente_nem_apaga_preferencias(self):
        self.executar()
        self.conn.execute("UPDATE chatbot.conversa SET id_etapa_atual=19,turno='manha' WHERE id_conversa=18")
        self.conn.execute('UPDATE chatbot.unidade SET link_agendamento=NULL')
        antes = self.fotografia()
        self.executar()
        self.assert_fotografia(antes)

    def test_reversao_antes_de_novos_atendimentos_e_reexecutavel(self):
        antes = self.fotografia()
        etapas = self.conn.execute('SELECT * FROM chatbot.etapa ORDER BY id_etapa').fetchall()
        mapa = self.conn.execute('SELECT * FROM chatbot.etapa_transicao ORDER BY id_transicao').fetchall()
        self.executar()
        self.executar(REVERSAO)
        self.assert_fotografia(antes)
        self.assertEqual(self.conn.execute('SELECT * FROM chatbot.etapa ORDER BY id_etapa').fetchall(), etapas)
        self.assertEqual(self.conn.execute('SELECT * FROM chatbot.etapa_transicao ORDER BY id_transicao').fetchall(), mapa)
        self.executar(REVERSAO)
        self.assert_fotografia(antes)

    def test_reversao_recusa_dados_da_nova_rota_sem_apagar_nada(self):
        self.executar()
        self.conn.execute("UPDATE chatbot.conversa SET id_etapa_atual=19,turno='tarde' WHERE id_conversa=18")
        antes = self.fotografia()
        with self.assertRaisesRegex(psycopg.errors.RaiseException, 'Reversão recusada'):
            self.executar(REVERSAO)
        self.conn.execute('ROLLBACK')
        self.assert_fotografia(antes)

    def test_catalogo_desconhecido_aborta_sem_alteracoes_parciais(self):
        self.conn.execute("UPDATE chatbot.etapa SET nome_etapa='Configuração não mapeada' WHERE id_etapa=18")
        antes = self.fotografia()
        with self.assertRaisesRegex(psycopg.errors.RaiseException, 'Catálogo/mapa diferente'):
            self.executar()
        self.conn.execute('ROLLBACK')
        self.assert_fotografia(antes)

    def test_fk_desconhecida_com_set_null_aborta_antes_de_apagar_vinculo(self):
        self.conn.execute('CREATE TABLE chatbot.referencia_extra(id INTEGER PRIMARY KEY, etapa INTEGER REFERENCES chatbot.etapa ON DELETE SET NULL)')
        self.conn.execute('INSERT INTO chatbot.referencia_extra VALUES(1,18)')
        with self.assertRaisesRegex(psycopg.errors.RaiseException, 'Referências de etapa não mapeadas'):
            self.executar()
        self.conn.execute('ROLLBACK')
        self.assertEqual(self.conn.execute('SELECT * FROM chatbot.referencia_extra').fetchall(), [(1,18)])
        self.assertEqual(self.conn.execute('SELECT id_etapa_atual FROM chatbot.conversa WHERE id_conversa=18').fetchone(), (18,))

    def test_resposta_migrada_e_reaproveitada_mesmo_apos_remocao_do_link(self):
        self.executar()
        self.conn.execute('UPDATE chatbot.unidade SET link_agendamento=NULL')
        conversa = self.conn.execute('SELECT to_jsonb(c) FROM chatbot.conversa c WHERE id_conversa=18').fetchone()[0]
        recebido = self.conn.execute('SELECT received_data_hora FROM chatbot.fila_mensagens WHERE id_mensagem=18').fetchone()[0]
        mensagem = {
            'id_mensagem': 18, 'id_hash': 'wamid.cliente.18', 'data_recebimento': recebido,
            'cliente_telefone': '5511999999918', 'id_phone_unidade': 'phone',
            'unidade_telefone': '5511888888888', 'tipo_mensagem': 'text',
            'conteudo_texto': 'Já reservei', 'retry_count': 2,
        }
        with self.conn.cursor() as cursor, patch(
            'workers.worker_flow.valida_historico.buscar_contexto_etapa20',
            side_effect=AssertionError('Replay não precisa do link para novo envio'),
        ), patch('workers.worker_flow.response_flow.flow_sender.resolve_etapa20') as resolver:
            contexto = valida_historico(mensagem, {
                'id_cliente': 18, 'id_unidade': 1, 'conversa': conversa,
            }, cursor)
            envio = flow_sender(contexto)
        resolver.assert_not_called()
        self.assertTrue(envio['resposta_ja_existia'])
        self.assertEqual(envio['id_etapa_resultante'], 21)
        self.assertEqual(envio['evento_transicao'], 'agendamento_confirmado')

    def test_locks_fila_e_fencing_continuam_funcionando_apos_remapeamento(self):
        self.executar()
        with self.conn.cursor() as cursor:
            ok, nova_versao = tentar_lock_conversa(18, cursor)
            self.assertTrue(ok)
            self.assertGreater(nova_versao, 8)
            self.assertFalse(unlock_conversa(18, 8, cursor))
            self.assertTrue(unlock_conversa(18, nova_versao, cursor))
        self.assertEqual(self.conn.execute(
            'SELECT id_etapa_atual,status_ativa,followup_stage FROM chatbot.conversa WHERE id_conversa=22'
        ).fetchone(), (24,False,1))
