"""Contexto inválido orienta sozinho, preservando rota e componentes do envio."""

import importlib
import inspect
import unittest
from contextlib import ExitStack
from unittest.mock import patch

from core.integrations.whatsapp.messages import etapa6_messages, etapa20_messages
from core.integrations.whatsapp.pywa_functions import cliente
from tests.unit.test_mensagens_reserva import cliente_simulado, contexto_resposta
from workers.worker_flow.response_flow.flow_sender import flow_sender


class MensagensContextoTests(unittest.TestCase):
    def test_contextos_nao_dependem_dos_montadores_ou_textos_de_repeticao(self):
        valores = {
            "nome": "Lucas",
            "nome_dependente": "Lucas",
            "idade_dependente": 10,
            "link_agendamento": "https://example.com/reservar",
        }
        for etapa in range(1, 25):
            modulo = importlib.import_module(
                f"core.integrations.whatsapp.messages.etapa{etapa}_messages"
            )
            montadores = [
                (nome, montar)
                for nome, montar in inspect.getmembers(modulo, inspect.isfunction)
                if nome.startswith("montar_mensagem_") and "contexto" in nome
            ]
            with ExitStack() as pilha:
                for nome in vars(modulo):
                    if nome.startswith("MENSAGEM_REPETICAO"):
                        pilha.enter_context(
                            patch.object(modulo, nome, "REPETICAO_INDEVIDA")
                        )
                    elif (
                        nome == "compor_tratamento"
                        or (
                            nome.startswith("montar_mensagem_")
                            and "contexto" not in nome
                        )
                        or nome in ("_montar_repeticao", "montar_pergunta_triagem")
                    ):
                        pilha.enter_context(
                            patch.object(
                                modulo,
                                nome,
                                side_effect=AssertionError("Repetição no contexto"),
                            )
                        )
                for nome, montar in montadores:
                    for dependente in (False, True):
                        with self.subTest(
                            etapa=etapa, nome=nome, dependente=dependente
                        ):
                            argumentos = dict(valores, status_dependente=dependente)
                            texto = montar(
                                **{
                                    chave: argumentos[chave]
                                    for chave in inspect.signature(montar).parameters
                                }
                            )
                            self.assertTrue(texto.strip())
                            self.assertNotIn("REPETICAO_INDEVIDA", texto)
                            self.assertNotIn("{nome", texto)

    def test_idade_pede_o_numero_uma_vez_e_preserva_participante(self):
        titular = etapa6_messages.montar_mensagem_contexto_idade_invalida_etapa6()
        dependente = (
            etapa6_messages.montar_mensagem_contexto_idade_dependente_invalida_etapa6(
                "Lucas"
            )
        )
        for texto in (titular, dependente):
            self.assertEqual(texto.count("idade"), 1)
            self.assertEqual(texto.count("Digite"), 1)
            self.assertNotIn("Me diz", texto)
        self.assertIn("sua idade", titular)
        self.assertIn("idade de Lucas", dependente)

    def test_fluxo_preserva_etapa_botoes_rodape_e_prefixo_unico(self):
        for etapa in (6, 7, *range(12, 18), 20, 21):
            for dependente in (False, True):
                for prefixo in (None, "Olá novamente, Maria!\n\n"):
                    with self.subTest(
                        etapa=etapa, dependente=dependente, prefixo=prefixo
                    ):
                        contexto = contexto_resposta(
                            etapa, "???", {}, dependente=dependente
                        )
                        contexto.update(
                            idade_pessoa_triagem=10 if dependente else 35,
                            link_agendamento_unidade="https://example.com/reservar",
                            saudacao_retorno=prefixo,
                        )
                        wa = cliente_simulado()
                        with patch.object(cliente, "WhatsApp", return_value=wa):
                            envio = flow_sender(contexto)
                        wa.send_message.assert_called_once()
                        texto = wa.send_message.call_args.kwargs["text"]
                        self.assertTrue(envio["tratamento"])
                        self.assertEqual(envio["id_etapa_resultante"], etapa)
                        self.assertNotIn("evento_transicao", envio)
                        self.assertEqual(
                            texto.count("Olá novamente"), int(bool(prefixo))
                        )
                        self.assertEqual(
                            envio["mensagem_bot"].count("Olá novamente"),
                            int(bool(prefixo)),
                        )
                        self.assertTrue(
                            texto.endswith(
                                envio["mensagem_bot"].removeprefix(prefixo or "")
                            )
                        )
                        self.assertNotIn("Que bom te ver novamente", texto)
                        if etapa != 21:
                            self.assertEqual("Lucas" in texto, dependente)
                        if etapa != 6:
                            self.assertTrue(wa.send_message.call_args.kwargs["buttons"])
                            rodape = envio["rodape_mensagem"]
                            self.assertEqual(texto.count(rodape), 1)
                        if 12 <= etapa <= 17:
                            botoes = wa.send_message.call_args.kwargs["buttons"]
                            self.assertEqual(
                                [b.title for b in botoes],
                                ["Nunca", "Às vezes", "Frequentemente"],
                            )
                            self.assertNotIn("Com que frequência", texto)
                        if etapa == 20:
                            self.assertEqual(
                                texto.count("https://example.com/reservar"), 1
                            )

    def test_contexto_preserva_validacao_dos_dados_de_apresentacao(self):
        for etapa in range(12, 18):
            modulo = importlib.import_module(
                f"core.integrations.whatsapp.messages.etapa{etapa}_messages"
            )
            montar = getattr(
                modulo, f"montar_mensagem_dependente_contexto_invalido_etapa{etapa}"
            )
            for idade in (None, True, 0, 100):
                with self.subTest(etapa=etapa, idade=idade):
                    with self.assertRaises(ValueError):
                        montar("Lucas", idade)
            with self.assertRaises(ValueError):
                montar("", 10)
        with self.assertRaises(ValueError):
            etapa20_messages.montar_mensagem_contexto_invalido_etapa20("")
        with self.assertRaises(ValueError):
            etapa20_messages.montar_mensagem_contexto_invalido_etapa20(
                "https://example.com", ""
            )
