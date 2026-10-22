"""Autoridade do chat e retomada de escritas parciais, sem serviços externos."""

from copy import deepcopy
import unittest
from unittest.mock import Mock, patch

from core.integrations.fireads.cliente import ClienteFireAds
from core.integrations.fireads.contrato import ABA_DESTINO, ErroFireAds, bloco_observacoes
from core.integrations.fireads.coleta_abertura import interpretar_parcial
from core.integrations.fireads.sincronizacao_coleta import dados_sincronizacao, escolher, preparar
from core.validacoes.coleta_abertura import campo, criar_contexto
from tests.unit.test_coleta_abertura import FORM, NUMERO, ROW, snapshot

BLOCO = bloco_observacoes(1, 1, 'NOVO LEAD : META ADS : TITULAR\n- Nome do cliente: Ana Paula', versao=3)


def coleta(texto=FORM + '\nTurno: Tarde', *, com_link=False):
    return criar_contexto(1, {'id_mensagem': 1, 'id_hash': 'wamid.teste',
                             'tipo_mensagem': 'text', 'conteudo_texto': texto},
                          coletar_turno=not com_link)


def retrato(estado=None, *, com_link=False):
    return dict(snapshot(), versao=4, observacoes=BLOCO,
                **dados_sincronizacao(estado or coleta(), com_link=com_link))


def row(**kwargs):
    return dict(ROW, **{'Período preferido': 'Manhã'}, **kwargs)


def planejar(rows, snap=None):
    snap = snap or retrato()
    snap['destino'] = escolher(rows, snap)
    return snap


class AutoridadeTests(unittest.TestCase):
    def test_nome_completo_relacao_email_turno_e_correcao_do_atendimento(self):
        estado = coleta(FORM.replace('Para mim', 'Minha filha') + '\nTurno: Tarde')
        estado['campos']['email'] = campo(['corrigido@example.com'], 'email', 'atendimento')
        campos = dados_sincronizacao(estado)['campos_dashboard']
        self.assertEqual(campos, {'Nome': 'Ana Paula Silva', 'Email': 'corrigido@example.com',
                                 'Para quem é': 'Minha filha', 'Período preferido': 'Tarde'})
        self.assertEqual(estado['mensagem_original']['email']['valor'], 'ana@example.com')

    def test_dados_ausentes_invalidos_conflitantes_ou_importados_nao_sobrescrevem(self):
        estado = coleta('Full name: Ana Paula Silva\nEmail: x\nPara quem é: Criança\nTurno: tarde ou noite')
        estado['campos']['email'] = campo(['importado@example.com'], 'email', 'dashboard')
        self.assertEqual(dados_sincronizacao(estado)['campos_dashboard'], {'Nome': 'Ana Paula Silva'})
        estado['campos']['email'] = campo(['a@example.com', 'b@example.com'], 'email')
        self.assertNotIn('Email', dados_sincronizacao(estado)['campos_dashboard'])

    def test_com_link_nao_escreve_turno_nem_o_usa_para_selecionar(self):
        snap = retrato(com_link=True)
        self.assertNotIn('Período preferido', snap['campos_dashboard'])
        self.assertNotIn('turno', snap['identidade_coleta'])
        self.assertFalse(snap['coletar_turno'])

    def test_consulta_divergente_preserva_os_conhecidos_e_deixa_so_ausente_pendente(self):
        estado = coleta('Nome: Ana Paula Silva\nPara quem é: Minha filha\nTurno: Tarde')
        r = interpretar_parcial([row(Nome='Outro Nome')], NUMERO, None, ABA_DESTINO, estado)
        for tipo in ('nome', 'destinatario', 'turno'):
            self.assertEqual(r['coleta']['campos'][tipo], estado['campos'][tipo])
        self.assertEqual(r['coleta']['campos']['email']['status'], 'ausente')


class SelecaoTests(unittest.TestCase):
    def test_incompativeis_do_mesmo_telefone_atualiza_mais_recente_elegivel(self):
        rows = [row(Nome='Outro', Email='outro@example.com', _row=44),
                row(Nome='Diferente', Email='dif@example.com', _row=45),
                row(_row=100, Canal='Indicação')]
        self.assertEqual(escolher(rows, retrato())['referencia']['linha'], 45)

    def test_relacao_exata_depois_logica_depois_demais_e_recencia(self):
        snap = retrato(coleta(FORM.replace('Para mim', 'Minha filha')))
        rows = [dict(row(), _row=10, **{'Para quem é': 'Para minha filha'}),
                dict(row(), _row=20, **{'Para quem é': 'Para uma amiga'}),
                dict(row(), _row=30, **{'Período preferido': 'Tarde'})]
        for restantes, linha in [(rows, 10), (rows[1:], 20), (rows[2:], 30)]:
            self.assertEqual(escolher(restantes, snap)['referencia']['linha'], linha)

    def test_prioridade_compativel_nome_email_antes_de_divergente_recente(self):
        rows = [row(_row=44), row(_row=99, Email='outro@example.com')]
        self.assertEqual(escolher(rows, retrato())['referencia']['linha'], 44)

    def test_fallback_usa_data_antes_da_linha(self):
        rows = [dict(row(Nome='X'), _row=90, **{'Data/Hora': '18/10/2026'}),
                dict(row(Nome='Y'), _row=44, **{'Data/Hora': '20/10/2026'})]
        self.assertEqual(escolher(rows, retrato())['referencia']['linha'], 44)

    def test_ausente_cria_com_nome_completo_e_turno(self):
        dados = preparar([], planejar([]), BLOCO)['dados']
        self.assertEqual(dados['Nome'], 'Ana Paula Silva')
        self.assertEqual(dados['Período preferido'], 'Tarde')
        self.assertEqual(dados['WhatsApp'], NUMERO)

    def test_manual_nao_e_alvo_e_outro_telefone_nao_e_alvo(self):
        self.assertEqual(escolher([row(Canal='Lead Franqueador')], retrato()), {'tipo': 'create'})
        with self.assertRaises(ErroFireAds):
            escolher([row(WhatsApp='5511999990003')], retrato())

    def test_vinculo_da_consulta_precede_nova_inscricao(self):
        from core.integrations.fireads.aba_geral import referencia_registro
        snap = retrato()
        snap['referencia'] = referencia_registro(row(), ABA_DESTINO)
        self.assertEqual(escolher([row(), row(_row=100)], snap)['referencia']['linha'], 44)


class RecuperacaoTests(unittest.TestCase):
    def setUp(self):
        self.original = row(Nome='Nome antigo', Email='antigo@example.com')
        self.snap = planejar([self.original])

    def aplicar(self, r, operacao):
        return dict(r, **operacao['campos'], **{'Observação': operacao['observacoes']})

    def test_update_preserva_outras_colunas_e_observacoes(self):
        antes = deepcopy(self.original)
        op = preparar([self.original], self.snap, BLOCO)
        depois = self.aplicar(self.original, op)
        self.assertEqual(depois['Nome'], 'Ana Paula Silva')
        self.assertEqual(depois['Email'], 'ana@example.com')
        self.assertEqual(depois['Período preferido'], 'Tarde')
        for c in set(self.original) - set(op['campos']) - {'Observação'}:
            self.assertEqual(depois[c], antes[c])
        self.assertEqual(depois['Observação'], antes['Observação'] + '\n\n' + BLOCO)
        self.assertEqual(self.original, antes)

    def test_resposta_perdida_reconcilia_e_nao_duplica_observacoes(self):
        depois = self.aplicar(self.original, preparar([self.original], self.snap, BLOCO))
        self.assertIsNone(preparar([depois], self.snap, BLOCO))

    def test_cada_ponto_de_queda_parcial_e_recuperavel_inclusive_linha_movida(self):
        op = preparar([self.original], self.snap, BLOCO)
        itens = list(op['campos'].items())
        for n in range(len(itens) + 1):
            with self.subTest(campos_aplicados=n):
                parcial = dict(self.original, _row=75, **dict(itens[:n]))
                reenvio = preparar([parcial], self.snap, BLOCO)
                self.assertEqual(reenvio['row'], 75)
                final = self.aplicar(parcial, reenvio)
                self.assertIsNone(preparar([final], self.snap, BLOCO))

    def test_marcador_so_nao_basta_se_campos_ainda_divergem(self):
        parcial = dict(self.original, **{'Observação': self.original['Observação'] + '\n\n' + BLOCO})
        op = preparar([parcial], self.snap, BLOCO)
        self.assertEqual(op['observacoes'], parcial['Observação'])
        self.assertEqual(op['campos']['Email'], 'ana@example.com')

    def test_mudanca_em_dado_do_chat_na_planilha_e_reaplicada(self):
        alterado = dict(self.original, Nome='Edição manual', Email='manual@example.com')
        op = preparar([alterado], self.snap, BLOCO)
        self.assertEqual(op['campos']['Nome'], 'Ana Paula Silva')

    def test_exclusao_nao_redireciona_para_outro_registro_ou_telefone(self):
        for substituto in (row(WhatsApp='5511999990003'),
                           dict(row(), **{'Data/Hora': '21/10/2026'})):
            with self.subTest(substituto=substituto):
                with self.assertRaises(ErroFireAds):
                    preparar([substituto], self.snap, BLOCO)

    def test_registros_indistinguiveis_movidos_nao_sao_adivinhados(self):
        with self.assertRaises(ErroFireAds):
            preparar([dict(self.original, _row=50), dict(self.original, _row=51)], self.snap, BLOCO)

    def test_novo_registro_apos_reserva_nao_troca_destino(self):
        rows = [self.original, dict(row(), _row=100, **{'Data/Hora': '22/10/2026'})]
        self.assertEqual(preparar(rows, self.snap, BLOCO)['row'], 44)

    def test_marcador_duplicado_ou_alterado_nao_confirma_entrega(self):
        marcado = dict(self.original, **{'Observação': BLOCO})
        with self.assertRaises(ErroFireAds):
            preparar([marcado, dict(marcado, _row=75)], self.snap, BLOCO)
        with self.assertRaises(ErroFireAds):
            preparar([dict(marcado, **{'Observação': BLOCO.replace('Ana Paula', 'Nome editado')})], self.snap, BLOCO)

    def test_append_aplicado_reconcilia_ou_repara_sem_novo_append(self):
        snap = planejar([])
        criado = dict(preparar([], snap, BLOCO)['dados'], _row=99)
        self.assertIsNone(preparar([criado], snap, BLOCO))
        criado['Email'] = 'antigo@example.com'
        op = preparar([criado], snap, BLOCO)
        self.assertEqual(op['row'], 99)
        self.assertNotIn('dados', op)
        self.assertEqual(op['observacoes'], BLOCO)

    def test_campo_ausente_na_resposta_nao_autoriza_sucesso(self):
        incompleto = dict(self.original)
        incompleto.pop('Período preferido')
        with self.assertRaises(ErroFireAds):
            preparar([incompleto], self.snap, BLOCO)


class ClienteTests(unittest.TestCase):
    def test_post_envia_quatro_campos_e_exige_recibo_de_todos(self):
        cliente = ClienteFireAds('https://script.google.com/macros/s/teste/exec')
        campos = retrato()['campos_dashboard']
        for confirmados, ok in [(list(campos) + ['Observação'], True), (['Observação'], False)]:
            with patch.object(cliente, '_request', return_value=Mock(json=Mock(return_value={
                    'success': True, 'aba': ABA_DESTINO, 'row': 44, 'updated': confirmados}))) as req:
                if ok:
                    cliente.enviar(ABA_DESTINO, row=44, campos=campos, observacoes=BLOCO)
                else:
                    with self.assertRaises(ErroFireAds):
                        cliente.enviar(ABA_DESTINO, row=44, campos=campos, observacoes=BLOCO)
                updates = req.call_args.kwargs['json']['updates']
                self.assertEqual(list(updates)[-1], 'Observação')
                self.assertEqual(updates, dict(campos, **{'Observação': BLOCO}))
        cliente.close()

    def test_campos_vazios_e_colunas_fora_do_escopo_nao_sao_enviados(self):
        cliente = ClienteFireAds('https://script.google.com/macros/s/teste/exec')
        with patch.object(cliente, '_request') as req:
            for campos in ({'Email': ''}, {'Nome': None}, {'Canal': 'Meta Ads'}, {'WhatsApp': NUMERO}):
                with self.assertRaises(ErroFireAds):
                    cliente.enviar(ABA_DESTINO, row=44, campos=campos, observacoes=BLOCO)
            req.assert_not_called()
        cliente.close()

    def test_script_recusa_coluna_mantem_erro(self):
        cliente = ClienteFireAds('https://script.google.com/macros/s/teste/exec')
        with patch.object(cliente, '_request', return_value=Mock(json=Mock(return_value={
                'success': False, 'error': 'Coluna não editável: Nome'}))):
            with self.assertRaisesRegex(ErroFireAds, 'atualizar EDITABLE_COLUMNS'):
                cliente.enviar(ABA_DESTINO, row=44, campos={'Nome': 'Ana'}, observacoes=BLOCO)
        cliente.close()


if __name__ == '__main__':
    unittest.main()
