"""DDL final e SQL de runtime; não executa migração nem usa banco de produção."""

from contextlib import contextmanager
from datetime import timedelta
import os
import unittest
from unittest.mock import patch

import psycopg
from tests.fixtures.fireads import aplicar_fireads
from psycopg.conninfo import conninfo_to_dict
from core.database.deploy_database import (
    bank_script,
    povoar_etapas,
    etapa_transicao_script,
)
from core.repositories.atendimento import followup
from core.repositories.atendimento.turnos import salvar_turno_conversa
from core.repositories.fluxo.contextos.etapa1 import buscar_contexto_etapa1
from core.repositories.fluxo.contextos.etapa6 import buscar_contexto_etapa6
from core.repositories.fluxo.contextos.etapa7 import buscar_contexto_etapa7
from core.repositories.fluxo.contextos.etapa9 import buscar_contexto_etapa9
from core.repositories.fluxo.contextos.etapa10 import buscar_contexto_etapa10
from core.repositories.fluxo.contextos.etapa18 import buscar_contexto_etapa18
from core.repositories.fluxo.contextos.etapa20 import buscar_contexto_etapa20
from core.repositories.funil import envios, leads
from core.repositories.monitoramento.painel import buscar_unidade, listar_conversas
from workers.worker_flow.transacoes.efeitos_transicao import (
    atualizar_banco_conforme_transicao_de_etapa,
)

DSN = os.environ.get("RESERVA_LINK_TEST_DSN")


@unittest.skipUnless(DSN, "Exige banco loopback vazio test_chatbot_reserva_link")
class ReservaLinkPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        params = conninfo_to_dict(DSN)
        locais = {"127.0.0.1", "::1", "localhost"}
        if (
            params.get("host") not in locais
            or params.get("dbname") != "test_chatbot_reserva_link"
            or params.get("service")
            or (params.get("hostaddr") and params["hostaddr"] not in locais)
        ):
            raise RuntimeError(
                "Teste exige loopback explícito e test_chatbot_reserva_link"
            )
        cls.conn = psycopg.connect(DSN, connect_timeout=5)
        cls.cursor = cls.conn.cursor()
        if (
            cls.conn.info.host not in locais
            or cls.conn.info.dbname != "test_chatbot_reserva_link"
        ):
            cls.conn.close()
            raise RuntimeError("Conexão efetiva não corresponde ao banco de teste")
        if (
            cls.conn.execute("SELECT to_regnamespace('chatbot')").fetchone()[0]
            is not None
        ):
            cls.conn.close()
            raise RuntimeError("Recusado schema chatbot preexistente")
        cls.conn.execute(
            "CREATE SCHEMA chatbot; CREATE TABLE chatbot.auth_user(id SERIAL PRIMARY KEY)"
        )

        @contextmanager
        def transacao(*_):
            yield cls.cursor

        with patch.object(bank_script, "transacao_deploy", transacao), patch.object(
            povoar_etapas, "transacao_deploy", transacao
        ), patch.object(etapa_transicao_script, "transacao_deploy", transacao):
            bank_script.criar_tabelas()
            povoar_etapas.insere_etapa_once()
            etapa_transicao_script.criar_e_povoar_transicoes_etapa()
        cls.conn.execute("""
            CREATE TABLE chatbot.cliente_bloqueado_meta(wa_id_cliente TEXT, phone_id_unidade TEXT);
            CREATE TABLE chatbot.webhook_flood_evento(wa_id_cliente TEXT, phone_id_unidade TEXT, received_at TIMESTAMPTZ);
            INSERT INTO chatbot.unidade(id_unidade,nome_unidade,nome_agente,genero,cnpj,email_responsavel,
                telefone,numero_comercial,waba_id,phone_number_id,link_agendamento)
            VALUES (1,'Unidade','Suh','feminino','cnpj','unidade@example.com','5571888888888',
                '5571999999999','waba','phone',NULL);
            INSERT INTO chatbot.cliente(id_cliente,nome,waid_telefone,idade,email)
                VALUES (1,'Ana','5571777777777',40,'ana@example.com');
            INSERT INTO chatbot.conversa(id_conversa,id_cliente,id_unidade,id_etapa_atual,profissao)
                VALUES (1,1,1,17,'Professora');
            INSERT INTO chatbot.integracao_funil_unidade(id_unidade,nome_widget,codigo_widget,link_api_carrossel,codigo_canal_venda)
                VALUES (1,'Widget','cod','https://example.com/api','canal');
        """)
        aplicar_fireads(cls.cursor)
        cls.conn.commit()

    @classmethod
    def tearDownClass(cls):
        cls.conn.rollback()
        cls.conn.execute("DROP SCHEMA chatbot CASCADE")
        cls.conn.commit()
        cls.conn.close()

    def tearDown(self):
        self.conn.rollback()

    def configurar(self, link, etapa):
        self.cursor.execute(
            "UPDATE chatbot.atendimento_customizado SET link_agendamento=%s WHERE id_unidade=1", (link,)
        )
        self.cursor.execute(
            "UPDATE chatbot.conversa SET id_etapa_atual=%s,lead_no_funil=FALSE WHERE id_conversa=1",
            (etapa,),
        )
        self.cursor.execute("DELETE FROM chatbot.funil_envios")

    def test_matriz_funil_na_fila_claim_leitura_e_confirmacao(self):
        for link in (None, "", "https://example.com"):
            for etapa in range(17, 25):
                with self.subTest(link=link, etapa=etapa):
                    self.configurar(link, etapa)
                    esperado = etapa >= 20 if link else etapa == 19 or etapa >= 21
                    self.assertEqual(
                        envios.sincronizar_envios_elegiveis(self.cursor), int(esperado)
                    )
                    envio = envios.reivindicar_proximo_envio(self.cursor)
                    lead = leads.buscar_dados_lead_funil(1, self.cursor)
                    self.assertEqual(envio is not None, esperado)
                    self.assertEqual(lead is not None, esperado)
                    if esperado:
                        self.assertEqual(lead["link_agendamento"], link or None)
                        self.assertTrue(
                            envios.marcar_envio_como_concluido(
                                envio["id_funil_envio"], 1, "ok", self.cursor
                            )
                        )
                        self.assertEqual(
                            envios.sincronizar_envios_elegiveis(self.cursor), 0
                        )

    def test_funil_pendente_revalida_link_adicionado(self):
        self.configurar(None, 19)
        self.assertEqual(envios.sincronizar_envios_elegiveis(self.cursor), 1)
        self.conn.execute(
            "UPDATE chatbot.atendimento_customizado SET link_agendamento='https://example.com' WHERE id_unidade=1"
        )
        self.assertIsNone(envios.reivindicar_proximo_envio(self.cursor))
        self.assertIsNone(leads.buscar_dados_lead_funil(1, self.cursor))
        self.conn.execute(
            "UPDATE chatbot.conversa SET id_etapa_atual=21 WHERE id_conversa=1"
        )
        self.assertIsNotNone(envios.reivindicar_proximo_envio(self.cursor))

    def test_aceite_externo_e_confirmado_mesmo_com_link_adicionado(self):
        self.configurar(None, 19)
        self.assertEqual(envios.sincronizar_envios_elegiveis(self.cursor), 1)
        envio = envios.reivindicar_proximo_envio(self.cursor)
        self.assertIsNotNone(leads.buscar_dados_lead_funil(1, self.cursor))
        # Simula a alteração após o despacho que o CRM confirmou com sucesso.
        self.conn.execute(
            "UPDATE chatbot.atendimento_customizado SET link_agendamento='https://example.com' WHERE id_unidade=1"
        )
        self.assertTrue(
            envios.marcar_envio_como_concluido(
                envio["id_funil_envio"],
                1,
                "ok",
                self.cursor,
            )
        )
        self.conn.execute(
            "UPDATE chatbot.conversa SET id_etapa_atual=21 WHERE id_conversa=1"
        )
        self.assertEqual(envios.sincronizar_envios_elegiveis(self.cursor), 0)
        self.assertIsNone(envios.reivindicar_proximo_envio(self.cursor))

    def test_limites_followup_por_configuracao_e_releitura(self):
        agora = self.conn.execute("SELECT clock_timestamp()").fetchone()[0]
        ancora = agora - timedelta(hours=7, minutes=1)
        self.cursor.execute(
            """
            INSERT INTO chatbot.historico_mensagens(id_conversa,id_etapa,received_data_hora,cliente_telefone,
                conteudo_texto,tipo_mensagem,id_hash_msg,id_phone_unidade,unidade_telefone,quem_enviou,status_envio)
            VALUES (1,17,%s,'5571777777777','Oi','text','wamid.cliente','phone','5571888888888','cliente',NULL),
                   (1,17,%s,'5571777777777','Pergunta','text','wamid.bot','phone','5571888888888','bot','sent');
            """,
            (ancora - timedelta(minutes=1), ancora),
        )
        self.cursor.execute(
            "UPDATE chatbot.conversa SET last_message_from='bot',last_interaction_at=%s WHERE id_conversa=1",
            (ancora,),
        )
        for link in (None, "", "https://example.com"):
            for etapa in (1, 17, 18, 19, 20, 21, 24):
                with self.subTest(link=link, etapa=etapa):
                    self.configurar(link, etapa)
                    esperado = etapa <= 17 or etapa == 18 and not link
                    self.assertEqual(
                        followup.reler_elegivel(1, self.cursor) is not None, esperado
                    )
        self.configurar(None, 18)
        self.assertIsNotNone(followup.reler_elegivel(1, self.cursor))
        self.conn.execute(
            "UPDATE chatbot.atendimento_customizado SET link_agendamento='https://example.com' WHERE id_unidade=1"
        )
        self.assertIsNone(followup.reler_elegivel(1, self.cursor))

    def test_turno_dominio_rollback_e_replay(self):
        self.configurar(None, 18)
        for turno in ("manha", "tarde", "noite"):
            with self.conn.transaction():
                self.conn.execute(
                    "UPDATE chatbot.conversa SET turno=NULL WHERE id_conversa=1"
                )
                self.assertTrue(
                    salvar_turno_conversa(1, 1, turno, self.cursor)["turno_persistido"]
                )
                self.assertTrue(
                    salvar_turno_conversa(1, 1, turno, self.cursor)["turno_persistido"]
                )
        self.conn.execute("UPDATE chatbot.conversa SET turno=NULL WHERE id_conversa=1")
        for invalido in ("manha/tarde", "dia", "manhã"):
            with self.assertRaises(psycopg.Error), self.conn.transaction():
                self.conn.execute(
                    "UPDATE chatbot.conversa SET turno=%s WHERE id_conversa=1",
                    (invalido,),
                )
        with self.assertRaisesRegex(RuntimeError, "simulada"), self.conn.transaction():
            self.conn.execute(
                "UPDATE chatbot.conversa SET id_etapa_atual=19 WHERE id_conversa=1"
            )
            atualizar_banco_conforme_transicao_de_etapa(
                {
                    "id_conversa": 1,
                    "id_unidade": 1,
                    "id_etapa_origem_transicao": 18,
                    "texto_cliente_atual": "Pela manhã",
                    "tipo_mensagem_atual": "text",
                },
                {
                    "id_etapa_resultante": 19,
                    "evento_transicao": "turno_escolhido",
                    "resposta_ja_existia": True,
                },
                self.cursor,
            )
            raise RuntimeError("Falha final simulada")
        self.assertEqual(
            self.conn.execute(
                "SELECT id_etapa_atual,turno FROM chatbot.conversa WHERE id_conversa=1"
            ).fetchone(),
            (18, None),
        )

    def test_contexto_painel_e_funil_expoem_turno_sem_cruzar_unidades(self):
        # A plataforma ainda é obrigatória para um novo envio na etapa 20.
        # Removê-la não deve improvisar uma mudança de rota no atendimento ativo.
        self.configurar("https://example.com", 20)
        self.assertEqual(
            buscar_contexto_etapa20(1, 1, self.cursor)["link_agendamento_unidade"],
            "https://example.com",
        )
        self.configurar(None, 20)
        with self.assertRaisesRegex(ValueError, "sem link de agendamento"):
            buscar_contexto_etapa20(1, 1, self.cursor)
        self.configurar(None, 19)
        salvar_turno_conversa(1, 1, "noite", self.cursor)
        self.assertEqual(buscar_contexto_etapa18(1, 1, self.cursor)["turno"], "noite")
        self.assertEqual(
            leads.buscar_dados_lead_funil(1, self.cursor)["turno"], "noite"
        )
        with self.assertRaises(ValueError):
            buscar_contexto_etapa18(1, 2, self.cursor)
        self.conn.execute("""
            INSERT INTO chatbot.historico_mensagens(id_conversa,id_etapa,received_data_hora,cliente_telefone,
                conteudo_texto,tipo_mensagem,id_hash_msg,id_phone_unidade,unidade_telefone,quem_enviou)
            VALUES (1,18,NOW(),'5571777777777','Pela noite','text','wamid.cliente','phone','5571888888888','cliente')
        """)
        fim = self.conn.execute(
            "SELECT clock_timestamp() + INTERVAL '1 minute'"
        ).fetchone()[0]
        dados = listar_conversas(1, None, fim, self.cursor)
        self.assertEqual(dados[0]["turno"], "noite")
        self.assertEqual(listar_conversas(2, None, fim, self.cursor), [])

    def test_personalizacao_direta_preserva_contextos_e_isolamento(self):
        self.assertIsNone(self.conn.execute(
            "SELECT to_regclass('chatbot.unidade_atendimento')"
        ).fetchone()[0])
        self.conn.execute("""
            INSERT INTO chatbot.unidade(id_unidade,nome_unidade,cnpj,email_responsavel,
                telefone,waba_id,phone_number_id)
            VALUES(2,'Outra unidade','outro-cnpj','outra@example.com',
                '5571666666666','outro-waba','outro-phone');
            INSERT INTO chatbot.atendimento_customizado
                (id_unidade,nome_agente,genero,numero_comercial)
            VALUES(2,'Outro agente','masculino','5571555555555');
            UPDATE chatbot.atendimento_customizado
            SET nome_agente='Dora',genero='feminino',bpa_ativo=TRUE,
                idade_minima_suporte=70,email_obrigatorio=FALSE,
                link_instagram='https://example.com/instagram',
                link_agendamento='https://example.com/reserva'
            WHERE id_unidade=1;
            UPDATE chatbot.conversa SET id_etapa_atual=7,status_dependente=FALSE
            WHERE id_conversa=1;
            INSERT INTO chatbot.dependente(id_cliente,id_conversa,nome_dependente,idade)
            VALUES(1,1,'Pedro',7);
        """)
        self.assertEqual(buscar_contexto_etapa1(1, self.cursor), {
            'nome_unidade': 'Unidade', 'nome_agente': 'Dora', 'genero': 'feminino',
        })
        self.assertEqual(buscar_contexto_etapa1(2, self.cursor)['nome_agente'], 'Outro agente')
        funcoes = (buscar_contexto_etapa6, buscar_contexto_etapa7, buscar_contexto_etapa9,
                   buscar_contexto_etapa10, buscar_contexto_etapa18, buscar_contexto_etapa20)
        for dependente in (False, True):
            self.conn.execute('UPDATE chatbot.conversa SET status_dependente=%s WHERE id_conversa=1', (dependente,))
            idade = buscar_contexto_etapa6(1, 1, self.cursor)
            self.assertEqual((idade['nome_agente'], idade['bpa_ativo_unidade'], idade['idade_minima_suporte']),
                             ('Dora', True, 70))
            for consulta in (buscar_contexto_etapa7, buscar_contexto_etapa9):
                self.assertEqual(consulta(1, 1, self.cursor)['link_instagram_unidade'], 'https://example.com/instagram')
            email = buscar_contexto_etapa10(1, 1, self.cursor)
            self.assertFalse(email['email_obrigatorio_unidade'])
            self.assertEqual(email['nome_dependente'], 'Pedro' if dependente else None)
            self.assertEqual(buscar_contexto_etapa18(1, 1, self.cursor)['nome_agente_unidade'], 'Dora')
            self.assertEqual(buscar_contexto_etapa20(1, 1, self.cursor)['link_agendamento_unidade'], 'https://example.com/reserva')
            self.assertEqual(followup.buscar_contexto_repeticao(1, 1, self.cursor)['nome_agente'], 'Dora')
            for consulta in funcoes:
                with self.subTest(consulta=consulta.__name__, dependente=dependente):
                    with self.assertRaises(ValueError):
                        consulta(1, 2, self.cursor)
        self.conn.execute("UPDATE chatbot.atendimento_customizado SET nome_agente='Lia',email_obrigatorio=TRUE WHERE id_unidade=1")
        self.assertEqual(buscar_contexto_etapa1(1, self.cursor)['nome_agente'], 'Lia')
        self.assertTrue(buscar_contexto_etapa10(1, 1, self.cursor)['email_obrigatorio_unidade'])
        self.assertEqual(buscar_unidade(1, self.cursor)['nome_agente'], 'Lia')
        self.assertEqual(buscar_unidade(2, self.cursor)['nome_agente'], 'Outro agente')
