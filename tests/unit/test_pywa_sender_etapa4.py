import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.messages.etapa4_messages import (
    montar_mensagem_cliente_menor_18_etapa4,
    montar_mensagem_contexto_idade_dependente_invalida_etapa4,
    montar_mensagem_contexto_idade_invalida_etapa4,
    montar_mensagem_dependente_menor_5_etapa4,
    montar_mensagem_idade_dependente_etapa4,
    montar_mensagem_idade_dependente_etapa4_financeiro,
    montar_mensagem_idade_dependente_etapa4_midia,
    montar_mensagem_idade_etapa4,
    montar_mensagem_idade_etapa4_financeiro,
    montar_mensagem_idade_etapa4_midia,
    montar_mensagem_idade_acima_99_etapa4,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders import (
    etapa4 as sender_module,
)


class FakeClienteWa:
    def __init__(self, erro=None):
        self.calls = []
        self.erro = erro

    def send_message(self, **kwargs):
        self.calls.append(kwargs)
        if self.erro:
            raise self.erro
        return SimpleNamespace(id="wamid.bot.4")


class PywaSenderEtapa4Tests(unittest.TestCase):
    def _executar_sender(self, funcao, *args):
        cliente_wa = FakeClienteWa()

        with patch.object(
            sender_module,
            "conta_wa",
            return_value=cliente_wa,
        ):
            resultado = funcao(
                "5571999999999",
                "123456",
                *args,
            )

        return cliente_wa, resultado

    def test_envios_normais_perguntam_idade_e_preservam_etapa4(self):
        casos = (
            (
                sender_module.enviar_etapa4_cliente,
                (),
                montar_mensagem_idade_etapa4(),
            ),
            (
                sender_module.enviar_etapa4_dependente,
                ("Alice",),
                montar_mensagem_idade_dependente_etapa4("Alice"),
            ),
        )

        for funcao, args, mensagem in casos:
            with self.subTest(funcao=funcao.__name__):
                cliente_wa, resultado = self._executar_sender(
                    funcao,
                    *args,
                )

                self.assertEqual(cliente_wa.calls[0]["text"], mensagem)
                self.assertEqual(resultado["id_hash_msg_bot"], "wamid.bot.4")
                self.assertEqual(resultado["id_etapa_resultante"], 4)
                self.assertNotIn("tratamento", resultado)

    def test_tratamentos_preservam_etapa4(self):
        casos = (
            (
                sender_module.enviar_etapa4_cliente_midia,
                (),
                montar_mensagem_idade_etapa4_midia(),
                sender_module.TIPO_TRATAMENTO_MIDIA,
            ),
            (
                sender_module.enviar_etapa4_dependente_midia,
                ("Alice",),
                montar_mensagem_idade_dependente_etapa4_midia("Alice"),
                sender_module.TIPO_TRATAMENTO_MIDIA,
            ),
            (
                sender_module.enviar_etapa4_cliente_financeiro,
                (),
                montar_mensagem_idade_etapa4_financeiro(),
                sender_module.TIPO_TRATAMENTO_FINANCEIRO,
            ),
            (
                sender_module.enviar_etapa4_dependente_financeiro,
                ("Alice",),
                montar_mensagem_idade_dependente_etapa4_financeiro(
                    "Alice"
                ),
                sender_module.TIPO_TRATAMENTO_FINANCEIRO,
            ),
            (
                sender_module.enviar_etapa4_cliente_contexto_idade_invalida,
                (),
                montar_mensagem_contexto_idade_invalida_etapa4(),
                sender_module.TIPO_TRATAMENTO_IDADE_INVALIDA,
            ),
            (
                sender_module.enviar_etapa4_dependente_contexto_idade_invalida,
                ("Alice",),
                montar_mensagem_contexto_idade_dependente_invalida_etapa4(
                    "Alice"
                ),
                sender_module.TIPO_TRATAMENTO_IDADE_INVALIDA,
            ),
        )

        for funcao, args, mensagem, tipo_tratamento in casos:
            with self.subTest(funcao=funcao.__name__):
                cliente_wa, resultado = self._executar_sender(
                    funcao,
                    *args,
                )

                self.assertEqual(cliente_wa.calls[0]["text"], mensagem)
                self.assertEqual(resultado["id_etapa_resultante"], 4)
                self.assertTrue(resultado["tratamento"])
                self.assertEqual(
                    resultado["tipo_tratamento"],
                    tipo_tratamento,
                )

    def test_encerramentos_por_idade_nao_usam_botao_nem_tratamento(self):
        casos = (
            (
                sender_module.enviar_etapa4_cliente_menor_18,
                (),
                montar_mensagem_cliente_menor_18_etapa4(),
            ),
            (
                sender_module.enviar_etapa4_dependente_menor_5,
                ("Alice",),
                montar_mensagem_dependente_menor_5_etapa4("Alice"),
            ),
        )

        for funcao, args, mensagem in casos:
            with self.subTest(funcao=funcao.__name__):
                cliente_wa, resultado = self._executar_sender(
                    funcao,
                    *args,
                )

                self.assertEqual(
                    cliente_wa.calls[0],
                    {
                        "to": "5571999999999",
                        "text": mensagem,
                    },
                )
                self.assertNotIn("tratamento", resultado)
                self.assertEqual(resultado["id_etapa_resultante"], 4)

    def test_acima_de_99_envia_numero_comercial_sem_tratamento(self):
        cliente_wa, resultado = self._executar_sender(
            sender_module.enviar_etapa4_idade_acima_99,
            "557536321234",
        )

        self.assertEqual(
            cliente_wa.calls[0]["text"],
            montar_mensagem_idade_acima_99_etapa4("557536321234"),
        )
        self.assertEqual(resultado["id_etapa_resultante"], 4)
        self.assertNotIn("tratamento", resultado)

    def test_meta_falhou_levanta_exception_controlada(self):
        cliente_wa = FakeClienteWa(
            erro=RuntimeError("meta indisponivel")
        )

        with patch.object(
            sender_module,
            "conta_wa",
            return_value=cliente_wa,
        ):
            with self.assertRaises(ErroEnvioMeta) as ctx:
                sender_module.enviar_etapa4_cliente(
                    "5571999999999",
                    "123456",
                )

        self.assertEqual(ctx.exception.id_etapa, 4)
        self.assertEqual(ctx.exception.cliente_telefone, "5571999999999")
        self.assertEqual(ctx.exception.phone_id_unidade, "123456")


if __name__ == "__main__":
    unittest.main()
