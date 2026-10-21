"""Consulta de idade: identidade, período, funil e autorização do relatório."""

from datetime import datetime, timedelta, timezone
import sqlite3
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from django.db import DatabaseError
from django.test import Client

from monitoramento.faixa_etaria import (
    consultar_faixa_etaria, distribuir_dependentes_por_titular,
)
from monitoramento.periodos import resolver_periodo
from monitoramento import services
from core.repositories.monitoramento import painel as repositorio


def perfil(cliente, *, dependente=None, idade=60, funil=False, nome='Ana'):
    return {
        'id_cliente': cliente, 'status_dependente': dependente is not None,
        'idade_titular': idade if dependente is None else 40,
        'idade_dependente': idade if dependente is not None else None,
        'id_dependente': dependente, 'nome_dependente': nome,
        'foi_funil': funil,
    }


class ContagemFaixaEtariaTests(unittest.TestCase):
    def test_titular_unico_e_dependentes_por_cadastro_sem_transferir_funil(self):
        linhas = [perfil(1), perfil(1, funil=True), perfil(1, funil=True),
                  perfil(1, dependente=10), perfil(1, dependente=11, funil=True),
                  perfil(1, dependente=11, funil=True), perfil(2, idade=59)]
        # Os dois cadastros possuem o mesmo nome e contam separadamente.
        todos = consultar_faixa_etaria(linhas, 60, 'todos')
        self.assertEqual(todos['titulares'], {'leads': 1, 'funil': 1})
        self.assertEqual(todos['dependentes'], {'leads': 2, 'funil': 1})
        self.assertEqual((todos['total'], todos['contatos']), (3, 1))
        for publico, total in (('titulares', 1), ('dependentes', 2)):
            resultado = consultar_faixa_etaria(linhas, 60, publico)
            self.assertEqual(resultado['total'], total)
            outro = 'dependentes' if publico == 'titulares' else 'titulares'
            self.assertEqual(resultado[outro], {'leads': 0, 'funil': 0})

    def test_idade_da_pessoa_atendida_limite_inclusivo_e_100_anos(self):
        linhas = [perfil(1, idade=59), perfil(2, idade=60), perfil(3, idade=100),
                  perfil(4, dependente=40, idade=60),
                  perfil(5, dependente=50, idade=10)]
        linhas[-1]['idade_titular'] = 80
        self.assertEqual(consultar_faixa_etaria(linhas, 60, 'todos')['total'], 3)
        self.assertEqual(consultar_faixa_etaria(linhas, 100, 'todos')['total'], 1)
        self.assertEqual(consultar_faixa_etaria(linhas, 101, 'todos')['total'], 0)

    def test_idade_ausente_ou_invalida_e_rota_desconhecida_nao_sao_inferidas(self):
        linhas = [perfil(i, idade=idade) for i, idade in enumerate(
            (None, True, False, 0, -1, 60.5, '60'))]
        linhas.append({**perfil(100), 'status_dependente': None})
        self.assertEqual(consultar_faixa_etaria(linhas, 1, 'todos')['total'], 0)

    def test_distribuicao_ignora_placeholder_e_nao_depende_da_idade_minima(self):
        linhas = [perfil(1, dependente=10, idade=10),
                  perfil(2, dependente=20, idade=70),
                  perfil(2, dependente=21, idade=None),
                  perfil(2, dependente=21, idade=None),
                  perfil(3, dependente=30, idade=None, nome=''), perfil(4)]
        self.assertEqual(distribuir_dependentes_por_titular(linhas), {
            'titulares': 2, 'dependentes': 3,
            'grupos': [{'dependentes_por_titular': 1, 'titulares': 1},
                       {'dependentes_por_titular': 2, 'titulares': 1}],
        })
        self.assertEqual(distribuir_dependentes_por_titular([])['grupos'], [])

    def test_servico_preserva_unidade_e_janela_do_relatorio(self):
        fim = datetime(2026, 9, 24, 17, 32, tzinfo=timezone.utc)
        for chave in ('total', '7d', '30d'):
            periodo = resolver_periodo(chave, agora=fim)
            with self.subTest(chave=chave), patch.object(services, 'connection', MagicMock()), \
                    patch.object(repositorio, 'buscar_perfis', return_value=[perfil(1)]) as buscar:
                resultado = services.carregar_faixa_etaria(
                    SimpleNamespace(id_unidade=20), periodo, 60, 'todos')
                self.assertEqual(buscar.call_args.args[:3], (20, periodo.inicio, fim))
                self.assertEqual(resultado['total'], 1)
                self.assertEqual(resultado['periodo']['chave'], chave)
                if chave == '7d':
                    self.assertEqual(fim - periodo.inicio, timedelta(hours=168))


class ConsultaPerfisSQLTests(unittest.TestCase):
    def test_sql_real_filtra_contato_unidade_e_envio_confirmado_no_periodo(self):
        banco = sqlite3.connect(':memory:')
        self.addCleanup(banco.close)
        banco.executescript('''
            ATTACH DATABASE ':memory:' AS chatbot;
            CREATE TABLE chatbot.cliente (id_cliente INTEGER, idade INTEGER);
            CREATE TABLE chatbot.conversa (
                id_cliente INTEGER, id_conversa INTEGER, id_unidade INTEGER,
                status_dependente INTEGER);
            CREATE TABLE chatbot.dependente (
                id_conversa INTEGER, id_dependente INTEGER, nome_dependente TEXT, idade INTEGER);
            CREATE TABLE chatbot.historico_mensagens (
                id_conversa INTEGER, quem_enviou TEXT, received_data_hora TEXT);
            CREATE TABLE chatbot.funil_envios (
                id_conversa INTEGER, status TEXT, enviado_em TEXT);
            INSERT INTO chatbot.cliente VALUES (1,60),(2,75),(3,80),(4,90);
            INSERT INTO chatbot.conversa VALUES
                (1,1,10,0),(1,2,10,0),(1,3,10,1),(1,4,10,1),
                (2,5,20,0),(3,6,10,0),(4,7,10,0);
            INSERT INTO chatbot.dependente VALUES (3,30,'Ana',60),(4,40,'Ana',70);
            INSERT INTO chatbot.historico_mensagens VALUES
                (1,'cliente','2026-09-17 17:32:00'),
                (1,'cliente','2026-09-18 17:32:00'),
                (2,'cliente','2026-09-20 17:32:00'),
                (3,'cliente','2026-09-20 17:32:00'),
                (4,'cliente','2026-09-20 17:32:00'),
                (5,'cliente','2026-09-20 17:32:00'),
                (6,'cliente','2026-09-17 17:31:59'),
                (6,'bot','2026-09-20 17:32:00'),
                (7,'cliente','2026-09-24 17:32:00');
            INSERT INTO chatbot.funil_envios VALUES
                (1,'sent','2026-09-17 17:31:59'),
                (2,'sent','2026-09-17 17:32:00'),
                (3,'sent','2026-09-24 17:32:00'),
                (3,'pending','2026-09-20 17:32:00'),
                (4,'sent','2026-09-20 17:32:00');
        ''')
        class CursorSQLite:
            def execute(self, sql, parametros):
                self.cursor = banco.execute(sql.replace('%s', '?'), parametros)
                self.description = self.cursor.description

            def fetchall(self):
                # SQLite representa booleanos como inteiros; PostgreSQL retorna bool.
                return [(*linha[:2], bool(linha[2]), *linha[3:-1], bool(linha[-1]))
                        for linha in self.cursor.fetchall()]

        inicio, fim = '2026-09-17 17:32:00', '2026-09-24 17:32:00'
        linhas = repositorio.buscar_perfis(10, inicio, fim, CursorSQLite())
        self.assertEqual({p['id_conversa'] for p in linhas}, {1, 2, 3, 4})
        self.assertEqual(len(linhas), 4)
        resultado = consultar_faixa_etaria(linhas, 60, 'todos')
        self.assertEqual(resultado['titulares'], {'leads': 1, 'funil': 1})
        self.assertEqual(resultado['dependentes'], {'leads': 2, 'funil': 1})
        outras = repositorio.buscar_perfis(20, inicio, fim, CursorSQLite())
        self.assertEqual([p['id_cliente'] for p in outras], [2])
        historico = repositorio.buscar_perfis(10, None, fim, CursorSQLite())
        self.assertEqual({p['id_conversa'] for p in historico}, {1, 2, 3, 4, 6})


class ApiFaixaEtariaTests(unittest.TestCase):
    ROTA = '/dados/relatorio/faixa-etaria/'

    @classmethod
    def setUpClass(cls):
        from tests.unit.test_monitoramento_login import LoginMonitoramentoTests
        cls.cenario_classe = LoginMonitoramentoTests
        cls.cenario_classe.setUpClass()

    @classmethod
    def tearDownClass(cls):
        cls.cenario_classe.tearDownClass()

    def setUp(self):
        self.cenario = self.cenario_classe(
            methodName='test_formulario_oculta_senha_e_nao_oferece_cadastro_ou_recuperacao')
        self.cenario.setUp()
        self.addCleanup(self.cenario.doCleanups)
        self.cliente = self.cenario.cliente

    def test_sessao_e_escopo_da_unidade(self):
        params = {'idade_minima': '60', 'publico': 'todos', 'periodo': '7d', 'id_unidade': '999'}
        with patch('monitoramento.views.carregar_faixa_etaria', return_value={}) as carregar:
            self.assertEqual(self.cliente.get(self.ROTA, params).status_code, 401)
            carregar.assert_not_called()
            for usuario, unidade in ((self.cenario.usuario_a, 10), (self.cenario.usuario_b, 20)):
                self.cliente = Client()
                self.cliente.force_login(usuario)
                resposta = self.cliente.get(self.ROTA, params)
                self.assertEqual(resposta.status_code, 200)
                self.assertIn('no-store', resposta['Cache-Control'])
                args = carregar.call_args.args
                self.assertEqual((args[0].id_unidade, args[1].chave, *args[2:]),
                                 (unidade, '7d', 60, 'todos'))
            with self.cenario.banco.cursor() as cursor:
                cursor.execute('UPDATE unidade SET id_usuario_monitoramento = NULL WHERE id_unidade = 20')
            self.assertEqual(self.cliente.get(self.ROTA, params).status_code, 403)

    def test_parametros_invalidos_e_multiplas_opcoes_sao_recusados(self):
        self.cliente.force_login(self.cenario.usuario_a)
        invalidos = ['', 'idade_minima=60', 'publico=todos',
                     'idade_minima=60&publico=todos&publico=titulares',
                     'idade_minima=60&idade_minima=70&publico=todos',
                     'idade_minima=60&publico=todos&periodo=7d&periodo=30d',
                     'idade_minima=60&publico=todos&periodo=invalido',
                     'idade_minima=60&publico=todos,titulares']
        invalidos += [f'idade_minima={idade}&publico=todos'
                      for idade in ('-1', '0', '1.5', 'abc', '1000', '1e2')]
        with patch('monitoramento.views.carregar_faixa_etaria') as carregar:
            for query in invalidos:
                with self.subTest(query=query):
                    self.assertEqual(self.cliente.get(self.ROTA + '?' + query).status_code, 400)
            self.assertEqual(self.cliente.post(self.ROTA).status_code, 405)
            carregar.assert_not_called()

    def test_falha_de_banco_nao_vira_contagem_zero_nem_expoe_detalhes(self):
        self.cliente.force_login(self.cenario.usuario_a)
        with patch('monitoramento.views.carregar_faixa_etaria', side_effect=DatabaseError('segredo SQL')):
            resposta = self.cliente.get(self.ROTA, {'idade_minima': '60', 'publico': 'todos'})
        self.assertEqual(resposta.status_code, 503)
        self.assertIn('erro', resposta.json())
        self.assertNotIn('segredo', resposta.content.decode())
