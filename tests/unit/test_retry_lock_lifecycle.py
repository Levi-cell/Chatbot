import unittest
from unittest.mock import patch

from core.repositories import deletes, querys, updates
from tests.helpers import FakeCursor
from workers.tratamento_erros_externos import expection_process
from workers.worker_flow.suporte import estado_ciclo
from workers.worker_flow.transacoes import finalizacao_fila, lock_conversa


class RetryLockLifecycleTests(unittest.TestCase):
    def test_erro_sem_id_nao_altera_fila(self):
        with patch.object(
            expection_process,
            "deletar_mensagem_se_max_retry",
        ) as deletar, patch.object(
            expection_process,
            "reagendar_mensagem",
        ) as reagendar:
            resultado = expection_process.tratar_erro_processamento(
                None,
                RuntimeError("falha"),
                3,
                object(),
            )

        self.assertEqual(resultado, "no_action")
        deletar.assert_not_called()
        reagendar.assert_not_called()

    def test_terceiro_retry_deleta_sem_reagendar(self):
        cursor = object()

        with patch.object(
            expection_process,
            "deletar_mensagem_se_max_retry",
            return_value=1,
        ) as deletar, patch.object(
            expection_process,
            "reagendar_mensagem",
        ) as reagendar:
            resultado = expection_process.tratar_erro_processamento(
                7,
                RuntimeError("falha"),
                3,
                cursor,
            )

        self.assertEqual(resultado, "delete")
        deletar.assert_called_once_with(7, 3, cursor)
        reagendar.assert_not_called()

    def test_erro_antes_do_limite_reagenda(self):
        cursor = object()
        erro = RuntimeError("falha temporaria")

        with patch.object(
            expection_process,
            "deletar_mensagem_se_max_retry",
            return_value=0,
        ), patch.object(
            expection_process,
            "reagendar_mensagem",
            return_value=1,
        ) as reagendar:
            resultado = expection_process.tratar_erro_processamento(
                7,
                erro,
                3,
                cursor,
            )

        self.assertEqual(resultado, "retry")
        reagendar.assert_called_once_with(7, erro, 3, cursor)

    def test_fila_que_ja_mudou_nao_sofre_nova_acao(self):
        with patch.object(
            expection_process,
            "deletar_mensagem_se_max_retry",
            return_value=0,
        ), patch.object(
            expection_process,
            "reagendar_mensagem",
            return_value=0,
        ):
            resultado = expection_process.tratar_erro_processamento(
                7,
                RuntimeError("falha"),
                3,
                object(),
            )

        self.assertEqual(resultado, "no_action")

    def test_unidade_invalida_deleta_mensagem(self):
        cursor = object()

        with patch.object(
            expection_process,
            "deletar_mensagem_por_id",
            return_value=1,
        ) as deletar:
            resultado = expection_process.tratar_unidade_nao_encontrada(
                8,
                RuntimeError("unidade ausente"),
                cursor,
            )

        self.assertEqual(resultado, "delete")
        deletar.assert_called_once_with(8, cursor)

    def test_reagendamento_com_erro_retorna_para_pending(self):
        cursor = FakeCursor(rowcount=1)

        linhas = updates.reagendar_mensagem(
            7,
            RuntimeError("meta caiu"),
            3,
            cursor,
        )

        sql, parametros = cursor.calls[0]
        self.assertEqual(linhas, 1)
        self.assertIn("status = 'pending'", sql)
        self.assertIn("INTERVAL '2 minutes'", sql)
        self.assertIn("processing_started_at = NULL", sql)
        self.assertIn("retry_count < %s", sql)
        self.assertEqual(parametros, ("meta caiu", 7, 3))

    def test_reagendamento_por_ordem_compensa_retry(self):
        cursor = FakeCursor(rowcount=1)

        linhas = updates.reagendar_mensagem_sem_erro(
            9,
            cursor,
            delay_seconds=30,
        )

        sql, parametros = cursor.calls[0]
        self.assertEqual(linhas, 1)
        self.assertIn("status = 'pending'", sql)
        self.assertIn("processing_started_at = NULL", sql)
        self.assertIn("retry_count = GREATEST", sql)
        self.assertIn("last_error = NULL", sql)
        self.assertEqual(parametros, (30, 9))

    def test_delete_por_max_retry_exige_limite_atingido(self):
        cursor = FakeCursor(rowcount=1)

        linhas = deletes.deletar_mensagem_se_max_retry(7, 3, cursor)

        sql, parametros = cursor.calls[0]
        self.assertEqual(linhas, 1)
        self.assertIn("retry_count >= %s", sql)
        self.assertEqual(parametros, (7, 3))

    def test_finalizacao_marca_exatamente_a_mensagem_como_sent(self):
        mensagem = {
            "id_mensagem": 7,
            "cliente_telefone": "5571999999999",
            "id_phone_unidade": "123456",
        }
        contexto_banco = {
            "id_unidade": 2,
            "conversa": {
                "id_conversa": 10,
                "estado": "ativa",
            },
        }
        cursor = object()

        with patch.object(finalizacao_fila, "marcar_mensagem_como_enviada") as marcar:
            finalizacao_fila.finalizar_mensagem_processada(
                mensagem,
                contexto_banco,
                lock_version=4,
                cursor=cursor,
            )

        marcar.assert_called_once_with(7, cursor)

    def test_unlock_so_ocorre_com_lock_completo(self):
        cursor = object()
        estado_incompleto = estado_ciclo.criar_estado_ciclo()

        with patch.object(lock_conversa, "unlock_conversa") as unlock:
            resultado = lock_conversa.liberar_lock_conversa_se_necessario(
                cursor,
                estado_incompleto,
            )

        self.assertIsNone(resultado)
        unlock.assert_not_called()

    def test_unlock_usa_mesma_conversa_e_versao_adquirida(self):
        cursor = object()
        estado = estado_ciclo.criar_estado_ciclo()
        estado.update({
            "lock_ok": True,
            "id_conversa": 10,
            "lock_version": 4,
        })

        with patch.object(
            lock_conversa,
            "unlock_conversa",
            return_value=True,
        ) as unlock:
            resultado = lock_conversa.liberar_lock_conversa_se_necessario(
                cursor,
                estado,
            )

        self.assertTrue(resultado)
        unlock.assert_called_once_with(10, 4, cursor)

    def test_lock_sem_retorno_e_negado(self):
        cursor = FakeCursor(fetchone_result=None)

        resultado = querys.tentar_lock_conversa(10, cursor)

        self.assertEqual(resultado, (False, None))

    def test_lock_retorna_versao_para_unlock_condicional(self):
        cursor = FakeCursor(fetchone_result=(True, 4))

        resultado = querys.tentar_lock_conversa(10, cursor)

        sql, parametros = cursor.calls[0]
        self.assertEqual(resultado, (True, 4))
        self.assertIn("chatbot.lock_conversa", sql)
        self.assertEqual(parametros, (10,))

    def test_unlock_sem_versao_nao_consulta_banco(self):
        cursor = FakeCursor()

        resultado = querys.unlock_conversa(10, None, cursor)

        self.assertFalse(resultado)
        self.assertEqual(cursor.calls, [])


if __name__ == "__main__":
    unittest.main()
