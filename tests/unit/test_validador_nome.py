import unittest

from workers.worker_flow.response_flow.etapas.validadores_universais import validador_nome


class ValidadorNomeTests(unittest.TestCase):
    def test_aceita_nome_simples_ou_composto_com_ponto_final_opcional(self):
        casos = [
            ("Pedro.", "Pedro"),
            ("Maria.", "Maria"),
            ("Maria Julia", "Maria Julia"),
            ("Maria  Julia.", "Maria Julia"),
            ("João Pedro.", "João Pedro"),
        ]

        for texto, primeiro_nome in casos:
            with self.subTest(texto=texto):
                resultado = validador_nome.validar_nome_cliente(texto)

                self.assertTrue(resultado.valido)
                self.assertEqual(resultado.primeiro_nome, primeiro_nome)
                self.assertIsNone(resultado.motivo)

    def test_bloqueia_qualquer_numero(self):
        casos = [
            "Pedro00",
            "Mano 99",
            "Joao99",
            "João99",
            "99",
            "Maria Julia3",
            "Puta99",
            "ppp99",
        ]

        for texto in casos:
            with self.subTest(texto=texto):
                resultado = validador_nome.validar_nome_cliente(texto)

                self.assertFalse(resultado.valido)
                self.assertEqual(resultado.motivo, validador_nome.MOTIVO_NUMERO)

    def test_bloqueia_caractere_exceto_um_ponto_final(self):
        casos = [
            "Pedro##",
            "Pedro  #",
            "Pedro😀",
            "😀Pedro",
            "Pe😀dro",
            "Pedro#Maria",
            "Maria, Julia",
            "Maria. Julia",
            r"Ana\Clara",
            r"Ana-\Clara",
            "-Maria",
            "Maria-",
            "D''Avila",
            "Pedro\u200bMaria",
            "pedro@gmail.com",
            "https://pedro.com",
            "p.u.t.a",
            "p.u.n.h.e.t.a",
        ]

        for texto in casos:
            with self.subTest(texto=texto):
                resultado = validador_nome.validar_nome_cliente(texto)

                self.assertFalse(resultado.valido)
                self.assertEqual(
                    resultado.motivo,
                    validador_nome.MOTIVO_CARACTERE_INVALIDO,
                )

    def test_aceita_pontuacao_natural_hifen_e_apostrofo(self):
        casos = [
            ("João!", "João"),
            ("João!!", "João"),
            ("João!?!", "João"),
            ("João?", "João"),
            ("João,", "João"),
            ("Maria...", "Maria"),
            ("Prazer, João", "João"),
            ("Prazer, João!", "João"),
            ("Aqui é João", "João"),
            ("Meu nome: João", "João"),
            ("Meu nome: João Pedro.", "João Pedro"),
            ("Meu apelido é João", "João"),
            ("meu apelido eh joao", "João"),
            ("Meu apelido: João", "João"),
            ("Ana-Clara", "Ana-Clara"),
            ("D'Ávila", "D'Ávila"),
        ]

        for texto, nome in casos:
            with self.subTest(texto=texto):
                resultado = validador_nome.validar_nome_cliente(texto)

                self.assertTrue(resultado.valido)
                self.assertEqual(resultado.primeiro_nome, nome)

    def test_aceita_palavra_unica_sem_confirmar_se_e_nome_real(self):
        casos = [
            ("João", "João"),
            ("Abraão", "Abraão"),
            ("Joao", "João"),
            ("pedro", "Pedro"),
            ("Ysabella", "Ysabella"),
            ("Anna", "Anna"),
            ("Lynn", "Lynn"),
        ]

        for texto, primeiro_nome in casos:
            with self.subTest(texto=texto):
                resultado = validador_nome.validar_nome_cliente(texto)

                self.assertTrue(resultado.valido)
                self.assertEqual(resultado.primeiro_nome, primeiro_nome)
                self.assertFalse(validador_nome.detecta_nome_invalido(texto))

    def test_preserva_acentos_e_til_na_resposta(self):
        nomes = [
            "João",
            "Abraão",
            "Simão",
            "Sebastião",
            "Damião",
            "Adão",
            "Romão",
            "Julião",
            "Estevão",
            "Cristóvão",
            "Cauã",
            "Kauã",
            "Conceição",
            "Assunção",
            "Ascensão",
            "Anunciação",
            "Aarão",
            "José",
            "Antônio",
            "Vitória",
            "Graça",
        ]

        for nome in nomes:
            with self.subTest(nome=nome):
                resultado = validador_nome.validar_nome_cliente(nome)

                self.assertTrue(resultado.valido)
                self.assertEqual(resultado.primeiro_nome, nome)

    def test_extrai_nome_de_frases_de_apresentacao_explicitas(self):
        casos = [
            ("É Pedro", "Pedro"),
            ("é joão", "João"),
            ("É jOÃO pEDRO.", "João Pedro"),
            ("E joao", "João"),
            ("eh joao", "João"),
            ("he joao", "João"),
            ("e joao pedro", "João Pedro"),
            ("Me chamo João", "João"),
            ("me chamo joao", "João"),
            ("me chamo de joao", "João"),
            ("eu me chamo de joao pedro", "João Pedro"),
            ("Eu me chamo João Pedro", "João Pedro"),
            ("Meu nome é João", "João"),
            ("Meu nome é João Pedro", "João Pedro"),
            ("O meu nome é Maria Julia.", "Maria Julia"),
            ("Pode me chamar de José", "José"),
            ("Sou João", "João"),
            ("Eu sou João Pedro", "João Pedro"),
        ]

        for texto, nome in casos:
            with self.subTest(texto=texto):
                resultado = validador_nome.validar_nome_cliente(texto)

                self.assertTrue(resultado.valido)
                self.assertEqual(resultado.primeiro_nome, nome)

    def test_corrige_nomes_conhecidos_quando_til_foi_omitido(self):
        casos = [
            ("joao", "João"),
            ("abraao", "Abraão"),
            ("simao", "Simão"),
            ("sebastiao", "Sebastião"),
            ("damiao", "Damião"),
            ("adao", "Adão"),
            ("cristovao", "Cristóvão"),
            ("caua", "Cauã"),
            ("kaua", "Kauã"),
            ("conceicao", "Conceição"),
            ("ubirata", "Ubiratã"),
            ("Maria Joao", "Maria João"),
        ]

        for texto, nome in casos:
            with self.subTest(texto=texto):
                resultado = validador_nome.validar_nome_cliente(texto)

                self.assertTrue(resultado.valido)
                self.assertEqual(resultado.primeiro_nome, nome)

    def test_nao_aplica_acento_fora_do_mapa_curado(self):
        resultado = validador_nome.validar_nome_cliente("Luan")

        self.assertTrue(resultado.valido)
        self.assertEqual(resultado.primeiro_nome, "Luan")

    def test_apresentacao_explicita_descarta_sobrenomes_posteriores(self):
        casos = [
            ("Meu nome é João Pedro da Silva", "João Pedro"),
            ("Meu nome é João da Silva", "João"),
            ("Eu me chamo Maria Eduarda Souza", "Maria Eduarda"),
            ("Pode me chamar de José dos Santos", "José"),
            ("Carlos Silva", "Carlos"),
            ("Carlos D'Ávila", "Carlos"),
            ("Maria Clara Silva", "Maria Clara"),
            ("Maria Clara Watanabe", "Maria Clara"),
            ("João Pedro Santos.", "João Pedro"),
            ("Edcarlos dos Santos Pereira Filho", "Edcarlos"),
        ]

        for texto, nome in casos:
            with self.subTest(texto=texto):
                resultado = validador_nome.validar_nome_cliente(texto)

                self.assertTrue(resultado.valido)
                self.assertEqual(resultado.primeiro_nome, nome)

    def test_aceita_variacoes_reais_de_primeiro_nome_composto(self):
        casos = [
            ("pedro joao", "Pedro João"),
            ("pedro joão", "Pedro João"),
            ("Me chamo pedro joão", "Pedro João"),
            ("Carlos Augusto", "Carlos Augusto"),
            ("Mario augusto", "Mario Augusto"),
            ("Me chamo Mário Augusto", "Mário Augusto"),
            ("Augusto Carlos", "Augusto Carlos"),
            ("Augusto Mário", "Augusto Mário"),
            ("Alexandre César", "Alexandre César"),
            ("José Alexandre", "José Alexandre"),
            ("César Alexandre", "César Alexandre"),
        ]

        for texto, nome in casos:
            with self.subTest(texto=texto):
                resultado = validador_nome.validar_nome_cliente(texto)

                self.assertTrue(resultado.valido)
                self.assertEqual(resultado.primeiro_nome, nome)

    def test_nao_extrai_nome_de_frase_generica_ou_cauda_invalida(self):
        casos = [
            ("Eu sou escolhido da favela", validador_nome.MOTIVO_FORA_CONTEXTO),
            ("Sou escolhido", validador_nome.MOTIVO_FORA_CONTEXTO),
            ("Meu nome é João Pedro Puta", validador_nome.MOTIVO_TERMO_PEJORATIVO),
            ("Meu nome é João Pedro teste", validador_nome.MOTIVO_FORA_CONTEXTO),
        ]

        for texto, motivo in casos:
            with self.subTest(texto=texto):
                resultado = validador_nome.validar_nome_cliente(texto)

                self.assertFalse(resultado.valido)
                self.assertEqual(resultado.motivo, motivo)

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
            "Cornelio",
            "Carolina",
            "Bianca",
            "Bia",
            "Safira",
            "Paloma",
            "Tadeu",
            "Tarcio",
            "Valdir",
            "Vagner",
            "Maciel",
            "Meredith",
            "John",
            "Ishimura",
        ]

        for texto in casos:
            with self.subTest(texto=texto):
                resultado = validador_nome.validar_nome_cliente(texto)

                self.assertTrue(resultado.valido)
                self.assertIsNotNone(resultado.primeiro_nome)

    def test_bloqueia_entrada_vazia_ou_sem_nome(self):
        casos = [
            "",
            "   ",
            ".",
        ]

        for texto in casos:
            with self.subTest(texto=texto):
                resultado = validador_nome.validar_nome_cliente(texto)

                self.assertFalse(resultado.valido)
                self.assertIsNone(resultado.primeiro_nome)

    def test_bloqueia_frase_generica_com_tres_palavras_ou_mais(self):
        casos = [
            ("Quero saber valores", validador_nome.MOTIVO_MULTIPLAS_PALAVRAS),
            ("Hoje quero conversar", validador_nome.MOTIVO_FORA_CONTEXTO),
            ("Banana Feliz Agora", validador_nome.MOTIVO_FORA_CONTEXTO),
        ]

        for texto, motivo in casos:
            with self.subTest(texto=texto):
                resultado = validador_nome.validar_nome_cliente(texto)

                self.assertFalse(resultado.valido)
                self.assertEqual(resultado.motivo, motivo)

    def test_bloqueia_tres_ou_mais_letras_iguais_seguidas(self):
        casos = [
            "ppp",
            "Pppjoao",
            "aaaa",
            "mariiiia",
        ]

        for texto in casos:
            with self.subTest(texto=texto):
                resultado = validador_nome.validar_nome_cliente(texto)

                self.assertFalse(resultado.valido)
                self.assertEqual(
                    resultado.motivo,
                    validador_nome.MOTIVO_REPETICAO_CARACTERE,
                )

    def test_bloqueia_termos_pejorativos_mesmo_disfarcados(self):
        casos = [
            "puta",
            "meu nome é Vagabunda",
            "Maria Puta",
            "putas",
            "putinhaa",
            "vagabundinha",
            "PutaMaria",
            "MariaPuta",
            "corno",
            "cuzao",
            "filhadaputa",
            "bostinha",
            "boqueteira",
            "mongoloide",
            "piriguete",
            "xoxota",
            "vsf",
            "tmnc",
            "p-u-t-a",
            "Maria-Puta",
        ]

        for texto in casos:
            with self.subTest(texto=texto):
                resultado = validador_nome.validar_nome_cliente(texto)

                self.assertFalse(resultado.valido)
                self.assertEqual(
                    resultado.motivo,
                    validador_nome.MOTIVO_TERMO_PEJORATIVO,
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
            "amanhã",
            "arquivo",
            "áudio",
            "cadastro",
            "desconto",
            "dúvida",
            "imagem",
            "matrícula",
            "mensalidade",
            "pagamento",
            "resposta",
            "senha",
            "unidade",
            "usuário",
            "Maria teste",
            "Pedro cadastro",
            "Ana pagamento",
            "me chamo",
            "chamo Pedro",
            "chamado Pedro",
            "de Pedro",
            "Pedro da Silva teste",
            "Quero",
            "Vai",
            "Mano",
            "Cole",
            "Banana Feliz",
            "Casa Azul",
            "Gosto daqui",
            "Laripo",
            "Zaneco",
            "Girafa Alegre",
            "Caderno Verde",
            "Maripo",
            "Zuleco",
        ]

        for texto in casos:
            with self.subTest(texto=texto):
                resultado = validador_nome.validar_nome_cliente(texto)

                self.assertFalse(resultado.valido)
                self.assertEqual(
                    resultado.motivo,
                    validador_nome.MOTIVO_FORA_CONTEXTO,
                )

    def test_bloqueia_falsos_positivos_conhecidos(self):
        casos = [
            "Quero",
            "Vai",
            "Mano",
            "Cole",
            "Quero Vai",
            "Banana Feliz",
            "Casa Azul",
            "Gosto daqui",
            "Laripo",
            "Zaneco",
            "Girafa Alegre",
            "Caderno Verde",
            "Maripo",
            "Zuleco",
            "Ana-Quero",
            "Quero-Ana",
            "e banana",
            "Meu nome é Banana Feliz",
        ]

        for texto in casos:
            with self.subTest(texto=texto):
                resultado = validador_nome.validar_nome_cliente(texto)

                self.assertFalse(resultado.valido)
                self.assertEqual(
                    resultado.motivo,
                    validador_nome.MOTIVO_FORA_CONTEXTO,
                )

    def test_bloqueia_tipo_invalido(self):
        for texto in (None, 123, True, ["Pedro"]):
            with self.subTest(texto=texto):
                resultado = validador_nome.validar_nome_cliente(texto)

                self.assertFalse(resultado.valido)
                self.assertEqual(
                    resultado.motivo,
                    validador_nome.MOTIVO_TIPO_INVALIDO,
                )

    def test_bloqueia_nome_com_comprimento_fora_do_limite(self):
        casos = [
            "A",
            "ab" * 26,
        ]

        for texto in casos:
            with self.subTest(texto=texto):
                resultado = validador_nome.validar_nome_cliente(texto)

                self.assertFalse(resultado.valido)
                self.assertEqual(
                    resultado.motivo,
                    validador_nome.MOTIVO_COMPRIMENTO_INVALIDO,
                )

    def test_bloqueia_estrutura_sem_vogal_ou_com_consoantes_improvaveis(self):
        casos = [
            "xzxzxz",
            "bcdfgh",
        ]

        for texto in casos:
            with self.subTest(texto=texto):
                resultado = validador_nome.validar_nome_cliente(texto)

                self.assertFalse(resultado.valido)
                self.assertEqual(
                    resultado.motivo,
                    validador_nome.MOTIVO_ESTRUTURA_IMPROVAVEL,
                )

    def test_resultado_preserva_contrato_e_adiciona_status_e_confianca(self):
        valido = validador_nome.validar_nome_cliente("João Pedro")
        invalido = validador_nome.validar_nome_cliente("João99")
        ambiguo = validador_nome.validar_nome_cliente("bcdfgh")

        self.assertTrue(valido.valido)
        self.assertEqual(valido.status, validador_nome.STATUS_VALIDO)
        self.assertGreaterEqual(valido.confianca, 0.90)
        self.assertLessEqual(valido.confianca, 1.0)

        self.assertFalse(invalido.valido)
        self.assertEqual(invalido.status, validador_nome.STATUS_INVALIDO)
        self.assertEqual(invalido.primeiro_nome, None)

        self.assertFalse(ambiguo.valido)
        self.assertEqual(ambiguo.status, validador_nome.STATUS_AMBIGUO)
        self.assertEqual(
            ambiguo.motivo,
            validador_nome.MOTIVO_ESTRUTURA_IMPROVAVEL,
        )

    def test_resultado_valido_nunca_pode_conter_nome_vazio(self):
        with self.assertRaises(ValueError):
            validador_nome.ResultadoValidacaoNome(
                True,
                status=validador_nome.STATUS_VALIDO,
            )

        with self.assertRaises(ValueError):
            validador_nome.ResultadoValidacaoNome(False)

    def test_normaliza_unicode_compativel_e_separadores_tipograficos(self):
        casos = [
            ("Ｊｏａｏ", "João"),
            ("Ana–Clara", "Ana-Clara"),
            ("Ana‑Clara", "Ana-Clara"),
            ("D’Ávila", "D'Ávila"),
            ("João\u00a0Pedro", "João Pedro"),
        ]

        for texto, nome in casos:
            with self.subTest(texto=texto):
                resultado = validador_nome.validar_nome_cliente(texto)

                self.assertTrue(resultado.valido)
                self.assertEqual(resultado.primeiro_nome, nome)

    def test_bloqueia_unicode_invisivel_misto_ou_nao_latino(self):
        casos = [
            "Pedro\u200bMaria",
            "João\u202e",
            "Jo\u0301\u0301ao",
            "Јoão",
            "Jοão",
            "张伟",
            "João\ufffd",
        ]

        for texto in casos:
            with self.subTest(texto=texto):
                resultado = validador_nome.validar_nome_cliente(texto)

                self.assertFalse(resultado.valido)
                self.assertEqual(
                    resultado.motivo,
                    validador_nome.MOTIVO_CARACTERE_INVALIDO,
                )

    def test_aceita_saudacao_antes_de_apresentacao_explicita(self):
        casos = [
            ("Oi, meu nome é João", "João"),
            ("Olá! Eu me chamo Maria Clara", "Maria Clara"),
            ("Bom dia, sou Carlos", "Carlos"),
            ("Boa tarde, aqui é Ana", "Ana"),
            ("Boa noite, pode me chamar de José", "José"),
        ]

        for texto, nome in casos:
            with self.subTest(texto=texto):
                resultado = validador_nome.validar_nome_cliente(texto)

                self.assertTrue(resultado.valido)
                self.assertEqual(resultado.primeiro_nome, nome)

    def test_aceita_artigo_e_cortesia_em_apresentacao(self):
        casos = [
            ("Sou o João", "João"),
            ("Eu sou a Maria", "Maria"),
            ("João, prazer", "João"),
            ("Maria, obrigada", "Maria"),
        ]

        for texto, nome in casos:
            with self.subTest(texto=texto):
                resultado = validador_nome.validar_nome_cliente(texto)

                self.assertTrue(resultado.valido)
                self.assertEqual(resultado.primeiro_nome, nome)

    def test_composto_conhecido_tem_prioridade_e_sobrenome_e_removido(self):
        casos = [
            ("José Alexandre", "José Alexandre"),
            ("César Alexandre", "César Alexandre"),
            ("Maria Tanaka", "Maria"),
            ("Ana Beatriz Tanaka", "Ana Beatriz"),
            ("João Vitor Silva", "João Vitor"),
        ]

        for texto, nome in casos:
            with self.subTest(texto=texto):
                resultado = validador_nome.validar_nome_cliente(texto)

                self.assertTrue(resultado.valido)
                self.assertEqual(resultado.primeiro_nome, nome)

    def test_aceita_formas_tradicionais_e_preserva_primeiro_nome(self):
        casos = [
            ("Maria das Dores", "Maria"),
            ("Maria das Graças", "Maria"),
            ("Maria de Fátima", "Maria"),
            ("Maria de Lourdes Silva", "Maria"),
            ("Maria do Socorro", "Maria"),
            ("José de Ribamar", "José"),
            ("João de Deus", "João"),
        ]

        for texto, nome in casos:
            with self.subTest(texto=texto):
                resultado = validador_nome.validar_nome_cliente(texto)

                self.assertTrue(resultado.valido)
                self.assertEqual(resultado.primeiro_nome, nome)

    def test_bloqueia_reacoes_e_comandos_comuns_da_conversa(self):
        casos = [
            "Tudo bem",
            "Ok",
            "Okay",
            "Queria saber",
            "Gostaria",
            "Avançar",
            "Prosseguir",
            "Seguir",
            "Eai",
            "Rsrs",
            "Hahaha",
            "Qwerty",
        ]

        for texto in casos:
            with self.subTest(texto=texto):
                resultado = validador_nome.validar_nome_cliente(texto)

                self.assertFalse(resultado.valido)
                self.assertEqual(
                    resultado.motivo,
                    validador_nome.MOTIVO_FORA_CONTEXTO,
                )

        repeticao = validador_nome.validar_nome_cliente("Kkkk")
        self.assertFalse(repeticao.valido)
        self.assertEqual(
            repeticao.motivo,
            validador_nome.MOTIVO_REPETICAO_CARACTERE,
        )

    def test_helpers_reaproveitam_a_mesma_validacao(self):
        self.assertEqual(
            validador_nome.extrair_primeiro_nome_cliente("Maria Julia."),
            "Maria Julia",
        )
        self.assertEqual(
            validador_nome.extrair_primeiro_nome_cliente("Meu nome é Pedro"),
            "Pedro",
        )


if __name__ == "__main__":
    unittest.main()
