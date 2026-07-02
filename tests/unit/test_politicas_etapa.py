import unittest
import inspect
from datetime import datetime

from core.repositories import querys
from core.repositories.politicas_etapa import (
    BloqueioConversa,
    buscar_bloqueio_ativo_por_cliente_unidade,
    buscar_bloqueio_conversa_por_id,
    buscar_politica_etapa,
)


class CursorFake:
    def __init__(self, resultado=None):
        self.resultado = resultado
        self.sql = None
        self.params = None

    def execute(self, sql, params):
        self.sql = sql
        self.params = params

    def fetchone(self):
        return self.resultado


class PoliticasEtapaTests(unittest.TestCase):
    def test_carrega_politica_da_etapa_final(self):
        cursor = CursorFake((7, True, 30, True))

        politica = buscar_politica_etapa(7, cursor)

        self.assertTrue(politica.encerra_automaticamente)
        self.assertEqual(politica.bloqueio_dias, 30)
        self.assertTrue(politica.elegivel_funil)
        self.assertEqual(cursor.params, (7,))

    def test_etapa_sem_cadastro_falha_sem_assumir_politica(self):
        cursor = CursorFake()

        with self.assertRaisesRegex(ValueError, "não encontrada"):
            buscar_politica_etapa(99, cursor)

    def test_busca_bloqueio_por_conversa_com_prazo_do_banco(self):
        finalizou_em = datetime(2026, 7, 1, 10, 0)
        cursor = CursorFake((finalizou_em, 30))

        bloqueio = buscar_bloqueio_conversa_por_id(10, cursor)

        self.assertEqual(
            bloqueio,
            BloqueioConversa(finalizou_em, 30),
        )
        self.assertIn("e.bloqueio_dias > 0", cursor.sql)
        self.assertEqual(cursor.params, (10,))

    def test_fallback_busca_apenas_bloqueio_ainda_ativo(self):
        finalizou_em = datetime(2026, 7, 1, 10, 0)
        cursor = CursorFake((finalizou_em, 30))

        bloqueio = buscar_bloqueio_ativo_por_cliente_unidade(
            "5575999999999",
            "123456",
            cursor,
        )

        self.assertEqual(bloqueio.bloqueio_dias, 30)
        self.assertIn(
            "e.bloqueio_dias * INTERVAL '1 day'",
            cursor.sql,
        )
        self.assertEqual(
            cursor.params,
            ("5575999999999", "123456"),
        )

    def test_estado_conversa_nao_depende_do_numero_sete(self):
        source = inspect.getsource(querys.buscar_estado_conversa)

        self.assertNotIn("id_etapa_atual = 7", source)
        self.assertIn("LEFT JOIN chatbot.etapa", source)
        self.assertIn("COALESCE(e.bloqueio_dias, 0)", source)


if __name__ == "__main__":
    unittest.main()
