"""Contrato dos transportes do projeto com o SDK real, sem acessar a Meta.

Somente o transporte HTTP é simulado. Assim, mudanças na serialização da PyWa,
nos objetos retornados e nas exceções são exercitadas junto dos nossos senders.
"""

import json
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import httpx
from pywa.errors import WhatsAppError

from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.pywa_functions import cliente
from core.integrations.whatsapp.pywa_functions.pywa_senders import (
    etapa6, etapa7, etapa21, followup,
)
from core.integrations.whatsapp.pywa_functions.resposta_envio import extrair_id_hash_msg_bot
from core.integrations.whatsapp.tools import usuarios


PHONE_ID = "1234567890"
TELEFONE_CLIENTE = "5511999999999"
ID_MENSAGEM = "wamid.teste.compatibilidade"


class PywaCompatibilidadeTests(unittest.TestCase):
    def setUp(self):
        self.requisicoes = []
        self.resposta = {
            "messaging_product": "whatsapp",
            "contacts": [{"input": TELEFONE_CLIENTE, "wa_id": TELEFONE_CLIENTE}],
            "messages": [{"id": ID_MENSAGEM}],
        }
        self.status_http = 200
        self.falha_transporte = None
        self.session = httpx.Client(transport=httpx.MockTransport(self._responder))
        self.addCleanup(self.session.close)

    def _responder(self, requisicao):
        self.requisicoes.append(requisicao)
        if self.falha_transporte:
            raise self.falha_transporte
        return httpx.Response(self.status_http, json=self.resposta)

    def _cliente_real(self):
        return cliente.conta_wa(PHONE_ID, token="token-de-teste", session=self.session)

    def _payload(self):
        return json.loads(self.requisicoes[-1].content)

    def test_texto_prefixo_e_versao_configurada_da_graph(self):
        with patch.object(cliente, "get_meta_graph_api_version", return_value="25.0"):
            with cliente.usar_prefixo_mensagem_bot("Olá novamente!\n\n"):
                retorno = self._cliente_real().send_message(
                    to=TELEFONE_CLIENTE, text="Podemos continuar?",
                )
        self.assertEqual(extrair_id_hash_msg_bot(retorno), ID_MENSAGEM)
        self.assertEqual(str(self.requisicoes[0].url),
                         f"https://graph.facebook.com/v25.0/{PHONE_ID}/messages")
        payload = self._payload()
        self.assertEqual(payload["to"], TELEFONE_CLIENTE)
        self.assertEqual(payload["type"], "text")
        self.assertEqual(payload["text"]["body"], "Olá novamente!\n\nPodemos continuar?")

    def test_oferta_preserva_botao_reserva_e_id_para_persistencia(self):
        with patch.object(etapa7, "conta_wa", return_value=self._cliente_real()):
            resultado = etapa7.enviar_etapa7_cliente(TELEFONE_CLIENTE, PHONE_ID, "Ana")
        interativa = self._payload()["interactive"]
        self.assertEqual(interativa["type"], "button")
        self.assertIn({"type": "reply", "reply": {
            "id": "Reservar agora", "title": "Reservar agora",
        }}, interativa["action"]["buttons"])
        self.assertEqual(resultado["id_hash_msg_bot"], ID_MENSAGEM)
        self.assertTrue(resultado["enviou"])

    def test_contato_comercial_preserva_mensagem_pronta_no_link(self):
        texto = "Olá, sou Ana e tenho 71 anos. Gostaria de conhecer o Supera!"
        with patch.object(etapa6, "conta_wa", return_value=self._cliente_real()):
            resultado = etapa6.enviar_etapa6_suporte_idoso(
                TELEFONE_CLIENTE, PHONE_ID, "5511888888888", 70,
                mensagem_comercial=texto,
            )
        interativa = self._payload()["interactive"]
        self.assertEqual(interativa["type"], "cta_url")
        link = urlsplit(interativa["action"]["parameters"]["url"])
        self.assertEqual(link.netloc, "wa.me")
        self.assertEqual(link.path, "/5511888888888")
        self.assertEqual(parse_qs(link.query)["text"], [texto])
        self.assertEqual(resultado["id_hash_msg_bot"], ID_MENSAGEM)

    def test_avaliacao_preserva_cinco_opcoes_e_callbacks(self):
        with patch.object(etapa21, "conta_wa", return_value=self._cliente_real()):
            resultado = etapa21.enviar_etapa21(TELEFONE_CLIENTE, PHONE_ID, "Ana")
        interativa = self._payload()["interactive"]
        self.assertEqual(interativa["type"], "list")
        linhas = interativa["action"]["sections"][0]["rows"]
        self.assertEqual({linha["id"] for linha in linhas},
                         {f"satisfacao_{nota}" for nota in range(1, 6)})
        self.assertEqual(resultado["id_hash_msg_bot"], ID_MENSAGEM)

    def test_followup_mantem_timeout_e_envia_sem_prefixo(self):
        with patch.object(followup.httpx, "Client", return_value=self.session) as criar:
            with cliente.usar_prefixo_mensagem_bot("Olá novamente!"):
                resultado = followup.enviar_followup(
                    TELEFONE_CLIENTE, PHONE_ID, mensagem="Podemos continuar?",
                )
        self.assertEqual(criar.call_args.kwargs["timeout"].connect, 5)
        self.assertEqual(criar.call_args.kwargs["timeout"].read, 20)
        self.assertEqual(len(self.requisicoes), 1)
        self.assertEqual(self._payload()["text"]["body"], "Podemos continuar?")
        self.assertEqual(resultado["id_hash_msg_bot"], ID_MENSAGEM)

    def test_rejeicao_meta_chega_ao_worker_sem_sucesso_ou_retry_http(self):
        cliente_wa = self._cliente_real()
        for status, codigo in ((400, 131047), (429, 4), (500, 131000)):
            with self.subTest(status=status, codigo=codigo):
                self.status_http = status
                self.resposta = {"error": {"code": codigo, "message": "Falha simulada"}}
                self.requisicoes.clear()
                with patch.object(etapa7, "conta_wa", return_value=cliente_wa):
                    with self.assertRaises(ErroEnvioMeta) as erro:
                        etapa7.enviar_etapa7_cliente(TELEFONE_CLIENTE, PHONE_ID, "Ana")
                self.assertIsInstance(erro.exception.__cause__, WhatsAppError)
                self.assertEqual(erro.exception.__cause__.code, codigo)
                self.assertEqual(erro.exception.__cause__.status_code, status)
                self.assertEqual(len(self.requisicoes), 1)

    def test_timeout_do_followup_permanece_resultado_incerto_sem_reenvio(self):
        self.falha_transporte = httpx.ReadTimeout("Resposta não recebida")
        with patch.object(followup.httpx, "Client", return_value=self.session):
            with self.assertRaises(ErroEnvioMeta) as erro:
                followup.enviar_followup(TELEFONE_CLIENTE, PHONE_ID)
        self.assertIs(erro.exception.__cause__, self.falha_transporte)
        self.assertEqual(len(self.requisicoes), 1)

    def test_resposta_sem_id_nao_e_confirmada_como_envio(self):
        self.resposta["messages"] = [{}]
        with patch.object(etapa7, "conta_wa", return_value=self._cliente_real()):
            with self.assertRaises(ErroEnvioMeta):
                etapa7.enviar_etapa7_cliente(TELEFONE_CLIENTE, PHONE_ID, "Ana")

    def test_bloqueio_e_desbloqueio_preservam_numero_e_resultado(self):
        cliente_wa = self._cliente_real()
        for funcao, metodo, campo in (
            (usuarios.bloquear_usuario_meta, "POST", "added_users"),
            (usuarios.desbloquear_usuario_meta, "DELETE", "removed_users"),
        ):
            with self.subTest(operacao=campo):
                self.resposta = {"block_users": {campo: [
                    {"input": TELEFONE_CLIENTE, "wa_id": TELEFONE_CLIENTE},
                ]}}
                with patch.object(usuarios, "conta_wa", return_value=cliente_wa):
                    resultado = funcao(TELEFONE_CLIENTE, PHONE_ID)
                self.assertEqual(self.requisicoes[-1].method, metodo)
                self.assertTrue(self.requisicoes[-1].url.path.endswith(f"/{PHONE_ID}/block_users"))
                self.assertEqual(self._payload()["block_users"], [{"user": TELEFONE_CLIENTE}])
                self.assertEqual(getattr(resultado, campo)[0].wa_id, TELEFONE_CLIENTE)

    def test_lista_bloqueados_percorre_paginas_com_objetos_reais(self):
        self.resposta = {
            "data": [{"input": TELEFONE_CLIENTE, "wa_id": TELEFONE_CLIENTE}],
            "paging": {"next": f"https://graph.facebook.com/v26.0/{PHONE_ID}/block_users?after=2"},
        }
        pagina = self._cliente_real().get_blocked_users()
        self.resposta = {"data": [{"input": "5511888888888", "wa_id": "5511888888888"}]}
        bloqueados = pagina.all(sleep=0)
        self.assertEqual([usuario.wa_id for usuario in bloqueados],
                         [TELEFONE_CLIENTE, "5511888888888"])
        self.assertEqual(len(self.requisicoes), 2)
        self.assertEqual(self.requisicoes[1].url.params["after"], "2")


if __name__ == "__main__":
    unittest.main()
