import unittest
from unittest.mock import patch

from workers.worker_flow.transacoes import (
    encerramento_atendimento as encerramento,
)
from workers.worker_flow.transacoes import finalizacao_fila


def contexto_historico(texto, *, status_dependente=False):
    return {
        "id_conversa": 10,
        "id_etapa_origem_transicao": 4,
        "texto_cliente_atual": texto,
        "status_dependente": status_dependente,
    }


class EncerramentoEtapa4Tests(unittest.TestCase):
    def test_retry_reconstroi_encerramento_de_cliente_menor(self):
        resultado = encerramento.resolver_intencao_encerramento(
            contexto_historico("17"),
            {
                "resposta_ja_existia": True,
                "id_etapa_resultante": 4,
            },
        )

        self.assertEqual(
            resultado,
            {
                "motivo": encerramento.MOTIVO_CLIENTE_MENOR_18,
                "excluir_dependente": False,
            },
        )

    def test_retry_reconstroi_exclusao_de_dependente_menor(self):
        resultado = encerramento.resolver_intencao_encerramento(
            contexto_historico("4", status_dependente=True),
            {
                "resposta_ja_existia": True,
                "id_etapa_resultante": 4,
            },
        )

        self.assertEqual(
            resultado,
            {
                "motivo": encerramento.MOTIVO_DEPENDENTE_MENOR_5,
                "excluir_dependente": True,
            },
        )

    def test_idade_invalida_nao_inventa_encerramento_no_retry(self):
        resultado = encerramento.resolver_intencao_encerramento(
            contexto_historico("não sei"),
            {
                "resposta_ja_existia": True,
                "id_etapa_resultante": 4,
            },
        )

        self.assertIsNone(resultado)

    def test_aplicacao_exclui_dependente_antes_de_encerrar(self):
        chamadas = []

        with patch.object(
            encerramento,
            "excluir_dependente_da_conversa",
            side_effect=lambda *_args: chamadas.append("excluir"),
        ), patch.object(
            encerramento,
            "encerrar_conversa",
            side_effect=lambda *_args: chamadas.append("encerrar"),
        ):
            aplicado = encerramento.aplicar_encerramento_se_necessario(
                10,
                {
                    "motivo": encerramento.MOTIVO_DEPENDENTE_MENOR_5,
                    "excluir_dependente": True,
                },
                object(),
            )

        self.assertTrue(aplicado)
        self.assertEqual(chamadas, ["excluir", "encerrar"])

    def test_finalizacao_aplica_encerramento_antes_do_sent(self):
        chamadas = []
        mensagem = {
            "id_mensagem": 20,
            "cliente_telefone": "5575999999999",
            "id_phone_unidade": "123456",
        }
        contexto_banco = {
            "id_unidade": 30,
            "conversa": {
                "id_conversa": 10,
                "estado": "ativa",
            },
        }
        contexto_final = {
            "intencao_encerramento": {
                "motivo": encerramento.MOTIVO_CLIENTE_MENOR_18,
                "excluir_dependente": False,
            }
        }

        with patch.object(
            finalizacao_fila,
            "aplicar_encerramento_se_necessario",
            side_effect=lambda *_args: chamadas.append("encerrar") or True,
        ), patch.object(
            finalizacao_fila,
            "marcar_mensagem_como_enviada",
            side_effect=lambda *_args: chamadas.append("sent"),
        ):
            finalizacao_fila.finalizar_mensagem_processada(
                mensagem,
                contexto_banco,
                lock_version=7,
                cursor=object(),
                contexto_final=contexto_final,
            )

        self.assertEqual(chamadas, ["encerrar", "sent"])


if __name__ == "__main__":
    unittest.main()
