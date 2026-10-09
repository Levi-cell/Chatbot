"""FireAds em PostgreSQL local descartável; apenas HTTP é substituído."""

from contextlib import contextmanager, ExitStack
from datetime import timedelta
import os
import unittest
from unittest.mock import Mock, patch

import psycopg
from psycopg.conninfo import conninfo_to_dict

from core.database.deploy_database import (
    bank_script,
    povoar_etapas,
    etapa_transicao_script,
)
from core.repositories.atendimento.conversas import (
    inserindo_em_conversa_caso_seja_nova,
    tentar_lock_conversa,
)
from core.repositories.atendimento.followup import LockConversaPerdido
from core.repositories.fireads import consulta, envios
from core.repositories.funil.leads import buscar_dados_lead_funil
from core.integrations.funil.oportunidades import montar_payload_oportunidade
from core.integrations.fireads.contrato import bloco_observacoes
from workers.worker_flow.fireads import preparar_abertura, interpretar
from workers.worker_funil.fireads import processar
from tests.fixtures.fireads import MIGRACAO_FIREADS, aplicar_fireads

DSN = os.environ.get("FIREADS_TEST_DSN")
NUMERO = "5511999990002"
GOOGLE = {
    "Nome": "Ana Paula Silva",
    "Email": "ana@example.com",
    "WhatsApp": NUMERO,
    "Perfil/Faixa": "Para mim",
    "Data/Hora": "08/10/2026 12:00",
}


@unittest.skipUnless(
    DSN, "Exige FIREADS_TEST_DSN local e banco vazio test_chatbot_fireads"
)
class FireAdsPostgresTests(unittest.TestCase):
    def setUp(self):
        params = conninfo_to_dict(DSN)
        locais = {"127.0.0.1", "::1", "localhost"}
        if (
            params.get("host") not in locais
            or params.get("dbname") != "test_chatbot_fireads"
            or params.get("service")
            or (params.get("hostaddr") and params["hostaddr"] not in locais)
        ):
            raise RuntimeError("FireAds exige banco descartável explícito em loopback")
        self.conn = psycopg.connect(DSN, connect_timeout=5)
        self.addCleanup(self.conn.close)
        if (
            self.conn.info.host not in locais
            or self.conn.info.dbname != "test_chatbot_fireads"
        ):
            raise RuntimeError("Destino efetivo não é o banco de teste")
        if (
            self.conn.execute("SELECT to_regnamespace('chatbot')").fetchone()[0]
            is not None
        ):
            raise RuntimeError("Recusado schema chatbot preexistente")
        self.addCleanup(self.limpar)
        self.cursor = self.conn.cursor()
        self.cursor.execute(
            "CREATE SCHEMA chatbot; CREATE TABLE chatbot.auth_user(id SERIAL PRIMARY KEY)"
        )

        @contextmanager
        def transacao(*_):
            yield self.cursor

        with ExitStack() as stack:
            for module in (bank_script, povoar_etapas, etapa_transicao_script):
                stack.enter_context(patch.object(module, "transacao_deploy", transacao))
            bank_script.criar_tabelas()
            bank_script.criar_funcoes_lock()
            povoar_etapas.insere_etapa_once()
            etapa_transicao_script.criar_e_povoar_transicoes_etapa()
        self.cursor.execute("""
            INSERT INTO chatbot.unidade(nome_unidade,nome_agente,genero,cnpj,email_responsavel,
                telefone,numero_comercial,waba_id,phone_number_id)
            VALUES('Teste FireAds','Dora','feminino','teste','unidade@example.com',
                '5511999990000','5511999990001','waba-teste','phone-teste');
            INSERT INTO chatbot.cliente(nome,waid_telefone,email) VALUES('Antigo','5511999990002','antigo@example.com');
            INSERT INTO chatbot.conversa(id_cliente,id_unidade,status_ativa) VALUES(1,1,FALSE);
        """)
        aplicar_fireads(self.cursor)
        self.cursor.execute("""
            INSERT INTO chatbot.integracao_fireads(id_unidade,url_dashbord,contrato_validado,integracao_ativa)
            VALUES(1,'https://script.google.com/macros/s/teste/exec',TRUE,TRUE);
            INSERT INTO chatbot.integracao_funil_unidade(id_unidade,nome_widget,codigo_widget,
                link_api_carrossel,codigo_canal_venda)
            VALUES(1,'Teste','TESTE','https://example.com/api','113340');
        """)
        self.conn.commit()

    def limpar(self):
        self.conn.rollback()
        self.conn.execute("DROP SCHEMA IF EXISTS chatbot CASCADE")
        self.conn.commit()

    def nova_conversa(self):
        cid = inserindo_em_conversa_caso_seja_nova(1, 1, self.cursor)
        self.conn.commit()
        return cid

    def test_unidade_desativada_nao_consulta_fireads(self):
        cid, mensagem, versao, contexto = self.preparar_mensagem()
        self.cursor.execute("UPDATE chatbot.unidade SET status_pagamento=FALSE")
        self.conn.commit()
        with patch("workers.worker_flow.fireads.ClienteFireAds") as api:
            self.assertEqual(preparar_abertura(contexto, mensagem, versao, self.conn, self.cursor), contexto)
        api.assert_not_called()
        self.assertEqual(self.conn.execute("SELECT count(*) FROM chatbot.consulta_fireads").fetchone()[0], 0)

    def test_desativacao_suspende_funil_e_dash_preservando_pendencias(self):
        from core.repositories.funil import envios as funil
        envio = self.preparar_envio()
        cid = envio["conversa"]
        self.cursor.execute("UPDATE chatbot.conversa SET lead_no_funil=FALSE WHERE id_conversa=%s", (cid,))
        self.assertEqual(funil.sincronizar_envios_elegiveis(self.cursor), 1)
        self.cursor.execute("UPDATE chatbot.conversa SET lead_no_funil=TRUE WHERE id_conversa=%s", (cid,))
        self.cursor.execute("UPDATE chatbot.unidade SET status_pagamento=FALSE")
        self.conn.commit()
        with patch("workers.worker_funil.fireads.ClienteFireAds") as api:
            self.assertFalse(processar(envio, self.conn, self.cursor))
        api.assert_not_called()
        for status in (False, None):
            self.cursor.execute("UPDATE chatbot.unidade SET status_pagamento=%s", (status,))
            self.cursor.execute("UPDATE chatbot.envios_dash SET next_attempt_at=clock_timestamp()")
            self.assertIsNone(envios.reservar(self.cursor))
            self.cursor.execute("UPDATE chatbot.conversa SET lead_no_funil=FALSE WHERE id_conversa=%s", (cid,))
            self.assertIsNone(funil.reivindicar_proximo_envio(self.cursor))
            self.assertIsNone(buscar_dados_lead_funil(cid, self.cursor))
            self.cursor.execute("UPDATE chatbot.conversa SET lead_no_funil=TRUE WHERE id_conversa=%s", (cid,))
        self.assertEqual(self.conn.execute("SELECT status,snapshot FROM chatbot.envios_dash").fetchone(), ("pending", envio["snapshot"]))
        self.assertEqual(self.conn.execute("SELECT status FROM chatbot.funil_envios").fetchone(), ("pending",))
        self.cursor.execute("UPDATE chatbot.unidade SET status_pagamento=TRUE")
        self.assertIsNotNone(envios.reservar(self.cursor))

    def test_migracao_dequeue_pula_inativas_sem_perder_ordem_ou_retry(self):
        from pathlib import Path
        migration = Path(__file__).resolve().parents[2] / 'deploy/migrations/20261009_status_pagamento_workers.sql'
        self.conn.commit()
        # Usa o mesmo arquivo que será aplicado no DBeaver e confirma reexecução.
        self.conn.execute(migration.read_text(encoding='utf-8'), prepare=False)
        self.conn.execute(migration.read_text(encoding='utf-8'), prepare=False)
        cid, mensagem, _, _ = self.preparar_mensagem()
        self.cursor.execute("UPDATE chatbot.fila_mensagens SET status='pending',retry_count=0,processing_started_at=NULL,next_attempt_at=clock_timestamp()-INTERVAL '1 minute'")
        self.cursor.execute("""
            INSERT INTO chatbot.unidade(nome_unidade,cnpj,email_responsavel,telefone,waba_id,phone_number_id)
            VALUES('Unidade ativa','outro','outro@example.com','5511999990003','outro','phone-ativo');
            INSERT INTO chatbot.atendimento_customizado(id_unidade,nome_agente,genero,numero_comercial)
            SELECT id_unidade,'Agente','masculino','5511999990004' FROM chatbot.unidade WHERE phone_number_id='phone-ativo';
            INSERT INTO chatbot.fila_mensagens(cliente_telefone,conteudo_texto,tipo_mensagem,id_phone_unidade,unidade_telefone,
                id_hash_msg,received_data_hora,status,next_attempt_at)
            VALUES('5511999990005','Oi','text','phone-ativo','5511999990003','wamid.ativa',clock_timestamp(),'pending',clock_timestamp());
            UPDATE chatbot.unidade SET status_pagamento=FALSE WHERE id_unidade=1;
        """)
        self.conn.commit()
        row = self.conn.execute("SELECT * FROM chatbot.dequeue_message()").fetchone()
        self.assertEqual(row[4], 'phone-ativo')
        self.cursor.execute("UPDATE chatbot.fila_mensagens SET status='sent',processing_started_at=NULL WHERE id_mensagem=%s", (row[0],))
        for status in (False, None):
            self.cursor.execute("UPDATE chatbot.unidade SET status_pagamento=%s WHERE id_unidade=1", (status,))
            self.assertIsNone(self.conn.execute("SELECT * FROM chatbot.dequeue_message()").fetchone())
        self.assertEqual(self.conn.execute("SELECT status,retry_count FROM chatbot.fila_mensagens WHERE id_mensagem=%s", (mensagem['id_mensagem'],)).fetchone(), ('pending', 0))
        self.cursor.execute("UPDATE chatbot.unidade SET status_pagamento=TRUE WHERE id_unidade=1")
        retomada = self.conn.execute("SELECT * FROM chatbot.dequeue_message()").fetchone()
        self.assertEqual(retomada[0], mensagem['id_mensagem'])
        from core.repositories.atendimento.fila import reagendar_mensagem_sem_erro
        self.assertEqual(reagendar_mensagem_sem_erro(
            retomada[0], self.cursor, retry_esperado=retomada[-1] - 1,
        ), 0)
        self.assertEqual(reagendar_mensagem_sem_erro(
            retomada[0], self.cursor, retry_esperado=retomada[-1],
        ), 1)
        self.cursor.execute("UPDATE chatbot.fila_mensagens SET status='sent' WHERE id_mensagem=%s", (retomada[0],))
        self.assertEqual(reagendar_mensagem_sem_erro(
            retomada[0], self.cursor, retry_esperado=retomada[-1],
        ), 0)

    def preparar_mensagem(self):
        cid = self.nova_conversa()
        self.cursor.execute(
            """INSERT INTO chatbot.fila_mensagens
            (cliente_telefone,conteudo_texto,tipo_mensagem,id_phone_unidade,unidade_telefone,
             id_hash_msg,id_conversa,status,retry_count,processing_started_at,received_data_hora)
            VALUES(%s,'Oi','text','phone-teste','5511999990000','wamid.fireads',%s,'processing',1,clock_timestamp(),clock_timestamp())
            RETURNING id_mensagem""",
            (NUMERO, cid),
        )
        mensagem = {
            "id_mensagem": self.cursor.fetchone()[0],
            "retry_count": 1,
            "cliente_telefone": NUMERO,
        }
        ok, versao = tentar_lock_conversa(cid, self.cursor)
        self.assertTrue(ok)
        self.conn.commit()
        contexto = {
            "id_cliente": 1,
            "id_unidade": 1,
            "conversa": {"id_conversa": cid, "id_etapa_atual": None},
        }
        return cid, mensagem, versao, contexto

    def importar(self, cid):
        abertura = consulta.buscar_abertura(cid, self.cursor)
        ident = consulta.reservar_consulta(abertura, cid, self.cursor)
        return consulta.concluir_consulta(
            abertura, cid, ident, interpretar([GOOGLE], [], NUMERO, None), self.cursor
        )

    def preparar_envio(self):
        cid = self.nova_conversa()
        estado = self.importar(cid)
        self.cursor.execute(
            """UPDATE chatbot.conversa SET id_etapa_atual=19,turno='manha',
            profissao='Professora',status_dependente=FALSE WHERE id_conversa=%s""",
            (cid,),
        )
        self.cursor.execute("UPDATE chatbot.cliente SET idade=35 WHERE id_cliente=1")
        self.cursor.execute(
            """INSERT INTO chatbot.respostas_desafios(id_conversa,id_etapa,resposta)
            SELECT %s,etapa,'Às vezes' FROM generate_series(12,17) etapa""",
            (cid,),
        )
        consulta.guardar_coletas(
            {"id_cliente": 1, "id_conversa": cid, "contexto_fireads": estado},
            {"destino_dado": "cliente"},
            self.cursor,
        )
        dados = buscar_dados_lead_funil(cid, self.cursor)
        self.assertEqual(dados["nome_cliente"], "Ana Paula")
        self.assertEqual(dados["idade_cliente"], 35)
        payload = montar_payload_oportunidade(dados)
        esperado = {
            "codigo_canal_venda": "113340",
            "link_api_carrossel": "https://example.com/api",
        }
        original = envios.congelar(dados, payload, esperado, self.cursor)
        self.assertEqual(original[1], "113336")
        self.assertEqual(envios.congelar(dados, {}, esperado, self.cursor), original)
        self.assertIsNone(envios.reservar(self.cursor))  # Funil ainda não confirmou.
        self.cursor.execute(
            "UPDATE chatbot.conversa SET lead_no_funil=TRUE WHERE id_conversa=%s",
            (cid,),
        )
        envio = envios.reservar(self.cursor)
        self.conn.commit()
        return envio

    def test_migracao_preserva_personalizacao_conversas_e_reexecuta(self):
        remocao = MIGRACAO_FIREADS.with_name('20261009_remover_view_unidade_atendimento.sql')
        for _ in range(2):
            self.conn.execute(remocao.read_text(encoding='utf-8'), prepare=False)
        self.conn.execute(MIGRACAO_FIREADS.read_text(encoding="utf-8"), prepare=False)
        self.assertIsNone(self.conn.execute(
            "SELECT to_regclass('chatbot.unidade_atendimento')"
        ).fetchone()[0])
        self.assertEqual(self.conn.execute(
            "SELECT versao FROM chatbot.migracoes_fireads"
        ).fetchall(), [('20261007_fireads_v1',)])
        self.assertEqual(
            self.conn.execute(
                "SELECT ac.nome_agente FROM chatbot.unidade u "
                "JOIN chatbot.atendimento_customizado ac ON ac.id_unidade=u.id_unidade"
            ).fetchone(),
            ("Dora",),
        )
        self.assertEqual(
            self.conn.execute(
                "SELECT id_conversa,id_chat FROM chatbot.conversa"
            ).fetchall(),
            [(1, 1)],
        )
        self.nova_conversa()
        self.assertEqual(
            self.conn.execute("SELECT count(*) FROM chatbot.chat").fetchone()[0], 1
        )
        self.assertEqual(
            self.conn.execute(
                "SELECT count(*) FROM chatbot.etapa_transicao"
            ).fetchone()[0],
            30,
        )

    def test_importacao_dependente_e_retry_recuperam_snapshot(self):
        cid, mensagem, versao, contexto = self.preparar_mensagem()
        api = Mock()
        api.consultar.side_effect = [
            {
                "headers": list(GOOGLE),
                "rows": [dict(GOOGLE, **{"Perfil/Faixa": "Para outra pessoa"})],
            },
            {
                "headers": ["full_name", "email", "phone_number", "para_quem"],
                "rows": [],
            },
        ]
        with patch("workers.worker_flow.fireads.ClienteFireAds", return_value=api):
            obtido = preparar_abertura(
                contexto, mensagem, versao, self.conn, self.cursor
            )
        self.assertTrue(obtido["conversa"]["status_dependente"])
        self.assertEqual(
            self.conn.execute("SELECT nome,email FROM chatbot.cliente").fetchone(),
            ("Ana Paula", "ana@example.com"),
        )
        self.assertEqual(
            self.conn.execute(
                "SELECT count(*) FROM chatbot.dependente WHERE id_conversa=%s", (cid,)
            ).fetchone()[0],
            1,
        )
        with patch("workers.worker_flow.fireads.ClienteFireAds") as http:
            self.assertEqual(
                preparar_abertura(contexto, mensagem, versao, self.conn, self.cursor),
                obtido,
            )
            http.assert_not_called()

    def test_lock_perdido_durante_http_nao_importa_dados(self):
        cid, mensagem, versao, contexto = self.preparar_mensagem()

        def resposta(aba):
            if "Google" in aba:
                with psycopg.connect(DSN) as outro:
                    outro.execute(
                        "UPDATE chatbot.conversa SET lock_version=lock_version+1 WHERE id_conversa=%s",
                        (cid,),
                    )
                return {"headers": list(GOOGLE), "rows": [GOOGLE]}
            return {
                "headers": ["full_name", "email", "phone_number", "para_quem"],
                "rows": [],
            }

        api = Mock()
        api.consultar.side_effect = resposta
        with patch("workers.worker_flow.fireads.ClienteFireAds", return_value=api):
            with self.assertRaises(LockConversaPerdido):
                preparar_abertura(contexto, mensagem, versao, self.conn, self.cursor)
        self.conn.rollback()
        self.assertEqual(
            self.conn.execute("SELECT nome FROM chatbot.cliente").fetchone()[0],
            "Antigo",
        )
        self.assertIsNone(
            self.conn.execute(
                "SELECT origem_fireads FROM chatbot.conversa WHERE id_conversa=%s",
                (cid,),
            ).fetchone()[0]
        )

    def test_nova_conversa_atualiza_consulta_sem_apagar_contexto_anterior(self):
        cid = self.nova_conversa()
        antigo = self.importar(cid)
        self.cursor.execute(
            "UPDATE chatbot.conversa SET status_ativa=FALSE WHERE id_conversa=%s",
            (cid,),
        )
        novo = self.nova_conversa()
        atual = self.importar(novo)
        self.assertEqual(atual["id_consulta"], antigo["id_consulta"])
        self.assertEqual(
            self.conn.execute(
                "SELECT contexto_fireads FROM chatbot.conversa WHERE id_conversa=%s",
                (cid,),
            ).fetchone()[0],
            antigo,
        )
        self.assertEqual(
            self.conn.execute(
                "SELECT id_conversa_referencia FROM chatbot.consulta_fireads"
            ).fetchone()[0],
            novo,
        )

    def test_retry_dash_reconcilia_bloco_sem_segundo_post(self):
        envio = self.preparar_envio()
        snap = envio["snapshot"]
        bloco = bloco_observacoes(
            envio["integracao"], envio["conversa"], snap["observacoes"]
        )
        api = Mock()
        api.consultar.return_value = {
            "headers": ["Nome", "Email", "WhatsApp", "Observação"],
            "rows": [
                {
                    "_row": 2,
                    "Nome": "Ana",
                    "Email": "ana@example.com",
                    "WhatsApp": NUMERO,
                    "Observação": "FR002\n\n" + bloco,
                }
            ],
        }
        with patch("workers.worker_funil.fireads.ClienteFireAds", return_value=api):
            self.assertTrue(processar(envio, self.conn, self.cursor))
        api.enviar.assert_not_called()
        self.assertTrue(
            self.conn.execute(
                "SELECT lead_no_dash FROM chatbot.conversa WHERE id_conversa=%s",
                (envio["conversa"],),
            ).fetchone()[0]
        )

    def test_falha_dash_fica_pending_preserva_funil_e_nao_tenta_no_mesmo_ciclo(self):
        envio = self.preparar_envio()
        api = Mock()
        api.consultar.side_effect = TimeoutError("teste")
        with patch("workers.worker_funil.fireads.ClienteFireAds", return_value=api):
            self.assertFalse(processar(envio, self.conn, self.cursor))
        self.assertEqual(
            self.conn.execute("SELECT status FROM chatbot.envios_dash").fetchone()[0],
            "pending",
        )
        self.assertIsNone(envios.reservar(self.cursor))
        self.assertTrue(
            self.conn.execute(
                "SELECT lead_no_funil FROM chatbot.conversa WHERE id_conversa=%s",
                (envio["conversa"],),
            ).fetchone()[0]
        )

    def test_reserva_concorrente_nao_e_reivindicada_e_configuracao_mudada_bloqueia(
        self,
    ):
        envio = self.preparar_envio()
        with psycopg.connect(DSN) as outro:
            self.assertIsNone(envios.reservar(outro.cursor()))
        self.cursor.execute(
            "UPDATE chatbot.integracao_fireads SET aba_destino='Outra aba'"
        )
        self.conn.commit()
        with patch("workers.worker_funil.fireads.ClienteFireAds") as http:
            self.assertFalse(processar(envio, self.conn, self.cursor))
            http.assert_not_called()

    def test_personalizacao_obrigatoria_e_chat_nao_cruza_unidades(self):
        with self.assertRaises(psycopg.errors.RaiseException):
            self.conn.execute("DELETE FROM chatbot.atendimento_customizado")
            self.conn.commit()
        self.conn.rollback()
        with self.assertRaises(psycopg.errors.UniqueViolation):
            self.conn.execute(
                "INSERT INTO chatbot.chat(id_cliente,id_unidade) VALUES(1,1)"
            )
        self.conn.rollback()
        with self.assertRaises(psycopg.errors.ForeignKeyViolation):
            self.conn.execute(
                "UPDATE chatbot.conversa SET id_chat=999 WHERE id_conversa=1"
            )

    def test_relatorios_consultam_tabelas_sem_view_incluindo_unidades_vazias(self):
        from utilitarios.reports_functions import total, weekly

        self.conn.execute("""
            INSERT INTO chatbot.unidade(id_unidade,nome_unidade,cnpj,email_responsavel,
                telefone,waba_id,phone_number_id)
            VALUES(2,'Sem histórico','outra','outra@example.com','5511999990010','waba-2','phone-2');
            INSERT INTO chatbot.atendimento_customizado(id_unidade,nome_agente,genero,numero_comercial)
            VALUES(2,'Outro agente','masculino','5511999990011');
            UPDATE chatbot.atendimento_customizado SET bpa_ativo=TRUE,idade_minima_suporte=70
            WHERE id_unidade=1;
            UPDATE chatbot.conversa SET status_dependente=FALSE,profissao='Professora'
            WHERE id_conversa=1;
            UPDATE chatbot.cliente SET idade=35 WHERE id_cliente=1;
            INSERT INTO chatbot.historico_mensagens
                (id_conversa,id_etapa,received_data_hora,cliente_telefone,conteudo_texto,
                 tipo_mensagem,id_hash_msg,id_phone_unidade,unidade_telefone,quem_enviou)
            VALUES(1,1,clock_timestamp(),'5511999990002','Olá','text',
                'wamid.relatorio','phone-teste','5511999990000','cliente');
        """)
        instante = self.conn.execute('SELECT clock_timestamp()').fetchone()[0]
        self.conn.commit()
        fim = instante + timedelta(minutes=1)
        snapshot = weekly.coletar_snapshot(self.conn, instante - timedelta(days=1), fim)
        unidades = {u['id_unidade']: u for u in snapshot['unidades']}
        self.assertEqual(set(unidades), {1, 2})
        self.assertEqual((unidades[1]['nome_agente'], unidades[1]['bpa_ativo'], unidades[1]['idade_minima_suporte']),
                         ('Dora', True, 70))
        self.assertEqual(len(unidades[1]['conversas']), 1)
        self.assertEqual(unidades[2]['conversas'], [])
        filtrado = weekly.coletar_snapshot(self.conn, instante - timedelta(days=1), fim, ids_unidade=[2])
        self.assertEqual([u['id_unidade'] for u in filtrado['unidades']], [2])
        primeiros = {u['id_unidade']: u for u in total.coletar_primeiros_registros(self.conn, fim)}
        self.assertIsNotNone(primeiros[1]['primeiro_registro'])
        self.assertIsNone(primeiros[2]['primeiro_registro'])
        self.assertEqual([u['id_unidade'] for u in total.coletar_primeiros_registros(self.conn, fim, [2])], [2])
