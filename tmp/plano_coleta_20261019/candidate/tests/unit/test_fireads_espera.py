"""Latência simulada sem HTTP real: espera, retomada e limites de concorrência."""

from tests.fixtures.fireads import como_aba_geral
import unittest
from unittest.mock import Mock, patch

from core.integrations.fireads.cliente import ClienteFireAds
from core.integrations.fireads.contrato import ErroFireAds, selecionar
from tests.helpers import FakeConn, FakeCursor
from tests.unit.test_fireads import GOOGLE, META, NUMERO
from workers.worker_flow import fireads
from workers.worker_flow.suporte.consultas_fireads import (
    ConsultaFireAdsPendente,
)


class ConsultaHTTPTests(unittest.TestCase):
    def test_300_segundos_sao_compartilhados_entre_abas_e_redirects(self):
        session = Mock()
        resposta = Mock(status_code=200)
        resposta.json.side_effect = [
            {"success": True, "data": {"aba": aba, "headers": [], "rows": []}}
            for aba in ("google", "meta")
        ]
        redirect = Mock(
            status_code=302,
            headers={
                "Location": "https://script.googleusercontent.com/macros/echo?teste=1",
            },
        )
        with patch(
            "core.integrations.fireads.cliente.time.monotonic", return_value=0
        ) as tempo:
            cliente = ClienteFireAds(
                "https://script.google.com/macros/s/teste/exec",
                segundos=300,
                timeout_leitura=None,
                session=session,
            )

            def responder(*_args, **_kwargs):
                if session.request.call_count == 1:
                    tempo.return_value = 65
                    return redirect
                if session.request.call_count == 2:
                    tempo.return_value = 100
                else:
                    tempo.return_value = 299
                return resposta

            session.request.side_effect = responder
            cliente.consultar("google")
            cliente.consultar("meta")
            self.assertEqual(
                [c.kwargs["timeout"][1] for c in session.request.call_args_list],
                [300, 235, 200],
            )
            tempo.return_value = 300
            with self.assertRaises(ErroFireAds):
                cliente.consultar("meta")
            self.assertEqual(session.request.call_count, 3)

    def test_resposta_tardia_nao_e_aceita_mesmo_que_http_seja_200(self):
        session = Mock()
        with patch(
            "core.integrations.fireads.cliente.time.monotonic", return_value=0
        ) as tempo:
            cliente = ClienteFireAds(
                "https://script.google.com/macros/s/teste/exec",
                segundos=300,
                timeout_leitura=None,
                session=session,
            )

            def atrasar(*_args, **_kwargs):
                tempo.return_value = 301
                return Mock(status_code=200)

            session.request.side_effect = atrasar
            with self.assertRaises(ErroFireAds):
                cliente.consultar("google")

    def test_consulta_sem_prazo_aceita_duas_abas_e_redirect_apos_120_segundos(self):
        session = Mock()
        resposta = Mock(status_code=200)
        resposta.json.side_effect = [
            {"success": True, "data": {"aba": aba, "headers": [], "rows": []}}
            for aba in ("google", "meta")
        ]
        redirect = Mock(
            status_code=302,
            headers={
                "Location": "https://script.googleusercontent.com/macros/echo?teste=1",
            },
        )
        session.request.side_effect = [redirect, resposta, redirect, resposta]
        with patch("core.integrations.fireads.cliente.time.monotonic") as relogio:
            relogio.return_value = 0
            cliente = ClienteFireAds(
                "https://script.google.com/macros/s/teste/exec",
                segundos=None,
                session=session,
            )
            relogio.return_value = 300
            cliente.consultar("google")
            relogio.return_value = 600
            cliente.consultar("meta")
        self.assertEqual(session.request.call_count, 4)
        for chamada in session.request.call_args_list:
            self.assertIsNone(chamada.kwargs["timeout"])
            self.assertEqual(chamada.args[0], "GET")

    def test_orcamento_finito_das_escritas_permanece(self):
        session = Mock()
        with patch(
            "core.integrations.fireads.cliente.time.monotonic", return_value=0
        ) as tempo:
            cliente = ClienteFireAds(
                "https://script.google.com/macros/s/teste/exec",
                segundos=40,
                session=session,
            )
            tempo.return_value = 41
            with self.assertRaises(ErroFireAds):
                cliente.enviar("geral", dados={})
        session.request.assert_not_called()


class DecisaoConsultaTests(unittest.TestCase):
    def test_formularios_repetidos_iguais_nao_impedem_importacao_sem_fuso(self):
        for origem, rows in (
            ("google", [dict(GOOGLE, _row=44), dict(GOOGLE, _row=45)]),
            (
                "meta",
                [
                    {
                        "full_name": "Ana Paula Silva",
                        "email": "ana@example.com",
                        "para_quem": "para_mim",
                        "phone_number": NUMERO,
                        "created_time": "2026-10-09T00:00:00Z",
                        "id": id_,
                    }
                    for id_ in (1, 2)
                ],
            ),
        ):
            with self.subTest(origem=origem):
                google, meta = (rows, []) if origem == "google" else ([], rows)
                resultado = fireads.interpretar(como_aba_geral(google, meta), NUMERO, None)
                self.assertEqual(resultado["resultado"], "importado")
                self.assertEqual(resultado["origem"], origem)

    def test_ultimo_formulario_substitui_dados_antigos_sem_ambiguidade(self):
        for diferenca in (
            {"Nome": "Maria Silva"},
            {"Email": "outro@example.com"},
            {"Perfil/Faixa": "Para meu pai/mãe"},
        ):
            with self.subTest(diferenca=diferenca):
                ultimo = dict(GOOGLE, _row=46, **diferenca)
                self.assertIs(
                    selecionar([ultimo, dict(GOOGLE, _row=44)], [], NUMERO)[1],
                    ultimo,
                )
                resultado = fireads.interpretar(como_aba_geral([dict(GOOGLE, _row=44), ultimo], []), NUMERO, None)
                self.assertEqual(resultado["resultado"], "importado")

    def test_caso_tres_formularios_meia_noite_usa_linha_46_titular(self):
        rows = [dict(GOOGLE, _row=n, **{
            "Data/Hora": "09/10/2026 00:00",
            "Perfil/Faixa": "Para mim" if n == 46 else "Para meu pai/mãe",
        }) for n in (44, 45, 46)]
        resultado = fireads.interpretar(como_aba_geral(rows, []), NUMERO, None)
        self.assertEqual(resultado["resultado"], "importado")
        self.assertFalse(resultado["status_dependente"])

    def test_data_prevalece_sobre_linha_e_ordem_em_ambas_as_abas(self):
        for origem, base, campo in (
            ("google", GOOGLE, "Data/Hora"), ("meta", META, "created_time"),
        ):
            with self.subTest(origem=origem):
                novo = dict(base, _row=2, **{campo: "2026-10-09T18:00:00Z"})
                antigo = dict(base, _row=100, **{campo: "2026-10-08T18:00:00Z"})
                rows = [novo, antigo]
                google, meta = (rows, []) if origem == "google" else ([], rows)
                self.assertIs(selecionar(google, meta, NUMERO)[1], novo)

    def test_mais_recente_entre_abas_com_varias_inscricoes(self):
        for vencedor in ("google", "meta"):
            with self.subTest(vencedor=vencedor):
                google = [dict(GOOGLE, **{"Data/Hora": f"0{dia}/10/2026 12:00"})
                          for dia in (1, 2, 9 if vencedor == "google" else 3)]
                meta = [dict(META, created_time=f"2026-10-0{dia}T15:00:00Z")
                        for dia in (1, 2, 9 if vencedor == "meta" else 3)]
                self.assertEqual(selecionar(google, meta, NUMERO)[0], vencedor)

    def test_variante_sem_nono_digito_mais_nova_tambem_participa(self):
        novo = dict(GOOGLE, WhatsApp=NUMERO[:4] + NUMERO[5:],
                    **{"Data/Hora": "09/10/2026 12:00"})
        self.assertIs(selecionar([GOOGLE, novo], [], NUMERO)[1], novo)

    def test_empate_meta_usa_linha_sem_inferir_cronologia_do_id(self):
        novo = dict(META, _row=46, id="1", para_quem="para_mim")
        antigo = dict(META, _row=44, id="999999999")
        resultado = fireads.interpretar(como_aba_geral([], [novo, antigo]), NUMERO, None)
        self.assertFalse(resultado["status_dependente"])

    def test_datas_invalidas_e_linhas_ausentes_usam_ultima_posicao(self):
        antigo = dict(GOOGLE, **{"Data/Hora": "invalida"})
        novo = dict(antigo, Nome="Maria Silva")
        self.assertIs(selecionar([antigo, novo], [], NUMERO)[1], novo)
        self.assertIs(selecionar([GOOGLE, novo], [], NUMERO)[1], GOOGLE)

    def test_empate_entre_abas_usa_maior_linha_sem_prioridade_por_origem(self):
        for linha_google, linha_meta, origem in (
            (46, 44, "google"),
            (44, 46, "meta"),
        ):
            with self.subTest(origem=origem):
                google = dict(GOOGLE, _row=linha_google)
                meta = dict(META, _row=linha_meta, created_time="2026-10-01T15:00:00Z")
                escolhido = selecionar([google], [meta], NUMERO)
                self.assertEqual(escolhido[0], origem)
                self.assertIs(escolhido[1], google if origem == "google" else meta)
