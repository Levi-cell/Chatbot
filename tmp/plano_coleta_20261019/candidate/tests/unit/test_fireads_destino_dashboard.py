"""Seleção e retomada do envio: banco, HTTP e dados de clientes são simulados."""

from contextlib import ExitStack
from copy import deepcopy
import unittest
from unittest.mock import Mock, patch

from core.integrations.fireads.contrato import ErroFireAds, bloco_observacoes
from core.integrations.fireads.destino_dashboard import destinatario_perfil
from tests.helpers import FakeConn, FakeCursor
from workers.worker_funil import fireads


NUMERO = "5511999990002"


def linha(numero, canal="Google Ads", perfil="Para mim", **campos):
    return {
        "_row": numero,
        "Nome": "Ana",
        "WhatsApp": NUMERO,
        "Email": "ana@example.com",
        "Canal": canal,
        "Perfil/Faixa": perfil,
        "Observação": "FR002\nAnotação comercial existente",
        **campos,
    }


class DestinoDashboardTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = {
            "telefone": NUMERO,
            "nome": "Ana",
            "email": "ana@example.com",
            "origem": "google",
            "perfil": "Titular (40 anos)",
            "status_dependente": False,
            "url": "https://script.google.com/macros/s/teste/exec",
            "aba": "LEADS GERAL - Feedback",
            "observacoes": "Canal de venda: Google Ads\nTexto do Funil",
        }
        self.bloco = bloco_observacoes(1, 287, self.snapshot["observacoes"])

    def preparar(self, rows):
        return fireads.preparar_escrita(rows, self.snapshot, self.bloco)

    def test_canal_prevalece_sobre_linha_e_destinatario(self):
        self.snapshot["origem"] = "meta"
        self.assertEqual(self.preparar([
            linha(44, "Meta Ads", "Para meu pai/mãe"),
            linha(46),
        ])["row"], 44)

    def test_variantes_de_canal_google_incluem_organico_site(self):
        for canal in ("Google Ads", "MKT DIGITAL - GOOGLE ADS", "Organico Site", "Orgânico Site"):
            with self.subTest(canal=canal):
                self.assertEqual(self.preparar([
                    linha(44, canal), linha(46, "Meta Ads"),
                ])["row"], 44)

    def test_variantes_de_canal_meta(self):
        self.snapshot["origem"] = "meta"
        for canal in ("meta_ads", "MKT DIGITAL - META ADS (FACEBOOK/INSTAGRAM)"):
            with self.subTest(canal=canal):
                self.assertEqual(self.preparar([
                    linha(44, canal), linha(46),
                ])["row"], 44)

    def test_organico_site_nao_e_preferencia_para_origem_organica(self):
        self.snapshot["origem"] = "organico"
        self.assertEqual(self.preparar([
            linha(44, "Orgânico"), linha(46, "Organico Site"),
        ])["row"], 44)

    def test_titular_ou_dependente_prevalece_sobre_linha_no_mesmo_canal(self):
        for dependente, esperado in ((False, 44), (True, 46)):
            with self.subTest(dependente=dependente):
                self.snapshot["status_dependente"] = dependente
                self.assertEqual(self.preparar([
                    linha(44), linha(46, perfil="Para mim e outra pessoa"),
                ])["row"], esperado)

    def test_envio_antigo_sem_booleano_recupera_destinatario_do_perfil(self):
        self.snapshot.pop("status_dependente")
        for perfil, esperado in (("Titular (40 anos)", 44), ("Dependente: Enzo (12 anos)", 45)):
            with self.subTest(perfil=perfil):
                self.snapshot["perfil"] = perfil
                self.assertEqual(self.preparar([
                    linha(44), linha(45, perfil="Para meu filho ou filha"),
                    linha(46, perfil="61_a_75"),
                ])["row"], esperado)

    def test_faixa_etaria_nao_define_titular_ou_dependente(self):
        for perfil in ("61_a_75", "Adulto", "6 a 15 anos", "Pessoa com 60 anos ou mais", "", None):
            with self.subTest(perfil=perfil):
                self.assertIsNone(destinatario_perfil(perfil))
        self.assertEqual(self.preparar([
            linha(44, perfil="6 a 15 anos"), linha(46, perfil="61_a_75"),
        ])["row"], 46)

    def test_sem_destinatario_compativel_usa_maior_linha_do_canal(self):
        self.assertEqual(self.preparar([
            linha(44, perfil="Para outra pessoa"),
            linha(46, perfil="Para meu avô/avó"),
        ])["row"], 46)

    def test_sem_canal_compativel_usa_maior_linha_do_telefone(self):
        self.assertEqual(self.preparar([
            linha(44, "FACHADA"), linha(46, "", "Para outra pessoa"),
        ])["row"], 46)

    def test_escrita_usa_maior_linha_independente_da_data_e_ordem_recebida(self):
        rows = [linha(46, **{"Data/Hora": "01/10/2026 00:00"}),
                linha(45, **{"Data/Hora": "10/10/2026 12:00"}), linha(44)]
        self.assertEqual(self.preparar(rows)["row"], 46)
        self.assertEqual(self.preparar(list(reversed(rows)))["row"], 46)

    def test_equivalentes_de_telefone_participam_igualmente(self):
        self.assertEqual(self.preparar([
            linha(44), linha(45, WhatsApp="p:+5511999990002"),
            linha(46, WhatsApp="(11) 9999-0002"),
        ])["row"], 46)

    def test_email_diferente_nao_bloqueia_nem_altera_demais_campos(self):
        rows = [linha(44), linha(46, Nome="Outro nome", Email="novo@example.com")]
        original = deepcopy(rows)
        op = self.preparar(rows)
        self.assertEqual(set(op), {"row", "observacoes"})
        self.assertEqual(op["row"], 46)
        self.assertEqual(op["observacoes"], rows[1]["Observação"] + "\n\n" + self.bloco)
        self.assertEqual(rows, original)

    def test_retry_reconcilia_linha_antiga_antes_de_escolher_outra(self):
        self.assertIsNone(self.preparar([
            linha(44, "Meta Ads", "61_a_75", **{"Observação": "campanha\n\n" + self.bloco}),
            linha(46),
        ]))

    def test_bloco_de_outra_conversa_nao_impede_entrega(self):
        antigo = bloco_observacoes(1, 286, "Atendimento anterior")
        self.assertEqual(self.preparar([
            linha(44, **{"Observação": antigo}), linha(46),
        ])["row"], 46)

    def test_bloco_divergente_em_linha_antiga_nao_e_repetido_em_outra(self):
        alterado = self.bloco.replace("Texto do Funil", "Texto editado")
        with self.assertRaisesRegex(ErroFireAds, "conteúdo divergente"):
            self.preparar([linha(44, **{"Observação": alterado}), linha(46)])

    def test_linha_invalida_ou_observacao_ausente_nao_autoriza_escrita(self):
        for invalida in (None, "46", 1, -1, True, 46.5):
            with self.subTest(linha=invalida), self.assertRaisesRegex(ErroFireAds, "Linha"):
                self.preparar([linha(invalida)])
        sem_obs = linha(46)
        sem_obs.pop("Observação")
        with self.assertRaisesRegex(ErroFireAds, "Observação ausente"):
            self.preparar([sem_obs])

    def test_organico_novo_cria_somente_com_dados_do_atendimento(self):
        self.snapshot["origem"] = "organico"
        op = self.preparar([linha(9999, WhatsApp="5511888880003", Email="outro@example.com")])
        self.assertEqual(op, {"dados": {
            "Nome": "Ana", "Email": "ana@example.com", "WhatsApp": NUMERO,
            "Perfil/Faixa": self.snapshot["perfil"], "Canal": "Orgânico",
            "Observação": self.bloco,
        }})

    def test_email_em_outro_telefone_continua_pendente_sem_atualizar_terceiro(self):
        with self.assertRaisesRegex(ErroFireAds, "outro telefone"):
            self.preparar([linha(46, WhatsApp="5511888880003")])

    def preparar_processamento(self, rows):
        stack = ExitStack()
        self.addCleanup(stack.close)
        api = Mock()
        api.consultar.return_value = {
            "headers": ["Nome", "Email", "WhatsApp", "Observação", "Canal", "Perfil/Faixa"],
            "rows": rows,
        }
        mocks = {nome: stack.enter_context(patch.object(fireads, nome)) for nome in (
            "bloquear_contato", "liberar_contato", "conferir_posse", "concluir", "reagendar",
        )}
        mocks["bloquear_contato"].return_value = True
        stack.enter_context(patch.object(fireads, "ClienteFireAds", return_value=api))
        envio = {"id": 1, "integracao": 1, "conversa": 287, "tentativa": 2, "snapshot": self.snapshot}
        conn = FakeConn(FakeCursor())
        return api, mocks, envio, conn

    def test_worker_reconcilia_sem_post_e_grava_linha_no_recibo(self):
        api, mocks, envio, conn = self.preparar_processamento([
            linha(44, "Meta Ads", **{"Observação": self.bloco}), linha(46),
        ])
        self.assertTrue(fireads.processar(envio, conn, conn.cursor()))
        api.enviar.assert_not_called()
        recibo = mocks["concluir"].call_args.args[1]
        self.assertEqual(recibo["linhas_reconciliadas"], [44])
        self.assertTrue(recibo["reconciliado"])
        mocks["reagendar"].assert_not_called()
        mocks["liberar_contato"].assert_called_once()
        api.close.assert_called_once()

    def test_worker_envia_so_observacoes_e_persiste_recibo_confirmado(self):
        api, mocks, envio, conn = self.preparar_processamento([linha(44), linha(46)])
        api.enviar.return_value = {"success": True, "row": 46, "aba": self.snapshot["aba"], "updated": ["Observação"]}
        self.assertTrue(fireads.processar(envio, conn, conn.cursor()))
        api.enviar.assert_called_once_with(
            self.snapshot["aba"], row=46, observacoes=linha(46)["Observação"] + "\n\n" + self.bloco
        )
        self.assertEqual(mocks["concluir"].call_args.args[1], api.enviar.return_value)
        self.assertEqual(mocks["conferir_posse"].call_count, 2)
        mocks["reagendar"].assert_not_called()

    def test_worker_falha_externa_reagenda_sem_marcar_sucesso(self):
        api, mocks, envio, conn = self.preparar_processamento([linha(46)])
        api.enviar.side_effect = ErroFireAds("FireAds recusou a operação")
        self.assertFalse(fireads.processar(envio, conn, conn.cursor()))
        mocks["concluir"].assert_not_called()
        mocks["reagendar"].assert_called_once()
        mocks["liberar_contato"].assert_called_once()
        self.assertEqual(conn.rollbacks, 1)

    def test_worker_lock_ocupado_nao_consulta_nem_envia(self):
        api, mocks, envio, conn = self.preparar_processamento([linha(46)])
        mocks["bloquear_contato"].return_value = False
        self.assertFalse(fireads.processar(envio, conn, conn.cursor()))
        api.consultar.assert_not_called()
        api.enviar.assert_not_called()
        mocks["concluir"].assert_not_called()
        mocks["reagendar"].assert_called_once()
        mocks["liberar_contato"].assert_not_called()
