import inspect
import unittest
from unittest.mock import ANY, call, patch

from callback.webhook.services.populating_fila_mensagens import (
    extrair_dados_whatsapp,
)
from core.database.deploy_database import bank_script
from tests.helpers import FakeConn, FakeCursor
from tests.payloads import payload_texto_meta
from workers.worker_flow import valida_banco
from workers.worker_funil import processamento as processamento_funil


class MultiWabaIsolamentoTests(unittest.TestCase):
    def test_webhook_preserva_phone_id_para_mesmo_cliente_em_duas_unidades(self):
        cliente = "5571999999999"
        dados_a = extrair_dados_whatsapp(
            payload_texto_meta(
                wa_id=cliente,
                phone_number_id="phone-a",
                message_id="wamid.a",
            )
        )
        dados_b = extrair_dados_whatsapp(
            payload_texto_meta(
                wa_id=cliente,
                phone_number_id="phone-b",
                message_id="wamid.b",
            )
        )

        self.assertEqual(dados_a["cliente_telefone"], cliente)
        self.assertEqual(dados_b["cliente_telefone"], cliente)
        self.assertEqual(dados_a["id_phone_unidade"], "phone-a")
        self.assertEqual(dados_b["id_phone_unidade"], "phone-b")

    def test_worker_resolve_matriz_cliente_unidade_em_conversas_distintas(self):
        unidade_por_phone = {
            "phone-a": 1,
            "phone-b": 2,
        }
        cliente_por_telefone = {
            "cliente-a": 10,
            "cliente-b": 20,
        }
        conversa_por_par = {
            (10, 1): 101,
            (10, 2): 102,
            (20, 1): 103,
        }

        with (
            patch.object(
                valida_banco,
                "obter_id_unidade_redis_ou_plsql",
                side_effect=lambda phone, _cursor: unidade_por_phone[phone],
            ),
            patch.object(
                valida_banco,
                "buscar_cliente_cache",
                side_effect=lambda telefone: cliente_por_telefone[telefone],
            ),
            patch.object(
                valida_banco,
                "buscar_estado_conversa",
                return_value=None,
            ) as buscar_estado,
            patch.object(
                valida_banco,
                "inserindo_em_conversa_caso_seja_nova",
                side_effect=lambda cliente, unidade, _cursor: (
                    conversa_por_par[(cliente, unidade)]
                ),
            ),
        ):
            contextos = [
                valida_banco.validar_banco_mensagem(
                    {
                        "cliente_telefone": cliente,
                        "id_phone_unidade": phone,
                    },
                    object(),
                )
                for cliente, phone in (
                    ("cliente-a", "phone-a"),
                    ("cliente-a", "phone-b"),
                    ("cliente-b", "phone-a"),
                )
            ]

        self.assertEqual(
            [
                (
                    contexto["id_cliente"],
                    contexto["id_unidade"],
                    contexto["conversa"]["id_conversa"],
                )
                for contexto in contextos
            ],
            [
                (10, 1, 101),
                (10, 2, 102),
                (20, 1, 103),
            ],
        )
        self.assertEqual(
            buscar_estado.call_args_list,
            [
                call(10, 1, ANY),
                call(10, 2, ANY),
                call(20, 1, ANY),
            ],
        )

    def test_funil_seleciona_integracao_da_unidade_de_cada_conversa(self):
        unidades_por_conversa = {
            101: 1,
            102: 2,
            103: 1,
        }
        integracoes = {
            1: {
                "link_api_carrossel": "https://funil-a.example/api?W=A",
                "codigo_canal_venda": "canal-a",
                "integracao_ativa": True,
                "widget_ativo": True,
            },
            2: {
                "link_api_carrossel": "https://funil-b.example/api?W=B",
                "codigo_canal_venda": "canal-b",
                "integracao_ativa": True,
                "widget_ativo": True,
            },
        }

        def buscar_lead(id_conversa, _cursor):
            return {
                "id_conversa": id_conversa,
                "id_unidade": unidades_por_conversa[id_conversa],
            }

        def buscar_integracao(id_unidade, _cursor):
            return integracoes[id_unidade]

        conn = FakeConn(FakeCursor())

        with (
            patch.object(
                processamento_funil,
                "buscar_dados_lead_funil",
                side_effect=buscar_lead,
            ),
            patch.object(
                processamento_funil,
                "buscar_integracao_funil_por_unidade",
                side_effect=buscar_integracao,
            ) as buscar_integracao_mock,
            patch.object(
                processamento_funil,
                "montar_payload_oportunidade",
                side_effect=lambda dados: {
                    "id_conversa": dados["id_conversa"],
                },
            ),
            patch.object(
                processamento_funil,
                "enviar_oportunidade",
                return_value={
                    "status_http": 200,
                    "resposta": {"success": True},
                },
            ) as enviar,
            patch.object(
                processamento_funil,
                "marcar_envio_como_concluido",
                return_value=True,
            ),
        ):
            for id_funil_envio, id_conversa in enumerate(
                (101, 102, 103),
                start=1,
            ):
                self.assertTrue(
                    processamento_funil.processar_envio_funil(
                        {
                            "id_funil_envio": id_funil_envio,
                            "id_conversa": id_conversa,
                            "attempt_count": 1,
                        },
                        conn,
                        conn.cursor_obj,
                    )
                )

        self.assertEqual(
            [chamada.args[0] for chamada in buscar_integracao_mock.call_args_list],
            [1, 2, 1],
        )
        self.assertEqual(
            [
                (
                    chamada.kwargs["link_api_carrossel"],
                    chamada.kwargs["codigo_canal_venda"],
                )
                for chamada in enviar.call_args_list
            ],
            [
                ("https://funil-a.example/api?W=A", "canal-a"),
                ("https://funil-b.example/api?W=B", "canal-b"),
                ("https://funil-a.example/api?W=A", "canal-a"),
            ],
        )

    def test_schema_separa_conversa_ativa_por_cliente_e_unidade(self):
        source = inspect.getsource(bank_script.criar_tabelas)

        self.assertIn(
            "ON chatbot.conversa (id_cliente, id_unidade)",
            source,
        )
        self.assertIn(
            "id_unidade INT NOT NULL UNIQUE",
            source,
        )
        self.assertIn(
            "phone_number_id VARCHAR(100) UNIQUE NOT NULL",
            source,
        )
        self.assertIn(
            "waba_id VARCHAR(100) UNIQUE NOT NULL",
            source,
        )


if __name__ == "__main__":
    unittest.main()
