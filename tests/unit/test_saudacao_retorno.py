import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from core.integrations.whatsapp.messages.componentes_compartilhados import (
    montar_saudacao_retorno,
)
from core.integrations.whatsapp.pywa_functions import cliente
from core.repositories.atendimento import historico
from workers.worker_flow.response_flow import flow_sender


SAUDACAO = "Bom te ver novamente, Maria ☺️\n"


def contexto_sender(*, saudacao=SAUDACAO, resposta_bot=None, etapa=2):
    return {
        "id_conversa": 10,
        "id_etapa_atual": etapa,
        "id_etapa_origem_transicao": etapa,
        "retry_count": 1,
        "saudacao_retorno": saudacao,
        "status_dependente": False,
        "mensagem_cliente_atual": {
            "id_mensagem_fila": 20,
            "id_hash_msg": "wamid.cliente",
        },
        "resposta_bot_para_mensagem_atual": resposta_bot,
    }


def contexto_envio(texto, *, tratamento=False):
    return {
        "enviou": True,
        "resposta_ja_existia": False,
        "mensagem_bot": texto,
        "id_hash_msg_bot": "wamid.bot",
        "id_etapa_resultante": 3 if not tratamento else 2,
        "tipo_mensagem": "text",
        "tratamento": tratamento,
    }


class SaudacaoRetornoRegraTests(unittest.TestCase):
    def test_exatamente_tres_horas_ativa_a_saudacao(self):
        ultima_bot = datetime(2026, 8, 25, 8, 0, tzinfo=timezone.utc)

        resultado = montar_saudacao_retorno(
            "  Maria  ",
            ultima_bot,
            ultima_bot + timedelta(hours=3),
            2,
        )

        self.assertEqual(resultado, SAUDACAO)

    def test_antes_de_tres_horas_preserva_o_texto_da_v1_0_7(self):
        ultima_bot = datetime(2026, 8, 25, 8, 0)

        resultado = montar_saudacao_retorno(
            "Maria",
            ultima_bot,
            ultima_bot + timedelta(hours=3) - timedelta(seconds=1),
            2,
        )

        self.assertIsNone(resultado)

    def test_etapa_um_nome_ausente_e_datas_incompativeis_nao_saudam(self):
        ultima_bot = datetime(2026, 8, 25, 8, 0)
        atual = ultima_bot + timedelta(hours=4)

        casos = (
            ("Maria", ultima_bot, atual, 1),
            (None, ultima_bot, atual, 2),
            ("Maria", None, atual, 2),
            (
                "Maria",
                ultima_bot.replace(tzinfo=timezone.utc),
                atual,
                2,
            ),
        )

        for caso in casos:
            with self.subTest(caso=caso):
                self.assertIsNone(montar_saudacao_retorno(*caso))


class SaudacaoRetornoRepositorioTests(unittest.TestCase):
    def test_consulta_usa_apenas_ultimo_bot_sent_da_mesma_conversa(self):
        cursor = MagicMock()
        ultima_bot = datetime(2026, 8, 25, 8, 0)
        cursor.fetchone.return_value = ("Maria", ultima_bot)

        resultado = historico.buscar_contexto_saudacao_retorno(
            10,
            5,
            cursor,
        )

        consulta, parametros = cursor.execute.call_args.args
        self.assertIn("hm.id_conversa = cv.id_conversa", consulta)
        self.assertIn("hm.quem_enviou = 'bot'", consulta)
        self.assertIn("hm.status_envio = 'sent'", consulta)
        self.assertIn("hm.received_data_hora DESC", consulta)
        self.assertEqual(parametros, (10, 5))
        self.assertEqual(resultado, ("Maria", ultima_bot))

    def test_falha_sql_preserva_rollback_e_retry_do_worker(self):
        cursor = MagicMock()
        cursor.execute.side_effect = RuntimeError("banco indisponível")

        with self.assertRaisesRegex(RuntimeError, "banco indisponível"):
            historico.buscar_contexto_saudacao_retorno(10, 5, cursor)


class SaudacaoRetornoSenderTests(unittest.TestCase):
    def test_resposta_valida_recebe_prefixo_na_mesma_mensagem(self):
        resolver = MagicMock(
            return_value=contexto_envio(
                "Entendi. Vamos para a próxima etapa."
            )
        )
        with patch.object(
            flow_sender,
            "resolve_etapa2",
            resolver,
        ):
            resultado = flow_sender.flow_sender(contexto_sender())

        self.assertEqual(
            resultado["mensagem_bot"],
            f"{SAUDACAO}Entendi. Vamos para a próxima etapa.",
        )
        self.assertTrue(resultado["saudacao_retorno_aplicada"])
        self.assertFalse(resultado["tratamento"])

    def test_resposta_invalida_recebe_prefixo_e_mantem_tratamento(self):
        resolver = MagicMock(
            return_value=contexto_envio(
                "Não entendi. Escolha uma das opções.",
                tratamento=True,
            )
        )
        with patch.object(
            flow_sender,
            "resolve_etapa2",
            resolver,
        ):
            resultado = flow_sender.flow_sender(contexto_sender())

        self.assertEqual(
            resultado["mensagem_bot"],
            f"{SAUDACAO}Não entendi. Escolha uma das opções.",
        )
        self.assertTrue(resultado["tratamento"])
        self.assertEqual(resultado["id_etapa_resultante"], 2)

    def test_excecao_do_resolver_nao_vaza_prefixo_para_proximo_envio(self):
        with patch.object(
            flow_sender,
            "resolve_etapa2",
            side_effect=RuntimeError("falha no resolver"),
        ):
            with self.assertRaisesRegex(RuntimeError, "falha no resolver"):
                flow_sender.flow_sender(contexto_sender())

        self.assertEqual(
            cliente.aplicar_prefixo_mensagem_bot("Resposta posterior."),
            "Resposta posterior.",
        )

    def test_retry_com_resposta_existente_nao_chama_resolver(self):
        resposta_existente = {
            "id_mensagem": 30,
            "id_hash_msg": "wamid.bot.existente",
            "id_etapa": 2,
        }

        with patch.object(
            flow_sender,
            "resolve_etapa2",
            side_effect=AssertionError("resolver não pode rodar no retry"),
        ):
            resultado = flow_sender.flow_sender(
                contexto_sender(resposta_bot=resposta_existente)
            )

        self.assertFalse(resultado["enviou"])
        self.assertTrue(resultado["resposta_ja_existia"])
        self.assertNotIn("saudacao_retorno_aplicada", resultado)

    def test_transporte_e_historico_recebem_o_mesmo_prefixo_uma_vez(self):
        cliente_pywa = MagicMock()
        cliente_pywa.send_message.return_value = MagicMock(id="wamid.bot")

        with patch.object(
            cliente,
            "WhatsApp",
            return_value=cliente_pywa,
        ), patch.object(
            cliente,
            "get_meta_graph_api_version",
            return_value="23.0",
        ):
            with cliente.usar_prefixo_mensagem_bot(SAUDACAO):
                conta = cliente.conta_wa("123456")
                conta.send_message(
                    to="5571999999999",
                    text="Entendi.",
                )

            cliente.conta_wa("123456").send_message(
                to="5571999999999",
                text="Próxima resposta.",
            )

        chamadas = cliente_pywa.send_message.call_args_list
        self.assertEqual(chamadas[0].kwargs["text"], f"{SAUDACAO}Entendi.")
        self.assertEqual(chamadas[1].kwargs["text"], "Próxima resposta.")

    def test_pedido_de_contato_tambem_recebe_prefixo(self):
        cliente_pywa = MagicMock()
        cliente_pywa.request_contact_info.return_value = MagicMock(
            id="wamid.contato"
        )

        with patch.object(
            cliente,
            "WhatsApp",
            return_value=cliente_pywa,
        ), patch.object(
            cliente,
            "get_meta_graph_api_version",
            return_value="23.0",
        ), cliente.usar_prefixo_mensagem_bot(SAUDACAO):
            cliente.conta_wa("123456").request_contact_info(
                to="user-id",
                sender="123456",
                text="Compartilhe seu contato.",
                tracker="contato:10:etapa:2",
            )

        chamada = cliente_pywa.request_contact_info.call_args
        self.assertEqual(
            chamada.kwargs["text"],
            f"{SAUDACAO}Compartilhe seu contato.",
        )


if __name__ == "__main__":
    unittest.main()
