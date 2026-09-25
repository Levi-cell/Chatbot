"""A introdução, os tratamentos e os retornos preservam a pessoa da triagem."""

import unittest
from unittest.mock import MagicMock, patch

from core.integrations.whatsapp.messages import etapa11_messages as mensagens
from core.integrations.whatsapp.messages.componentes_compartilhados import (
    CABECALHO_ETAPA11_TRIAGEM,
)
from core.integrations.whatsapp.pywa_functions import cliente
from core.integrations.whatsapp.pywa_functions.pywa_senders import etapa11
from core.repositories.fluxo.contextos.etapa10 import buscar_contexto_etapa10
from tests.unit.test_followup import contexto as contexto_followup
from tests.unit.test_mensagens_reserva import cliente_simulado, contexto_resposta
from workers.worker_flow.response_flow.flow_sender import flow_sender
from workers.worker_flow.response_flow.repeticao_followup import (
    enviar_repeticao_followup,
)


class MensagensEtapa11Tests(unittest.TestCase):
    def conferir_participante(self, texto, dependente):
        self.assertEqual("de Lucas" in texto, dependente)
        self.assertEqual("seu cérebro" in texto, not dependente)
        self.assertNotIn("{nome", texto)
        self.assertNotIn("quem participará", texto)

    def conferir_envio(self, envio, wa, dependente, prefixo):
        wa.send_message.assert_called_once()
        texto = wa.send_message.call_args.kwargs["text"]
        self.conferir_participante(texto, dependente)
        self.assertIn(envio["mensagem_bot"].removeprefix(prefixo), texto)
        self.assertEqual(texto.count(CABECALHO_ETAPA11_TRIAGEM), 1)
        if prefixo:
            self.assertEqual(texto.count(prefixo.strip()), 1)
        else:
            self.assertNotIn("Olá novamente", texto)
            self.assertNotIn("Que bom te ver novamente", texto)
        self.assertEqual(
            [botao.title for botao in wa.send_message.call_args.kwargs["buttons"]],
            ["Começar triagem"],
        )
        self.assertEqual(envio["id_etapa_resultante"], 11)
        return texto

    def test_entrada_10_11_recebe_nome_do_banco_e_preserva_email_e_rota(self):
        for dependente in (False, True):
            for prefixo in ("", "Olá novamente, Maria!\n\n"):
                with self.subTest(dependente=dependente, prefixo=prefixo):
                    cursor = MagicMock()
                    cursor.fetchone.return_value = (
                        True,
                        dependente,
                        35,
                        " Lucas " if dependente else None,
                    )
                    dados = buscar_contexto_etapa10(1, 2, cursor)
                    self.assertEqual(
                        dados.pop("status_dependente_contexto_email"), dependente
                    )
                    self.assertEqual(
                        dados["nome_dependente"], "Lucas" if dependente else None
                    )
                    cx = contexto_resposta(
                        10,
                        "maria@example.com",
                        {"email_valido": 11},
                        dependente=dependente,
                    )
                    cx.pop("nome_dependente")  # Deve vir da consulta, não da fixture.
                    cx.update(dados, saudacao_retorno=prefixo)
                    wa = cliente_simulado()
                    with patch.object(cliente, "WhatsApp", return_value=wa):
                        envio = flow_sender(cx)
                    texto = self.conferir_envio(envio, wa, dependente, prefixo)
                    self.assertIn("*triagem com 6 perguntas rápidas*", texto)
                    self.assertIn("experiência personalizada, vamos começar?", texto)
                    self.assertEqual(envio["evento_transicao"], "email_valido")
                    self.assertEqual(envio["email_cliente"], "maria@example.com")

    def test_tratamentos_e_inatividade_preservam_rota_sem_repetir_apresentacao(self):
        casos = (
            ("???", "text", "confirmacao_triagem_invalida"),
            ("Quanto custa?", "text", "pergunta_financeira"),
            ("É reforço escolar?", "text", "duvida_reforco_escolar"),
            ("", "image", "tipo_mensagem_nao_suportado"),
        )
        for dependente in (False, True):
            for prefixo in ("", "Olá novamente, Maria!\n\n"):
                for entrada, tipo, tratamento in casos:
                    with self.subTest(
                        dependente=dependente, prefixo=prefixo, tratamento=tratamento
                    ):
                        cx = contexto_resposta(11, entrada, {}, dependente=dependente)
                        cx.update(
                            idade_pessoa_triagem=10 if dependente else 35,
                            saudacao_retorno=prefixo,
                            tipo_mensagem_atual=tipo,
                        )
                        wa = cliente_simulado()
                        with patch.object(cliente, "WhatsApp", return_value=wa):
                            envio = flow_sender(cx)
                        texto = self.conferir_envio(envio, wa, dependente, prefixo)
                        self.assertNotIn("antes de prosseguir", texto)
                        self.assertEqual(texto.lower().count("vamos iniciar"), 1)
                        self.assertEqual(envio["tipo_tratamento"], tratamento)
                        self.assertNotIn("evento_transicao", envio)
                        if tratamento == "confirmacao_triagem_invalida":
                            self.assertIn("Olha, não consegui entender", texto)
                            self.assertEqual(texto.count("saúde"), 1)

    def test_repeticao_neutra_followup_preserva_pessoa_da_triagem(self):
        for dependente in (False, True):
            with self.subTest(dependente=dependente):
                cx = contexto_followup()
                cx["dados_repeticao"].update(
                    status_dependente=dependente, nome_dependente="Lucas"
                )
                cx["mensagem_cliente_atual"]["conteudo_texto"] = "???"
                wa = cliente_simulado()
                with patch.object(cliente, "WhatsApp", return_value=wa):
                    envio = enviar_repeticao_followup(cx)
                texto = self.conferir_envio(
                    envio, wa, dependente, "Bom te ver novamente, Ana ☺️\n"
                )
                self.assertEqual(envio["mensagem_bot"], texto)
                self.assertNotIn("antes de prosseguir", texto)
                self.assertNotIn("Olha, não consegui entender", texto)
                self.assertNotIn("evento_transicao", envio)
                self.assertNotIn("tratamento", envio)

    def test_dependente_sem_nome_nao_vira_titular_nem_chega_a_meta(self):
        for nome in (None, "", "   ", 123):
            with self.subTest(nome=nome):
                cursor = MagicMock()
                cursor.fetchone.return_value = (True, True, 35, nome)
                with self.assertRaises(ValueError):
                    buscar_contexto_etapa10(1, 2, cursor)
                for enviar in (
                    etapa11.enviar_etapa11,
                    etapa11.enviar_etapa11_midia,
                    etapa11.enviar_etapa11_financeiro,
                    etapa11.enviar_etapa11_reforco_escolar,
                    etapa11.enviar_etapa11_contexto_invalido,
                ):
                    with patch.object(cliente, "WhatsApp") as wa:
                        with self.assertRaises(ValueError):
                            enviar(
                                "cliente",
                                "unidade",
                                status_dependente=True,
                                nome_dependente=nome,
                            )
                        wa.assert_not_called()

    def test_contexto_e_autonomo_e_titular_ignora_nome_de_dependente_antigo(self):
        with patch.object(
            mensagens,
            "montar_mensagem_triagem_cognitiva_etapa11",
            side_effect=AssertionError("Contexto não concatena repetição"),
        ):
            for dependente in (False, True):
                texto = mensagens.montar_mensagem_contexto_invalido_etapa11(
                    status_dependente=dependente, nome_dependente="Lucas"
                )
                self.conferir_participante(texto, dependente)
                self.assertEqual(texto.count("?"), 1)

    def test_confirmacao_avanca_e_as_seis_perguntas_conservam_participante(self):
        for dependente, idade in ((False, 35), (True, 10), (True, 65)):
            for destino in range(12, 18):
                with self.subTest(dependente=dependente, idade=idade, destino=destino):
                    origem = destino - 1
                    evento = (
                        "triagem_iniciada"
                        if origem == 11
                        else f"triagem_pergunta_{origem - 11}_respondida"
                    )
                    cx = contexto_resposta(
                        origem,
                        "Começar triagem" if origem == 11 else "Nunca",
                        {evento: destino},
                        dependente=dependente,
                    )
                    cx["idade_pessoa_triagem"] = idade
                    wa = cliente_simulado()
                    with patch.object(cliente, "WhatsApp", return_value=wa):
                        envio = flow_sender(cx)
                    texto = wa.send_message.call_args.kwargs["text"]
                    self.assertIn(
                        (
                            "Com que frequência Lucas"
                            if dependente
                            else "Com que frequência você"
                        ),
                        texto,
                    )
                    self.assertEqual(envio["id_etapa_resultante"], destino)
                    self.assertEqual(envio["evento_transicao"], evento)

                    retorno = contexto_followup()
                    retorno["id_etapa_atual"] = destino
                    retorno["dados_repeticao"].update(
                        status_dependente=dependente,
                        nome_dependente="Lucas",
                        idade_dependente=idade,
                    )
                    wa = cliente_simulado()
                    with patch.object(cliente, "WhatsApp", return_value=wa):
                        repeticao = enviar_repeticao_followup(retorno)
                    self.assertIn(
                        (
                            "Com que frequência Lucas"
                            if dependente
                            else "Com que frequência você"
                        ),
                        repeticao["mensagem_bot"],
                    )
                    self.assertEqual(repeticao["id_etapa_resultante"], destino)
                    self.assertNotIn("evento_transicao", repeticao)
