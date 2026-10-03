"""Extração dos formatos interativos sem confundir resposta com mensagem citada."""

import unittest

from callback.webhook.services.populating_fila_mensagens import extrair_dados_whatsapp


def payload_botao(tipo, resposta, *, campo="interactive"):
    return {"entry": [{"changes": [{"value": {
        "metadata": {"display_phone_number": "5511000000000", "phone_number_id": "phone"},
        "contacts": [{"wa_id": "5511999999999"}],
        "messages": [{
            "id": "wamid.resposta", "timestamp": "1791036000", "type": tipo,
            "context": {"id": "wamid.pergunta", "body": "Pela manhã, pela tarde ou pela noite"},
            campo: resposta,
        }],
    }}]}]}


class BotoesWebhookTests(unittest.TestCase):
    def test_titulo_callback_e_alias_chegam_ao_texto_da_fila(self):
        for tipo in ("interactive", "interactive_button"):
            for campo in ("interactive", "interactive_button"):
                for opcao in (
                    {"title": "Pela manhã", "id": "callback-diferente"},
                    {"id": "Pela manhã"},
                    {"title": " ", "id": "Pela manhã"},
                ):
                    with self.subTest(tipo=tipo, campo=campo, opcao=opcao):
                        dados = extrair_dados_whatsapp(payload_botao(
                            tipo, {"type": "button_reply", "button_reply": opcao}, campo=campo,
                        ))
                        self.assertNotIn("erro", dados)
                        self.assertEqual(dados["tipo_mensagem"], tipo)
                        self.assertEqual(dados["conteudo_texto"], "Pela manhã")

    def test_lista_e_botao_legado_preservam_texto_e_callback(self):
        for tipo, campo, resposta, esperado in (
            ("interactive", "interactive", {"type": "list_reply", "list_reply": {"title": "5", "id": "satisfacao_5"}}, "5"),
            ("interactive_button", "interactive", {"type": "list_reply", "list_reply": {"id": "satisfacao_5"}}, "satisfacao_5"),
            ("button", "button", {"text": "Sim", "payload": "Sim"}, "Sim"),
            ("button", "button", {"payload": "Não"}, "Não"),
        ):
            with self.subTest(tipo=tipo, resposta=resposta):
                dados = extrair_dados_whatsapp(payload_botao(tipo, resposta, campo=campo))
                self.assertEqual(dados["conteudo_texto"], esperado)

    def test_resposta_ausente_ou_malformada_nao_inventa_texto(self):
        for resposta in (
            None, "Pela manhã", [], {}, {"type": "button_reply"},
            {"type": "button_reply", "button_reply": None},
            {"type": "button_reply", "button_reply": {"title": ["manhã"], "id": 7}},
            {"type": "button_reply", "button_reply": {"title": " "}},
        ):
            for tipo in ("interactive", "interactive_button"):
                with self.subTest(resposta=resposta, tipo=tipo):
                    dados = extrair_dados_whatsapp(payload_botao(tipo, resposta))
                    self.assertNotIn("erro", dados)
                    self.assertIsNone(dados["conteudo_texto"])
