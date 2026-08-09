import unittest

from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa2 import (
    PARENTESCOS_ACEITOS,
    validar_etapa2,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa4 import (
    TAMANHO_MAXIMO_PROFISSAO,
    validar_profissao_etapa4,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa6 import (
    STATUS_IDADE_ACIMA_LIMITE,
    STATUS_IDADE_INVALIDA,
    obter_idade_minima_dependente,
    validar_idade,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa7 import (
    validar_etapa7,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa9 import (
    validar_etapa9,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa10 import (
    validar_etapa10,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa19 import (
    validar_etapa19,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa20 import (
    validar_decisao_comentario_etapa20,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa21 import (
    normalizar_comentario_etapa21,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.validador_financeiro_etapa4 import (
    validar_pergunta_financeira_etapa4,
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
    EVENTO_COMENTARIO_SATISFACAO_ACEITO,
    EVENTO_COMENTARIO_SATISFACAO_RECUSADO,
    EVENTO_OFERTA_ACEITA,
    EVENTO_OFERTA_ADIADA,
    EVENTO_PARA_MIM,
    EVENTO_PARA_OUTRA_PESSOA,
    EVENTO_RETORNO_ADIADO,
    EVENTO_RETORNO_CONFIRMADO,
)


class ValidadoresEssenciaisTests(unittest.TestCase):
    def test_etapa2_classifica_frases_para_a_propria_pessoa(self):
        frases = (
            "Para mim",
            "Só para mim!",
            "Eu mesmo",
            "Eu mesma",
            "Sim, é para mim.",
            "Não, é para mim",
            "Quero para mim",
            "Pra eu",
        )

        for frase in frases:
            with self.subTest(frase=frase):
                self.assertEqual(validar_etapa2(frase), EVENTO_PARA_MIM)

    def test_etapa2_classifica_parentescos_e_frases_para_dependente(self):
        frases = (
            "Para um dependente",
            "Para outra pessoa",
            "Para um dependente meu",
            "Para alguém que depende de mim",
            "Para uma criança",
            "Para um idoso",
            "Para um deficiente",
            "Minha irmã",
            "Sim, para meu filho",
            "Quero para a minha filha",
            "Sim eu quero, é para o meu avô",
            "Quero para a minha",
            "Pra minha enteada",
            "Para meu filha",
            "Não, é para minha filha",
            "Não é para mim, é para o meu pai",
            "É pro meu filho",
            "Sim, é pra minha mãe",
            "É pra outra pessoa",
            "Para meus pais",
            "Sim eu quero, é para as minhas filhas",
        )

        for frase in frases:
            with self.subTest(frase=frase):
                self.assertEqual(
                    validar_etapa2(frase),
                    EVENTO_PARA_OUTRA_PESSOA,
                )

        for parentesco in PARENTESCOS_ACEITOS:
            with self.subTest(parentesco=parentesco):
                self.assertEqual(
                    validar_etapa2(f"Para meu {parentesco}"),
                    EVENTO_PARA_OUTRA_PESSOA,
                )

    def test_etapa2_rejeita_respostas_ambiguas_ou_fora_do_contexto(self):
        for frase in (
            "",
            "Sim",
            "Quero",
            "Talvez",
            "Qual o valor?",
            "Meu nome é Carlos",
            "Para meu cachorro",
            None,
        ):
            with self.subTest(frase=frase):
                self.assertIsNone(validar_etapa2(frase))

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

    def test_profissao_aceita_textos_livres_reais_e_siglas(self):
        profissoes = (
            "PJ",
            "MEI",
            "TI",
            "call center",
            "telemarketing",
            "autônomo",
            "Sou analista de custos",
            "Trabalho com finanças",
        )

        for texto in profissoes:
            with self.subTest(texto=texto):
                resultado = validar_profissao_etapa4(texto, "text")
                self.assertTrue(resultado.valida)
                self.assertEqual(resultado.profissao, texto)

    def test_profissao_rejeita_contextos_minimos_invalidos(self):
        entradas = (
            "",
            "!!!",
            "12345",
            "sim",
            "sim 👍",
            "Não",
            "ok",
            "ok ✅",
            "Prefiro não informar",
            "Prefiro não informar 🙏",
            "Prefiro não responder",
            "Não quero responder",
            "a" * (TAMANHO_MAXIMO_PROFISSAO + 1),
            "TI" + (" " * TAMANHO_MAXIMO_PROFISSAO) + "PJ",
        )

        for texto in entradas:
            with self.subTest(texto=texto):
                resultado = validar_profissao_etapa4(texto, "text")
                self.assertFalse(resultado.valida)
                self.assertIsNone(resultado.profissao)
                self.assertIsNotNone(resultado.motivo)

        resultado_interativo = validar_profissao_etapa4(
            "Para mim",
            "interactive",
        )
        self.assertFalse(resultado_interativo.valida)

    def test_financeiro_da_profissao_distingue_preco_de_ocupacao(self):
        perguntas_financeiras = (
            "Qual o valor?",
            "Quanto custa?",
            "Custo",
            "valor",
            "Qual a mensalidade?",
            "O investimento é de R$ 100?",
            "Tem mensalidade?",
            "Aceita pix?",
            "Qual seria o valor?",
            "Quanto vou investir?",
            "Quanto vai ser?",
            "100 reais",
        )

        for texto in perguntas_financeiras:
            with self.subTest(texto=texto):
                self.assertTrue(
                    validar_pergunta_financeira_etapa4(texto)
                )

        profissoes = (
            "Sou analista de custos",
            "Trabalho com finanças",
            "Analista de crédito",
            "Consultor de investimentos",
            "Analista de valores mobiliários",
        )
        for texto in profissoes:
            with self.subTest(texto=texto):
                self.assertFalse(
                    validar_pergunta_financeira_etapa4(texto)
                )

    def test_decisoes_das_etapas_seis_e_oito_traduzem_eventos(self):
        validadores = (
            (
                validar_etapa7,
                EVENTO_OFERTA_ACEITA,
                EVENTO_OFERTA_ADIADA,
            ),
            (
                validar_etapa9,
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
        resultado = validar_etapa10("Meu email é Ed@Gmail.com.")
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
                self.assertFalse(validar_etapa10(texto).valido)

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
                self.assertEqual(validar_etapa19(texto), nota)

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
                self.assertIsNone(validar_etapa19(texto))

    def test_decisao_de_comentar_aceita_intencoes_claras(self):
        positivos = (
            "Sim",
            "Quero comentar",
            "Quero sugerir",
            "Sim, quero comentar",
            "SIM!!!",
        )
        negativos = (
            "Não",
            "Nao quero comentar",
            "Não quero sugerir",
            "Prefiro não comentar",
            "PREFIRO NAO COMENTAR!!!",
        )

        for texto in positivos:
            with self.subTest(texto=texto):
                self.assertEqual(
                    validar_decisao_comentario_etapa20(texto, "text"),
                    EVENTO_COMENTARIO_SATISFACAO_ACEITO,
                )

        for texto in negativos:
            with self.subTest(texto=texto):
                self.assertEqual(
                    validar_decisao_comentario_etapa20(
                        texto,
                        "interactive",
                    ),
                    EVENTO_COMENTARIO_SATISFACAO_RECUSADO,
                )

        self.assertEqual(
            validar_decisao_comentario_etapa20(
                "Sim, quero comentar",
                "button",
            ),
            EVENTO_COMENTARIO_SATISFACAO_ACEITO,
        )

    def test_decisao_de_comentar_rejeita_ambiguidade_conteudo_e_midia(self):
        for texto, tipo in (
            ("Talvez", "text"),
            ("Não sei", "text"),
            ("Sim, mas não quero comentar", "text"),
            ("Quero comentar, mas não agora", "text"),
            ("O atendimento foi ótimo", "text"),
            ("", "text"),
            ("Sim", "image"),
        ):
            with self.subTest(texto=texto, tipo=tipo):
                self.assertIsNone(
                    validar_decisao_comentario_etapa20(texto, tipo)
                )

    def test_comentario_da_etapa21_preserva_texto_e_rejeita_vazio_ou_midia(self):
        self.assertEqual(
            normalizar_comentario_etapa21(
                "  Atendimento muito atencioso!  ",
                "text",
            ),
            "Atendimento muito atencioso!",
        )

        for texto, tipo in (
            ("", "text"),
            ("   ", "text"),
            ("legenda ignorada", "image"),
        ):
            with self.subTest(texto=texto, tipo=tipo):
                self.assertIsNone(
                    normalizar_comentario_etapa21(texto, tipo)
                )


if __name__ == "__main__":
    unittest.main()
