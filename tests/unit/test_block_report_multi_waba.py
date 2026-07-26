import unittest
from unittest.mock import call, patch

from core.integrations.whatsapp.tools import block_report


class BlockReportMultiWabaTests(unittest.TestCase):
    def test_relatorio_bloqueios_compara_phone_e_cliente(self):
        bloqueios_meta = [
            {
                "id_unidade": 1,
                "nome_unidade": "Unidade A",
                "phone_id_unidade": "phone-a",
                "wa_ids_bloqueados": ["cliente-1", "cliente-2"],
            }
        ]
        bloqueios_banco = [
            {
                "id_bloqueio": 10,
                "wa_id_cliente": "cliente-1",
                "id_unidade": 1,
                "phone_id_unidade": "phone-a",
                "nome_unidade": "Unidade A",
            },
            {
                "id_bloqueio": 11,
                "wa_id_cliente": "cliente-3",
                "id_unidade": 1,
                "phone_id_unidade": "phone-a",
                "nome_unidade": "Unidade A",
            },
        ]

        with (
            patch.object(
                block_report,
                "listar_bloqueados_de_cada_unidade",
                return_value=bloqueios_meta,
            ),
            patch.object(
                block_report,
                "_listar_bloqueios_banco",
                return_value=bloqueios_banco,
            ),
            patch("builtins.print"),
        ):
            resultado = (
                block_report
                .job_reconciliacao_bloqueios_cliente_unidades_meta()
            )

        self.assertEqual(
            resultado["sincronizados"],
            [("phone-a", "cliente-1")],
        )
        self.assertEqual(
            resultado["somente_meta"],
            [("phone-a", "cliente-2")],
        )
        self.assertEqual(
            resultado["somente_banco"],
            [("phone-a", "cliente-3")],
        )

    def test_relatorio_registros_consulta_cada_waba_do_banco(self):
        unidades = [
            {
                "id_unidade": 1,
                "nome_unidade": "Unidade A",
                "waba_id": "waba-a",
                "phone_id_unidade": "phone-a",
            },
            {
                "id_unidade": 2,
                "nome_unidade": "Unidade B",
                "waba_id": "waba-b",
                "phone_id_unidade": "phone-b",
            },
        ]

        def numeros_por_waba(waba_id):
            sufixo = waba_id[-1]
            return [
                {
                    "waba_id": waba_id,
                    "phone_id_unidade": f"phone-{sufixo}",
                    "display_phone_number": f"55000000000{sufixo}",
                    "verified_name": f"Unidade {sufixo.upper()}",
                    "status": "CONNECTED",
                    "registrado_cloud_api": True,
                }
            ]

        with (
            patch.object(
                block_report,
                "_listar_unidades_banco",
                return_value=unidades,
            ),
            patch.object(
                block_report,
                "_listar_numeros_waba_meta",
                side_effect=numeros_por_waba,
            ) as listar_meta,
            patch("builtins.print"),
        ):
            resultado = (
                block_report
                .job_reconciliacao_register__waba_unidades_meta()
            )

        self.assertEqual(
            listar_meta.call_args_list,
            [call("waba-a"), call("waba-b")],
        )
        self.assertEqual(
            resultado["sincronizados"],
            ["phone-a", "phone-b"],
        )
        self.assertEqual(resultado["somente_meta"], [])
        self.assertEqual(resultado["somente_banco"], [])


if __name__ == "__main__":
    unittest.main()
