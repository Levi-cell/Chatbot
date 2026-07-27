from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from callback.webhook.services import post_flow
from tests.helpers import (
    FakeRequest,
    json_response_payload,
)
from tests.payloads import payload_texto_meta


@override_settings(
    WEBHOOK_MAX_BODY_BYTES=1024 * 256,
)
class WebhookErroInesperadoIntegracaoTests(
    SimpleTestCase,
):
    def setUp(self):
        self.print_patcher = patch("builtins.print")
        self.print_patcher.start()
        self.addCleanup(self.print_patcher.stop)

    def _executar_com_erro_generico(
        self,
        payload,
        tentativa,
    ):
        request = FakeRequest(payload)

        with patch.object(
            post_flow,
            "validar_assinatura_meta",
            return_value=True,
        ), patch.object(
            post_flow,
            "responder_se_cliente_marcado_para_bloqueio",
            return_value=None,
        ), patch.object(
            post_flow,
            "responder_se_flood",
            side_effect=RuntimeError("falha inesperada"),
        ), patch.object(
            post_flow,
            "registrar_tentativa_erro_inesperado",
            return_value=tentativa,
        ) as registrar, patch.object(
            post_flow,
            "preparar_dados_fila",
        ) as preparar_fila:
            response = post_flow.responder_post_webhook(
                request,
            )

        return response, registrar, preparar_fila

    def test_primeiras_tres_falhas_retornam_503(self):
        for numero_tentativa in (1, 2, 3):
            with self.subTest(
                tentativa=numero_tentativa,
            ):
                tentativa = {
                    "cache_ok": True,
                    "identificavel": True,
                    "tentativa": numero_tentativa,
                    "retornar_503": True,
                    "motivo": "dentro_limite_503",
                }
                response, registrar, preparar_fila = (
                    self._executar_com_erro_generico(
                        payload_texto_meta(),
                        tentativa,
                    )
                )

                self.assertEqual(
                    response.status_code,
                    503,
                )
                self.assertEqual(
                    json_response_payload(response),
                    {
                        "status": "unavailable",
                        "reason": (
                            "unexpected_error_retry"
                        ),
                        "attempt": numero_tentativa,
                    },
                )
                registrar.assert_called_once_with(
                    "wamid.test.1",
                )
                preparar_fila.assert_not_called()

    def test_quarta_falha_retorna_200_sem_fila(self):
        tentativa = {
            "cache_ok": True,
            "identificavel": True,
            "tentativa": 4,
            "retornar_503": False,
            "motivo": "limite_503_esgotado",
        }
        response, registrar, preparar_fila = (
            self._executar_com_erro_generico(
                payload_texto_meta(),
                tentativa,
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            json_response_payload(response)["reason"],
            "unexpected_error_retry_exhausted",
        )
        registrar.assert_called_once_with(
            "wamid.test.1",
        )
        preparar_fila.assert_not_called()

    def test_wamid_ausente_retorna_200_sem_fila(self):
        tentativa = {
            "cache_ok": False,
            "identificavel": False,
            "tentativa": None,
            "retornar_503": False,
            "motivo": "wamid_ausente",
        }
        response, registrar, preparar_fila = (
            self._executar_com_erro_generico(
                payload_texto_meta(message_id=None),
                tentativa,
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            json_response_payload(response)["reason"],
            "unexpected_error_retry_unavailable",
        )
        registrar.assert_called_once_with(None)
        preparar_fila.assert_not_called()

    def test_redis_indisponivel_retorna_200_sem_fila(
        self,
    ):
        tentativa = {
            "cache_ok": False,
            "identificavel": True,
            "tentativa": None,
            "retornar_503": False,
            "motivo": "redis_indisponivel",
        }
        response, registrar, preparar_fila = (
            self._executar_com_erro_generico(
                payload_texto_meta(),
                tentativa,
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            json_response_payload(response)["reason"],
            "unexpected_error_retry_unavailable",
        )
        registrar.assert_called_once_with(
            "wamid.test.1",
        )
        preparar_fila.assert_not_called()

    def test_erro_estrutural_na_classificacao_e_orcado(
        self,
    ):
        tentativa = {
            "cache_ok": False,
            "identificavel": False,
            "tentativa": None,
            "retornar_503": False,
            "motivo": "wamid_ausente",
        }
        request = FakeRequest({"entry": []})

        with patch.object(
            post_flow,
            "validar_assinatura_meta",
            return_value=True,
        ), patch.object(
            post_flow,
            "registrar_tentativa_erro_inesperado",
            return_value=tentativa,
        ) as registrar, patch.object(
            post_flow,
            "preparar_dados_fila",
        ) as preparar_fila:
            response = post_flow.responder_post_webhook(
                request,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            json_response_payload(response)["reason"],
            "unexpected_error_retry_unavailable",
        )
        registrar.assert_called_once_with(None)
        preparar_fila.assert_not_called()

