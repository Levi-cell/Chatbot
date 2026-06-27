import unittest

from workers.worker_flow.response_flow.etapas.detector_etapas import detector_nome


class DetectorNomeV1ContractTests(unittest.TestCase):
    def test_primeiro_nome_limpo_avanca(self):
        resultado = detector_nome.validar_nome_cliente("Pedro")

        self.assertTrue(resultado.valido)
        self.assertEqual(resultado.primeiro_nome, "Pedro")

    def test_numero_e_simbolo_sao_descartados_quando_sobra_uma_palavra(self):
        resultado = detector_nome.validar_nome_cliente("João99##")

        self.assertTrue(resultado.valido)
        self.assertEqual(resultado.primeiro_nome, "Joao")

    def test_palavra_comum_unica_e_risco_aceito(self):
        resultado = detector_nome.validar_nome_cliente("Quero")

        self.assertTrue(resultado.valido)
        self.assertEqual(resultado.primeiro_nome, "Quero")

    def test_nome_composto_nao_avanca(self):
        resultado = detector_nome.validar_nome_cliente("Maria Julia")

        self.assertFalse(resultado.valido)
        self.assertEqual(
            resultado.motivo,
            detector_nome.MOTIVO_MULTIPLAS_PALAVRAS,
        )

    def test_simbolo_entre_blocos_nao_converte_frase_em_nome(self):
        resultado = detector_nome.validar_nome_cliente("Pedro#Maria")

        self.assertFalse(resultado.valido)
        self.assertEqual(
            resultado.motivo,
            detector_nome.MOTIVO_MULTIPLAS_PALAVRAS,
        )

    def test_emoji_sozinho_nao_produz_nome_vazio(self):
        resultado = detector_nome.validar_nome_cliente("😀🔥")

        self.assertFalse(resultado.valido)
        self.assertIsNone(resultado.primeiro_nome)
        self.assertEqual(resultado.motivo, detector_nome.MOTIVO_SEM_LETRAS)

    def test_frase_nao_avanca(self):
        resultado = detector_nome.validar_nome_cliente("Meu nome é Pedro")

        self.assertFalse(resultado.valido)
        self.assertEqual(
            resultado.motivo,
            detector_nome.MOTIVO_MULTIPLAS_PALAVRAS,
        )


if __name__ == "__main__":
    unittest.main()
