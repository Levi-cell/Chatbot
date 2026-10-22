"""Abertura Chat Fire, preferência antecipada e salto seguro após a triagem."""

from copy import deepcopy
from unittest import TestCase
from unittest.mock import patch

from core.validacoes.coleta_abertura import criar_contexto, extrair, completo, valor, etapa_inicial
from core.integrations.fireads.coleta_abertura import interpretar_parcial
from core.integrations.fireads.contrato import CANAIS, ABA_DESTINO
from core.integrations.fireads.destino_coleta import preparar, escolher
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa18 import validar_etapa18
from workers.worker_flow.response_flow.etapas import resolver_etapa17 as r17
from tests.unit.test_coleta_abertura import FORM, ROW, NUMERO, snapshot


def coleta(texto=FORM, *, turno=True):
    return criar_contexto(1, {'id_mensagem': 1, 'id_hash': 'teste',
                            'tipo_mensagem': 'text', 'conteudo_texto': texto}, coletar_turno=turno)


class ApresentacaoTests(TestCase):
    def test_apresentacoes_naturais(self):
        for prefixo in ('Eu me chamo', 'Me chamo', 'Sou', 'Eu sou', 'Eu sou a',
                        'Meu nome é', 'O meu nome é', 'Aqui é', 'Aqui quem fala é',
                        'Pode me chamar de'):
            for saudacao in ('', 'Olá! ', 'Oi, ', 'Boa tarde. '):
                with self.subTest(prefixo=prefixo, saudacao=saudacao):
                    campo = extrair(saudacao + prefixo + ' Alline. Vim pelo site.')['nome']
                    self.assertEqual(campo['valor'], 'Alline')
                    self.assertEqual(campo['identidade'], 'alline')

    def test_compostos_e_continuacao_sem_pontuacao(self):
        self.assertEqual(extrair('Eu me chamo João Pedro Silva e quero conhecer o curso')['nome']['valor'], 'João Pedro')
        self.assertEqual(extrair('Olá sou Alline vim pelo site')['nome']['identidade'], 'alline')

    def test_profissao_local_parentesco_e_idade_nao_sao_nomes(self):
        for texto in ('Eu sou professora', 'Sou de Santo André', 'Sou aposentada',
                      'Sou a mãe da Ana', 'Meu filho se chama Carlos', 'Sou de manhã',
                      'Sou uma pessoa interessada', 'Eu sou 60+', 'Sou o responsável',
                      'Olá! Quero informações', 'Sou aluna', 'Aqui é a professora'):
            with self.subTest(texto=texto):
                self.assertNotEqual(extrair(texto)['nome']['status'], 'aceito')

    def test_apresentacoes_distintas_mantem_conflito(self):
        self.assertEqual(extrair('Sou Ana\nEu me chamo Maria')['nome']['status'], 'conflitante')

    def test_quem_vai_fazer_nao_inventa_destinatario_por_faixa(self):
        for opcao in ('Criança', 'Adulto', 'Idoso'):
            self.assertEqual(extrair('Quem vai fazer: ' + opcao)['destinatario']['status'], 'invalido')
        self.assertFalse(extrair('Quem vai fazer: Para mim')['destinatario']['valor']['dependente'])


class TurnoAberturaTests(TestCase):
    def test_rotulos_e_valores_validos(self):
        for rotulo in ('Melhor período', 'Período preferido', 'Turno', 'Turno de preferência'):
            for texto, esperado in [('Manhã', 'manha'), ('Tarde', 'tarde'), ('Noite', 'noite'), ('Sábado', 'sabado')]:
                with self.subTest(rotulo=rotulo, texto=texto):
                    c = coleta(FORM + '\n' + rotulo + ': ' + texto)
                    self.assertEqual(valor(c, 'turno'), esperado)
                    self.assertTrue(completo(c))
                    self.assertEqual(etapa_inicial(c), 4)

    def test_escolha_explicita_e_nao_saudacao_ou_trabalho(self):
        for texto, esperado in [('Prefiro ir de manhã', 'manha'), ('Posso sábado', 'sabado'),
                                 ('Boa tarde', None), ('Trabalho à noite', None),
                                 ('Prefiro tarde ou noite', None), ('Prefiro não ir sábado', None)]:
            with self.subTest(texto=texto):
                self.assertEqual(valor(coleta(FORM + '\n' + texto), 'turno'), esperado)

    def test_turno_nao_e_exigido_nem_extraido_com_link(self):
        c = coleta(FORM + '\nMelhor período: Sábado', turno=False)
        self.assertTrue(completo(c))
        self.assertNotIn('turno', c['campos'])
        r = interpretar_parcial([dict(ROW, **{'Período preferido': 'Tarde'})], NUMERO, None, ABA_DESTINO, c)
        self.assertNotIn('turno', r['coleta']['campos'])

    def test_duplicado_equivalente_e_conflitante(self):
        self.assertEqual(valor(coleta(FORM + '\nTurno: Tarde\nMelhor período: tarde'), 'turno'), 'tarde')
        c = coleta(FORM + '\nTurno: Tarde\nMelhor período: Sábado')
        self.assertEqual(c['campos']['turno']['status'], 'conflitante')
        self.assertFalse(completo(c))

    def test_turno_pendente_nao_muda_a_etapa_inicial(self):
        c = coleta()
        self.assertFalse(completo(c))
        self.assertEqual(etapa_inicial(c), 4)

    def test_sabado_digitado_na_etapa18(self):
        for texto in ('Sábado', 'Pode ser sábado', 'Só posso sábado'):
            self.assertEqual(validar_etapa18(texto), 'sabado')
        self.assertIsNone(validar_etapa18('sábado ou tarde'))


class ChatFireTests(TestCase):
    def consultar(self, c, rows):
        return interpretar_parcial(rows, NUMERO, None, ABA_DESTINO, c)

    def test_caso_alline_email_no_dash_destinatario_perguntado_turno_preservado(self):
        texto = ('Olá! Sou Alline. Vim pelo site e quero agendar minha demonstração de cortesia.\n'
                 'Quem vai fazer: Criança\nMotivo: Apoiar o desempenho nos estudos\n'
                 'De onde venho: Outra cidade\nMelhor período: Sábado')
        row = dict(ROW, Nome='Alline', Email='alline@example.com', Canal='Chat Fire',
                   **{'Para quem é': '', 'Perfil/Faixa': 'Criança', 'Período preferido': ''})
        r = self.consultar(coleta(texto), [row])
        self.assertEqual(r['origem'], 'chat_fire')
        self.assertEqual(valor(r['coleta'], 'nome'), 'Alline')
        self.assertEqual(valor(r['coleta'], 'email'), 'alline@example.com')
        self.assertEqual(valor(r['coleta'], 'turno'), 'sabado')
        self.assertIsNone(valor(r['coleta'], 'destinatario'))
        self.assertEqual(etapa_inicial(r['coleta']), 2)
        self.assertEqual(r['referencia']['linha'], ROW['_row'])

    def test_turno_do_dash_completa_conflito_sem_sobrescrever_aceito(self):
        row = dict(ROW, Canal='Chat Fire', **{'Período preferido': 'Noite'})
        for complemento, esperado in [('', 'noite'), ('\nTurno: Tarde\nTurno: Sábado', 'noite'),
                                     ('\nTurno: Sábado', 'sabado')]:
            r = self.consultar(coleta(FORM + complemento), [row])
            self.assertEqual(valor(r['coleta'], 'turno'), esperado)
            self.assertTrue(completo(r['coleta']))

    def test_turno_nao_e_identidade_nem_autoriza_importar_outro_email(self):
        c = coleta(FORM + '\nTurno: Sábado')
        r = self.consultar(c, [dict(ROW, Email='outro@example.com', Canal='Chat Fire', **{'Período preferido': 'Sábado'})])
        self.assertIsNone(r['referencia'])
        self.assertEqual(valor(r['coleta'], 'email'), 'ana@example.com')

    def test_chat_fire_participa_da_recencia_sem_alterar_outros_codigos(self):
        row = dict(ROW, Canal='Chat Fire', _row=50)
        self.assertEqual(self.consultar(coleta('Oi'), [ROW, row])['origem'], 'chat_fire')
        self.assertEqual(CANAIS['chat_fire'], ('Chat Fire', '113481'))
        self.assertEqual(CANAIS['google'][1], '113336')
        self.assertEqual(CANAIS['meta'][1], '113340')

    def test_create_chat_fire_preserva_nome_canal(self):
        from core.integrations.fireads.contrato import bloco_observacoes
        snap = snapshot()
        snap.update(origem='chat_fire', destino=escolher([], snap))
        dados = preparar([], snap, bloco_observacoes(1, 1, 'Resumo'))['dados']
        self.assertEqual(dados['Canal'], 'Chat Fire')


class SaidaTriagemTests(TestCase):
    def contexto(self, turno=None, link=None):
        return {'id_conversa': 1, 'id_etapa_cliente': 17, 'id_etapa_atual': 17,
                'id_etapa_origem_transicao': 17, 'tipo_mensagem_atual': 'text',
                'texto_cliente_atual': 'Às vezes', 'status_dependente': False,
                'idade_pessoa_triagem': 40, 'idade_cliente': 40, 'nome_cliente': 'Ana',
                'nome_agente_unidade': 'Dora', 'genero_agente_unidade': 'feminino',
                'numero_comercial_unidade': '5511999990001', 'turno': turno,
                'link_agendamento_unidade': link,
                'transicoes_permitidas': {'triagem_concluida_turno_coletado': 19,
                    'triagem_concluida_sem_link': 18, 'triagem_pergunta_6_respondida': 20},
                'mensagem_cliente_atual': {'cliente_telefone': NUMERO,
                    'id_phone_unidade': 'teste', 'id_mensagem_fila': 1}}

    def resolver(self, ctx):
        with patch.object(r17, 'enviar_etapa18', return_value={'id_etapa_resultante': 18}) as turno, \
             patch.object(r17, 'enviar_etapa19', return_value={'id_etapa_resultante': 19}) as comercial, \
             patch.object(r17, 'enviar_etapa20', return_value={'id_etapa_resultante': 20}) as agenda:
            resultado = r17.resolve_etapa17(ctx)
        return resultado, turno, comercial, agenda

    def test_sem_link_turno_coletado_pula_pergunta_e_inclui_preferencia(self):
        for turno in ('manha', 'tarde', 'noite', 'sabado'):
            with self.subTest(turno=turno):
                r, pergunta, comercial, agenda = self.resolver(self.contexto(turno=turno))
                self.assertEqual(r['id_etapa_resultante'], 19)
                self.assertEqual(r['resposta_triagem'], 'às vezes')
                pergunta.assert_not_called()
                agenda.assert_not_called()
                comercial.assert_called_once()

    def test_link_atual_prevalece_mesmo_com_turno_salvo(self):
        r, pergunta, comercial, agenda = self.resolver(self.contexto(turno='sabado', link='https://example.com'))
        self.assertEqual(r['id_etapa_resultante'], 20)
        comercial.assert_not_called()
        pergunta.assert_not_called()

    def test_sem_turno_mantem_pergunta_original(self):
        r, pergunta, comercial, _ = self.resolver(self.contexto())
        self.assertEqual(r['id_etapa_resultante'], 18)
        pergunta.assert_called_once()
        comercial.assert_not_called()

    def test_resposta_triagem_invalida_nao_pula(self):
        c = self.contexto(turno='sabado')
        c['texto_cliente_atual'] = 'quero saber mais'
        with patch.object(r17, 'enviar_etapa17_cliente_contexto_invalido', return_value={'id_etapa_resultante': 17}):
            r, pergunta, comercial, agenda = self.resolver(c)
        self.assertEqual(r['id_etapa_resultante'], 17)
        comercial.assert_not_called()
