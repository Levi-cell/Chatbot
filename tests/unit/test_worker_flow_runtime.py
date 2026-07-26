import unittest
from contextlib import ExitStack
from datetime import datetime
from unittest.mock import patch

from tests.helpers import FakeConn, FakeCursor
from workers.worker_flow.response_flow import flow_worker
from workers.worker_flow.suporte import estado_ciclo


class PararWorker(BaseException):
    pass


def registro_fila():
    return (
        7,
        "5571999999999",
        "Ola",
        "text",
        "123456",
        "5571000000000",
        datetime(2026, 6, 18, 10, 0),
        "wamid.cliente.7",
        1,
    )


def contexto_banco():
    return {
        "id_unidade": 2,
        "id_cliente": 6,
        "cliente_telefone": "5571999999999",
        "id_phone_unidade": "123456",
        "cliente_inserido": False,
        "cliente_cache_pendente": False,
        "conversa": {
            "id_conversa": 10,
            "estado": "ativa",
        },
    }


def contexto_historico():
    return {
        "id_conversa": 10,
        "id_etapa_atual": None,
        "id_etapa_cliente": 1,
        "id_etapa_resposta": 1,
        "mensagem_cliente_inserida": True,
        "mensagem_cliente_atual": {
            "id_mensagem_fila": 7,
            "id_hash_msg": "wamid.cliente.7",
            "cliente_telefone": "5571999999999",
            "id_phone_unidade": "123456",
        },
        "resposta_bot_para_mensagem_atual": None,
        "retry_count": 1,
    }


def contexto_envio():
    return {
        "enviou": True,
        "resposta_ja_existia": False,
        "id_hash_msg_bot": "wamid.bot.7",
        "id_etapa_resultante": 1,
        "tipo_mensagem": "text",
    }


def contexto_final():
    return {
        "id_etapa_resultante": 1,
        "resposta_ja_existia": False,
        "id_hash_msg_bot": "wamid.bot.7",
    }


class WorkerFlowRuntimeTests(unittest.TestCase):
    def test_fila_vazia_aguarda_tres_segundos(self):
        with (
            patch.object(estado_ciclo.time, "sleep") as sleep,
            patch.object(estado_ciclo.logger, "debug") as log_debug,
        ):
            estado_ciclo.aguardar_fila_vazia()

        sleep.assert_called_once_with(3)
        log_debug.assert_called_once_with(
            "fila_vazia | acao=aguardar segundos=3"
        )

    def test_erro_operacional_psycopg3_reinicia_conexao(self):
        erro = flow_worker.psycopg.OperationalError("conexao indisponivel")

        with ExitStack() as stack:
            stack.enter_context(patch("builtins.print"))
            stack.enter_context(patch.object(
                flow_worker,
                "get_conn",
                side_effect=[erro, PararWorker()],
            ))
            tratar_conexao = stack.enter_context(patch.object(
                flow_worker,
                "handle_erro_conexao",
                return_value=10,
            ))

            with self.assertRaises(PararWorker):
                flow_worker.worker_flow()

        tratar_conexao.assert_called_once_with(erro, 5)

    def test_fila_vazia_fecha_conexao_antes_de_aguardar(self):
        conn = FakeConn(FakeCursor())

        with ExitStack() as stack:
            stack.enter_context(patch("builtins.print"))
            stack.enter_context(patch.object(
                flow_worker,
                "get_conn",
                side_effect=[conn, PararWorker()],
            ))
            stack.enter_context(patch.object(
                flow_worker,
                "pegar_mensagens_da_fila",
                return_value=None,
            ))
            close = stack.enter_context(patch.object(
                conn,
                "close",
                wraps=conn.close,
            ))

            def verificar_conexao_fechada():
                self.assertTrue(conn.closed)

            stack.enter_context(patch.object(
                flow_worker,
                "aguardar_fila_vazia",
                side_effect=verificar_conexao_fechada,
            ))

            with self.assertRaises(PararWorker):
                flow_worker.worker_flow()

        close.assert_called_once_with()
        self.assertEqual(conn.commits, 1)
        self.assertEqual(conn.rollbacks, 0)

    def _patch_fluxo_base(self, stack, conn, eventos):
        stack.enter_context(patch("builtins.print"))
        stack.enter_context(patch.object(
            flow_worker,
            "get_conn",
            side_effect=[conn, PararWorker()],
        ))
        stack.enter_context(patch.object(
            flow_worker,
            "pegar_mensagens_da_fila",
            return_value=registro_fila(),
        ))
        stack.enter_context(patch.object(
            flow_worker,
            "validar_banco_mensagem",
            side_effect=lambda *_args: eventos.append("validar_banco") or contexto_banco(),
        ))
        stack.enter_context(patch.object(
            flow_worker,
            "vincular_mensagem_fila_a_conversa",
            side_effect=lambda *_args: eventos.append("vincular_conversa") or 1,
        ))
        stack.enter_context(patch.object(
            flow_worker,
            "confirmar_cache_cliente_se_pendente",
            return_value=False,
        ))
        stack.enter_context(patch.object(
            flow_worker,
            "tentar_lock_conversa",
            side_effect=lambda *_args: eventos.append("adquirir_lock") or (True, 4),
        ))
        stack.enter_context(patch.object(
            flow_worker,
            "reagendar_se_houver_mensagem_anterior",
            side_effect=lambda *_args: eventos.append("verificar_ordem") or False,
        ))
        stack.enter_context(patch.object(
            flow_worker,
            "valida_historico",
            side_effect=lambda *_args: eventos.append("persistir_cliente") or contexto_historico(),
        ))
        stack.enter_context(patch.object(
            flow_worker,
            "flow_sender",
            side_effect=lambda *_args: eventos.append("enviar_meta") or contexto_envio(),
        ))
        stack.enter_context(patch.object(
            flow_worker,
            "liberar_lock_conversa_se_necessario",
            side_effect=lambda *_args: eventos.append("liberar_lock") or True,
        ))
        stack.enter_context(patch.object(
            flow_worker,
            "handle_erro_generico",
        ))

    def test_mensagem_anterior_reagenda_antes_de_validar_banco(self):
        conn = FakeConn(FakeCursor())

        with ExitStack() as stack:
            stack.enter_context(patch("builtins.print"))
            stack.enter_context(patch.object(
                flow_worker,
                "get_conn",
                side_effect=[conn, PararWorker()],
            ))
            stack.enter_context(patch.object(
                flow_worker,
                "pegar_mensagens_da_fila",
                return_value=registro_fila(),
            ))
            barreira = stack.enter_context(patch.object(
                flow_worker,
                "reagendar_se_houver_mensagem_anterior",
                return_value=True,
            ))
            validar = stack.enter_context(patch.object(
                flow_worker,
                "validar_banco_mensagem",
            ))
            lock = stack.enter_context(patch.object(
                flow_worker,
                "tentar_lock_conversa",
            ))
            vincular = stack.enter_context(patch.object(
                flow_worker,
                "vincular_mensagem_fila_a_conversa",
            ))

            with self.assertRaises(PararWorker):
                flow_worker.worker_flow()

        barreira.assert_called_once()
        validar.assert_not_called()
        lock.assert_not_called()
        vincular.assert_not_called()
        self.assertEqual(conn.commits, 2)
        self.assertEqual(conn.rollbacks, 0)
        self.assertTrue(conn.closed)

    def test_ciclo_normal_persiste_resposta_antes_de_marcar_sent(self):
        conn = FakeConn(FakeCursor())
        eventos = []

        with ExitStack() as stack:
            self._patch_fluxo_base(stack, conn, eventos)
            stack.enter_context(patch.object(
                flow_worker,
                "atualizar_banco_com_contexto_final",
                side_effect=lambda *_args: eventos.append("persistir_bot") or contexto_final(),
            ))
            finalizar = stack.enter_context(patch.object(
                flow_worker,
                "finalizar_mensagem_processada",
                side_effect=lambda *_args: (
                    eventos.append("marcar_sent")
                    or {"atendimento_encerrado": False}
                ),
            ))

            with self.assertRaises(PararWorker):
                flow_worker.worker_flow()

        self.assertEqual(
            eventos,
            [
                "verificar_ordem",
                "validar_banco",
                "adquirir_lock",
                "vincular_conversa",
                "persistir_cliente",
                "enviar_meta",
                "persistir_bot",
                "marcar_sent",
                "liberar_lock",
            ],
        )
        finalizar.assert_called_once()
        self.assertEqual(conn.commits, 7)
        self.assertEqual(conn.rollbacks, 0)
        self.assertTrue(conn.closed)

    def test_checkpoint_cache_e_atomicidade_vinculo_historico(self):
        conn = FakeConn(FakeCursor())
        eventos = []
        commits_observados = {}

        def confirmar_cache(*_args):
            commits_observados["cache"] = conn.commits
            return False

        def vincular_conversa(*_args):
            commits_observados["vinculo"] = conn.commits
            return 1

        def persistir_historico(*_args):
            commits_observados["historico"] = conn.commits
            return contexto_historico()

        with ExitStack() as stack:
            self._patch_fluxo_base(stack, conn, eventos)
            stack.enter_context(patch.object(
                flow_worker,
                "confirmar_cache_cliente_se_pendente",
                side_effect=confirmar_cache,
            ))
            stack.enter_context(patch.object(
                flow_worker,
                "vincular_mensagem_fila_a_conversa",
                side_effect=vincular_conversa,
            ))
            stack.enter_context(patch.object(
                flow_worker,
                "valida_historico",
                side_effect=persistir_historico,
            ))
            stack.enter_context(patch.object(
                flow_worker,
                "atualizar_banco_com_contexto_final",
                return_value=contexto_final(),
            ))
            stack.enter_context(patch.object(
                flow_worker,
                "finalizar_mensagem_processada",
                return_value={"atendimento_encerrado": False},
            ))

            with self.assertRaises(PararWorker):
                flow_worker.worker_flow()

        self.assertEqual(commits_observados["cache"], 2)
        self.assertEqual(commits_observados["vinculo"], 3)
        self.assertEqual(commits_observados["historico"], 3)

    def test_lock_recusado_reagenda_sem_consumir_retry(self):
        conn = FakeConn(FakeCursor())
        eventos = []

        with ExitStack() as stack:
            self._patch_fluxo_base(stack, conn, eventos)
            stack.enter_context(patch.object(
                flow_worker,
                "tentar_lock_conversa",
                return_value=(False, None),
            ))
            reagendar = stack.enter_context(patch.object(
                flow_worker,
                "reagendar_mensagem_sem_erro",
                return_value=1,
            ))
            vincular = stack.enter_context(patch.object(
                flow_worker,
                "vincular_mensagem_fila_a_conversa",
            ))
            historico = stack.enter_context(patch.object(
                flow_worker,
                "valida_historico",
            ))
            enviar = stack.enter_context(patch.object(
                flow_worker,
                "flow_sender",
            ))
            stack.enter_context(patch.object(
                flow_worker,
                "liberar_lock_conversa_se_necessario",
                return_value=None,
            ))

            with self.assertRaises(PararWorker):
                flow_worker.worker_flow()

        reagendar.assert_called_once_with(
            7,
            conn.cursor_obj,
            delay_seconds=5,
        )
        vincular.assert_not_called()
        historico.assert_not_called()
        enviar.assert_not_called()
        self.assertEqual(conn.commits, 4)
        self.assertEqual(conn.rollbacks, 0)
        self.assertTrue(conn.closed)

    def test_vinculo_inconsistente_reagenda_sem_enviar(self):
        conn = FakeConn(FakeCursor())
        eventos = []

        with ExitStack() as stack:
            self._patch_fluxo_base(stack, conn, eventos)
            stack.enter_context(patch.object(
                flow_worker,
                "vincular_mensagem_fila_a_conversa",
                return_value=0,
            ))
            tratar_erro = stack.enter_context(patch.object(
                flow_worker,
                "handle_erro_generico",
            ))
            reagendar = stack.enter_context(patch.object(
                flow_worker,
                "reagendar_mensagem_sem_erro",
                return_value=1,
            ))
            aviso = stack.enter_context(patch.object(
                flow_worker.logger,
                "critical",
            ))
            persistir_bot = stack.enter_context(patch.object(
                flow_worker,
                "atualizar_banco_com_contexto_final",
            ))
            finalizar = stack.enter_context(patch.object(
                flow_worker,
                "finalizar_mensagem_processada",
            ))

            with self.assertRaises(PararWorker):
                flow_worker.worker_flow()

        tratar_erro.assert_not_called()
        persistir_bot.assert_not_called()
        finalizar.assert_not_called()
        reagendar.assert_called_once_with(7, conn.cursor_obj, delay_seconds=300)
        self.assertEqual(
            eventos,
            [
                "verificar_ordem",
                "validar_banco",
                "adquirir_lock",
                "liberar_lock",
            ],
        )
        aviso.assert_called_once()
        self.assertIn(
            "motivo=historico_conflitante_ou_fila_ausente",
            aviso.call_args.args[0],
        )
        self.assertEqual(conn.rollbacks, 0)
        self.assertTrue(conn.closed)

    def test_falha_do_banco_apos_meta_reagenda_sem_marcar_sent(self):
        conn = FakeConn(FakeCursor())
        eventos = []

        with ExitStack() as stack:
            self._patch_fluxo_base(stack, conn, eventos)
            stack.enter_context(patch.object(
                flow_worker,
                "atualizar_banco_com_contexto_final",
                side_effect=RuntimeError("banco caiu apos envio"),
            ))
            finalizar = stack.enter_context(patch.object(
                flow_worker,
                "finalizar_mensagem_processada",
                side_effect=lambda *_args: (
                    eventos.append("marcar_sent")
                    or {"atendimento_encerrado": False}
                ),
            ))
            tratar_erro = stack.enter_context(patch.object(
                flow_worker,
                "handle_erro_generico",
            ))

            with self.assertRaises(PararWorker):
                flow_worker.worker_flow()

        finalizar.assert_not_called()
        tratar_erro.assert_called_once()
        self.assertNotIn("marcar_sent", eventos)
        self.assertEqual(conn.rollbacks, 1)
        self.assertEqual(conn.commits, 6)
        self.assertTrue(conn.closed)


if __name__ == "__main__":
    unittest.main()
