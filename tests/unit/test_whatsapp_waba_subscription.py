import unittest
from unittest.mock import Mock, patch

from core.integrations.whatsapp.tools import desativa_waba_id


class DesativarWabaIdTests(unittest.TestCase):
    def test_desativa_inscricao_do_app_no_waba(self):
        response = Mock(
            status_code=200,
            ok=True,
        )
        response.json.return_value = {"success": True}

        with patch.object(
            desativa_waba_id,
            "get_token_usuario_meta",
            return_value="token-teste",
        ), patch.object(
            desativa_waba_id,
            "get_meta_http_timeout",
            return_value=(30, 35),
        ), patch.object(
            desativa_waba_id.requests,
            "delete",
            return_value=response,
        ) as delete:
            status, payload = desativa_waba_id.desativar_waba_id(
                "waba-1"
            )

        delete.assert_called_once_with(
            (
                "https://graph.facebook.com/v25.0/"
                "waba-1/subscribed_apps"
            ),
            headers={
                "Authorization": "Bearer token-teste",
                "Content-Type": "application/json",
            },
            timeout=(30, 35),
        )
        self.assertEqual(status, 200)
        self.assertEqual(payload, {"success": True})

    def test_resposta_nao_json_tem_fallback(self):
        response = Mock(
            status_code=503,
            ok=False,
            text="indisponivel",
        )
        response.json.side_effect = ValueError("sem json")

        self.assertEqual(
            desativa_waba_id._normalizar_resposta(response),
            {
                "success": False,
                "text": "indisponivel",
            },
        )


if __name__ == "__main__":
    unittest.main()
