"""Preferência explícita de um turno; nunca inferir a escolha pelo horário."""

import unittest

from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa18 import (
    validar_etapa18,
)


class ValidarEtapa18Tests(unittest.TestCase):
    def test_frases_afirmativas_com_um_unico_turno(self):
        casos = {
            "manha": (
                "Pela manhã", "manhã", "Só de manhã", "Somente pela manhã",
                "Eu prefiro pela manhã", "Posso ir de manhã",
                "Para mim, só dá de manhã", "Pode marcar pela manhã",
                "Amanhã pela manhã", "No período matutino", "Manhã, prefiro manhã",
                "Bom dia! Quero reservar de manhã, por favor.",
                "Pela manhã fica melhor para mim", "Tenho disponibilidade de manhã",
                "Estou livre de manhã", "Pode marcar para a manhã",
            ),
            "tarde": (
                "Pela tarde", "à tarde", "Apenas à tarde", "Só posso pela tarde",
                "Prefiro ir à tarde", "Quero o turno da tarde", "amanhã pela tarde",
                "Pra mim é melhor de tarde", "No período vespertino",
                "Consigo comparecer à tarde", "De tarde está bom para mim",
                "  PELA\n TARDE! 👍", "Minha preferência é pela tarde",
                "Eu estou disponível à tarde", "Pode agendar para o período vespertino",
            ),
            "noite": (
                "Pela noite", "à noite", "Somente à noite", "Só consigo à noite",
                "Gostaria de ir à noite", "O melhor para mim é à noite",
                "Pode ser no período noturno", "Escolho a noite", "Vou à noite",
                "Fico com o turno da noite", "À noite funciona melhor para mim",
                "Tenho horário livre à noite", "Boa tarde! Prefiro à noite.",
                "À noite pode ser", "Pela noite dá certo para mim",
            ),
        }
        for turno, frases in casos.items():
            for frase in frases:
                for tipo in ("text", "interactive", "interactive_button"):
                    with self.subTest(frase=frase, tipo=tipo):
                        self.assertEqual(validar_etapa18(frase, tipo), turno)

    def test_nao_escolhe_por_mencao_ambigua_negativa_ou_multiplos_turnos(self):
        for frase in (
            "manhã e tarde", "tarde ou noite", "manhã/tarde", "manhã tarde noite",
            "Só pela manhã e pela noite", "Prefiro manhã, mas também posso à tarde",
            "Não posso de manhã, prefiro à noite", "matutino ou vespertino",
            "Não posso à noite", "n posso de manhã", "sem manhã", "nem de tarde",
            "Talvez pela manhã", "Acho que à tarde", "Qualquer turno", "Tanto faz",
            "manhã ou qualquer outro turno", "Depende, à noite", "Quem sabe de manhã",
            "Tem horário pela manhã?", "Quais horários vocês têm de tarde",
            "Queria saber se tem vaga à noite", "Pode ser de manhã?",
            "Boa tarde", "boa noite", "amanhã", "mais tarde", "Hoje à noite chove",
            "Eu trabalho de manhã", "À tarde eu trabalho", "Só depois da manhã",
            "Não sei", "Sim", "14h", "qualquer coisa", "", "👍",
        ):
            with self.subTest(frase=frase):
                self.assertIsNone(validar_etapa18(frase))

    def test_conteudo_ausente_ou_midia_nao_define_turno(self):
        for texto in (None, {}, [], 3):
            self.assertIsNone(validar_etapa18(texto))
        for tipo in ("audio", "image", "video", "document", "unsupported", None):
            self.assertIsNone(validar_etapa18("Pela manhã", tipo))
