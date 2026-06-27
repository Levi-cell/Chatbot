import unittest

from workers.worker_flow.response_flow.etapas.detector_etapas import detector_nome


class DetectorNomeTests(unittest.TestCase):
    def test_remove_numeros_e_caracteres_de_uma_palavra(self):
        casos = [
            ("Pedro00", "Pedro"),
            ("Pedro##", "Pedro"),
            ("Pedro.", "Pedro"),
            ("Pedro  #", "Pedro"),
            ("Mano 99", "Mano"),
            ("Joao99", "Joao"),
            ("João99", "Joao"),
            ("Pedro😀", "Pedro"),
            ("😀Pedro", "Pedro"),
        ]

        for texto, primeiro_nome in casos:
            with self.subTest(texto=texto):
                resultado = detector_nome.validar_nome_cliente(texto)

                self.assertTrue(resultado.valido)
                self.assertEqual(resultado.primeiro_nome, primeiro_nome)
                self.assertIsNone(resultado.motivo)

    def test_aceita_palavra_unica_sem_confirmar_se_e_nome_real(self):
        casos = [
            ("Mano", "Mano"),
            ("Cole", "Cole"),
            ("Quero", "Quero"),
            ("João", "Joao"),
            ("Abraão", "Abraao"),
            ("Joao", "Joao"),
            ("pedro", "Pedro"),
            ("Ysabella", "Ysabella"),
            ("Anna", "Anna"),
            ("Lynn", "Lynn"),
        ]

        for texto, primeiro_nome in casos:
            with self.subTest(texto=texto):
                resultado = detector_nome.validar_nome_cliente(texto)

                self.assertTrue(resultado.valido)
                self.assertEqual(resultado.primeiro_nome, primeiro_nome)
                self.assertFalse(detector_nome.detecta_nome_invalido(texto))

    def test_preserva_nomes_reais_comuns_raros_e_internacionais(self):
        casos = [
            "Ana",
            "João",
            "Maria",
            "Pedro",
            "Paulo",
            "Cunha",
            "Edcarlos",
            "Ysabella",
            "Christopher",
            "Schwartz",
            "Rhys",
            "Nguyen",
            "Ayla",
            "Vitória",
            "Graça",
            "Sol",
            "Luz",
            "Rosa",
            "Violeta",
            "Ubirajara",
            "Washington",
            "Wellington",
            "Jefferson",
            "Gleydson",
            "Kethlynn",
        ]

        for texto in casos:
            with self.subTest(texto=texto):
                resultado = detector_nome.validar_nome_cliente(texto)

                self.assertTrue(resultado.valido)
                self.assertIsNotNone(resultado.primeiro_nome)

    def test_bloqueia_entrada_sem_letras(self):
        casos = [
            "000",
            "999",
            "###",
            "##99",
            "## 99",
            "9 9",
            "# #",
        ]

        for texto in casos:
            with self.subTest(texto=texto):
                resultado = detector_nome.validar_nome_cliente(texto)

                self.assertFalse(resultado.valido)
                self.assertEqual(resultado.motivo, detector_nome.MOTIVO_SEM_LETRAS)

    def test_bloqueia_nomes_compostos_e_frases(self):
        casos = [
            "Maria julia",
            "Meu nome é Pedro",
            "Pedro Maria99",
            "Pedro#Maria",
            "Maria-Julia",
            "Meu.nome.e.Pedro",
            "Meu_nome_e_Pedro",
            "Pedro\u200bMaria",
            "Pe😀dro",
            "pedro@gmail.com",
            "https://pedro.com",
        ]

        for texto in casos:
            with self.subTest(texto=texto):
                resultado = detector_nome.validar_nome_cliente(texto)

                self.assertFalse(resultado.valido)
                self.assertEqual(
                    resultado.motivo,
                    detector_nome.MOTIVO_MULTIPLAS_PALAVRAS,
                )

    def test_bloqueia_tres_ou_mais_letras_iguais_seguidas(self):
        casos = [
            "ppp",
            "Pppjoao",
            "aaaa",
            "mariiiia",
            "ppp99",
        ]

        for texto in casos:
            with self.subTest(texto=texto):
                resultado = detector_nome.validar_nome_cliente(texto)

                self.assertFalse(resultado.valido)
                self.assertEqual(
                    resultado.motivo,
                    detector_nome.MOTIVO_REPETICAO_CARACTERE,
                )

    def test_bloqueia_termos_pejorativos_mesmo_disfarcados(self):
        casos = [
            "puta",
            "Puta99",
            "p.u.t.a",
            "meu nome é Vagabunda",
            "putas",
            "putinhaa",
            "vagabundinha",
            "PutaMaria",
            "MariaPuta",
        ]

        for texto in casos:
            with self.subTest(texto=texto):
                resultado = detector_nome.validar_nome_cliente(texto)

                self.assertFalse(resultado.valido)
                self.assertEqual(
                    resultado.motivo,
                    detector_nome.MOTIVO_TERMO_PEJORATIVO,
                )

    def test_bloqueia_respostas_obvias_fora_do_contexto(self):
        casos = [
            "oi",
            "olá",
            "sim",
            "não",
            "teste",
            "continuar",
            "valor",
            "custo",
            "agendamento",
            "obrigado",
            "computador",
            "celular",
            "whatsapp",
            "MeuNomeEPedro",
            "mechamoCarlos",
        ]

        for texto in casos:
            with self.subTest(texto=texto):
                resultado = detector_nome.validar_nome_cliente(texto)

                self.assertFalse(resultado.valido)
                self.assertEqual(
                    resultado.motivo,
                    detector_nome.MOTIVO_FORA_CONTEXTO,
                )

    def test_mantem_risco_controlado_de_palavras_ambiguas(self):
        casos = [
            ("Quero", "Quero"),
            ("Vai", "Vai"),
            ("Mano", "Mano"),
            ("Cole", "Cole"),
        ]

        for texto, primeiro_nome in casos:
            with self.subTest(texto=texto):
                resultado = detector_nome.validar_nome_cliente(texto)

                self.assertTrue(resultado.valido)
                self.assertEqual(resultado.primeiro_nome, primeiro_nome)

    def test_bloqueia_tipo_invalido(self):
        for texto in (None, 123, True, ["Pedro"]):
            with self.subTest(texto=texto):
                resultado = detector_nome.validar_nome_cliente(texto)

                self.assertFalse(resultado.valido)
                self.assertEqual(
                    resultado.motivo,
                    detector_nome.MOTIVO_TIPO_INVALIDO,
                )

    def test_bloqueia_nome_com_comprimento_fora_do_limite(self):
        casos = [
            "A",
            "ab" * 26,
        ]

        for texto in casos:
            with self.subTest(texto=texto):
                resultado = detector_nome.validar_nome_cliente(texto)

                self.assertFalse(resultado.valido)
                self.assertEqual(
                    resultado.motivo,
                    detector_nome.MOTIVO_COMPRIMENTO_INVALIDO,
                )

    def test_bloqueia_estrutura_sem_vogal_ou_com_consoantes_improvaveis(self):
        casos = [
            "xzxzxz",
            "bcdfgh",
        ]

        for texto in casos:
            with self.subTest(texto=texto):
                resultado = detector_nome.validar_nome_cliente(texto)

                self.assertFalse(resultado.valido)
                self.assertEqual(
                    resultado.motivo,
                    detector_nome.MOTIVO_ESTRUTURA_IMPROVAVEL,
                )

    def test_helpers_reaproveitam_a_mesma_validacao(self):
        self.assertEqual(
            detector_nome.extrair_primeiro_nome_cliente("Pedro99"),
            "Pedro",
        )
        self.assertIsNone(
            detector_nome.extrair_primeiro_nome_cliente("Meu nome é Pedro")
        )


if __name__ == "__main__":
    unittest.main()
