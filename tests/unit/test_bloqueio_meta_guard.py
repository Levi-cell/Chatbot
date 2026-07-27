import unittest
from unittest.mock import patch

from callback.webhook.services import bloqueio_meta_guard
from tests.helpers import FakeConn, FakeCursor, json_response_payload


WA_ID = "5571999999999"
PHONE_ID = "123456"


class BloqueioMetaGuardTests(unittest.TestCase):
    def test_cliente_marcado_tenta_meta_e_retorna_ignored(self):
        with patch.object(
            bloqueio_meta_guard,
            "_consultar_cliente_marcado_para_bloqueio",
            return_value={"banco_ok": True, "marcado": True},
        ), patch.object(
            bloqueio_meta_guard,
            "bloquear_usuario_meta",
        ) as bloquear_meta:
            response = (
                bloqueio_meta_guard
                .responder_se_cliente_marcado_para_bloqueio(
                    WA_ID,
                    PHONE_ID,
                )
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            json_response_payload(response),
            {
                "status": "ignored",
                "reason": "cliente_marcado_bloqueio_meta",
            },
        )
        bloquear_meta.assert_called_once_with(WA_ID, PHONE_ID)

    def test_meta_falha_mas_mensagem_continua_ignorada(self):
        with patch.object(
            bloqueio_meta_guard,
            "_consultar_cliente_marcado_para_bloqueio",
            return_value={"banco_ok": True, "marcado": True},
        ), patch.object(
            bloqueio_meta_guard,
            "bloquear_usuario_meta",
            side_effect=RuntimeError("Meta recusou"),
        ):
            response = (
                bloqueio_meta_guard
                .responder_se_cliente_marcado_para_bloqueio(
                    WA_ID,
                    PHONE_ID,
                )
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            json_response_payload(response)["reason"],
            "cliente_marcado_bloqueio_meta",
        )

    def test_cada_nova_mensagem_repete_tentativa_na_meta(self):
        with patch.object(
            bloqueio_meta_guard,
            "_consultar_cliente_marcado_para_bloqueio",
            return_value={"banco_ok": True, "marcado": True},
        ) as consultar, patch.object(
            bloqueio_meta_guard,
            "bloquear_usuario_meta",
            side_effect=RuntimeError("Meta recusou"),
        ) as bloquear_meta:
            primeira = (
                bloqueio_meta_guard
                .responder_se_cliente_marcado_para_bloqueio(
                    WA_ID,
                    PHONE_ID,
                )
            )
            segunda = (
                bloqueio_meta_guard
                .responder_se_cliente_marcado_para_bloqueio(
                    WA_ID,
                    PHONE_ID,
                )
            )

        self.assertEqual(primeira.status_code, 200)
        self.assertEqual(segunda.status_code, 200)
        self.assertEqual(consultar.call_count, 2)
        self.assertEqual(bloquear_meta.call_count, 2)

    def test_cliente_nao_marcado_segue_fluxo_normal(self):
        with patch.object(
            bloqueio_meta_guard,
            "_consultar_cliente_marcado_para_bloqueio",
            return_value={"banco_ok": True, "marcado": False},
        ), patch.object(
            bloqueio_meta_guard,
            "bloquear_usuario_meta",
        ) as bloquear_meta:
            response = (
                bloqueio_meta_guard
                .responder_se_cliente_marcado_para_bloqueio(
                    WA_ID,
                    PHONE_ID,
                )
            )

        self.assertIsNone(response)
        bloquear_meta.assert_not_called()

    def test_mesmo_wa_id_em_outro_phone_id_nao_bloqueia(self):
        def consultar(
            _wa_id,
            phone_id,
            nome_cliente=None,
        ):
            del nome_cliente
            return {
                "banco_ok": True,
                "marcado": phone_id == PHONE_ID,
            }

        with patch.object(
            bloqueio_meta_guard,
            "_consultar_cliente_marcado_para_bloqueio",
            side_effect=consultar,
        ), patch.object(
            bloqueio_meta_guard,
            "bloquear_usuario_meta",
        ) as bloquear_meta:
            response = (
                bloqueio_meta_guard
                .responder_se_cliente_marcado_para_bloqueio(
                    WA_ID,
                    "outro-phone-id",
                )
            )

        self.assertIsNone(response)
        bloquear_meta.assert_not_called()

    def test_consulta_da_lista_indisponivel_retorna_503(self):
        with patch.object(
            bloqueio_meta_guard,
            "_consultar_cliente_marcado_para_bloqueio",
            return_value={"banco_ok": False, "marcado": False},
        ), patch.object(
            bloqueio_meta_guard,
            "bloquear_usuario_meta",
        ) as bloquear_meta:
            response = (
                bloqueio_meta_guard
                .responder_se_cliente_marcado_para_bloqueio(
                    WA_ID,
                    PHONE_ID,
                )
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            json_response_payload(response),
            {
                "status": "unavailable",
                "reason": "blocklist_validation_unavailable",
            },
        )
        bloquear_meta.assert_not_called()

    def test_dados_incompletos_nao_consultam_banco_nem_meta(self):
        with patch.object(
            bloqueio_meta_guard,
            "_consultar_cliente_marcado_para_bloqueio",
        ) as consultar, patch.object(
            bloqueio_meta_guard,
            "bloquear_usuario_meta",
        ) as bloquear_meta:
            response = (
                bloqueio_meta_guard
                .responder_se_cliente_marcado_para_bloqueio(
                    None,
                    PHONE_ID,
                )
            )

        self.assertIsNone(response)
        consultar.assert_not_called()
        bloquear_meta.assert_not_called()

    def test_consulta_persistida_usa_wa_id_phone_id_e_fecha_conexao(self):
        cursor = FakeCursor(fetchone_result=(True,))
        conn = FakeConn(cursor=cursor)

        with patch.object(
            bloqueio_meta_guard,
            "get_conn",
            return_value=conn,
        ):
            resultado = (
                bloqueio_meta_guard
                ._consultar_cliente_marcado_para_bloqueio(
                    WA_ID,
                    PHONE_ID,
                )
            )

        self.assertEqual(
            resultado,
            {
                "banco_ok": True,
                "marcado": True,
            },
        )
        self.assertEqual(cursor.calls[0][1], (WA_ID, PHONE_ID))
        self.assertEqual(conn.commits, 1)
        self.assertEqual(conn.rollbacks, 0)
        self.assertTrue(conn.closed)

    def test_falha_na_consulta_faz_rollback_e_fecha_conexao(self):
        conn = FakeConn()

        with patch.object(
            bloqueio_meta_guard,
            "get_conn",
            return_value=conn,
        ), patch.object(
            bloqueio_meta_guard,
            "cliente_bloqueado_meta_existe_banco",
            side_effect=RuntimeError("banco caiu"),
        ), patch.object(
            bloqueio_meta_guard.logger,
            "exception",
        ):
            resultado = (
                bloqueio_meta_guard
                ._consultar_cliente_marcado_para_bloqueio(
                    WA_ID,
                    PHONE_ID,
                )
            )

        self.assertEqual(
            resultado,
            {
                "banco_ok": False,
                "marcado": False,
            },
        )
        self.assertEqual(conn.commits, 0)
        self.assertEqual(conn.rollbacks, 1)
        self.assertTrue(conn.closed)

    def test_limite_promove_para_denylist_antes_da_meta(self):
        conn = FakeConn()
        suspeita = {
            "id_conversa": 10,
            "id_cliente": 20,
            "nome_cliente": "Cliente Persistido",
            "id_unidade": 30,
            "phone_id_unidade": PHONE_ID,
            "turnos_sem_avanco": 12,
        }

        with patch.object(
            bloqueio_meta_guard,
            "get_conn",
            return_value=conn,
        ), patch.object(
            bloqueio_meta_guard,
            "cliente_bloqueado_meta_existe_banco",
            return_value=False,
        ), patch.object(
            bloqueio_meta_guard,
            "buscar_conversa_no_limite_sem_avanco",
            return_value=suspeita,
        ), patch.object(
            bloqueio_meta_guard,
            "registrar_cliente_bloqueado_meta_banco",
            return_value=99,
        ) as registrar:
            resultado = (
                bloqueio_meta_guard
                ._consultar_cliente_marcado_para_bloqueio(
                    WA_ID,
                    PHONE_ID,
                    nome_cliente="Nome Meta",
                )
            )

        self.assertEqual(
            resultado,
            {
                "banco_ok": True,
                "marcado": True,
            },
        )
        registrar.assert_called_once_with(
            20,
            WA_ID,
            30,
            PHONE_ID,
            conn.cursor(),
            nome_cliente="Cliente Persistido",
        )
        self.assertEqual(conn.commits, 1)
        self.assertEqual(conn.rollbacks, 0)
        self.assertTrue(conn.closed)

    def test_nome_do_profile_e_fallback_da_promocao(self):
        conn = FakeConn()
        suspeita = {
            "id_conversa": 10,
            "id_cliente": 20,
            "nome_cliente": None,
            "id_unidade": 30,
            "phone_id_unidade": PHONE_ID,
            "turnos_sem_avanco": 12,
        }

        with patch.object(
            bloqueio_meta_guard,
            "get_conn",
            return_value=conn,
        ), patch.object(
            bloqueio_meta_guard,
            "cliente_bloqueado_meta_existe_banco",
            return_value=False,
        ), patch.object(
            bloqueio_meta_guard,
            "buscar_conversa_no_limite_sem_avanco",
            return_value=suspeita,
        ), patch.object(
            bloqueio_meta_guard,
            "registrar_cliente_bloqueado_meta_banco",
            return_value=99,
        ) as registrar:
            bloqueio_meta_guard._consultar_cliente_marcado_para_bloqueio(
                WA_ID,
                PHONE_ID,
                nome_cliente="Nome Meta",
            )

        self.assertEqual(
            registrar.call_args.kwargs["nome_cliente"],
            "Nome Meta",
        )

    def test_falha_ao_persistir_promocao_faz_rollback(self):
        conn = FakeConn()
        suspeita = {
            "id_conversa": 10,
            "id_cliente": 20,
            "nome_cliente": "Cliente",
            "id_unidade": 30,
            "phone_id_unidade": PHONE_ID,
            "turnos_sem_avanco": 12,
        }

        with patch.object(
            bloqueio_meta_guard,
            "get_conn",
            return_value=conn,
        ), patch.object(
            bloqueio_meta_guard,
            "cliente_bloqueado_meta_existe_banco",
            return_value=False,
        ), patch.object(
            bloqueio_meta_guard,
            "buscar_conversa_no_limite_sem_avanco",
            return_value=suspeita,
        ), patch.object(
            bloqueio_meta_guard,
            "registrar_cliente_bloqueado_meta_banco",
            side_effect=RuntimeError("banco caiu"),
        ), patch.object(
            bloqueio_meta_guard.logger,
            "exception",
        ):
            resultado = (
                bloqueio_meta_guard
                ._consultar_cliente_marcado_para_bloqueio(
                    WA_ID,
                    PHONE_ID,
                )
            )

        self.assertEqual(
            resultado,
            {
                "banco_ok": False,
                "marcado": False,
            },
        )
        self.assertEqual(conn.commits, 0)
        self.assertEqual(conn.rollbacks, 1)
        self.assertTrue(conn.closed)


if __name__ == "__main__":
    unittest.main()
