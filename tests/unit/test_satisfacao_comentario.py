import unittest
from unittest.mock import patch

import workers.worker_flow.response_flow.etapas.resolver_etapa20 as etapa20
import workers.worker_flow.response_flow.etapas.resolver_etapa21 as etapa21
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_20_DECISAO_COMENTARIO,
    ETAPA_21_COMENTARIO_SATISFACAO,
    ETAPA_22_FINALIZACAO,
    EVENTO_COMENTARIO_SATISFACAO_ACEITO,
    EVENTO_COMENTARIO_SATISFACAO_RECEBIDO,
    EVENTO_COMENTARIO_SATISFACAO_RECUSADO,
)


def contexto_etapa20(texto, tipo="text"):
    return {
        "id_conversa": 10,
        "id_etapa_cliente": ETAPA_20_DECISAO_COMENTARIO,
        "id_etapa_origem_transicao": ETAPA_20_DECISAO_COMENTARIO,
        "transicoes_permitidas": {
            EVENTO_COMENTARIO_SATISFACAO_ACEITO: (
                ETAPA_21_COMENTARIO_SATISFACAO
            ),
            EVENTO_COMENTARIO_SATISFACAO_RECUSADO: ETAPA_22_FINALIZACAO,
        },
        "texto_cliente_atual": texto,
        "tipo_mensagem_atual": tipo,
        "mensagem_cliente_atual": {
            "id_mensagem_fila": 20,
            "cliente_telefone": "5571999999999",
            "id_phone_unidade": "phone-id",
        },
    }


def contexto_etapa21(texto, tipo="text"):
    return {
        "id_conversa": 10,
        "id_etapa_cliente": ETAPA_21_COMENTARIO_SATISFACAO,
        "id_etapa_origem_transicao": ETAPA_21_COMENTARIO_SATISFACAO,
        "transicoes_permitidas": {
            EVENTO_COMENTARIO_SATISFACAO_RECEBIDO: ETAPA_22_FINALIZACAO,
        },
        "texto_cliente_atual": texto,
        "tipo_mensagem_atual": tipo,
        "mensagem_cliente_atual": {
            "id_mensagem_fila": 20,
            "cliente_telefone": "5571999999999",
            "id_phone_unidade": "phone-id",
        },
    }


def contexto_envio(id_etapa, *, tratamento=False):
    contexto = {
        "enviou": True,
        "resposta_ja_existia": False,
        "mensagem_bot": "mensagem",
        "id_hash_msg_bot": "wamid.bot",
        "id_etapa_resultante": id_etapa,
        "tipo_mensagem": "text",
    }
    if tratamento:
        contexto.update(
            {
                "tratamento": True,
                "tipo_tratamento": "teste",
            }
        )
    return contexto


class SatisfacaoComentarioTests(unittest.TestCase):
    def test_etapa20_aceite_encaminha_para_captura_sem_salvar_comentario(self):
        with (
            patch.object(
                etapa20,
                "enviar_etapa21",
                return_value=contexto_envio(
                    ETAPA_21_COMENTARIO_SATISFACAO
                ),
            ) as enviar_etapa21,
            patch.object(etapa20, "enviar_etapa22") as enviar_etapa22,
        ):
            resultado = etapa20.resolve_etapa20(
                contexto_etapa20("Sim, quero comentar")
            )

        enviar_etapa21.assert_called_once_with(
            "5571999999999",
            "phone-id",
        )
        enviar_etapa22.assert_not_called()
        self.assertEqual(
            resultado["evento_transicao"],
            EVENTO_COMENTARIO_SATISFACAO_ACEITO,
        )
        self.assertEqual(
            resultado["id_etapa_resultante"],
            ETAPA_21_COMENTARIO_SATISFACAO,
        )
        self.assertNotIn("comentario_satisfacao", resultado)

    def test_etapa20_recusa_pula_para_finalizacao_com_comentario_nulo(self):
        with (
            patch.object(etapa20, "enviar_etapa21") as enviar_etapa21,
            patch.object(
                etapa20,
                "enviar_etapa22",
                return_value=contexto_envio(ETAPA_22_FINALIZACAO),
            ) as enviar_etapa22,
        ):
            resultado = etapa20.resolve_etapa20(
                contexto_etapa20("Prefiro não comentar", "interactive")
            )

        enviar_etapa21.assert_not_called()
        enviar_etapa22.assert_called_once_with(
            "5571999999999",
            "phone-id",
        )
        self.assertEqual(
            resultado["evento_transicao"],
            EVENTO_COMENTARIO_SATISFACAO_RECUSADO,
        )
        self.assertEqual(resultado["comentario_satisfacao"], None)
        self.assertEqual(
            resultado["id_etapa_resultante"],
            ETAPA_22_FINALIZACAO,
        )

    def test_etapa20_tratamentos_nao_carregam_transicao(self):
        casos = (
            (
                "Talvez",
                "text",
                "enviar_etapa20_contexto_invalido",
            ),
            (
                "Qual o valor?",
                "text",
                "enviar_etapa20_financeiro",
            ),
            (
                "Sim",
                "image",
                "enviar_etapa20_midia",
            ),
        )

        for texto, tipo, nome_sender in casos:
            with self.subTest(texto=texto, tipo=tipo), patch.object(
                etapa20,
                nome_sender,
                return_value=contexto_envio(
                    ETAPA_20_DECISAO_COMENTARIO,
                    tratamento=True,
                ),
            ):
                resultado = etapa20.resolve_etapa20(
                    contexto_etapa20(texto, tipo)
                )

            self.assertTrue(resultado["tratamento"])
            self.assertEqual(
                resultado["id_etapa_resultante"],
                ETAPA_20_DECISAO_COMENTARIO,
            )
            self.assertNotIn("evento_transicao", resultado)

    def test_etapa21_salva_texto_livre_e_encaminha_para_finalizacao(self):
        with patch.object(
            etapa21,
            "enviar_etapa22",
            return_value=contexto_envio(ETAPA_22_FINALIZACAO),
        ) as enviar_etapa22:
            resultado = etapa21.resolve_etapa21(
                contexto_etapa21(
                    "  O valor poderia ser mais acessível.  "
                )
            )

        enviar_etapa22.assert_called_once_with(
            "5571999999999",
            "phone-id",
        )
        self.assertEqual(
            resultado["evento_transicao"],
            EVENTO_COMENTARIO_SATISFACAO_RECEBIDO,
        )
        self.assertEqual(
            resultado["comentario_satisfacao"],
            "O valor poderia ser mais acessível.",
        )
        self.assertEqual(
            resultado["id_etapa_resultante"],
            ETAPA_22_FINALIZACAO,
        )

    def test_etapa21_permite_desistencia_explicita_com_comentario_nulo(self):
        with patch.object(
            etapa21,
            "enviar_etapa22",
            return_value=contexto_envio(ETAPA_22_FINALIZACAO),
        ):
            resultado = etapa21.resolve_etapa21(
                contexto_etapa21("Prefiro não comentar", "button")
            )

        self.assertEqual(
            resultado["evento_transicao"],
            EVENTO_COMENTARIO_SATISFACAO_RECEBIDO,
        )
        self.assertIsNone(resultado["comentario_satisfacao"])
        self.assertEqual(
            resultado["id_etapa_resultante"],
            ETAPA_22_FINALIZACAO,
        )

    def test_etapa21_contexto_invalido_e_midia_permanecem_na_etapa(self):
        casos = (
            (
                "Ok",
                "text",
                "enviar_etapa21_contexto_invalido",
            ),
            (
                "legenda",
                "image",
                "enviar_etapa21_midia",
            ),
        )

        for texto, tipo, nome_sender in casos:
            with self.subTest(texto=texto, tipo=tipo), patch.object(
                etapa21,
                nome_sender,
                return_value=contexto_envio(
                    ETAPA_21_COMENTARIO_SATISFACAO,
                    tratamento=True,
                ),
            ):
                resultado = etapa21.resolve_etapa21(
                    contexto_etapa21(texto, tipo)
                )

            self.assertTrue(resultado["tratamento"])
            self.assertEqual(
                resultado["id_etapa_resultante"],
                ETAPA_21_COMENTARIO_SATISFACAO,
            )
            self.assertNotIn("evento_transicao", resultado)


if __name__ == "__main__":
    unittest.main()
