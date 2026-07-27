import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

from django.contrib import admin

from callback.webhook.services import bloqueio_meta_guard, post_flow
from core.repositories.seguranca import suspeita_bot
from tests.helpers import FakeConn
from webhook import admin as webhook_admin
from webhook.models import ClienteBloqueadoMeta
from workers.worker_flow.transacoes import persistencia_resposta
from workers.worker_flow.transacoes.movimento_conversa import (
    MOVIMENTO_SEM_AVANCO,
    MOVIMENTO_TRANSICAO,
)


WA_ID = "5571999999999"
PHONE_ID = "123456"


class RepositorioTurnosSemAvancoTests(unittest.TestCase):
    def test_incremento_e_limitado_a_doze(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = (12,)

        contador = suspeita_bot.incrementar_turnos_sem_avanco(
            10,
            cursor,
        )

        self.assertEqual(contador, 12)
        sql, parametros = cursor.execute.call_args.args
        self.assertIn("LEAST", sql)
        self.assertEqual(
            parametros,
            (suspeita_bot.LIMITE_TURNOS_SEM_AVANCO, 10),
        )

    def test_reset_define_zero(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = (0,)

        contador = suspeita_bot.resetar_turnos_sem_avanco(
            10,
            cursor,
        )

        self.assertEqual(contador, 0)
        self.assertEqual(cursor.execute.call_args.args[1], (10,))

    def test_consulta_isola_wa_id_phone_id_e_conversa_ativa(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = (
            10,
            20,
            "Cliente",
            30,
            PHONE_ID,
            12,
        )

        resultado = suspeita_bot.buscar_conversa_no_limite_sem_avanco(
            WA_ID,
            PHONE_ID,
            cursor,
        )

        sql, parametros = cursor.execute.call_args.args
        self.assertIn("cliente.waid_telefone = %s", sql)
        self.assertIn("unidade.phone_number_id = %s", sql)
        self.assertIn("conversa.status_ativa = TRUE", sql)
        self.assertNotIn("FOR UPDATE", sql)
        self.assertEqual(
            parametros,
            (WA_ID, PHONE_ID, suspeita_bot.LIMITE_TURNOS_SEM_AVANCO),
        )
        self.assertEqual(resultado["id_conversa"], 10)
        self.assertEqual(resultado["turnos_sem_avanco"], 12)


class WorkerTurnosSemAvancoTests(unittest.TestCase):
    def test_tratamento_novo_incrementa(self):
        cursor = object()

        with patch.object(
            persistencia_resposta,
            "incrementar_turnos_sem_avanco",
            return_value=6,
        ) as incrementar, patch.object(
            persistencia_resposta,
            "resetar_turnos_sem_avanco",
        ) as resetar:
            resultado = (
                persistencia_resposta._persistir_turnos_sem_avanco(
                    id_conversa=10,
                    movimento=MOVIMENTO_SEM_AVANCO,
                    tratamento=True,
                    historico_bot_inserido=True,
                    cursor=cursor,
                )
            )

        self.assertEqual(resultado, 6)
        incrementar.assert_called_once_with(10, cursor)
        resetar.assert_not_called()

    def test_retry_de_tratamento_nao_incrementa(self):
        with patch.object(
            persistencia_resposta,
            "incrementar_turnos_sem_avanco",
        ) as incrementar:
            resultado = (
                persistencia_resposta._persistir_turnos_sem_avanco(
                    id_conversa=10,
                    movimento=MOVIMENTO_SEM_AVANCO,
                    tratamento=True,
                    historico_bot_inserido=False,
                    cursor=object(),
                )
            )

        self.assertIsNone(resultado)
        incrementar.assert_not_called()

    def test_resposta_sem_tratamento_e_sem_transicao_nao_incrementa(self):
        with patch.object(
            persistencia_resposta,
            "incrementar_turnos_sem_avanco",
        ) as incrementar:
            resultado = (
                persistencia_resposta._persistir_turnos_sem_avanco(
                    id_conversa=10,
                    movimento=MOVIMENTO_SEM_AVANCO,
                    tratamento=False,
                    historico_bot_inserido=True,
                    cursor=object(),
                )
            )

        self.assertIsNone(resultado)
        incrementar.assert_not_called()

    def test_transicao_valida_reseta_mesmo_em_reaplicacao(self):
        cursor = object()

        with patch.object(
            persistencia_resposta,
            "resetar_turnos_sem_avanco",
            return_value=0,
        ) as resetar, patch.object(
            persistencia_resposta,
            "incrementar_turnos_sem_avanco",
        ) as incrementar:
            resultado = (
                persistencia_resposta._persistir_turnos_sem_avanco(
                    id_conversa=10,
                    movimento=MOVIMENTO_TRANSICAO,
                    tratamento=False,
                    historico_bot_inserido=False,
                    cursor=cursor,
                )
            )

        self.assertEqual(resultado, 0)
        resetar.assert_called_once_with(10, cursor)
        incrementar.assert_not_called()


class WebhookSuspeitaBotTests(unittest.TestCase):
    def test_limite_promove_para_denylist_antes_da_meta(self):
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
            return_value=99,
        ) as registrar:
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
        registrar.assert_called_once_with(
            20,
            WA_ID,
            30,
            PHONE_ID,
            conn.cursor(),
            nome_cliente="Cliente",
        )
        self.assertEqual(conn.commits, 1)
        self.assertEqual(conn.rollbacks, 0)
        self.assertTrue(conn.closed)

    def test_abaixo_do_limite_nao_cria_denylist(self):
        conn = FakeConn()

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
            return_value=None,
        ), patch.object(
            bloqueio_meta_guard,
            "registrar_cliente_bloqueado_meta_banco",
        ) as registrar:
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
                "marcado": False,
            },
        )
        registrar.assert_not_called()

    def test_falha_ao_persistir_promocao_retorna_estado_indisponivel(self):
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


class CoberturaAdicionalTests(unittest.TestCase):
    def test_isolamento_e_conversa_encerrada(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = None
        limite = suspeita_bot.LIMITE_TURNOS_SEM_AVANCO
        for wa, phone in (("a", "1"), ("a", "2"), ("b", "1")):
            suspeita_bot.buscar_conversa_no_limite_sem_avanco(wa, phone, cursor)
        self.assertEqual([c.args[1] for c in cursor.execute.call_args_list], [("a", "1", limite), ("a", "2", limite), ("b", "1", limite)])
        self.assertIn("conversa.status_ativa = TRUE", cursor.execute.call_args.args[0])

    def test_nome_profile_e_fallback_persistido(self):
        payload = {"entry": [{"changes": [{"value": {"contacts": [{"profile": {"name": " Nome Meta "}}]}}]}]}
        self.assertEqual(post_flow._extrair_nome_cliente(payload), "Nome Meta")
        conn = FakeConn()
        suspeita = {"id_conversa": 10, "id_cliente": 20, "nome_cliente": None, "id_unidade": 30, "phone_id_unidade": PHONE_ID, "turnos_sem_avanco": 12}
        with patch.object(bloqueio_meta_guard, "get_conn", return_value=conn), patch.object(bloqueio_meta_guard, "cliente_bloqueado_meta_existe_banco", return_value=False), patch.object(bloqueio_meta_guard, "buscar_conversa_no_limite_sem_avanco", return_value=suspeita), patch.object(bloqueio_meta_guard, "registrar_cliente_bloqueado_meta_banco", return_value=99) as registrar:
            bloqueio_meta_guard._consultar_cliente_marcado_para_bloqueio(WA_ID, PHONE_ID, nome_cliente="Nome Meta")
        self.assertEqual(registrar.call_args.kwargs["nome_cliente"], "Nome Meta")

    def test_falha_meta_e_retry_sequencial(self):
        with patch.object(bloqueio_meta_guard, "_consultar_cliente_marcado_para_bloqueio", return_value={"banco_ok": True, "marcado": True}), patch.object(bloqueio_meta_guard, "bloquear_usuario_meta", side_effect=[RuntimeError("falha"), None]) as bloquear:
            respostas = [bloqueio_meta_guard.responder_se_cliente_marcado_para_bloqueio(WA_ID, PHONE_ID) for _ in range(2)]
        self.assertTrue(all(r.status_code == 200 for r in respostas))
        self.assertEqual(bloquear.call_args_list, [call(WA_ID, PHONE_ID), call(WA_ID, PHONE_ID)])

    def test_admin_reseta_antes_de_excluir_denylist(self):
        ma = webhook_admin.ClienteBloqueadoMetaAdmin(ClienteBloqueadoMeta, admin.site)
        request = SimpleNamespace(user="operador")
        obj = SimpleNamespace(id_cliente_id=20, id_unidade_id=30, wa_id_cliente=WA_ID, phone_id_unidade=PHONE_ID)
        qs = MagicMock()
        with patch.object(webhook_admin.Conversa.objects, "filter", return_value=qs) as filtrar, patch.object(admin.ModelAdmin, "delete_model") as excluir:
            ma.delete_model(request, obj)
        filtrar.assert_called_once_with(id_cliente_id=20, id_unidade_id=30, status_ativa=True)
        qs.update.assert_called_once_with(turnos_sem_avanco=0)
        excluir.assert_called_once_with(request, obj)


if __name__ == "__main__":
    unittest.main()
