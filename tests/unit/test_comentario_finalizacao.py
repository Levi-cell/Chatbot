"""Comentário livre, recuperação e despedida com o participante correto."""

import unittest
from contextlib import ExitStack
from datetime import datetime, timezone
from unittest.mock import patch

from core.integrations.whatsapp.pywa_functions import cliente
from core.integrations.whatsapp.pywa_functions.pywa_senders import etapa22
from core.repositories.fluxo.contextos.etapa22 import buscar_contexto_etapa22
from tests.helpers import FakeCursor
from tests.unit.test_mensagens_reserva import cliente_simulado, contexto_resposta
from workers.worker_flow import valida_historico as historico
from workers.worker_flow.response_flow.flow_sender import flow_sender
from workers.worker_flow.transacoes import efeitos_transicao


EVENTO_COMENTARIO = "comentario_satisfacao_recebido"
EVENTO_RECUSA = "comentario_satisfacao_recusado"


class ComentarioFinalizacaoTests(unittest.TestCase):
    def test_comentario_livre_avanca_sem_classificar_conteudo(self):
        for texto in (
            "ok",
            "sim",
            "beleza",
            "🧡",
            "???",
            "Quanto custa?",
            "É reforço escolar?",
            "  Não gostei.\nFoi demorado!  ",
        ):
            for dependente in (False, True):
                with self.subTest(texto=texto, dependente=dependente):
                    contexto = contexto_resposta(
                        21, texto, {EVENTO_COMENTARIO: 22}, dependente=dependente
                    )
                    wa = cliente_simulado()
                    with patch.object(cliente, "WhatsApp", return_value=wa):
                        envio = flow_sender(contexto)
                    wa.send_message.assert_called_once()
                    self.assertEqual(envio["id_etapa_resultante"], 22)
                    self.assertEqual(envio["evento_transicao"], EVENTO_COMENTARIO)
                    self.assertEqual(envio["comentario_satisfacao"], texto.strip())
                    self.assertFalse(envio.get("tratamento", False))
                    self.assertEqual(
                        envio["mensagem_bot"], wa.send_message.call_args.kwargs["text"]
                    )

    def test_dois_caminhos_de_finalizacao_buscam_participante_no_banco(self):
        momento = datetime(2026, 9, 22, 10, tzinfo=timezone.utc)
        for origem, texto, evento in (
            (20, "Prefiro não comentar", EVENTO_RECUSA),
            (21, "Gostei", EVENTO_COMENTARIO),
        ):
            for dependente in (False, True):
                for prefixo in (None, "Olá novamente, Maria!\n\n"):
                    with self.subTest(
                        origem=origem, dependente=dependente, prefixo=prefixo
                    ), ExitStack() as pilha:
                        # O nome vem desta conversa, inclusive quando não houve comentário.
                        cursor = FakeCursor(fetchone_result=(dependente, "  João  "))
                        retornos = {
                            "inserir_historico_mensagem_cliente": (
                                100,
                                momento,
                                origem,
                                True,
                            ),
                            "buscar_resposta_bot_por_mensagem_cliente": None,
                            "buscar_contexto_saudacao_retorno": ("Maria", None),
                            "montar_saudacao_retorno": prefixo,
                            "listar_transicoes_permitidas": {evento: 22},
                            "atualizar_conversa_mensagem_cliente": None,
                        }
                        for nome, retorno in retornos.items():
                            pilha.enter_context(
                                patch.object(historico, nome, return_value=retorno)
                            )
                        contexto = historico.valida_historico(
                            {
                                "id_mensagem": 10,
                                "id_hash": "wamid.entrada",
                                "retry_count": 0,
                                "conteudo_texto": texto,
                                "tipo_mensagem": "text",
                                "cliente_telefone": "5511999999999",
                                "id_phone_unidade": "phone",
                                "unidade_telefone": "5511888888888",
                            },
                            {
                                "id_cliente": 5,
                                "id_unidade": 2,
                                "conversa": {
                                    "id_conversa": 1,
                                    "id_etapa_atual": origem,
                                    "status_dependente": dependente,
                                    "last_message_from": "bot",
                                },
                            },
                            cursor,
                        )
                        self.assertEqual(cursor.calls[0][1], (1, 2))
                        self.assertIn("c.id_unidade = %s", cursor.calls[0][0])
                        wa = cliente_simulado()
                        pilha.enter_context(
                            patch.object(cliente, "WhatsApp", return_value=wa)
                        )
                        envio = flow_sender(contexto)
                        despedida = envio["mensagem_bot"]
                        self.assertIn(
                            "receber você e João" if dependente else "te receber",
                            despedida,
                        )
                        self.assertEqual("João" in despedida, dependente)
                        self.assertNotIn("{nome_dependente}", despedida)
                        self.assertEqual(
                            despedida.count("Olá novamente"), int(bool(prefixo))
                        )
                        self.assertEqual(
                            despedida, wa.send_message.call_args.kwargs["text"]
                        )
                        self.assertEqual(envio["id_etapa_resultante"], 22)
                        self.assertEqual(envio["evento_transicao"], evento)
                        wa.send_message.assert_called_once()

    def test_retry_persiste_mesmo_comentario_ou_nulo(self):
        for tipo, texto, esperado in (
            ("text", "ok", "ok"),
            ("text", "sim", "sim"),
            ("text", "🧡", "🧡"),
            ("text", "???", "???"),
            ("text", "Prefiro não comentar", None),
            ("text", "   ", None),
            ("interactive", "Sim, quero comentar", None),
            ("button", "Prefiro não comentar", None),
        ):
            with self.subTest(tipo=tipo, texto=texto):
                contexto = contexto_resposta(21, texto, {EVENTO_COMENTARIO: 22})
                contexto["tipo_mensagem_atual"] = tipo
                wa = cliente_simulado()
                with patch.object(cliente, "WhatsApp", return_value=wa):
                    envio = flow_sender(contexto)
                self.assertEqual(envio["id_etapa_resultante"], 22)
                self.assertEqual(envio["comentario_satisfacao"], esperado)
                retry = dict(envio, resposta_ja_existia=True)
                del retry["comentario_satisfacao"]
                cursor = object()
                for resultado in (envio, retry):
                    with patch.object(
                        efeitos_transicao,
                        "salvar_comentario_satisfacao",
                        return_value={"inserido": False},
                    ) as salvar:
                        efeitos_transicao.atualizar_banco_conforme_transicao_de_etapa(
                            contexto, resultado, cursor
                        )
                    salvar.assert_called_once_with(1, esperado, cursor)

    def test_midia_continua_pedindo_comentario_em_texto(self):
        for tipo in ("image", "audio", "video", "document", "sticker"):
            contexto = contexto_resposta(21, "", {EVENTO_COMENTARIO: 22})
            contexto["tipo_mensagem_atual"] = tipo
            wa = cliente_simulado()
            with self.subTest(tipo=tipo), patch.object(
                cliente, "WhatsApp", return_value=wa
            ):
                envio = flow_sender(contexto)
                self.assertEqual(envio["id_etapa_resultante"], 21)
                self.assertEqual(
                    envio["tipo_tratamento"], "tipo_mensagem_nao_suportado"
                )
                self.assertNotIn("evento_transicao", envio)

    def test_dependente_sem_nome_nao_recebe_despedida_de_titular(self):
        for resultado in (None, (None, None), (True, None), (True, " ")):
            with self.subTest(resultado=resultado), self.assertRaises(ValueError):
                buscar_contexto_etapa22(1, 2, FakeCursor(fetchone_result=resultado))
        with patch.object(etapa22, "conta_wa") as conta:
            with self.assertRaises(ValueError):
                etapa22.enviar_etapa22("5511999999999", "phone", status_dependente=True)
            conta.assert_not_called()

    def test_transicao_ausente_nao_envia_encerramento(self):
        contexto = contexto_resposta(21, "ok", {})
        wa = cliente_simulado()
        with patch.object(cliente, "WhatsApp", return_value=wa), self.assertRaises(
            ValueError
        ):
            flow_sender(contexto)
        wa.send_message.assert_not_called()
