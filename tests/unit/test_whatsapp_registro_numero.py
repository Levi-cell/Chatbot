import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core.integrations.whatsapp.tools import (
    ativando_numero,
    desativando_numero,
)


class WhatsappRegistroNumeroTests(unittest.TestCase):
    def test_registro_usa_pin_configurado_e_timeout(self):
        response = SimpleNamespace(
            status_code=200,
            ok=True,
            text="",
            json=lambda: {"success": True},
        )

        with patch.object(
            ativando_numero,
            "get_token_usuario_meta",
            return_value="token-falso",
        ), patch.object(
            ativando_numero,
            "get_phone_registration_pin",
            return_value="654321",
        ), patch.object(
            ativando_numero,
            "get_meta_http_timeout",
            return_value=(30, 35),
        ), patch.object(
            ativando_numero.requests,
            "post",
            return_value=response,
        ) as post:
            status, payload = (
                ativando_numero.registrar_numero_whatsapp("phone-1")
            )

        self.assertEqual(status, 200)
        self.assertEqual(payload, {"success": True})
        self.assertEqual(
            post.call_args.kwargs["json"]["pin"],
            "654321",
        )
        self.assertEqual(
            post.call_args.kwargs["timeout"],
            (30, 35),
        )

    def test_pin_explicito_preserva_contrato_operacional(self):
        response = SimpleNamespace(
            status_code=200,
            ok=True,
            text="",
            json=lambda: {"success": True},
        )

        with patch.object(
            ativando_numero,
            "get_token_usuario_meta",
            return_value="token-falso",
        ), patch.object(
            ativando_numero,
            "get_meta_http_timeout",
            return_value=(30, 35),
        ), patch.object(
            ativando_numero.requests,
            "post",
            return_value=response,
        ) as post:
            ativando_numero.registrar_numero_whatsapp(
                "phone-1",
                pin="112233",
            )

        self.assertEqual(
            post.call_args.kwargs["json"]["pin"],
            "112233",
        )

    def test_desregistro_usa_timeout_configurado(self):
        response = SimpleNamespace(
            status_code=200,
            ok=True,
            text="",
            json=lambda: {"success": True},
        )

        with patch.object(
            desativando_numero,
            "get_token_usuario_meta",
            return_value="token-falso",
        ), patch.object(
            desativando_numero,
            "get_meta_http_timeout",
            return_value=(30, 35),
        ), patch.object(
            desativando_numero.requests,
            "post",
            return_value=response,
        ) as post:
            status, payload = (
                desativando_numero.desregistrar_numero_whatsapp(
                    "phone-1"
                )
            )

        self.assertEqual(status, 200)
        self.assertEqual(payload, {"success": True})
        self.assertEqual(
            post.call_args.kwargs["timeout"],
            (30, 35),
        )


if __name__ == "__main__":
    unittest.main()
