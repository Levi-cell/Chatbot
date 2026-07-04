import unittest

from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa8 import (
    MOTIVO_DOMINIO_INVALIDO,
    MOTIVO_EMAIL_AUSENTE,
    MOTIVO_MULTIPLOS_EMAILS,
    validar_etapa8,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_EMAIL_VALIDO,
)


class ValidaEtapa8Tests(unittest.TestCase):
    def test_extrai_email_de_resposta_direta_ou_frase(self):
        casos = (
            (
                "edcaspfilho@gmail.com",
                "edcaspfilho@gmail.com",
            ),
            (
                "Meu email é edcaspfilho@gmail.com.",
                "edcaspfilho@gmail.com",
            ),
            (
                "Pode usar nome.sobrenome+agenda@sub.exemplo.com.br!",
                "nome.sobrenome+agenda@sub.exemplo.com.br",
            ),
            (
                "Contato: USUARIO@HOTMAIL.COM",
                "USUARIO@hotmail.com",
            ),
            (
                "Envie para usuario@empresa.technology, por favor.",
                "usuario@empresa.technology",
            ),
        )

        for texto, email_esperado in casos:
            with self.subTest(texto=texto):
                resultado = validar_etapa8(texto)

                self.assertTrue(resultado.valido)
                self.assertEqual(resultado.email, email_esperado)
                self.assertEqual(
                    resultado.evento,
                    EVENTO_EMAIL_VALIDO,
                )
                self.assertIsNone(resultado.motivo)

    def test_aceita_qualquer_terminacao_com_estrutura_minima(self):
        emails = (
            "cliente@gmail.com",
            "cliente@hotmail.com.br",
            "cliente@instituto.org",
            "cliente@empresa.x",
            "cliente@empresa.123",
            "cliente@empresa.terminacao-futura",
            ".cliente..@-empresa.$final",
        )

        for email in emails:
            with self.subTest(email=email):
                self.assertTrue(validar_etapa8(email).valido)

    def test_rejeita_entrada_sem_email(self):
        for texto in ("", "meu email ficou faltando", "nomegmail.com"):
            with self.subTest(texto=texto):
                resultado = validar_etapa8(texto)

                self.assertFalse(resultado.valido)
                self.assertEqual(
                    resultado.motivo,
                    MOTIVO_EMAIL_AUSENTE,
                )

    def test_rejeita_multiplos_emails_ou_arrobas(self):
        entradas = (
            "um@gmail.com e dois@hotmail.com",
            "nome@@gmail.com",
        )

        for texto in entradas:
            with self.subTest(texto=texto):
                resultado = validar_etapa8(texto)

                self.assertFalse(resultado.valido)
                self.assertEqual(
                    resultado.motivo,
                    MOTIVO_MULTIPLOS_EMAILS,
                )

    def test_rejeita_email_quebrado_por_espaco(self):
        entradas = (
            "nome @gmail.com",
            "nome@ gmail.com",
        )

        for texto in entradas:
            with self.subTest(texto=texto):
                self.assertFalse(validar_etapa8(texto).valido)

    def test_rejeita_dominio_invalido(self):
        entradas = (
            "nome@gmail",
            "nome@.com",
            "nome@gmail.",
        )

        for texto in entradas:
            with self.subTest(texto=texto):
                resultado = validar_etapa8(texto)

                self.assertFalse(resultado.valido)
                self.assertEqual(
                    resultado.motivo,
                    MOTIVO_DOMINIO_INVALIDO,
                )


if __name__ == "__main__":
    unittest.main()
