import importlib
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.messages.triagem_componentes import (
    BOTOES_TRIAGEM,
    RODAPE_TRIAGEM,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders import (
    triagem_base,
)


class FakeClienteWa:
    def __init__(self, erro=None):
        self.calls = []
        self.erro = erro

    def send_message(self, **kwargs):
        self.calls.append(kwargs)

        if self.erro:
            raise self.erro

        return SimpleNamespace(id="wamid.bot.triagem")


class PywaSenderTriagemTests(unittest.TestCase):
    def test_senders_normais_enviam_header_footer_e_tres_botoes(self):
        for etapa in range(10, 16):
            with self.subTest(etapa=etapa):
                modulo = importlib.import_module(
                    "core.integrations.whatsapp.pywa_functions."
                    f"pywa_senders.etapa{etapa}"
                )
                cliente_wa = FakeClienteWa()

                with patch.object(
                    triagem_base,
                    "conta_wa",
                    return_value=cliente_wa,
                ):
                    resultado = getattr(
                        modulo,
                        f"enviar_etapa{etapa}_cliente",
                    )(
                        "5571999999999",
                        "123456",
                    )

                chamada = cliente_wa.calls[0]
                self.assertEqual(
                    chamada["header"],
                    f"Teste Cognitivo - Pergunta {etapa - 9}",
                )
                self.assertEqual(chamada["footer"], RODAPE_TRIAGEM)
                self.assertEqual(
                    [botao.title for botao in chamada["buttons"]],
                    list(BOTOES_TRIAGEM),
                )
                self.assertEqual(
                    resultado["id_etapa_resultante"],
                    etapa,
                )
                self.assertNotIn("tratamento", resultado)

    def test_senders_de_tratamento_repetem_pergunta_do_dependente(self):
        for etapa in range(10, 16):
            with self.subTest(etapa=etapa):
                modulo = importlib.import_module(
                    "core.integrations.whatsapp.pywa_functions."
                    f"pywa_senders.etapa{etapa}"
                )
                cliente_wa = FakeClienteWa()

                with patch.object(
                    triagem_base,
                    "conta_wa",
                    return_value=cliente_wa,
                ):
                    resultado = getattr(
                        modulo,
                        "enviar_etapa"
                        f"{etapa}_dependente_contexto_invalido",
                    )(
                        "5571999999999",
                        "123456",
                        "Alice",
                    )

                self.assertIn(
                    "Não consegui entender sua resposta.",
                    cliente_wa.calls[0]["text"],
                )
                self.assertIn("Alice", cliente_wa.calls[0]["text"])
                self.assertTrue(resultado["tratamento"])
                self.assertEqual(
                    resultado["tipo_tratamento"],
                    "resposta_triagem_invalida",
                )
                self.assertEqual(
                    resultado["id_etapa_resultante"],
                    etapa,
                )

    def test_falha_meta_levanta_erro_controlado_com_etapa(self):
        modulo = importlib.import_module(
            "core.integrations.whatsapp.pywa_functions."
            "pywa_senders.etapa10"
        )
        cliente_wa = FakeClienteWa(
            erro=RuntimeError("meta indisponível")
        )

        with patch.object(
            triagem_base,
            "conta_wa",
            return_value=cliente_wa,
        ):
            with self.assertRaises(ErroEnvioMeta) as contexto:
                modulo.enviar_etapa10_cliente(
                    "5571999999999",
                    "123456",
                )

        self.assertEqual(contexto.exception.id_etapa, 10)


if __name__ == "__main__":
    unittest.main()
