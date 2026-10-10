"""Latência simulada sem HTTP real: espera, retomada e limites de concorrência."""

from concurrent.futures import Future
from threading import Event, current_thread
import unittest
from unittest.mock import Mock, patch

from core.integrations.fireads.cliente import ClienteFireAds
from core.integrations.fireads.contrato import ErroFireAds
from tests.helpers import FakeConn, FakeCursor
from tests.unit.test_fireads import GOOGLE, NUMERO
from workers.worker_flow import fireads
from workers.worker_flow.suporte.consultas_fireads import (
    ConsultaFireAdsPendente,
    ConsultasFireAdsEmAndamento,
)


class ConsultaHTTPTests(unittest.TestCase):
    def test_300_segundos_sao_compartilhados_entre_abas_e_redirects(self):
        session = Mock()
        resposta = Mock(status_code=200)
        resposta.json.side_effect = [
            {"success": True, "data": {"aba": aba, "headers": [], "rows": []}}
            for aba in ("google", "meta")
        ]
        redirect = Mock(status_code=302, headers={
            "Location": "https://script.googleusercontent.com/macros/echo?teste=1",
        })
        with patch("core.integrations.fireads.cliente.time.monotonic", return_value=0) as tempo:
            cliente = ClienteFireAds(
                "https://script.google.com/macros/s/teste/exec", segundos=300,
                timeout_leitura=None, session=session,
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
            self.assertEqual([c.kwargs["timeout"][1] for c in session.request.call_args_list], [300, 235, 200])
            tempo.return_value = 300
            with self.assertRaises(ErroFireAds):
                cliente.consultar("meta")
            self.assertEqual(session.request.call_count, 3)

    def test_resposta_tardia_nao_e_aceita_mesmo_que_http_seja_200(self):
        session = Mock()
        with patch("core.integrations.fireads.cliente.time.monotonic", return_value=0) as tempo:
            cliente = ClienteFireAds(
                "https://script.google.com/macros/s/teste/exec", segundos=300,
                timeout_leitura=None, session=session,
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
        redirect = Mock(status_code=302, headers={
            "Location": "https://script.googleusercontent.com/macros/echo?teste=1",
        })
        session.request.side_effect = [redirect, resposta, redirect, resposta]
        with patch("core.integrations.fireads.cliente.time.monotonic") as relogio:
            relogio.return_value = 0
            cliente = ClienteFireAds(
                "https://script.google.com/macros/s/teste/exec",
                segundos=None, session=session,
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
        with patch("core.integrations.fireads.cliente.time.monotonic", return_value=0) as tempo:
            cliente = ClienteFireAds(
                "https://script.google.com/macros/s/teste/exec",
                segundos=40, session=session,
            )
            tempo.return_value = 41
            with self.assertRaises(ErroFireAds):
                cliente.enviar("geral", dados={})
        session.request.assert_not_called()


class ConsultasEmAndamentoTests(unittest.TestCase):
    def test_leitura_lenta_e_reutilizada_sem_prender_chamador(self):
        pool = ConsultasFireAdsEmAndamento(simultaneas=2, resultados=2)
        liberar, iniciou = Event(), Event()

        def lenta():
            self.assertTrue(current_thread().daemon)
            iniciou.set()
            liberar.wait(3)
            return {"resultado": "importado"}

        consulta = Mock(side_effect=lenta)
        futuro = pool.obter("conversa1", consulta)
        try:
            self.assertTrue(iniciou.wait(2))
            for _ in range(5):
                self.assertIs(pool.obter("conversa1", consulta), futuro)
                self.assertFalse(futuro.done())
            outra = pool.obter("conversa2", lambda: "ausente")
            self.assertEqual(outra.result(timeout=2), "ausente")
        finally:
            liberar.set()
            self.assertEqual(futuro.result(timeout=2)["resultado"], "importado")
        consulta.assert_called_once()
        self.assertIs(pool.obter("conversa1", consulta), futuro)
        pool.confirmar("conversa1", futuro)
        novo = pool.obter("conversa1", lambda: "nova leitura")
        self.assertEqual(novo.result(timeout=2), "nova leitura")

    def test_capacidade_reagenda_sem_descartar_leitura_ativa(self):
        pool = ConsultasFireAdsEmAndamento(simultaneas=1, resultados=1)
        liberar = Event()
        futuro = pool.obter("primeira", lambda: liberar.wait(3))
        try:
            with self.assertRaises(ConsultaFireAdsPendente):
                pool.obter("segunda", lambda: None)
            self.assertIs(pool.obter("primeira", lambda: None), futuro)
        finally:
            liberar.set()
            futuro.result(timeout=2)
        # Um resultado abandonado pode sair da memória; uma leitura ativa não.
        segundo = pool.obter("segunda", lambda: "ok")
        self.assertEqual(segundo.result(timeout=2), "ok")

    def test_excecao_na_tarefa_nao_fica_pendente_para_sempre(self):
        pool = ConsultasFireAdsEmAndamento()
        futuro = pool.obter("teste", Mock(side_effect=ValueError("falha")))
        with self.assertRaises(ValueError):
            futuro.result(timeout=2)


class AberturaPendenteTests(unittest.TestCase):
    def test_formularios_repetidos_iguais_nao_impedem_importacao_sem_fuso(self):
        for origem, rows in (
            ("google", [dict(GOOGLE, _row=44), dict(GOOGLE, _row=45)]),
            ("meta", [{"full_name": "Ana Paula Silva", "email": "ana@example.com",
                       "para_quem": "para_mim", "phone_number": NUMERO,
                       "created_time": "2026-10-09T00:00:00Z", "id": id_}
                      for id_ in (1, 2)]),
        ):
            with self.subTest(origem=origem):
                google, meta = (rows, []) if origem == "google" else ([], rows)
                resultado = fireads.interpretar(google, meta, NUMERO, None)
                self.assertEqual(resultado["resultado"], "importado")
                self.assertEqual(resultado["origem"], origem)

    def test_registros_com_dados_ou_datas_diferentes_continuam_exigindo_desempate(self):
        for diferenca in (
            {"Nome": "Maria Silva"}, {"Email": "outro@example.com"},
            {"Perfil/Faixa": "Para meu pai/mãe"}, {"Data/Hora": "02/10/2026 12:00"},
        ):
            with self.subTest(diferenca=diferenca):
                resultado = fireads.interpretar([GOOGLE, dict(GOOGLE, **diferenca)], [], NUMERO, None)
                self.assertEqual(resultado["resultado"], "ambiguidade")

    def test_nao_grava_organico_enquanto_pendente_e_importa_apos_retomada(self):
        abertura = {
            "contexto": None, "etapa": None, "aplicavel": True,
            "id_integracao": 1, "id_cliente": 4,
            "url": "https://script.google.com/macros/s/teste/exec",
            "aba_google": "google", "aba_meta": "meta", "fuso": None,
        }
        contexto = {"conversa": {"id_conversa": 2, "id_etapa_atual": None}}
        mensagem = {"id_mensagem": 7, "retry_count": 1, "cliente_telefone": NUMERO}
        conn, cursor, futuro = FakeConn(), FakeCursor(), Future()
        pool = Mock()
        pool.obter.return_value = futuro
        with (
            patch.object(fireads, "buscar_abertura", return_value=abertura),
            patch.object(fireads, "reservar_consulta", return_value=5),
            patch.object(fireads, "segundos_restantes_consulta", return_value=300),
            patch.object(fireads, "proteger_conversa"),
            patch.object(fireads, "proteger_mensagem_abertura") as proteger,
            patch.object(fireads, "importar_dados_abertura", return_value=True) as importar,
            patch.object(fireads, "concluir_consulta", side_effect=lambda a, c, i, d, cur: d) as concluir,
            patch.object(fireads, "consultas_em_andamento", pool),
        ):
            for _ in range(4):
                with self.assertRaises(ConsultaFireAdsPendente):
                    fireads.preparar_abertura(contexto, mensagem, 1, conn, cursor)
            concluir.assert_not_called()
            importar.assert_not_called()
            proteger.assert_not_called()
            futuro.set_result(fireads.interpretar([GOOGLE], [], NUMERO, None))
            resultado = fireads.preparar_abertura(contexto, mensagem, 5, conn, cursor)
            self.assertEqual(resultado["contexto_fireads"]["resultado"], "importado")
            importar.assert_called_once()
            proteger.assert_called_once_with(mensagem, cursor)
            concluir.assert_called_once()
            pool.confirmar.assert_called_once()

    def test_prazo_esgotado_grava_organico_sem_iniciar_ou_reaproveitar_http(self):
        abertura = {"contexto": None, "etapa": None, "aplicavel": True,
                    "id_integracao": 1, "url": "https://script.google.com/macros/s/teste/exec",
                    "aba_google": "google", "aba_meta": "meta", "fuso": None}
        with (
            patch.object(fireads, "buscar_abertura", return_value=abertura),
            patch.object(fireads, "reservar_consulta", return_value=5),
            patch.object(fireads, "segundos_restantes_consulta", return_value=0),
            patch.object(fireads, "proteger_conversa"),
            patch.object(fireads, "proteger_mensagem_abertura"),
            patch.object(fireads, "importar_dados_abertura") as importar,
            patch.object(fireads, "concluir_consulta", side_effect=lambda a, c, i, d, cur: d),
            patch.object(fireads, "consultas_em_andamento") as pool,
        ):
            resultado = fireads.preparar_abertura(
                {"conversa": {"id_conversa": 2, "id_etapa_atual": None}},
                {"cliente_telefone": NUMERO}, 1, FakeConn(), FakeCursor(),
            )
        self.assertEqual(resultado["contexto_fireads"]["origem"], "organico")
        self.assertEqual(resultado["contexto_fireads"]["motivo"], "tempo_limite_300s")
        pool.obter.assert_not_called()
        importar.assert_not_called()

    def test_consulta_usa_300_segundos_e_so_decide_apos_as_duas_fontes(self):
        api = Mock()
        api.consultar.side_effect = [
            {"headers": list(GOOGLE), "rows": [GOOGLE]},
            {"headers": ["full_name", "email", "phone_number", "para_quem"], "rows": []},
        ]
        with patch.object(fireads, "ClienteFireAds", return_value=api) as cliente:
            resultado = fireads.consultar_formularios({
                "url": "https://script.google.com/macros/s/teste/exec",
                "aba_google": "google", "aba_meta": "meta", "fuso": None,
            }, NUMERO, 2)
        self.assertEqual(resultado["resultado"], "importado")
        self.assertGreater(cliente.call_args.kwargs["segundos"], 299)
        self.assertLessEqual(cliente.call_args.kwargs["segundos"], 300)
        self.assertIsNone(cliente.call_args.kwargs["timeout_leitura"])
        self.assertEqual([c.args[0] for c in api.consultar.call_args_list], ["google", "meta"])
        api.close.assert_called_once()
