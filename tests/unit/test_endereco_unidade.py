"""Regressões de localização, retomada e composição sem enviar à Meta."""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from core.database.deploy_database.etapa_transicao_script import TRANSICOES_INICIAIS

from core.integrations.whatsapp.pywa_functions import cliente
from core.integrations.whatsapp.messages.tratamentos.composicao import aplicar_prefixo_retorno
from core.integrations.whatsapp.messages.tratamentos.endereco import montar_mensagem_tratamento_endereco
from core.validacoes.endereco import validar_pedido_endereco
from tests.unit.test_followup import contexto, dados
from workers.worker_flow.response_flow.flow_sender import flow_sender
from workers.worker_flow.response_flow.retomada_followup import enviar_retorno_followup
from workers.worker_flow.response_flow.tratamentos_informativos import classificar_tratamento_informativo
from workers.worker_flow.transacoes.retorno_followup import _validar_retorno_etapa8


ENDERECO = 'Rua Dr. Eduardo Monteiro, 188 - Jardim Bela Vista, Santo André - SP, CEP 09041-300'
SAUDACAO = 'Bom te ver novamente ☺️\n\n'
HORARIOS = 'segunda a sexta das 9h às 19h, exceto quarta-feira até as 21h, e sábado das 8h30 às 13h30'


def atendimento(etapa, texto='Aonde fica', dependente=False):
    cx = contexto()
    cx.update(
        id_etapa_atual=etapa, id_etapa_origem_transicao=etapa, retry_count=1,
        texto_cliente_atual=texto, tipo_mensagem_atual='text',
        status_dependente=dependente, endereco_unidade=ENDERECO,
        horarios_funcionamento=HORARIOS,
        nome_unidade='Supera Santo André', nome_agente='Dora', genero='feminino',
        saudacao_retorno=None,
        nome_titular='Ana', nome_dependente='Bia' if dependente else None,
        transicoes_permitidas={evento: destino for origem, evento, destino in TRANSICOES_INICIAIS if origem == etapa},
    )
    cx['dados_repeticao'] = dict(dados(), status_dependente=dependente)
    return cx


class IdentificacaoTests(unittest.TestCase):
    def test_palavra_endereco_ativa_sem_exigir_pergunta_ou_intencao(self):
        for texto in (
            'Endereço', 'ENDERECO', 'Me diz o endereço de vocês',
            'Meu endereço é Rua A, 12', 'Quero informar meu endereço',
            'Preciso atualizar meu endereço', 'Já tenho o endereço',
            'Não quero o endereço', 'Não me mande o endereço',
            'Não me diz o endereço', 'Não me diga o endereço de vocês',
            'Não sei qual o endereço da minha filha',
            'Me passa o endereço do site', 'Qual o endereço IP?',
            'Me diz o endereço do site', 'Esqueci o endereço de vocês',
        ):
            with self.subTest(texto=texto):
                self.assertTrue(validar_pedido_endereco(texto))

    def test_endereco_de_email_e_excecao_por_ocorrencia(self):
        for pedido in (
            'Qual seu endereço de email?', 'Me diz o endereço de e-mail de vocês',
            'ENDEREÇO ELETRÔNICO', 'Endereço do email', 'Endereço e-mail',
            'Endereço de e mail', 'Endereço de\nemail', 'Endereço: email',
            'Meu endereço de e-mail é ana@example.com',
        ):
            with self.subTest(pedido=pedido):
                self.assertFalse(validar_pedido_endereco(pedido))
                self.assertTrue(validar_pedido_endereco(pedido + '. E qual o endereço da unidade?'))
                self.assertTrue(validar_pedido_endereco(pedido + '. E qual a rua de vocês?'))
                self.assertTrue(validar_pedido_endereco('Me diz o endereço da unidade. ' + pedido))

    def test_pedidos_com_artigos_preposicoes_e_ligacoes_opcionais(self):
        for pedido in (
            'Me diz bairro', 'Me diz o bairro', 'Me diz qual é o bairro',
            'Me diz que bairro', 'Me diz q bairro', 'Me diz em qual bairro',
            'Qual bairro', 'Qual o bairro', 'Qual é o bairro', 'Qual q é o bairro',
            'Qual que é o bairro', 'Qual é que é o bairro',
            'Qual o bairro que vocês ficam', 'Qual o bairro em que fica a unidade',
            'Me diz local', 'Me diz o local', 'Qual local', 'Qual é o local',
            'Onde é o local', 'Aonde q é o local', 'Me diz onde é o local',
            'Me diz rua', 'Me diz a rua', 'Qual rua', 'Qual q é a rua',
            'Onde é a rua', 'Aonde q é a rua', 'Qual a rua que fica a unidade',
            'Onde fica', 'Onde é que fica', 'Aonde q fica', 'Aonde é q fica',
            'Me diz onde q fica', 'Me diz onde é q fica',
            'Onde', 'Aonde', 'Me diz onde', 'Aonde por favor',
        ):
            for sufixo in ('', '?'):
                with self.subTest(pedido=pedido, sufixo=sufixo):
                    self.assertTrue(validar_pedido_endereco(pedido + sufixo))

    def test_abreviacoes_inversoes_e_perguntas_dentro_da_mensagem(self):
        exemplos = (
            'Onde fica a unidade', 'Aonde é', 'Aonde q fica', 'aonde q fca',
            'FIca aonde', 'Fica onde', 'Onde vcs ficam', 'Vcs ficam aonde',
            'Aonde que fica', 'Onde é que vocês ficam', 'Onde q vcs fcam',
            'A unidade fica aonde', 'Onde a unidade fica', 'Aonde q é',
            'Aonde eh', 'ond fica', 'aond q fca', 'Onde fica localizada a unidade',
            'Em qual bairro vocês ficam', 'Em que rua fica a unidade',
            'Qual bairro fica a unidade', 'Em q cidade vcs ficam',
            'Onde vocês estão', 'Onde vcs estão localizados',
            'Onde vocês se localizam', 'Vocês se localizam onde',
            'Onde vocês atendem', 'Qual é a localização da unidade',
            'Qual o local da unidade', 'Qual o ponto de referência',
            'Me manda o endereço por favor', 'Me envia sua localização pfv',
            'Pode me informar o endereço', 'Quero saber o CEP da unidade',
            'Me diz o endereço de vocês', 'me diz o endereco de vcs',
            'Diz o endereço', 'Me diga o endereço de vocês',
            'Pode me dizer o endereço de vocês', 'Me diz a localização da unidade',
            'Como eu chego aí', 'Como faço pra chegar', 'Como q eu chego na unidade',
            'Gostaria de saber onde fica a unidade para levar minha filha',
            'Tenho interesse, mas antes queria saber aonde q fca',
            'Boa tarde, sou professora e queria saber onde fica',
            'Não sei onde fica', 'Ainda não tenho o endereço, me passa a localização',
            'Oi, endereço por favor', 'Boa noite! Localização',
            'Onde\nfica a unidade', 'Onde\tvcs\tficam',
            'A unidade é aonde', 'Vocês ficam em qual endereço',
            'Queria o endereço', 'Preciso do endereço', 'Gostaria de uma localização',
            'Pode mandar a localização por gentileza', 'Como chegar até aí',
            'Como chegar de ônibus', 'Me passa o endereço pelo WhatsApp',
            'aonde q fca 😊', 'Boa tarde! *Onde fica a unidade?*',
        )
        for texto in exemplos:
            for sufixo in ('', '?', '??'):
                with self.subTest(texto=texto, sufixo=sufixo):
                    self.assertTrue(validar_pedido_endereco(texto + sufixo))

    def test_outros_assuntos_sem_palavra_endereco_nao_ativam(self):
        for texto in (
            'Onde fica o botão da pesquisa?', 'Aonde é a pesquisa de satisfação?',
            'Onde fica meu cadastro?', 'Onde está meu formulário?',
            'Onde fica a unidade no aplicativo?', 'Fica onde meu e-mail?',
            'Minha casa fica onde?', 'Minha filha fica onde?',
            'Onde fica minha casa?', 'Onde fica o banco?', 'Aonde é o teste?',
            'Como chegar aos 60 anos saudável?', 'Como chegar na próxima etapa?',
            'Como chegar ao resultado da pesquisa?',
            'Qual seu endereço de e-mail?', 'Qual seu endereço eletrônico?',
            'Onde encontro o link?', 'Onde respondo a pesquisa?',
            'Qual é o local do botão?', 'Onde é o local do teste?',
            'Me diz qual o bairro da minha filha', 'Qual a rua da minha casa',
            'Qual bairro que fica o banco', 'Qual a rua que fica meu trabalho',
            'Qual local que é a pesquisa', 'Me diz a rua do hospital',
            'Bairro', 'Local', 'Rua', 'Moro na rua principal',
            'Endereçamento', 'Reendereçou', 'Sou localizado no centro',
            'Qual o local de trabalho do cliente?',
            'O resultado fica onde?', 'O link fica onde?', 'O teste é onde?',
            'Já sei onde fica', 'Eu sei onde fica a unidade',
            'Já conheço a localização da unidade', 'Não preciso saber onde fica',
            'Não me diz o bairro', 'Não me diga a localização de vocês',
            'Me diz o endereço de e-mail de vocês',
            'Me diz onde fica minha casa',
            'Eu trabalho onde fica a unidade', 'Moro onde fica o Supera',
            'Não sei onde fica minha casa',
            'fica', 'fca', 'q', 'Me diga onde errei',
            'Sou professora', 'Meu bairro é Centro', 'Santo André',
            'Tenho interesse em ir até a unidade', 'Tem uma faca na unidade',
            123, [], {},
        ):
            with self.subTest(texto=texto):
                self.assertFalse(validar_pedido_endereco(texto))

    def test_pergunta_fisica_nao_e_ocultada_por_outra_informacao(self):
        for texto in (
            'Meu endereço é Rua A, 12. Aonde q fca a unidade?',
            'Minha casa fica no centro, onde fica a unidade?',
            'Qual seu endereço de e-mail? E onde fica a unidade?',
            'Me passa o endereço do site e onde fica a unidade',
            'Não preciso do email, mas me passa o endereço da unidade',
            'Já sei onde fica o banco. Aonde é a unidade?',
            'Já sei onde fica a unidade, mas qual é o CEP?',
            'Full name: Maria\nEmail: maria@example.com\nAonde q fca?',
        ):
            with self.subTest(texto=texto):
                self.assertTrue(validar_pedido_endereco(texto))

    def test_pedidos_de_localizacao(self):
        for texto in ('Aonde fica', 'Onde vocês ficam?', 'qual o endereço?',
                      'Me passa a localização', 'como chegar aí?', 'Endereço?',
                      'Qual é o CEP?', 'Onde fica a unidade de Santo André?',
                      'Onde vcs ficam?', 'Qual é o endereço de vocês?'):
            with self.subTest(texto=texto):
                self.assertTrue(validar_pedido_endereco(texto))

    def test_dados_informados_nao_sao_pedidos(self):
        for texto in (None, '', 'Sou professora',
                      'Endereço de e-mail: ana@example.com', 'ana@example.com',
                      'Qual seu endereço de email?', 'Meu bairro: Centro',
                      'Moro no centro', 'Tenho 18 anos'):
            with self.subTest(texto=texto):
                self.assertFalse(validar_pedido_endereco(texto))

    def test_prioridades_e_escopo_das_etapas(self):
        self.assertIsNone(classificar_tratamento_informativo(dict(atendimento(9), tipo_mensagem_atual='image')))
        for etapa in (23, 24):
            self.assertIsNone(classificar_tratamento_informativo(atendimento(etapa)))
        self.assertEqual(classificar_tratamento_informativo(atendimento(8, 'Quanto custa e onde fica?')), 'pergunta_financeira')
        self.assertIsNone(classificar_tratamento_informativo(atendimento(9, 'Quanto custa e onde fica?')))
        # Na etapa de profissão, professor de inglês continua sendo profissão.
        self.assertIsNone(classificar_tratamento_informativo(atendimento(4, 'Professor de inglês')))


class EnvioTests(unittest.TestCase):
    def enviar(self, cx, retorno=False):
        fake = MagicMock()
        fake.send_message.return_value = SimpleNamespace(id='wamid.bot')
        with patch.object(cliente, 'WhatsApp', return_value=fake):
            envio = (enviar_retorno_followup if retorno else flow_sender)(cx)
        fake.send_message.assert_called_once()
        chamada = fake.send_message.call_args.kwargs
        self.assertEqual(envio['mensagem_bot'], chamada['text'])
        self.assertNotIn('para continuarmos', envio['mensagem_bot'].casefold())
        self.assertNotIn('\n\n\n', envio['mensagem_bot'])
        self.assertEqual(envio['mensagem_bot'].count(ENDERECO), 1 if cx.get('endereco_unidade') else 0)
        if envio.get('tipo_tratamento') == 'pedido_endereco':
            horario = cx.get('horarios_funcionamento')
            self.assertEqual('Nosso horário de funcionamento é de ' in envio['mensagem_bot'], bool(horario and horario.strip()))
            if horario and horario.strip():
                self.assertEqual(envio['mensagem_bot'].count(horario.strip()), 1)
        return envio, chamada

    def test_endereco_em_todas_etapas_preserva_etapa_exceto_retorno_da8(self):
        for dependente in (False, True):
            for etapa in range(1, 23):
                with self.subTest(etapa=etapa, dependente=dependente):
                    envio, _ = self.enviar(atendimento(etapa, dependente=dependente))
                    self.assertEqual(envio['id_etapa_resultante'], 9 if etapa == 8 else etapa)
                    self.assertEqual(envio['tipo_tratamento'], 'pedido_endereco')
                    self.assertEqual(bool(envio.get('tratamento')), etapa != 8)
                    if etapa == 8:
                        self.assertEqual(envio['evento_transicao'], 'cliente_retornou')
                    else:
                        self.assertNotIn('evento_transicao', envio)
                    self.assertNotIn('não consegui entender', envio['mensagem_bot'])

    def test_maria_na_etapa9_recebe_endereco_e_botoes_da_reserva(self):
        envio, chamada = self.enviar(atendimento(9))
        self.assertIn('reserva', envio['mensagem_bot'])
        self.assertIn('buttons', chamada)
        self.assertEqual(envio['id_etapa_resultante'], 9)

    def test_me_diz_o_endereco_na_coleta_do_nome_do_dependente(self):
        for retorno in ('sem', 'inatividade', 'followup'):
            with self.subTest(retorno=retorno):
                cx = atendimento(5, 'Me diz o endereço de vocês', dependente=True)
                cx['nome_dependente'] = None
                cx['dados_repeticao']['nome_dependente'] = None
                if retorno == 'inatividade':
                    cx['saudacao_retorno'] = SAUDACAO
                envio, _ = self.enviar(cx, retorno=retorno == 'followup')
                texto = envio['mensagem_bot']
                self.assertEqual(envio['tipo_tratamento'], 'pedido_endereco')
                self.assertEqual(envio['id_etapa_resultante'], 5)
                self.assertNotIn('evento_transicao', envio)
                self.assertNotIn('nome_dependente', envio)
                self.assertIsNone(cx['nome_dependente'])
                self.assertNotIn('não consegui entender', texto)
                self.assertNotIn('Pedro', texto)
                self.assertTrue(texto.endswith('\n\nMe diz, qual o nome da pessoa?'))
                self.assertEqual(texto.count('Bom te ver novamente'), int(retorno != 'sem'))

    def test_pedidos_abreviados_seguem_o_mesmo_tratamento_no_fluxo_e_retorno(self):
        for texto in ('Aonde é', 'aonde q fca', 'FIca aonde',
                      'Boa tarde, onde vcs ficam?', 'Me diz o endereço de vocês',
                      'Já tenho o endereço', 'Qual q é o bairro',
                      'Me diz a rua', 'Onde é o local', 'Aonde'):
            for etapa, retorno in ((None, False), (9, False), (8, True), (19, True)):
                with self.subTest(texto=texto, etapa=etapa, retorno=retorno):
                    envio, _ = self.enviar(atendimento(etapa, texto), retorno=retorno)
                    self.assertEqual(envio['tipo_tratamento'], 'pedido_endereco')
                    self.assertEqual(envio['id_etapa_resultante'], 1 if etapa is None else 9 if etapa == 8 else etapa)

    def test_abertura_apresenta_agente_endereco_e_pede_nome(self):
        envio, _ = self.enviar(atendimento(None))
        self.assertIn('Dora', envio['mensagem_bot'])
        self.assertIn('nome', envio['mensagem_bot'])
        self.assertEqual(envio['id_etapa_resultante'], 1)

    def test_abertura_parcial_e_completa_preserva_campos_ja_coletados(self):
        from tests.unit.test_coleta_abertura import estado, FORM
        from core.integrations.whatsapp.messages.etapa2_messages import MENSAGEM_REPETICAO_ETAPA2
        from core.integrations.whatsapp.messages.etapa4_messages import MENSAGEM_REPETICAO_ETAPA4
        from core.integrations.whatsapp.messages.componentes_compartilhados import RODAPE_OPCAO_UNICA
        perguntas = {1: 'Me diz, qual o seu nome?', 2: MENSAGEM_REPETICAO_ETAPA2, 4: MENSAGEM_REPETICAO_ETAPA4}
        for formulario, etapa in (('Email: ana@example.com', 1), ('Full name: Ana', 2), (FORM, 4)):
            for identificado in (False, True):
                for horario in (None, HORARIOS):
                    with self.subTest(etapa=etapa, identificado=identificado, horario=horario):
                        cx = atendimento(None, formulario + '\nMe diz o endereço de vocês')
                        cx['horarios_funcionamento'] = horario
                        cx['contexto_coleta'] = estado(formulario)
                        cx['contexto_coleta']['formulario_identificado'] = identificado
                        envio, payload = self.enviar(cx)
                        texto = envio['mensagem_bot']
                        self.assertEqual(envio['id_etapa_resultante'], etapa)
                        self.assertEqual('formulários' in texto, identificado)
                        self.assertLess(texto.index('assistente do'), texto.index(ENDERECO))
                        final = perguntas[etapa]
                        if etapa == 2:
                            final += '\n\n_' + RODAPE_OPCAO_UNICA + '_'
                            self.assertEqual([botao.title for botao in payload['buttons']], ['Para mim', 'Para um dependente'])
                        self.assertTrue(texto.endswith('\n\n' + final))
                        if identificado:
                            self.assertLess(texto.index(ENDERECO), texto.index('Vi que você'))
                            if horario:
                                self.assertLess(texto.index(HORARIOS), texto.index('Vi que você'))
                        if etapa != 1:
                            self.assertNotIn('qual o seu nome', texto)

    def test_abertura_fireads_legada_tambem_responde_endereco(self):
        cx = atendimento(None)
        cx['contexto_fireads'] = {
            'concluida': True, 'resultado': 'importado', 'id_conversa': 1,
            'dados_titular': {'nome': 'Ana', 'email': 'ana@example.com', 'resultado_email': 'email_valido'},
        }
        envio, _ = self.enviar(cx)
        self.assertEqual(envio['id_etapa_resultante'], 4)
        self.assertIn('profissão', envio['mensagem_bot'])
        self.assertLess(envio['mensagem_bot'].index(HORARIOS), envio['mensagem_bot'].index('Vi que você'))

    def test_sem_endereco_cadastrado_nao_inventa_ou_usa_outra_unidade(self):
        cx = atendimento(9)
        cx['endereco_unidade'] = None
        envio, _ = self.enviar(cx)
        self.assertIn('Ainda não tenho o endereço', envio['mensagem_bot'])
        self.assertNotIn('Rua', envio['mensagem_bot'])

    def test_retorno_etapa8_responde_duvida_e_abre9_com_botoes(self):
        for texto, tipo in (
            ('Aonde fica', 'pedido_endereco'),
            ('Quanto custa?', 'pergunta_financeira'),
            ('Vocês oferecem reforço escolar?', 'duvida_reforco_escolar'),
        ):
            for dependente in (False, True):
                for retorno in ('sem', 'inatividade', 'followup'):
                    with self.subTest(tipo=tipo, dependente=dependente, retorno=retorno):
                        cx = atendimento(8, texto, dependente)
                        if tipo != 'pedido_endereco':
                            cx['endereco_unidade'] = None
                        if retorno == 'inatividade':
                            cx['saudacao_retorno'] = SAUDACAO
                        envio, payload = self.enviar(cx, retorno=retorno == 'followup')
                        self.assertEqual(envio['id_etapa_resultante'], 9)
                        self.assertEqual(envio['id_etapa_origem_transicao'], 8)
                        self.assertEqual(envio['evento_transicao'], 'cliente_retornou')
                        self.assertEqual(envio['tipo_tratamento'], tipo)
                        self.assertFalse(envio.get('tratamento'))
                        mensagem = envio['mensagem_bot']
                        self.assertEqual(mensagem.startswith(SAUDACAO), retorno != 'sem')
                        self.assertIn('\n\nVamos dar prosseguimento à reserva', mensagem)
                        self.assertEqual('de Bia' in mensagem, dependente)
                        for trecho in ('Instagram', 'Um abraço', 'Podemos continuar no seu ritmo',
                                       'Que bom ver você aqui novamente', 'Vamos lá', '\n\n\n'):
                            self.assertNotIn(trecho, mensagem)
                        self.assertEqual([botao.title for botao in payload['buttons']],
                                         ['Reservar agora', 'Talvez mais tarde'])
                        _validar_retorno_etapa8(envio)

    def test_duvida_na8_exige_transicao_autorizada_antes_do_envio(self):
        for mapa in ({}, {'cliente_retornou': 10}):
            cx = atendimento(8)
            cx['transicoes_permitidas'] = mapa
            with patch.object(cliente, 'WhatsApp') as transporte:
                with self.assertRaises(ValueError):
                    flow_sender(cx)
            transporte.assert_not_called()

    def test_replay_da8_recupera_tanto_resposta_antiga_na8_quanto_nova_na9(self):
        for destino in (8, 9):
            cx = atendimento(8)
            cx['resposta_bot_para_mensagem_atual'] = {'id_etapa': destino, 'id_hash_msg': 'wamid.bot'}
            with patch.object(cliente, 'WhatsApp') as transporte:
                envio = flow_sender(cx)
            transporte.assert_not_called()
            self.assertEqual(envio['id_etapa_resultante'], destino)
            self.assertEqual(envio.get('evento_transicao'), 'cliente_retornou' if destino == 9 else None)

    def test_etapa19_preserva_contato_comercial_apos_duvida(self):
        for texto in ('Aonde fica', 'Qual o valor?', 'É reforço escolar?'):
            cx = atendimento(19, texto)
            if texto != 'Aonde fica':
                cx['endereco_unidade'] = None
            envio, chamada = self.enviar(cx)
            self.assertEqual(envio['id_etapa_resultante'], 19)
            self.assertIn('button', str(chamada).lower())
            self.assertNotIn('grau de satisfação', envio['mensagem_bot'])

    def test_retry_com_resposta_salva_nao_envia_novamente(self):
        cx = atendimento(9)
        cx['resposta_bot_para_mensagem_atual'] = {'id_etapa': 9, 'id_hash_msg': 'wamid.bot'}
        with patch.object(cliente, 'WhatsApp') as meta:
            envio = flow_sender(cx)
        meta.assert_not_called()
        self.assertTrue(envio['resposta_ja_existia'])

    def test_cabecalho_saudacao_endereco_horarios_e_pergunta_na_ordem(self):
        from core.integrations.whatsapp.messages.etapa11_messages import montar_mensagem_triagem_cognitiva_etapa11
        for retorno in (False, True):
            for horario in (None, '', '  \n ', HORARIOS):
                with self.subTest(retorno=retorno, horario=horario):
                    cx = atendimento(11)
                    cx['horarios_funcionamento'] = horario
                    cx['saudacao_retorno'] = SAUDACAO if retorno else None
                    envio, chamada = self.enviar(cx)
                    texto = envio['mensagem_bot']
                    prefixo = '*Triagem cognitiva*\n\n' + (SAUDACAO if retorno else '')
                    self.assertTrue(texto.startswith(prefixo + 'Nossa unidade fica localizada em '))
                    pergunta = montar_mensagem_triagem_cognitiva_etapa11(repeticao=True)
                    self.assertIn('\n\n' + pergunta, texto)
                    if horario and horario.strip():
                        self.assertLess(texto.index(ENDERECO), texto.index(HORARIOS))
                        self.assertLess(texto.index(HORARIOS), texto.index(pergunta))
                    self.assertNotIn('Ana', texto)
                    self.assertIn('buttons', chamada)

    def test_tratamentos_triagem_e_nota_preservam_pergunta_opcoes_e_estado(self):
        from core.triagem.perguntas import montar_pergunta_triagem
        from core.integrations.whatsapp.messages.etapa21_messages import MENSAGEM_REPETICAO_ETAPA21
        tratamentos = (
            ('Aonde q fca?', 'pedido_endereco', 'Nossa unidade fica localizada'),
            ('Quanto custa?', 'pergunta_financeira', 'Olha, demais informações'),
            ('É reforço escolar?', 'duvida_reforco_escolar', 'Olha, o Supera não é reforço escolar'),
        )
        for etapa in (*range(12, 18), 21):
            for dependente, idade in ((False, 35), (True, 12), (True, 35)):
                for retorno in ('sem', 'inatividade', 'followup'):
                    for pergunta, tipo, inicio in tratamentos:
                        with self.subTest(etapa=etapa, dependente=dependente, idade=idade, retorno=retorno, tipo=tipo):
                            cx = atendimento(etapa, pergunta, dependente)
                            cx['dados_repeticao']['idade_dependente'] = idade
                            if tipo != 'pedido_endereco':
                                cx['endereco_unidade'] = None
                            if retorno == 'inatividade':
                                cx['saudacao_retorno'] = SAUDACAO
                            envio, payload = self.enviar(cx, retorno=retorno == 'followup')
                            texto = envio['mensagem_bot']
                            titulo = f'*Pergunta {etapa - 11}*' if etapa != 21 else '*Pesquisa de satisfação*'
                            saudacao = SAUDACAO if retorno != 'sem' else ''
                            self.assertTrue(texto.startswith(titulo + '\n\n' + saudacao + inicio))
                            self.assertEqual(texto.count(titulo), 1)
                            self.assertEqual(texto.count('Bom te ver novamente'), int(retorno != 'sem'))
                            self.assertNotIn('Vamos lá', texto)
                            self.assertNotIn('\n\n\n', texto)
                            self.assertEqual(envio['tipo_tratamento'], tipo)
                            self.assertEqual(envio['id_etapa_resultante'], etapa)
                            for campo in ('evento_transicao', 'resposta_triagem', 'nota_satisfacao', 'comentario_satisfacao'):
                                self.assertNotIn(campo, envio)
                            if etapa == 21:
                                self.assertNotIn('Para continuarmos:', texto)
                                esperado = MENSAGEM_REPETICAO_ETAPA21
                                linhas = payload['buttons'].sections[0].rows
                                self.assertEqual([linha.callback_data for linha in linhas], [f'satisfacao_{n}' for n in (5, 4, 3, 2, 1)])
                            else:
                                esperado = montar_pergunta_triagem(
                                    etapa, faixa_etaria='infantil' if idade < 18 else 'adulta',
                                    nome_dependente='Bia' if dependente else None,
                                )
                                self.assertEqual([botao.title for botao in payload['buttons']], ['Nunca', 'Às vezes', 'Frequentemente'])
                            self.assertEqual(texto.count(esperado), 1)
                            self.assertIn('\n\n' + esperado, texto)

    def test_prioridades_na_triagem_e_nota_nao_consumem_resposta_mista(self):
        for etapa in (12, 17, 21):
            for pergunta, tipo in (
                ('Quanto custa e onde fica?', 'pergunta_financeira'),
                ('É reforço escolar? Quanto custa e onde fica?', 'duvida_reforco_escolar'),
                ('Às vezes, mas aonde fica?', 'pedido_endereco'),
                ('5, mas quanto custa?', 'pergunta_financeira'),
            ):
                with self.subTest(etapa=etapa, pergunta=pergunta):
                    cx = atendimento(etapa, pergunta)
                    if tipo != 'pedido_endereco':
                        cx['endereco_unidade'] = None
                    envio, _ = self.enviar(cx)
                    self.assertEqual(envio['tipo_tratamento'], tipo)
                    self.assertEqual(envio['id_etapa_resultante'], etapa)
                    self.assertNotIn('resposta_triagem', envio)
                    self.assertNotIn('nota_satisfacao', envio)
            cx = atendimento(etapa)
            cx['tipo_mensagem_atual'] = 'image'
            self.assertIsNone(classificar_tratamento_informativo(cx))

    def test_replay_nas_novas_etapas_nao_repete_tratamento(self):
        for etapa in (*range(12, 18), 21):
            cx = atendimento(etapa)
            cx['resposta_bot_para_mensagem_atual'] = {'id_etapa': etapa, 'id_hash_msg': 'wamid.ja-salva'}
            with patch.object(cliente, 'WhatsApp') as meta:
                envio = flow_sender(cx)
            meta.assert_not_called()
            self.assertTrue(envio['resposta_ja_existia'])


class ComposicaoTests(unittest.TestCase):
    def test_aberturas_fireads_endereco_antes_do_formulario_com_cinco_paragrafos(self):
        from core.integrations.whatsapp.messages.abertura_coleta import montar_abertura
        from core.integrations.whatsapp.messages.etapa4_messages import montar_abertura_fireads
        from tests.unit.test_coleta_abertura import estado
        cx = atendimento(None)
        cx['contexto_coleta'] = estado('Full name: Edcarlos\nEmail: ed@example.com\nPara quem é: Para meu filho')
        cx['contexto_coleta']['formulario_identificado'] = True
        cx['contexto_fireads'] = {'dados_titular': {'nome': 'Edcarlos'}}
        esperado = '\n\n'.join((
            'Boa tarde, Edcarlos! Sou a Dora, assistente do Supera Santo André. ☺️',
            'Nossa unidade fica localizada em ' + ENDERECO + '.',
            'Nosso horário de funcionamento é de ' + HORARIOS + '.',
            'Vi que você já preencheu um dos nossos formulários. Para avançarmos com sua reserva '
            'por cortesia da unidade vamos precisar fazer mais algumas perguntinhas, ok?',
            'Me diz, qual a sua *profissão* hoje?',
        ))
        for montar in (montar_abertura, montar_abertura_fireads):
            with self.subTest(montar=montar.__name__):
                self.assertEqual(montar(cx, saudacao='Boa tarde', tratamento='pedido_endereco'), esperado)

    def test_separadores_exatos_entre_blocos_e_aplicacao_idempotente(self):
        from core.integrations.whatsapp.messages.tratamentos.composicao import compor_tratamento
        from core.integrations.whatsapp.messages.componentes_compartilhados import montar_texto_com_cabecalho
        from core.integrations.whatsapp.messages.tratamentos.financeiro import montar_mensagem_tratamento_financeiro
        from core.integrations.whatsapp.messages.tratamentos.reforco_escolar import montar_mensagem_tratamento_reforco_escolar
        for separador in ('', '\n', '\n\n', '\n\n\n', ' \n '):
            with self.subTest(separador=separador):
                tratamento = compor_tratamento('Orientação.' + separador, separador + 'Pergunta?')
                self.assertEqual(tratamento, 'Orientação.\n\nPergunta?')
                texto = montar_texto_com_cabecalho(separador + tratamento, 'Pesquisa de satisfação')
                saudacao = SAUDACAO.strip() + separador
                esperado = '*Pesquisa de satisfação*\n\n' + SAUDACAO + tratamento
                self.assertEqual(aplicar_prefixo_retorno(texto, saudacao), esperado)
                self.assertEqual(aplicar_prefixo_retorno(esperado, saudacao), esperado)
        for montar in (montar_mensagem_tratamento_financeiro, montar_mensagem_tratamento_reforco_escolar):
            self.assertNotIn('Vamos lá', montar('Pergunta?'))
            self.assertTrue(montar('Pergunta?').endswith('\n\nPergunta?'))

    def test_endereco_com_referencia_e_horario_opcional_sem_pontuacao_duplicada(self):
        endereco = ENDERECO + '. Ponto de referência: em frente à praça.'
        for horario in (None, '', ' \n ', HORARIOS, HORARIOS + '.'):
            with self.subTest(horario=horario):
                texto = montar_mensagem_tratamento_endereco('Qual o seu nome?', endereco, horario)
                self.assertTrue(texto.startswith('Nossa unidade fica localizada em ' + endereco + '\n\n'))
                self.assertNotIn('..', texto)
                self.assertEqual('Nosso horário' in texto, bool(horario and horario.strip()))
                self.assertNotIn('para continuarmos', texto.casefold())
                self.assertTrue(texto.endswith('\n\nQual o seu nome?'))

    def test_retorno_retira_abertura_repetida_mas_preserva_confirmacoes_e_participante(self):
        from core.integrations.whatsapp.messages import etapa5_messages, etapa10_messages, etapa11_messages, etapa24_messages
        for mensagem in (
            etapa5_messages.MENSAGEM_PADRAO_ETAPA5,
            etapa10_messages.MENSAGEM_PADRAO_ETAPA10,
            etapa11_messages.MENSAGEM_PADRAO_CLIENTE_ETAPA11,
        ):
            with self.subTest(mensagem=mensagem):
                self.assertNotIn('Certo,', aplicar_prefixo_retorno(mensagem, SAUDACAO))
                self.assertEqual(aplicar_prefixo_retorno(mensagem, None), mensagem)
        despedida = etapa24_messages.montar_mensagem_etapa24(status_dependente=True, nome_dependente='Lucas')
        self.assertEqual(aplicar_prefixo_retorno(despedida, SAUDACAO), SAUDACAO + despedida)

    def test_pesquisa_com_cabecalho_primeiro_e_sem_segunda_saudacao(self):
        original = '*Pesquisa de satisfação*\n\nMaravilha, Ana! 😊\n\nAntes de finalizarmos, qual seu grau de satisfação?'
        esperado = '*Pesquisa de satisfação*\n\n' + SAUDACAO + 'Antes de finalizarmos, qual seu grau de satisfação?'
        self.assertEqual(aplicar_prefixo_retorno(original, SAUDACAO), esperado)
        self.assertEqual(aplicar_prefixo_retorno(esperado, SAUDACAO), esperado)
        self.assertEqual(aplicar_prefixo_retorno(original, None), original)

    def test_negrito_de_corpo_nao_vira_cabecalho_e_texto_substantivo_preservado(self):
        texto = '*A sua reserva* é importante. Obrigado pela resposta!'
        self.assertEqual(aplicar_prefixo_retorno(texto, SAUDACAO), SAUDACAO + texto)
        texto = 'Perfeito! 😊\n\nSua experiência é gratuita.'
        self.assertEqual(aplicar_prefixo_retorno(texto, SAUDACAO), SAUDACAO + 'Sua experiência é gratuita.')


if __name__ == '__main__':
    unittest.main()
