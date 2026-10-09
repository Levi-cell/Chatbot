"""Regressões de identidade FireAds, sem acesso ao banco ou às APIs reais."""

from copy import deepcopy
import unittest
from unittest.mock import Mock, patch

from core.integrations.fireads.contrato import (
    ErroFireAds,
    bloco_observacoes,
    formatos_telefone,
    localizar,
    telefone,
)
from tests.helpers import FakeConn, FakeCursor
from workers.worker_flow.fireads import interpretar
from workers.worker_funil.fireads import preparar_escrita, processar


SEM_NONO = "557194111866"
COM_NONO = "5571994111866"
MASCARAS = (
    "71994111866", "(71) 99411-1866", "+55 (71) 99411-1866",
    "p:+5571994111866", "p:71994111866", COM_NONO,
    "7194111866", "(71) 9411-1866", "+55 (71) 9411-1866",
    "p:+557194111866", "p:7194111866", SEM_NONO,
)


def snapshot(numero=SEM_NONO):
    return {
        "telefone": numero,
        "nome": "Ana Paula",
        "email": "ana@example.com",
        "perfil": "Titular",
        "origem": "google",
        "url": "https://script.google.com/macros/s/teste/exec",
        "aba": "geral",
        "observacoes": "Texto do Funil",
    }


class FireAdsTelefonesTests(unittest.TestCase):
    def test_formulario_com_mascara_e_whatsapp_sem_nono_importam(self):
        google = {
            "Nome": "Ana Paula Silva", "Email": "ana@example.com",
            "WhatsApp": "(71) 99411-1866", "Perfil/Faixa": "Para meu pai/mãe",
            "Canal": "Organico Site", "Data/Hora": "09/10/2026 00:00",
        }
        decisao = interpretar([google], [], SEM_NONO, None)
        self.assertEqual(decisao["resultado"], "importado")
        self.assertEqual(decisao["origem"], "google")
        self.assertEqual(decisao["dados_titular"]["nome"], "Ana Paula")
        self.assertIs(decisao["status_dependente"], True)

    def test_google_e_meta_aceitam_formatos_em_ambos_os_sentidos(self):
        for recebido in MASCARAS:
            for cadastrado in MASCARAS:
                google = {"Nome": "Ana Paula Silva", "Email": "ana@example.com",
                          "WhatsApp": cadastrado, "Perfil/Faixa": "Para mim"}
                meta = {"full_name": "Ana Paula Silva", "email": "ana@example.com",
                        "phone_number": cadastrado, "para_quem": "para_mim"}
                for origem, g, m in (("google", [google], []), ("meta", [], [meta])):
                    with self.subTest(recebido=recebido, cadastrado=cadastrado, origem=origem):
                        decisao = interpretar(g, m, recebido, None)
                        self.assertEqual(decisao["resultado"], "importado")
                        self.assertEqual(decisao["origem"], origem)

    def test_exato_tem_prioridade_na_mesma_aba_e_variacao_e_fallback(self):
        exato = {"WhatsApp": SEM_NONO}
        alternativo = {"WhatsApp": COM_NONO}
        self.assertEqual(localizar([alternativo, exato], SEM_NONO, "WhatsApp"), [exato])
        self.assertEqual(localizar([exato, alternativo], COM_NONO, "WhatsApp"), [alternativo])
        self.assertEqual(localizar([alternativo], SEM_NONO, "WhatsApp"), [alternativo])

    def test_mais_recente_entre_fontes_continua_valendo_com_variacao(self):
        google = {"Nome": "Ana Paula Silva", "Email": "ana@example.com",
                  "WhatsApp": SEM_NONO, "Perfil/Faixa": "Para mim",
                  "Data/Hora": "2026-10-09T12:00:00-03:00"}
        meta = {"full_name": "Ana Paula Silva", "email": "ana@example.com",
                "phone_number": COM_NONO, "para_quem": "para_mim",
                "created_time": "2026-10-09T12:01:00-03:00"}
        for numero in (SEM_NONO, COM_NONO):
            self.assertEqual(interpretar([google], [meta], numero, None)["origem"], "meta")

    def test_nono_digito_nao_torna_dados_incompletos_validos(self):
        google = {"Nome": "Ana Paula Silva", "Email": "invalido",
                  "WhatsApp": COM_NONO, "Perfil/Faixa": "Para mim"}
        self.assertEqual(interpretar([google], [], SEM_NONO, None)["resultado"], "incompleto")

    def test_atualiza_so_observacao_e_retry_nao_duplica_bloco(self):
        bloco = bloco_observacoes(1, 2, "Texto do Funil")
        for recebido in (SEM_NONO, COM_NONO):
            for cadastrado in MASCARAS:
                with self.subTest(recebido=recebido, cadastrado=cadastrado):
                    row = {"_row": 44, "WhatsApp": cadastrado, "Email": "ana@example.com",
                           "Nome": "Nome original", "Observação": "FR002", "Canal": "Organico Site"}
                    anterior = deepcopy(row)
                    operacao = preparar_escrita([row], snapshot(recebido), bloco)
                    self.assertEqual(operacao, {"row": 44, "observacoes": "FR002\n\n" + bloco})
                    self.assertEqual(row, anterior)
                    row["Observação"] = operacao["observacoes"]
                    self.assertIsNone(preparar_escrita([row], snapshot(recebido), bloco))

    def test_duas_linhas_com_variantes_nao_sao_escolhidas_arbitrariamente(self):
        rows = [{"_row": i, "WhatsApp": n, "Email": "ana@example.com", "Observação": "FR002"}
                for i, n in ((44, SEM_NONO), (45, COM_NONO))]
        for numero in (SEM_NONO, COM_NONO):
            with self.assertRaisesRegex(ErroFireAds, "Mais de uma linha"):
                preparar_escrita(rows, snapshot(numero), bloco_observacoes(1, 2, "Texto"))

    def test_variacao_nao_ignora_conflito_de_email(self):
        row = {"_row": 44, "WhatsApp": COM_NONO,
               "Email": "outra@example.com", "Observação": "FR002"}
        with self.assertRaisesRegex(ErroFireAds, "emails diferentes"):
            preparar_escrita([row], snapshot(), bloco_observacoes(1, 2, "Texto"))

    def test_numero_diferente_ddd_fixo_e_invalido_nao_geram_correspondencia(self):
        for outro in ("5575994111866", "5571994111867", "55994111866", "", None):
            self.assertEqual(localizar([{"WhatsApp": outro}], SEM_NONO, "WhatsApp"), [])
        for recebido, cadastrado in (("551134561234", "5511934561234"),
                                     ("5511934561234", "551134561234")):
            self.assertEqual(localizar([{"WhatsApp": cadastrado}], recebido, "WhatsApp"), [])
        for invalido in ("", None, "123", "+1 202 555 0123"):
            with self.assertRaises(ErroFireAds):
                localizar([], invalido, "WhatsApp")

    def test_novo_lead_preserva_numero_normalizado_sem_inventar_nono(self):
        for recebido in (SEM_NONO, COM_NONO):
            operacao = preparar_escrita([], snapshot(recebido), bloco_observacoes(1, 2, "Texto"))
            self.assertEqual(operacao["dados"]["WhatsApp"], recebido)

    def test_worker_serializa_mesmo_contato_com_e_sem_nono(self):
        chaves = []
        for recebido in (SEM_NONO, COM_NONO):
            envio = {"snapshot": snapshot(recebido), "integracao": 1, "conversa": 2, "tentativa": 1}
            cursor = FakeCursor(fetchone_result=(True,))
            conn = FakeConn(cursor)
            api = Mock()
            api.consultar.return_value = {"headers": ["Nome", "Email", "WhatsApp", "Observação"], "rows": []}
            with patch("workers.worker_funil.fireads.ClienteFireAds", return_value=api), \
                    patch("workers.worker_funil.fireads.conferir_posse"), \
                    patch("workers.worker_funil.fireads.concluir"), \
                    patch("workers.worker_funil.fireads.reagendar") as reagendar:
                self.assertTrue(processar(envio, conn, cursor))
                reagendar.assert_not_called()
            self.assertEqual(cursor.calls[0][0], "SELECT pg_try_advisory_lock(%s)")
            chaves.append(cursor.calls[0][1])
            self.assertEqual(cursor.calls[-1][1], chaves[-1])
        self.assertEqual(chaves[0], chaves[1])

    def test_utilitario_e_producao_compartilham_a_busca(self):
        from utilitarios.fireAds.test_Dash import gerar_formatos_dashboard, localizar_registros

        rows = [{"WhatsApp": "(71) 99411-1866"}]
        for numero in MASCARAS:
            self.assertEqual(gerar_formatos_dashboard(numero), list(formatos_telefone(numero)))
            self.assertEqual(localizar_registros(rows, numero), localizar(rows, numero, "WhatsApp"))
            self.assertEqual(telefone(numero), formatos_telefone(numero)[0])


if __name__ == "__main__":
    unittest.main()
