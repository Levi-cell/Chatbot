"""Contratos de mensagens e decisões na oferta da experiência Supera."""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from core.integrations.whatsapp.messages import etapa6_messages, etapa7_messages
from core.integrations.whatsapp.messages import etapa9_messages, etapa18_messages
from core.integrations.whatsapp.pywa_functions import cliente
from core.integrations.whatsapp.pywa_functions.pywa_senders import etapa7, etapa18
from core.repositories.atendimento.followup import buscar_contexto_repeticao
from tests.unit.test_followup import contexto as contexto_followup
from workers.worker_flow.response_flow import repeticao_followup
from workers.worker_flow.response_flow.etapas import resolver_etapa2, resolver_etapa7
from workers.worker_flow.response_flow.flow_sender import flow_sender
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa2 import validar_etapa2
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa7 import validar_etapa7
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa9 import validar_etapa9
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa18 import validar_etapa18
from workers.worker_flow.response_flow.etapas.validadores_contexto.validador_financeiro_etapa4 import (
    validar_pergunta_financeira_etapa4,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_financeiro import (
    validar_pergunta_financeira,
)


def contexto_resposta(etapa, texto, transicoes, *, dependente=False):
    return {
        'id_conversa': 1, 'id_etapa_atual': etapa, 'id_etapa_cliente': etapa,
        'id_etapa_origem_transicao': etapa, 'transicoes_permitidas': transicoes,
        'texto_cliente_atual': texto, 'tipo_mensagem_atual': 'text',
        'status_dependente': dependente, 'nome_cliente': 'Maria',
        'nome_dependente': 'Lucas', 'retry_count': 0,
        'resposta_bot_para_mensagem_atual': None,
        'mensagem_cliente_atual': {
            'cliente_telefone': '5511999999999', 'id_phone_unidade': 'phone',
            'id_mensagem_fila': 10, 'id_hash_msg': 'wamid.entrada',
        },
    }


class DestinoAtendimentoTests(unittest.TestCase):
    def test_negativa_sem_destino_alternativo_repete_pergunta(self):
        for texto in (
            'Não é para mim', 'não é para meu filho', 'Não para minha mãe',
            'não é para a minha filha', 'não é para um dependente',
            'não é para outra pessoa', 'não',
        ):
            with self.subTest(texto=texto):
                self.assertIsNone(validar_etapa2(texto))

    def test_destino_explicito_e_correcao_com_virgula_continuam_validos(self):
        casos = {
            'Para mim': 'para_mim', 'Para um dependente': 'para_outra_pessoa',
            'Não, é para mim': 'para_mim', 'não, para minha filha': 'para_outra_pessoa',
            'Não é para mim, é para meu filho': 'para_outra_pessoa',
            'É para minha mãe': 'para_outra_pessoa', 'meu neto': 'para_outra_pessoa',
        }
        for texto, esperado in casos.items():
            with self.subTest(texto=texto):
                self.assertEqual(validar_etapa2(texto), esperado)

    def test_negativa_nao_gera_evento_nem_escolha_de_destino(self):
        ctx = contexto_resposta(2, 'Não é para mim', {'destino_atendimento_definido': 3})
        with patch.object(resolver_etapa2, 'enviar_etapa2_contexto_opcao_invalida',
                          return_value={'id_etapa_resultante': 2, 'tratamento': True}), \
                patch.object(resolver_etapa2, 'enviar_etapa3') as confirmar:
            envio = resolver_etapa2.resolve_etapa2(ctx)
        confirmar.assert_not_called()
        self.assertTrue(envio['tratamento'])
        self.assertNotIn('evento_transicao', envio)
        self.assertNotIn('status_dependente', envio)


class GratuidadeExperienciaTests(unittest.TestCase):
    def test_duvida_explicita_sobre_a_atividade_inclusive_na_profissao(self):
        for texto in ('A demonstração prática é gratuita?', 'A experiência Supera é gratuita',
                      'É gratuita a demonstração?', 'Demonstração gratuita?'):
            with self.subTest(texto=texto):
                self.assertTrue(validar_pergunta_financeira(texto))
                self.assertTrue(validar_pergunta_financeira_etapa4(texto))

    def test_pergunta_curta_exige_contexto_de_oferta(self):
        for texto in ('É gratuita?', 'Gratuita mesmo?', 'Quero reservar, é gratuita?'):
            with self.subTest(texto=texto):
                self.assertFalse(validar_pergunta_financeira(texto))
                self.assertTrue(validar_pergunta_financeira(texto, referencia_experiencia=True))
        for texto in ('A consulta médica é gratuita?', 'Quero reservar minha experiência Supera gratuita',
                      'Trabalho com distribuição gratuita de alimentos'):
            with self.subTest(texto=texto):
                self.assertFalse(validar_pergunta_financeira(texto, referencia_experiencia=True))
                self.assertFalse(validar_pergunta_financeira_etapa4(texto))

    def test_duvida_na_oferta_recebe_esclarecimento_sem_avancar(self):
        wa = MagicMock()
        wa.send_message.return_value = SimpleNamespace(id='wamid.financeiro')
        for dependente in (False, True):
            ctx = contexto_resposta(7, 'Quero reservar, é gratuita?',
                                    {'oferta_aceita': 10}, dependente=dependente)
            with self.subTest(dependente=dependente), patch.object(cliente, 'WhatsApp', return_value=wa):
                envio = resolver_etapa7.resolve_etapa7(ctx)
            self.assertEqual(envio['id_etapa_resultante'], 7)
            self.assertEqual(envio['tipo_tratamento'], 'pergunta_financeira')
            self.assertNotIn('evento_transicao', envio)
            self.assertIn('*experiência Supera gratuita*', envio['mensagem_bot'])
            self.assertIn('valores de investimento', envio['mensagem_bot'])


class MensagensReservaTests(unittest.TestCase):
    def test_dependente_continua_sendo_quem_participa(self):
        oferta = etapa7_messages.montar_mensagem_oferta_dependente_etapa7('Lucas')
        self.assertIn('convidar Lucas', oferta)
        self.assertIn('*experiência Supera gratuita* de Lucas?', oferta)
        self.assertIn('Lucas também participará', oferta)
        self.assertNotIn('Você também participará', oferta)
        financeiro = etapa6_messages.montar_mensagem_idade_dependente_etapa6_financeiro('Lucas')
        self.assertIn('*experiência Supera gratuita*', financeiro)
        self.assertIn('qual é a idade de Lucas?', financeiro)
        retorno = etapa9_messages.montar_mensagem_retorno_dependente_etapa9('Maria', 'Lucas')
        self.assertIn('sua reserva para a *experiência Supera gratuita* de Lucas', retorno)

    def test_texto_enviado_e_historico_permanecem_identicos(self):
        for modulo, enviar, extra in (
            (etapa7, etapa7.enviar_etapa7_cliente, 'Maria'),
            (etapa18, etapa18.enviar_etapa18, 'https://example.com/horarios'),
        ):
            with self.subTest(modulo=modulo.__name__):
                wa = MagicMock()
                wa.send_message.return_value = SimpleNamespace(id='wamid.novo')
                with patch.object(modulo, 'conta_wa', return_value=wa):
                    envio = enviar('5511999999999', 'phone', extra)
                self.assertEqual(wa.send_message.call_args.kwargs['text'], envio['mensagem_bot'])
                self.assertIn('experiência Supera gratuita', envio['mensagem_bot'])
                self.assertNotRegex(envio['mensagem_bot'].lower(), r'cortesia|agendamento|aula\s+\*?gratuita')

    def test_followup_mantem_etapa_e_envia_uma_unica_saudacao(self):
        for numero in (7, 9, 18):
            for dependente in (False, True):
                with self.subTest(etapa=numero, dependente=dependente):
                    ctx = contexto_followup()
                    ctx['id_etapa_atual'] = numero
                    ctx['dados_repeticao'].update(status_dependente=dependente, nome_cliente='Maria', nome_dependente='Lucas')
                    wa = MagicMock()
                    wa.send_message.return_value = SimpleNamespace(id='wamid.followup')
                    with patch.object(cliente, 'WhatsApp', return_value=wa):
                        envio = repeticao_followup.enviar_repeticao_followup(ctx)
                    self.assertEqual(envio['id_etapa_resultante'], numero)
                    self.assertEqual(wa.send_message.call_count, 1)
                    self.assertEqual(wa.send_message.call_args.kwargs['text'], envio['mensagem_bot'])
                    self.assertEqual(envio['mensagem_bot'].count('novamente'), 1)
                    self.assertIn('experiência Supera gratuita', envio['mensagem_bot'])
                    self.assertNotIn('evento_transicao', envio)

    def test_retorno_da_espera_preserva_uma_saudacao_com_ou_sem_inatividade(self):
        for dependente in (False, True):
            for saudacao in (None, 'Olá novamente, Maria!\n\n'):
                with self.subTest(dependente=dependente, saudacao=saudacao):
                    ctx = contexto_resposta(8, 'Olá', {'cliente_retornou': 9}, dependente=dependente)
                    ctx['saudacao_retorno'] = saudacao
                    wa = MagicMock()
                    wa.send_message.return_value = SimpleNamespace(id='wamid.retorno')
                    with patch.object(cliente, 'WhatsApp', return_value=wa):
                        envio = flow_sender(ctx)
                    self.assertEqual(envio['id_etapa_resultante'], 9)
                    self.assertEqual(envio['mensagem_bot'].count('novamente'), 1)
                    self.assertEqual(wa.send_message.call_args.kwargs['text'], envio['mensagem_bot'])

    def test_resposta_persistida_nao_envia_novamente(self):
        ctx = contexto_followup()
        ctx['resposta_bot_para_mensagem_atual'] = {'id_hash_msg': 'wamid.antigo'}
        with patch.object(repeticao_followup, '_selecionar_sender') as selecionar:
            envio = repeticao_followup.enviar_repeticao_followup(ctx)
        selecionar.assert_not_called()
        self.assertFalse(envio['enviou'])
        self.assertEqual(envio['id_hash_msg_bot'], 'wamid.antigo')

    def test_contexto_repeticao_preserva_barreira_terminal_sem_responsavel(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = (
            'Titular', 'Aluno', 12, 'Unidade', 'Bot', 'masculino',
            'https://example.com', None, True, False,
        )
        dados = buscar_contexto_repeticao(8, 2, cursor)
        self.assertTrue(dados['status_dependente'])
        self.assertEqual(cursor.execute.call_args.args[1], (8, 2))
        cursor.fetchone.return_value = (*cursor.fetchone.return_value[:-1], True)
        with self.assertRaises(ValueError):
            buscar_contexto_repeticao(8, 2, cursor)


class AceiteReservaTests(unittest.TestCase):
    def test_botao_novo_e_textos_legados_preservam_o_aceite_flexivel(self):
        for validar, esperado in ((validar_etapa7, 'oferta_aceita'), (validar_etapa9, 'retorno_confirmado')):
            for texto in ('Quero reservar', 'quero', 'Quero agendar', 'Pode reservar', 'sim',
                          'Quero reservar!', 'Quero pensar melhor', 'Gostaria de desistir'):
                with self.subTest(validador=validar.__name__, texto=texto):
                    self.assertEqual(validar(texto), esperado)
            for texto in ('não quero reservar', 'como reservar?', 'quero saber como reservar', 'quero mais informações'):
                with self.subTest(validador=validar.__name__, texto=texto):
                    self.assertIsNone(validar(texto))
        self.assertEqual(validar_etapa7('Talvez mais tarde'), 'oferta_adiada')
        self.assertEqual(validar_etapa9('Talvez mais tarde'), 'retorno_adiado')

    def test_etapa18_so_avanca_com_conclusao(self):
        for texto in (*etapa18_messages.montar_botoes_etapa18(), 'já reservei!', 'Já agendei', 'agendamento feito'):
            self.assertEqual(validar_etapa18(texto), 'agendamento_confirmado')
        for texto in ('Quero reservar', 'Quero agendar', 'não reservei', 'vou reservar', 'sim'):
            self.assertIsNone(validar_etapa18(texto))
