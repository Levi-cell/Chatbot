import random
import string
import unittest

from workers.worker_flow.response_flow.etapas.validadores_universais import validador_nome
from workers.worker_flow.response_flow.etapas.validadores_universais.nome.lexicos import (
    PRIMEIROS_NOMES_COMPOSTOS,
    SOBRENOMES_COMPLEMENTARES,
)


class ValidadorNomeRobustezTests(unittest.TestCase):
    def test_todos_compostos_curados_sao_aceitos(self):
        for primeiro, segundo in PRIMEIROS_NOMES_COMPOSTOS:
            texto = f"{primeiro.title()} {segundo.title()}"

            with self.subTest(texto=texto):
                resultado = validador_nome.validar_nome_cliente(texto)

                self.assertTrue(resultado.valido)
                self.assertEqual(
                    len(resultado.primeiro_nome.split()),
                    2,
                )

    def test_sobrenomes_complementares_sao_removidos(self):
        for sobrenome in SOBRENOMES_COMPLEMENTARES:
            texto = f"Meu nome é Carlos {sobrenome.title()}"

            with self.subTest(texto=texto):
                resultado = validador_nome.validar_nome_cliente(texto)

                self.assertTrue(resultado.valido)
                self.assertEqual(resultado.primeiro_nome, "Carlos")

    def test_fuzz_deterministico_preserva_invariantes(self):
        gerador = random.Random(20260629)
        alfabeto = (
            string.ascii_letters
            + string.digits
            + " áéíóúãõâêôçÁÉÍÓÚÃÕÂÊÔÇ-'.,!?@#$%&/\\"
            + "😀🔥"
            + "\u200b\u202e\ufffd"
        )

        for _ in range(10_000):
            tamanho = gerador.randint(0, 40)
            texto = "".join(
                gerador.choice(alfabeto)
                for _ in range(tamanho)
            )
            primeiro = validador_nome.validar_nome_cliente(texto)
            segundo = validador_nome.validar_nome_cliente(texto)

            self.assertEqual(primeiro, segundo)
            self.assertGreaterEqual(primeiro.confianca, 0.0)
            self.assertLessEqual(primeiro.confianca, 1.0)

            if primeiro.valido:
                self.assertTrue(primeiro.primeiro_nome)
                self.assertIsNone(primeiro.motivo)
                self.assertEqual(
                    primeiro.status,
                    validador_nome.STATUS_VALIDO,
                )
                self.assertLessEqual(
                    len(primeiro.primeiro_nome.split()),
                    2,
                )
            else:
                self.assertIsNone(primeiro.primeiro_nome)
                self.assertIsNotNone(primeiro.motivo)
                self.assertIn(
                    primeiro.status,
                    {
                        validador_nome.STATUS_INVALIDO,
                        validador_nome.STATUS_AMBIGUO,
                    },
                )


if __name__ == "__main__":
    unittest.main()
