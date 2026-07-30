import unittest
from unittest.mock import call, patch

from operations.monitoring import blocked_users


def unidade(
    *,
    id_unidade=1,
    nome="Unidade A",
    waba="waba-a",
    phone="phone-a",
):
    return {
        "id_unidade": id_unidade,
        "nome_unidade": nome,
        "waba_id": waba,
        "phone_id_unidade": phone,
    }


def bloqueio(
    wa_id,
    *,
    id_bloqueio=10,
    id_unidade=1,
    nome_unidade="Unidade A",
    waba="waba-a",
    phone="phone-a",
    phone_registrado=None,
    nome_cliente=None,
):
    return {
        "id_bloqueio": id_bloqueio,
        "id_cliente": None,
        "nome_cliente": nome_cliente,
        "wa_id_cliente": wa_id,
        "id_unidade": id_unidade,
        "nome_unidade": nome_unidade,
        "waba_id": waba,
        "phone_id_unidade": phone,
        "phone_id_registrado": phone_registrado or phone,
    }


class BlockReportMultiWabaTests(unittest.TestCase):
    def test_execucao_sem_argumentos_escolhe_relatorio_principal(self):
        resultado = {
            "sincronizados": [],
            "somente_meta": [],
            "somente_banco": [],
            "nao_comparados_banco": [],
            "vinculos_unidade_divergentes": [],
            "falhas_meta": [],
        }
        with (
            patch.object(
                blocked_users,
                "reconciliar_bloqueios_meta_banco",
                return_value=resultado,
            ) as reconciliar,
            patch.object(
                blocked_users,
                "reconciliar_registros_waba_meta",
            ) as reconciliar_registros,
        ):
            codigo = blocked_users.main([])

        self.assertEqual(codigo, 0)
        reconciliar.assert_called_once_with(mostrar_wa_id=True)
        reconciliar_registros.assert_not_called()

    def test_compara_bloqueios_por_waba_phone_e_cliente(self):
        bloqueios_meta = [{
            **unidade(),
            "status_meta": "ok",
            "erro_meta": None,
            "wa_ids_bloqueados": ["cliente-1", "cliente-2"],
        }]
        bloqueios_banco = [
            bloqueio("cliente-1", nome_cliente="Maria"),
            bloqueio("cliente-3", id_bloqueio=11),
        ]

        resultado = blocked_users.comparar_bloqueios(
            bloqueios_meta,
            bloqueios_banco,
        )

        self.assertEqual(
            [item["wa_id_cliente"] for item in resultado["sincronizados"]],
            ["cliente-1"],
        )
        self.assertEqual(
            [item["wa_id_cliente"] for item in resultado["somente_meta"]],
            ["cliente-2"],
        )
        self.assertEqual(
            [item["wa_id_cliente"] for item in resultado["somente_banco"]],
            ["cliente-3"],
        )
        self.assertEqual(
            resultado["sincronizados"][0]["nome_cliente"],
            "Maria",
        )

    def test_falha_meta_nao_vira_falso_somente_banco(self):
        bloqueios_meta = [{
            **unidade(),
            "status_meta": "erro",
            "erro_meta": "TimeoutError: indisponível",
            "wa_ids_bloqueados": [],
        }]

        resultado = blocked_users.comparar_bloqueios(
            bloqueios_meta,
            [bloqueio("cliente-1")],
        )

        self.assertEqual(resultado["somente_banco"], [])
        self.assertEqual(
            [item["wa_id_cliente"]
             for item in resultado["nao_comparados_banco"]],
            ["cliente-1"],
        )
        self.assertEqual(len(resultado["falhas_meta"]), 1)

    def test_vinculo_phone_gravado_divergente_e_sinalizado(self):
        resultado = blocked_users.comparar_bloqueios(
            [{
                **unidade(),
                "status_meta": "ok",
                "erro_meta": None,
                "wa_ids_bloqueados": [],
            }],
            [
                bloqueio(
                    "cliente-1",
                    phone="phone-atual",
                    phone_registrado="phone-antigo",
                )
            ],
        )

        self.assertEqual(resultado["somente_banco"], [])
        self.assertEqual(
            resultado["vinculos_unidade_divergentes"][0][
                "wa_id_cliente"
            ],
            "cliente-1",
        )

    def test_coleta_registros_consulta_cada_waba_do_banco(self):
        unidades = [
            unidade(),
            unidade(
                id_unidade=2,
                nome="Unidade B",
                waba="waba-b",
                phone="phone-b",
            ),
        ]
        chamadas = []

        def listar(waba_id):
            chamadas.append(call(waba_id))
            return [{
                "waba_id": waba_id,
                "phone_id_unidade": f"phone-{waba_id[-1]}",
                "registrado_cloud_api": True,
                "status": "CONNECTED",
            }]

        numeros, falhas = blocked_users.coletar_registros_meta(
            unidades,
            list_factory=listar,
        )
        resultado = blocked_users.comparar_registros_waba(
            unidades,
            numeros,
            falhas,
        )

        self.assertEqual(chamadas, [call("waba-a"), call("waba-b")])
        self.assertEqual(len(resultado["sincronizados"]), 2)
        self.assertEqual(resultado["somente_meta"], [])
        self.assertEqual(resultado["somente_banco"], [])

    def test_mesmo_phone_em_wabas_diferentes_nao_e_sincronizado(self):
        unidades = [unidade()]
        numeros = [{
            "waba_id": "waba-b",
            "phone_id_unidade": "phone-a",
            "registrado_cloud_api": True,
            "status": "CONNECTED",
        }]

        resultado = blocked_users.comparar_registros_waba(
            unidades,
            numeros,
            [],
        )

        self.assertEqual(resultado["sincronizados"], [])
        self.assertEqual(len(resultado["waba_divergente"]), 1)
        self.assertEqual(
            resultado["waba_divergente"][0]["waba_id_banco"],
            "waba-a",
        )
        self.assertEqual(
            resultado["waba_divergente"][0]["waba_id_meta"],
            "waba-b",
        )


if __name__ == "__main__":
    unittest.main()
