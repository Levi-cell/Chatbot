import unittest
from unittest.mock import patch

from callback.webhook.services import populating_fila_mensagens as fila
from tests.helpers import FakeCursor
from tests.payloads import (
    payload_imagem_meta,
    payload_interactive_button_meta,
    payload_interactive_list_meta,
    payload_sem_mensagem,
    payload_texto_meta,
)


class PopulatingFilaTests(unittest.TestCase):
    def test_extrair_dados_whatsapp_payload_valido(self):
        dados = fila.extrair_dados_whatsapp(payload_texto_meta())

        self.assertNotIn("erro", dados)
        self.assertEqual(dados["status"], "pending")
        self.assertEqual(dados["retry_count"], 0)
        self.assertEqual(dados["cliente_telefone"], "5571999999999")
        self.assertEqual(dados["id_phone_unidade"], "123456")
        self.assertEqual(dados["id_hash_msg"], "wamid.test.1")
        self.assertEqual(dados["tipo_mensagem"], "text")
        self.assertEqual(dados["conteudo_texto"], "ola")

    def test_extrair_dados_whatsapp_interactive_button_preenche_conteudo_texto(self):
        dados = fila.extrair_dados_whatsapp(
            payload_interactive_button_meta(titulo_botao="Aperte em mim")
        )

        self.assertNotIn("erro", dados)
        self.assertEqual(dados["tipo_mensagem"], "interactive")
        self.assertEqual(dados["conteudo_texto"], "Aperte em mim")

    def test_extrair_dados_whatsapp_interactive_list_preenche_conteudo_texto(self):
        dados = fila.extrair_dados_whatsapp(
            payload_interactive_list_meta(titulo_opcao="Opcao A")
        )

        self.assertNotIn("erro", dados)
        self.assertEqual(dados["tipo_mensagem"], "interactive")
        self.assertEqual(dados["conteudo_texto"], "Opcao A")

    def test_extrair_dados_whatsapp_imagem_mantem_conteudo_texto_nulo(self):
        dados = fila.extrair_dados_whatsapp(payload_imagem_meta())

        self.assertNotIn("erro", dados)
        self.assertEqual(dados["tipo_mensagem"], "image")
        self.assertIsNone(dados["conteudo_texto"])

    def test_extrair_dados_whatsapp_sem_mensagem(self):
        dados = fila.extrair_dados_whatsapp(payload_sem_mensagem())

        self.assertEqual(dados["erro"], "evento_sem_mensagem")

    def test_preparar_dados_fila_evento_sem_mensagem_retorna_ignored(self):
        preparacao = fila.preparar_dados_fila(payload_sem_mensagem())

        self.assertEqual(preparacao["status"], "ignored")
        self.assertEqual(preparacao["reason"], "evento_sem_mensagem")
        self.assertIsNone(preparacao["dados"])

    def test_turno_bloqueado_nao_insere(self):
        cursor = FakeCursor()
        dados = fila.extrair_dados_whatsapp(payload_texto_meta())

        with patch.object(
            fila,
            "avaliar_turno_cliente_para_fila",
            return_value={
                "pode_enfileirar": False,
                "motivo": "fila_aberta_sem_resposta_bot",
            },
        ):
            resultado = fila.inserir_dados_na_tabela_fila(dados, cursor)

        self.assertEqual(resultado["status"], "ignored")
        self.assertEqual(resultado["reason"], "fila_aberta_sem_resposta_bot")
        self.assertFalse(
            any("INSERT INTO chatbot.fila_mensagens" in call[0] for call in cursor.calls)
        )

    def test_turno_liberado_insere(self):
        cursor = FakeCursor(rowcount=1)
        dados = fila.extrair_dados_whatsapp(payload_texto_meta())

        with patch.object(
            fila,
            "avaliar_turno_cliente_para_fila",
            return_value={"pode_enfileirar": True, "motivo": "sem_fila_aberta"},
        ):
            resultado = fila.inserir_dados_na_tabela_fila(dados, cursor)

        self.assertEqual(resultado["status"], "inserted")
        self.assertTrue(
            any("INSERT INTO chatbot.fila_mensagens" in call[0] for call in cursor.calls)
        )

    def test_conflito_unico_retorna_ignored(self):
        cursor = FakeCursor(rowcount=0)
        dados = fila.extrair_dados_whatsapp(payload_texto_meta())

        with patch.object(
            fila,
            "avaliar_turno_cliente_para_fila",
            return_value={"pode_enfileirar": True, "motivo": "sem_fila_aberta"},
        ):
            resultado = fila.inserir_dados_na_tabela_fila(dados, cursor)

        self.assertEqual(resultado["status"], "ignored")
        self.assertEqual(resultado["reason"], "conflito_unico")

    def test_falha_de_banco_propaga_para_orquestrador(self):
        cursor = FakeCursor()
        dados = fila.extrair_dados_whatsapp(payload_texto_meta())

        def fake_turno(**_kwargs):
            raise RuntimeError("banco caiu")

        with patch.object(
            fila,
            "avaliar_turno_cliente_para_fila",
            fake_turno,
        ), self.assertRaisesRegex(RuntimeError, "banco caiu"):
            fila.inserir_dados_na_tabela_fila(dados, cursor)


if __name__ == "__main__":
    unittest.main()
