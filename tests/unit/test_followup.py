import unittest
from contextlib import ExitStack
from datetime import datetime, timezone
from threading import Event
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from core.repositories.atendimento import followup as repo
from core.integrations.whatsapp.pywa_functions.pywa_senders import followup as sender
from workers.worker_followup import followup_worker as worker
from workers.worker_flow.response_flow import repeticao_followup as repeticao
from workers.worker_flow.transacoes import retorno_followup as retorno

AGORA = datetime(2026, 9, 7, 12, tzinfo=timezone.utc)


def banco(stage=1):
    return {
        "id_cliente": 2,
        "id_unidade": 3,
        "conversa": {
            "id_conversa": 1,
            "id_etapa_atual": 11,
            "status_ativa": True,
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
    }


def dados():
    return {
        "nome_cliente": "Ana",
        "nome_dependente": "Bia",
        "idade_dependente": 12,
        "nome_unidade": "Unidade Teste",
        "nome_agente": "Suh",
        "genero": "feminino",
        "link_agendamento": "https://example.com/agendar",
        "link_instagram": "https://example.com/rede",
        "status_dependente": False,
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
    }


class RetornoTests(unittest.TestCase):
    def preparar(
        self, stage=1, tipo="text", retomada=None, resposta=None, enviado_em=AGORA
    ):
        with ExitStack() as stack:
            mocks = {}
            valores = {
                "buscar_retomada": retomada,
                "buscar_resposta_bot_por_mensagem_cliente": resposta,
                "buscar_contexto_repeticao": dados(),
                "registrar_retomada": None,
                "inserir_historico_mensagem_cliente": (
                    6,
                    AGORA,
                    11,
                    not bool(resposta),
                ),
                "atualizar_conversa_mensagem_cliente": None,
            }
            for nome, valor in valores.items():
                mocks[nome] = stack.enter_context(
                    patch.object(retorno, nome, return_value=valor)
                )
            cx_banco = banco(stage)
            cx_banco["conversa"]["followup_last_sent_at"] = enviado_em
            result = retorno.preparar_retorno_followup(
                mensagem(tipo), cx_banco, MagicMock()
            )
        return result, mocks

    def test_zero_preserva_caminho_normal(self):
        result, mocks = self.preparar(stage=0)
        self.assertIsNone(result)
        mocks["inserir_historico_mensagem_cliente"].assert_not_called()

    def test_reacoes_nao_passam_por_validacao(self):
        for stage in (1, 2, 3, 9):
            for tipo in ("text", "interactive", "image", "audio", "unsupported"):
                with self.subTest(stage=stage, tipo=tipo):
                    result, mocks = self.preparar(stage=stage, tipo=tipo)
                    self.assertEqual(result["id_etapa_resposta"], 11)
                    self.assertTrue(result["retorno_followup"])
                    self.assertNotIn("transicoes_permitidas", result)
                    self.assertNotIn("saudacao_retorno", result)
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
        self.assertEqual(result["id_etapa_resposta"], 11)
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
            retorno, "inserir_historico_mensagem_bot"
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
            "inserir_historico_mensagem_bot",
            side_effect=lambda *_: eventos.append("historico") or (7, AGORA, True),
        ), patch.object(
            retorno, "concluir_retomada", side_effect=lambda *_: eventos.append("reset")
        ):
            final = retorno.persistir_retorno_followup(contexto(), envio, MagicMock())
        self.assertEqual(eventos, ["historico", "reset"])
        self.assertNotIn("turnos_sem_avanco", final)
        self.assertNotIn("efeitos_transicao", final)
        self.assertIsNone(final["intencao_encerramento"])

    def test_falha_historico_nao_chega_ao_reset(self):
        envio = {"enviou": True, "id_etapa_resultante": 11}
        with patch.object(
            retorno, "inserir_historico_mensagem_bot", side_effect=RuntimeError
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
                    cx["dados_repeticao"]["nome_cliente"] = nome_antigo
                    cx["mensagem_cliente_atual"]["conteudo_texto"] = "Opa"
                    fake = MagicMock()
                    fake.send_message.return_value = SimpleNamespace(id="wamid.bot")
                    with patch.object(cliente, "WhatsApp", return_value=fake):
                        envio = repeticao.enviar_repeticao_followup(cx)
                    self.assertTrue(
                        envio["mensagem_bot"].startswith("Que bom te ver novamente!\n\n")
                    )
                    self.assertIn("Como você se chama?", envio["mensagem_bot"])
                    if nome_antigo:
                        self.assertNotIn(nome_antigo, envio["mensagem_bot"])
                    self.assertNotIn("Opa", envio["mensagem_bot"])
                    self.assertEqual(envio["id_etapa_resultante"], 1)
                    self.assertNotIn("evento_transicao", envio)
                    self.assertEqual(cx["dados_repeticao"]["nome_cliente"], nome_antigo)
                    self.assertEqual(
                        envio["mensagem_bot"], fake.send_message.call_args.kwargs["text"]
                    )

    def test_todas_etapas_repetiveis_usam_senders_existentes(self):
        # Executa catálogos e senders reais; substitui somente o cliente HTTP.
        from core.integrations.whatsapp.pywa_functions import cliente

        for dependente in (False, True):
            for etapa in range(1, 22):
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
                        "Que bom te ver novamente!\n\n"
                        if etapa == 1
                        else "Que bom te ver novamente, Ana!\n\n"
                    )
                    self.assertTrue(
                        envio["mensagem_bot"].startswith(saudacao_esperada)
                    )
                    self.assertEqual(
                        envio["mensagem_bot"].count("Que bom te ver novamente"), 1
                    )

    def test_sem_nome_usa_saudacao_generica_e_preserva_texto_enviado(self):
        from core.integrations.whatsapp.pywa_functions import cliente

        for nome in (None, "", "   "):
            with self.subTest(nome=nome):
                cx = contexto()
                cx["id_etapa_atual"] = 1
                cx["dados_repeticao"]["nome_cliente"] = nome
                fake = MagicMock()
                fake.send_message.return_value = SimpleNamespace(id="wamid.bot")
                with patch.object(cliente, "WhatsApp", return_value=fake):
                    with cliente.usar_prefixo_mensagem_bot(
                        "Olá novamente, Nome antigo!\n\n"
                    ):
                        envio = repeticao.enviar_repeticao_followup(cx)
                self.assertTrue(
                    envio["mensagem_bot"].startswith("Que bom te ver novamente!\n\n")
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
            "nome_cliente": "Edcarlos",
            "tipo_mensagem_atual": "text",
            "texto_cliente_atual": "Maria",
            "transicoes_permitidas": {"nome_cliente_valido": 2},
            "mensagem_cliente_atual": contexto()["mensagem_cliente_atual"],
        }
        with patch.object(
            resolver_etapa1, "enviar_etapa2",
            return_value={"enviou": True, "id_etapa_resultante": 2},
        ) as enviar:
            envio = resolver_etapa1.resolve_etapa1(cx)
        self.assertEqual(enviar.call_args.kwargs["nome"], "Maria")
        self.assertEqual(envio["primeiro_nome_cliente"], "Maria")
        self.assertEqual(envio["evento_transicao"], "nome_cliente_valido")

    def test_terminal_e_dado_ausente_falham_antes_da_meta(self):
        for etapa in (None, 0, 22, 23):
            with self.assertRaises(ValueError):
                repeticao._selecionar_sender(etapa, dados())
        cx = dados()
        cx["nome_dependente"] = None
        cx["status_dependente"] = True
        with self.assertRaises(ValueError):
            repeticao._selecionar_sender(12, cx)


class ProativoTests(unittest.TestCase):
    def test_texto_exato_e_numero_da_unidade(self):
        wa = MagicMock()
        wa.send_message.return_value = SimpleNamespace(id="wamid.bot")
        with patch.object(sender, "conta_wa", return_value=wa) as conta, patch.object(
            sender.httpx, "Client"
        ):
            result = sender.enviar_followup("5511999999999", "unidade-3")
        self.assertEqual(conta.call_args.args, ("unidade-3",))
        wa.send_message.assert_called_once_with(
            to="5511999999999", text="Você viu a minha mensagem?"
        )
        self.assertEqual(result["mensagem_bot"], "Você viu a minha mensagem?")

    def _processar(
        self, *, elegivel=True, lock=True, erro_envio=None, erro_banco=None, parar=False
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
                    return_value=candidato() if elegivel else None,
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
