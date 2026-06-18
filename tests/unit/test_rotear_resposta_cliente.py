import unittest
from unittest.mock import patch

import workers.worker_flow.response_flow.rotear_resposta_cliente as roteador_module
from workers.worker_flow.valida_resposta_cliente import (
    RESULTADO_MENSAGEM_FORA_DE_CONTEXTO,
    RESULTADO_RESPOSTA_VALIDA,
    RESULTADO_TIPO_MENSAGEM_NAO_SUPORTADO,
)


def contexto_historico_base():
    return {
        "id_conversa": 10,
        "id_etapa_cliente": 1,
        "id_etapa_resposta": 2,
        "tipo_mensagem_atual": "text",
        "mensagem_cliente_atual": {
            "id_mensagem_fila": 20,
            "id_hash_msg": "wamid.cliente",
            "cliente_telefone": "5571999999999",
            "id_phone_unidade": "123456",
        },
        "resposta_bot_para_mensagem_atual": None,
    }


class RotearRespostaClienteTests(unittest.TestCase):
    def test_resposta_valida_vai_para_flow_sender(self):
        contexto = contexto_historico_base()

        with patch.object(
            roteador_module,
            "validar_resposta_cliente",
            return_value={"resultado": RESULTADO_RESPOSTA_VALIDA},
        ), patch.object(
            roteador_module,
            "flow_sender",
            return_value={"origem": "sender"},
        ) as flow_sender:
            resultado = roteador_module.rotear_resposta_cliente(contexto)

        self.assertEqual(resultado, {"origem": "sender"})
        flow_sender.assert_called_once_with(contexto)

    def test_tipo_nao_suportado_vai_para_tratamento_de_tipo(self):
        contexto = contexto_historico_base()
        contexto_validacao = {
            "resultado": RESULTADO_TIPO_MENSAGEM_NAO_SUPORTADO,
            "tipo_tratamento": RESULTADO_TIPO_MENSAGEM_NAO_SUPORTADO,
        }

        with patch.object(
            roteador_module,
            "validar_resposta_cliente",
            return_value=contexto_validacao,
        ), patch.object(
            roteador_module,
            "flow_treat_unsupported_type",
            return_value={"origem": "unsupported_type"},
        ) as flow_treat_unsupported_type:
            resultado = roteador_module.rotear_resposta_cliente(contexto)

        self.assertEqual(resultado, {"origem": "unsupported_type"})
        flow_treat_unsupported_type.assert_called_once_with(
            contexto,
            contexto_validacao,
        )

    def test_fora_de_contexto_vai_para_tratamento_de_contexto(self):
        contexto = contexto_historico_base()
        contexto_validacao = {
            "resultado": RESULTADO_MENSAGEM_FORA_DE_CONTEXTO,
            "tipo_tratamento": RESULTADO_MENSAGEM_FORA_DE_CONTEXTO,
        }

        with patch.object(
            roteador_module,
            "validar_resposta_cliente",
            return_value=contexto_validacao,
        ), patch.object(
            roteador_module,
            "flow_treat_context",
            return_value={"origem": "context"},
        ) as flow_treat_context:
            resultado = roteador_module.rotear_resposta_cliente(contexto)

        self.assertEqual(resultado, {"origem": "context"})
        flow_treat_context.assert_called_once_with(
            contexto,
            contexto_validacao,
        )


if __name__ == "__main__":
    unittest.main()
