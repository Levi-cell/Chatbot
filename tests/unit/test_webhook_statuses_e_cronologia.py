import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from django.test import override_settings

from callback.webhook.services import post_flow
from callback.webhook.services import populating_fila_mensagens as fila
from core.repositories.seguranca import turno_cliente
from tests.helpers import FakeCursor, FakeRequest, json_response_payload
from tests.payloads import payload_texto_meta


CLIENTE = "5571999999999"
PHONE_ID = "123456"


def payload_status_meta(status="sent"):
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba.test",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "5571000000000",
                                "phone_number_id": PHONE_ID,
                            },
                            "contacts": [
                                {
                                    "wa_id": CLIENTE,
                                }
                            ],
                            "statuses": [
                                {
                                    "id": "wamid.bot.test",
                                    "status": status,
                                    "timestamp": "1782509800",
                                    "recipient_id": CLIENTE,
                                    "pricing": {
                                        "billable": False,
                                        "pricing_model": "PMP",
                                        "category": "service",
                                        "type": "free_customer_service",
                                    },
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }


class WebhookStatusesTests(unittest.TestCase):
    def setUp(self):
        self.print_patcher = patch("builtins.print")
        self.print_patcher.start()
        self.addCleanup(self.print_patcher.stop)

    @override_settings(WEBHOOK_MAX_BODY_BYTES=1024 * 256)
    def test_status_valido_retorna_200_sem_flood_redis_banco_ou_fila(self):
        request = FakeRequest(payload_status_meta())

        with patch.object(
            post_flow,
            "validar_assinatura_meta",
            return_value=True,
        ), patch.object(
            post_flow,
            "responder_se_flood",
        ) as flood, patch.object(
            post_flow,
            "unidade_esta_ativa",
        ) as unidade, patch.object(
            post_flow,
            "conversa_esta_bloqueada_cache",
        ) as bloqueio, patch.object(
            post_flow,
            "get_conn",
        ) as get_conn:
            response = post_flow.responder_post_webhook(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(json_response_payload(response), {"status": "ok"})
        flood.assert_not_called()
        unidade.assert_not_called()
        bloqueio.assert_not_called()
        get_conn.assert_not_called()

    @override_settings(WEBHOOK_MAX_BODY_BYTES=1024 * 256)
    def test_status_com_assinatura_invalida_continua_rejeitado(self):
        request = FakeRequest(payload_status_meta())

        with patch.object(
            post_flow,
            "validar_assinatura_meta",
            return_value=False,
        ):
            response = post_flow.responder_post_webhook(request)

        self.assertEqual(response.status_code, 403)

    def test_classificador_distingue_messages_de_statuses(self):
        self.assertEqual(
            post_flow._classificar_evento_meta(payload_texto_meta()),
            post_flow.TIPO_EVENTO_MENSAGEM,
        )
        self.assertEqual(
            post_flow._classificar_evento_meta(payload_status_meta()),
            post_flow.TIPO_EVENTO_STATUS,
        )


class BarreiraCronologicaTests(unittest.TestCase):
    def test_timestamp_meta_preserva_instante_utc_com_fuso_explicito(self):
        timestamp_meta = "1760000000"

        dados = fila.extrair_dados_whatsapp(
            payload_texto_meta(timestamp=timestamp_meta)
        )

        esperado = datetime.fromtimestamp(
            int(timestamp_meta),
            tz=timezone.utc,
        )
        self.assertEqual(dados["received_data_hora"], esperado)
        self.assertEqual(dados["next_attempt_at"], esperado)
        self.assertIs(dados["received_data_hora"].tzinfo, timezone.utc)

    def test_mensagem_unica_reentregue_sem_interacao_posterior_e_aceita(self):
        recebida_em = datetime(2026, 6, 26, 18, 22, 11)

        with patch.object(
            turno_cliente,
            "buscar_interacao_posterior_a_mensagem",
            return_value=None,
        ), patch.object(
            turno_cliente,
            "avaliar_filas_abertas_turno",
            return_value={
                "existe_fila_aberta": False,
                "todas_abertas_respondidas": False,
                "total_abertas": 0,
                "id_mensagem_bloqueadora": None,
            },
        ):
            resultado = turno_cliente.avaliar_turno_cliente_para_fila(
                cursor=object(),
                cliente_telefone=CLIENTE,
                id_phone_unidade=PHONE_ID,
                received_data_hora=recebida_em,
            )

        self.assertTrue(resultado["pode_enfileirar"])
        self.assertEqual(resultado["motivo"], "sem_fila_aberta")

    def test_mensagem_antiga_reentregue_depois_do_bot_e_ignorada(self):
        recebida_em = datetime(2026, 6, 26, 18, 22, 11)
        resposta_bot_em = datetime(2026, 6, 26, 18, 36, 46)

        with patch.object(
            turno_cliente,
            "buscar_interacao_posterior_a_mensagem",
            return_value=resposta_bot_em,
        ), patch.object(
            turno_cliente,
            "avaliar_filas_abertas_turno",
        ) as avaliar_filas:
            resultado = turno_cliente.avaliar_turno_cliente_para_fila(
                cursor=object(),
                cliente_telefone=CLIENTE,
                id_phone_unidade=PHONE_ID,
                received_data_hora=recebida_em,
            )

        self.assertFalse(resultado["pode_enfileirar"])
        self.assertEqual(
            resultado["motivo"],
            "mensagem_reentregue_fora_de_ordem",
        )
        avaliar_filas.assert_not_called()

    def test_mensagem_nova_depois_do_bot_continua_fluxo_normal(self):
        resposta_bot_em = datetime(2026, 6, 26, 18, 36, 46)
        mensagem_nova_em = resposta_bot_em + timedelta(seconds=10)

        with patch.object(
            turno_cliente,
            "buscar_interacao_posterior_a_mensagem",
            return_value=None,
        ), patch.object(
            turno_cliente,
            "avaliar_filas_abertas_turno",
            return_value={
                "existe_fila_aberta": False,
                "todas_abertas_respondidas": False,
                "total_abertas": 0,
                "id_mensagem_bloqueadora": None,
            },
        ):
            resultado = turno_cliente.avaliar_turno_cliente_para_fila(
                cursor=object(),
                cliente_telefone=CLIENTE,
                id_phone_unidade=PHONE_ID,
                received_data_hora=mensagem_nova_em,
            )

        self.assertTrue(resultado["pode_enfileirar"])

    def test_consulta_cronologica_usa_timestamp_meta_e_comparacao_estrita(self):
        recebida_em = datetime(2026, 6, 26, 18, 22, 11)
        cursor = FakeCursor(fetchone_result=None)

        resultado = turno_cliente.buscar_interacao_posterior_a_mensagem(
            cursor,
            CLIENTE,
            PHONE_ID,
            recebida_em,
        )

        sql, params = cursor.calls[0]
        self.assertIsNone(resultado)
        self.assertIn("%s < c.last_interaction_at", sql)
        self.assertEqual(params, (CLIENTE, PHONE_ID, recebida_em))

    def test_insercao_repassa_timestamp_meta_para_regra_de_turno(self):
        dados = fila.extrair_dados_whatsapp(payload_texto_meta())
        cursor = FakeCursor(rowcount=1)

        with patch.object(
            fila,
            "avaliar_turno_cliente_para_fila",
            return_value={
                "pode_enfileirar": False,
                "motivo": "mensagem_reentregue_fora_de_ordem",
            },
        ) as avaliar_turno:
            resultado = fila.inserir_dados_na_tabela_fila(dados, cursor)

        self.assertEqual(resultado["status"], "ignored")
        self.assertEqual(
            resultado["reason"],
            "mensagem_reentregue_fora_de_ordem",
        )
        avaliar_turno.assert_called_once_with(
            cursor=cursor,
            cliente_telefone=dados["cliente_telefone"],
            id_phone_unidade=dados["id_phone_unidade"],
            received_data_hora=dados["received_data_hora"],
            usar_lock=True,
        )
        self.assertFalse(
            any(
                "INSERT INTO chatbot.fila_mensagens" in chamada[0]
                for chamada in cursor.calls
            )
        )


if __name__ == "__main__":
    unittest.main()
