import unittest

from workers.worker_flow.valida_resposta_cliente import (
    RESULTADO_MENSAGEM_FORA_DE_CONTEXTO,
    RESULTADO_PERGUNTA_FINANCEIRA,
    RESULTADO_RESPOSTA_VALIDA,
    RESULTADO_TIPO_MENSAGEM_NAO_SUPORTADO,
    TIPO_TRATAMENTO_FINANCEIRO,
    TIPO_TRATAMENTO_NOME_INVALIDO,
    validar_resposta_cliente,
)


def contexto_historico_base(
    tipo="text",
    texto="ola",
    id_etapa_atual=None,
    id_etapa_cliente=1,
):
    return {
        "id_conversa": 10,
        "id_etapa_atual": id_etapa_atual,
        "id_etapa_cliente": id_etapa_cliente,
        "id_etapa_resposta": 2,
        "tipo_mensagem_atual": tipo,
        "texto_cliente_atual": texto,
        "mensagem_cliente_atual": {
            "id_mensagem_fila": 20,
            "cliente_telefone": "5571999999999",
            "id_phone_unidade": "123456",
        },
    }


class ValidaRespostaClienteTests(unittest.TestCase):
    def test_text_e_valido_em_conversa_nova_mesmo_com_texto_estranho(self):
        for texto in ("ola", "pppppp", "xzxzxzxz", "a123sa1319xcz5", "**eada"):
            with self.subTest(texto=texto):
                resultado = validar_resposta_cliente(
                    contexto_historico_base("text", texto, id_etapa_atual=None)
                )

            self.assertEqual(resultado["resultado"], RESULTADO_RESPOSTA_VALIDA)
            self.assertIsNone(resultado["tipo_tratamento"])

    def test_interactive_e_valido(self):
        resultado = validar_resposta_cliente(contexto_historico_base("interactive"))

        self.assertEqual(resultado["resultado"], RESULTADO_RESPOSTA_VALIDA)
        self.assertIsNone(resultado["tipo_tratamento"])

    def test_image_nao_e_valido_e_nao_avanca_etapa(self):
        resultado = validar_resposta_cliente(contexto_historico_base("image"))

        self.assertEqual(resultado["resultado"], RESULTADO_TIPO_MENSAGEM_NAO_SUPORTADO)
        self.assertEqual(resultado["tipo_tratamento"], RESULTADO_TIPO_MENSAGEM_NAO_SUPORTADO)
        self.assertEqual(resultado["tipo_mensagem"], "image")
        self.assertFalse(resultado["avancar_etapa"])

    def test_texto_com_pergunta_financeira_vai_para_tratamento_sem_avancar(self):
        for texto in (
            "qual o valor?",
            "quanto custa?",
            "preço da mensalidade",
            "investimento",
            "capital",
        ):
            with self.subTest(texto=texto):
                resultado = validar_resposta_cliente(
                    contexto_historico_base("text", texto, id_etapa_atual=1)
                )

            self.assertEqual(resultado["resultado"], RESULTADO_PERGUNTA_FINANCEIRA)
            self.assertEqual(resultado["tipo_tratamento"], TIPO_TRATAMENTO_FINANCEIRO)
            self.assertFalse(resultado["avancar_etapa"])

    def test_nome_valido_na_etapa_1_segue_fluxo_normal(self):
        for nome in ("Ana", "João Silva", "Maria Clara", "Luiz"):
            with self.subTest(nome=nome):
                resultado = validar_resposta_cliente(
                    contexto_historico_base("text", nome, id_etapa_atual=1)
                )

            self.assertEqual(resultado["resultado"], RESULTADO_RESPOSTA_VALIDA)
            self.assertIsNone(resultado["tipo_tratamento"])

    def test_nome_invalido_na_etapa_1_vai_para_tratamento_de_contexto(self):
        for texto in ("pppppp", "xzxzxzxz", "a123sa1319xcz5", "**eada", "puta"):
            with self.subTest(texto=texto):
                resultado = validar_resposta_cliente(
                    contexto_historico_base("text", texto, id_etapa_atual=1)
                )

            self.assertEqual(resultado["resultado"], RESULTADO_MENSAGEM_FORA_DE_CONTEXTO)
            self.assertEqual(resultado["tipo_tratamento"], TIPO_TRATAMENTO_NOME_INVALIDO)
            self.assertFalse(resultado["avancar_etapa"])


if __name__ == "__main__":
    unittest.main()
