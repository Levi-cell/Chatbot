"""PyWa real e transporte simulado: nenhum acesso à Meta, RDS ou Redis."""

import json
import unittest
from contextlib import ExitStack
from functools import partial
from unittest.mock import patch

import httpx
from pywa import WhatsApp

from core.integrations.whatsapp.pywa_functions import cliente, digitacao
from tests.helpers import FakeConn, FakeCursor
from tests.unit import test_worker_flow_runtime as runtime
from workers.worker_consulta_dash import consulta_worker
from workers.worker_flow.response_flow.flow_sender import flow_sender
from workers.worker_flow.response_flow.retomada_followup import enviar_retorno_followup


PHONE_ID = "123456"
WAMID = "wamid.cliente.7"
TELEFONE = "5571999999999"


class HTTPMetaSimulada:
    def preparar_http(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.requisicoes = []
        self.eventos = []
        self.resposta_indicador = {"success": True}
        self.falha_indicador = None
        self.status_indicador = 200
        self.ao_indicar = None
        self.sessoes = []
        self.transporte = self.stack.enter_context(patch.object(
            digitacao.httpx, "HTTPTransport",
            side_effect=lambda **_: httpx.MockTransport(self.responder),
        ))
        self.stack.enter_context(patch.object(
            cliente, "WhatsApp", side_effect=self.criar_cliente,
        ))

    def criar_cliente(self, **kwargs):
        if "session" not in kwargs:
            sessao = httpx.Client(
                timeout=30.0, transport=httpx.MockTransport(self.responder),
            )
            self.stack.callback(sessao.close)
            kwargs["session"] = sessao
        self.sessoes.append(kwargs["session"])
        return WhatsApp(**kwargs)

    def responder(self, request):
        self.requisicoes.append(request)
        payload = json.loads(request.content)
        if "typing_indicator" in payload:
            self.eventos.append("digitacao")
            if self.ao_indicar:
                self.ao_indicar()
            if self.falha_indicador:
                raise self.falha_indicador
            return httpx.Response(self.status_indicador, json=self.resposta_indicador)
        self.eventos.append("resposta")
        return httpx.Response(200, json={
            "messaging_product": "whatsapp",
            "contacts": [{"input": TELEFONE, "wa_id": TELEFONE}],
            "messages": [{"id": "wamid.bot.7"}],
        })

    def solicitar(self):
        return digitacao.indicar_digitacao(
            PHONE_ID, WAMID, id_mensagem=7, id_conversa=10,
        )


class DigitacaoTransporteTests(HTTPMetaSimulada, unittest.TestCase):
    def setUp(self):
        self.preparar_http()

    def test_sdk_marca_entrada_lida_na_conta_correta_com_timeout_isolado(self):
        with cliente.antes_do_primeiro_envio(self.solicitar):
            wa = cliente.conta_wa(PHONE_ID)
            self.assertEqual(self.requisicoes, [])  # Criar o cliente não ativa.
            wa.send_message(to=TELEFONE, text="Olá!")
        self.assertEqual(self.eventos, ["digitacao", "resposta"])
        indicador, resposta = self.requisicoes
        self.assertTrue(indicador.url.path.endswith(f"/{PHONE_ID}/messages"))
        self.assertEqual(json.loads(indicador.content), {
            "messaging_product": "whatsapp", "status": "read",
            "message_id": WAMID, "typing_indicator": {"type": "text"},
        })
        self.assertEqual(indicador.extensions["timeout"], {
            "connect": 1.0, "read": 2.0, "write": 2.0, "pool": 1.0,
        })
        self.assertEqual(resposta.extensions["timeout"]["read"], 30.0)
        self.transporte.assert_called_once_with(retries=0)
        self.assertIsNot(self.sessoes[0], self.sessoes[1])
        self.assertTrue(self.sessoes[1].is_closed)

    def test_uma_tentativa_por_turno_mesmo_com_dois_clientes_e_prefixo(self):
        with cliente.antes_do_primeiro_envio(self.solicitar):
            with cliente.usar_prefixo_mensagem_bot("Olá novamente!\n\n"):
                cliente.conta_wa(PHONE_ID).send_message(to=TELEFONE, text="Primeira")
                cliente.conta_wa(PHONE_ID).request_contact_info(
                    to=TELEFONE, text="Segunda",
                )
        self.assertEqual(self.eventos, ["digitacao", "resposta", "resposta"])
        self.assertEqual(json.loads(self.requisicoes[1].content)["text"]["body"],
                         "Olá novamente!\n\nPrimeira")
        # Um envio fora do worker (por exemplo, proativo) não herda o indicador.
        cliente.conta_wa(PHONE_ID).send_message(to=TELEFONE, text="Fora do turno")
        self.assertEqual(self.eventos.count("digitacao"), 1)

    def test_falhas_opcionais_nao_retentam_nem_impedem_resposta(self):
        for erro, status, payload in (
            (httpx.ReadTimeout("segredo nao deve aparecer"), 200, {}),
            (httpx.ConnectError("indisponivel"), 200, {}),
            (None, 400, {"error": {"code": 100, "message": "recusado"}}),
            (None, 200, {"success": False}),
            (None, 200, {}),
        ):
            with self.subTest(erro=erro, status=status, payload=payload):
                self.eventos.clear()
                self.falha_indicador = erro
                self.status_indicador = status
                self.resposta_indicador = payload
                with patch.object(digitacao.logger, "warning") as log:
                    with cliente.antes_do_primeiro_envio(self.solicitar):
                        wa = cliente.conta_wa(PHONE_ID)
                        wa.send_message(to=TELEFONE, text="Resposta")
                        wa.send_message(to=TELEFONE, text="Complemento")
                self.assertEqual(self.eventos, ["digitacao", "resposta", "resposta"])
                log.assert_called_once()
                self.assertNotIn("segredo", str(log.call_args))
                self.assertNotIn(WAMID, str(log.call_args))
                self.assertTrue(self.sessoes[-1].is_closed)

    def test_identificadores_ausentes_ou_invalidos_omitem_apenas_indicador(self):
        for phone, wamid in ((None, WAMID), (PHONE_ID, None),
                             (PHONE_ID, 7), (PHONE_ID, "wamid.")):
            with self.subTest(phone=phone, wamid=wamid):
                with cliente.antes_do_primeiro_envio(partial(
                    digitacao.indicar_digitacao, phone, wamid,
                )):
                    cliente.conta_wa(PHONE_ID).send_message(to=TELEFONE, text="Ok")
        self.assertEqual(self.eventos, ["resposta"] * 4)
        self.transporte.assert_not_called()

    def test_escopo_restaurado_apos_excecao_e_nao_vaza_entre_unidades(self):
        with self.assertRaises(ValueError):
            with cliente.antes_do_primeiro_envio(self.solicitar):
                raise ValueError("resolver sem resposta")
        cliente.conta_wa(PHONE_ID).send_message(to=TELEFONE, text="Sem indicador")
        with cliente.antes_do_primeiro_envio(partial(
            digitacao.indicar_digitacao, "987654", "wamid.outro.cliente",
        )):
            cliente.conta_wa("987654").send_message(to=TELEFONE, text="Outra unidade")
        self.assertEqual(self.eventos, ["resposta", "digitacao", "resposta"])
        self.assertTrue(self.requisicoes[1].url.path.endswith("/987654/messages"))
        self.assertEqual(json.loads(self.requisicoes[1].content)["message_id"],
                         "wamid.outro.cliente")


class DigitacaoWorkerTests(HTTPMetaSimulada, unittest.TestCase):
    def setUp(self):
        self.preparar_http()
        self.conn = FakeConn(FakeCursor())
        runtime.WorkerFlowRuntimeTests._patch_fluxo_base(
            self, self.stack, self.conn, self.eventos,
        )
        self.contexto = dict(
            runtime.contexto_historico(), nome_unidade="Supera Teste",
            nome_agente="Dora", genero="feminino", tipo_mensagem_atual="text",
            texto_cliente_atual="Olá", status_dependente=False,
            dados_repeticao={"nome_titular": "Ana", "status_dependente": False,
                             "nome_unidade": "Supera Teste", "nome_agente": "Dora",
                             "genero": "feminino"},
        )
        self.patch("valida_historico", side_effect=lambda *_: self.contexto)
        self.patch("flow_sender", side_effect=flow_sender)
        self.patch("enviar_retorno_followup", side_effect=enviar_retorno_followup)
        self.guarda_unidade = self.patch(
            "exigir_unidade_habilitada_por_phone_id",
            side_effect=lambda *_: self.eventos.append("unidade_ok"),
        )
        self.guarda_lock = self.patch(
            "proteger_conversa", side_effect=lambda *_a, **_kw: self.eventos.append("lock_ok"),
        )
        self.persistir = self.patch(
            "atualizar_banco_com_contexto_final", return_value=runtime.contexto_final(),
        )
        self.persistir_followup = self.patch(
            "persistir_retorno_followup", return_value=runtime.contexto_final(),
        )
        self.finalizar = self.patch(
            "finalizar_mensagem_processada", return_value={"atendimento_encerrado": False},
        )
        self.patch("registrar_cache_bloqueio_apos_commit")
        self.reagendar = self.patch("reagendar_mensagem_sem_erro")
        self.erro = self.patch("handle_erro_generico")

    def patch(self, nome, **kwargs):
        return self.stack.enter_context(patch.object(runtime.flow_worker, nome, **kwargs))

    def executar(self):
        with self.assertRaises(runtime.PararWorker):
            runtime.flow_worker.worker_flow()

    def test_abertura_ativa_so_apos_guardas_e_commit_sem_alterar_persistencia(self):
        # Verifica o checkpoint sem criar uma transação para a chamada opcional.
        self.ao_indicar = lambda: self.assertEqual(self.conn.commits, 5)
        self.executar()
        indice = self.eventos.index("digitacao")
        self.assertEqual(self.eventos[indice - 2:indice], ["lock_ok", "unidade_ok"])
        self.assertEqual(self.eventos[indice:indice + 2], ["digitacao", "resposta"])
        self.persistir.assert_called_once()
        self.assertTrue(self.persistir.call_args.args[1]["enviou"])
        self.finalizar.assert_called_once()
        self.reagendar.assert_not_called()
        self.assertEqual(self.conn.commits, 8)

    def test_falha_indicador_preserva_envio_fila_e_retry(self):
        self.falha_indicador = httpx.ReadTimeout("Meta indisponivel")
        self.executar()
        self.assertIn("resposta", self.eventos)
        self.persistir.assert_called_once()
        self.finalizar.assert_called_once()
        self.reagendar.assert_not_called()
        self.erro.assert_not_called()
        self.assertEqual(self.conn.rollbacks, 0)

    def test_replay_recupera_resposta_sem_indicador_ou_reenvio(self):
        self.contexto["resposta_bot_para_mensagem_atual"] = {
            "id_etapa": 1, "id_hash_msg": "wamid.bot.7", "id_mensagem": 99,
        }
        self.executar()
        self.assertEqual(self.requisicoes, [])
        self.assertFalse(self.persistir.call_args.args[1]["enviou"])
        self.finalizar.assert_called_once()

    def test_fireads_pendente_existente_nao_ativa(self):
        self.patch("preparar_abertura", side_effect=runtime.flow_worker.ConsultaFireAdsPendente())
        self.executar()
        self.assertEqual(self.requisicoes, [])
        self.persistir.assert_not_called()
        self.reagendar.assert_called_once_with(
            7, self.conn.cursor_obj, delay_seconds=5, retry_esperado=1,
        )

    def test_fireads_nova_pendencia_ativa_apos_commit_mesmo_se_meta_falhar(self):
        self.patch("preparar_abertura", side_effect=runtime.flow_worker.ConsultaFireAdsPendente(
            consulta_nova=True,
        ))
        self.ao_indicar = lambda: self.assertEqual(self.conn.commits, 4)
        self.falha_indicador = httpx.ReadTimeout("Meta indisponivel")
        self.executar()
        self.assertEqual(self.eventos.count("digitacao"), 1)
        self.assertNotIn("resposta", self.eventos)
        self.persistir.assert_not_called()
        self.finalizar.assert_not_called()
        self.reagendar.assert_called_once()
        self.erro.assert_not_called()
        self.assertEqual(self.conn.rollbacks, 0)

    def test_pendencia_sem_commit_nao_ativa_indicador(self):
        self.patch("preparar_abertura", side_effect=runtime.flow_worker.ConsultaFireAdsPendente(
            consulta_nova=True,
        ))
        with patch.object(self.conn, "commit", side_effect=[
            None, None, None, RuntimeError("commit indisponivel"), None,
        ]):
            with self.assertRaisesRegex(RuntimeError, "commit indisponivel"):
                runtime.flow_worker.worker_flow()
        self.assertEqual(self.requisicoes, [])

    def test_fireads_tres_ativacoes_com_rechecagens_sem_repeticao(self):
        conexoes = [FakeConn(FakeCursor()) for _ in range(4)]
        self.patch("get_conn", side_effect=[
            item for conn in conexoes for item in (conn, runtime.PararWorker())
        ])
        self.patch("preparar_abertura", side_effect=[
            runtime.flow_worker.ConsultaFireAdsPendente(consulta_nova=True),
            runtime.flow_worker.ConsultaFireAdsPendente(),
            runtime.flow_worker.ConsultaFireAdsPendente(),
            runtime.contexto_banco(),
        ])
        for _ in range(3):
            self.executar()
        self.assertEqual(self.eventos.count("digitacao"), 1)
        self.assertNotIn("resposta", self.eventos)

        with ExitStack() as stack:
            preparar_consulta_simulada(stack, self.eventos)
            self.assertTrue(consulta_worker.executar_ciclo())
        self.assertEqual(self.eventos.count("digitacao"), 2)
        self.executar()
        self.assertEqual([e for e in self.eventos if e in {"digitacao", "consulta", "resposta"}],
                         ["digitacao", "digitacao", "consulta", "digitacao", "resposta"])
        self.assertEqual([json.loads(r.content)["message_id"] for r in self.requisicoes[:-1]],
                         [WAMID] * 3)
        self.persistir.assert_called_once()
        self.finalizar.assert_called_once()

    def test_fireads_concluida_ativa_para_abertura_personalizada(self):
        self.contexto["contexto_fireads"] = {
            "concluida": True, "resultado": "importado", "id_conversa": 10,
            "dados_titular": {"nome": "Ana", "email": "ana@example.test",
                              "resultado_email": "email_valido"},
        }
        self.executar()
        self.assertEqual(self.eventos.count("digitacao"), 1)
        self.assertEqual(self.persistir.call_args.args[1]["id_etapa_resultante"], 4)
        texto = json.loads(self.requisicoes[-1].content)["text"]["body"]
        self.assertIn("preencheu um dos nossos formulários", texto)

    def test_continuacao_e_reacao_followup_ativam_uma_vez(self):
        self.contexto.update(id_etapa_atual=1, retorno_followup=True,
                             texto_cliente_atual="123")
        self.patch("preparar_retorno_followup", return_value=self.contexto)
        self.executar()
        self.assertEqual(self.eventos.count("digitacao"), 1)
        self.assertEqual(self.eventos.count("resposta"), 1)
        self.persistir_followup.assert_called_once()
        self.erro.assert_not_called()

    def test_continuacao_normal_ativa_antes_de_repetir_pergunta(self):
        self.contexto.update(id_etapa_atual=1, texto_cliente_atual="123")
        self.executar()
        self.assertEqual(self.eventos.count("digitacao"), 1)
        self.assertEqual(self.eventos.count("resposta"), 1)
        self.assertEqual(self.persistir.call_args.args[1]["id_etapa_resultante"], 1)
        self.erro.assert_not_called()

    def test_followup_replay_nao_ativa(self):
        self.contexto.update(id_etapa_atual=1, retorno_followup=True,
                             resposta_bot_para_mensagem_atual={
                                 "id_etapa": 1, "id_hash_msg": "wamid.bot.7",
                             })
        self.patch("preparar_retorno_followup", return_value=self.contexto)
        self.executar()
        self.assertEqual(self.requisicoes, [])
        self.persistir_followup.assert_called_once()

    def test_etapa_sem_rota_nao_ativa(self):
        self.contexto["id_etapa_atual"] = 999
        self.executar()
        self.assertEqual(self.requisicoes, [])
        self.erro.assert_called_once()
        self.persistir.assert_not_called()

    def test_apresentacao_incompleta_nao_ativa(self):
        self.contexto.pop("nome_agente")
        self.executar()
        self.assertEqual(self.requisicoes, [])
        self.erro.assert_called_once()

    def test_guardas_rejeitadas_nao_chegam_a_meta(self):
        casos = (
            ("reagendar_se_houver_mensagem_anterior", {"return_value": True}),
            ("tentar_lock_conversa", {"return_value": (False, None)}),
            ("vincular_mensagem_fila_a_conversa", {"return_value": 0}),
            ("exigir_unidade_habilitada_por_phone_id", {
                "side_effect": [None, None, runtime.flow_worker.UnidadeDesativada()],
            }),
            ("proteger_conversa", {"side_effect": runtime.flow_worker.LockConversaPerdido()}),
            ("validar_banco_mensagem", {"return_value": dict(
                runtime.contexto_banco(), conversa={"id_conversa": 10, "estado": "bloqueada"},
            )}),
        )
        for nome, kwargs in casos:
            with self.subTest(guarda=nome):
                self.patch("get_conn", side_effect=[self.conn, runtime.PararWorker()])
                self.patch("tratar_conversa_bloqueada")
                with patch.object(runtime.flow_worker, nome, **kwargs):
                    self.executar()
                self.assertEqual(self.requisicoes, [])
                self.persistir.assert_not_called()
                self.erro.assert_not_called()


def preparar_consulta_simulada(stack, eventos):
    conn = FakeConn(FakeCursor())
    reserva = dict(id_consulta=20, id_conversa=10, versao=1, restante=290, entrada={})
    stack.enter_context(patch.object(consulta_worker, "get_conn", return_value=conn))
    reservar = stack.enter_context(patch.object(
        consulta_worker.pendencias, "reservar", return_value=reserva,
    ))
    mensagem = stack.enter_context(patch.object(
        consulta_worker.pendencias, "buscar_mensagem_aguardando", return_value={
            "id_mensagem": 7, "id_phone_unidade": PHONE_ID, "id_hash": WAMID,
        },
    ))
    stack.enter_context(patch.object(consulta_worker.pendencias, "expirar", return_value=0))
    concluir = stack.enter_context(patch.object(consulta_worker.pendencias, "concluir", return_value=True))
    liberar = stack.enter_context(patch.object(consulta_worker.pendencias, "liberar_reserva", return_value=True))
    consultar = stack.enter_context(patch.object(
        consulta_worker, "consultar", side_effect=lambda _: eventos.append("consulta")
        or {"decisao": {"resultado": "ausente"}, "fontes": {}},
    ))
    return conn, reserva, reservar, mensagem, consultar, concluir, liberar


class DigitacaoConsultaTests(HTTPMetaSimulada, unittest.TestCase):
    def setUp(self):
        self.preparar_http()
        (self.conn, self.reserva, self.reservar, self.mensagem,
         self.consultar, self.concluir, self.liberar) = preparar_consulta_simulada(
            self.stack, self.eventos,
        )

    def test_indicador_apos_commit_e_antes_da_consulta_preserva_resultado(self):
        self.ao_indicar = lambda: self.assertEqual(self.conn.commits, 3)
        self.assertTrue(consulta_worker.executar_ciclo())
        self.assertEqual(self.eventos, ["digitacao", "consulta"])
        self.concluir.assert_called_once()
        self.liberar.assert_called_once_with(20, self.conn.cursor_obj)
        self.assertEqual(self.conn.rollbacks, 0)
        self.assertTrue(self.conn.closed)

    def test_timeout_indicador_nao_impede_consulta_nem_salvamento(self):
        self.falha_indicador = httpx.ReadTimeout("Meta indisponivel")
        self.assertTrue(consulta_worker.executar_ciclo())
        self.assertEqual(self.eventos, ["digitacao", "consulta"])
        self.concluir.assert_called_once()
        self.assertEqual(self.conn.rollbacks, 0)

    def test_sem_entrada_elegivel_omite_so_indicador(self):
        self.mensagem.return_value = None
        self.assertTrue(consulta_worker.executar_ciclo())
        self.assertEqual(self.eventos, ["consulta"])
        self.concluir.assert_called_once()

    def test_sem_reserva_nao_busca_mensagem_nem_ativa(self):
        self.reservar.return_value = None
        self.assertFalse(consulta_worker.executar_ciclo())
        self.assertEqual(self.eventos, [])
        self.mensagem.assert_not_called()
        self.liberar.assert_not_called()

    def test_indicador_nao_reinicia_prazo_da_consulta(self):
        for inicio, fim, esperado in ((100, 103, 287), (100, 401, 0)):
            with self.subTest(restante=esperado):
                self.reserva["restante"] = 290
                with patch.object(consulta_worker, "time") as relogio, patch.object(
                    consulta_worker, "get_conn", return_value=FakeConn(FakeCursor()),
                ):
                    relogio.monotonic.side_effect = [inicio, fim]
                    self.assertTrue(consulta_worker.executar_ciclo())
                self.assertEqual(self.consultar.call_args.args[0]["restante"], esperado)


if __name__ == "__main__":
    unittest.main()
