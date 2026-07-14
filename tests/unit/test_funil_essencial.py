import unittest
from unittest.mock import patch

from core.integrations.funil.cliente import (
    enviar_oportunidade,
    montar_url_envio,
)
from core.integrations.funil.exceptions import OportunidadeRejeitadaFunil
from core.integrations.funil.oportunidades import (
    montar_dados_lead_teste,
    montar_payload_oportunidade,
)
from tests.helpers import FakeConn, FakeCursor
from workers.worker_funil.exceptions import BancoFalhouAposEnvioFunil
from workers.worker_funil.funil_worker import executar_ciclo_funil
from workers.worker_funil.processamento import processar_envio_funil


class _FakeResponse:
    status_code = 200

    def __init__(self, corpo):
        self.corpo = corpo

    def raise_for_status(self):
        return None

    def json(self):
        return self.corpo


class _FakeSession:
    def __init__(self, corpo):
        self.corpo = corpo
        self.calls = []

    def post(self, url, json, timeout):
        self.calls.append((url, json, timeout))
        return _FakeResponse(self.corpo)


class FunilEssencialTests(unittest.TestCase):
    def test_payload_dependente_preenche_contato_e_observacoes(self):
        dados = montar_dados_lead_teste()
        dados["id_conversa"] = 123

        oportunidade = montar_payload_oportunidade(dados)["oportunidades"][0]
        personalizados = {
            item["titulo"]: item["valor"]
            for item in oportunidade["personalizados"]
        }

        self.assertEqual(oportunidade["titulo"], "Chatbot Lead [C123]")
        self.assertEqual(oportunidade["contato"]["nome"], dados["nome_cliente"])
        self.assertEqual(
            oportunidade["contato"]["telefone1"],
            dados["telefone_cliente"],
        )
        self.assertEqual(
            oportunidade["contato"]["email"],
            dados["email_cliente"],
        )
        self.assertEqual(personalizados["Origem do lead"], "Meta Chatbot")
        self.assertIn("Nome do dependente: Enzo Teste", personalizados["Observações"])
        self.assertIn("Às vezes: 3", personalizados["Observações"])

    def test_payload_titular_usa_somente_idade_do_cliente(self):
        dados = montar_dados_lead_teste()
        dados.update(
            {
                "status_dependente": False,
                "idade_cliente": 25,
                "nome_dependente": None,
                "idade_dependente": None,
            }
        )

        oportunidade = montar_payload_oportunidade(dados)["oportunidades"][0]
        observacoes = oportunidade["personalizados"][0]["valor"]

        self.assertIn("Idade do cliente: 25", observacoes)
        self.assertNotIn("Nome do dependente", observacoes)

    def test_payload_rejeita_triagem_incompleta(self):
        dados = montar_dados_lead_teste()
        dados["triagem_total"] = 5

        with self.assertRaisesRegex(ValueError, "exatamente 6"):
            montar_payload_oportunidade(dados)

    def test_cliente_preserva_widget_e_forca_canal(self):
        url = montar_url_envio(
            "https://leads.example/api/?W=ABC",
            "113340",
        )
        self.assertEqual(
            url,
            "https://leads.example/api/?W=ABC&ForceCodeChannel=113340",
        )

        session = _FakeSession({"response": "success"})
        resultado = enviar_oportunidade(
            link_api_carrossel="https://leads.example/api/?W=ABC",
            codigo_canal_venda="113340",
            payload={"oportunidades": []},
            timeout=(10, 30),
            session=session,
        )
        self.assertEqual(resultado["status_http"], 200)

    def test_cliente_nao_confunde_http_200_com_sucesso_logico(self):
        session = _FakeSession(
            {"response": "failure", "message": "payload inválido"}
        )

        with self.assertRaises(OportunidadeRejeitadaFunil):
            enviar_oportunidade(
                link_api_carrossel="https://leads.example/api/?W=ABC",
                codigo_canal_venda="113340",
                payload={"oportunidades": []},
                timeout=(10, 30),
                session=session,
            )

    @patch("workers.worker_funil.processamento.buscar_dados_lead_funil")
    @patch("workers.worker_funil.processamento.buscar_integracao_funil_por_unidade")
    @patch("workers.worker_funil.processamento.enviar_oportunidade")
    @patch("workers.worker_funil.processamento.marcar_envio_como_concluido")
    def test_falha_local_apos_sucesso_externo_preserva_janela_para_reconciliar(
        self,
        marcar_mock,
        enviar_mock,
        integracao_mock,
        dados_mock,
    ):
        dados_mock.return_value = montar_dados_lead_teste()
        integracao_mock.return_value = {
            "link_api_carrossel": "https://leads.example/api/?W=ABC",
            "codigo_canal_venda": "113340",
            "integracao_ativa": True,
            "widget_ativo": True,
        }
        enviar_mock.return_value = {
            "status_http": 200,
            "resposta": {"response": "success"},
        }
        marcar_mock.side_effect = RuntimeError("banco indisponível")
        conn = FakeConn(FakeCursor())
        envio = {"id_funil_envio": 7, "id_conversa": 123, "retry_count": 1}

        with self.assertRaises(BancoFalhouAposEnvioFunil):
            processar_envio_funil(envio, conn, conn.cursor_obj)

        self.assertEqual(conn.commits, 1)
        self.assertEqual(conn.rollbacks, 1)

    @patch("workers.worker_funil.flow_worker.get_conn")
    @patch("workers.worker_funil.flow_worker.sincronizar_envios_elegiveis")
    @patch("workers.worker_funil.flow_worker.reivindicar_proximo_envio")
    @patch("workers.worker_funil.flow_worker.processar_envio_funil")
    def test_ciclo_continua_depois_de_falha_individual(
        self,
        processar_mock,
        reivindicar_mock,
        sincronizar_mock,
        get_conn_mock,
    ):
        cursor = FakeCursor()
        cursor.close = lambda: None
        conn = FakeConn(cursor)
        get_conn_mock.return_value = conn
        sincronizar_mock.return_value = 2
        reivindicar_mock.side_effect = [
            {"id_funil_envio": 1, "id_conversa": 101, "retry_count": 1},
            {"id_funil_envio": 2, "id_conversa": 102, "retry_count": 1},
            None,
        ]
        processar_mock.side_effect = [False, True]

        resumo = executar_ciclo_funil()

        self.assertEqual(
            resumo,
            {
                "materializados": 2,
                "processados": 2,
                "enviados": 1,
                "falhas": 1,
            },
        )
        self.assertEqual(processar_mock.call_count, 2)


if __name__ == "__main__":
    unittest.main()
