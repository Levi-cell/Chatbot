"""Comparacao do formulario nao representa procura por um curso de ingles."""

import unittest

from workers.worker_flow.fireads import classificar_tratamento_abertura
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_financeiro import (
    validar_pergunta_financeira,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_reforco_escolar import (
    validar_duvida_reforco_escolar,
)


COMPARACAO = "O investimento fica na faixa de um curso de inglês"
FORMULARIO = (
    "Olá! Preenchi seu formulário e gostaria de saber mais sobre sua empresa.\n"
    "Em qual cidade você mora?: Cidade Teste\n"
    "Para quem é o treino?: Para mim\n"
    f"{COMPARACAO}. Quem decide a matrícula?: Eu, junto com a família\n"
    "Email: ana@example.com\n"
    "Full name: Ana Silva"
)


class ComparacaoInvestimentoTests(unittest.TestCase):
    def test_comparacao_isolada_ou_no_formulario_nao_pede_aulas(self):
        for texto in (
            COMPARACAO,
            FORMULARIO,
            FORMULARIO.replace("Para mim", "Para meu filho"),
            FORMULARIO.upper(),
            COMPARACAO.replace("inglês", "ingles"),
            COMPARACAO.replace(" ", " \n\t "),
            f"{COMPARACAO}. {COMPARACAO}.",
        ):
            with self.subTest(texto=texto):
                self.assertFalse(validar_duvida_reforco_escolar(texto))

    def test_pergunta_real_adicionada_ao_formulario_continua_reconhecida(self):
        for pergunta in (
            "Vocês têm curso de inglês?",
            "Preciso de aulas de inglês.",
            "Tem reforço escolar para meu filho?",
            "Oferecem aulas de matemática?",
        ):
            for texto in (
                f"{FORMULARIO}\n{pergunta}",
                f"{pergunta}\n{FORMULARIO}",
            ):
                with self.subTest(texto=texto):
                    self.assertTrue(validar_duvida_reforco_escolar(texto))

    def test_mencoes_fora_da_comparacao_conservam_o_tratamento(self):
        for texto in (
            "Curso de inglês",
            "Quanto custa o curso de inglês?",
            "O investimento no curso de inglês é quanto?",
            "Quanto custa o reforço escolar?",
        ):
            with self.subTest(texto=texto):
                self.assertTrue(validar_duvida_reforco_escolar(texto))

    def test_entradas_vazias_e_profissao_continuam_sem_tratamento(self):
        for texto in (None, 123, "", "   ", "Sou professora de inglês"):
            with self.subTest(texto=texto):
                self.assertFalse(validar_duvida_reforco_escolar(texto))


class EnunciadoFormularioTests(unittest.TestCase):
    def test_comparacao_e_rotulo_do_formulario_nao_sao_pergunta_financeira(self):
        for texto in (
            COMPARACAO,
            FORMULARIO,
            FORMULARIO.upper(),
            FORMULARIO.replace("inglês", "ingles").replace("matrícula", "matricula"),
            FORMULARIO.replace(" ", " \n\t "),
            FORMULARIO.replace("matrícula?:", "matrícula:"),
            FORMULARIO.replace("Quem decide a matrícula?:", "Quem decide a matrícula??:"),
        ):
            with self.subTest(texto=texto):
                self.assertFalse(validar_pergunta_financeira(texto))
                self.assertIsNone(classificar_tratamento_abertura({
                    "tipo_mensagem_atual": "text", "texto_cliente_atual": texto,
                }))

    def test_duvidas_financeiras_fora_do_enunciado_continuam_reconhecidas(self):
        for pergunta in (
            "Qual o valor?",
            "Quanto custa a matrícula?",
            "Aceita cartão?",
            "É caro?",
            "A experiência é gratuita?",
        ):
            for texto in (
                pergunta,
                f"{FORMULARIO}\n{pergunta}",
                f"{pergunta}\n{FORMULARIO}",
            ):
                with self.subTest(texto=texto):
                    self.assertTrue(validar_pergunta_financeira(texto))
                    self.assertEqual(classificar_tratamento_abertura({
                        "tipo_mensagem_atual": "text", "texto_cliente_atual": texto,
                    }), "pergunta_financeira")

    def test_resposta_ao_rotulo_nao_e_descartada(self):
        texto = FORMULARIO.replace("Eu, junto com a família", "Depende do valor")
        self.assertTrue(validar_pergunta_financeira(texto))

    def test_rotulo_isolado_e_outros_investimentos_nao_sao_ignorados(self):
        for texto in (
            "Quem decide a matrícula?: Eu",
            "Quem decide a matrícula?",
            "O investimento para o curso é quanto?",
            f"{COMPARACAO}. Quanto custa a matrícula?:",
            f"{COMPARACAO}. Quem decide a matrícula?",
        ):
            with self.subTest(texto=texto):
                self.assertTrue(validar_pergunta_financeira(texto))

    def test_midia_e_pergunta_escolar_mantem_prioridade_na_abertura(self):
        contexto = {"tipo_mensagem_atual": "image", "texto_cliente_atual": FORMULARIO}
        self.assertEqual(
            classificar_tratamento_abertura(contexto), "tipo_mensagem_nao_suportado"
        )
        contexto.update(
            tipo_mensagem_atual="text",
            texto_cliente_atual=f"{FORMULARIO}\nQuanto custa o reforço escolar?",
        )
        self.assertEqual(classificar_tratamento_abertura(contexto), "duvida_reforco_escolar")
