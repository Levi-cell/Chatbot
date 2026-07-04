import importlib
import unittest
from unittest.mock import patch

from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_TRIAGEM_PERGUNTA_1_RESPONDIDA,
    EVENTO_TRIAGEM_PERGUNTA_2_RESPONDIDA,
    EVENTO_TRIAGEM_PERGUNTA_3_RESPONDIDA,
    EVENTO_TRIAGEM_PERGUNTA_4_RESPONDIDA,
    EVENTO_TRIAGEM_PERGUNTA_5_RESPONDIDA,
    EVENTO_TRIAGEM_PERGUNTA_6_RESPONDIDA,
)


CASOS_TRIAGEM = (
    (10, 11, EVENTO_TRIAGEM_PERGUNTA_1_RESPONDIDA),
    (11, 12, EVENTO_TRIAGEM_PERGUNTA_2_RESPONDIDA),
    (12, 13, EVENTO_TRIAGEM_PERGUNTA_3_RESPONDIDA),
    (13, 14, EVENTO_TRIAGEM_PERGUNTA_4_RESPONDIDA),
    (14, 15, EVENTO_TRIAGEM_PERGUNTA_5_RESPONDIDA),
    (15, 16, EVENTO_TRIAGEM_PERGUNTA_6_RESPONDIDA),
)


def contexto_historico(
    etapa,
    destino,
    evento,
    *,
    texto="Às vezes",
    tipo_mensagem="interactive",
    status_dependente=False,
):
    return {
        "id_conversa": 10,
        "id_etapa_atual": etapa,
        "id_etapa_cliente": etapa,
        "id_etapa_origem_transicao": etapa,
        "transicoes_permitidas": {evento: destino},
        "tipo_mensagem_atual": tipo_mensagem,
        "texto_cliente_atual": texto,
        "status_dependente": status_dependente,
        "nome_dependente": "Alice" if status_dependente else None,
        "mensagem_cliente_atual": {
            "id_mensagem": 900 + etapa,
            "id_mensagem_fila": 100 + etapa,
            "cliente_telefone": "5571999999999",
            "id_phone_unidade": "123456",
        },
    }


def contexto_sender(etapa):
    return {
        "enviou": True,
        "resposta_ja_existia": False,
        "id_hash_msg_bot": f"wamid.bot.{etapa}",
        "id_etapa_resultante": etapa,
    }


class ResolversTriagemTests(unittest.TestCase):
    def test_respostas_validas_avancam_uma_pergunta(self):
        for etapa, destino, evento in CASOS_TRIAGEM[:-1]:
            with self.subTest(etapa=etapa):
                modulo = importlib.import_module(
                    "workers.worker_flow.response_flow.etapas."
                    f"resolver_etapa{etapa}"
                )
                nome_sender = f"enviar_etapa{destino}_cliente"

                with patch.object(
                    modulo,
                    nome_sender,
                    return_value=contexto_sender(destino),
                ) as sender:
                    resultado = getattr(
                        modulo,
                        f"resolve_etapa{etapa}",
                    )(
                        contexto_historico(
                            etapa,
                            destino,
                            evento,
                        )
                    )

                sender.assert_called_once_with(
                    "5571999999999",
                    "123456",
                )
                self.assertEqual(
                    resultado["id_etapa_resultante"],
                    destino,
                )
                self.assertEqual(resultado["evento_transicao"], evento)
                self.assertEqual(
                    resultado["resposta_triagem"],
                    "às vezes",
                )
                self.assertNotIn("tratamento", resultado)

    def test_resposta_valida_do_dependente_envia_nome_na_proxima_pergunta(self):
        modulo = importlib.import_module(
            "workers.worker_flow.response_flow.etapas.resolver_etapa10"
        )

        with patch.object(
            modulo,
            "enviar_etapa11_dependente",
            return_value=contexto_sender(11),
        ) as sender:
            resultado = modulo.resolve_etapa10(
                contexto_historico(
                    10,
                    11,
                    EVENTO_TRIAGEM_PERGUNTA_1_RESPONDIDA,
                    status_dependente=True,
                )
            )

        sender.assert_called_once_with(
            "5571999999999",
            "123456",
            "Alice",
        )
        self.assertEqual(resultado["id_etapa_resultante"], 11)

    def test_resposta_invalida_repete_a_mesma_pergunta_sem_evento(self):
        for etapa, destino, evento in CASOS_TRIAGEM:
            with self.subTest(etapa=etapa):
                modulo = importlib.import_module(
                    "workers.worker_flow.response_flow.etapas."
                    f"resolver_etapa{etapa}"
                )
                nome_sender = (
                    f"enviar_etapa{etapa}_cliente_contexto_invalido"
                )
                tratamento = {
                    **contexto_sender(etapa),
                    "tratamento": True,
                    "tipo_tratamento": "resposta_triagem_invalida",
                }

                with patch.object(
                    modulo,
                    nome_sender,
                    return_value=tratamento,
                ) as sender:
                    resultado = getattr(
                        modulo,
                        f"resolve_etapa{etapa}",
                    )(
                        contexto_historico(
                            etapa,
                            destino,
                            evento,
                            texto="quanto custa?",
                        )
                    )

                sender.assert_called_once_with(
                    "5571999999999",
                    "123456",
                )
                self.assertEqual(
                    resultado["id_etapa_resultante"],
                    etapa,
                )
                self.assertTrue(resultado["tratamento"])
                self.assertNotIn("evento_transicao", resultado)

    def test_midia_e_tratada_como_contexto_invalido(self):
        modulo = importlib.import_module(
            "workers.worker_flow.response_flow.etapas.resolver_etapa12"
        )
        tratamento = {
            **contexto_sender(12),
            "tratamento": True,
            "tipo_tratamento": "resposta_triagem_invalida",
        }

        with patch.object(
            modulo,
            "enviar_etapa12_cliente_contexto_invalido",
            return_value=tratamento,
        ):
            resultado = modulo.resolve_etapa12(
                contexto_historico(
                    12,
                    13,
                    EVENTO_TRIAGEM_PERGUNTA_3_RESPONDIDA,
                    texto="Nunca",
                    tipo_mensagem="image",
                )
            )

        self.assertTrue(resultado["tratamento"])
        self.assertEqual(resultado["id_etapa_resultante"], 12)

    def test_pergunta_6_persiste_evento_e_prepara_etapa16(self):
        modulo = importlib.import_module(
            "workers.worker_flow.response_flow.etapas.resolver_etapa15"
        )

        resultado = modulo.resolve_etapa15(
            contexto_historico(
                15,
                16,
                EVENTO_TRIAGEM_PERGUNTA_6_RESPONDIDA,
                texto="Frequentemente",
                tipo_mensagem="text",
            )
        )

        self.assertTrue(resultado["envio_simulado"])
        self.assertEqual(resultado["id_etapa_resultante"], 16)
        self.assertEqual(
            resultado["evento_transicao"],
            EVENTO_TRIAGEM_PERGUNTA_6_RESPONDIDA,
        )
        self.assertEqual(
            resultado["resposta_triagem"],
            "frequentemente",
        )


if __name__ == "__main__":
    unittest.main()
