import unittest
from unittest.mock import call, patch

from core.integrations.funil.cliente import (
    enviar_oportunidade,
    montar_url_envio,
)
from core.integrations.funil.exceptions import OportunidadeRejeitadaFunil
from core.integrations.funil.oportunidades import (
    montar_dados_lead_teste,
    montar_payload_oportunidade,
)
from core.repositories.funil.envios import (
    reivindicar_proximo_envio,
    sincronizar_envios_elegiveis,
)
from core.repositories.funil.leads import buscar_dados_lead_funil
from tests.helpers import FakeConn, FakeCursor
from workers.worker_funil import funil_worker as executor_funil
from workers.worker_funil import iniciar_worker_funil as supervisor_funil
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
    def test_worker_registra_lote_e_aguarda_trinta_minutos(self):
        resumo = {
            "materializados": 2,
            "processados": 2,
            "enviados": 2,
            "falhas": 0,
        }

        with (
            patch.object(
                executor_funil,
                "executar_ciclo_funil",
                side_effect=[resumo, KeyboardInterrupt],
            ),
            patch.object(executor_funil.time, "sleep") as sleep_mock,
            patch("builtins.print") as print_mock,
            patch.object(executor_funil.logger, "info") as log_info,
        ):
            with self.assertRaises(KeyboardInterrupt):
                executor_funil.funil_worker()

        self.assertEqual(executor_funil.FUNIL_INTERVALO_SEGUNDOS, 1800)
        self.assertEqual(executor_funil.FUNIL_LIMITE_POR_CICLO, 100)
        sleep_mock.assert_called_once_with(1800)
        print_mock.assert_called_once_with("PROXIMO CICLO EM 30 MINUTOS")
        self.assertIn(
            call(
                "funil_worker_iniciado | intervalo_segundos=%s "
                "limite_por_ciclo=%s",
                1800,
                100,
            ),
            log_info.call_args_list,
        )
        self.assertIn(
            call(
                "funil_ciclo_concluido | acao=aguardar_proximo "
                "materializados=%s processados=%s enviados=%s falhas=%s "
                "limite_por_ciclo=%s aguardar=%ss",
                2,
                2,
                2,
                0,
                100,
                1800,
            ),
            log_info.call_args_list,
        )

    def test_materializacao_exclui_conversas_ja_enfileiradas_antes_do_limite(self):
        cursor = FakeCursor()

        sincronizar_envios_elegiveis(cursor, limite=100)

        sql, parametros = cursor.calls[0]
        self.assertIn("NOT EXISTS", sql)
        self.assertIn(
            "fe_existente.id_conversa = c.id_conversa",
            sql,
        )
        self.assertIn("e.elegivel_funil = TRUE", sql)
        self.assertIn("c.lead_no_funil IS NOT TRUE", sql)
        self.assertEqual(parametros, (100,))

    def test_reivindicacao_prioriza_menor_numero_de_tentativas(self):
        cursor = FakeCursor()

        reivindicar_proximo_envio(cursor, lease_segundos=900)

        sql, parametros = cursor.calls[0]
        ordenacao = sql.split("ORDER BY", 1)[1].split("FOR UPDATE", 1)[0]
        posicao_tentativas = ordenacao.index("fe.attempt_count ASC")
        posicao_tempo = ordenacao.index("CASE")
        posicao_id = ordenacao.index("fe.id_funil_envio ASC")

        self.assertLess(posicao_tentativas, posicao_tempo)
        self.assertLess(posicao_tempo, posicao_id)
        self.assertIn("fe.next_attempt_at", ordenacao)
        self.assertIn("fe.processing_started_at", ordenacao)
        self.assertEqual(parametros, (900,))

    def test_payload_dependente_preenche_contato_e_observacoes(self):
        dados = montar_dados_lead_teste()
        dados["id_conversa"] = 123

        oportunidade = montar_payload_oportunidade(dados)["oportunidades"][0]
        personalizados = {
            item["titulo"]: item["valor"]
            for item in oportunidade["personalizados"]
        }

        self.assertEqual(
            oportunidade["titulo"],
            "Chatbot Lead Supera Santo Antônio de Jesus",
        )
        self.assertEqual(
            oportunidade["empresa"]["nome"],
            "Edcarlos Teste - Não contatar | Enzo Teste | 12",
        )
        self.assertEqual(oportunidade["contato"]["nome"], dados["nome_cliente"])
        self.assertEqual(
            oportunidade["contato"]["telefone1"],
            "5571994111866",
        )
        self.assertEqual(
            oportunidade["contato"]["email"],
            dados["email_cliente"],
        )
        self.assertEqual(personalizados["Origem do lead"], "Meta Chatbot")
        self.assertIn("Nome do dependente: Enzo Teste", personalizados["Observações"])
        self.assertIn(
            "- Profissão: Engenheiro",
            personalizados["Observações"],
        )
        self.assertIn("Às vezes: 3", personalizados["Observações"])
        self.assertLess(
            personalizados["Observações"].index(
                "- Idade do dependente: 12"
            ),
            personalizados["Observações"].index(
                "- Profissão: Engenheiro"
            ),
        )
        self.assertLess(
            personalizados["Observações"].index(
                "- Profissão: Engenheiro"
            ),
            personalizados["Observações"].index(
                "Resultado do teste de triagem"
            ),
        )

    def test_snapshot_funil_inclui_profissao_da_conversa(self):
        cursor = FakeCursor(
            fetchone_result=(
                123,
                1,
                "Supera Teste",
                False,
                "Maria",
                "5571999999999",
                "maria@example.com",
                30,
                "Analista financeira",
                None,
                None,
                6,
                1,
                2,
                3,
                0,
            )
        )

        dados = buscar_dados_lead_funil(123, cursor)

        sql, parametros = cursor.calls[0]
        self.assertIn("c.profissao", sql)
        self.assertEqual(parametros, (123,))
        self.assertEqual(dados["profissao"], "Analista financeira")

    def test_payload_legado_exibe_profissao_nao_informada(self):
        dados = montar_dados_lead_teste()
        dados["profissao"] = None

        oportunidade = montar_payload_oportunidade(dados)["oportunidades"][0]
        observacoes = oportunidade["personalizados"][0]["valor"]

        self.assertIn("- Profissão: Não informada", observacoes)
        self.assertLess(
            observacoes.index("- Profissão: Não informada"),
            observacoes.index("Resultado do teste de triagem"),
        )

    def test_payload_adiciona_nono_digito_ao_telefone_brasileiro(self):
        dados = montar_dados_lead_teste()
        dados["telefone_cliente"] = "557587006911"

        oportunidade = montar_payload_oportunidade(dados)["oportunidades"][0]

        self.assertEqual(
            oportunidade["contato"]["telefone1"],
            "5575987006911",
        )

    def test_payload_internacional_omite_telefone1_e_avisa_nas_observacoes(self):
        dados = montar_dados_lead_teste()
        dados["telefone_cliente"] = "351912345678"

        oportunidade = montar_payload_oportunidade(dados)["oportunidades"][0]
        observacoes = oportunidade["personalizados"][0]["valor"]

        self.assertEqual(oportunidade["contato"]["telefone1"], "")
        self.assertIn("351912345678", observacoes)
        self.assertIn(
            "número internacional fora do padrão brasileiro",
            observacoes,
        )
        self.assertLess(
            observacoes.index("- Idade do dependente: 12"),
            observacoes.index(
                "O cliente possui um número internacional fora do padrão brasileiro"
            ),
        )
        self.assertLess(
            observacoes.index(
                "O cliente possui um número internacional fora do padrão brasileiro"
            ),
            observacoes.index("Resultado do teste de triagem"),
        )
        self.assertIn(
            "- Idade do dependente: 12\n\n"
            "O cliente possui um número internacional fora do padrão brasileiro, "
            "por isso o campo Telefone 1 não foi preenchido.\n\n"
            "- Profissão: Engenheiro\n\n"
            "Resultado do teste de triagem",
            observacoes,
        )

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

        self.assertEqual(
            oportunidade["titulo"],
            "Chatbot Lead Supera Santo Antônio de Jesus",
        )
        self.assertEqual(
            oportunidade["empresa"]["nome"],
            "Edcarlos Teste - Não contatar | 25",
        )
        self.assertIn("Idade do cliente: 25", observacoes)
        self.assertNotIn("Nome do dependente", observacoes)

    def test_payload_rejeita_triagem_incompleta(self):
        dados = montar_dados_lead_teste()
        dados["triagem_total"] = 5

        with self.assertRaisesRegex(ValueError, "exatamente 6"):
            montar_payload_oportunidade(dados)

    def test_payload_nao_inclui_dados_da_pesquisa_de_satisfacao(self):
        dados = montar_dados_lead_teste()
        dados["nota_satisfacao"] = 5
        dados["comentario_satisfacao"] = "Comentário interno da pesquisa"

        payload_serializado = repr(montar_payload_oportunidade(dados))

        self.assertNotIn("nota_satisfacao", payload_serializado)
        self.assertNotIn("comentario_satisfacao", payload_serializado)
        self.assertNotIn("Comentário interno da pesquisa", payload_serializado)

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
        envio = {"id_funil_envio": 7, "id_conversa": 123, "attempt_count": 1}

        with self.assertRaises(BancoFalhouAposEnvioFunil):
            processar_envio_funil(envio, conn, conn.cursor_obj)

        self.assertEqual(conn.commits, 1)
        self.assertEqual(conn.rollbacks, 1)

    @patch("workers.worker_funil.funil_worker.get_conn")
    @patch("workers.worker_funil.funil_worker.sincronizar_envios_elegiveis")
    @patch("workers.worker_funil.funil_worker.reivindicar_proximo_envio")
    @patch("workers.worker_funil.funil_worker.processar_envio_funil")
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
            {"id_funil_envio": 1, "id_conversa": 101, "attempt_count": 1},
            {"id_funil_envio": 2, "id_conversa": 102, "attempt_count": 1},
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

    def test_supervisor_reinicia_ciclo_apos_falha_global(self):
        with (
            patch.object(supervisor_funil, "FUNIL_WORKER_ENABLED", True),
            patch.object(supervisor_funil, "validar_configuracao_funil"),
            patch.object(
                supervisor_funil,
                "funil_worker",
                side_effect=[RuntimeError("banco indisponível"), KeyboardInterrupt],
            ) as worker_mock,
            patch.object(supervisor_funil.time, "sleep") as sleep_mock,
            patch.object(supervisor_funil.logger, "exception"),
        ):
            with self.assertRaises(KeyboardInterrupt):
                supervisor_funil.iniciar_worker_funil()

        self.assertEqual(worker_mock.call_count, 2)
        sleep_mock.assert_called_once_with(5)

    def test_funil_worker_recupera_banco_com_backoff_linear(self):
        erro_banco = executor_funil.psycopg.OperationalError(
            "banco indisponivel"
        )

        with (
            patch.object(
                executor_funil,
                "executar_ciclo_funil",
                side_effect=[erro_banco, KeyboardInterrupt],
            ) as ciclo_mock,
            patch.object(
                executor_funil,
                "handle_erro_conexao",
                return_value=10,
            ) as retry_mock,
        ):
            with self.assertRaises(KeyboardInterrupt):
                executor_funil.funil_worker()

        self.assertEqual(ciclo_mock.call_count, 2)
        retry_mock.assert_called_once_with(
            erro_banco,
            5,
            incremento_retry=5,
        )


if __name__ == "__main__":
    unittest.main()
