import json
import unittest
from unittest.mock import patch

from django.http import JsonResponse
from django.test import override_settings

from callback.webhook.services import post_flow
from tests.helpers import FakeRequest, json_response_payload
from tests.payloads import payload_texto_meta


class WebhookPostFlowTests(unittest.TestCase):
    def test_content_type_invalido_retorna_415_antes_de_assinatura(self):
        request = FakeRequest(
            payload_texto_meta(),
            content_type="text/plain",
        )

        with patch.object(post_flow, "validar_assinatura_meta") as assinatura:
            response = post_flow.responder_post_webhook(request)

        self.assertEqual(response.status_code, 415)
        self.assertEqual(
            json_response_payload(response)["status"],
            "unsupported_media_type",
        )
        assinatura.assert_not_called()

    @override_settings(WEBHOOK_MAX_BODY_BYTES=10)
    def test_body_grande_retorna_413_antes_de_parse_json(self):
        request = FakeRequest(
            payload_texto_meta(),
            headers={"Content-Length": "999"},
        )

        with patch.object(post_flow, "validar_assinatura_meta") as assinatura:
            response = post_flow.responder_post_webhook(request)

        self.assertEqual(response.status_code, 413)
        self.assertEqual(json_response_payload(response)["status"], "payload_too_large")
        assinatura.assert_not_called()

    @override_settings(WEBHOOK_MAX_BODY_BYTES=1024 * 256)
    def test_assinatura_invalida_retorna_403(self):
        request = FakeRequest(payload_texto_meta())

        with patch.object(post_flow, "validar_assinatura_meta", return_value=False):
            response = post_flow.responder_post_webhook(request)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(json_response_payload(response)["status"], "forbidden")

    @override_settings(WEBHOOK_MAX_BODY_BYTES=1024 * 256)
    def test_json_invalido_retorna_ignored(self):
        request = FakeRequest("{json quebrado")

        with patch.object(post_flow, "validar_assinatura_meta", return_value=True):
            response = post_flow.responder_post_webhook(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(json_response_payload(response)["reason"], "invalid_json")

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
        ) as fila:
            response = post_flow.responder_post_webhook(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(json_response_payload(response)["reason"], "flood_redis")
        unidade.assert_not_called()
        fila.assert_not_called()

    @override_settings(WEBHOOK_MAX_BODY_BYTES=1024 * 256)
    def test_payload_valido_enfileira(self):
        request = FakeRequest(payload_texto_meta())

        with patch.object(post_flow, "validar_assinatura_meta", return_value=True), patch.object(
            post_flow,
            "responder_se_flood",
            return_value=None,
        ), patch.object(post_flow, "unidade_esta_ativa", return_value=True), patch.object(
            post_flow,
            "conversa_esta_bloqueada_cache",
            return_value=False,
        ), patch.object(
            post_flow,
            "povoando_fila",
            return_value={"status": "inserted", "reason": None},
        ):
            response = post_flow.responder_post_webhook(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content.decode("utf-8"))["status"], "ok")


if __name__ == "__main__":
    unittest.main()
