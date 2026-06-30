import inspect
import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from core.integrations.whatsapp.tools import block_report


class ReconciliacaoUnidadesMetaTests(unittest.TestCase):
    def test_compara_banco_com_registros_cloud_api(self):
        unidades_banco = [
            {
                "id_unidade": 1,
                "nome_unidade": "Unidade sincronizada",
                "phone_id_unidade": "phone-1",
            },
            {
                "id_unidade": 2,
                "nome_unidade": "Somente banco",
                "phone_id_unidade": "phone-2",
            },
        ]
        numeros_meta = [
            {
                "phone_id_unidade": "phone-1",
                "display_phone_number": "+55 71 0000-0001",
                "verified_name": "Unidade sincronizada",
                "quality_rating": "GREEN",
                "code_verification_status": "VERIFIED",
                "platform_type": "CLOUD_API",
                "name_status": "APPROVED",
                "status": "CONNECTED",
                "registrado_cloud_api": True,
            },
            {
                "phone_id_unidade": "phone-3",
                "display_phone_number": "+55 71 0000-0003",
                "verified_name": "Somente Meta",
                "quality_rating": "GREEN",
                "code_verification_status": "VERIFIED",
                "platform_type": "CLOUD_API",
                "name_status": "APPROVED",
                "status": "CONNECTED",
                "registrado_cloud_api": True,
            },
            {
                "phone_id_unidade": "phone-2",
                "display_phone_number": "+55 71 0000-0002",
                "verified_name": "Nao Cloud API",
                "quality_rating": "GREEN",
                "code_verification_status": "VERIFIED",
                "platform_type": "NOT_APPLICABLE",
                "name_status": "APPROVED",
                "status": "DISCONNECTED",
                "registrado_cloud_api": False,
            },
        ]

        with patch.object(
            block_report,
            "_listar_unidades_banco",
            return_value=unidades_banco,
        ), patch.object(
            block_report,
            "_listar_numeros_waba_meta",
            return_value=numeros_meta,
        ), redirect_stdout(io.StringIO()):
            resultado = (
                block_report
                .job_reconciliacao_register__waba_unidades_meta()
            )

        self.assertEqual(resultado["sincronizados"], ["phone-1"])
        self.assertEqual(resultado["somente_banco"], ["phone-2"])
        self.assertEqual(resultado["somente_meta"], ["phone-3"])

    def test_job_nao_possui_operacao_de_escrita_meta(self):
        source = inspect.getsource(
            block_report
            .job_reconciliacao_register__waba_unidades_meta
        )

        self.assertNotIn("registrar_numero_whatsapp", source)
        self.assertNotIn("desregistrar_numero_whatsapp", source)
        self.assertNotIn("cursor.execute", source)


if __name__ == "__main__":
    unittest.main()
