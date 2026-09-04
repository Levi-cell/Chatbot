from __future__ import annotations

import unittest

from callback.webhook.services.populating_fila_mensagens import (
    extrair_conteudo_texto_mensagem,
)
from core.integrations.whatsapp.messages.etapa11_messages import (
    BOTAO_ETAPA11_INICIAR_TRIAGEM,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa11 import (
    validar_etapa11,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_TRIAGEM_INICIADA,
)


class ValidarEtapa11Tests(unittest.TestCase):
    def test_rotulo_real_do_botao_inicia_a_triagem(self) -> None:
        self.assertEqual(BOTAO_ETAPA11_INICIAR_TRIAGEM, "Começar triagem")
        self.assertEqual(
            validar_etapa11(BOTAO_ETAPA11_INICIAR_TRIAGEM),
            EVENTO_TRIAGEM_INICIADA,
        )

    def test_confirmacoes_digitadas_iniciam_a_triagem(self) -> None:
        confirmacoes = (
            "Começar triagem",
            "sim começar triagem",
            "pode começar triagem",
            "Iniciar triagem",
            "Iniciar a triagem",
            "sim começar",
            "vamos começar",
            "pode começar",
            "sim",
            "vamos",
            "começar a triagem",
            "bora",
            "bora começar a triagem",
            "vamos lá começar a triagem",
            "podemos começar triagem",
            "pode sim começar agora",
            "quero iniciar a triagem",
            "comece a triagem",
            "inicie a triagem",
            "claro que sim",
            "manda ver",
            "pode prosseguir",
            "  SIM,   PODE COMEÇAR TRIAGEM!  ",
        )

        for resposta in confirmacoes:
            with self.subTest(resposta=resposta):
                self.assertEqual(
                    validar_etapa11(resposta),
                    EVENTO_TRIAGEM_INICIADA,
                )

    def test_botao_interativo_legado_e_texto_usam_a_mesma_regra(self) -> None:
        mensagens = (
            (
                "interactive",
                {
                    "type": "interactive",
                    "interactive": {
                        "type": "button_reply",
                        "button_reply": {
                            "id": BOTAO_ETAPA11_INICIAR_TRIAGEM,
                            "title": BOTAO_ETAPA11_INICIAR_TRIAGEM,
                        },
                    },
                },
            ),
            (
                "interactive",
                {
                    "type": "interactive",
                    "interactive": {
                        "type": "button_reply",
                        "button_reply": {
                            "id": BOTAO_ETAPA11_INICIAR_TRIAGEM,
                        },
                    },
                },
            ),
            (
                "button",
                {
                    "type": "button",
                    "button": {
                        "payload": BOTAO_ETAPA11_INICIAR_TRIAGEM,
                        "text": BOTAO_ETAPA11_INICIAR_TRIAGEM,
                    },
                },
            ),
            (
                "text",
                {
                    "type": "text",
                    "text": {"body": BOTAO_ETAPA11_INICIAR_TRIAGEM},
                },
            ),
        )

        for tipo, mensagem in mensagens:
            with self.subTest(tipo=tipo, mensagem=mensagem):
                conteudo = extrair_conteudo_texto_mensagem(mensagem, tipo)
                self.assertEqual(conteudo, BOTAO_ETAPA11_INICIAR_TRIAGEM)
                self.assertEqual(
                    validar_etapa11(conteudo),
                    EVENTO_TRIAGEM_INICIADA,
                )

    def test_negativas_e_respostas_ambiguas_nao_iniciam_a_triagem(self) -> None:
        respostas = (
            "não",
            "não quero começar",
            "não começar triagem",
            "sim, mas depois",
            "vamos depois",
            "talvez",
            "começar depois",
            "como funciona?",
            "quero saber mais",
            "quero tirar uma dúvida",
            "",
            None,
            123,
        )

        for resposta in respostas:
            with self.subTest(resposta=resposta):
                self.assertIsNone(validar_etapa11(resposta))


if __name__ == "__main__":
    unittest.main()
