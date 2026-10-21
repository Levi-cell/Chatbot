"""Contrato PostgreSQL real. Exige banco local vazio chamado test_chatbot_followup."""

import os
import unittest
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

import psycopg
from psycopg.conninfo import conninfo_to_dict

from core.database.deploy_database import bank_script, etapa_transicao_script
from core.repositories.atendimento import followup as repo
from core.repositories.atendimento.conversas import (
    tentar_lock_conversa,
    unlock_conversa,
)
from workers.worker_flow.transacoes.retorno_followup import (
    preparar_retorno_followup,
    persistir_retorno_followup,
)
from workers.worker_flow.response_flow.retomada_followup import enviar_retorno_followup
from core.integrations.whatsapp.pywa_functions import cliente as cliente_wa
from core.repositories.monitoramento import painel
from callback.monitoramento.apresentacao import consolidar_conversas
from workers.worker_flow.valida_banco import valida_conversa
from workers.worker_flow.valida_historico import valida_historico
from workers.worker_flow.response_flow.flow_sender import flow_sender

DSN = os.environ.get("FOLLOWUP_TEST_DSN")
MIGRACAO = (
    Path(__file__).resolve().parents[2] / "deploy/migrations/followup_registros.sql"
)


@unittest.skipUnless(DSN, "Defina FOLLOWUP_TEST_DSN para PostgreSQL local descartável")
class FollowupPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parametros = conninfo_to_dict(DSN)
        if (
            parametros.get("host") not in {"127.0.0.1", "::1", "localhost"}
            or parametros.get("dbname") != "test_chatbot_followup"
        ):
            raise RuntimeError(
                "Teste exige host loopback e dbname=test_chatbot_followup"
            )
        cls.conn = psycopg.connect(DSN, connect_timeout=5)
        cls.cursor = cls.conn.cursor()
        cls.cursor.execute("SELECT to_regnamespace('chatbot')")
        if cls.cursor.fetchone()[0] is not None:
            cls.conn.close()
            raise RuntimeError(
                "Banco de teste não está vazio: schema chatbot já existe"
            )
        cls.cursor.execute(
            "CREATE SCHEMA chatbot; CREATE TABLE chatbot.auth_user (id SERIAL PRIMARY KEY);"
        )

        @contextmanager
        def transacao_local(*_):
            yield cls.cursor

        with patch.object(bank_script, "transacao_deploy", transacao_local):
            bank_script.criar_tabelas()
            bank_script.criar_funcoes_lock()
        # Colunas reais usadas nas barreiras; não simula o comportamento da Meta.
        cls.cursor.execute(
            """
            CREATE TABLE chatbot.cliente_bloqueado_meta
                (wa_id_cliente VARCHAR(100), phone_id_unidade VARCHAR(100));
            CREATE TABLE chatbot.webhook_flood_evento
                (wa_id_cliente VARCHAR(100), phone_id_unidade VARCHAR(100), received_at TIMESTAMPTZ);
            INSERT INTO chatbot.etapa(id_etapa, nome_etapa)
            SELECT etapa, 'Etapa de teste ' || etapa::text FROM generate_series(1, 24) AS etapa;
            INSERT INTO chatbot.cliente(id_cliente, waid_telefone, nome, idade) VALUES (1, '5511999999999', 'Ana', 35);
            INSERT INTO chatbot.unidade
                (id_unidade, nome_unidade, nome_agente, genero, cnpj, email_responsavel,
                 telefone, numero_comercial, waba_id, phone_number_id, link_agendamento)
            VALUES (1, 'Unidade Teste', 'Suh', 'feminino', 'teste', 'teste@example.com',
                '5511888888888', '5511999999998', 'waba-teste', 'phone-teste', 'https://example.com/agendar');
            INSERT INTO chatbot.conversa(id_conversa, id_cliente, id_unidade, id_etapa_atual)
            VALUES (1, 1, 1, 11);
        """
        )
        with patch.object(etapa_transicao_script, "transacao_deploy", transacao_local):
            etapa_transicao_script.criar_e_povoar_transicoes_etapa()
        cls.conn.commit()

    @classmethod
    def tearDownClass(cls):
        cls.conn.rollback()
        cls.cursor.execute("DROP SCHEMA chatbot CASCADE")
        cls.conn.commit()
        cls.conn.close()

    def setUp(self):
        self.conn.rollback()
        self.cursor.execute("SELECT clock_timestamp()")
        self.agora = self.cursor.fetchone()[0]
        self.ancora = self.agora - timedelta(hours=7, seconds=1)
        self.cursor.execute(
            """
            INSERT INTO chatbot.historico_mensagens
                (id_conversa, id_etapa, received_data_hora, cliente_telefone, conteudo_texto,
                 tipo_mensagem, id_hash_msg, id_phone_unidade, unidade_telefone, quem_enviou, status_envio)
            VALUES (1, 11, %s, '5511999999999', 'mensagem', 'text', 'wamid.cliente',
                    'phone-teste', '5511888888888', 'cliente', NULL),
                   (1, 11, %s, '5511999999999', 'Podemos começar?', 'text', 'wamid.bot',
                    'phone-teste', '5511888888888', 'bot', 'sent');
        """,
            (self.ancora - timedelta(minutes=1), self.ancora),
        )
        self.cursor.execute(
            "UPDATE chatbot.conversa SET last_message_from = 'bot', last_interaction_at = %s WHERE id_conversa = 1",
            (self.ancora,),
        )

    def tearDown(self):
        self.conn.rollback()

    def test_sete_horas_um_envio_e_reinicio_nao_duplica(self):
        dados = repo.reler_elegivel(1, self.cursor)
        self.assertIsNotNone(dados)
        ok, versao = tentar_lock_conversa(1, self.cursor)
        self.assertTrue(ok)
        envio = {
            "enviou": True,
            "mensagem_bot": "Você viu a minha mensagem?",
            "id_hash_msg_bot": "wamid.followup",
        }
        id_bot, data = repo.persistir_followup(dados, envio, versao, self.cursor)
        self.assertIsNone(repo.reler_elegivel(1, self.cursor))
        self.cursor.execute(
            "SELECT followup_stage, followup_last_sent_at FROM chatbot.conversa WHERE id_conversa=1"
        )
        self.assertEqual(self.cursor.fetchone(), (1, data))
        self.cursor.execute(
            "SELECT id_mensagem_fila, id_hash_cliente_origem FROM chatbot.historico_mensagens WHERE id_mensagem=%s AND received_data_hora=%s",
            (id_bot, data),
        )
        self.assertEqual(self.cursor.fetchone(), (None, None))

    def _primeiro_followup_vencido(self):
        dados = repo.reler_elegivel(1, self.cursor)
        _, versao = tentar_lock_conversa(1, self.cursor)
        repo.persistir_followup(dados, {
            "enviou": True, "mensagem_bot": "Primeiro lembrete",
            "id_hash_msg_bot": "wamid.followup1",
        }, versao, self.cursor)
        # O primeiro envio acabou de acontecer: não basta a âncora original ter 7h.
        self.assertIsNone(repo.reler_elegivel(1, self.cursor))
        self.cursor.execute("""
            UPDATE chatbot.historico_mensagens
               SET received_data_hora=received_data_hora-INTERVAL '7 hours 1 second';
            UPDATE chatbot.followup_envio
               SET ancora_em=ancora_em-INTERVAL '7 hours 1 second',
                   enviado_em=enviado_em-INTERVAL '7 hours 1 second';
            UPDATE chatbot.conversa
               SET last_interaction_at=last_interaction_at-INTERVAL '7 hours 1 second',
                   followup_last_sent_at=followup_last_sent_at-INTERVAL '7 hours 1 second';
        """)
        return repo.reler_elegivel(1, self.cursor), versao

    def _confirmar_segundo(self, dados, versao):
        return repo.persistir_followup(dados, {
            "enviou": True, "mensagem_bot": "Despedida",
            "id_hash_msg_bot": "wamid.followup2",
        }, versao, self.cursor)

    def test_segundo_apos_mais_sete_horas_fecha_atomicamente_sem_terceiro(self):
        dados, versao = self._primeiro_followup_vencido()
        self.assertEqual(dados["followup_stage"], 1)
        self.cursor.execute("UPDATE chatbot.conversa SET turnos_sem_avanco=4")
        self.cursor.execute("SAVEPOINT antes_despedida")
        _, encerrada_em = self._confirmar_segundo(dados, versao)
        self.cursor.execute("""
            SELECT followup_stage,status_ativa,motivo_encerramento,finalizou_em,
                   followup_last_sent_at,id_etapa_atual,turnos_sem_avanco
            FROM chatbot.conversa WHERE id_conversa=1
        """)
        self.assertEqual(self.cursor.fetchone(), (
            2, False, "followup_sem_resposta", encerrada_em, encerrada_em, 11, 4,
        ))
        self.assertIsNone(repo.reler_elegivel(1, self.cursor))
        self.cursor.execute("SELECT count(*) FROM chatbot.followup_envio")
        self.assertEqual(self.cursor.fetchone()[0], 2)
        self.cursor.execute("ROLLBACK TO SAVEPOINT antes_despedida")
        self.cursor.execute("SELECT followup_stage,status_ativa,finalizou_em FROM chatbot.conversa")
        self.assertEqual(self.cursor.fetchone(), (1, True, None))
        self.cursor.execute("SELECT count(*) FROM chatbot.followup_envio")
        self.assertEqual(self.cursor.fetchone()[0], 1)
        self.cursor.execute("SELECT count(*) FROM chatbot.historico_mensagens WHERE id_hash_msg='wamid.followup2'")
        self.assertEqual(self.cursor.fetchone()[0], 0)

    def test_segundo_apenas_etapas1_a17_incluindo8_e_guardas_de_silencio(self):
        _, _ = self._primeiro_followup_vencido()
        for etapa in range(1, 25):
            with self.subTest(etapa=etapa):
                self.cursor.execute("UPDATE chatbot.conversa SET id_etapa_atual=%s", (etapa,))
                self.assertEqual(repo.reler_elegivel(1, self.cursor) is not None, etapa <= 17)
        self.cursor.execute("UPDATE chatbot.conversa SET id_etapa_atual=8")
        for sql in (
            "UPDATE chatbot.conversa SET last_message_from='cliente'",
            "UPDATE chatbot.conversa SET followup_last_sent_at=clock_timestamp()",
            "UPDATE chatbot.historico_mensagens SET received_data_hora=clock_timestamp() WHERE quem_enviou='cliente'",
            "UPDATE chatbot.historico_mensagens SET received_data_hora=clock_timestamp()-INTERVAL '24 hours' WHERE quem_enviou='cliente'",
            "DELETE FROM chatbot.followup_envio",
            "UPDATE chatbot.conversa SET followup_stage=2",
            "UPDATE chatbot.unidade SET status_pagamento=FALSE",
            """INSERT INTO chatbot.fila_mensagens
                (received_data_hora,cliente_telefone,conteudo_texto,tipo_mensagem,id_hash_msg,id_phone_unidade,unidade_telefone)
                VALUES (clock_timestamp(),'5511999999999','Voltei','text','pendente','phone-teste','5511888888888')""",
        ):
            with self.subTest(guarda=sql):
                self.cursor.execute("SAVEPOINT guarda_segundo")
                self.cursor.execute(sql)
                self.assertIsNone(repo.reler_elegivel(1, self.cursor))
                self.cursor.execute("ROLLBACK TO SAVEPOINT guarda_segundo")

    def test_retorno_apos_segundo_abre_nova_conversa_sem_prefixo(self):
        dados, versao = self._primeiro_followup_vencido()
        self._confirmar_segundo(dados, versao)
        unlock_conversa(1, versao, self.cursor)
        # A fixture usa ID explícito; sincroniza apenas a sequência local do teste.
        self.cursor.execute("SELECT setval(pg_get_serial_sequence('chatbot.conversa','id_conversa'), 1)")
        nova = valida_conversa(1, 1, False, self.cursor)
        self.assertNotEqual(nova["id_conversa"], 1)
        self.assertIsNone(nova["id_etapa_atual"])
        self.assertEqual(nova["followup_stage"], 0)
        self.assertTrue(nova["status_ativa"])
        mensagem = {
            "id_mensagem": 10, "id_hash": "wamid.novo", "data_recebimento": self.agora,
            "cliente_telefone": "5511999999999", "id_phone_unidade": "phone-teste",
            "unidade_telefone": "5511888888888", "tipo_mensagem": "text",
            "conteudo_texto": "Olá", "retry_count": 0,
        }
        self.cursor.execute("""
            INSERT INTO chatbot.fila_mensagens
                (id_mensagem,received_data_hora,cliente_telefone,conteudo_texto,tipo_mensagem,id_hash_msg,id_phone_unidade,unidade_telefone)
            VALUES(10,clock_timestamp(),'5511999999999','Olá','text','wamid.novo','phone-teste','5511888888888')
        """)
        contexto_banco = {"id_cliente": 1, "id_unidade": 1, "conversa": nova}
        self.assertIsNone(preparar_retorno_followup(mensagem, contexto_banco, self.cursor))
        contexto = valida_historico(mensagem, contexto_banco, self.cursor)
        self.assertIsNone(contexto["saudacao_retorno"])
        with patch.object(cliente_wa, "WhatsApp") as wa:
            wa.return_value.send_message.return_value = SimpleNamespace(id="wamid.abertura")
            envio = flow_sender(contexto)
        self.assertEqual(envio["id_etapa_resultante"], 1)
        self.assertNotIn("te ver novamente", envio["mensagem_bot"])
        self.assertIn("Suh", envio["mensagem_bot"])
        self.cursor.execute("SELECT followup_stage,status_ativa FROM chatbot.conversa WHERE id_conversa=1")
        self.assertEqual(self.cursor.fetchone(), (2, False))

    def test_painel_considera_so_ultima_conversa_mesmo_fora_do_periodo(self):
        dados, versao = self._primeiro_followup_vencido()
        fim = self.agora + timedelta(days=1)
        def chats(ate=fim):
            return consolidar_conversas(painel.listar_conversas(1, None, ate, self.cursor))
        self.assertEqual(chats()[0]["followup_stage"], 1)
        self._confirmar_segundo(dados, versao)
        self.assertEqual(chats()[0]["followup_stage"], 2)
        self.cursor.execute("""
            INSERT INTO chatbot.unidade
                (id_unidade,nome_unidade,nome_agente,genero,cnpj,email_responsavel,
                 telefone,numero_comercial,waba_id,phone_number_id,link_agendamento)
            VALUES(2,'Outra','Mia','feminino','outro','outro@example.com',
                   '5511777777777','5511999999997','outra-waba','outro-phone','https://example.com');
            INSERT INTO chatbot.conversa(id_conversa,id_cliente,id_unidade,id_etapa_atual)
            VALUES(3,1,2,1);
        """)
        # O mesmo cliente em outra unidade não pode esconder o follow-up daqui.
        self.assertEqual(chats()[0]["followup_stage"], 2)
        self.cursor.execute("""
            INSERT INTO chatbot.conversa(id_conversa,id_cliente,id_unidade,id_etapa_atual)
            VALUES(2,1,1,1)
        """)
        # A nova conversa nem possui histórico no período: ainda assim oculta a antiga.
        self.assertEqual(chats()[0]["followup_stage"], 0)
        self.assertEqual(chats(self.agora - timedelta(hours=1))[0]["followup_stage"], 0)
        self.cursor.execute("""
            INSERT INTO chatbot.historico_mensagens
                (id_conversa,id_etapa,received_data_hora,cliente_telefone,conteudo_texto,tipo_mensagem,
                 id_hash_msg,id_phone_unidade,unidade_telefone,quem_enviou)
            VALUES(2,1,clock_timestamp(),'5511999999999','Oi','text','wamid.nova.conversa','phone-teste','5511888888888','cliente');
            UPDATE chatbot.conversa SET followup_stage=1 WHERE id_conversa=2;
        """)
        chat = chats()[0]
        self.assertEqual(chat["ids_conversa"], [1, 2])
        self.assertEqual(chat["followup_stage"], 1)
        self.cursor.execute("UPDATE chatbot.conversa SET followup_stage=0 WHERE id_conversa=2")
        self.assertEqual(chats()[0]["followup_stage"], 0)

    def test_antes_de_sete_horas_e_fora_da_janela_meta(self):
        self.cursor.execute(
            "UPDATE chatbot.historico_mensagens SET received_data_hora=%s WHERE quem_enviou='bot'",
            (self.agora - timedelta(hours=6),),
        )
        self.cursor.execute(
            "UPDATE chatbot.conversa SET last_interaction_at=%s",
            (self.agora - timedelta(hours=6),),
        )
        self.assertIsNone(repo.reler_elegivel(1, self.cursor))
        self.cursor.execute(
            "UPDATE chatbot.historico_mensagens SET received_data_hora=%s WHERE quem_enviou='bot'",
            (self.ancora,),
        )
        self.cursor.execute(
            "UPDATE chatbot.conversa SET last_interaction_at=%s", (self.ancora,)
        )
        self.cursor.execute(
            "UPDATE chatbot.historico_mensagens SET received_data_hora=%s WHERE quem_enviou='cliente'",
            (self.agora - timedelta(hours=24),),
        )
        self.assertIsNone(repo.reler_elegivel(1, self.cursor))

    def test_fila_sem_vinculo_bloqueia_so_o_par_correto(self):
        self.cursor.execute(
            """
            INSERT INTO chatbot.fila_mensagens
                (received_data_hora, cliente_telefone, conteudo_texto, tipo_mensagem,
                 id_hash_msg, id_phone_unidade, unidade_telefone)
            VALUES (%s, '5511999999999', 'Olá', 'text', 'fila-test', 'outra-unidade', 'outro-numero');
        """,
            (self.agora,),
        )
        self.assertIsNotNone(repo.reler_elegivel(1, self.cursor))
        self.cursor.execute(
            "UPDATE chatbot.fila_mensagens SET id_phone_unidade='phone-teste'"
        )
        self.assertIsNone(repo.reler_elegivel(1, self.cursor))

    def test_bloqueios_stage_e_unidade_impedem_despacho(self):
        # Mesmo ativas e não terminais, as etapas a partir do agendamento são excluídas.
        for etapa in range(1, 25):
            with self.subTest(etapa=etapa):
                self.cursor.execute("SAVEPOINT faixa_etapa")
                self.cursor.execute(
                    "UPDATE chatbot.conversa SET id_etapa_atual=%s", (etapa,)
                )
                self.assertEqual(
                    repo.reler_elegivel(1, self.cursor) is not None, etapa < 18
                )
                self.assertEqual(
                    bool(repo.listar_elegiveis(self.cursor, 20)), etapa < 18
                )
                self.cursor.execute("ROLLBACK TO SAVEPOINT faixa_etapa")
        for sql in (
            "UPDATE chatbot.conversa SET followup_stage=1",
            "UPDATE chatbot.conversa SET followup_stage=2",
            "UPDATE chatbot.conversa SET followup_stage=-1",
            "UPDATE chatbot.conversa SET turnos_sem_avanco=12",
            "UPDATE chatbot.conversa SET status_ativa=FALSE",
            "UPDATE chatbot.unidade SET status_pagamento=FALSE",
            "INSERT INTO chatbot.cliente_bloqueado_meta VALUES ('5511999999999','phone-teste')",
        ):
            with self.subTest(sql=sql):
                self.cursor.execute("SAVEPOINT variacao")
                self.cursor.execute(sql)
                self.assertIsNone(repo.reler_elegivel(1, self.cursor))
                self.cursor.execute("ROLLBACK TO SAVEPOINT variacao")

    def test_unicidade_da_ancora_e_rollback_do_historico(self):
        dados = repo.reler_elegivel(1, self.cursor)
        _, versao = tentar_lock_conversa(1, self.cursor)
        envio = {
            "enviou": True,
            "mensagem_bot": "Você viu a minha mensagem?",
            "id_hash_msg_bot": "wamid.followup",
        }
        repo.persistir_followup(dados, envio, versao, self.cursor)
        self.cursor.execute("SAVEPOINT duplicado")
        with self.assertRaises(psycopg.errors.UniqueViolation):
            repo.persistir_followup(dados, envio, versao, self.cursor)
        self.cursor.execute("ROLLBACK TO SAVEPOINT duplicado")
        self.cursor.execute("SELECT count(*) FROM chatbot.followup_envio")
        self.assertEqual(self.cursor.fetchone()[0], 1)

    def test_reset_e_marcador_sao_atomicos(self):
        _, versao = tentar_lock_conversa(1, self.cursor)
        self.cursor.execute(
            "UPDATE chatbot.conversa SET followup_stage=1, followup_last_sent_at=%s",
            (self.agora,),
        )
        contexto = {
            "id_conversa": 1,
            "lock_version": versao,
            "id_etapa_atual": 11,
            "stage_anterior": 1,
            "followup_em": self.agora,
            "mensagem_cliente_atual": {
                "id_mensagem_fila": 10,
                "id_hash_msg": "wamid.reacao",
            },
        }
        self.cursor.execute("SAVEPOINT sem_marcador")
        with self.assertRaises(ValueError):
            repo.concluir_retomada(contexto, self.agora, self.cursor)
        self.cursor.execute("ROLLBACK TO SAVEPOINT sem_marcador")
        self.cursor.execute("SELECT followup_stage FROM chatbot.conversa")
        self.assertEqual(self.cursor.fetchone()[0], 1)
        self.cursor.execute(
            "INSERT INTO chatbot.followup_retomada(id_conversa,id_mensagem_fila,id_hash_cliente,id_etapa,stage_anterior,followup_em) VALUES(1,10,'wamid.reacao',11,1,%s)",
            (self.agora,),
        )
        repo.concluir_retomada(contexto, self.agora, self.cursor)
        self.cursor.execute(
            "SELECT followup_stage,followup_last_sent_at,turnos_sem_avanco,id_etapa_atual FROM chatbot.conversa"
        )
        self.assertEqual(self.cursor.fetchone(), (0, self.agora, 0, 11))

    def test_reacao_real_rollback_e_replay_preservam_ciclo_posterior(self):
        self._verificar_reacao_real(origem=11, destino=11)

    def test_reacao_etapa8_avanca_e_rollback_e_replay_preservam_ciclo(self):
        self._verificar_reacao_real(origem=8, destino=9)

    def test_nome_valido_avanca_e_grava_cliente_com_reset_atomico(self):
        self._verificar_reacao_real(origem=1, destino=2, texto="Antonia")

    def test_triagem_valida_avanca_e_grava_resposta_com_reset_atomico(self):
        self._verificar_reacao_real(origem=12, destino=13, texto="Às vezes")

    def test_tratamento_especifico_preserva_etapa_e_contador(self):
        self._verificar_reacao_real(origem=6, destino=6, texto="Quanto custa?")

    def _verificar_reacao_real(self, *, origem, destino, texto="???"):
        mensagem = {
            "id_mensagem": 10,
            "id_hash": "wamid.reacao",
            "data_recebimento": self.agora,
            "cliente_telefone": "5511999999999",
            "id_phone_unidade": "phone-teste",
            "unidade_telefone": "5511888888888",
            "tipo_mensagem": "text",
            "conteudo_texto": texto,
            "retry_count": 1,
        }
        self.cursor.execute(
            """
            INSERT INTO chatbot.fila_mensagens
                (id_mensagem, id_conversa, received_data_hora, cliente_telefone,
                 conteudo_texto, tipo_mensagem, id_hash_msg, id_phone_unidade,
                 unidade_telefone, status)
            VALUES (10, 1, %s, '5511999999999', %s, 'text',
                    'wamid.reacao', 'phone-teste', '5511888888888', 'processing');
            """,
            (self.agora, texto),
        )
        for followup_em in (None, self.agora):
            with self.subTest(legado=followup_em is None):
                self.cursor.execute("SAVEPOINT ciclo_reacao")
                self.cursor.execute(
                    "UPDATE chatbot.conversa SET followup_stage=1, followup_last_sent_at=%s, turnos_sem_avanco=5, id_etapa_atual=%s",
                    (followup_em, origem),
                )
                _, versao = tentar_lock_conversa(1, self.cursor)
                contexto_banco = repo.reler_conversa(
                    {"conversa": {"id_conversa": 1}, "id_cliente": 1, "id_unidade": 1},
                    versao,
                    self.cursor,
                )
                contexto = preparar_retorno_followup(
                    mensagem, contexto_banco, self.cursor
                )
                with patch.object(cliente_wa, "WhatsApp") as wa:
                    wa.return_value.send_message.return_value = SimpleNamespace(
                        id="wamid.repeticao"
                    )
                    envio = enviar_retorno_followup(contexto)
                self.assertEqual(envio["id_etapa_resultante"], destino)
                self.cursor.execute("SELECT followup_stage FROM chatbot.conversa")
                self.assertEqual(self.cursor.fetchone()[0], 1)

                # Uma falha deve reverter histórico, avanço (na etapa 8) e reset juntos.
                self.cursor.execute("SAVEPOINT confirmacao")
                persistir_retorno_followup(contexto, envio, self.cursor)
                self.cursor.execute("ROLLBACK TO SAVEPOINT confirmacao")
                self.cursor.execute(
                    "SELECT followup_stage, id_etapa_atual, turnos_sem_avanco FROM chatbot.conversa"
                )
                self.assertEqual(self.cursor.fetchone(), (1, origem, 5))
                self.cursor.execute(
                    "SELECT concluida_em FROM chatbot.followup_retomada"
                )
                self.assertIsNone(self.cursor.fetchone()[0])
                self.cursor.execute("SELECT count(*) FROM chatbot.historico_mensagens")
                self.assertEqual(self.cursor.fetchone()[0], 3)

                persistir_retorno_followup(contexto, envio, self.cursor)
                self.cursor.execute(
                    "SELECT followup_stage,followup_last_sent_at,turnos_sem_avanco,id_etapa_atual FROM chatbot.conversa"
                )
                self.assertEqual(
                    self.cursor.fetchone(),
                    (0, followup_em, 0 if origem != destino else 5, destino),
                )
                if origem == 1:
                    self.cursor.execute(
                        "SELECT nome FROM chatbot.cliente WHERE id_cliente=1"
                    )
                    self.assertEqual(self.cursor.fetchone()[0], "Antonia")
                if origem == 12:
                    self.cursor.execute(
                        "SELECT resposta FROM chatbot.respostas_desafios WHERE id_conversa=1 AND id_etapa=12"
                    )
                    self.assertEqual(self.cursor.fetchone()[0], "às vezes")
                self.cursor.execute(
                    "SELECT conteudo_texto, id_etapa FROM chatbot.historico_mensagens WHERE id_hash_msg='wamid.repeticao'"
                )
                self.assertEqual(
                    self.cursor.fetchone(), (envio["mensagem_bot"], destino)
                )
                self.cursor.execute(
                    "SELECT id_etapa FROM chatbot.historico_mensagens WHERE id_hash_msg='wamid.reacao'"
                )
                self.assertEqual(self.cursor.fetchone()[0], origem)
                self.cursor.execute(
                    "SELECT id_etapa, concluida_em FROM chatbot.followup_retomada"
                )
                etapa_checkpoint, concluida_em = self.cursor.fetchone()
                self.assertEqual(etapa_checkpoint, origem)
                self.assertIsNotNone(concluida_em)

                # Simula recuperação da mesma fila após outro ciclo já ter começado.
                self.cursor.execute(
                    "UPDATE chatbot.conversa SET followup_stage=1, followup_last_sent_at=%s, id_etapa_atual=10",
                    (self.agora + timedelta(hours=1),),
                )
                self.cursor.execute("SELECT to_jsonb(c) FROM chatbot.conversa c")
                antes_replay = self.cursor.fetchone()[0]
                contexto_banco = repo.reler_conversa(
                    contexto_banco, versao, self.cursor
                )
                contexto = preparar_retorno_followup(
                    mensagem, contexto_banco, self.cursor
                )
                self.assertIsNotNone(contexto["resposta_bot_para_mensagem_atual"])
                final = persistir_retorno_followup(
                    contexto,
                    {"enviou": False, "id_hash_msg_bot": "wamid.repeticao"},
                    self.cursor,
                )
                self.assertTrue(final["resposta_ja_existia"])
                self.assertEqual(final["id_etapa_resultante"], destino)
                self.cursor.execute("SELECT to_jsonb(c) FROM chatbot.conversa c")
                self.assertEqual(self.cursor.fetchone()[0], antes_replay)
                self.cursor.execute("SELECT count(*) FROM chatbot.historico_mensagens")
                self.assertEqual(self.cursor.fetchone()[0], 4)
                self.cursor.execute("ROLLBACK TO SAVEPOINT ciclo_reacao")

    def test_dois_processos_lock_recusa_e_fencing(self):
        # ROLLBACK remove apenas a fixture desta função. A conversa-base é confirmada.
        self.conn.rollback()
        ok, antiga = tentar_lock_conversa(1, self.cursor)
        self.assertTrue(ok)
        self.conn.commit()
        try:
            with psycopg.connect(DSN, connect_timeout=5) as outro:
                with outro.cursor() as cursor:
                    self.assertFalse(tentar_lock_conversa(1, cursor)[0])
                    cursor.execute(
                        "UPDATE chatbot.conversa SET processing_started_at=clock_timestamp()-INTERVAL '111 seconds' WHERE id_conversa=1"
                    )
                    ok, nova = tentar_lock_conversa(1, cursor)
                    self.assertTrue(ok)
                    self.assertGreater(nova, antiga)
            with self.assertRaises(repo.LockConversaPerdido):
                repo.proteger_conversa(1, antiga, self.cursor)
            self.assertFalse(unlock_conversa(1, antiga, self.cursor))
        finally:
            self.conn.rollback()
            self.cursor.execute(
                "UPDATE chatbot.conversa SET processing=FALSE, processing_started_at=NULL WHERE id_conversa=1"
            )
            self.conn.commit()


@unittest.skipUnless(DSN, "Defina FOLLOWUP_TEST_DSN para PostgreSQL local descartável")
class MigracaoLegadoPostgresTests(unittest.TestCase):
    def setUp(self):
        # Reutiliza a base real e as verificações de banco vazio/loopback.
        FollowupPostgresTests.setUpClass.__func__(type(self))
        self.addCleanup(self.limpar_banco)
        self.cursor.execute(
            "DROP TABLE chatbot.followup_envio, chatbot.followup_retomada, chatbot.followup_legado"
        )
        self.cursor.execute(
            """
            INSERT INTO chatbot.cliente(id_cliente, waid_telefone, nome)
            VALUES (2,'5511999999992','Bia'), (3,'5511999999993','Caio'), (4,'5511999999994','Davi');
            INSERT INTO chatbot.conversa(id_conversa,id_cliente,id_unidade,id_etapa_atual,status_ativa,followup_stage)
            VALUES (2,2,1,18,TRUE,NULL), (3,3,1,11,FALSE,0), (4,4,1,11,TRUE,2);
        """
        )
        self.conn.commit()

    def limpar_banco(self):
        FollowupPostgresTests.tearDownClass.__func__(type(self))

    def executar_migracao(self):
        self.cursor.execute(MIGRACAO.read_text(encoding="utf-8"), prepare=False)
        while self.cursor.nextset():
            pass

    def test_marca_ativas_preserva_dados_e_nao_reaplica(self):
        self.cursor.execute(
            "SELECT id_conversa, to_jsonb(c) FROM chatbot.conversa c ORDER BY id_conversa"
        )
        antes = dict(self.cursor.fetchall())
        self.conn.commit()
        self.executar_migracao()
        self.cursor.execute(
            "SELECT id_conversa, to_jsonb(c) FROM chatbot.conversa c ORDER BY id_conversa"
        )
        depois = dict(self.cursor.fetchall())
        for id_conversa, original in antes.items():
            esperado = dict(original)
            if original["status_ativa"]:
                esperado["followup_stage"] = 1
            self.assertEqual(depois[id_conversa], esperado)
        self.cursor.execute(
            "SELECT id_conversa,stage_anterior FROM chatbot.followup_legado ORDER BY id_conversa"
        )
        self.assertEqual(self.cursor.fetchall(), [(1, 0), (2, None), (4, 2)])
        self.cursor.execute(
            "SELECT (SELECT COUNT(*) FROM chatbot.followup_envio), (SELECT COUNT(*) FROM chatbot.historico_mensagens)"
        )
        self.assertEqual(self.cursor.fetchone(), (0, 0))
        self.cursor.execute(
            "UPDATE chatbot.conversa SET followup_stage=0 WHERE id_conversa=1"
        )
        self.cursor.execute(
            """
            INSERT INTO chatbot.cliente(id_cliente,waid_telefone) VALUES(5,'5511999999995');
            INSERT INTO chatbot.conversa(id_conversa,id_cliente,id_unidade,id_etapa_atual)
            VALUES(5,5,1,1);
        """
        )
        self.conn.commit()
        with self.assertRaises(psycopg.errors.DuplicateTable):
            self.executar_migracao()
        self.conn.rollback()
        self.cursor.execute(
            "SELECT id_conversa,followup_stage FROM chatbot.conversa WHERE id_conversa IN (1,5) ORDER BY id_conversa"
        )
        self.assertEqual(self.cursor.fetchall(), [(1, 0), (5, 0)])

    def test_legado_terminal_recusa_migracao_sem_marcar_ninguem(self):
        self.cursor.execute(
            "UPDATE chatbot.conversa SET id_etapa_atual=22 WHERE id_conversa=1"
        )
        self.conn.commit()
        with self.assertRaises(psycopg.errors.RaiseException):
            self.executar_migracao()
        self.conn.rollback()
        self.cursor.execute(
            "SELECT followup_stage FROM chatbot.conversa WHERE id_conversa=1"
        )
        self.assertEqual(self.cursor.fetchone(), (0,))
        self.cursor.execute("SELECT to_regclass('chatbot.followup_legado')")
        self.assertIsNone(self.cursor.fetchone()[0])


@unittest.skipUnless(DSN, "Defina FOLLOWUP_TEST_DSN para PostgreSQL local descartável")
class MigracaoSegundoFollowupTests(unittest.TestCase):
    def test_migracao_completa_preserva_dados_e_amplia_somente_motivo(self):
        FollowupPostgresTests.setUpClass.__func__(type(self))
        self.addCleanup(FollowupPostgresTests.tearDownClass.__func__, type(self))
        self.cursor.execute("""
            ALTER TABLE chatbot.conversa DROP CONSTRAINT ck_conversa_motivo_encerramento;
            ALTER TABLE chatbot.conversa ADD CONSTRAINT ck_conversa_motivo_encerramento
                CHECK(motivo_encerramento IS NULL OR motivo_encerramento IN
                    ('idade_invalida','foi_agendado','encaminhado_suporte_idoso'));
            SELECT to_jsonb(c) FROM chatbot.conversa c;
        """)
        while self.cursor.nextset():
            pass
        antes = self.cursor.fetchone()[0]
        with self.assertRaisesRegex(ValueError, "SCHEMA_SEGUNDO_FOLLOWUP_AUSENTE"):
            repo.validar_schema_followup(self.cursor)
        self.conn.commit()
        sql = (MIGRACAO.parent / "20260924_segundo_followup.sql").read_text(encoding="utf-8")
        self.cursor.execute(sql, prepare=False)
        while self.cursor.nextset():
            pass
        self.cursor.execute("SELECT to_jsonb(c) FROM chatbot.conversa c")
        self.assertEqual(self.cursor.fetchone()[0], antes)
        repo.validar_schema_followup(self.cursor)
        self.cursor.execute("UPDATE chatbot.conversa SET motivo_encerramento='followup_sem_resposta'")
        self.cursor.execute("SELECT motivo_encerramento FROM chatbot.conversa")
        self.assertEqual(self.cursor.fetchone()[0], "followup_sem_resposta")
        self.cursor.execute("SAVEPOINT motivo_invalido")
        with self.assertRaises(psycopg.errors.CheckViolation):
            self.cursor.execute("UPDATE chatbot.conversa SET motivo_encerramento='motivo_invalido'")
        self.cursor.execute("ROLLBACK TO SAVEPOINT motivo_invalido")


if __name__ == "__main__":
    unittest.main()
