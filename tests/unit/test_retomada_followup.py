"""Retornos passam pelos validadores/senders reais; nenhum envio externo é feito."""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from core.integrations.whatsapp.pywa_functions import cliente
from tests.unit import test_followup as fixtures
from workers.worker_flow.response_flow.flow_sender import flow_sender
from workers.worker_flow.response_flow.retomada_followup import enviar_retorno_followup
from workers.worker_flow.transacoes import persistencia_resposta as persistencia


class RetomadaValidadaTests(unittest.TestCase):
    def preparar(self, etapa, texto, dependente=False, tipo="text"):
        contexto, _ = fixtures.RetornoTests().preparar(
            etapa=etapa, texto=texto, dependente=dependente, tipo=tipo
        )
        return contexto

    def enviar(self, contexto, *, normal=False):
        fake = MagicMock()
        fake.send_message.return_value = SimpleNamespace(id="wamid.resposta")
        with patch.object(cliente, "WhatsApp", return_value=fake):
            envio = (
                flow_sender(contexto) if normal else enviar_retorno_followup(contexto)
            )
        fake.send_message.assert_called_once()
        texto_enviado = fake.send_message.call_args.kwargs["text"]
        self.assertEqual(envio["mensagem_bot"], texto_enviado)
        self.assertEqual(texto_enviado.count("Bom te ver novamente"), 1)
        self.assertNotIn("Que bom te ver novamente", texto_enviado)
        if contexto["id_etapa_atual"] == 1:
            self.assertTrue(texto_enviado.startswith("Bom te ver novamente ☺️\n"))
        else:
            self.assertTrue(texto_enviado.startswith("Bom te ver novamente, Ana ☺️\n"))
        return envio, fake.send_message.call_args.kwargs

    def test_respostas_validas_avancam_e_preservam_dados_das_duas_rotas(self):
        casos = [
            (1, "Antonia", 2),
            (2, "Para mim", 3),
            (3, "Sim", 4),
            (4, "Professora", None),
            (5, "Pedro", 6),
            (6, "35", 7),
            (7, "Reservar agora", 10),
            (7, "Quero reservar", 10),
            (7, "Talvez mais tarde", 8),
            (8, "Quero reservar", 9),
            (8, "Reservar agora", 9),
            (9, "Reservar agora", 10),
            (9, "Quero reservar", 10),
            (9, "Talvez mais tarde", 8),
            (10, "ana@example.com", 11),
            (11, "Começar triagem", 12),
            *((etapa, "Às vezes", etapa + 1) for etapa in range(12, 18)),
            (18, "Já agendei", 19),
            (19, "5", 20),
            (20, "Sim", 21),
            (20, "Não", 22),
            (21, "Gostei do atendimento", 22),
        ]
        for dependente in (False, True):
            for etapa, texto, destino in casos:
                with self.subTest(etapa=etapa, texto=texto, dependente=dependente):
                    cx = self.preparar(etapa, texto, dependente)
                    envio, _ = self.enviar(cx)
                    esperado = (5 if dependente else 6) if etapa == 4 else destino
                    self.assertEqual(envio["id_etapa_resultante"], esperado)
                    self.assertTrue(envio.get("evento_transicao"))
                    self.assertFalse(envio.get("tratamento", False))
                    if etapa == 1:
                        self.assertEqual(envio["primeiro_nome_cliente"], "Antonia")
                        self.assertNotIn("Ana", envio["mensagem_bot"])
                    if etapa == 5:
                        self.assertEqual(envio["primeiro_nome_dependente"], "Pedro")
                    if 12 <= etapa <= 17:
                        self.assertEqual(envio["resposta_triagem"], "às vezes")

    def test_resposta_sem_contexto_repete_neutra_com_botoes_e_rodape(self):
        for dependente in (False, True):
            for etapa in (*range(1, 8), *range(9, 21)):
                with self.subTest(etapa=etapa, dependente=dependente):
                    cx = self.preparar(etapa, "???", dependente)
                    envio, payload = self.enviar(cx)
                    self.assertEqual(envio["id_etapa_resultante"], etapa)
                    self.assertFalse(envio.get("tratamento", False))
                    self.assertNotIn("evento_transicao", envio)
                    self.assertNotIn("não consegui entender", envio["mensagem_bot"])
                    if etapa in (2, 3, 7, 9, 11, *range(12, 18), 19, 20):
                        self.assertTrue(payload.get("buttons"))
                    if etapa in (2, 3, 7, 9, *range(12, 18)):
                        self.assertTrue(
                            payload.get("footer")
                            or "_Selecione apenas uma opção" in envio["mensagem_bot"]
                        )
                    if etapa == 2:
                        self.assertNotIn("Prazer", envio["mensagem_bot"])
                    if dependente and etapa in (6, 7, 9, 11, *range(12, 18), 18):
                        self.assertIn("Bia", envio["mensagem_bot"])

    def test_tratamentos_especificos_preservam_prioridades(self):
        for dependente in (False, True):
            for etapa in (*range(1, 8), 9, 10, 11, 18):
                for tipo, texto, tratamento in (
                    ("image", "Quanto custa?", "tipo_mensagem_nao_suportado"),
                    ("text", "Quanto custa o curso?", "pergunta_financeira"),
                    (
                        "text",
                        "Vocês oferecem reforço escolar?",
                        "duvida_reforco_escolar",
                    ),
                ):
                    with self.subTest(
                        etapa=etapa, dependente=dependente, tratamento=tratamento
                    ):
                        envio, _ = self.enviar(
                            self.preparar(etapa, texto, dependente, tipo)
                        )
                        self.assertEqual(envio["id_etapa_resultante"], etapa)
                        self.assertEqual(envio["tipo_tratamento"], tratamento)
                        self.assertTrue(envio["tratamento"])

    def test_continuar_nao_vira_nome_e_triagem_nao_ganha_tratamentos(self):
        envio, _ = self.enviar(self.preparar(1, "Quero continuar"))
        self.assertEqual(envio["id_etapa_resultante"], 1)
        self.assertNotIn("primeiro_nome_cliente", envio)
        for tipo, texto in (("image", ""), ("text", "Quanto custa?")):
            envio, _ = self.enviar(self.preparar(12, texto, True, tipo))
            self.assertEqual(envio["id_etapa_resultante"], 12)
            self.assertFalse(envio.get("tratamento", False))

    def test_inatividade_segue_contexto_invalido_normal(self):
        cx = self.preparar(6, "???", True)
        cx.pop("retorno_followup")
        cx["saudacao_retorno"] = "Bom te ver novamente, Ana ☺️\n"
        envio, _ = self.enviar(cx, normal=True)
        self.assertTrue(envio["tratamento"])
        self.assertEqual(envio["tipo_tratamento"], "idade_invalida")
        self.assertIn("não consegui entender", envio["mensagem_bot"])

    def test_idade_preserva_encerramentos_e_excecao_configurada(self):
        for dependente, idade, limite, encerra in (
            (False, "17", None, True),
            (True, "3", None, True),
            (False, "100", None, True),
            (True, "100", None, True),
            (False, "70", 70, True),
            (True, "70", 70, False),
        ):
            with self.subTest(dependente=dependente, idade=idade, limite=limite):
                cx = self.preparar(6, idade, dependente)
                cx["idade_minima_suporte"] = limite
                envio, _ = self.enviar(cx)
                self.assertEqual(bool(envio.get("encerrar_atendimento")), encerra)
                self.assertEqual(envio["idade_aluno"], int(idade))
                self.assertEqual(envio["id_etapa_resultante"], 6 if encerra else 7)

    def test_confirmacao_negativa_altera_destino_uma_unica_vez(self):
        for dependente in (False, True):
            envio, _ = self.enviar(self.preparar(3, "Não", dependente))
            self.assertEqual(envio["status_dependente_final"], not dependente)
            self.assertEqual(envio["id_etapa_resultante"], 4)

    def test_contador_isenta_primeira_reacao_e_conta_proximo_tratamento(self):
        with patch.object(
            persistencia, "incrementar_turnos_sem_avanco", return_value=12
        ) as incrementar, patch.object(
            persistencia, "resetar_turnos_sem_avanco", return_value=0
        ) as resetar:
            for tratamento in (False, True):
                persistencia._persistir_turnos_sem_avanco(
                    id_conversa=1,
                    movimento="sem_avanco",
                    tratamento=tratamento,
                    historico_bot_inserido=True,
                    cursor=None,
                    retorno_followup=True,
                )
            incrementar.assert_not_called()
            resetar.assert_not_called()
            self.assertEqual(
                persistencia._persistir_turnos_sem_avanco(
                    id_conversa=1,
                    movimento="sem_avanco",
                    tratamento=True,
                    historico_bot_inserido=True,
                    cursor=None,
                ),
                12,
            )
            self.assertEqual(
                persistencia._persistir_turnos_sem_avanco(
                    id_conversa=1,
                    movimento="transicao",
                    tratamento=False,
                    historico_bot_inserido=True,
                    cursor=None,
                    retorno_followup=True,
                ),
                0,
            )
