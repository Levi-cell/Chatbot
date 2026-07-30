import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core.integrations.whatsapp.messages.componentes_compartilhados import (
    CABECALHO_ETAPA10_TRIAGEM,
    CABECALHO_PESQUISA_SATISFACAO,
    RODAPE_OPCAO_UNICA,
    montar_texto_com_cabecalho,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders import (
    etapa10,
    etapa18,
    etapa19,
    triagem_base,
)


class _ClienteWhatsAppFake:
    def __init__(self):
        self.ultimo_envio = None

    def send_message(self, **kwargs):
        self.ultimo_envio = kwargs
        return SimpleNamespace(id="wamid.teste")


class CabecalhosWhatsAppTests(unittest.TestCase):
    def test_helper_mantem_cabecalho_em_negrito_com_tamanho_do_corpo(self):
        self.assertEqual(
            montar_texto_com_cabecalho("Conteúdo", "Cabeçalho"),
            "*Cabeçalho*\n\nConteúdo",
        )

    def test_introducao_da_triagem_nao_usa_header_nativo(self):
        cliente = _ClienteWhatsAppFake()

        with (
            patch.object(etapa10, "conta_wa", return_value=cliente),
            patch.object(etapa10.logger, "info") as log_info,
        ):
            contexto = etapa10.enviar_etapa10(
                "5511999999999",
                "phone-id",
            )

        self._assert_cabecalho_padronizado(
            cliente,
            CABECALHO_ETAPA10_TRIAGEM,
        )
        self.assertEqual(
            contexto["cabecalho_mensagem"],
            CABECALHO_ETAPA10_TRIAGEM,
        )
        self.assertEqual(contexto["tipo_mensagem"], "interactive_button")
        self._assert_log_cabecalho_no_corpo(log_info)

    def test_perguntas_da_triagem_nao_usam_header_nativo(self):
        cliente = _ClienteWhatsAppFake()

        with (
            patch.object(triagem_base, "conta_wa", return_value=cliente),
            patch.object(triagem_base.logger, "info") as log_info,
        ):
            contexto = triagem_base.enviar_pergunta_triagem(
                "5511999999999",
                "phone-id",
                id_etapa=11,
                cabecalho="Pergunta 1",
                mensagem_bot="Texto da pergunta",
                evento_log="teste_triagem",
            )

        self._assert_cabecalho_padronizado(cliente, "Pergunta 1")
        self.assertTrue(
            cliente.ultimo_envio["text"].endswith(
                f"\n\n_{RODAPE_OPCAO_UNICA}_"
            )
        )
        self.assertEqual(contexto["cabecalho_mensagem"], "Pergunta 1")
        self.assertEqual(contexto["tipo_mensagem"], "interactive_button")
        self._assert_log_cabecalho_no_corpo(log_info)

    def test_lista_da_pesquisa_nao_usa_header_nativo(self):
        cliente = _ClienteWhatsAppFake()

        with (
            patch.object(etapa18, "conta_wa", return_value=cliente),
            patch.object(etapa18.logger, "info") as log_info,
        ):
            contexto = etapa18.enviar_etapa18(
                "5511999999999",
                "phone-id",
                "Edcarlos",
            )

        self._assert_cabecalho_padronizado(
            cliente,
            CABECALHO_PESQUISA_SATISFACAO,
        )
        self.assertEqual(
            contexto["cabecalho_mensagem"],
            CABECALHO_PESQUISA_SATISFACAO,
        )
        self.assertEqual(contexto["tipo_mensagem"], "interactive_list")
        self._assert_log_cabecalho_no_corpo(log_info)

    def test_comentario_da_pesquisa_nao_usa_header_nativo(self):
        cliente = _ClienteWhatsAppFake()

        with (
            patch.object(etapa19, "conta_wa", return_value=cliente),
            patch.object(etapa19.logger, "info") as log_info,
        ):
            contexto = etapa19.enviar_etapa19(
                "5511999999999",
                "phone-id",
            )

        self._assert_cabecalho_padronizado(
            cliente,
            CABECALHO_PESQUISA_SATISFACAO,
        )
        self.assertEqual(
            contexto["cabecalho_mensagem"],
            CABECALHO_PESQUISA_SATISFACAO,
        )
        self.assertEqual(contexto["tipo_mensagem"], "interactive_button")
        self._assert_log_cabecalho_no_corpo(log_info)

    def _assert_cabecalho_padronizado(self, cliente, cabecalho):
        self.assertNotIn("header", cliente.ultimo_envio)
        self.assertIn("buttons", cliente.ultimo_envio)
        self.assertTrue(
            cliente.ultimo_envio["text"].startswith(
                f"*{cabecalho}*\n\n"
            )
        )

    def _assert_log_cabecalho_no_corpo(self, log_info):
        formatos = [
            chamada.args[0]
            for chamada in log_info.call_args_list
            if chamada.args
        ]
        self.assertTrue(
            any(
                "cabecalho=corpo_negrito" in formato
                for formato in formatos
            )
        )


if __name__ == "__main__":
    unittest.main()
