import unittest

from workers.worker_flow.valida_resposta_cliente import (
    RESULTADO_RESPOSTA_VALIDA,
    RESULTADO_TIPO_MENSAGEM_NAO_SUPORTADO,
    validar_resposta_cliente,
)


def contexto_historico_base(tipo="text"):
    return {
        "id_conversa": 10,
        "id_etapa_cliente": 1,
        "id_etapa_resposta": 2,
        "tipo_mensagem_atual": tipo,
        "mensagem_cliente_atual": {
            "id_mensagem_fila": 20,
            "cliente_telefone": "5571999999999",
            "id_phone_unidade": "123456",
        },
    }


class ValidaRespostaClienteTests(unittest.TestCase):
    def test_text_e_valido(self):
        resultado = validar_resposta_cliente(contexto_historico_base("text"))

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


if __name__ == "__main__":
    unittest.main()
