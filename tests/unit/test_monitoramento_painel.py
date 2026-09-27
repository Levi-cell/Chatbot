"""Contratos de leitura, isolamento e exportação do painel de monitoramento."""

import csv
from datetime import datetime, timedelta, timezone
from io import StringIO
import unittest
from unittest.mock import patch

from django.test import Client

from monitoramento.apresentacao import (
    botoes_para_mensagem,
    consolidar_conversas,
    montar_relatorio,
    normalizar_telefone_google,
)
from monitoramento.periodos import PERIODOS, resolver_periodo
from monitoramento.services import _agrupar_perfis
from core.repositories.monitoramento import painel as repositorio_painel
from tests.fixtures.monitoramento_painel import CONTATOS, CONVERSAS, MENSAGENS, RELATORIO


CABECALHO_OFICIAL_GOOGLE_CONTATOS = [
    'Name Prefix', 'First Name', 'Middle Name', 'Last Name', 'Name Suffix',
    'Phonetic First Name', 'Phonetic Middle Name', 'Phonetic Last Name',
    'Nickname', 'File As', 'E-mail 1 - Label', 'E-mail 1 - Value',
    'Phone 1 - Label', 'Phone 1 - Value', 'Address 1 - Label',
    'Address 1 - Country', 'Address 1 - Street',
    'Address 1 - Extended Address', 'Address 1 - City', 'Address 1 - Region',
    'Address 1 - Postal Code', 'Address 1 - PO Box', 'Organization Name',
    'Organization Title', 'Organization Department', 'Birthday',
    'Event 1 - Label', 'Event 1 - Value', 'Relation 1 - Label',
    'Relation 1 - Value', 'Website 1 - Label', 'Website 1 - Value',
    'Custom Field 1 - Label', 'Custom Field 1 - Value', 'Notes', 'Labels',
]


class MonitoramentoPainelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from tests.unit.test_monitoramento_login import LoginMonitoramentoTests
        cls.cenario_classe = LoginMonitoramentoTests
        cls.cenario_classe.setUpClass()

    @classmethod
    def tearDownClass(cls):
        cls.cenario_classe.tearDownClass()
        super().tearDownClass()

    def setUp(self):
        self.cenario = self.cenario_classe(
            methodName='test_formulario_oculta_senha_e_nao_oferece_cadastro_ou_recuperacao'
        )
        self.cenario.setUp()
        self.cliente = self.cenario.cliente

    def tearDown(self):
        self.cenario.doCleanups()

    def autenticar(self, usuario=None):
        self.cliente.force_login(usuario or self.cenario.usuario_a)

    def test_painel_exige_sessao_e_entrega_interface_somente_leitura(self):
        self.assertEqual(self.cliente.get('/').status_code, 302)
        for rota in ('/dados/conversas/', '/dados/relatorio/', '/contatos.csv'):
            with self.subTest(rota=rota):
                self.assertEqual(self.cliente.get(rota).status_code, 401)
        self.autenticar()
        resposta = self.cliente.get('/')
        html = resposta.content.decode()
        self.assertEqual(resposta.status_code, 200)
        self.assertIn('Conversas', html)
        self.assertIn('Relatórios', html)
        self.assertIn('somente para monitoramento', html)
        self.assertNotIn('Enviar mensagem', html)
        self.assertIn("default-src 'self'", resposta.headers['Content-Security-Policy'])
        self.assertIn('no-store', resposta.headers['Cache-Control'])

    def test_endpoints_usam_unidade_do_usuario_autenticado(self):
        for usuario, unidade in ((self.cenario.usuario_a, 10), (self.cenario.usuario_b, 20)):
            with self.subTest(unidade=unidade):
                self.cliente = Client()
                self.autenticar(usuario)
                with patch('monitoramento.views.carregar_conversas', return_value=CONVERSAS) as carregar:
                    resposta = self.cliente.get('/dados/conversas/')
                self.assertEqual(resposta.status_code, 200)
                self.assertEqual(carregar.call_args.args[0].id_unidade, unidade)

    def test_mensagens_de_cliente_inexistente_ou_de_outro_escopo_nao_vazam(self):
        self.autenticar()
        with patch('monitoramento.views.carregar_mensagens', return_value={'id_cliente': 999, 'mensagens': []}) as carregar:
            resposta = self.cliente.get('/dados/conversas/999/')
        self.assertEqual(resposta.status_code, 404)
        self.assertEqual(carregar.call_args.args[0].id_unidade, 10)
        self.assertNotIn('Unidade B', resposta.content.decode())

    def test_periodo_invalido_e_metodos_de_escrita_sao_recusados(self):
        self.autenticar()
        with patch('monitoramento.views.carregar_conversas') as carregar:
            self.assertEqual(self.cliente.get('/dados/conversas/?periodo=qualquer').status_code, 400)
            carregar.assert_not_called()
        for rota in ('/dados/conversas/', '/dados/relatorio/', '/contatos.csv'):
            self.assertEqual(self.cliente.post(rota).status_code, 405)

    def test_csv_google_completo_e_elegivel(self):
        self.autenticar()
        with patch('monitoramento.views.carregar_contatos', return_value=CONTATOS):
            completo = self.cliente.get('/contatos.csv?tipo=todos')
            elegivel = self.cliente.get('/contatos.csv?tipo=elegiveis')
        self.assertFalse(completo.content.startswith(b'\xef\xbb\xbf'))
        linhas = list(csv.reader(StringIO(completo.content.decode('utf-8'))))
        self.assertEqual(linhas[0], CABECALHO_OFICIAL_GOOGLE_CONTATOS)
        self.assertTrue(all(len(linha) == 36 for linha in linhas))
        self.assertEqual(linhas[1][1], 'Edcarlos')
        self.assertEqual(linhas[1][3], 'Silva')
        self.assertEqual(
            linhas[1][10:14],
            ['Work', 'edcarlos@example.com', 'Mobile', '+557194111866'],
        )
        self.assertTrue(all(not valor for valor in linhas[1][14:34]))
        self.assertEqual(
            linhas[1][34],
            'Contato exportado pelo monitoramento ESL Tech',
        )
        self.assertTrue(linhas[1][35])
        self.assertEqual(linhas[2][10:12], ['', ''])
        self.assertEqual(linhas[2][12:14], ['Mobile', '+557599111222'])
        self.assertEqual(len(linhas), 3)
        linhas_elegiveis = list(csv.reader(StringIO(elegivel.content.decode('utf-8'))))
        self.assertEqual(len(linhas_elegiveis), 2)
        self.assertTrue(all(len(linha) == 36 for linha in linhas_elegiveis))
        self.assertEqual(normalizar_telefone_google('(71) 94111-1866'), '+5571941111866')
        self.assertEqual(normalizar_telefone_google('123'), '')

        contato_invalido = [{
            'nome': 'Contato Inválido', 'email': 'sem-arroba',
            'waid_telefone': '557194111866',
        }]
        with patch('monitoramento.views.carregar_contatos', return_value=contato_invalido):
            elegivel = self.cliente.get('/contatos.csv?tipo=elegiveis')
        self.assertEqual(
            len(list(csv.reader(StringIO(elegivel.content.decode('utf-8'))))), 1
        )

    def test_csv_essencial_preserva_nome_completo_acentos_e_campos_vazios(self):
        self.autenticar()
        contatos = [
            {'nome': ' João da Silva ', 'email': 'joao@example.com', 'waid_telefone': '557194111866'},
            {'nome': None, 'email': None, 'waid_telefone': '557599111222'},
            {'nome': 'Sem telefone', 'email': 'outro@example.com', 'waid_telefone': None},
            {'nome': '=Nome; "especial"', 'email': '=1+1', 'waid_telefone': '123'},
        ]
        with patch('monitoramento.views.carregar_contatos', return_value=contatos):
            completo = self.cliente.get('/contatos.csv?formato=essencial&tipo=todos')
            elegivel = self.cliente.get('/contatos.csv?formato=essencial&tipo=elegiveis')
        self.assertTrue(completo.content.startswith(b'\xef\xbb\xbf'))
        linhas = list(csv.reader(StringIO(completo.content.decode('utf-8-sig')), delimiter=';'))
        self.assertEqual(linhas, [
            ['Nome', 'E-mail', 'Telefone'],
            ['João da Silva', 'joao@example.com', '7194111866'],
            ['', '', '7599111222'],
            ['Sem telefone', 'outro@example.com', ''],
            ["'=Nome; \"especial\"", "'=1+1", ''],
        ])
        self.assertEqual(
            list(csv.reader(StringIO(elegivel.content.decode('utf-8-sig')), delimiter=';')),
            linhas[:2],
        )
        self.assertIn('contatos_essenciais_total_todos.csv', completo['Content-Disposition'])
        self.assertIn('no-store', completo['Cache-Control'])

    def test_quatro_exports_respeitam_todos_periodos_e_unidade_autorizada(self):
        agora = datetime(2026, 9, 7, 12, tzinfo=timezone.utc)
        for usuario, unidade in ((self.cenario.usuario_a, 10), (self.cenario.usuario_b, 20)):
            self.cliente = Client()
            self.autenticar(usuario)
            for chave in ('total', *PERIODOS):
                periodo = resolver_periodo(chave, agora=agora)
                for formato in ('google', 'essencial'):
                    for tipo in ('todos', 'elegiveis'):
                        with self.subTest(unidade=unidade, periodo=chave, formato=formato, tipo=tipo):
                            with patch('monitoramento.views.resolver_periodo', return_value=periodo) as resolver, \
                                 patch('monitoramento.views.carregar_contatos', return_value=CONTATOS) as carregar:
                                resposta = self.cliente.get('/contatos.csv', {
                                    'formato': formato, 'tipo': tipo, 'periodo': chave,
                                    'id_unidade': 999,
                                })
                            self.assertEqual(resposta.status_code, 200)
                            resolver.assert_called_once_with(chave)
                            acesso, recebido = carregar.call_args.args
                            self.assertEqual(acesso.id_unidade, unidade)
                            self.assertEqual(recebido, periodo)
                            leitor = csv.reader(
                                StringIO(resposta.content.decode('utf-8-sig')),
                                delimiter=';' if formato == 'essencial' else ',',
                            )
                            linhas = list(leitor)
                            self.assertEqual(len(linhas), 2 if tipo == 'elegiveis' else 3)
                            self.assertTrue(all(len(linha) == (3 if formato == 'essencial' else 36) for linha in linhas))
                            self.assertEqual(
                                linhas[1][2 if formato == 'essencial' else 13],
                                '7194111866' if formato == 'essencial' else '+557194111866',
                            )
                            self.assertIn(f'_{chave}_{tipo}.csv', resposta['Content-Disposition'])

    def test_export_essencial_recusa_acesso_invalido_e_parametros_invalidos(self):
        rota = '/contatos.csv?formato=essencial'
        with patch('monitoramento.views.carregar_contatos') as carregar:
            self.assertEqual(self.cliente.get(rota).status_code, 401)
            self.autenticar()
            self.assertEqual(self.cliente.get(rota + '&periodo=invalido').status_code, 400)
            self.assertEqual(self.cliente.get('/contatos.csv?formato=invalido').status_code, 400)
            self.assertEqual(self.cliente.post(rota).status_code, 405)
            with self.cenario.banco.cursor() as cursor:
                cursor.execute('UPDATE unidade SET id_usuario_monitoramento = NULL WHERE id_unidade = 10')
            self.assertEqual(self.cliente.get(rota).status_code, 403)
            carregar.assert_not_called()

    def test_botoes_historicos_vem_do_catalogo_oficial(self):
        mensagem = {'quem_enviou': 'bot', 'tipo': 'interactive_button', 'id_etapa': 2}
        self.assertEqual(botoes_para_mensagem(mensagem), ['Para mim', 'Para um dependente'])
        mensagem['id_etapa'] = 12
        self.assertEqual(botoes_para_mensagem(mensagem), ['Nunca', 'Às vezes', 'Frequentemente'])
        mensagem['quem_enviou'] = 'cliente'
        self.assertEqual(botoes_para_mensagem(mensagem), [])

    def test_consolidacao_cria_tags_sem_misturar_unidades(self):
        linhas = [
            {'id_cliente': 1, 'id_conversa': 10, 'nome_cliente': 'Ana', 'waid_telefone': '5511',
             'status_dependente': True, 'idade_dependente': 12, 'foi_funil': False,
             'avaliada': False, 'ultima_atividade': '2026-09-01',
             'ultima_mensagem_id': 20, 'ultima_mensagem': 'Oi'},
            {'id_cliente': 1, 'id_conversa': 11, 'nome_cliente': 'Ana', 'waid_telefone': '5511',
             'status_dependente': False, 'idade_titular': 65, 'foi_funil': True,
             'avaliada': True, 'ultima_atividade': '2026-09-01',
             'ultima_mensagem_id': 21, 'ultima_mensagem': 'Olá'},
        ]
        resultado = consolidar_conversas(linhas)
        self.assertEqual(resultado[0]['ids_conversa'], [10, 11])
        self.assertEqual(resultado[0]['perfis'], ['dependente', 'menor', 'idoso'])
        self.assertEqual(resultado[0]['perfis_resumidos'], ['dependente_menor', 'idoso'])
        self.assertEqual(resultado[0]['ultima_mensagem'], 'Olá')

    def test_perfis_resumidos_distinguem_dependentes_e_titulares(self):
        cenarios = (
            (1, True, 12, 'dependente_menor'),
            (2, True, 35, 'dependente_adulto'),
            (3, True, 65, 'dependente_idoso'),
            (4, False, 35, 'adulto'),
            (5, False, 65, 'idoso'),
        )
        linhas = []
        for id_cliente, dependente, idade, esperado in cenarios:
            linhas.append({
                'id_cliente': id_cliente,
                'id_conversa': id_cliente * 10,
                'nome_cliente': f'Cliente {id_cliente}',
                'waid_telefone': f'551{id_cliente}',
                'status_dependente': dependente,
                'idade_dependente': idade if dependente else None,
                'idade_titular': None if dependente else idade,
                'foi_funil': False,
                'avaliada': False,
                'ultima_atividade': f'2026-09-0{id_cliente}',
                'ultima_mensagem_id': id_cliente,
                'ultima_mensagem': esperado,
            })

        resultado = {item['id_cliente']: item for item in consolidar_conversas(linhas)}
        for id_cliente, _dependente, _idade, esperado in cenarios:
            self.assertEqual(resultado[id_cliente]['perfis_resumidos'], [esperado])

    def test_periodos_finitos_possuem_comparacao_e_total_nao(self):
        finito = resolver_periodo('7d')
        total = resolver_periodo('total')
        self.assertEqual(finito.fim_anterior, finito.inicio)
        self.assertIsNotNone(finito.inicio_anterior)
        self.assertIsNone(total.inicio)
        self.assertIsNone(total.inicio_anterior)

    def test_comparacao_aceita_periodo_atual_sem_avaliacoes(self):
        relatorio = montar_relatorio(
            {'leads': 2, 'mensagens': 4, 'funil': 1, 'avaliacoes': 0, 'nota_media': None},
            {'leads': 1, 'mensagens': 2, 'funil': 0, 'avaliacoes': 1, 'nota_media': 5.0},
            {}, {}, [], [],
        )
        self.assertIsNone(relatorio['tendencias']['nota_media'])

    def test_perfil_so_conta_lead_totalmente_sem_classificacao(self):
        perfis = _agrupar_perfis([
            {'id_cliente': 1, 'status_dependente': None, 'idade_titular': 35,
             'idade_dependente': None, 'foi_funil': False},
            {'id_cliente': 1, 'status_dependente': False, 'idade_titular': 35,
             'idade_dependente': None, 'foi_funil': True},
            {'id_cliente': 2, 'status_dependente': None, 'idade_titular': 44,
             'idade_dependente': None, 'foi_funil': False},
        ], bpa_ativo=False)
        titular_adulto = next(
            item for item in perfis['linhas'] if item['chave'] == 'titular_adulto'
        )
        self.assertEqual(titular_adulto['leads'], 1)
        self.assertEqual(perfis['sem_classificacao'], 1)

    def test_relatorio_e_conversas_sao_serializados_sem_consultar_rds(self):
        self.autenticar()
        with patch('monitoramento.views.carregar_relatorio', return_value=RELATORIO):
            resposta = self.cliente.get('/dados/relatorio/?periodo=7d')
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(len(resposta.json()['etapas']), 22)
        with patch('monitoramento.views.carregar_mensagens', return_value=MENSAGENS[140]):
            resposta = self.cliente.get('/dados/conversas/140/')
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json()['mensagens'][1]['botoes'][0], 'Para mim')

    def test_todas_as_consultas_recebem_escopo_e_parametros_completos(self):
        class CursorContrato:
            description = [('valor',)]

            def __init__(self):
                self.execucoes = []

            def execute(self, sql, parametros):
                self.execucoes.append((sql, parametros))
                if sql.count('%s') != len(parametros):
                    raise AssertionError(
                        f'placeholders={sql.count("%s")} parametros={len(parametros)}'
                    )

            def fetchall(self):
                return []

            def fetchone(self):
                return None

        agora = datetime.now(timezone.utc)
        inicio = agora - timedelta(days=7)
        chamadas = (
            lambda c: repositorio_painel.buscar_unidade(10, c),
            lambda c: repositorio_painel.listar_conversas(10, inicio, agora, c),
            lambda c: repositorio_painel.buscar_mensagens(10, 99, inicio, agora, c),
            lambda c: repositorio_painel.buscar_metricas(10, inicio, agora, c),
            lambda c: repositorio_painel.buscar_perfis(10, inicio, agora, c),
            lambda c: repositorio_painel.buscar_satisfacao(10, inicio, agora, c),
            lambda c: repositorio_painel.buscar_etapas(10, inicio, agora, c),
            lambda c: repositorio_painel.buscar_atividade(10, inicio, agora, c, 'dia'),
            lambda c: repositorio_painel.listar_contatos(10, inicio, agora, c),
        )
        for chamada in chamadas:
            with self.subTest(chamada=chamada):
                cursor = CursorContrato()
                chamada(cursor)
                sql, parametros = cursor.execucoes[0]
                self.assertIn(10, parametros)
                self.assertIn('id_unidade', sql)
