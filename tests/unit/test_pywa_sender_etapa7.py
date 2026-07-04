import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.messages.componentes_compartilhados import (
    CABECALHO_ETAPA7_RETORNO,
    RODAPE_OPCAO_UNICA,
)
from core.integrations.whatsapp.messages.etapa7_messages import (
    BOTAO_ETAPA7_QUERO_AGENDAR,
    BOTAO_ETAPA7_TALVEZ_MAIS_TARDE,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders import (
    etapa7 as sender_module,
)


class FakeClienteWa:
    def __init__(self, erro=None):
        self.calls = []
        self.erro = erro

    def send_message(self, **kwargs):
        self.calls.append(kwargs)
        if self.erro:
            raise self.erro
        return SimpleNamespace(id="wamid.bot.7")


class PywaSenderEtapa7Tests(unittest.TestCase):
    def test_oito_senders_usam_botoes_e_contexto_da_etapa7(self):
        casos = (
            (sender_module.enviar_etapa7_cliente, (), None),
            (sender_module.enviar_etapa7_dependente, ("Alice",), None),
            (
                sender_module.enviar_etapa7_cliente_midia,
                (),
                sender_module.TIPO_TRATAMENTO_MIDIA,
            ),
            (
                sender_module.enviar_etapa7_dependente_midia,
                ("Alice",),
                sender_module.TIPO_TRATAMENTO_MIDIA,
            ),
            (
                sender_module.enviar_etapa7_cliente_financeiro,
                (),
                sender_module.TIPO_TRATAMENTO_FINANCEIRO,
            ),
            (
                sender_module.enviar_etapa7_dependente_financeiro,
                ("Alice",),
                sender_module.TIPO_TRATAMENTO_FINANCEIRO,
            ),
            (
                sender_module.enviar_etapa7_cliente_contexto_invalido,
                (),
                sender_module.TIPO_TRATAMENTO_CONTEXTO_INVALIDO,
            ),
            (
                sender_module.enviar_etapa7_dependente_contexto_invalido,
                ("Alice",),
                sender_module.TIPO_TRATAMENTO_CONTEXTO_INVALIDO,
            ),
        )

        for funcao, argumentos, tratamento in casos:
            with self.subTest(funcao=funcao.__name__):
                cliente_wa = FakeClienteWa()

                with patch.object(
                    sender_module,
                    "conta_wa",
                    return_value=cliente_wa,
                ):
                    resultado = funcao(
                        "5571999999999",
                        "123456",
                        *argumentos,
                    )

                chamada = cliente_wa.calls[0]
                self.assertEqual(
                    chamada["header"],
                    CABECALHO_ETAPA7_RETORNO,
                )
                self.assertEqual(
                    chamada["footer"],
                    RODAPE_OPCAO_UNICA,
                )
                self.assertEqual(
                    [botao.title for botao in chamada["buttons"]],
                    [
                        BOTAO_ETAPA7_QUERO_AGENDAR,
                        BOTAO_ETAPA7_TALVEZ_MAIS_TARDE,
                    ],
                )
                self.assertEqual(resultado["id_etapa_resultante"], 7)
                self.assertEqual(
                    resultado["tipo_mensagem"],
                    "interactive_button",
                )
                self.assertEqual(
                    resultado["cabecalho_mensagem"],
                    CABECALHO_ETAPA7_RETORNO,
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
                sender_module.enviar_etapa7_cliente(
                    "5571999999999",
                    "123456",
                )

        self.assertEqual(contexto.exception.id_etapa, 7)


if __name__ == "__main__":
    unittest.main()
