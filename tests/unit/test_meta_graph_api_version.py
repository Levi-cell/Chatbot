import re
import unittest
from pathlib import Path
from unittest.mock import patch

from core.integrations.whatsapp.pywa_functions import cliente
from core.integrations.whatsapp.tools import (
    ativando_numero,
    config,
    desativando_numero,
)
from operations.monitoring import blocked_users


class _RespostaMetaFake:
    def __init__(self, corpo=None):
        self.status_code = 200
        self.ok = True
        self.text = ""
        self._corpo = corpo if corpo is not None else {"success": True}

    def json(self):
        return self._corpo

    def raise_for_status(self):
        return None


class MetaGraphApiVersionTests(unittest.TestCase):
    def test_configuracao_expoe_versao_sem_v_e_monta_url_versionada(self):
        self.assertEqual(config.get_meta_graph_api_version(), "26.0")
        self.assertEqual(
            config.construir_url_graph_api("/phone-id/messages/"),
            "https://graph.facebook.com/v26.0/phone-id/messages",
        )

        with patch.object(config, "META_GRAPH_API_VERSION", "27.0"):
            self.assertEqual(
                config.construir_url_graph_api("phone-id/messages"),
                "https://graph.facebook.com/v27.0/phone-id/messages",
            )

    def test_configuracao_recusa_prefixo_v_e_formato_invalido(self):
        for valor in ("v26.0", "26", "26.00", "26.x", ""):
            with self.subTest(valor=valor):
                with self.assertRaises(RuntimeError):
                    config._normalizar_meta_graph_api_version(valor)

    def test_cliente_pywa_recebe_a_mesma_versao_global(self):
        with patch.object(cliente, "WhatsApp") as whatsapp:
            cliente.conta_wa(" phone-id ", token="token-teste")

        whatsapp.assert_called_once_with(
            token="token-teste",
            phone_id="phone-id",
            api_version="26.0",
        )

    def test_registro_e_desregistro_usam_versao_global(self):
        resposta = _RespostaMetaFake()

        with patch.object(
            ativando_numero.requests,
            "post",
            return_value=resposta,
        ) as post:
            ativando_numero.registrar_numero_whatsapp(
                "phone-id",
                pin="123456",
            )

        self.assertEqual(
            post.call_args.args[0],
            "https://graph.facebook.com/v26.0/phone-id/register",
        )

        with patch.object(
            desativando_numero.requests,
            "post",
            return_value=resposta,
        ) as post:
            desativando_numero.desregistrar_numero_whatsapp("phone-id")

        self.assertEqual(
            post.call_args.args[0],
            "https://graph.facebook.com/v26.0/phone-id/deregister",
        )

    def test_relatorio_operacional_usa_versao_global(self):
        resposta = _RespostaMetaFake(corpo={"data": []})

        with (
            patch.object(
                blocked_users,
                "configure_local_operations",
            ),
            patch.object(
                blocked_users.requests,
                "get",
                return_value=resposta,
            ) as get,
        ):
            resultado = blocked_users.listar_numeros_waba_meta("waba-id")

        self.assertEqual(resultado, [])
        self.assertEqual(
            get.call_args.args[0],
            "https://graph.facebook.com/v26.0/waba-id/phone_numbers",
        )

    def test_integracao_nao_contem_versao_graph_api_hardcoded(self):
        raiz = Path(__file__).resolve().parents[2]
        pastas = (
            raiz / "core" / "integrations" / "whatsapp",
            raiz / "operations",
        )
        padrao = re.compile(
            r"https://graph\.facebook\.com/v\d+\.\d+",
        )
        ocorrencias = []

        for pasta in pastas:
            for arquivo in pasta.rglob("*.py"):
                if padrao.search(arquivo.read_text(encoding="utf-8")):
                    ocorrencias.append(str(arquivo.relative_to(raiz)))

        self.assertEqual(ocorrencias, [])


if __name__ == "__main__":
    unittest.main()
