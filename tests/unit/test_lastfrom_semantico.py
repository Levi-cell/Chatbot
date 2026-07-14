import unittest
from unittest.mock import patch

from workers.worker_flow import valida_historico


DATA_CLIENTE = "2026-01-01T00:00:00"
DATA_BOT = "2026-01-01T00:01:00"


def mensagem_base(retry=1):
    return {
        "id_mensagem": 20,
        "cliente_telefone": "5571999999999",
        "conteudo_texto": "ola",
        "tipo_mensagem": "text",
        "id_phone_unidade": "123456",
        "unidade_telefone": "5571000000000",
        "data_recebimento": "2026-01-01T00:00:00",
        "id_hash": "wamid.cliente",
        "retry_count": retry,
    }


def contexto_banco_base(last_from="bot", etapa=1):
    return {
        "id_unidade": 1,
        "conversa": {
            "id_conversa": 10,
            "id_etapa_atual": etapa,
            "status_dependente": False,
            "last_message_from": last_from,
        }
    }


class LastFromSemanticoTests(unittest.TestCase):
    def test_conversa_nova_registra_cliente_e_responde_etapa1(self):
        chamadas = []

        def fake_inserir(mensagem, id_conversa, id_etapa, cursor):
            chamadas.append(("insert_cliente", id_conversa, id_etapa, cursor))
            return 100, DATA_CLIENTE, 1, True

        def fake_buscar_resposta(**_kwargs):
            return None

        def fake_update_cliente(
            id_conversa,
            data_interacao,
            cursor,
        ):
            chamadas.append(
                (
                    "update_cliente",
                    id_conversa,
                    data_interacao,
                    cursor,
                )
            )
            return 1

        def fake_update_bot(*_args, **_kwargs):
            raise AssertionError("conversa nova ainda nao tem resposta do bot")

        cursor = object()

        with patch.object(
            valida_historico,
            "inserir_historico_mensagem_cliente",
            fake_inserir,
        ), patch.object(
            valida_historico,
            "buscar_resposta_bot_por_mensagem_cliente",
            fake_buscar_resposta,
        ), patch.object(
            valida_historico,
            "atualizar_conversa_mensagem_cliente",
            fake_update_cliente,
        ), patch.object(
            valida_historico,
            "atualizar_conversa_resposta_bot_sem_avancar",
            fake_update_bot,
        ), patch.object(
            valida_historico,
            "listar_transicoes_permitidas",
            return_value={"nome_cliente_valido": 2},
        ), patch.object(
            valida_historico,
            "buscar_contexto_etapa1",
            return_value={"nome_unidade": "Supera Teste"},
        ):
            contexto = valida_historico.valida_historico(
                mensagem_base(),
                contexto_banco_base(last_from="cliente", etapa=None),
                cursor,
            )

        self.assertEqual(contexto["id_etapa_cliente"], 1)
        self.assertEqual(contexto["id_etapa_resposta"], 1)
        self.assertEqual(contexto["last_message_from"], "cliente")
        self.assertEqual(
            [chamada[0] for chamada in chamadas],
            ["insert_cliente", "update_cliente"],
        )

    def test_retry_antes_da_resposta_mantem_etapa_e_last_from_cliente(self):
        chamadas = []

        def fake_inserir(mensagem, id_conversa, id_etapa, cursor):
            chamadas.append(("insert_cliente", id_conversa, id_etapa, cursor))
            return 100, DATA_CLIENTE, 1, False

        def fake_buscar_resposta(**_kwargs):
            return None

        def fake_update_cliente(
            id_conversa,
            data_interacao,
            cursor,
        ):
            chamadas.append(
                (
                    "update_cliente",
                    id_conversa,
                    data_interacao,
                    cursor,
                )
            )
            return 1

        cursor = object()

        with patch.object(
            valida_historico,
            "inserir_historico_mensagem_cliente",
            fake_inserir,
        ), patch.object(
            valida_historico,
            "buscar_resposta_bot_por_mensagem_cliente",
            fake_buscar_resposta,
        ), patch.object(
            valida_historico,
            "atualizar_conversa_mensagem_cliente",
            fake_update_cliente,
        ), patch.object(
            valida_historico,
            "listar_transicoes_permitidas",
            return_value={"nome_cliente_valido": 2},
        ):
            contexto = valida_historico.valida_historico(
                mensagem_base(retry=2),
                contexto_banco_base(last_from="cliente", etapa=1),
                cursor,
            )

        self.assertEqual(contexto["id_etapa_cliente"], 1)
        self.assertEqual(contexto["id_etapa_resposta"], 2)
        self.assertEqual(contexto["last_message_from"], "cliente")
        self.assertFalse(contexto["mensagem_cliente_inserida"])

        self.assertIn(
            ("update_cliente", 10, DATA_CLIENTE, cursor),
            chamadas,
        )

    def test_retry_apos_resposta_usa_etapas_persistidas_sem_regredir(self):
        chamadas = []

        def fake_inserir(mensagem, id_conversa, id_etapa, cursor):
            chamadas.append(("insert_cliente", id_conversa, id_etapa, cursor))
            return 100, DATA_CLIENTE, 1, False

        def fake_buscar_resposta(**_kwargs):
            return (
                200,
                10,
                2,
                DATA_BOT,
                "5571999999999",
                "Ola",
                "text",
                "wamid.bot",
                20,
                "wamid.cliente",
                "123456",
                "5571000000000",
                "bot",
                "sent",
            )

        def fake_update_cliente(*_args, **_kwargs):
            raise AssertionError("nao deve atualizar cliente quando resposta bot ja existe")

        def fake_update_bot(*_args, **_kwargs):
            raise AssertionError("last_from ja esta semanticamente como bot")

        cursor = object()

        with patch.object(
            valida_historico,
            "inserir_historico_mensagem_cliente",
            fake_inserir,
        ), patch.object(
            valida_historico,
            "buscar_resposta_bot_por_mensagem_cliente",
            fake_buscar_resposta,
        ), patch.object(
            valida_historico,
            "atualizar_conversa_mensagem_cliente",
            fake_update_cliente,
        ), patch.object(
            valida_historico,
            "atualizar_conversa_resposta_bot_sem_avancar",
            fake_update_bot,
        ), patch.object(
            valida_historico,
            "listar_transicoes_permitidas",
            return_value={"nome_cliente_valido": 2},
        ):
            contexto = valida_historico.valida_historico(
                mensagem_base(retry=2),
                contexto_banco_base(last_from="bot", etapa=2),
                cursor,
            )

        self.assertEqual(contexto["id_etapa_cliente"], 1)
        self.assertEqual(contexto["id_etapa_resposta"], 2)
        self.assertEqual(contexto["last_message_from"], "bot")
        self.assertTrue(contexto["resposta_bot_para_mensagem_atual"])
        self.assertEqual([chamada[0] for chamada in chamadas], ["insert_cliente"])

    def test_retry_repara_last_from_cliente_quando_resposta_bot_ja_existe(self):
        chamadas = []

        def fake_inserir(mensagem, id_conversa, id_etapa, cursor):
            return 100, DATA_CLIENTE, 1, False

        def fake_buscar_resposta(**_kwargs):
            return (
                200,
                10,
                2,
                DATA_BOT,
                "5571999999999",
                "Ola",
                "text",
                "wamid.bot",
                20,
                "wamid.cliente",
                "123456",
                "5571000000000",
                "bot",
                "sent",
            )

        def fake_update_bot(
            id_conversa,
            data_interacao,
            cursor,
        ):
            chamadas.append(
                (
                    "update_bot_sem_avancar",
                    id_conversa,
                    data_interacao,
                    cursor,
                )
            )
            return 1

        cursor = object()

        with patch.object(
            valida_historico,
            "inserir_historico_mensagem_cliente",
            fake_inserir,
        ), patch.object(
            valida_historico,
            "buscar_resposta_bot_por_mensagem_cliente",
            fake_buscar_resposta,
        ), patch.object(
            valida_historico,
            "atualizar_conversa_resposta_bot_sem_avancar",
            fake_update_bot,
        ), patch.object(
            valida_historico,
            "listar_transicoes_permitidas",
            return_value={"nome_cliente_valido": 2},
        ):
            contexto = valida_historico.valida_historico(
                mensagem_base(retry=2),
                contexto_banco_base(last_from="cliente", etapa=2),
                cursor,
            )

        self.assertEqual(contexto["id_etapa_cliente"], 1)
        self.assertEqual(contexto["id_etapa_resposta"], 2)
        self.assertEqual(contexto["last_message_from"], "bot")
        self.assertEqual(
            chamadas,
            [("update_bot_sem_avancar", 10, DATA_BOT, cursor)],
        )


if __name__ == "__main__":
    unittest.main()
