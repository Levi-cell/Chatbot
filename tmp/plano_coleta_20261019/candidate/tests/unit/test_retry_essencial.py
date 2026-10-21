import unittest
from unittest.mock import patch

from core.repositories.atendimento import conversas, fila
from tests.helpers import FakeCursor
from workers.tratamento_erros_externos import expection_process
from workers.worker_flow.suporte import estado_ciclo
from workers.worker_flow.transacoes import lock_conversa


class CursorComRowcounts(FakeCursor):
    def __init__(self, rowcounts):
        super().__init__()
        self._rowcounts = iter(rowcounts)

    def execute(self, sql, params=None):
        super().execute(sql, params)
        self.rowcount = next(self._rowcounts)


class RetryEssencialTests(unittest.TestCase):
    def test_falha_temporaria_reagenda_e_limite_atingido_deleta(self):
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
                object(),
            )

        self.assertEqual(resultado, "retry")
        reagendar.assert_called_once()

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
                erro,
                3,
                object(),
            )

        self.assertEqual(resultado, "delete")
        deletar.assert_called_once()
        reagendar.assert_not_called()

    def test_reagendamento_libera_processing_e_respeita_delay(self):
        cursor = FakeCursor(rowcount=1)

        linhas = fila.reagendar_mensagem(
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

    def test_ordem_da_fila_usa_cliente_phone_data_e_id(self):
        cursor = FakeCursor(fetchone_result=(True,))

        existe = fila.existe_mensagem_anterior_aberta_atendimento(
            "5571999999999",
            "123456",
            7,
            "2026-06-18T10:00:00Z",
            cursor,
        )

        sql, parametros = cursor.calls[0]
        self.assertTrue(existe)
        self.assertIn("cliente_telefone = %s", sql)
        self.assertIn("id_phone_unidade = %s", sql)
        self.assertIn("received_data_hora < %s", sql)
        self.assertIn("id_mensagem < %s", sql)
        self.assertEqual(
            parametros,
            (
                "5571999999999",
                "123456",
                7,
                "2026-06-18T10:00:00Z",
                "2026-06-18T10:00:00Z",
                7,
            ),
        )

    def test_vinculo_legado_so_e_reparado_sem_historico(self):
        cursor = CursorComRowcounts([0, 1])

        linhas = fila.vincular_mensagem_fila_a_conversa(
            7,
            10,
            cursor,
        )

        self.assertEqual(linhas, 1)
        self.assertEqual(len(cursor.calls), 2)
        sql_normal, _ = cursor.calls[0]
        sql_reparo, _ = cursor.calls[1]
        self.assertIn("status = 'processing'", sql_normal)
        self.assertIn("NOT EXISTS", sql_reparo)
        self.assertIn("historico.id_mensagem_fila", sql_reparo)

    def test_vinculo_com_historico_conflitante_falha_fechado(self):
        cursor = CursorComRowcounts([0, 0])

        linhas = fila.vincular_mensagem_fila_a_conversa(
            7,
            10,
            cursor,
        )

        self.assertEqual(linhas, 0)
        self.assertEqual(len(cursor.calls), 2)

    def test_lock_retorna_versao_e_unlock_usa_a_mesma_versao(self):
        cursor_lock = FakeCursor(fetchone_result=(True, 4))
        self.assertEqual(
        conversas.tentar_lock_conversa(10, cursor_lock),
            (True, 4),
        )

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
                object(),
                estado,
            )

        self.assertTrue(resultado)
        unlock.assert_called_once()
        self.assertEqual(unlock.call_args.args[:2], (10, 4))

    def test_lock_incompleto_nunca_tenta_unlock(self):
        with patch.object(lock_conversa, "unlock_conversa") as unlock:
            resultado = lock_conversa.liberar_lock_conversa_se_necessario(
                object(),
                estado_ciclo.criar_estado_ciclo(),
            )

        self.assertIsNone(resultado)
        unlock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
