import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.messages.componentes_compartilhados import (
    RODAPE_OPCAO_UNICA,
)
from core.integrations.whatsapp.messages.etapa5_messages import (
    BOTAO_ETAPA5_QUERO_AGENDAR,
    BOTAO_ETAPA5_TALVEZ_MAIS_TARDE,
    montar_mensagem_oferta_cliente_contexto_invalido_etapa5,
    montar_mensagem_oferta_cliente_etapa5,
    montar_mensagem_oferta_cliente_financeiro_etapa5,
    montar_mensagem_oferta_cliente_midia_etapa5,
    montar_mensagem_oferta_dependente_contexto_invalido_etapa5,
    montar_mensagem_oferta_dependente_etapa5,
    montar_mensagem_oferta_dependente_financeiro_etapa5,
    montar_mensagem_oferta_dependente_midia_etapa5,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders import (
    etapa5 as sender_module,
)


class FakeClienteWa:
    def __init__(self, resposta=None, erro=None):
        self.calls = []
        self.resposta = resposta or SimpleNamespace(id="wamid.bot.5")
        self.erro = erro

    def send_message(self, **kwargs):
        self.calls.append(kwargs)
        if self.erro:
            raise self.erro
        return self.resposta


def titulos_botoes(call):
    return [botao.title for botao in call["buttons"]]


class PywaSenderEtapa5Tests(unittest.TestCase):
    def _executar(self, funcao, *args):
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

        return cliente_wa.calls[0], resultado

    def test_oito_senders_usam_mensagem_e_botoes_corretos(self):
        casos = (
            (
                sender_module.enviar_etapa5_cliente,
                ("Edcarlos",),
                montar_mensagem_oferta_cliente_etapa5("Edcarlos"),
                None,
            ),
            (
                sender_module.enviar_etapa5_dependente,
                ("Alice",),
                montar_mensagem_oferta_dependente_etapa5("Alice"),
                None,
            ),
            (
                sender_module.enviar_etapa5_cliente_midia,
                (),
                montar_mensagem_oferta_cliente_midia_etapa5(),
                sender_module.TIPO_TRATAMENTO_MIDIA,
            ),
            (
                sender_module.enviar_etapa5_dependente_midia,
                ("Alice",),
                montar_mensagem_oferta_dependente_midia_etapa5("Alice"),
                sender_module.TIPO_TRATAMENTO_MIDIA,
            ),
            (
                sender_module.enviar_etapa5_cliente_financeiro,
                (),
                montar_mensagem_oferta_cliente_financeiro_etapa5(),
                sender_module.TIPO_TRATAMENTO_FINANCEIRO,
            ),
            (
                sender_module.enviar_etapa5_dependente_financeiro,
                ("Alice",),
                montar_mensagem_oferta_dependente_financeiro_etapa5(
                    "Alice"
                ),
                sender_module.TIPO_TRATAMENTO_FINANCEIRO,
            ),
            (
                sender_module.enviar_etapa5_cliente_contexto_invalido,
                (),
                montar_mensagem_oferta_cliente_contexto_invalido_etapa5(),
                sender_module.TIPO_TRATAMENTO_CONTEXTO_INVALIDO,
            ),
            (
                sender_module.enviar_etapa5_dependente_contexto_invalido,
                ("Alice",),
                montar_mensagem_oferta_dependente_contexto_invalido_etapa5(
                    "Alice"
                ),
                sender_module.TIPO_TRATAMENTO_CONTEXTO_INVALIDO,
            ),
        )

        for funcao, argumentos, mensagem, tratamento in casos:
            with self.subTest(funcao=funcao.__name__):
                call, resultado = self._executar(funcao, *argumentos)

                self.assertEqual(call["to"], "5571999999999")
                self.assertEqual(call["text"], mensagem)
                self.assertEqual(call["footer"], RODAPE_OPCAO_UNICA)
                self.assertEqual(
                    titulos_botoes(call),
                    [
                        BOTAO_ETAPA5_QUERO_AGENDAR,
                        BOTAO_ETAPA5_TALVEZ_MAIS_TARDE,
                    ],
                )
                self.assertTrue(resultado["enviou"])
                self.assertFalse(resultado["resposta_ja_existia"])
                self.assertEqual(resultado["mensagem_bot"], mensagem)
                self.assertEqual(
                    resultado["id_hash_msg_bot"],
                    "wamid.bot.5",
                )
                self.assertEqual(resultado["id_etapa_resultante"], 5)
                self.assertEqual(
                    resultado["tipo_mensagem"],
                    "interactive_button",
                )
                self.assertEqual(
                    resultado["rodape_mensagem"],
                    RODAPE_OPCAO_UNICA,
                )

                if tratamento:
                    self.assertTrue(resultado["tratamento"])
                    self.assertEqual(
                        resultado["tipo_tratamento"],
                        tratamento,
                    )
                else:
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
            with self.assertRaises(ErroEnvioMeta) as contexto:
                sender_module.enviar_etapa5_cliente(
                    "5571999999999",
                    "123456",
                    "Edcarlos",
                )

        self.assertEqual(contexto.exception.id_etapa, 5)
        self.assertEqual(
            contexto.exception.cliente_telefone,
            "5571999999999",
        )
        self.assertEqual(
            contexto.exception.phone_id_unidade,
            "123456",
        )


if __name__ == "__main__":
    unittest.main()
