import unittest
from unittest.mock import patch

from workers.worker_flow.suporte import cache_repair
from workers.worker_flow.transacoes import ordem_turno
from workers.worker_flow.transacoes import persistencia_resposta as persistencia


DATA_BOT = "2026-01-01T00:00:00"


def contexto_historico_base(
    resposta_bot=None,
    *,
    id_etapa_atual=None,
    texto_cliente="Ola",
):
    return {
        "resposta_bot_para_mensagem_atual": resposta_bot,
        "id_conversa": 10,
        "id_etapa_atual": id_etapa_atual,
        "texto_cliente_atual": texto_cliente,
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
            persistencia,
            "inserir_historico_mensagem_bot",
            fake_inserir_historico,
        ), patch.object(
            persistencia,
            "atualizar_conversa_resposta_bot",
            fake_atualizar_conversa,
        ), patch.object(
            persistencia,
            "atualizar_conversa_resposta_bot_sem_avancar",
            fake_atualizar_sem_avancar,
        ):
            resultado = persistencia.atualizar_banco_com_contexto_final(
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
            persistencia,
            "inserir_historico_mensagem_bot",
            fake_inserir_historico,
        ), patch.object(
            persistencia,
            "atualizar_conversa_resposta_bot",
            fake_atualizar_conversa,
        ), patch.object(
            persistencia,
            "atualizar_conversa_resposta_bot_sem_avancar",
            fake_atualizar_sem_avancar,
        ):
            resultado = persistencia.atualizar_banco_com_contexto_final(
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
            persistencia,
            "inserir_historico_mensagem_bot",
            fake_inserir_historico,
        ), patch.object(
            persistencia,
            "atualizar_conversa_resposta_bot",
            fake_atualizar_conversa,
        ), patch.object(
            persistencia,
            "atualizar_conversa_resposta_bot_sem_avancar",
            fake_atualizar_sem_avancar,
        ):
            resultado = persistencia.atualizar_banco_com_contexto_final(
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
            persistencia,
            "inserir_historico_mensagem_bot",
            fake_inserir_historico,
        ), patch.object(
            persistencia,
            "atualizar_conversa_resposta_bot",
            fake_atualizar_conversa,
        ), patch.object(
            persistencia,
            "atualizar_conversa_resposta_bot_sem_avancar",
            fake_atualizar_sem_avancar,
        ):
            resultado = persistencia.atualizar_banco_com_contexto_final(
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

    def test_atualizar_banco_conforme_transicao_de_etapa_salva_nome_quando_etapa_um_avanca_para_dois(self):
        chamadas = []
        cursor = object()

        def fake_atualizar_nome(telefone, nome, cursor_recebido):
            chamadas.append((telefone, nome, cursor_recebido))
            return 1

        with patch.object(
            persistencia,
            "atualizar_nome_cliente_por_telefone",
            fake_atualizar_nome,
        ):
            resultado = persistencia.atualizar_banco_conforme_transicao_de_etapa(
                contexto_historico_base(
                    id_etapa_atual=1,
                    texto_cliente="Maria",
                ),
                {
                    "id_etapa_resultante": 2,
                    "primeiro_nome_cliente": "Maria",
                },
                cursor,
            )

        self.assertEqual(chamadas, [("5571999999999", "Maria", cursor)])
        self.assertEqual(
            resultado,
            {
                "cliente_nome_atualizado": True,
                "primeiro_nome_cliente": "Maria",
            },
        )

    def test_atualizar_banco_conforme_transicao_de_etapa_reconstroi_nome_em_reparo_idempotente(self):
        chamadas = []
        cursor = object()

        def fake_atualizar_nome(telefone, nome, cursor_recebido):
            chamadas.append((telefone, nome, cursor_recebido))
            return 1

        with patch.object(
            persistencia,
            "atualizar_nome_cliente_por_telefone",
            fake_atualizar_nome,
        ):
            resultado = persistencia.atualizar_banco_conforme_transicao_de_etapa(
                contexto_historico_base(
                    id_etapa_atual=1,
                    texto_cliente="Maria",
                ),
                {
                    "resposta_ja_existia": True,
                    "id_etapa_resultante": 2,
                },
                cursor,
            )

        self.assertEqual(chamadas, [("5571999999999", "Maria", cursor)])
        self.assertEqual(resultado["primeiro_nome_cliente"], "Maria")

    def test_atualizar_banco_conforme_transicao_de_etapa_nao_salva_nome_em_tratamento(self):
        cursor = object()

        with patch.object(
            persistencia,
            "atualizar_nome_cliente_por_telefone",
        ) as atualizar_nome:
            resultado = persistencia.atualizar_banco_conforme_transicao_de_etapa(
                contexto_historico_base(
                    id_etapa_atual=1,
                    texto_cliente="Maria",
                ),
                {
                    "id_etapa_resultante": 2,
                    "primeiro_nome_cliente": "Maria",
                    "tratamento": True,
                },
                cursor,
            )

        self.assertIsNone(resultado)
        atualizar_nome.assert_not_called()

    def test_atualizar_banco_conforme_transicao_de_etapa_falha_se_nome_nao_for_resolvido(self):
        cursor = object()

        with patch.object(
            persistencia,
            "atualizar_nome_cliente_por_telefone",
        ) as atualizar_nome:
            with self.assertRaises(ValueError):
                persistencia.atualizar_banco_conforme_transicao_de_etapa(
                    contexto_historico_base(
                        id_etapa_atual=1,
                        texto_cliente="99",
                    ),
                    {
                        "id_etapa_resultante": 2,
                    },
                    cursor,
                )

        atualizar_nome.assert_not_called()

    def test_resposta_existente_sem_data_persistida_falha(self):
        with self.assertRaises(ValueError):
            persistencia.atualizar_banco_com_contexto_final(
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
            persistencia.atualizar_banco_com_contexto_final(
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
            ordem_turno,
            "existe_mensagem_anterior_aberta_conversa",
            return_value=True,
        ), patch.object(
            ordem_turno,
            "reagendar_mensagem_sem_erro",
            fake_reagendar,
        ):
            resultado = ordem_turno.reagendar_se_houver_mensagem_anterior(
                mensagem,
                contexto_banco,
                lock_version=7,
                cursor=cursor,
            )

        self.assertTrue(resultado)
        self.assertEqual(chamadas, [(44, 30, cursor)])

    def test_reparar_cache_cliente_stale_so_age_com_fk_cliente(self):
        estado = {"cliente_telefone": "5571999999999", "id_mensagem": 1}

        with patch.object(cache_repair, "remover_cliente_cache", return_value=True) as remover:
            self.assertTrue(
                cache_repair.reparar_cache_cliente_stale_se_fk_invalida(
                    RuntimeError("violates foreign key constraint conversa_id_cliente_fkey"),
                    estado,
                )
            )
            remover.assert_called_once_with("5571999999999")

        with patch.object(cache_repair, "remover_cliente_cache", return_value=True) as remover:
            self.assertFalse(
                cache_repair.reparar_cache_cliente_stale_se_fk_invalida(
                    RuntimeError("erro qualquer"),
                    estado,
                )
            )
            remover.assert_not_called()


if __name__ == "__main__":
    unittest.main()
