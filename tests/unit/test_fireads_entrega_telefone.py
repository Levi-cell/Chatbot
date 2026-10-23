"""Telefone/recência e orçamento por operação, sem rede nem banco."""

import unittest
from unittest.mock import Mock, patch

from core.integrations.fireads.aba_geral import selecionar_entrega, referencia_registro
from core.integrations.fireads.cliente import ClienteFireAds
from core.integrations.fireads.contrato import ABA_DESTINO, ErroFireAds
from core.integrations.fireads.coleta_abertura import interpretar_parcial
from core.integrations.fireads.sincronizacao_coleta import preparar
from tests.unit.test_coleta_abertura import ROW, NUMERO
from tests.unit.test_fireads_sincronizacao_coleta import retrato, BLOCO, coleta


class TelefoneTests(unittest.TestCase):
    def test_nome_email_relacao_turno_nao_filtram_e_variantes_concorrem(self):
        for numero in (NUMERO, NUMERO[2:], 'p:+' + NUMERO, '(11) 99999-0002',
                       '551199990002', '(11) 9999-0002'):
            with self.subTest(numero=numero):
                recente = dict(ROW, _row=751, WhatsApp=numero, Nome='Ed',
                               Email='outro@example.com', Canal='Chat Fire',
                               **{'Para quem é': 'Meu filho', 'Período preferido': 'Manhã'})
                self.assertIs(selecionar_entrega([ROW, recente], NUMERO), recente)

    def test_excecao_manual_independe_da_quantidade_e_recencia(self):
        manuais = [dict(ROW, _row=900, Canal='Indicação'), dict(ROW, _row=901, Canal='Lead Franqueador')]
        self.assertIsNone(selecionar_entrega(manuais, NUMERO))
        self.assertIs(selecionar_entrega([ROW, *manuais], NUMERO), ROW)
        organico = dict(ROW, _row=902, Canal='Orgânico')
        self.assertIsNone(selecionar_entrega([*manuais, organico], NUMERO))
        self.assertIs(selecionar_entrega([ROW, *manuais, organico], NUMERO), ROW)

    def test_data_precede_linha_e_canal_desconhecido_nao_autoriza_criacao(self):
        novo = dict(ROW, _row=2, **{'Data/Hora': '22/10/2026 15:01'})
        self.assertIs(selecionar_entrega([ROW, novo], NUMERO), novo)
        self.assertIsNone(selecionar_entrega([ROW], '5511999990003'))
        for canal in ('', 'Canal novo'):
            with self.assertRaises(ErroFireAds):
                selecionar_entrega([dict(novo, Canal=canal)], NUMERO)

    def test_consulta_importa_so_ausencias_e_nao_inventa_meta(self):
        estado = coleta('Nome: Edcarlos\nPara quem é: Minha filha\nTurno: Sábado')
        row = dict(ROW, Nome='Ed', Canal='Chat Fire', **{'Período preferido': 'Tarde'})
        r = interpretar_parcial([row], NUMERO, None, ABA_DESTINO, estado)
        self.assertEqual(r['origem'], 'chat_fire')
        self.assertEqual(r['coleta']['campos']['email']['valor'], 'ana@example.com')
        for tipo in ('nome', 'destinatario', 'turno'):
            self.assertEqual(r['coleta']['campos'][tipo], estado['campos'][tipo])
        self.assertEqual(interpretar_parcial([], NUMERO, None, ABA_DESTINO, estado)['origem'], 'organico')

    def test_v5_reconcilia_append_organico_sem_novo_cadastro(self):
        snap = dict(retrato(), versao=5, origem='organico', destino={'tipo': 'create'})
        manual = dict(ROW, Canal='Indicação')
        op = preparar([manual], snap, BLOCO)
        self.assertEqual(op['dados']['Canal'], 'Orgânico')
        criado = dict(op['dados'], _row=100)
        self.assertIsNone(preparar([manual, criado], snap, BLOCO))
        # Telefone é identidade: mesmo e-mail de outro telefone não impede append.
        self.assertIn('dados', preparar([dict(manual, WhatsApp='5511999990003')], snap, BLOCO))

    def test_v5_retry_mantem_linha_mesmo_que_apareca_registro_novo(self):
        row = dict(ROW, **{'Período preferido': 'Manhã'})
        snap = dict(retrato(), versao=5, destino={
            'tipo': 'update', 'referencia': referencia_registro(row, ABA_DESTINO)})
        recente = dict(row, _row=751, Canal='Chat Fire')
        op = preparar([row, recente], snap, BLOCO)
        self.assertEqual(op['row'], 44)
        modificado = dict(row, **op['campos'], **{'Observação': op['observacoes']})
        self.assertIsNone(preparar([modificado, recente], snap, BLOCO))
        self.assertEqual(recente['Observação'], ROW['Observação'])


class PrazosTests(unittest.TestCase):
    def test_get_e_post_tem_300s_cada_redirect_compartilha_orcamento(self):
        session = Mock()
        with patch('core.integrations.fireads.cliente.time.monotonic', return_value=0) as tempo:
            cliente = ClienteFireAds('https://script.google.com/macros/s/teste/exec',
                                     segundos=300, timeout_leitura=None,
                                     por_operacao=True, session=session)

            def responder(method, *_args, **_kwargs):
                if session.request.call_count == 1:
                    tempo.return_value = 250
                    return Mock(status_code=302, headers={'Location': 'https://script.googleusercontent.com/macros/echo'})
                if method == 'GET':
                    tempo.return_value = 299
                    return Mock(status_code=200, json=Mock(return_value={
                        'success': True, 'data': {'aba': ABA_DESTINO, 'headers': [], 'rows': []}}))
                tempo.return_value = 580
                return Mock(status_code=200, json=Mock(return_value={'success': True, 'aba': ABA_DESTINO, 'inserted': 1}))

            session.request.side_effect = responder
            cliente.consultar(ABA_DESTINO)
            cliente.enviar(ABA_DESTINO, dados={})
            self.assertEqual([c.kwargs['timeout'][1] for c in session.request.call_args_list], [300, 50, 300])
            self.assertEqual([c.args[0] for c in session.request.call_args_list], ['GET', 'GET', 'POST'])
            cliente.close()

    def test_post_nao_e_repetido_automaticamente_apos_timeout(self):
        session = Mock()
        session.request.side_effect = TimeoutError('Resposta perdida')
        cliente = ClienteFireAds('https://script.google.com/macros/s/teste/exec',
                                 segundos=300, timeout_leitura=None, por_operacao=True, session=session)
        with self.assertRaises(TimeoutError):
            cliente.enviar(ABA_DESTINO, dados={})
        session.request.assert_called_once()
        cliente.close()
