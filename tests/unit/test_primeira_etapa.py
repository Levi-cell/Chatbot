import unittest
from unittest.mock import patch

from workers.worker_flow.response_flow.etapas import (
    primeira_etapa as etapa_module,
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


class PrimeiraEtapaTests(unittest.TestCase):
    def test_conversa_nova_com_midia_usa_tratamento_de_inicio(self):
        with patch.object(
            etapa_module,
            "enviar_primeira_etapa_midia_inicio",
            return_value=retorno("midia_inicio"),
        ) as sender:
            resultado = etapa_module.resolve_primeira_etapa(
                contexto_historico(tipo_mensagem="image")
            )

        sender.assert_called_once_with("5571999999999", "123456")
        self.assertEqual(resultado["nome"], "midia_inicio")

    def test_conversa_nova_com_financeiro_usa_tratamento_de_inicio(self):
        with patch.object(
            etapa_module,
            "enviar_primeira_etapa_financeiro_inicio",
            return_value=retorno("financeiro_inicio"),
        ) as sender:
            resultado = etapa_module.resolve_primeira_etapa(
                contexto_historico(texto="qual o valor?")
            )

        sender.assert_called_once_with("5571999999999", "123456")
        self.assertEqual(resultado["nome"], "financeiro_inicio")

    def test_conversa_nova_com_texto_normal_envia_primeira_etapa(self):
        with patch.object(
            etapa_module,
            "enviar_primeira_etapa",
            return_value=retorno("etapa_1"),
        ) as sender:
            resultado = etapa_module.resolve_primeira_etapa(
                contexto_historico(texto="ola")
            )

        sender.assert_called_once_with("5571999999999", "123456")
        self.assertEqual(resultado["nome"], "etapa_1")

    def test_etapa_um_com_midia_usa_tratamento_da_etapa(self):
        with patch.object(
            etapa_module,
            "enviar_primeira_etapa_midia",
            return_value=retorno("midia_etapa_1"),
        ) as sender:
            resultado = etapa_module.resolve_primeira_etapa(
                contexto_historico(etapa_atual=1, etapa_resposta=2, tipo_mensagem="video")
            )

        sender.assert_called_once_with("5571999999999", "123456")
        self.assertEqual(resultado["nome"], "midia_etapa_1")

    def test_etapa_um_com_financeiro_usa_tratamento_da_etapa(self):
        with patch.object(
            etapa_module,
            "enviar_primeira_etapa_financeiro",
            return_value=retorno("financeiro_etapa_1"),
        ) as sender:
            resultado = etapa_module.resolve_primeira_etapa(
                contexto_historico(etapa_atual=1, etapa_resposta=2, texto="quanto custa?")
            )

        sender.assert_called_once_with("5571999999999", "123456")
        self.assertEqual(resultado["nome"], "financeiro_etapa_1")

    def test_etapa_um_com_nome_invalido_usa_tratamento_de_contexto(self):
        with patch.object(
            etapa_module,
            "enviar_primeira_etapa_contexto_nome_invalido",
            return_value=retorno("nome_invalido"),
        ) as sender:
            resultado = etapa_module.resolve_primeira_etapa(
                contexto_historico(etapa_atual=1, etapa_resposta=2, texto="pppppp")
            )

        sender.assert_called_once_with("5571999999999", "123456")
        self.assertEqual(resultado["nome"], "nome_invalido")

    def test_etapa_um_com_nome_valido_envia_segunda_etapa(self):
        with patch.object(
            etapa_module,
            "enviar_segunda_etapa",
            return_value=retorno("etapa_2", id_etapa_resultante=2),
        ) as sender:
            resultado = etapa_module.resolve_primeira_etapa(
                contexto_historico(etapa_atual=1, etapa_resposta=2, texto="Maria")
            )

        sender.assert_called_once_with(
            "5571999999999",
            "123456",
            nome="Maria",
        )
        self.assertEqual(resultado["nome"], "etapa_2")
        self.assertEqual(resultado["id_etapa_resultante"], 2)
        self.assertEqual(resultado["primeiro_nome_cliente"], "Maria")


if __name__ == "__main__":
    unittest.main()
