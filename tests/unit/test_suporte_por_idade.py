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
from monitoramento.apresentacao import classificar_faixa
from monitoramento.encerramentos import montar_tabela_encerramentos
from monitoramento.periodos import PERIODOS, resolver_periodo
from webhook.admin import UnidadeAdmin
from webhook.models import Unidade
from tests.helpers import FakeCursor
from tests.unit.test_suporte_idoso_email_obrigatorio import contexto_etapa6, contexto_envio
from workers.worker_flow.response_flow.etapas import resolver_etapa6
from workers.worker_flow.transacoes import efeitos_transicao, encerramento_atendimento


LIMITES = (None, 50, 60, 70, 80)

# Amostra independente do catálogo atual: a produção ainda pode enviar esse texto.
MENSAGEM_LEGADA_SEM_FAIXA = (
    'Certo, olha, para idades mais avançadas oferecemos um atendimento '
    'personalizado com o nosso time! 😊\n\n'
    'Para entrar em contato, basta clicar no botão abaixo.'
)
MENSAGEM_ENCAMINHAMENTO_ATUAL = (
    'Certo, vou te passar o contato da nossa equipe para dar continuidade a sua experiência supera! 😊\n'
    'Para entrar em contato, basta clicar no botão abaixo.'
)
MENSAGEM_ANAMNESE_100_MAIS = (
    'Certo, olha, para idades mais avançadas vamos precisar realizar uma pequena '
    '*anamnese* com um dos nossos consultores.\n'
    'Basta clicar no botão abaixo para falar com nosso time e iniciar a anamnese! 😊\n\n'
    '_Nosso time vai orientar os próximos passos. 🧡_'
)


class SuportePorIdadeTests(unittest.TestCase):
    def test_dominio_contexto_e_formulario_modelo(self):
        campo = Unidade._meta.get_field('idade_minima_suporte')
        for limite in LIMITES:
            with self.subTest(limite=limite):
                self.assertEqual(validar_idade_minima_suporte(limite), limite)
                self.assertEqual(campo.clean(limite, Unidade()), limite)
                contexto = buscar_contexto_etapa6(10, 1, FakeCursor(
                    fetchone_result=('5571999999999', False, limite, 'Maria', None, 'Suh', 'feminino', 'Supera Centro')
                ))
                self.assertEqual(contexto['idade_minima_suporte'], limite)
                self.assertEqual(contexto['nome_agente'], 'Suh')
                self.assertEqual(contexto['genero_agente_unidade'], 'feminino')
                self.assertEqual(contexto['nome_unidade'], 'Supera Centro')
        self.assertEqual(list(campo.formfield().choices), [(None, 'Desativado')] + [
            (idade, f'{idade}+') for idade in LIMITES[1:]
        ])
        for invalido in (True, False, 0, -1, 49, 55, 90, 100, '60', 60.0):
            with self.subTest(invalido=invalido), self.assertRaises(ValueError):
                validar_idade_minima_suporte(invalido)
        with self.assertRaises(ValueError):
            buscar_contexto_etapa6(10, 1, FakeCursor(
                fetchone_result=(None, False, True, None, None, 'Suh', 'feminino', 'Supera Centro')
            ))

    def test_admin_exige_contato_ao_ativar_e_ao_remover_numero(self):
        admin = UnidadeAdmin(Unidade, AdminSite())
        request = RequestFactory().get('/admin/')
        request.user = SimpleNamespace(has_perm=lambda *_: True)
        instance = Unidade(id_unidade=1, link_agendamento="https://example.com")
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
                        esperado = telefone == '(71) 99999-9999'
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
            idades = {4, 5, 17, 18, 49, 50, 59, 60, 69, 70, 79, 80, 89, 90, 99, 100, 105}
            for idade in sorted(idades):
                for dependente in (False, True):
                    for bpa in (False, True):
                        contexto = contexto_etapa6(idade, suporte=limite, dependente=dependente)
                        contexto['bpa_ativo_unidade'] = bpa
                        esperado = (
                            'cem' if idade >= 90 else
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
        mensagem_esperada = MENSAGEM_ENCAMINHAMENTO_ATUAL
        for limite in LIMITES[1:]:
            for genero, nome_agente, artigo in (('feminino', 'Mia', 'a'), ('masculino', 'Léo', 'o')):
                with self.subTest(limite=limite, genero=genero), patch.object(sender, 'conta_wa') as conta:
                    conta.return_value.send_message.return_value = SimpleNamespace(id='wamid.teste')
                    contexto = contexto_etapa6(limite + 1, suporte=limite)
                    contexto.update(
                        nome_agente=nome_agente, genero_agente_unidade=genero,
                        nome_titular='Ana & José', idade_cliente=20,
                        nome_unidade='Supera São João & Centro + Sul',
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
                        'chatbot da unidade Supera São João & Centro + Sul. '
                        f'Me chamo Ana & José, tenho {limite + 1} anos '
                        'e gostaria de reservar minha experiência Supera.'
                    ]})
                    self.assertEqual(envio['tipo_mensagem'], 'interactive_cta_url')
                    self.assertEqual(envio['motivo_encerramento'], 'encaminhado_suporte_idoso')
                    self.assertEqual(envio['idade_aluno'], limite + 1)
                    conta.return_value.send_message.assert_called_once()
        with self.assertRaises(ValueError):
            montar_mensagem_suporte_idoso_etapa6(None)

    def test_acima_99_encaminha_ambas_rotas_com_anamnese_e_rodape(self):
        for limite in LIMITES:
            for dependente in (False, True):
                with self.subTest(limite=limite, dependente=dependente), patch.object(
                    sender, 'conta_wa'
                ) as conta:
                    conta.return_value.send_message.return_value = SimpleNamespace(id='wamid.cem')
                    contexto = contexto_etapa6(100, suporte=limite, dependente=dependente)
                    # Idades antigas não podem substituir a resposta atual.
                    contexto.update(idade_cliente=40, idade_dependente=70)
                    envio = resolver_etapa6.resolve_etapa6(contexto)
                    enviado = conta.return_value.send_message.call_args.kwargs
                    self.assertEqual(enviado['text'], MENSAGEM_ANAMNESE_100_MAIS)
                    self.assertEqual(enviado['text'], envio['mensagem_bot'])
                    link = urlsplit(enviado['buttons'].url)
                    self.assertEqual((link.scheme, link.netloc, link.path), ('https', 'wa.me', '/5571999999999'))
                    origem = (
                        'Olá, vim do atendimento com a Suh, '
                        'chatbot da unidade Supera Santo Antônio de Jesus. '
                    )
                    pedido = (
                        'Me chamo Maria e gostaria de reservar uma experiência Supera '
                        'para João, que tem 100 anos.'
                        if dependente else
                        'Me chamo Maria, tenho 100 anos '
                        'e gostaria de reservar minha experiência Supera.'
                    )
                    self.assertEqual(parse_qs(link.query), {'text': [origem + pedido]})
                    self.assertEqual(enviado['buttons'].title, 'Falar com Consultor')
                    self.assertEqual(envio['motivo_encerramento'], 'idade_acima_99')
                    self.assertEqual(envio['id_etapa_resultante'], 6)
                    self.assertNotIn('evento_transicao', envio)
                    conta.return_value.send_message.assert_called_once()

                    # A resposta comprovada de 100+ preserva o motivo legado: o corpo
                    # sozinho não prova qual limiar universal era vigente.
                    contexto['resposta_bot_para_mensagem_atual'] = {
                        'tipo_mensagem': 'interactive_cta_url',
                        'conteudo_texto': enviado['text'],
                    }
                    intencao = encerramento_atendimento.resolver_intencao_encerramento(
                        contexto, {'resposta_ja_existia': True}, object()
                    )
                    self.assertEqual(intencao['motivo'], 'idade_acima_99')
                    self.assertEqual(intencao['motivo_encerramento'], 'idade_invalida')
                    self.assertEqual(intencao['bloqueio_dias'], 0)

    def test_dados_ausentes_nao_geram_texto_incorreto_no_botao(self):
        for idade, dependente, suporte in (
            (71, False, 70), (100, False, None), (100, True, None),
        ):
            campos = [
                ('nome_titular', None), ('nome_agente', ''),
                ('genero_agente_unidade', 'desconhecido'), ('nome_unidade', ' '),
            ]
            if dependente:
                campos.append(('nome_dependente', None))
            for campo, valor in campos:
                contexto = contexto_etapa6(idade, suporte=suporte, dependente=dependente)
                contexto[campo] = valor
                with self.subTest(idade=idade, dependente=dependente, campo=campo), patch.object(sender, 'conta_wa') as conta:
                    with self.assertRaises(ValueError):
                        resolver_etapa6.resolve_etapa6(contexto)
                    conta.assert_not_called()

    def test_persistencia_50_a_99_e_encerramento_sem_bloqueio(self):
        for idade in (50, 59, 60, 99):
            contexto = contexto_etapa6(idade, suporte=50)
            envio = contexto_envio(6)
            envio.update(encerrar_atendimento=True, motivo_encerramento='encaminhado_suporte_idoso', idade_aluno=idade, limite_idade_encerramento=50)
            cursor = object()
            with patch.object(efeitos_transicao, 'atualizar_idade_cliente') as salvar:
                efeitos_transicao.atualizar_banco_conforme_transicao_de_etapa(contexto, envio, cursor)
            salvar.assert_called_once_with(5, idade, cursor)
            intencao = encerramento_atendimento.resolver_intencao_encerramento(contexto, envio, cursor)
            self.assertEqual(intencao['bloqueio_dias'], 0)
            self.assertFalse(intencao['excluir_dependente'])

    def test_recuperacao_reconhece_variantes_e_reconstroi_faixa_compativel(self):
        textos = [
            MENSAGEM_LEGADA_SEM_FAIXA,
            # Corpo salvo pela V1.5.2, antes da redução de espaçamento.
            'Certo, vou te passar o contato da nossa equipe para dar continuidade a sua experiência supera! 😊\n\n'
            'Para entrar em contato, basta clicar no botão abaixo.',
            montar_mensagem_suporte_idoso_etapa6(50),
        ]
        for texto_enviado in textos:
            for atual, idade, encerra in ((70, 65, True), (70, 75, True), (None, 95, True), (50, 55, True)):
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
                contar = stack.enter_context(patch.object(services.repositorio_encerramentos, 'contar_encerramentos_por_motivo', return_value=[{'motivo_encerramento':'idade_universal_90','status_dependente':False,'conversas':3}]))
                payload = services.carregar_relatorio(SimpleNamespace(id_unidade=10), periodo)
                self.assertEqual(contar.call_args.args[:3], (10, periodo.inicio, periodo.fim))
                self.assertEqual(payload['encerramentos_por_idade']['total_encaminhadas'], 3)
                self.assertIsNone(payload['unidade']['idade_minima_suporte'])
                contar.side_effect = RuntimeError('banco indisponível')
                with self.assertRaises(RuntimeError):
                    services.carregar_relatorio(SimpleNamespace(id_unidade=10), periodo)

    def test_card_nao_inventa_zero_e_tags_permanecem_fixas(self):
        for invalido in (None, True, -1, '1'):
            with self.assertRaises(ValueError):
                montar_tabela_encerramentos([{'conversas': invalido}], idade_minima_suporte=60, bpa_ativo=False)
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
