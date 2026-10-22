"""Complementação usa prioridades de destinatário sem sobrescrever a mensagem."""

from copy import deepcopy
import unittest

from core.validacoes.coleta_abertura import criar_contexto, valor
from core.integrations.fireads.coleta_abertura import interpretar_parcial
from core.integrations.fireads.destino_coleta import escolher, preparar
from core.integrations.fireads.contrato import ABA_DESTINO, bloco_observacoes
from tests.unit.test_coleta_abertura import ROW, NUMERO, snapshot


def registro(linha, destinatario, **dados):
    return dict(ROW, _row=linha, **{'Para quem é': destinatario}, **dados)


def coleta(destinatario='Minha filha', *, turno=None, com_link=False, extras=''):
    texto = 'Full name: Ana Paula Silva\nPara quem é: ' + destinatario
    if turno:
        texto += '\nTurno: ' + turno
    return criar_contexto(1, {'id_mensagem': 1, 'id_hash': 'wamid.teste',
                             'tipo_mensagem': 'text', 'conteudo_texto': texto + extras},
                          coletar_turno=not com_link)


def consultar(rows, estado=None):
    return interpretar_parcial(rows, NUMERO, None, ABA_DESTINO, estado or coleta())


class PrioridadeDestinatarioTests(unittest.TestCase):
    def test_registro_unico_de_amiga_completa_email_da_conversa_para_filha(self):
        estado = coleta()
        antes = deepcopy(estado)
        r = consultar([registro(44, 'Minha amiga')], estado)
        self.assertEqual(r['referencia']['linha'], 44)
        self.assertEqual(valor(r['coleta'], 'email'), 'ana@example.com')
        self.assertEqual(valor(r['coleta'], 'destinatario')['chave'], 'filha')
        self.assertEqual(r['coleta']['campos']['destinatario']['fonte'], 'mensagem')
        self.assertEqual(estado, antes)

    def test_relacao_exata_antiga_precede_dependente_equivalente_mais_recente(self):
        r = consultar([registro(44, 'Para minha filha'), registro(90, 'Para uma amiga',
                       **{'Data/Hora': '21/10/2026 10:00'})])
        self.assertEqual(r['referencia']['linha'], 44)

    def test_mesmo_tipo_precede_outro_tipo_mais_recente(self):
        r = consultar([registro(44, 'Minha amiga'), registro(90, 'Para mim',
                       **{'Data/Hora': '21/10/2026 10:00'})])
        self.assertEqual(r['referencia']['linha'], 44)

    def test_cada_prioridade_desempata_por_data_e_linha(self):
        for destinatario in ('Minha filha', 'Meu amigo', 'Para mim'):
            with self.subTest(destinatario=destinatario):
                rows = [registro(100, destinatario, **{'Data/Hora': '18/10/2026'}),
                        registro(44, destinatario), registro(45, destinatario)]
                self.assertEqual(consultar(rows)['referencia']['linha'], 45)

    def test_fallback_outro_tipo_preserva_destinatario_aceito(self):
        for informado, planilha in [('Minha filha', 'Para mim'), ('Para mim', 'Minha amiga'),
                                   ('Minha filha', ''), ('Minha filha', 'Criança')]:
            with self.subTest(informado=informado, planilha=planilha):
                estado = coleta(informado)
                r = consultar([registro(44, planilha)], estado)
                self.assertEqual(r['referencia']['linha'], 44)
                self.assertEqual(valor(r['coleta'], 'email'), 'ana@example.com')
                self.assertEqual(r['coleta']['campos']['destinatario'], estado['campos']['destinatario'])

    def test_ultimo_recurso_exige_turno_igual_quando_ja_aceito_sem_link(self):
        estado = coleta(turno='Tarde')
        rows = [registro(44, 'Para mim', **{'Período preferido': 'Tarde'}),
                registro(45, 'Para mim', **{'Período preferido': 'Noite'}),
                registro(46, 'Para mim', **{'Período preferido': ''})]
        r = consultar(rows, estado)
        self.assertEqual(r['referencia']['linha'], 44)
        self.assertEqual(valor(r['coleta'], 'turno'), 'tarde')
        r = consultar(rows[1:], estado)
        self.assertIsNone(r['referencia'])
        self.assertIsNone(valor(r['coleta'], 'email'))

    def test_turno_nao_anula_prioridades_de_relacao_ou_tipo(self):
        for destinatario in ('Minha filha', 'Minha amiga'):
            with self.subTest(destinatario=destinatario):
                r = consultar([registro(44, destinatario, **{'Período preferido': 'Noite'})],
                              coleta(turno='Tarde'))
                self.assertEqual(r['referencia']['linha'], 44)
                self.assertEqual(valor(r['coleta'], 'turno'), 'tarde')

    def test_com_link_turno_nao_participa_do_ultimo_recurso(self):
        r = consultar([registro(44, 'Para mim', **{'Período preferido': 'Noite'})],
                      coleta(turno='Tarde', com_link=True))
        self.assertEqual(r['referencia']['linha'], 44)
        self.assertNotIn('turno', r['coleta']['campos'])

    def test_nome_email_conhecidos_filtram_todos_os_niveis(self):
        for destinatario in ('Minha filha', 'Minha amiga', 'Para mim'):
            with self.subTest(destinatario=destinatario):
                self.assertIsNone(consultar([registro(44, destinatario, Nome='Outra Pessoa')])['referencia'])
                r = consultar([registro(44, destinatario, Email='outro@example.com')],
                              coleta(extras='\nEmail: ana@example.com'))
                self.assertIsNone(r['referencia'])
        rows = [registro(45, 'Minha filha', Nome='Outra Pessoa'), registro(44, 'Minha amiga')]
        self.assertEqual(consultar(rows)['referencia']['linha'], 44)

    def test_outro_telefone_e_canal_manual_nao_entram_na_prioridade(self):
        rows = [registro(44, 'Minha filha', WhatsApp='5511999990003'),
                registro(45, 'Minha filha', Canal='Indicação'), registro(43, 'Minha amiga')]
        self.assertEqual(consultar(rows)['referencia']['linha'], 43)
        self.assertIsNone(consultar(rows[:2])['referencia'])

    def test_destinatario_ausente_usa_mais_recente_sem_inventar_valor(self):
        rows = [registro(44, 'Minha filha'), registro(45, '', **{'Período preferido': ''})]
        r = consultar(rows, coleta('', turno='Sábado'))
        self.assertEqual(r['referencia']['linha'], 45)
        self.assertIsNone(valor(r['coleta'], 'destinatario'))
        self.assertEqual(valor(r['coleta'], 'turno'), 'sabado')

    def test_nao_mistura_email_de_outra_linha_apos_escolher_relacao_exata(self):
        rows = [registro(44, 'Minha filha', Email=''), registro(45, 'Minha amiga')]
        r = consultar(rows)
        self.assertEqual(r['referencia']['linha'], 44)
        self.assertIsNone(valor(r['coleta'], 'email'))

    def test_entrega_usa_a_linha_vinculada_sem_alterar_campos_da_planilha(self):
        row = registro(44, 'Minha amiga')
        antes = deepcopy(row)
        r = consultar([row])
        snap = snapshot()
        snap['referencia'] = r['referencia']
        snap['destino'] = escolher([row], snap)
        op = preparar([row], snap, bloco_observacoes(1, 1, 'Resumo para a filha'))
        self.assertEqual(op['row'], 44)
        self.assertEqual(set(op), {'row', 'observacoes'})
        self.assertTrue(op['observacoes'].startswith(ROW['Observação']))
        self.assertEqual(row, antes)
