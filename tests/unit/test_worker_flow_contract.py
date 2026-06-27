import inspect
import unittest

from workers.worker_flow.response_flow import flow_worker


class WorkerFlowContractTests(unittest.TestCase):
    def test_sent_fica_depois_do_flow_sender_e_da_persistencia_final(self):
        source = inspect.getsource(flow_worker.worker_flow)

        pos_valida_historico = source.index("contexto_historico = valida_historico")
        pos_flow_sender = source.index("contexto_envio = flow_sender")
        pos_atualizar_banco = source.index("contexto_final = atualizar_banco_com_contexto_final")
        pos_finalizar = source.index("finalizar_mensagem_processada")

        self.assertLess(pos_valida_historico, pos_flow_sender)
        self.assertLess(pos_flow_sender, pos_atualizar_banco)
        self.assertLess(pos_atualizar_banco, pos_finalizar)

    def test_erro_meta_nao_marca_sent(self):
        source = inspect.getsource(flow_worker.worker_flow)

        pos_except_meta = source.index("except ErroEnvioMeta as erro:")
        pos_except_banco_meta = source.index("except BancoFalhouAposEnvioMeta as erro:")
        bloco_meta = source[pos_except_meta:pos_except_banco_meta]

        self.assertIn("conn_ciclo.rollback()", bloco_meta)
        self.assertIn("handle_erro_generico", bloco_meta)
        self.assertNotIn("finalizar_mensagem_processada", bloco_meta)

    def test_banco_falhou_apos_meta_fica_explicito_no_log(self):
        source = inspect.getsource(flow_worker.worker_flow)

        self.assertIn("BancoFalhouAposEnvioMeta", source)
        self.assertIn("banco_falhou_apos_envio_meta", source)
        self.assertIn("risco=resposta_duplicada", source)

    def test_commit_rollback_close_continuam_no_worker(self):
        source = inspect.getsource(flow_worker.worker_flow)

        self.assertIn("conn_ciclo.commit()", source)
        self.assertIn("conn_ciclo.rollback()", source)
        self.assertIn("conn_ciclo.close()", source)


if __name__ == "__main__":
    unittest.main()
