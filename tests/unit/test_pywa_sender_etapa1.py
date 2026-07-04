import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.messages.componentes_compartilhados import (
    CABECALHO_ETAPA1_SAUDACAO,
    RODAPE_ETAPA1_BOAS_VINDAS,
    RODAPE_TRATAMENTO_TEXTO,
)
from core.integrations.whatsapp.messages.etapa1_messages import (
    montar_mensagem_etapa1,
    montar_mensagem_financeiro_etapa1,
    montar_mensagem_financeiro_inicio,
    montar_mensagem_midia_inicio,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders import (
    etapa1 as sender_module,
)


class FakeClienteWa:
    def __init__(self, resposta=None, erro=None):
        self.calls = []
        self.resposta = resposta or SimpleNamespace(id="wamid.bot.1")
        self.erro = erro

    def send_message(self, **kwargs):
        self.calls.append(kwargs)
        if self.erro:
            raise self.erro
        return self.resposta


class PywaSenderEtapa1Tests(unittest.TestCase):
    def test_enviar_etapa1_usa_saudacao(self):
        cliente_wa = FakeClienteWa()

        with patch.object(
            sender_module,
            "conta_wa",
            return_value=cliente_wa,
        ), patch.object(
            sender_module,
            "obter_saudacao_por_horario",
            return_value="Boa tarde",
        ):
            resultado = sender_module.enviar_etapa1(
                "5571999999999",
                "123456",
            )

        mensagem_esperada = montar_mensagem_etapa1("Boa tarde")

        self.assertEqual(cliente_wa.calls[0]["to"], "5571999999999")
        self.assertEqual(cliente_wa.calls[0]["text"], mensagem_esperada)
        self.assertTrue(
            mensagem_esperada.startswith(
                f"*{CABECALHO_ETAPA1_SAUDACAO}*"
            )
        )
        self.assertTrue(
            mensagem_esperada.endswith(
                f"_{RODAPE_ETAPA1_BOAS_VINDAS}_"
            )
        )
        self.assertTrue(resultado["enviou"])
        self.assertFalse(resultado["resposta_ja_existia"])
        self.assertEqual(resultado["mensagem_bot"], mensagem_esperada)
        self.assertEqual(resultado["id_hash_msg_bot"], "wamid.bot.1")
        self.assertEqual(resultado["id_etapa_resultante"], 1)
        self.assertNotIn("tratamento", resultado)

    def test_midia_inicio_usa_saudacao_e_marca_tratamento(self):
        cliente_wa = FakeClienteWa()

        with patch.object(
            sender_module,
            "conta_wa",
            return_value=cliente_wa,
        ), patch.object(
            sender_module,
            "obter_saudacao_por_horario",
            return_value="Bom dia",
        ):
            resultado = sender_module.enviar_etapa1_midia_inicio(
                "5571999999999",
                "123456",
            )

        mensagem_esperada = montar_mensagem_midia_inicio("Bom dia")

        self.assertEqual(cliente_wa.calls[0]["text"], mensagem_esperada)
        self.assertTrue(resultado["tratamento"])
        self.assertEqual(
            resultado["tipo_tratamento"],
            sender_module.TIPO_TRATAMENTO_MIDIA,
        )
        self.assertEqual(resultado["id_etapa_resultante"], 1)

    def test_financeiro_inicio_usa_saudacao_e_marca_tratamento(self):
        cliente_wa = FakeClienteWa()

        with patch.object(
            sender_module,
            "conta_wa",
            return_value=cliente_wa,
        ), patch.object(
            sender_module,
            "obter_saudacao_por_horario",
            return_value="Boa noite",
        ):
            resultado = sender_module.enviar_etapa1_financeiro_inicio(
                "5571999999999",
                "123456",
            )

        mensagem_esperada = montar_mensagem_financeiro_inicio("Boa noite")

        self.assertEqual(cliente_wa.calls[0]["text"], mensagem_esperada)
        self.assertTrue(resultado["tratamento"])
        self.assertEqual(
            resultado["tipo_tratamento"],
            sender_module.TIPO_TRATAMENTO_FINANCEIRO,
        )
        self.assertEqual(resultado["id_etapa_resultante"], 1)

    def test_financeiro_etapa1_nao_usa_saudacao(self):
        cliente_wa = FakeClienteWa()

        with patch.object(
            sender_module,
            "conta_wa",
            return_value=cliente_wa,
        ):
            resultado = sender_module.enviar_etapa1_financeiro(
                "5571999999999",
                "123456",
            )

        self.assertEqual(
            cliente_wa.calls[0]["text"],
            montar_mensagem_financeiro_etapa1(),
        )
        self.assertTrue(
            resultado["mensagem_bot"].endswith(
                f"_{RODAPE_TRATAMENTO_TEXTO}_"
            )
        )
        self.assertTrue(resultado["tratamento"])
        self.assertEqual(resultado["id_etapa_resultante"], 1)

    def test_meta_falhou_levanta_exception_controlada(self):
        cliente_wa = FakeClienteWa(erro=RuntimeError("meta indisponivel"))

        with patch.object(
            sender_module,
            "conta_wa",
            return_value=cliente_wa,
        ):
            with self.assertRaises(ErroEnvioMeta) as ctx:
                sender_module.enviar_etapa1(
                    "5571999999999",
                    "123456",
                )

        self.assertEqual(ctx.exception.id_etapa, 1)
        self.assertEqual(ctx.exception.cliente_telefone, "5571999999999")
        self.assertEqual(ctx.exception.phone_id_unidade, "123456")


if __name__ == "__main__":
    unittest.main()
