import unittest
from datetime import datetime
from unittest.mock import patch

from workers.worker_flow import valida_banco


def estado_conversa(
    estado,
    id_conversa=10,
    id_etapa_atual=2,
    status_ativa=True,
    finalizou_em=None,
    status_dependente=False,
    last_message_from="bot",
    followup_stage=0,
    followup_last_sent_at=None,
    lead_no_funil=False,
):
    return (
        id_conversa,
        id_etapa_atual,
        status_ativa,
        finalizou_em,
        estado,
        status_dependente,
        last_message_from,
        followup_stage,
        followup_last_sent_at,
        lead_no_funil,
    )


class ValidaBancoTests(unittest.TestCase):
    def test_cliente_em_cache_nao_consulta_insert(self):
        with patch.object(
            valida_banco,
            "buscar_cliente_cache",
            return_value=5,
        ), patch.object(
            valida_banco,
            "inserindo_em_cliente_caso_seja_novo",
        ) as inserir:
            resultado = valida_banco.valida_cliente("5571999999999", object())

        self.assertEqual(resultado, (5, False, False))
        inserir.assert_not_called()

    def test_cliente_resolvido_no_banco_fica_pendente_para_cache_apos_commit(self):
        cursor = object()

        with patch.object(
            valida_banco,
            "buscar_cliente_cache",
            return_value=None,
        ), patch.object(
            valida_banco,
            "inserindo_em_cliente_caso_seja_novo",
            return_value=(6, True),
        ) as inserir:
            resultado = valida_banco.valida_cliente("5571999999999", cursor)

        self.assertEqual(resultado, (6, True, True))
        inserir.assert_called_once_with("5571999999999", cursor)

    def test_cliente_novo_cria_conversa_nova(self):
        cursor = object()

        with patch.object(
            valida_banco,
            "inserindo_em_conversa_caso_seja_nova",
            return_value=11,
        ) as inserir, patch.object(
            valida_banco,
            "buscar_estado_conversa",
        ) as buscar:
            contexto = valida_banco.valida_conversa(6, 2, True, cursor)

        inserir.assert_called_once_with(6, 2, cursor)
        buscar.assert_not_called()
        self.assertEqual(contexto["id_conversa"], 11)
        self.assertEqual(contexto["estado"], "nova")
        self.assertEqual(contexto["motivo"], "cliente_novo")
        self.assertIsNone(contexto["id_etapa_atual"])
        self.assertEqual(contexto["last_message_from"], "cliente")

    def test_cliente_existente_sem_conversa_na_unidade_cria_nova(self):
        cursor = object()

        with patch.object(
            valida_banco,
            "buscar_estado_conversa",
            return_value=None,
        ), patch.object(
            valida_banco,
            "inserindo_em_conversa_caso_seja_nova",
            return_value=12,
        ):
            contexto = valida_banco.valida_conversa(6, 2, False, cursor)

        self.assertEqual(contexto["id_conversa"], 12)
        self.assertEqual(contexto["estado"], "liberada")
        self.assertEqual(contexto["motivo"], "sem_historico_unidade")

    def test_conversa_ativa_preserva_estado_persistido(self):
        finalizou_em = datetime(2026, 6, 1, 10, 0)
        followup_em = datetime(2026, 6, 2, 10, 0)
        registro = estado_conversa(
            "ativa",
            finalizou_em=finalizou_em,
            status_dependente=True,
            last_message_from="cliente",
            followup_stage=2,
            followup_last_sent_at=followup_em,
            lead_no_funil=True,
        )

        with patch.object(
            valida_banco,
            "buscar_estado_conversa",
            return_value=registro,
        ), patch.object(
            valida_banco,
            "inserindo_em_conversa_caso_seja_nova",
        ) as inserir:
            contexto = valida_banco.valida_conversa(6, 2, False, object())

        inserir.assert_not_called()
        self.assertEqual(contexto["id_conversa"], 10)
        self.assertEqual(contexto["id_etapa_atual"], 2)
        self.assertEqual(contexto["last_message_from"], "cliente")
        self.assertTrue(contexto["status_dependente"])
        self.assertEqual(contexto["followup_stage"], 2)
        self.assertEqual(contexto["followup_last_sent_at"], followup_em)
        self.assertTrue(contexto["lead_no_funil"])
        self.assertEqual(contexto["finalizou_em"], finalizou_em)
        self.assertEqual(contexto["motivo"], "conversa_ativa")

    def test_conversa_bloqueada_nao_cria_nova_antes_de_30_dias(self):
        finalizou_em = datetime(2026, 6, 1, 10, 0)

        with patch.object(
            valida_banco,
            "buscar_estado_conversa",
            return_value=estado_conversa(
                "bloqueada",
                finalizou_em=finalizou_em,
            ),
        ), patch.object(
            valida_banco,
            "inserindo_em_conversa_caso_seja_nova",
        ) as inserir:
            contexto = valida_banco.valida_conversa(6, 2, False, object())

        inserir.assert_not_called()
        self.assertEqual(contexto["estado"], "bloqueada")
        self.assertEqual(contexto["motivo"], "finalizada_30_dias")
        self.assertEqual(contexto["finalizou_em"], finalizou_em)

    def test_bloqueio_expirado_cria_nova_conversa_e_referencia_anterior(self):
        cursor = object()

        with patch.object(
            valida_banco,
            "buscar_estado_conversa",
            return_value=estado_conversa("liberada", id_conversa=10),
        ), patch.object(
            valida_banco,
            "inserindo_em_conversa_caso_seja_nova",
            return_value=13,
        ) as inserir:
            contexto = valida_banco.valida_conversa(6, 2, False, cursor)

        inserir.assert_called_once_with(6, 2, cursor)
        self.assertEqual(contexto["id_conversa"], 13)
        self.assertEqual(contexto["conversa_anterior"], 10)
        self.assertEqual(contexto["motivo"], "bloqueio_expirado")
        self.assertEqual(contexto["last_message_from"], "cliente")

    def test_estado_desconhecido_falha_sem_criar_conversa(self):
        with patch.object(
            valida_banco,
            "buscar_estado_conversa",
            return_value=estado_conversa("invalido"),
        ), patch.object(
            valida_banco,
            "inserindo_em_conversa_caso_seja_nova",
        ) as inserir:
            with self.assertRaisesRegex(ValueError, "Estado de conversa invalido"):
                valida_banco.valida_conversa(6, 2, False, object())

        inserir.assert_not_called()

    def test_validacao_completa_propaga_contexto_e_cache_pendente(self):
        mensagem = {
            "cliente_telefone": "5571999999999",
            "id_phone_unidade": "123456",
        }
        cursor = object()
        conversa = {
            "id_conversa": 10,
            "estado": "ativa",
        }

        with patch.object(
            valida_banco,
            "obter_id_unidade_redis_ou_plsql",
            return_value=2,
        ) as unidade, patch.object(
            valida_banco,
            "valida_cliente",
            return_value=(6, False, True),
        ) as cliente, patch.object(
            valida_banco,
            "valida_conversa",
            return_value=conversa,
        ) as resolver_conversa:
            contexto = valida_banco.validar_banco_mensagem(mensagem, cursor)

        unidade.assert_called_once_with("123456", cursor)
        cliente.assert_called_once_with("5571999999999", cursor)
        resolver_conversa.assert_called_once_with(6, 2, False, cursor)
        self.assertEqual(contexto["id_unidade"], 2)
        self.assertEqual(contexto["id_cliente"], 6)
        self.assertTrue(contexto["cliente_cache_pendente"])
        self.assertIs(contexto["conversa"], conversa)


if __name__ == "__main__":
    unittest.main()
