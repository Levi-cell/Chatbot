import unittest
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.admin.sites import AdminSite

from core.integrations.whatsapp.tools import (
    ativando_waba_id,
    desativa_waba_id,
    validando_phone_waba,
)
from webhook.admin import UnidadeAdmin
from webhook.models import Unidade


class _RespostaMetaFake:
    def __init__(self, status_code=200, corpo=None):
        self.status_code = status_code
        self._corpo = corpo if corpo is not None else {"success": True}
        self.ok = 200 <= status_code < 300
        self.text = ""

    def json(self):
        return self._corpo


class AdminUnidadeMultiWabaTests(unittest.TestCase):
    def setUp(self):
        self.admin = UnidadeAdmin(Unidade, AdminSite())
        self.request = SimpleNamespace()

    def test_ativacao_usa_waba_recebida_e_token_unico_do_sistema(self):
        resposta = _RespostaMetaFake()

        with (
            patch.object(
                ativando_waba_id,
                "get_token_usuario_meta",
                return_value="token-unico",
            ),
            patch.object(
                ativando_waba_id,
                "get_meta_http_timeout",
                return_value=(30, 35),
            ),
            patch.object(
                ativando_waba_id.requests,
                "post",
                return_value=resposta,
            ) as post,
        ):
            status, corpo = ativando_waba_id.ativar_waba_id("waba-cliente-b")

        self.assertEqual(status, 200)
        self.assertEqual(corpo, {"success": True})
        post.assert_called_once_with(
            "https://graph.facebook.com/v26.0/"
            "waba-cliente-b/subscribed_apps",
            headers={
                "Authorization": "Bearer token-unico",
                "Content-Type": "application/json",
            },
            timeout=(30, 35),
        )

    def test_ativacao_recusa_waba_vazia_sem_chamar_graph_api(self):
        with patch.object(ativando_waba_id.requests, "post") as post:
            with self.assertRaisesRegex(ValueError, "waba_id nao informado"):
                ativando_waba_id.ativar_waba_id(" ")

        post.assert_not_called()

    def test_validacao_confirma_phone_id_na_waba_com_paginacao(self):
        primeira_pagina = _RespostaMetaFake(
            corpo={
                "data": [{"id": "phone-a"}],
                "paging": {
                    "next": "https://graph.facebook.com/pagina-2",
                },
            }
        )
        segunda_pagina = _RespostaMetaFake(
            corpo={"data": [{"id": "phone-b"}]}
        )

        with (
            patch.object(
                validando_phone_waba,
                "get_token_usuario_meta",
                return_value="token-unico",
            ),
            patch.object(
                validando_phone_waba,
                "get_meta_http_timeout",
                return_value=(30, 35),
            ),
            patch.object(
                validando_phone_waba.requests,
                "get",
                side_effect=[primeira_pagina, segunda_pagina],
            ) as get,
        ):
            status, corpo = (
                validando_phone_waba
                .validar_phone_number_id_da_waba(
                    "waba-b",
                    "phone-b",
                )
            )

        self.assertEqual(status, 200)
        self.assertTrue(corpo["success"])
        self.assertTrue(corpo["belongs"])
        self.assertEqual(get.call_count, 2)
        self.assertEqual(
            get.call_args_list[0].args[0],
            "https://graph.facebook.com/v26.0/waba-b/phone_numbers",
        )
        self.assertEqual(
            get.call_args_list[0].kwargs["params"],
            {"fields": "id", "limit": 100},
        )
        self.assertIsNone(get.call_args_list[1].kwargs["params"])

    def test_validacao_recusa_phone_id_ausente_da_waba(self):
        resposta = _RespostaMetaFake(
            corpo={"data": [{"id": "outro-phone"}]}
        )

        with patch.object(
            validando_phone_waba.requests,
            "get",
            return_value=resposta,
        ):
            status, corpo = (
                validando_phone_waba
                .validar_phone_number_id_da_waba(
                    "waba-a",
                    "phone-a",
                )
            )

        self.assertEqual(status, 200)
        self.assertFalse(corpo["success"])
        self.assertFalse(corpo["belongs"])
        self.assertEqual(
            corpo["reason"],
            "phone_number_not_in_waba",
        )

    def test_admin_valida_vinculo_antes_de_ativar_e_registrar(self):
        ordem = []

        with (
            patch.object(
                self.admin,
                "_validar_vinculo_phone_waba_antes_de_salvar",
                side_effect=lambda request, waba_id, phone_id: (
                    ordem.append(
                        ("validar", request, waba_id, phone_id)
                    )
                    or True
                ),
            ),
            patch.object(
                self.admin,
                "_ativar_waba_antes_de_salvar",
                side_effect=lambda request, waba_id: (
                    ordem.append(("waba", request, waba_id)) or True
                ),
            ),
            patch.object(
                self.admin,
                "_registrar_meta_antes_de_salvar",
                side_effect=lambda request, phone_id: (
                    ordem.append(("phone", request, phone_id)) or True
                ),
            ),
        ):
            campo_erro = self.admin._preparar_meta_antes_de_salvar(
                self.request,
                "waba-a",
                "phone-a",
            )

        self.assertIsNone(campo_erro)
        self.assertEqual(
            [item[0] for item in ordem],
            ["validar", "waba", "phone"],
        )
        self.assertEqual(ordem[0][2:], ("waba-a", "phone-a"))

    def test_admin_repassa_waba_do_formulario_para_graph_api(self):
        with patch(
            "webhook.admin.ativar_waba_id",
            return_value=(200, {"success": True}),
        ) as ativar:
            sucesso = self.admin._ativar_waba_antes_de_salvar(
                self.request,
                "waba-do-formulario",
            )

        self.assertTrue(sucesso)
        ativar.assert_called_once_with("waba-do-formulario")
        self.assertEqual(
            self.request._unidade_meta_sucesso,
            [
                {
                    "acao": "ativar_waba",
                    "waba_id": "waba-do-formulario",
                }
            ],
        )

    def test_falha_waba_impede_registro_do_phone_id(self):
        with (
            patch.object(
                self.admin,
                "_validar_vinculo_phone_waba_antes_de_salvar",
                return_value=True,
            ),
            patch.object(
                self.admin,
                "_ativar_waba_antes_de_salvar",
                return_value=False,
            ),
            patch.object(
                self.admin,
                "_registrar_meta_antes_de_salvar",
            ) as registrar,
        ):
            campo_erro = self.admin._preparar_meta_antes_de_salvar(
                self.request,
                "waba-a",
                "phone-a",
            )

        self.assertEqual(campo_erro, "waba_id")
        registrar.assert_not_called()

    def test_falha_vinculo_impede_ativacao_e_registro(self):
        with (
            patch.object(
                self.admin,
                "_validar_vinculo_phone_waba_antes_de_salvar",
                return_value=False,
            ),
            patch.object(
                self.admin,
                "_ativar_waba_antes_de_salvar",
            ) as ativar,
            patch.object(
                self.admin,
                "_registrar_meta_antes_de_salvar",
            ) as registrar,
        ):
            campo_erro = self.admin._preparar_meta_antes_de_salvar(
                self.request,
                "waba-a",
                "phone-a",
            )

        self.assertEqual(campo_erro, "vinculo_waba_phone")
        ativar.assert_not_called()
        registrar.assert_not_called()

    def test_desativacao_usa_waba_recebida(self):
        resposta = _RespostaMetaFake()

        with (
            patch.object(
                desativa_waba_id,
                "get_token_usuario_meta",
                return_value="token-unico",
            ),
            patch.object(
                desativa_waba_id,
                "get_meta_http_timeout",
                return_value=(30, 35),
            ),
            patch.object(
                desativa_waba_id.requests,
                "delete",
                return_value=resposta,
            ) as delete,
        ):
            status, corpo = desativa_waba_id.desativar_waba_id(
                "waba-a"
            )

        self.assertEqual(status, 200)
        self.assertEqual(corpo, {"success": True})
        delete.assert_called_once_with(
            "https://graph.facebook.com/v26.0/"
            "waba-a/subscribed_apps",
            headers={
                "Authorization": "Bearer token-unico",
                "Content-Type": "application/json",
            },
            timeout=(30, 35),
        )

    def test_exclusao_desassina_waba_antes_de_desregistrar_numero(self):
        unidade = SimpleNamespace(
            id_unidade=7,
            waba_id="waba-a",
            phone_number_id="phone-a",
        )
        ordem = []

        with (
            patch(
                "webhook.admin.desativar_waba_id",
                side_effect=lambda waba_id: (
                    ordem.append(("waba", waba_id))
                    or (200, {"success": True})
                ),
            ),
            patch(
                "webhook.admin.desregistrar_numero_whatsapp",
                side_effect=lambda phone_id: (
                    ordem.append(("phone", phone_id))
                    or (200, {"success": True})
                ),
            ),
        ):
            sucesso = self.admin._desregistrar_meta_antes_de_excluir(
                self.request,
                unidade,
            )

        self.assertTrue(sucesso)
        self.assertEqual(
            ordem,
            [("waba", "waba-a"), ("phone", "phone-a")],
        )
        self.assertEqual(
            self.request._unidade_meta_sucesso,
            [
                {
                    "acao": "desativar_waba",
                    "waba_id": "waba-a",
                },
                {
                    "acao": "desregistrar_numero",
                    "phone_number_id": "phone-a",
                },
            ],
        )

    def test_falha_ao_desassinar_waba_impede_desregistro_numero(self):
        unidade = SimpleNamespace(
            id_unidade=7,
            waba_id="waba-a",
            phone_number_id="phone-a",
        )

        with (
            patch(
                "webhook.admin.desativar_waba_id",
                return_value=(500, {"success": False}),
            ),
            patch(
                "webhook.admin.desregistrar_numero_whatsapp",
            ) as desregistrar,
            patch.object(self.admin, "message_user"),
        ):
            sucesso = self.admin._desregistrar_meta_antes_de_excluir(
                self.request,
                unidade,
            )

        self.assertFalse(sucesso)
        desregistrar.assert_not_called()

    def test_ids_meta_ficam_imutaveis_depois_da_criacao(self):
        self.assertEqual(
            self.admin.get_readonly_fields(self.request, obj=SimpleNamespace()),
            ("waba_id", "phone_number_id"),
        )
        self.assertEqual(
            self.admin.get_readonly_fields(self.request, obj=None),
            (),
        )


if __name__ == "__main__":
    unittest.main()
