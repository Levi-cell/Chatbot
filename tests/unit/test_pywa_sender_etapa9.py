import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.messages.componentes_compartilhados import (
    CABECALHO_ETAPA9_TRIAGEM,
)
from core.integrations.whatsapp.messages.etapa9_messages import (
    BOTAO_ETAPA9_INICIAR_TRIAGEM,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders import (
    etapa9 as sender_module,
)


class FakeClienteWa:
    def __init__(self, erro=None):
        self.calls = []
        self.erro = erro

    def send_message(self, **kwargs):
        self.calls.append(kwargs)

        if self.erro:
            raise self.erro

        return SimpleNamespace(id="wamid.bot.9")


class PywaSenderEtapa9Tests(unittest.TestCase):
    def test_sender_envia_mensagem_com_botao_unico(self):
        cliente_wa = FakeClienteWa()

        with patch.object(
            sender_module,
            "conta_wa",
            return_value=cliente_wa,
        ):
            resultado = sender_module.enviar_etapa9(
                "5571999999999",
                "123456",
            )

        chamada = cliente_wa.calls[0]
        self.assertEqual(
            chamada["header"],
            CABECALHO_ETAPA9_TRIAGEM,
        )
        self.assertNotIn("footer", chamada)
        self.assertEqual(
            [botao.title for botao in chamada["buttons"]],
            [BOTAO_ETAPA9_INICIAR_TRIAGEM],
        )
        self.assertEqual(resultado["id_etapa_resultante"], 9)
        self.assertEqual(
            resultado["tipo_mensagem"],
            "interactive_button",
        )
        self.assertEqual(
            resultado["cabecalho_mensagem"],
            CABECALHO_ETAPA9_TRIAGEM,
        )
        self.assertNotIn("rodape_mensagem", resultado)
        self.assertNotIn("tratamento", resultado)

    def test_meta_falhou_levanta_exception_controlada(self):
        cliente_wa = FakeClienteWa(
            erro=RuntimeError("meta indisponível")
        )

        with patch.object(
            sender_module,
            "conta_wa",
            return_value=cliente_wa,
        ):
            with self.assertRaises(ErroEnvioMeta) as contexto:
                sender_module.enviar_etapa9(
                    "5571999999999",
                    "123456",
                )

        self.assertEqual(contexto.exception.id_etapa, 9)


if __name__ == "__main__":
    unittest.main()
