import unittest
from contextlib import ExitStack
from datetime import datetime, timezone
from threading import Event
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from core.repositories.atendimento import followup as repo
from core.integrations.whatsapp.messages.followup_messages import (
    MENSAGEM_FOLLOWUP,
    montar_mensagem_followup,
    montar_mensagem_encerramento_followup,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders import followup as sender
from workers.worker_followup import followup_worker as worker
from workers.worker_flow.response_flow import repeticao_followup as repeticao
from workers.worker_flow.transacoes import retorno_followup as retorno
from workers.worker_flow import valida_historico as historico
from core.database.deploy_database.etapa_transicao_script import TRANSICOES_INICIAIS

AGORA = datetime(2026, 9, 7, 12, tzinfo=timezone.utc)


def banco(stage=1):
    return {
        "id_cliente": 2,
        "id_unidade": 3,
        "conversa": {
            "id_conversa": 1,
            "id_etapa_atual": 11,
            "status_ativa": True,
            "status_dependente": False,
            "followup_stage": stage,
            "followup_last_sent_at": AGORA,
            "lock_version": 4,
        },
    }


def mensagem(tipo="text"):
    return {
        "id_mensagem": 5,
        "id_hash": "wamid.entrada",
        "cliente_telefone": "5511999999999",
        "id_phone_unidade": "123456",
        "unidade_telefone": "5511888888888",
        "conteudo_texto": "Começar triagem",
        "tipo_mensagem": tipo,
        "received_data_hora": AGORA,
        "retry_count": 1,
    }


def dados():
    return {
        "nome_titular": "Ana",
        "turno": "tarde",
        "numero_comercial": "5511999990000",
        "nome_dependente": "Bia",
        "idade_dependente": 12,
        "nome_unidade": "Unidade Teste",
        "nome_agente": "Suh",
        "genero": "feminino",
        "link_agendamento": "https://example.com/agendar",
        "link_instagram": "https://example.com/rede",
        "link_instagram_unidade": "https://example.com/rede",
        "link_agendamento_unidade": "https://example.com/agendar",
        "status_dependente": False,
        "idade_cliente": 35,
        "idade_minima_suporte": None,
        "bpa_ativo_unidade": False,
        "numero_comercial_unidade": "5511999990000",
        "genero_agente_unidade": "feminino",
    }


def contexto():
    return {
        "id_conversa": 1,
        "id_unidade": 3,
        "id_etapa_atual": 11,
        "lock_version": 4,
        "stage_anterior": 1,
        "followup_em": AGORA,
        "dados_repeticao": dados(),
        "mensagem_cliente_atual": {
            "id_mensagem_fila": 5,
            "id_hash_msg": "wamid.entrada",
            "cliente_telefone": "5511999999999",
            "id_phone_unidade": "123456",
        },
        "resposta_bot_para_mensagem_atual": None,
    }


def candidato():
    return {
        "id_conversa": 1,
        "id_cliente": 2,
        "id_unidade": 3,
        "id_etapa": 11,
        "cliente_telefone": "5511999999999",
        "id_phone_unidade": "123456",
        "unidade_telefone": "5511888888888",
        "id_ancora": 8,
        "ancora_em": AGORA,
        "followup_stage": 0,
        "nome_titular": "Ana",
        "nome_dependente": "Bia",
        "status_dependente": False,
        "nome_agente": "Suh",
    }


class RetornoTests(unittest.TestCase):
    def preparar(
        self,
        stage=1,
        tipo="text",
        retomada=None,
        resposta=None,
        enviado_em=AGORA,
        etapa=11,
        dependente=False,
        texto=None,
    ):
        with ExitStack() as stack:
            mocks = {}
            dados_etapa = dict(dados(), status_dependente=dependente)
            valores = {
                "buscar_retomada": retomada,
                "buscar_resposta_bot_por_mensagem_cliente": resposta,
                "buscar_contexto_repeticao": dados_etapa,
                "registrar_retomada": None,
                "inserir_historico_mensagem_cliente": (
                    6,
                    AGORA,
                    (retomada or {}).get("id_etapa", etapa),
                    not bool(resposta),
                ),
            }
            for nome, valor in valores.items():
                mocks[nome] = stack.enter_context(
                    patch.object(retorno, nome, return_value=valor)
                )
            valores_historico = {
                "inserir_historico_mensagem_cliente": valores[
                    "inserir_historico_mensagem_cliente"
                ],
                "buscar_resposta_bot_por_mensagem_cliente": None,
                "atualizar_conversa_mensagem_cliente": None,
                "buscar_contexto_saudacao_retorno": ("Ana", AGORA),
                "listar_transicoes_permitidas": {
                    evento: destino
                    for origem, evento, destino in TRANSICOES_INICIAIS
                    if origem == etapa
                },
                **{
                    f"buscar_contexto_etapa{n}": dict(dados_etapa)
                    for n in (6, 7, 9, 20)
                },
                "buscar_contexto_etapa10": dict(
                    dados_etapa,
                    status_dependente_contexto_email=dependente,
                    email_obrigatorio=False,
                ),
                "buscar_contexto_etapa18": dict(dados_etapa, status_dependente_reserva=dependente),
                "buscar_contexto_etapa24": dict(
                    dados_etapa, status_dependente_contexto_finalizacao=dependente
                ),
                "buscar_contexto_triagem": dict(
                    dados_etapa,
                    status_dependente_contexto_triagem=dependente,
                    idade_pessoa_triagem=12 if dependente else 35,
                ),
            }
            for nome, valor in valores_historico.items():
                mocks[nome] = stack.enter_context(
                    patch.object(historico, nome, return_value=valor)
                )
            cx_banco = banco(stage)
            cx_banco["conversa"]["status_dependente"] = dependente
            cx_banco["conversa"]["id_etapa_atual"] = etapa
            cx_banco["conversa"]["followup_last_sent_at"] = enviado_em
            msg = mensagem(tipo)
            if texto is not None:
                msg["conteudo_texto"] = texto
            result = retorno.preparar_retorno_followup(msg, cx_banco, MagicMock())
        return result, mocks

    def test_zero_preserva_caminho_normal(self):
        result, mocks = self.preparar(stage=0)
        self.assertIsNone(result)
        mocks["inserir_historico_mensagem_cliente"].assert_not_called()

    def test_reacoes_carregam_contexto_normal_sem_saudacao_de_tres_horas(self):
        for stage in (1, 2, 3, 9):
            for tipo in ("text", "interactive", "image", "audio", "unsupported"):
                with self.subTest(stage=stage, tipo=tipo):
                    result, mocks = self.preparar(stage=stage, tipo=tipo)
                    self.assertEqual(result["id_etapa_resposta"], 12)
                    self.assertTrue(result["retorno_followup"])
                    self.assertEqual(
                        result["transicoes_permitidas"], {"triagem_iniciada": 12}
                    )
                    self.assertIsNone(result["saudacao_retorno"])
                    mocks["buscar_contexto_saudacao_retorno"].assert_not_called()
                    self.assertEqual(
                        result["mensagem_cliente_atual"]["tipo_mensagem"], tipo
                    )
                    mocks["registrar_retomada"].assert_called_once()

    def test_stage_negativo_falha(self):
        with self.assertRaises(ValueError):
            self.preparar(stage=-1)

    def test_legado_com_stage_positivo_sem_data_de_envio_reapresenta_etapa(self):
        result, mocks = self.preparar(enviado_em=None)
        self.assertTrue(result["retorno_followup"])
        self.assertIsNone(result["followup_em"])
        self.assertEqual(result["id_etapa_resposta"], 12)
        mocks["registrar_retomada"].assert_called_once()

    def test_retry_nao_zera_ciclo_posterior(self):
        registro = {
            "id_etapa": 11,
            "stage_anterior": 1,
            "followup_em": AGORA,
            "concluida_em": AGORA,
        }
        resposta = (
            7,
            1,
            11,
            AGORA,
            "",
            "",
            "",
            "wamid.bot",
            5,
            "",
            "",
            "",
            "bot",
            "sent",
        )
        result, mocks = self.preparar(stage=1, retomada=registro, resposta=resposta)
        mocks["buscar_contexto_repeticao"].assert_not_called()
        mocks["atualizar_conversa_mensagem_cliente"].assert_not_called()
        with patch.object(retorno, "concluir_retomada") as concluir, patch.object(
            retorno, "atualizar_banco_com_contexto_final"
        ) as inserir:
            final = retorno.persistir_retorno_followup(
                result, {"id_hash_msg_bot": "wamid.bot"}, MagicMock()
            )
        concluir.assert_not_called()
        inserir.assert_not_called()
        self.assertIsNone(final["intencao_encerramento"])

    def test_resposta_normal_existente_tem_prioridade(self):
        result, mocks = self.preparar(resposta=(1,))
        self.assertIsNone(result)
        mocks["registrar_retomada"].assert_not_called()

    def test_concluida_sem_historico_nao_reenvia(self):
        with self.assertRaises(ValueError):
            self.preparar(stage=0, retomada={"concluida_em": AGORA})

    def test_retorno_so_reseta_apos_historico(self):
        eventos = []
        envio = {
            "enviou": True,
            "id_etapa_resultante": 11,
            "id_hash_msg_bot": "wamid.bot",
        }
        with patch.object(
            retorno,
            "atualizar_banco_com_contexto_final",
            side_effect=lambda *_: eventos.append("historico")
            or {
                "data_historico_bot": AGORA,
                "id_etapa_resultante": 11,
                "intencao_encerramento": None,
            },
        ), patch.object(
            retorno,
            "concluir_retomada",
            side_effect=lambda *_, **kw: eventos.append("reset"),
        ):
            final = retorno.persistir_retorno_followup(contexto(), envio, MagicMock())
        self.assertEqual(eventos, ["historico", "reset"])
        self.assertNotIn("turnos_sem_avanco", final)
        self.assertNotIn("efeitos_transicao", final)
        self.assertIsNone(final["intencao_encerramento"])

    def test_falha_historico_nao_chega_ao_reset(self):
        envio = {"enviou": True, "id_etapa_resultante": 11}
        with patch.object(
            retorno, "atualizar_banco_com_contexto_final", side_effect=RuntimeError
        ), patch.object(retorno, "concluir_retomada") as concluir:
            with self.assertRaises(RuntimeError):
                retorno.persistir_retorno_followup(contexto(), envio, MagicMock())
            concluir.assert_not_called()


class RepeticaoTests(unittest.TestCase):
    def test_etapa1_nao_usa_nome_de_atendimento_anterior(self):
        from core.integrations.whatsapp.pywa_functions import cliente

        for nome_antigo in ("Edcarlos", "Ana", None):
            for stage in (1, 2):
                with self.subTest(nome_antigo=nome_antigo, stage=stage):
                    cx = contexto()
                    cx["id_etapa_atual"] = 1
                    cx["stage_anterior"] = stage
                    cx["dados_repeticao"]["nome_titular"] = nome_antigo
                    cx["mensagem_cliente_atual"]["conteudo_texto"] = "Opa"
                    fake = MagicMock()
                    fake.send_message.return_value = SimpleNamespace(id="wamid.bot")
                    with patch.object(cliente, "WhatsApp", return_value=fake):
                        envio = repeticao.enviar_repeticao_followup(cx)
                    self.assertTrue(
                        envio["mensagem_bot"].startswith("Bom te ver novamente ☺️\n")
                    )
                    self.assertIn(
                        "Me diz, qual o seu primeiro nome?", envio["mensagem_bot"]
                    )
                    self.assertNotIn("assistente do", envio["mensagem_bot"])
                    if nome_antigo:
                        self.assertNotIn(nome_antigo, envio["mensagem_bot"])
                    self.assertNotIn("Opa", envio["mensagem_bot"])
                    self.assertEqual(envio["id_etapa_resultante"], 1)
                    self.assertNotIn("evento_transicao", envio)
                    self.assertEqual(cx["dados_repeticao"]["nome_titular"], nome_antigo)
                    self.assertEqual(
                        envio["mensagem_bot"],
                        fake.send_message.call_args.kwargs["text"],
                    )

    def test_todas_etapas_repetiveis_usam_senders_existentes(self):
        # Executa catálogos e senders reais; substitui somente o cliente HTTP.
        from core.integrations.whatsapp.pywa_functions import cliente

        for dependente in (False, True):
            for etapa in range(1, 24):
                if etapa == 8:
                    continue  # A exceção 8 -> 9 tem cobertura própria abaixo.
                with self.subTest(etapa=etapa, dependente=dependente):
                    cx = contexto()
                    cx["id_etapa_atual"] = etapa
                    cx["dados_repeticao"]["status_dependente"] = dependente
                    fake = MagicMock()
                    fake.send_message.return_value = SimpleNamespace(id="wamid.bot")
                    with patch.object(cliente, "WhatsApp", return_value=fake):
                        envio = repeticao.enviar_repeticao_followup(cx)
                    fake.send_message.assert_called_once()
                    self.assertEqual(envio["id_etapa_resultante"], etapa)
                    self.assertEqual(
                        envio["mensagem_bot"],
                        fake.send_message.call_args.kwargs["text"],
                    )
                    self.assertNotIn("evento_transicao", envio)
                    self.assertNotIn("tratamento", envio)
                    self.assertNotIn("Olá novamente", envio["mensagem_bot"])
                    saudacao_esperada = (
                        "Bom te ver novamente ☺️\n"
                        if etapa == 1
                        else "Bom te ver novamente, Ana ☺️\n"
                    )
                    self.assertTrue(envio["mensagem_bot"].startswith(saudacao_esperada))
                    self.assertEqual(
                        envio["mensagem_bot"].count("Bom te ver novamente"), 1
                    )

    def test_sem_nome_usa_saudacao_generica_e_preserva_texto_enviado(self):
        from core.integrations.whatsapp.pywa_functions import cliente

        for nome in (None, "", "   "):
            with self.subTest(nome=nome):
                cx = contexto()
                cx["id_etapa_atual"] = 1
                cx["dados_repeticao"]["nome_titular"] = nome
                fake = MagicMock()
                fake.send_message.return_value = SimpleNamespace(id="wamid.bot")
                with patch.object(cliente, "WhatsApp", return_value=fake):
                    with cliente.usar_prefixo_mensagem_bot(
                        "Olá novamente, Nome antigo!\n\n"
                    ):
                        envio = repeticao.enviar_repeticao_followup(cx)
                self.assertTrue(
                    envio["mensagem_bot"].startswith("Bom te ver novamente ☺️\n")
                )
                self.assertEqual(
                    envio["mensagem_bot"], fake.send_message.call_args.kwargs["text"]
                )
                self.assertNotIn("Olá novamente", envio["mensagem_bot"])

    def test_falha_sender_restaura_prefixo_anterior(self):
        from core.integrations.whatsapp.pywa_functions import cliente

        with patch.object(
            repeticao,
            "_selecionar_sender",
            return_value=(MagicMock(side_effect=RuntimeError("Meta")), ()),
        ):
            with cliente.usar_prefixo_mensagem_bot("prefixo anterior: "):
                with self.assertRaises(RuntimeError):
                    repeticao.enviar_repeticao_followup(contexto())
                self.assertEqual(
                    cliente.aplicar_prefixo_mensagem_bot("teste"),
                    "prefixo anterior: teste",
                )

    def test_retry_nao_chama_sender(self):
        for etapa in (1, 11):
            with self.subTest(etapa=etapa):
                cx = contexto()
                cx["id_etapa_atual"] = etapa
                cx["resposta_bot_para_mensagem_atual"] = {"id_hash_msg": "wamid.bot"}
                with patch.object(repeticao, "_selecionar_sender") as selecionar:
                    envio = repeticao.enviar_repeticao_followup(cx)
                selecionar.assert_not_called()
                self.assertFalse(envio["enviou"])
                self.assertEqual(envio["id_hash_msg_bot"], "wamid.bot")

    def test_nome_novo_informado_na_etapa1_prevalece_sobre_cadastro_antigo(self):
        from workers.worker_flow.response_flow.etapas import resolver_etapa1

        cx = {
            "id_conversa": 1,
            "id_etapa_atual": 1,
            "id_etapa_origem_transicao": 1,
            "nome_titular": "Edcarlos",
            "tipo_mensagem_atual": "text",
            "texto_cliente_atual": "Maria",
            "transicoes_permitidas": {"nome_cliente_valido": 2},
            "mensagem_cliente_atual": contexto()["mensagem_cliente_atual"],
        }
        with patch.object(
            resolver_etapa1,
            "enviar_etapa2",
            return_value={"enviou": True, "id_etapa_resultante": 2},
        ) as enviar:
            envio = resolver_etapa1.resolve_etapa1(cx)
        self.assertEqual(enviar.call_args.kwargs["nome_titular"], "Maria")
        self.assertEqual(envio["primeiro_nome_cliente"], "Maria")
        self.assertEqual(envio["evento_transicao"], "nome_cliente_valido")

    def test_terminal_e_dado_ausente_falham_antes_da_meta(self):
        for etapa in (None, 0, 24, 25):
            with self.assertRaises(ValueError):
                repeticao._selecionar_sender(etapa, dados())
        cx = dados()
        cx["nome_dependente"] = None
        cx["status_dependente"] = True
        with self.assertRaises(ValueError):
            repeticao._selecionar_sender(12, cx)


class RetornoEtapa8Tests(unittest.TestCase):
    def test_preparacao_preserva_origem_e_carrega_mapa(self):
        for enviado_em in (None, AGORA):
            cx, mocks = RetornoTests().preparar(etapa=8, enviado_em=enviado_em)
            self.assertEqual(cx["id_etapa_atual"], 8)
            self.assertEqual(cx["id_etapa_cliente"], 8)
            self.assertEqual(cx["id_etapa_resposta"], 9)
            self.assertEqual(cx["id_etapa_origem_transicao"], 8)
            self.assertEqual(cx["transicoes_permitidas"], {"cliente_retornou": 9})
            mocks["listar_transicoes_permitidas"].assert_called_once()
            self.assertEqual(
                mocks["inserir_historico_mensagem_cliente"].call_args.kwargs[
                    "id_etapa"
                ],
                8,
            )

    def test_qualquer_reacao_apresenta_9_sem_repetir_8_nem_consumir_aceite(self):
        from core.integrations.whatsapp.pywa_functions import cliente
        from core.integrations.whatsapp.pywa_functions.pywa_senders import etapa8

        for dependente in (False, True):
            for tipo, texto in (
                ("text", "Quero reservar"),
                ("text", "Quanto custa?"),
                ("interactive", "Talvez mais tarde"),
                ("image", ""),
                ("audio", ""),
                ("unsupported", ""),
            ):
                with self.subTest(dependente=dependente, tipo=tipo, texto=texto):
                    cx, _ = RetornoTests().preparar(etapa=8, tipo=tipo)
                    cx["dados_repeticao"]["status_dependente"] = dependente
                    cx["dados_repeticao"]["link_instagram"] = None
                    cx["mensagem_cliente_atual"]["conteudo_texto"] = texto
                    fake = MagicMock()
                    fake.send_message.return_value = SimpleNamespace(
                        id="wamid.retorno9"
                    )
                    with patch.object(
                        cliente, "WhatsApp", return_value=fake
                    ), patch.object(
                        etapa8,
                        "enviar_etapa8",
                        side_effect=AssertionError("Não repetir etapa 8"),
                    ):
                        envio = repeticao.enviar_repeticao_followup(cx)
                    self.assertEqual(envio["id_etapa_resultante"], 9)
                    self.assertEqual(envio["id_etapa_origem_transicao"], 8)
                    self.assertEqual(envio["evento_transicao"], "cliente_retornou")
                    self.assertNotIn("tratamento", envio)
                    self.assertEqual(
                        envio["mensagem_bot"].count("Bom te ver novamente"), 1
                    )
                    self.assertNotIn(
                        "Que bom ver você aqui novamente", envio["mensagem_bot"]
                    )
                    self.assertNotIn("Instagram", envio["mensagem_bot"])
                    self.assertEqual("de Bia" in envio["mensagem_bot"], dependente)
                    fake.send_message.assert_called_once()
                    self.assertEqual(
                        envio["mensagem_bot"],
                        fake.send_message.call_args.kwargs["text"],
                    )
                    self.assertEqual(
                        [
                            b.title
                            for b in fake.send_message.call_args.kwargs["buttons"]
                        ],
                        ["Reservar agora", "Talvez mais tarde"],
                    )

    def test_mapa_ausente_ou_destino_errado_recusa_antes_de_enviar(self):
        from core.integrations.whatsapp.pywa_functions import cliente

        for mapa in ({}, {"cliente_retornou": 10}):
            cx, _ = RetornoTests().preparar(etapa=8)
            cx["transicoes_permitidas"] = mapa
            with patch.object(cliente, "WhatsApp") as wa:
                with self.assertRaises(ValueError):
                    repeticao.enviar_repeticao_followup(cx)
            wa.assert_not_called()

    def test_persistencia_normal_antecede_reset_no_destino_9(self):
        cx, _ = RetornoTests().preparar(etapa=8)
        envio = {
            "enviou": True,
            "id_etapa_origem_transicao": 8,
            "evento_transicao": "cliente_retornou",
            "id_etapa_resultante": 9,
        }
        final = {"data_historico_bot": AGORA, "id_etapa_resultante": 9}
        passos = []
        with patch.object(
            retorno,
            "atualizar_banco_com_contexto_final",
            side_effect=lambda *_: passos.append("persistir") or final,
        ), patch.object(
            retorno,
            "concluir_retomada",
            side_effect=lambda *_, **kw: passos.append(("reset", kw)),
        ):
            resultado = retorno.persistir_retorno_followup(cx, envio, MagicMock())
        self.assertEqual(passos, ["persistir", ("reset", {"id_etapa_resultante": 9})])
        self.assertIs(resultado, final)
        with patch.object(
            retorno, "atualizar_banco_com_contexto_final", side_effect=RuntimeError
        ), patch.object(retorno, "concluir_retomada") as concluir:
            with self.assertRaises(RuntimeError):
                retorno.persistir_retorno_followup(cx, envio, MagicMock())
        concluir.assert_not_called()
        with patch.object(retorno, "atualizar_banco_com_contexto_final") as persistir:
            with self.assertRaises(ValueError):
                retorno.persistir_retorno_followup(
                    cx, dict(envio, id_etapa_resultante=8), MagicMock()
                )
        persistir.assert_not_called()

    def test_retry_recupera_destino_gravado_sem_reenvio_ou_reset(self):
        for destino in (8, 9):  # Inclui respostas da versão anterior ao deploy.
            registro = {
                "id_etapa": 8,
                "stage_anterior": 1,
                "followup_em": AGORA,
                "concluida_em": AGORA,
            }
            resposta = (7, 1, destino, AGORA, "", "", "", "wamid.bot")
            cx, mocks = RetornoTests().preparar(
                etapa=10, retomada=registro, resposta=resposta
            )
            mocks["listar_transicoes_permitidas"].assert_not_called()
            with patch.object(
                repeticao, "_enviar_retorno_etapa8"
            ) as enviar, patch.object(
                retorno, "atualizar_banco_com_contexto_final"
            ) as persistir, patch.object(
                retorno, "concluir_retomada"
            ) as concluir:
                envio = repeticao.enviar_repeticao_followup(cx)
                final = retorno.persistir_retorno_followup(cx, envio, MagicMock())
            enviar.assert_not_called()
            persistir.assert_not_called()
            concluir.assert_not_called()
            self.assertEqual(envio["id_etapa_resultante"], destino)
            self.assertEqual(final["id_etapa_resultante"], destino)
            self.assertFalse(final["atualizar_last_from_bot"])


class ProativoTests(unittest.TestCase):
    def test_primeiro_personaliza_convite_sem_reutilizar_nomes_antigos(self):
        for etapa, dependente, nome_dependente, nome_titular, saudacao, convite in (
            (1, False, None, "Ana", "Olá! ☺️", "receber você na nossa unidade para sua"),
            (1, True, "Bia", "Ana", "Olá! ☺️", "receber você na nossa unidade para sua"),
            (2, False, "Bia", " Ana ", "Olá, Ana! ☺️", "receber você na nossa unidade para sua"),
            (8, True, " Bia ", "Ana", "Olá, Ana! ☺️", "receber você e Bia na nossa unidade para a"),
            (5, True, None, "Ana", "Olá, Ana! ☺️", "receber vocês na nossa unidade para a"),
            (5, True, "", "Ana", "Olá, Ana! ☺️", "receber vocês na nossa unidade para a"),
            (5, True, "   ", "Ana", "Olá, Ana! ☺️", "receber vocês na nossa unidade para a"),
            (2, False, None, None, "Olá! ☺️", "receber você na nossa unidade para sua"),
        ):
            with self.subTest(etapa=etapa, dependente=dependente, nome=nome_dependente):
                texto = montar_mensagem_followup(
                    id_etapa=etapa, nome_titular=nome_titular,
                    status_dependente=dependente, nome_dependente=nome_dependente,
                )
                self.assertTrue(texto.startswith(saudacao + "\n\n"))
                self.assertIn(convite + " *experiência Supera gratuita*! 🧡", texto)
                self.assertEqual(len(texto.split("\n\n")), 4)
                self.assertTrue(texto.endswith("\n\n_Estaremos te esperando!_"))
                self.assertNotIn("\n\n\n", texto)
                self.assertNotIn("{", texto)
                if etapa == 1:
                    self.assertNotIn("Ana", texto)
                    self.assertNotIn("Bia", texto)
                if not dependente:
                    self.assertNotIn("Bia", texto)

    def test_primeiro_mantem_pergunta_de_atendimento_antes_e_depois_da_oferta(self):
        for etapa, dependente, nome_dependente in (
            (1, False, None),
            (6, False, None),
            (6, True, "Bia"),
            (7, False, "Bia"),
            (7, True, " Bia "),
            (8, False, None),
            (8, True, "Bia"),
            (17, False, None),
            (17, True, "Bia"),
            (7, True, None),
            (7, True, "   "),
        ):
            with self.subTest(etapa=etapa, dependente=dependente, nome=nome_dependente):
                texto = montar_mensagem_followup(
                    id_etapa=etapa, nome_titular="Ana", status_dependente=dependente,
                    nome_dependente=nome_dependente,
                )
                self.assertEqual(texto.split("\n\n")[2], "Podemos continuar seu atendimento por aqui?")

    def test_despedida_preserva_nome_da_rota_e_oculta_cadastro_antigo_na_etapa1(self):
        for etapa, dependente, nome_dependente, inicio, beneficio in (
            (1, False, None, "Oi, tudo bem? ☺️", "pode te oferecer"),
            (1, True, "Bia", "Oi, tudo bem? ☺️", "pode te oferecer"),
            (2, False, None, "Oi Ana, tudo bem? ☺️", "pode te oferecer"),
            (11, True, "Bia", "Oi Ana, tudo bem? ☺️", "você e Bia não estão preparados"),
            (5, True, None, "Oi Ana, tudo bem? ☺️", "pode te oferecer"),
            (5, True, "", "Oi Ana, tudo bem? ☺️", "pode te oferecer"),
            (5, True, "   ", "Oi Ana, tudo bem? ☺️", "pode te oferecer"),
        ):
            with self.subTest(etapa=etapa, dependente=dependente):
                texto = montar_mensagem_encerramento_followup(
                    id_etapa=etapa, nome_titular="Ana", nome_agente="Suh",
                    status_dependente=dependente, nome_dependente=nome_dependente,
                )
                self.assertTrue(texto.startswith(inicio))
                self.assertIn(beneficio, texto)
                self.assertIn("para aproveitar todos os benefícios", texto)
                self.assertIn(
                    "Então eu vou liberar a vaga para a próxima pessoa "
                    "e encerrar o seu atendimento, tudo bem?", texto,
                )
                self.assertTrue(texto.endswith(
                    "tudo bem?\n\nFico à disposição caso precise falar comigo novamente! ☺️👋"
                    "\n\n_Abraços, Suh. 🧡_"
                ))
                self.assertEqual(texto.count("Abraços,"), 1)
                self.assertNotIn("\n\n\n", texto)
                self.assertNotIn("{", texto)
                if dependente and etapa > 1 and str(nome_dependente or "").strip():
                    self.assertIn("que o Supera pode oferecer. Então eu vou liberar a vaga", texto)
                    if nome_dependente:
                        self.assertEqual(texto.count(nome_dependente), 1)
                else:
                    self.assertEqual(texto, montar_mensagem_encerramento_followup(
                        id_etapa=etapa, nome_titular="Ana", nome_agente="Suh",
                        status_dependente=False,
                    ))
                    self.assertNotIn("você e ", texto)
                if etapa == 1:
                    self.assertNotIn("Ana", texto)

    def test_texto_exato_e_numero_da_unidade(self):
        wa = MagicMock()
        wa.send_message.return_value = SimpleNamespace(id="wamid.bot")
        with patch.object(sender, "conta_wa", return_value=wa) as conta, patch.object(
            sender.httpx, "Client"
        ):
            result = sender.enviar_followup("5511999999999", "unidade-3")
        self.assertEqual(conta.call_args.args, ("unidade-3",))
        wa.send_message.assert_called_once_with(
            to="5511999999999", text=MENSAGEM_FOLLOWUP
        )
        self.assertEqual(result["mensagem_bot"], MENSAGEM_FOLLOWUP)

    def _processar(
        self, *, elegivel=True, lock=True, erro_envio=None, erro_banco=None, parar=False,
        stage=0, dados_releitura=None,
    ):
        conn = MagicMock()
        stop = Event()
        if parar:
            stop.set()
        with ExitStack() as stack:
            stack.enter_context(patch.object(worker, "get_conn", return_value=conn))
            stack.enter_context(
                patch.object(worker, "tentar_lock_conversa", return_value=(lock, 4))
            )
            stack.enter_context(patch.object(worker, "proteger_conversa"))
            reler = stack.enter_context(
                patch.object(
                    worker,
                    "reler_elegivel",
                    return_value={**candidato(), "followup_stage": stage,
                                  **(dados_releitura or {})} if elegivel else None,
                )
            )
            enviar = stack.enter_context(
                patch.object(
                    worker,
                    "enviar_followup",
                    return_value={"enviou": True, "id_hash_msg_bot": "wamid.bot"},
                    side_effect=erro_envio,
                )
            )
            persistir = stack.enter_context(
                patch.object(
                    worker,
                    "persistir_followup",
                    return_value=(9, AGORA),
                    side_effect=erro_banco,
                )
            )
            unlock = stack.enter_context(patch.object(worker, "unlock_conversa"))
            result = worker.processar_candidato(candidato(), stop)
        return result, conn, enviar, persistir, reler, unlock

    def test_confirmacao_commit_e_unlock(self):
        ok, conn, enviar, persistir, _, unlock = self._processar()
        self.assertTrue(ok)
        enviar.assert_called_once()
        persistir.assert_called_once()
        unlock.assert_called_once()
        conn.close.assert_called_once()
        conn.rollback.assert_not_called()

    def test_primeiro_usa_rota_e_nomes_da_releitura_antes_do_envio(self):
        ok, _, enviar, persistir, _, _ = self._processar(dados_releitura={
            "id_etapa": 8, "nome_titular": "Maria", "status_dependente": True,
            "nome_dependente": "Pedro",
        })
        self.assertTrue(ok)
        texto = enviar.call_args.kwargs["mensagem"]
        self.assertTrue(texto.startswith("Olá, Maria! ☺️\n\n"))
        self.assertIn("receber você e Pedro na nossa unidade", texto)
        self.assertIn("Podemos continuar seu atendimento por aqui?", texto)
        self.assertNotIn("Ana", texto)
        self.assertTrue(texto.endswith("\n\n_Estaremos te esperando!_"))
        self.assertEqual(persistir.call_args.args[0]["followup_stage"], 0)

    def test_segundo_envia_despedida_e_so_persiste_apos_confirmacao(self):
        ok, _, enviar, persistir, _, _ = self._processar(stage=1)
        self.assertTrue(ok)
        self.assertIn("Oi Ana, tudo bem? ☺️", enviar.call_args.kwargs["mensagem"])
        self.assertIn("Abraços, Suh.", enviar.call_args.kwargs["mensagem"])
        self.assertEqual(persistir.call_args.args[0]["followup_stage"], 1)
        ok, conn, _, persistir, _, _ = self._processar(
            stage=1, erro_envio=RuntimeError("Meta")
        )
        self.assertFalse(ok)
        persistir.assert_not_called()
        conn.rollback.assert_called_once()

    def test_cliente_chegou_antes_do_envio(self):
        ok, _, enviar, persistir, _, _ = self._processar(elegivel=False)
        self.assertFalse(ok)
        enviar.assert_not_called()
        persistir.assert_not_called()

    def test_lock_recusado_nao_envia_nem_libera_lock_alheio(self):
        ok, _, enviar, _, reler, unlock = self._processar(lock=False)
        self.assertFalse(ok)
        enviar.assert_not_called()
        reler.assert_not_called()
        unlock.assert_not_called()

    def test_falha_sender_nao_persiste_stage(self):
        ok, conn, _, persistir, _, _ = self._processar(erro_envio=RuntimeError("Meta"))
        self.assertFalse(ok)
        conn.rollback.assert_called_once()
        persistir.assert_not_called()

    def test_falha_persistencia_reverte(self):
        ok, conn, _, _, _, _ = self._processar(erro_banco=RuntimeError("banco"))
        self.assertFalse(ok)
        conn.rollback.assert_called_once()

    def test_sigterm_impede_proximo_despacho(self):
        _, _, enviar, _, _, _ = self._processar(parar=True)
        enviar.assert_not_called()


class LoteTests(unittest.TestCase):
    def test_falha_nao_interrompe_lote_e_volta_apos_fim_da_varredura(self):
        config = SimpleNamespace(lote=2, intervalo=60)
        parar = MagicMock()
        parar.is_set.return_value = False
        ids_processados = []
        primeiro = candidato()
        segundo = dict(primeiro, id_conversa=2)
        terceiro = dict(primeiro, id_conversa=3)

        def processar(item, _parar):
            ids_processados.append(item["id_conversa"])
            if len(ids_processados) == 1:
                raise RuntimeError("Conexão falhou antes do despacho")
            return True

        def esperar(_intervalo):
            if len(ids_processados) == 4:
                parar.is_set.return_value = True

        parar.wait.side_effect = esperar
        with patch.object(
            worker,
            "obter_lote",
            side_effect=[[primeiro, segundo], [terceiro], [primeiro]],
        ) as obter, patch.object(worker, "processar_candidato", side_effect=processar):
            worker.executar_worker(config, parar)
        self.assertEqual(ids_processados, [1, 2, 3, 1])
        self.assertEqual(
            [c.args for c in obter.call_args_list],
            [(2, None), (2, (AGORA, 2)), (2, None)],
        )
        self.assertEqual(
            [c.args for c in parar.wait.call_args_list], [(60,), (60,), (60,)]
        )


class SQLTests(unittest.TestCase):
    def test_fencing_recusa_dono_antigo(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = None
        with self.assertRaises(repo.LockConversaPerdido):
            repo.proteger_conversa(1, 3, cursor)
        self.assertIn("FOR UPDATE", cursor.execute.call_args.args[0])

    def test_reset_condicional_sem_limpar_data_auditoria(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = (1,)
        cursor.rowcount = 1
        repo.concluir_retomada(contexto(), AGORA, cursor)
        sql, params = cursor.execute.call_args_list[1].args
        self.assertNotIn("followup_last_sent_at =", sql.split("WHERE")[0])
        self.assertIn("followup_stage = 0", sql)
        self.assertIn("lock_version = %s", sql)
        self.assertEqual(sql.count("%s"), len(params))

    def test_parametros_proativo_e_paginacao(self):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [(1,), (9, AGORA)]
        cursor.rowcount = 1
        repo.persistir_followup(
            candidato(),
            {
                "enviou": True,
                "id_hash_msg_bot": "wamid.bot",
                "mensagem_bot": "Você viu a minha mensagem?",
            },
            4,
            cursor,
        )
        for chamada in cursor.execute.call_args_list:
            sql, params = chamada.args
            self.assertEqual(sql.count("%s"), len(params))
        insert = cursor.execute.call_args_list[1].args[0]
        self.assertIn("NULL, NULL", insert)
        cursor.reset_mock()
        cursor.fetchall.return_value = []
        repo.listar_elegiveis(cursor, 20, (AGORA, 1))
        sql, params = cursor.execute.call_args.args
        self.assertEqual(sql.count("%s"), len(params))


if __name__ == "__main__":
    unittest.main()
