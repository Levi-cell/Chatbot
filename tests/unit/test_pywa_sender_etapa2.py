import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.messages.etapa2_messages import (
    BOTAO_ETAPA2_OUTRA_PESSOA,
    BOTAO_ETAPA2_PARA_MIM,
    montar_mensagem_etapa2,
    montar_mensagem_financeiro_etapa2,
    montar_mensagem_midia_etapa2,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders import (
    etapa2 as sender_module,
)


class FakeClienteWa:
    def __init__(self, resposta=None, erro=None):
        self.calls = []
        self.resposta = resposta or SimpleNamespace(id="wamid.bot.2")
        self.erro = erro

    def send_message(self, **kwargs):
        self.calls.append(kwargs)
        if self.erro:
            raise self.erro
        return self.resposta


def titulos_botoes(call):
    return [botao.title for botao in call["buttons"]]


class PywaSenderEtapa2Tests(unittest.TestCase):
    def test_enviar_etapa2_usa_nome_e_botoes(self):
        cliente_wa = FakeClienteWa()

        with patch.object(
            sender_module,
            "conta_wa",
            return_value=cliente_wa,
        ):
            resultado = sender_module.enviar_etapa2(
                "5571999999999",
                "123456",
                nome="Edcarlos",
            )

        mensagem_esperada = montar_mensagem_etapa2("Edcarlos")

        self.assertEqual(cliente_wa.calls[0]["to"], "5571999999999")
        self.assertEqual(cliente_wa.calls[0]["text"], mensagem_esperada)
        self.assertEqual(
            titulos_botoes(cliente_wa.calls[0]),
            [BOTAO_ETAPA2_PARA_MIM, BOTAO_ETAPA2_OUTRA_PESSOA],
        )
        self.assertTrue(resultado["enviou"])
        self.assertFalse(resultado["resposta_ja_existia"])
        self.assertEqual(resultado["mensagem_bot"], mensagem_esperada)
        self.assertEqual(resultado["id_hash_msg_bot"], "wamid.bot.2")
        self.assertEqual(resultado["id_etapa_resultante"], 2)
        self.assertEqual(resultado["tipo_mensagem"], "interactive_button")
        self.assertNotIn("tratamento", resultado)

    def test_midia_etapa2_marca_tratamento_e_mantem_botoes(self):
        cliente_wa = FakeClienteWa()

        with patch.object(
            sender_module,
            "conta_wa",
            return_value=cliente_wa,
        ):
            resultado = sender_module.enviar_etapa2_midia(
                "5571999999999",
                "123456",
            )

        self.assertEqual(
            cliente_wa.calls[0]["text"],
            montar_mensagem_midia_etapa2(),
        )
        self.assertEqual(
            titulos_botoes(cliente_wa.calls[0]),
            [BOTAO_ETAPA2_PARA_MIM, BOTAO_ETAPA2_OUTRA_PESSOA],
        )
        self.assertTrue(resultado["tratamento"])
        self.assertEqual(
            resultado["tipo_tratamento"],
            sender_module.TIPO_TRATAMENTO_MIDIA,
        )
        self.assertEqual(resultado["id_etapa_resultante"], 2)

    def test_financeiro_etapa2_marca_tratamento(self):
        cliente_wa = FakeClienteWa()

        with patch.object(
            sender_module,
            "conta_wa",
            return_value=cliente_wa,
        ):
            resultado = sender_module.enviar_etapa2_financeiro(
                "5571999999999",
                "123456",
            )

        self.assertEqual(
            cliente_wa.calls[0]["text"],
            montar_mensagem_financeiro_etapa2(),
        )
        self.assertTrue(resultado["tratamento"])
        self.assertEqual(
            resultado["tipo_tratamento"],
            sender_module.TIPO_TRATAMENTO_FINANCEIRO,
        )
        self.assertEqual(resultado["id_etapa_resultante"], 2)

    def test_meta_falhou_levanta_exception_controlada(self):
        cliente_wa = FakeClienteWa(erro=RuntimeError("meta indisponivel"))

        with patch.object(
            sender_module,
            "conta_wa",
            return_value=cliente_wa,
        ):
            with self.assertRaises(ErroEnvioMeta) as ctx:
                sender_module.enviar_etapa2(
                    "5571999999999",
                    "123456",
                    nome="Edcarlos",
                )

        self.assertEqual(ctx.exception.id_etapa, 2)
        self.assertEqual(ctx.exception.cliente_telefone, "5571999999999")
        self.assertEqual(ctx.exception.phone_id_unidade, "123456")


if __name__ == "__main__":
    unittest.main()
