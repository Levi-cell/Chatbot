"""Fronteiras da política, recuperação atual e encaminhamentos registrados."""

from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
import sqlite3
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlsplit

from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory
from core.validacoes.suporte_por_idade import validar_idade_minima_suporte
from core.repositories.fluxo.contextos.etapa6 import buscar_contexto_etapa6
from core.repositories.monitoramento import painel as repositorio
from core.integrations.whatsapp.messages.etapa6_messages import montar_mensagem_suporte_idoso_etapa6
from core.integrations.whatsapp.pywa_functions.pywa_senders import etapa6 as sender
from monitoramento import services
from monitoramento.apresentacao import montar_relatorio, classificar_faixa
from monitoramento.periodos import PERIODOS, resolver_periodo
from webhook.admin import UnidadeAdmin
from webhook.models import Unidade
from tests.helpers import FakeCursor
from tests.unit.test_suporte_idoso_email_obrigatorio import contexto_etapa6, contexto_envio
from workers.worker_flow.response_flow.etapas import resolver_etapa6
from workers.worker_flow.transacoes import efeitos_transicao, encerramento_atendimento


LIMITES = (None, 50, 60, 70, 80, 90)

# Amostra histórica independente do catálogo atual: precisa sobreviver ao deploy.
MENSAGEM_LEGADA = (
    'Entendi. Para oferecer um atendimento mais adequado, esta unidade '
    'realiza o suporte a clientes com {limite} anos ou mais diretamente com a '
    'nossa equipe comercial.\n\n'
    'Vou te passar o contato para continuar o atendimento. Basta clicar '
    'no botão abaixo.'
)


class SuportePorIdadeTests(unittest.TestCase):
    def test_dominio_contexto_e_formulario_modelo(self):
        campo = Unidade._meta.get_field('idade_minima_suporte')
        for limite in LIMITES:
            with self.subTest(limite=limite):
                self.assertEqual(validar_idade_minima_suporte(limite), limite)
                self.assertEqual(campo.clean(limite, Unidade()), limite)
                contexto = buscar_contexto_etapa6(10, 1, FakeCursor(
                    fetchone_result=('5571999999999', False, limite, 'Maria', None, 'Suh', 'feminino')
                ))
                self.assertEqual(contexto['idade_minima_suporte'], limite)
                self.assertEqual(contexto['nome_agente_unidade'], 'Suh')
                self.assertEqual(contexto['genero_agente_unidade'], 'feminino')
        self.assertEqual(list(campo.formfield().choices), [(None, 'Desativado')] + [
            (idade, f'{idade}+') for idade in LIMITES[1:]
        ])
        for invalido in (True, False, 0, -1, 49, 55, 100, '60', 60.0):
            with self.subTest(invalido=invalido), self.assertRaises(ValueError):
                validar_idade_minima_suporte(invalido)
        with self.assertRaises(ValueError):
            buscar_contexto_etapa6(10, 1, FakeCursor(
                fetchone_result=(None, False, True, None, None, 'Suh', 'feminino')
            ))

    def test_admin_exige_contato_ao_ativar_e_ao_remover_numero(self):
        admin = UnidadeAdmin(Unidade, AdminSite())
        request = RequestFactory().get('/admin/')
        request.user = SimpleNamespace(has_perm=lambda *_: True)
        instance = Unidade(id_unidade=1)
        with patch.object(admin, '_validar_cache_unidades_form'), patch.object(
            admin, '_preparar_meta_antes_de_salvar'
        ) as meta:
            form_class = admin.get_form(request, instance, change=True,
                                        fields=['idade_minima_suporte', 'numero_comercial'])
            for limite in LIMITES:
                for telefone in ('', '123', '(71) 99999-9999'):
                    with self.subTest(limite=limite, telefone=telefone):
                        form = form_class(data={
                            'idade_minima_suporte': '' if limite is None else str(limite),
                            'numero_comercial': telefone,
                        }, instance=instance)
                        esperado = limite is None or telefone == '(71) 99999-9999'
                        self.assertEqual(form.is_valid(), esperado, form.errors)
                        if not esperado:
                            self.assertIn('numero_comercial', form.errors)
            for invalido in ('55', '100', 'True'):
                form = form_class(data={'idade_minima_suporte': invalido,
                                        'numero_comercial': '(71) 99999-9999'}, instance=instance)
                self.assertFalse(form.is_valid())
            meta.assert_not_called()

    def test_matriz_titulares_dependentes_e_100_mais(self):
        caminhos = {
            'suporte': 'enviar_etapa6_suporte_idoso',
            'cem': 'enviar_etapa6_idade_acima_99',
            'menor': 'enviar_etapa6_cliente_menor_18',
            'crianca': 'enviar_etapa6_dependente_menor_5',
            'titular': 'enviar_etapa7_cliente',
            'dependente': 'enviar_etapa7_dependente',
        }
        for limite in LIMITES:
            idades = {4, 5, 17, 18, 49, 50, 59, 60, 69, 70, 79, 80, 89, 90, 99, 100}
            for idade in sorted(idades):
                for dependente in (False, True):
                    for bpa in (False, True):
                        contexto = contexto_etapa6(idade, suporte=limite, dependente=dependente)
                        contexto['bpa_ativo_unidade'] = bpa
                        esperado = (
                            'cem' if idade >= 100 else
                            'suporte' if not dependente and limite is not None and idade >= limite else
                            'menor' if not dependente and idade < 18 else
                            'crianca' if dependente and idade < (4 if bpa else 5) else
                            'dependente' if dependente else 'titular'
                        )
                        with self.subTest(limite=limite, idade=idade, dependente=dependente, bpa=bpa), ExitStack() as stack:
                            mocks = {nome: stack.enter_context(patch.object(
                                resolver_etapa6, funcao,
                                return_value=contexto_envio(7 if nome in ('titular', 'dependente') else 6),
                            )) for nome, funcao in caminhos.items()}
                            resultado = resolver_etapa6.resolve_etapa6(contexto)
                            self.assertEqual([n for n,m in mocks.items() if m.called], [esperado])
                            if esperado == 'suporte':
                                self.assertEqual(mocks['suporte'].call_args.args[-1], limite)
                                self.assertEqual(resultado['id_etapa_resultante'], 6)
                                self.assertNotIn('evento_transicao', resultado)
                                self.assertEqual(resultado['idade_aluno'], idade)

    def test_chave_ausente_erro_nao_desativa_silenciosamente(self):
        contexto = contexto_etapa6(65)
        del contexto['idade_minima_suporte']
        with self.assertRaises(KeyError), patch.object(sender, 'conta_wa') as conta:
            resolver_etapa6.resolve_etapa6(contexto)
        conta.assert_not_called()

    def test_encaminhamento_completo_padroniza_faixas_e_preenche_contato(self):
        mensagem_esperada = (
            'Certo, olha, para idades mais avançadas oferecemos um atendimento '
            'personalizado com o nosso time! 😊\n\n'
            'Para entrar em contato, basta clicar no botão abaixo.'
        )
        for limite in LIMITES[1:]:
            for genero, nome_agente, artigo in (('feminino', 'Mia', 'a'), ('masculino', 'Léo', 'o')):
                with self.subTest(limite=limite, genero=genero), patch.object(sender, 'conta_wa') as conta:
                    conta.return_value.send_message.return_value = SimpleNamespace(id='wamid.teste')
                    contexto = contexto_etapa6(limite + 1, suporte=limite)
                    contexto.update(
                        nome_agente_unidade=nome_agente, genero_agente_unidade=genero,
                        nome_cliente='Ana & José', idade_cliente=20,
                    )
                    envio = resolver_etapa6.resolve_etapa6(contexto)
                    enviado = conta.return_value.send_message.call_args.kwargs
                    self.assertEqual(enviado['text'], mensagem_esperada)
                    self.assertEqual(enviado['text'], envio['mensagem_bot'])
                    self.assertEqual(enviado['buttons'].title, 'Falar agora')
                    link = urlsplit(enviado['buttons'].url)
                    self.assertEqual((link.scheme, link.netloc, link.path), ('https', 'wa.me', '/5571999999999'))
                    self.assertEqual(parse_qs(link.query), {'text': [
                        f'Olá, vim do atendimento com {artigo} {nome_agente}, '
                        f'me chamo Ana & José, tenho {limite + 1} anos '
                        'e gostaria de reservar uma demonstração prática.'
                    ]})
                    self.assertEqual(envio['tipo_mensagem'], 'interactive_cta_url')
                    self.assertEqual(envio['motivo_encerramento'], 'encaminhado_suporte_idoso')
                    self.assertEqual(envio['idade_aluno'], limite + 1)
                    conta.return_value.send_message.assert_called_once()
        with self.assertRaises(ValueError):
            montar_mensagem_suporte_idoso_etapa6(None)

    def test_dados_ausentes_nao_geram_texto_incorreto_no_botao(self):
        for campo, valor in (
            ('nome_cliente', None), ('nome_agente_unidade', ''),
            ('genero_agente_unidade', 'desconhecido'),
        ):
            contexto = contexto_etapa6(71, suporte=70)
            contexto[campo] = valor
            with self.subTest(campo=campo), patch.object(sender, 'conta_wa') as conta:
                with self.assertRaises(ValueError):
                    resolver_etapa6.resolve_etapa6(contexto)
                conta.assert_not_called()

    def test_persistencia_50_a_99_e_encerramento_sem_bloqueio(self):
        for idade in (50, 59, 60, 99):
            contexto = contexto_etapa6(idade, suporte=50)
            envio = contexto_envio(6)
            envio.update(encerrar_atendimento=True, motivo_encerramento='encaminhado_suporte_idoso', idade_aluno=idade)
            cursor = object()
            with patch.object(efeitos_transicao, 'atualizar_idade_cliente') as salvar:
                efeitos_transicao.atualizar_banco_conforme_transicao_de_etapa(contexto, envio, cursor)
            salvar.assert_called_once_with(5, idade, cursor)
            intencao = encerramento_atendimento.resolver_intencao_encerramento(contexto, envio, cursor)
            self.assertEqual(intencao['bloqueio_dias'], 0)
            self.assertFalse(intencao['excluir_dependente'])

    def test_recuperacao_reconhece_variantes_mas_usa_limite_atual(self):
        textos = [MENSAGEM_LEGADA.format(limite=limite) for limite in LIMITES[1:]]
        textos.append(montar_mensagem_suporte_idoso_etapa6(50))
        for texto_enviado in textos:
            for atual, idade, encerra in ((70, 65, False), (70, 75, True), (None, 95, False), (50, 55, True)):
                contexto = contexto_etapa6(idade, suporte=atual)
                contexto['resposta_bot_para_mensagem_atual'] = {
                    'tipo_mensagem': 'interactive_cta_url',
                    'conteudo_texto': 'Olá novamente, Maria!\n\n' + texto_enviado,
                }
                with self.subTest(texto=texto_enviado, atual=atual, idade=idade):
                    intencao = encerramento_atendimento.resolver_intencao_encerramento(
                        contexto, {'resposta_ja_existia': True, 'id_etapa_resultante': 6}, object()
                    )
                    self.assertEqual(intencao is not None, encerra)
        for texto, tipo in (('Procure o comercial', 'interactive_cta_url'),
                            (montar_mensagem_suporte_idoso_etapa6(50), 'text')):
            contexto['idade_minima_suporte'] = 50
            contexto['resposta_bot_para_mensagem_atual'] = {'tipo_mensagem': tipo, 'conteudo_texto': texto}
            self.assertIsNone(encerramento_atendimento.resolver_intencao_encerramento(
                contexto, {'resposta_ja_existia': True}, object()
            ))


class EncaminhamentosRelatorioTests(unittest.TestCase):
    def test_sql_deduplica_por_unidade_data_e_motivo_sem_depender_da_ultima_conversa(self):
        conn = sqlite3.connect(':memory:')
        self.addCleanup(conn.close)
        conn.execute("ATTACH DATABASE ':memory:' AS chatbot")
        conn.execute('''CREATE TABLE chatbot.conversa (
            id_conversa INTEGER, id_unidade INTEGER, id_cliente INTEGER,
            status_ativa BOOLEAN, motivo_encerramento TEXT, finalizou_em TEXT
        )''')
        motivo = 'encaminhado_suporte_idoso'
        conn.executemany('INSERT INTO chatbot.conversa VALUES (?, ?, ?, ?, ?, ?)', [
            (1, 10, 1, False, motivo, '2026-09-01'),
            (2, 10, 1, False, motivo, '2026-09-02'),
            (3, 10, 1, True, None, None),
            (4, 10, 2, False, motivo, '2026-08-31'),
            (5, 10, 3, False, motivo, '2026-10-01'),
            (6, 20, 4, False, motivo, '2026-09-05'),
            (7, 10, 5, False, 'idade_invalida', '2026-09-05'),
            (8, 10, 6, True, motivo, '2026-09-05'),
            (9, 10, 7, False, motivo, None),
        ])

        class CursorSQLite:
            def execute(self, sql, params): self.cursor = conn.execute(sql.replace('%s', '?'), params)
            def fetchone(self): return self.cursor.fetchone()

        cursor = CursorSQLite()
        self.assertEqual(repositorio.contar_encaminhados_comercial_por_idade(10, '2026-09-01', '2026-10-01', cursor), 1)
        self.assertEqual(repositorio.contar_encaminhados_comercial_por_idade(10, None, '2026-10-01', cursor), 2)
        self.assertEqual(repositorio.contar_encaminhados_comercial_por_idade(20, '2026-09-01', '2026-10-01', cursor), 1)
        self.assertEqual(repositorio.contar_encaminhados_comercial_por_idade(30, None, '2026-10-01', cursor), 0)

    def test_servico_propaga_unidade_periodos_politica_e_falha(self):
        fim = datetime(2026, 9, 11, tzinfo=timezone.utc)
        for chave in PERIODOS:
            periodo = resolver_periodo(chave, agora=fim)
            with self.subTest(periodo=chave), ExitStack() as stack:
                stack.enter_context(patch.object(services, 'connection', MagicMock()))
                stack.enter_context(patch.object(repositorio, 'buscar_unidade', return_value={
                    'nome_unidade': 'Teste', 'bpa_ativo': False, 'idade_minima_suporte': None,
                    'inicio_historico': fim - timedelta(days=300),
                }))
                stack.enter_context(patch.object(repositorio, 'buscar_metricas', return_value={}))
                for nome in ('buscar_perfis', 'buscar_satisfacao', 'buscar_etapas', 'buscar_atividade'):
                    stack.enter_context(patch.object(repositorio, nome, return_value=[]))
                contar = stack.enter_context(patch.object(repositorio, 'contar_encaminhados_comercial_por_idade', return_value=3))
                payload = services.carregar_relatorio(SimpleNamespace(id_unidade=10), periodo)
                self.assertEqual(contar.call_args.args[:3], (10, periodo.inicio, periodo.fim))
                self.assertEqual(payload['encaminhados_comercial_por_idade'], 3)
                self.assertIsNone(payload['unidade']['idade_minima_suporte'])
                contar.side_effect = RuntimeError('banco indisponível')
                with self.assertRaises(RuntimeError):
                    services.carregar_relatorio(SimpleNamespace(id_unidade=10), periodo)

    def test_card_nao_inventa_zero_e_tags_permanecem_fixas(self):
        for invalido in (None, True, -1, '1'):
            with self.assertRaises(ValueError):
                montar_relatorio({}, None, {}, {}, [], [], encaminhados_comercial_por_idade=invalido)
        self.assertEqual(classificar_faixa(59), 'adulto')
        self.assertEqual(classificar_faixa(60), 'idoso')
        perfis = services._agrupar_perfis([
            {'id_cliente': 1, 'status_dependente': False, 'idade_titular': 65, 'foi_funil': True},
        ], bpa_ativo=False)
        idoso = next(p for p in perfis['linhas'] if p['chave'] == 'titular_idoso')
        self.assertEqual(idoso['funil'], 1)
        self.assertEqual(idoso['taxa_funil'], 100.0)


if __name__ == '__main__':
    unittest.main()
