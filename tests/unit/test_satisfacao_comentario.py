import unittest
from unittest.mock import patch

import workers.worker_flow.response_flow.etapas.resolver_etapa19 as etapa19
import workers.worker_flow.response_flow.etapas.resolver_etapa20 as etapa20
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_19_DECISAO_COMENTARIO,
    ETAPA_20_COMENTARIO_SATISFACAO,
    ETAPA_21_FINALIZACAO,
    EVENTO_COMENTARIO_SATISFACAO_ACEITO,
    EVENTO_COMENTARIO_SATISFACAO_RECEBIDO,
    EVENTO_COMENTARIO_SATISFACAO_RECUSADO,
)


def contexto_etapa19(texto, tipo="text"):
    return {
        "id_conversa": 10,
        "id_etapa_cliente": ETAPA_19_DECISAO_COMENTARIO,
        "id_etapa_origem_transicao": ETAPA_19_DECISAO_COMENTARIO,
        "transicoes_permitidas": {
            EVENTO_COMENTARIO_SATISFACAO_ACEITO: (
                ETAPA_20_COMENTARIO_SATISFACAO
            ),
            EVENTO_COMENTARIO_SATISFACAO_RECUSADO: ETAPA_21_FINALIZACAO,
        },
        "texto_cliente_atual": texto,
        "tipo_mensagem_atual": tipo,
        "mensagem_cliente_atual": {
            "id_mensagem_fila": 20,
            "cliente_telefone": "5571999999999",
            "id_phone_unidade": "phone-id",
        },
    }


def contexto_etapa20(texto, tipo="text"):
    return {
        "id_conversa": 10,
        "id_etapa_cliente": ETAPA_20_COMENTARIO_SATISFACAO,
        "id_etapa_origem_transicao": ETAPA_20_COMENTARIO_SATISFACAO,
        "transicoes_permitidas": {
            EVENTO_COMENTARIO_SATISFACAO_RECEBIDO: ETAPA_21_FINALIZACAO,
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
    def test_etapa19_aceite_encaminha_para_captura_sem_salvar_comentario(self):
        with (
            patch.object(
                etapa19,
                "enviar_etapa20",
                return_value=contexto_envio(
                    ETAPA_20_COMENTARIO_SATISFACAO
                ),
            ) as enviar_etapa20,
            patch.object(etapa19, "enviar_etapa21") as enviar_etapa21,
        ):
            resultado = etapa19.resolve_etapa19(
                contexto_etapa19("Sim, quero comentar")
            )

        enviar_etapa20.assert_called_once_with(
            "5571999999999",
            "phone-id",
        )
        enviar_etapa21.assert_not_called()
        self.assertEqual(
            resultado["evento_transicao"],
            EVENTO_COMENTARIO_SATISFACAO_ACEITO,
        )
        self.assertEqual(
            resultado["id_etapa_resultante"],
            ETAPA_20_COMENTARIO_SATISFACAO,
        )
        self.assertNotIn("comentario_satisfacao", resultado)

    def test_etapa19_recusa_pula_para_finalizacao_com_comentario_nulo(self):
        with (
            patch.object(etapa19, "enviar_etapa20") as enviar_etapa20,
            patch.object(
                etapa19,
                "enviar_etapa21",
                return_value=contexto_envio(ETAPA_21_FINALIZACAO),
            ) as enviar_etapa21,
        ):
            resultado = etapa19.resolve_etapa19(
                contexto_etapa19("Prefiro não comentar", "interactive")
            )

        enviar_etapa20.assert_not_called()
        enviar_etapa21.assert_called_once_with(
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
            ETAPA_21_FINALIZACAO,
        )

    def test_etapa19_tratamentos_nao_carregam_transicao(self):
        casos = (
            (
                "Talvez",
                "text",
                "enviar_etapa19_contexto_invalido",
            ),
            (
                "Qual o valor?",
                "text",
                "enviar_etapa19_financeiro",
            ),
            (
                "Sim",
                "image",
                "enviar_etapa19_midia",
            ),
        )

        for texto, tipo, nome_sender in casos:
            with self.subTest(texto=texto, tipo=tipo), patch.object(
                etapa19,
                nome_sender,
                return_value=contexto_envio(
                    ETAPA_19_DECISAO_COMENTARIO,
                    tratamento=True,
                ),
            ):
                resultado = etapa19.resolve_etapa19(
                    contexto_etapa19(texto, tipo)
                )

            self.assertTrue(resultado["tratamento"])
            self.assertEqual(
                resultado["id_etapa_resultante"],
                ETAPA_19_DECISAO_COMENTARIO,
            )
            self.assertNotIn("evento_transicao", resultado)

    def test_etapa20_salva_texto_livre_e_encaminha_para_finalizacao(self):
        with patch.object(
            etapa20,
            "enviar_etapa21",
            return_value=contexto_envio(ETAPA_21_FINALIZACAO),
        ) as enviar_etapa21:
            resultado = etapa20.resolve_etapa20(
                contexto_etapa20(
                    "  O valor poderia ser mais acessível.  "
                )
            )

        enviar_etapa21.assert_called_once_with(
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
            ETAPA_21_FINALIZACAO,
        )

    def test_etapa20_permite_desistencia_explicita_com_comentario_nulo(self):
        with patch.object(
            etapa20,
            "enviar_etapa21",
            return_value=contexto_envio(ETAPA_21_FINALIZACAO),
        ):
            resultado = etapa20.resolve_etapa20(
                contexto_etapa20("Prefiro não comentar", "button")
            )

        self.assertEqual(
            resultado["evento_transicao"],
            EVENTO_COMENTARIO_SATISFACAO_RECEBIDO,
        )
        self.assertIsNone(resultado["comentario_satisfacao"])
        self.assertEqual(
            resultado["id_etapa_resultante"],
            ETAPA_21_FINALIZACAO,
        )

    def test_etapa20_contexto_invalido_e_midia_permanecem_na_etapa(self):
        casos = (
            (
                "Ok",
                "text",
                "enviar_etapa20_contexto_invalido",
            ),
            (
                "legenda",
                "image",
                "enviar_etapa20_midia",
            ),
        )

        for texto, tipo, nome_sender in casos:
            with self.subTest(texto=texto, tipo=tipo), patch.object(
                etapa20,
                nome_sender,
                return_value=contexto_envio(
                    ETAPA_20_COMENTARIO_SATISFACAO,
                    tratamento=True,
                ),
            ):
                resultado = etapa20.resolve_etapa20(
                    contexto_etapa20(texto, tipo)
                )

            self.assertTrue(resultado["tratamento"])
            self.assertEqual(
                resultado["id_etapa_resultante"],
                ETAPA_20_COMENTARIO_SATISFACAO,
            )
            self.assertNotIn("evento_transicao", resultado)


if __name__ == "__main__":
    unittest.main()
