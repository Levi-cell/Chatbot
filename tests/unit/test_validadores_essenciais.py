import unittest

from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa4 import (
    STATUS_IDADE_ACIMA_LIMITE,
    STATUS_IDADE_INVALIDA,
    obter_idade_minima_dependente,
    validar_idade,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa5 import (
    validar_etapa5,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa7 import (
    validar_etapa7,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa8 import (
    validar_etapa8,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa17 import (
    validar_etapa17,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa18 import (
    normalizar_comentario_etapa18,
)
from workers.worker_flow.response_flow.etapas.validadores_universais import (
    validador_nome,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_financeiro import (
    validar_pergunta_financeira,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_midia import (
    validar_midia,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_triagem import (
    RESPOSTA_TRIAGEM_AS_VEZES,
    RESPOSTA_TRIAGEM_FREQUENTEMENTE,
    RESPOSTA_TRIAGEM_NUNCA,
    validar_resposta_triagem,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_OFERTA_ACEITA,
    EVENTO_OFERTA_ADIADA,
    EVENTO_RETORNO_ADIADO,
    EVENTO_RETORNO_CONFIRMADO,
)


class ValidadoresEssenciaisTests(unittest.TestCase):
    def test_midia_e_financeiro_preservam_as_barreiras_universais(self):
        self.assertFalse(validar_midia("text"))
        self.assertFalse(validar_midia("interactive"))
        self.assertTrue(validar_midia("image"))
        self.assertTrue(validar_midia("audio"))

        for texto in (
            "Qual o valor?",
            "Quanto custa?",
            "Aceita pix?",
            "Tem mensalidade?",
        ):
            with self.subTest(texto=texto):
                self.assertTrue(validar_pergunta_financeira(texto))

        self.assertFalse(validar_pergunta_financeira("Meu nome e Pedro"))

    def test_nome_aceita_formatos_reais_e_extrai_no_maximo_dois_nomes(self):
        casos = (
            ("Joao", "João"),
            ("Maria Julia.", "Maria Julia"),
            ("Meu nome é Carlos Silva", "Carlos"),
            ("O nome da minha filha é Aline Braga", "Aline"),
            ("Ela se chama Alice", "Alice"),
            ("Ana-Clara", "Ana-Clara"),
        )

        for texto, esperado in casos:
            with self.subTest(texto=texto):
                resultado = validador_nome.validar_nome_cliente(texto)
                self.assertTrue(resultado.valido)
                self.assertEqual(resultado.primeiro_nome, esperado)
                self.assertLessEqual(len(esperado.split()), 2)

    def test_nome_bloqueia_entradas_objetivamente_invalidas(self):
        entradas = (
            "",
            "Pedro99",
            "Pedro😀",
            "Maria Puta",
            "Banana Feliz",
            "pppjoao",
            "xzxzxz",
        )

        for texto in entradas:
            with self.subTest(texto=texto):
                resultado = validador_nome.validar_nome_cliente(texto)
                self.assertFalse(resultado.valido)
                self.assertIsNone(resultado.primeiro_nome)
                self.assertIsNotNone(resultado.motivo)

    def test_idade_extrai_um_unico_valor_e_classifica_limites(self):
        casos_validos = (
            ("18", 18),
            ("Eu tenho trinta e nove anos", 39),
            ("Alice tem cinco anos", 5),
        )

        for texto, idade in casos_validos:
            with self.subTest(texto=texto):
                resultado = validar_idade(texto)
                self.assertTrue(resultado.valida)
                self.assertEqual(resultado.idade, idade)

        for texto in ("", "0", "-1", "Tenho 39 e meu filho 7", "18.5"):
            with self.subTest(texto=texto):
                self.assertEqual(validar_idade(texto).status, STATUS_IDADE_INVALIDA)

        self.assertEqual(
            validar_idade("cem anos").status,
            STATUS_IDADE_ACIMA_LIMITE,
        )
        self.assertEqual(obter_idade_minima_dependente(False), 5)
        self.assertEqual(obter_idade_minima_dependente(True), 4)

    def test_decisoes_das_etapas_cinco_e_sete_traduzem_eventos(self):
        validadores = (
            (
                validar_etapa5,
                EVENTO_OFERTA_ACEITA,
                EVENTO_OFERTA_ADIADA,
            ),
            (
                validar_etapa7,
                EVENTO_RETORNO_CONFIRMADO,
                EVENTO_RETORNO_ADIADO,
            ),
        )

        for validador, positivo, adiado in validadores:
            with self.subTest(validador=validador.__name__):
                self.assertEqual(validador("Quero agendar"), positivo)
                self.assertEqual(validador("bora"), positivo)
                self.assertEqual(validador("Talvez mais tarde"), adiado)
                self.assertIsNone(validador("não quero"))
                self.assertIsNone(validador("qualquer coisa"))

    def test_email_exige_um_arroba_e_um_ponto_no_dominio(self):
        resultado = validar_etapa8("Meu email é Ed@Gmail.com.")
        self.assertTrue(resultado.valido)
        self.assertEqual(resultado.email, "Ed@gmail.com")

        for texto in (
            "edcaspgmail.com",
            "edcasp@gmailcom",
            "edcarlosgmail",
            "um@gmail.com e dois@hotmail.com",
            "nome@@gmail.com",
        ):
            with self.subTest(texto=texto):
                self.assertFalse(validar_etapa8(texto).valido)

    def test_triagem_aceita_somente_o_conteudo_exato_das_opcoes(self):
        casos = (
            ("Nunca", "text", RESPOSTA_TRIAGEM_NUNCA),
            ("Às vezes", "interactive", RESPOSTA_TRIAGEM_AS_VEZES),
            (
                "Frequentemente",
                "button",
                RESPOSTA_TRIAGEM_FREQUENTEMENTE,
            ),
        )

        for texto, tipo, esperado in casos:
            with self.subTest(texto=texto):
                self.assertEqual(
                    validar_resposta_triagem(texto, tipo),
                    esperado,
                )

        for texto, tipo in (
            ("Nunca esqueço", "text"),
            ("Sempre", "text"),
            ("Nunca", "image"),
        ):
            with self.subTest(texto=texto, tipo=tipo):
                self.assertIsNone(validar_resposta_triagem(texto, tipo))

    def test_satisfacao_aceita_uma_unica_opcao_coerente(self):
        casos = (
            ("1", 1),
            ("Muito ruim", 1),
            ("1 - Muito ruim", 1),
            ("2 Ruim", 2),
            ("3 - Regular", 3),
            ("Muito bom", 4),
            ("satisfacao_5", 5),
            ("5 Excelente", 5),
        )

        for texto, nota in casos:
            with self.subTest(texto=texto):
                self.assertEqual(validar_etapa17(texto), nota)

        for texto in (
            "2 - Bom",
            "2 3",
            "2 - Ruim 3 - Regular",
            "5 - Muito bom",
            "Excelente ou Muito bom",
            "Qual é o horário?",
            "",
        ):
            with self.subTest(texto=texto):
                self.assertIsNone(validar_etapa17(texto))

    def test_comentario_preserva_texto_e_usa_null_para_recusa_ou_midia(self):
        self.assertEqual(
            normalizar_comentario_etapa18(
                "  Atendimento muito atencioso!  ",
                "text",
            ),
            "Atendimento muito atencioso!",
        )
        self.assertIsNone(
            normalizar_comentario_etapa18(
                "Prefiro não comentar",
                "interactive",
            )
        )
        self.assertIsNone(
            normalizar_comentario_etapa18("legenda ignorada", "image")
        )


if __name__ == "__main__":
    unittest.main()
