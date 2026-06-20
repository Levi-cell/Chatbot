import json
import unittest
from unittest.mock import patch

from django.http import JsonResponse
from django.test import override_settings

from callback.webhook.services import post_flow
from tests.helpers import FakeConn, FakeCursor, FakeRequest, json_response_payload
from tests.payloads import payload_sem_mensagem, payload_texto_meta


class WebhookPostFlowTests(unittest.TestCase):
    def test_content_type_invalido_retorna_415_antes_de_assinatura(self):
        request = FakeRequest(
            payload_texto_meta(),
            content_type="text/plain",
        )

        with patch.object(post_flow, "validar_assinatura_meta") as assinatura, patch.object(
            post_flow,
            "get_conn",
        ) as get_conn:
            response = post_flow.responder_post_webhook(request)

        self.assertEqual(response.status_code, 415)
        self.assertEqual(
            json_response_payload(response)["status"],
            "unsupported_media_type",
        )
        assinatura.assert_not_called()
        get_conn.assert_not_called()

    @override_settings(WEBHOOK_MAX_BODY_BYTES=10)
    def test_body_grande_retorna_413_antes_de_parse_json(self):
        request = FakeRequest(
            payload_texto_meta(),
            headers={"Content-Length": "999"},
        )

        with patch.object(post_flow, "validar_assinatura_meta") as assinatura, patch.object(
            post_flow,
            "get_conn",
        ) as get_conn:
            response = post_flow.responder_post_webhook(request)

        self.assertEqual(response.status_code, 413)
        self.assertEqual(json_response_payload(response)["status"], "payload_too_large")
        assinatura.assert_not_called()
        get_conn.assert_not_called()

    @override_settings(WEBHOOK_MAX_BODY_BYTES=1024 * 256)
    def test_assinatura_invalida_retorna_403(self):
        request = FakeRequest(payload_texto_meta())

        with patch.object(
            post_flow,
            "validar_assinatura_meta",
            return_value=False,
        ), patch.object(post_flow, "get_conn") as get_conn:
            response = post_flow.responder_post_webhook(request)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(json_response_payload(response)["status"], "forbidden")
        get_conn.assert_not_called()

    @override_settings(WEBHOOK_MAX_BODY_BYTES=1024 * 256)
    def test_json_invalido_retorna_ignored(self):
        request = FakeRequest("{json quebrado")

        with patch.object(
            post_flow,
            "validar_assinatura_meta",
            return_value=True,
        ), patch.object(post_flow, "get_conn") as get_conn:
            response = post_flow.responder_post_webhook(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(json_response_payload(response)["reason"], "invalid_json")
        get_conn.assert_not_called()

    @override_settings(WEBHOOK_MAX_BODY_BYTES=1024 * 256)
    def test_flood_bloqueia_antes_de_unidade_e_fila(self):
        request = FakeRequest(payload_texto_meta())

        with patch.object(post_flow, "validar_assinatura_meta", return_value=True), patch.object(
            post_flow,
            "responder_se_flood",
            return_value=JsonResponse({"status": "ignored", "reason": "flood_redis"}),
        ), patch.object(post_flow, "unidade_esta_ativa") as unidade, patch.object(
            post_flow,
            "povoando_fila",
        ) as fila, patch.object(post_flow, "get_conn") as get_conn:
            response = post_flow.responder_post_webhook(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(json_response_payload(response)["reason"], "flood_redis")
        unidade.assert_not_called()
        fila.assert_not_called()
        get_conn.assert_not_called()

    @override_settings(WEBHOOK_MAX_BODY_BYTES=1024 * 256)
    def test_evento_sem_mensagem_nao_abre_transacao(self):
        request = FakeRequest(payload_sem_mensagem())

        with patch.object(post_flow, "validar_assinatura_meta", return_value=True), patch.object(
            post_flow,
            "responder_se_flood",
            return_value=None,
        ), patch.object(post_flow, "unidade_esta_ativa", return_value=True), patch.object(
            post_flow,
            "conversa_esta_bloqueada_cache",
            return_value=False,
        ), patch.object(post_flow, "get_conn") as get_conn:
            response = post_flow.responder_post_webhook(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(json_response_payload(response)["status"], "ok")
        get_conn.assert_not_called()

    @override_settings(WEBHOOK_MAX_BODY_BYTES=1024 * 256)
    def test_payload_valido_commita_e_fecha(self):
        request = FakeRequest(payload_texto_meta())
        cursor = FakeCursor()
        conn = FakeConn(cursor=cursor)

        with patch.object(post_flow, "validar_assinatura_meta", return_value=True), patch.object(
            post_flow,
            "responder_se_flood",
            return_value=None,
        ), patch.object(post_flow, "unidade_esta_ativa", return_value=True), patch.object(
            post_flow,
            "conversa_esta_bloqueada_cache",
            return_value=False,
        ), patch.object(post_flow, "get_conn", return_value=conn), patch.object(
            post_flow,
            "povoando_fila",
            return_value={"status": "inserted", "reason": None},
        ) as fila:
            response = post_flow.responder_post_webhook(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content.decode("utf-8"))["status"], "ok")
        self.assertEqual(conn.commits, 1)
        self.assertEqual(conn.rollbacks, 0)
        self.assertTrue(conn.closed)
        fila.assert_called_once()
        self.assertIs(fila.call_args.args[1], cursor)

    @override_settings(WEBHOOK_MAX_BODY_BYTES=1024 * 256)
    def test_resultado_ignored_commita_para_liberar_lock(self):
        request = FakeRequest(payload_texto_meta())
        conn = FakeConn()

        with patch.object(post_flow, "validar_assinatura_meta", return_value=True), patch.object(
            post_flow,
            "responder_se_flood",
            return_value=None,
        ), patch.object(post_flow, "unidade_esta_ativa", return_value=True), patch.object(
            post_flow,
            "conversa_esta_bloqueada_cache",
            return_value=False,
        ), patch.object(post_flow, "get_conn", return_value=conn), patch.object(
            post_flow,
            "povoando_fila",
            return_value={
                "status": "ignored",
                "reason": "fila_aberta_sem_resposta_bot",
            },
        ):
            response = post_flow.responder_post_webhook(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(conn.commits, 1)
        self.assertEqual(conn.rollbacks, 0)
        self.assertTrue(conn.closed)

    @override_settings(WEBHOOK_MAX_BODY_BYTES=1024 * 256)
    def test_falha_na_insercao_faz_rollback_fecha_e_retorna_503(self):
        request = FakeRequest(payload_texto_meta())
        conn = FakeConn()

        with patch.object(post_flow, "validar_assinatura_meta", return_value=True), patch.object(
            post_flow,
            "responder_se_flood",
            return_value=None,
        ), patch.object(post_flow, "unidade_esta_ativa", return_value=True), patch.object(
            post_flow,
            "conversa_esta_bloqueada_cache",
            return_value=False,
        ), patch.object(post_flow, "get_conn", return_value=conn), patch.object(
            post_flow,
            "povoando_fila",
            side_effect=RuntimeError("banco caiu"),
        ):
            response = post_flow.responder_post_webhook(request)

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            json_response_payload(response),
            {
                "status": "unavailable",
                "reason": "insert_exception",
            },
        )
        self.assertEqual(conn.commits, 0)
        self.assertEqual(conn.rollbacks, 1)
        self.assertTrue(conn.closed)


if __name__ == "__main__":
    unittest.main()
