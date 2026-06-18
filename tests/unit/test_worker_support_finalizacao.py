import unittest
from unittest.mock import patch

from workers.worker_flow import suport_functions as support


DATA_BOT = "2026-01-01T00:00:00"


def contexto_historico_base(resposta_bot=None):
    return {
        "resposta_bot_para_mensagem_atual": resposta_bot,
        "id_conversa": 10,
        "mensagem_cliente_atual": {
            "id_mensagem_fila": 20,
            "id_hash_msg": "wamid.cliente",
            "cliente_telefone": "5571999999999",
            "id_phone_unidade": "123456",
            "unidade_telefone": "5571000000000",
        },
    }


class WorkerSupportFinalizacaoTests(unittest.TestCase):
    def test_atualizar_banco_com_contexto_final_persiste_bot_e_conversa(self):
        chamadas = []

        def fake_inserir_historico(contexto_historico, contexto_envio, cursor):
            chamadas.append(("insert_bot", contexto_historico, contexto_envio, cursor))
            return 300, DATA_BOT, True

        def fake_atualizar_conversa(
            id_conversa,
            id_etapa_resultante,
            data_interacao,
            cursor,
        ):
            chamadas.append(
                (
                    "update_conversa",
                    id_conversa,
                    id_etapa_resultante,
                    data_interacao,
                    cursor,
                )
            )
            return 1

        def fake_atualizar_sem_avancar(*_args, **_kwargs):
            raise AssertionError("fluxo normal deve atualizar conversa com etapa")

        cursor = object()
        contexto_envio = {
            "enviou": True,
            "resposta_ja_existia": False,
            "mensagem_bot": "Ola!",
            "id_hash_msg_bot": "wamid.bot",
            "id_etapa_resultante": 1,
            "tipo_mensagem": "interactive_button",
        }

        with patch.object(
            support,
            "inserir_historico_mensagem_bot",
            fake_inserir_historico,
        ), patch.object(
            support,
            "atualizar_conversa_resposta_bot",
            fake_atualizar_conversa,
        ), patch.object(
            support,
            "atualizar_conversa_resposta_bot_sem_avancar",
            fake_atualizar_sem_avancar,
        ):
            resultado = support.atualizar_banco_com_contexto_final(
                contexto_historico_base(),
                contexto_envio,
                cursor,
            )

        self.assertEqual([chamada[0] for chamada in chamadas], ["insert_bot", "update_conversa"])
        self.assertTrue(resultado["historico_bot_inserido"])
        self.assertEqual(resultado["id_hash_msg_bot"], "wamid.bot")
        self.assertTrue(resultado["atualizar_conversa"])
        self.assertTrue(resultado["atualizar_last_from_bot"])

    def test_tratamento_persiste_bot_sem_avancar_mas_volta_last_from_para_bot(self):
        chamadas = []

        def fake_inserir_historico(contexto_historico, contexto_envio, cursor):
            chamadas.append(("insert_bot", contexto_historico, contexto_envio, cursor))
            return 301, DATA_BOT, True

        def fake_atualizar_conversa(*_args, **_kwargs):
            raise AssertionError("tratamento nao deve atualizar etapa da conversa")

        def fake_atualizar_sem_avancar(
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

        contexto_envio = {
            "enviou": True,
            "resposta_ja_existia": False,
            "mensagem_bot": "Tratamento",
            "id_hash_msg_bot": "wamid.bot.tratamento",
            "id_etapa_resultante": 1,
            "tipo_mensagem": "interactive_button",
            "tratamento": True,
            "atualizar_conversa": False,
            "atualizar_last_from_bot": True,
        }

        cursor = object()

        with patch.object(
            support,
            "inserir_historico_mensagem_bot",
            fake_inserir_historico,
        ), patch.object(
            support,
            "atualizar_conversa_resposta_bot",
            fake_atualizar_conversa,
        ), patch.object(
            support,
            "atualizar_conversa_resposta_bot_sem_avancar",
            fake_atualizar_sem_avancar,
        ):
            resultado = support.atualizar_banco_com_contexto_final(
                contexto_historico_base(),
                contexto_envio,
                cursor,
            )

        self.assertEqual(
            [chamada[0] for chamada in chamadas],
            ["insert_bot", "update_bot_sem_avancar"],
        )
        self.assertTrue(resultado["historico_bot_inserido"])
        self.assertFalse(resultado["atualizar_conversa"])
        self.assertTrue(resultado["atualizar_last_from_bot"])

    def test_resposta_ja_existia_nao_insere_historico_do_bot(self):
        chamadas = []

        def fake_inserir_historico(*_args, **_kwargs):
            raise AssertionError("nao deve inserir historico quando resposta ja existe")

        def fake_atualizar_conversa(
            id_conversa,
            id_etapa_resultante,
            data_interacao,
            cursor,
        ):
            chamadas.append(
                (
                    id_conversa,
                    id_etapa_resultante,
                    data_interacao,
                    cursor,
                )
            )
            return 1

        def fake_atualizar_sem_avancar(*_args, **_kwargs):
            raise AssertionError("resposta normal idempotente deve atualizar etapa")

        cursor = object()

        with patch.object(
            support,
            "inserir_historico_mensagem_bot",
            fake_inserir_historico,
        ), patch.object(
            support,
            "atualizar_conversa_resposta_bot",
            fake_atualizar_conversa,
        ), patch.object(
            support,
            "atualizar_conversa_resposta_bot_sem_avancar",
            fake_atualizar_sem_avancar,
        ):
            resultado = support.atualizar_banco_com_contexto_final(
                contexto_historico_base(
                    {"received_data_hora": DATA_BOT}
                ),
                {
                    "enviou": False,
                    "resposta_ja_existia": True,
                    "id_hash_msg_bot": "wamid.bot.existente",
                    "id_etapa_resultante": 1,
                },
                cursor,
            )

        self.assertEqual(chamadas, [(10, 1, DATA_BOT, cursor)])
        self.assertTrue(resultado["resposta_ja_existia"])
        self.assertFalse(resultado["historico_bot_inserido"])
        self.assertTrue(resultado["atualizar_conversa"])
        self.assertTrue(resultado["atualizar_last_from_bot"])

    def test_resposta_ja_existia_de_tratamento_nao_atualiza_etapa_mas_volta_last_from_para_bot(self):
        chamadas = []

        def fake_inserir_historico(*_args, **_kwargs):
            raise AssertionError("nao deve inserir historico quando resposta ja existe")

        def fake_atualizar_conversa(*_args, **_kwargs):
            raise AssertionError("tratamento idempotente nao deve atualizar etapa")

        def fake_atualizar_sem_avancar(
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
            support,
            "inserir_historico_mensagem_bot",
            fake_inserir_historico,
        ), patch.object(
            support,
            "atualizar_conversa_resposta_bot",
            fake_atualizar_conversa,
        ), patch.object(
            support,
            "atualizar_conversa_resposta_bot_sem_avancar",
            fake_atualizar_sem_avancar,
        ):
            resultado = support.atualizar_banco_com_contexto_final(
                contexto_historico_base(
                    {"received_data_hora": DATA_BOT}
                ),
                {
                    "enviou": False,
                    "resposta_ja_existia": True,
                    "id_hash_msg_bot": "wamid.bot.existente",
                    "id_etapa_resultante": 1,
                    "atualizar_conversa": False,
                    "atualizar_last_from_bot": True,
                },
                cursor,
            )

        self.assertEqual(
            chamadas,
            [("update_bot_sem_avancar", 10, DATA_BOT, cursor)],
        )
        self.assertTrue(resultado["resposta_ja_existia"])
        self.assertFalse(resultado["historico_bot_inserido"])
        self.assertFalse(resultado["atualizar_conversa"])
        self.assertTrue(resultado["atualizar_last_from_bot"])

    def test_resposta_existente_sem_data_persistida_falha(self):
        with self.assertRaises(ValueError):
            support.atualizar_banco_com_contexto_final(
                contexto_historico_base({}),
                {
                    "enviou": False,
                    "resposta_ja_existia": True,
                    "id_hash_msg_bot": "wamid.bot.existente",
                    "id_etapa_resultante": 1,
                },
                object(),
            )

    def test_contexto_sem_envio_e_sem_resposta_existente_falha(self):
        with self.assertRaises(ValueError):
            support.atualizar_banco_com_contexto_final(
                contexto_historico_base(),
                {
                    "enviou": False,
                    "resposta_ja_existia": False,
                    "id_etapa_resultante": 1,
                },
                object(),
            )

    def test_reagendar_se_houver_mensagem_anterior_reagenda(self):
        chamadas = []

        def fake_reagendar(id_mensagem, cursor, delay_seconds=30):
            chamadas.append((id_mensagem, delay_seconds, cursor))
            return 1

        mensagem = {
            "id_mensagem": 44,
            "cliente_telefone": "5571999999999",
            "id_phone_unidade": "123456",
            "data_recebimento": "2026-01-01T00:00:00",
        }
        contexto_banco = {"conversa": {"id_conversa": 10}}
        cursor = object()

        with patch.object(
            support,
            "existe_mensagem_anterior_aberta_conversa",
            return_value=True,
        ), patch.object(
            support,
            "reagendar_mensagem_sem_erro",
            fake_reagendar,
        ):
            resultado = support.reagendar_se_houver_mensagem_anterior(
                mensagem,
                contexto_banco,
                lock_version=7,
                cursor=cursor,
            )

        self.assertTrue(resultado)
        self.assertEqual(chamadas, [(44, 30, cursor)])

    def test_reparar_cache_cliente_stale_so_age_com_fk_cliente(self):
        estado = {"cliente_telefone": "5571999999999", "id_mensagem": 1}

        with patch.object(support, "remover_cliente_cache", return_value=True) as remover:
            self.assertTrue(
                support.reparar_cache_cliente_stale_se_fk_invalida(
                    RuntimeError("violates foreign key constraint conversa_id_cliente_fkey"),
                    estado,
                )
            )
            remover.assert_called_once_with("5571999999999")

        with patch.object(support, "remover_cliente_cache", return_value=True) as remover:
            self.assertFalse(
                support.reparar_cache_cliente_stale_se_fk_invalida(
                    RuntimeError("erro qualquer"),
                    estado,
                )
            )
            remover.assert_not_called()


if __name__ == "__main__":
    unittest.main()
