"""Destinatário explícito na abertura e compatibilidade da inscrição externa."""

import unittest

from core.validacoes.coleta_abertura import extrair, destinatario, etapa_inicial, valor
from core.integrations.fireads.coleta_abertura import interpretar_parcial
from core.integrations.fireads.destino_coleta import escolher
from core.integrations.fireads.contrato import ABA_DESTINO
from tests.unit.test_coleta_abertura import estado, snapshot, ROW, NUMERO


class DestinatarioAberturaTests(unittest.TestCase):
    def test_exemplos_com_e_sem_para_definem_dependente(self):
        exemplos = {
            'Para uma amiga': 'amiga', 'Para um conhecido': 'conhecido',
            'Para minha amiga': 'amiga', 'Para meu amigo': 'amigo',
            'Minha filha': 'filha', 'Meu filho': 'filho',
            'Minha amiga': 'amiga', 'Meu amigo': 'amigo',
            'Meu conhecido': 'conhecido', 'Minha conhecida': 'conhecida',
            'Para uma conhecida': 'conhecida', 'Para um amigo': 'amigo',
            'A minha cunhada': 'cunhada', 'Para o meu enteado': 'enteado',
            'Minha afilhada': 'afilhada', 'Meu padrasto': 'padrasto',
            'Minha madrasta': 'madrasta', 'Meu genro': 'genro',
            'Minha nora': 'nora', 'Meu bisavô': 'bisavo',
            'Minha bisneta': 'bisneta', 'Minha vizinha': 'vizinha',
            'Meu colega': 'colega', 'Minha namorada': 'namorada',
            'Meu noivo': 'noivo', 'Para um familiar': 'familiar',
            'Minhas filhas': 'filhas', 'Meus sobrinhos': 'sobrinhos',
            'Para minhas amigas': 'amigas', 'Para meus irmãos': 'irmaos',
            ' MINHA AMIGA! 😊 ': 'amiga', 'Pra minha amiga': 'amiga',
        }
        for texto, chave in exemplos.items():
            with self.subTest(texto=texto):
                campo = extrair(texto)['destinatario']
                self.assertEqual(campo['status'], 'aceito')
                self.assertIs(campo['valor']['dependente'], True)
                self.assertEqual(campo['valor']['chave'], chave)

    def test_rotulos_identificam_o_campo_sem_inferir_idade(self):
        for rotulo in ('Para quem é', 'Para quem é o treino?', 'Quem vai fazer',
                       'Quem vai fazer o curso?', 'Quem vai fazer o treino'):
            for resposta, dependente in [('Meu filho', True), ('Minha amiga', True),
                                         ('Para um conhecido', True), ('Para mim', False)]:
                with self.subTest(rotulo=rotulo, resposta=resposta):
                    campo = extrair(f'{rotulo}: {resposta}')['destinatario']
                    self.assertEqual(campo['status'], 'aceito')
                    self.assertIs(campo['valor']['dependente'], dependente)

    def test_faixas_etarias_nao_definem_destinatario(self):
        for texto in ('Criança', 'Adulto', 'Idoso', 'Para uma criança', 'Para um adulto',
                      'Minha criança', 'Meu bebê', 'Para uma pessoa idosa', '61 a 75 anos'):
            for prefixo in ('', 'Quem vai fazer: ', 'Para quem é: '):
                with self.subTest(texto=prefixo + texto):
                    campo = extrair(prefixo + texto)['destinatario']
                    self.assertNotEqual(campo['status'], 'aceito')
                    self.assertIsNone(campo['valor'])

    def test_mencao_posse_negacao_e_pergunta_nao_definem_participante(self):
        for texto in ('Meu nome é João', 'Minha preferência é tarde', 'Meu email é ana@example.com',
                      'Minha amiga me indicou vocês', 'Meu filho já faz o curso',
                      'Minha filha não vai participar', 'Para meu amigo não',
                      'Meu amigo?', 'Quem vai fazer o pagamento: Minha mãe',
                      'Não é para minha amiga', 'Meu', 'Minha', 'Para uma', 'Para um'):
            with self.subTest(texto=texto):
                self.assertNotEqual(extrair(texto)['destinatario']['status'], 'aceito')
        self.assertIsNone(destinatario('Independente'))

    def test_preserva_chaves_historicas_e_combinacoes(self):
        for texto, chave in [('pai_ou_mae', 'mae+pai'), ('Para meu filho', 'filho'),
                             ('Para outra pessoa', 'dependente'),
                             ('Para mim e outra pessoa', 'titular+dependente')]:
            self.assertEqual(destinatario(texto)['chave'], chave)
        self.assertEqual(extrair('Minha mãe e meu pai')['destinatario']['valor']['chave'], 'mae+pai')

    def test_variantes_equivalentes_nao_conflitam_e_destinos_distintos_conflitam(self):
        iguais = extrair('Minha amiga\nPara uma amiga\nQuem vai fazer: Para minha amiga')
        self.assertEqual(iguais['destinatario']['status'], 'aceito')
        for outro in ('Para mim', 'Minha filha', 'Meu conhecido'):
            self.assertEqual(extrair('Minha amiga\n' + outro)['destinatario']['status'], 'conflitante')

    def test_nome_conhecido_pula_pergunta_destinatario_mas_preserva_email_pendente(self):
        coleta = estado('Sou Ana\nQuem vai fazer: Minha filha')
        self.assertEqual(etapa_inicial(coleta), 4)
        self.assertIsNone(valor(coleta, 'email'))
        self.assertTrue(valor(coleta, 'destinatario')['dependente'])
        self.assertEqual(etapa_inicial(estado('Meu amigo')), 1)

    def test_dashboard_usa_recencia_sem_substituir_relacao_da_mensagem(self):
        coleta = estado('Full name: Ana Paula Silva\nMinha amiga')
        amiga = dict(ROW, **{'Para quem é': 'Para uma amiga'})
        filha = dict(ROW, _row=46, **{'Para quem é': 'Para minha filha'})
        decisao = interpretar_parcial([amiga, filha], NUMERO, None, ABA_DESTINO, coleta)
        self.assertEqual(decisao['referencia']['linha'], filha['_row'])
        self.assertEqual(valor(decisao['coleta'], 'email'), 'ana@example.com')
        self.assertEqual(decisao['coleta']['campos']['destinatario']['fonte'], 'mensagem')
        equivalente = interpretar_parcial([filha], NUMERO, None, ABA_DESTINO, coleta)
        self.assertEqual(equivalente['referencia']['linha'], filha['_row'])
        self.assertEqual(valor(equivalente['coleta'], 'email'), 'ana@example.com')
        self.assertEqual(valor(equivalente['coleta'], 'destinatario')['chave'], 'amiga')

    def test_entrega_atualiza_relacao_compativel_ou_cria_se_divergente(self):
        snap = snapshot('Sou Ana Paula Silva\nana@example.com\nQuem vai fazer: Minha amiga')
        snap['rota_formulario_chat'] = estado(
            'Sou Ana Paula Silva\nana@example.com\nQuem vai fazer: Minha amiga'
        )['rota_formulario_chat']
        self.assertTrue(snap['rota_formulario_chat'])
        amiga = dict(ROW, **{'Para quem é': 'Para uma amiga'})
        filha = dict(ROW, _row=46, **{'Para quem é': 'Para minha filha'})
        destino = escolher([amiga, filha], snap)
        self.assertEqual(destino['tipo'], 'update')
        self.assertEqual(destino['referencia']['linha'], amiga['_row'])
        self.assertEqual(escolher([filha], snap), {'tipo': 'create'})
