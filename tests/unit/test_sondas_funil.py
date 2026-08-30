import unittest
from unittest.mock import patch

from utilitarios.integrations import funi_rio_teste, funil_saj
from utilitarios.montar_lead_teste import (
    montar_dados_lead_teste_rio_vermelho,
    montar_dados_lead_teste_saj,
)


class SondasFunilTestCase(unittest.TestCase):
    def test_leads_ficticios_identificam_suas_unidades(self):
        saj = montar_dados_lead_teste_saj()
        rio = montar_dados_lead_teste_rio_vermelho()

        self.assertEqual(saj["id_unidade"], 1)
        self.assertEqual(
            saj["nome_unidade"],
            "Supera Santo Antônio de Jesus",
        )
        self.assertIn("SAJ", saj["nome_cliente"])

        self.assertEqual(rio["id_unidade"], 2)
        self.assertEqual(rio["nome_unidade"], "Supera Rio Vermelho")
        self.assertIn("Rio Vermelho", rio["nome_cliente"])
        self.assertIsNot(saj["triagem_respostas"], rio["triagem_respostas"])

    def test_payload_saj_nao_se_confunde_com_rio(self):
        oportunidade = funil_saj.montar_payload_oportunidade_teste()[
            "oportunidades"
        ][0]

        self.assertEqual(
            oportunidade["titulo"],
            "Chatbot Lead Supera Santo Antônio de Jesus",
        )
        self.assertNotIn("Rio Vermelho", oportunidade["titulo"])

    def test_payload_rio_nao_se_confunde_com_saj(self):
        oportunidade = funi_rio_teste.montar_payload_oportunidade_teste()[
            "oportunidades"
        ][0]

        self.assertEqual(
            oportunidade["titulo"],
            "Chatbot Lead Supera Rio Vermelho",
        )
        self.assertNotIn("Santo Antônio", oportunidade["titulo"])

    def test_envios_exigem_confirmacao_explicita(self):
        with self.assertRaises(ValueError):
            funil_saj.criar_oportunidade_teste()
        with self.assertRaises(ValueError):
            funi_rio_teste.criar_oportunidade_teste()

    @patch.object(funil_saj, "enviar_oportunidade")
    def test_saj_envia_payload_saj_ao_widget_saj(self, enviar_mock):
        enviar_mock.return_value = {"response": "success"}

        funil_saj.criar_oportunidade_teste(confirmar_envio_real=True)

        kwargs = enviar_mock.call_args.kwargs
        self.assertEqual(
            kwargs["link_api_carrossel"],
            funil_saj.LINK_API_UNIDADE_SAJ,
        )
        self.assertEqual(
            kwargs["payload"]["oportunidades"][0]["titulo"],
            "Chatbot Lead Supera Santo Antônio de Jesus",
        )

    @patch.object(funi_rio_teste, "enviar_oportunidade")
    def test_rio_envia_payload_rio_ao_widget_rio(self, enviar_mock):
        enviar_mock.return_value = {"response": "success"}

        funi_rio_teste.criar_oportunidade_teste(
            confirmar_envio_real=True
        )

        kwargs = enviar_mock.call_args.kwargs
        self.assertEqual(
            kwargs["link_api_carrossel"],
            funi_rio_teste.LINK_API_RIO_VERMELHO,
        )
        self.assertEqual(
            kwargs["payload"]["oportunidades"][0]["titulo"],
            "Chatbot Lead Supera Rio Vermelho",
        )


if __name__ == "__main__":
    unittest.main()
