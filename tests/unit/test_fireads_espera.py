"""Latência simulada sem HTTP real: espera, retomada e limites de concorrência."""

import unittest
from unittest.mock import Mock, patch

from core.integrations.fireads.cliente import ClienteFireAds
from core.integrations.fireads.contrato import ErroFireAds
from tests.helpers import FakeConn, FakeCursor
from tests.unit.test_fireads import GOOGLE, NUMERO
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
                resultado = fireads.interpretar(google, meta, NUMERO, None)
                self.assertEqual(resultado["resultado"], "importado")
                self.assertEqual(resultado["origem"], origem)

    def test_registros_com_dados_ou_datas_diferentes_continuam_exigindo_desempate(self):
        for diferenca in (
            {"Nome": "Maria Silva"},
            {"Email": "outro@example.com"},
            {"Perfil/Faixa": "Para meu pai/mãe"},
            {"Data/Hora": "02/10/2026 12:00"},
        ):
            with self.subTest(diferenca=diferenca):
                resultado = fireads.interpretar(
                    [GOOGLE, dict(GOOGLE, **diferenca)], [], NUMERO, None
                )
                self.assertEqual(resultado["resultado"], "ambiguidade")
