import unittest
from unittest.mock import patch

from workers.worker_flow.response_flow.etapas import (
    etapa1_worker as etapa_module,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_NOME_CLIENTE_VALIDO,
)


def contexto_historico(
    *,
    etapa_atual=None,
    etapa_resposta=1,
    tipo_mensagem="text",
    texto="Ola",
):
    return {
        "id_conversa": 10,
        "id_etapa_atual": etapa_atual,
        "id_etapa_cliente": 1,
        "id_etapa_resposta": etapa_resposta,
        "id_etapa_origem_transicao": 1,
        "transicoes_permitidas": {
            EVENTO_NOME_CLIENTE_VALIDO: 2,
        },
        "tipo_mensagem_atual": tipo_mensagem,
        "texto_cliente_atual": texto,
        "mensagem_cliente_atual": {
            "id_mensagem_fila": 20,
            "id_hash_msg": "wamid.cliente",
            "cliente_telefone": "5571999999999",
            "id_phone_unidade": "123456",
        },
    }


def retorno(nome, *, id_etapa_resultante=1):
    return {
        "nome": nome,
        "enviou": True,
        "resposta_ja_existia": False,
        "id_hash_msg_bot": f"wamid.{nome}",
        "id_etapa_resultante": id_etapa_resultante,
    }


class Etapa1WorkerTests(unittest.TestCase):
    def test_conversa_nova_com_midia_usa_tratamento_de_inicio(self):
        with patch.object(
            etapa_module,
            "enviar_etapa1_midia_inicio",
            return_value=retorno("midia_inicio"),
        ) as sender:
            resultado = etapa_module.resolve_etapa1(
                contexto_historico(tipo_mensagem="image")
            )

        sender.assert_called_once_with("5571999999999", "123456")
        self.assertEqual(resultado["nome"], "midia_inicio")

    def test_conversa_nova_com_financeiro_usa_tratamento_de_inicio(self):
        with patch.object(
            etapa_module,
            "enviar_etapa1_financeiro_inicio",
            return_value=retorno("financeiro_inicio"),
        ) as sender:
            resultado = etapa_module.resolve_etapa1(
                contexto_historico(texto="qual o valor?")
            )

        sender.assert_called_once_with("5571999999999", "123456")
        self.assertEqual(resultado["nome"], "financeiro_inicio")

    def test_conversa_nova_com_texto_normal_envia_etapa1(self):
        with patch.object(
            etapa_module,
            "enviar_etapa1",
            return_value=retorno("etapa1"),
        ) as sender:
            resultado = etapa_module.resolve_etapa1(
                contexto_historico(texto="ola")
            )

        sender.assert_called_once_with("5571999999999", "123456")
        self.assertEqual(resultado["nome"], "etapa1")

    def test_etapa1_com_midia_usa_tratamento_da_etapa(self):
        with patch.object(
            etapa_module,
            "enviar_etapa1_midia",
            return_value=retorno("midia_etapa1"),
        ) as sender:
            resultado = etapa_module.resolve_etapa1(
                contexto_historico(etapa_atual=1, etapa_resposta=2, tipo_mensagem="video")
            )

        sender.assert_called_once_with("5571999999999", "123456")
        self.assertEqual(resultado["nome"], "midia_etapa1")

    def test_etapa1_com_financeiro_usa_tratamento_da_etapa(self):
        with patch.object(
            etapa_module,
            "enviar_etapa1_financeiro",
            return_value=retorno("financeiro_etapa1"),
        ) as sender:
            resultado = etapa_module.resolve_etapa1(
                contexto_historico(etapa_atual=1, etapa_resposta=2, texto="quanto custa?")
            )

        sender.assert_called_once_with("5571999999999", "123456")
        self.assertEqual(resultado["nome"], "financeiro_etapa1")

    def test_etapa1_com_nome_invalido_usa_tratamento_de_contexto(self):
        with patch.object(
            etapa_module,
            "enviar_etapa1_contexto_nome_invalido",
            return_value=retorno("nome_invalido"),
        ) as sender:
            resultado = etapa_module.resolve_etapa1(
                contexto_historico(etapa_atual=1, etapa_resposta=2, texto="pppppp")
            )

        sender.assert_called_once_with("5571999999999", "123456")
        self.assertEqual(resultado["nome"], "nome_invalido")

    def test_etapa1_com_nome_valido_envia_etapa2(self):
        with patch.object(
            etapa_module,
            "enviar_etapa2",
            return_value=retorno("etapa2", id_etapa_resultante=2),
        ) as sender:
            resultado = etapa_module.resolve_etapa1(
                contexto_historico(etapa_atual=1, etapa_resposta=2, texto="Maria")
            )

        sender.assert_called_once_with(
            "5571999999999",
            "123456",
            nome="Maria",
        )
        self.assertEqual(resultado["nome"], "etapa2")
        self.assertEqual(resultado["id_etapa_resultante"], 2)
        self.assertEqual(resultado["primeiro_nome_cliente"], "Maria")

    def test_etapa1_com_nome_composto_envia_etapa2_sem_ponto(self):
        with patch.object(
            etapa_module,
            "enviar_etapa2",
            return_value=retorno("etapa2", id_etapa_resultante=2),
        ) as sender:
            resultado = etapa_module.resolve_etapa1(
                contexto_historico(
                    etapa_atual=1,
                    etapa_resposta=2,
                    texto="Maria Julia.",
                )
            )

        sender.assert_called_once_with(
            "5571999999999",
            "123456",
            nome="Maria Julia",
        )
        self.assertEqual(resultado["primeiro_nome_cliente"], "Maria Julia")

    def test_etapa1_preserva_til_ao_enviar_etapa2(self):
        with patch.object(
            etapa_module,
            "enviar_etapa2",
            return_value=retorno("etapa2", id_etapa_resultante=2),
        ) as sender:
            resultado = etapa_module.resolve_etapa1(
                contexto_historico(
                    etapa_atual=1,
                    etapa_resposta=2,
                    texto="he joao",
                )
            )

        sender.assert_called_once_with(
            "5571999999999",
            "123456",
            nome="João",
        )
        self.assertEqual(resultado["primeiro_nome_cliente"], "João")

    def test_etapa1_remove_sobrenome_antes_de_enviar_etapa2(self):
        with patch.object(
            etapa_module,
            "enviar_etapa2",
            return_value=retorno("etapa2", id_etapa_resultante=2),
        ) as sender:
            resultado = etapa_module.resolve_etapa1(
                contexto_historico(
                    etapa_atual=1,
                    etapa_resposta=2,
                    texto="Carlos Silva",
                )
            )

        sender.assert_called_once_with(
            "5571999999999",
            "123456",
            nome="Carlos",
        )
        self.assertEqual(resultado["primeiro_nome_cliente"], "Carlos")


if __name__ == "__main__":
    unittest.main()
