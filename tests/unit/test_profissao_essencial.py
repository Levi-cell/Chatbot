import unittest

from django.contrib.admin.sites import AdminSite

from core.repositories.atendimento.conversas import (
    atualizar_profissao_conversa,
)
from tests.helpers import FakeCursor
from webhook.admin import ConversaAdmin
from webhook.models import Conversa


class ProfissaoEssencialTests(unittest.TestCase):
    def test_modelo_e_admin_expoem_profissao_opcional_de_100_caracteres(self):
        campo = Conversa._meta.get_field("profissao")
        admin = ConversaAdmin(Conversa, AdminSite())

        self.assertEqual(campo.max_length, 100)
        self.assertTrue(campo.null)
        self.assertTrue(campo.blank)
        self.assertIn("profissao", admin.list_display)
        self.assertIn("profissao", admin.search_fields)

    def test_repositorio_normaliza_e_atualiza_profissao_por_conversa(self):
        cursor = FakeCursor(rowcount=1)

        linhas = atualizar_profissao_conversa(
            123,
            "  Analista de custos  ",
            cursor,
        )

        sql, parametros = cursor.calls[0]
        self.assertIn("UPDATE chatbot.conversa", sql)
        self.assertIn("SET profissao = %s", sql)
        self.assertIn("WHERE id_conversa = %s", sql)
        self.assertEqual(parametros, ("Analista de custos", 123))
        self.assertEqual(linhas, 1)

    def test_repositorio_rejeita_profissao_fora_do_contrato(self):
        invalidas = (
            None,
            "",
            "   ",
            "Engenheiro\nProfessor",
            "x" * 101,
        )

        for profissao in invalidas:
            with self.subTest(profissao=profissao):
                cursor = FakeCursor()

                with self.assertRaisesRegex(ValueError, "profissao"):
                    atualizar_profissao_conversa(123, profissao, cursor)

                self.assertEqual(cursor.calls, [])

    def test_repositorio_falha_se_conversa_nao_for_atualizada(self):
        cursor = FakeCursor(rowcount=0)

        with self.assertRaisesRegex(
            ValueError,
            "Conversa nao foi atualizada com profissao",
        ):
            atualizar_profissao_conversa(
                999,
                "Autonomo",
                cursor,
            )


if __name__ == "__main__":
    unittest.main()
