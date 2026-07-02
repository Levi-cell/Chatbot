import unittest
from unittest.mock import patch

import workers.worker_flow.response_flow.flow_sender as flow_sender_module
from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_NOME_CLIENTE_VALIDO,
    EVENTO_NOME_DEPENDENTE_VALIDO,
    EVENTO_IDADE_VALIDA,
    EVENTO_PARA_MIM,
    EVENTO_PARA_OUTRA_PESSOA,
)


def contexto_historico_base(
    resposta_bot=None,
    etapa_atual=None,
    etapa_resposta=1,
    etapa_cliente=1,
    retry=1,
    transicoes=None,
):
    if transicoes is None:
        transicoes = {
            EVENTO_NOME_CLIENTE_VALIDO: 2,
        }

    return {
        "id_conversa": 10,
        "id_etapa_atual": etapa_atual,
        "id_etapa_cliente": etapa_cliente,
        "id_etapa_resposta": etapa_resposta,
        "id_etapa_origem_transicao": etapa_cliente,
        "transicoes_permitidas": transicoes,
        "retry_count": retry,
        "texto_cliente_atual": "Ola",
        "tipo_mensagem_atual": "text",
        "mensagem_cliente_atual": {
            "id_mensagem_fila": 20,
            "id_hash_msg": "wamid.cliente",
            "cliente_telefone": "5571999999999",
            "id_phone_unidade": "123456",
        },
        "resposta_bot_para_mensagem_atual": resposta_bot,
    }


class FlowSenderTests(unittest.TestCase):
    def test_idempotente_nao_chama_etapa1_quando_resposta_ja_existe(self):
        def falhar_se_chamar(*_args, **_kwargs):
            raise AssertionError("primeira etapa nao deveria ser chamada")

        with patch.object(
            flow_sender_module,
            "resolve_etapa1",
            falhar_se_chamar,
        ):
            resultado = flow_sender_module.flow_sender(
                contexto_historico_base(
                    resposta_bot={
                        "id_mensagem": 99,
                        "id_hash_msg": "wamid.bot.existente",
                        "id_etapa": 1,
                    }
                )
            )

        self.assertFalse(resultado["enviou"])
        self.assertTrue(resultado["resposta_ja_existia"])
        self.assertEqual(resultado["id_hash_msg_bot"], "wamid.bot.existente")
        self.assertEqual(resultado["id_etapa_resultante"], 1)

    def test_retry_para_mim_reconstroi_evento_dois_para_quatro(self):
        resultado = flow_sender_module.flow_sender(
            contexto_historico_base(
                resposta_bot={
                    "id_mensagem": 100,
                    "id_hash_msg": "wamid.bot.idade",
                    "id_etapa": 4,
                },
                etapa_atual=4,
                etapa_cliente=2,
                retry=2,
                transicoes={
                    EVENTO_PARA_MIM: 4,
                    EVENTO_PARA_OUTRA_PESSOA: 3,
                },
            )
        )

        self.assertFalse(resultado["enviou"])
        self.assertTrue(resultado["resposta_ja_existia"])
        self.assertEqual(resultado["evento_transicao"], EVENTO_PARA_MIM)
        self.assertEqual(resultado["id_etapa_resultante"], 4)

    def test_retry_reconstroi_evento_nome_dependente_tres_para_quatro(self):
        resultado = flow_sender_module.flow_sender(
            contexto_historico_base(
                resposta_bot={
                    "id_mensagem": 101,
                    "id_hash_msg": "wamid.etapa4",
                    "id_etapa": 4,
                },
                etapa_atual=4,
                etapa_cliente=3,
                retry=2,
                transicoes={
                    EVENTO_NOME_DEPENDENTE_VALIDO: 4,
                },
            )
        )

        self.assertFalse(resultado["enviou"])
        self.assertTrue(resultado["resposta_ja_existia"])
        self.assertEqual(
            resultado["evento_transicao"],
            EVENTO_NOME_DEPENDENTE_VALIDO,
        )
        self.assertEqual(resultado["id_etapa_resultante"], 4)

    def test_conversa_sem_etapa_vai_para_etapa1(self):
        esperado = {
            "enviou": True,
            "resposta_ja_existia": False,
            "id_hash_msg_bot": "wamid.bot",
            "id_etapa_resultante": 1,
        }

        with patch.object(
            flow_sender_module,
            "resolve_etapa1",
            return_value=esperado,
        ) as resolver:
            resultado = flow_sender_module.flow_sender(
                contexto_historico_base(etapa_atual=None)
            )

        resolver.assert_called_once()
        self.assertEqual(resultado, esperado)

    def test_etapa1_vai_para_etapa1(self):
        esperado = {
            "enviou": True,
            "resposta_ja_existia": False,
            "id_hash_msg_bot": "wamid.bot",
            "id_etapa_resultante": 1,
        }

        with patch.object(
            flow_sender_module,
            "resolve_etapa1",
            return_value=esperado,
        ) as resolver:
            resultado = flow_sender_module.flow_sender(
                contexto_historico_base(etapa_atual=1, etapa_resposta=2)
            )

        resolver.assert_called_once()
        self.assertEqual(resultado, esperado)

    def test_etapa2_vai_para_etapa2(self):
        esperado = {
            "enviou": True,
            "resposta_ja_existia": False,
            "id_hash_msg_bot": "wamid.bot",
            "id_etapa_resultante": 2,
        }

        with patch.object(
            flow_sender_module,
            "resolve_etapa2",
            return_value=esperado,
        ) as resolver:
            resultado = flow_sender_module.flow_sender(
                contexto_historico_base(etapa_atual=2, etapa_resposta=3)
            )

        resolver.assert_called_once()
        self.assertEqual(resultado, esperado)

    def test_etapa3_vai_para_etapa3(self):
        esperado = {
            "enviou": True,
            "resposta_ja_existia": False,
            "id_hash_msg_bot": "wamid.etapa4",
            "id_etapa_resultante": 4,
        }

        with patch.object(
            flow_sender_module,
            "resolve_etapa3",
            return_value=esperado,
        ) as resolver:
            resultado = flow_sender_module.flow_sender(
                contexto_historico_base(
                    etapa_atual=3,
                    etapa_resposta=4,
                )
            )

        resolver.assert_called_once()
        self.assertEqual(resultado, esperado)

    def test_etapa4_vai_para_etapa4(self):
        esperado = {
            "enviou": True,
            "envio_simulado": True,
            "id_hash_msg_bot": "simulacao.etapa5",
            "id_etapa_resultante": 5,
        }

        with patch.object(
            flow_sender_module,
            "resolve_etapa4",
            return_value=esperado,
        ) as resolver:
            resultado = flow_sender_module.flow_sender(
                contexto_historico_base(
                    etapa_atual=4,
                    etapa_resposta=5,
                    etapa_cliente=4,
                    transicoes={EVENTO_IDADE_VALIDA: 5},
                )
            )

        resolver.assert_called_once()
        self.assertEqual(resultado, esperado)

    def test_etapa_nao_implementada_nao_finge_sucesso(self):
        with self.assertRaises(NotImplementedError):
            flow_sender_module.flow_sender(
                contexto_historico_base(etapa_atual=5, etapa_resposta=6)
            )


if __name__ == "__main__":
    unittest.main()
