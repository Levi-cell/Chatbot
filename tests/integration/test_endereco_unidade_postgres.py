"""DDL, migração e atendimento com PostgreSQL local; nenhum envio real."""

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import psycopg
from tests.integration import test_fireads_postgres as base
from core.database.deploy_database import etapa_transicao_script, fireads_script
from core.database.deploy_database.enderecos_script import DDL_ENDERECO_UNIDADE
from core.repositories.unidades.enderecos import buscar_localizacao_unidade
from core.integrations.whatsapp.pywa_functions import cliente
from workers.worker_flow.valida_historico import valida_historico
from workers.worker_flow.response_flow.flow_sender import flow_sender
from workers.worker_flow.transacoes.persistencia_resposta import atualizar_banco_com_contexto_final
from unittest.mock import MagicMock


MIGRACAO = Path(__file__).resolve().parents[2] / 'deploy/migrations/20261027_endereco_unidade.sql'
HORARIOS_SANTO_ANDRE = (
    'segunda a sexta das 9h às 19h, exceto quarta-feira, quando vai até as 21h, '
    'e sábado das 8h30 às 13h30'
)


@unittest.skipUnless(base.DSN, 'Exige FIREADS_TEST_DSN local e test_chatbot_fireads vazio')
class EnderecoPostgresTests(unittest.TestCase):
    setUp = base.FireAdsPostgresTests.setUp
    limpar = base.FireAdsPostgresTests.limpar
    nova_conversa = base.FireAdsPostgresTests.nova_conversa
    preparar_mensagem = base.FireAdsPostgresTests.preparar_mensagem

    def migrar(self):
        texto = MIGRACAO.read_text(encoding='utf-8')
        # A transação é controlada pelo teste; todo o DDL e seed são os do deploy.
        corpo = texto.split('BEGIN;', 1)[1].rsplit('COMMIT;', 1)[0]
        self.cursor.execute(corpo)

    def cadastrar_unidades(self):
        self.cursor.execute("UPDATE chatbot.unidade SET nome_unidade='Supera Santo André' WHERE id_unidade=1")
        for i, nome in enumerate(('Supera Santo Antônio de Jesus', 'Supera Rio Vermelho'), 2):
            self.cursor.execute('''INSERT INTO chatbot.unidade
                (nome_unidade,cnpj,email_responsavel,telefone,waba_id,phone_number_id)
                VALUES(%s,%s,%s,%s,%s,%s)''',
                (nome, f'cnpj{i}', f'u{i}@example.com', f'551199999000{i}', f'waba{i}', f'phone{i}'))
            self.cursor.execute('''INSERT INTO chatbot.atendimento_customizado
                (id_unidade,nome_agente,genero,numero_comercial)
                SELECT id_unidade,'Dora','feminino','5511999990001'
                FROM chatbot.unidade WHERE nome_unidade=%s''', (nome,))

    def test_migracao_primeira_aplicacao_reexecucao_e_ddl_python(self):
        self.cadastrar_unidades()
        # Simula o cadastro já confirmado antes da janela de migração.
        self.conn.commit()
        self.cursor.execute('DROP TABLE chatbot.endereco_unidade')
        self.cursor.execute('ALTER TABLE chatbot.unidade DROP COLUMN horarios_funcionamento')
        antes = self.cursor.execute('SELECT count(*) FROM chatbot.conversa').fetchone()[0]
        self.migrar()
        self.conn.commit()
        self.assertEqual(self.cursor.execute('SELECT count(*) FROM chatbot.endereco_unidade').fetchone()[0], 3)
        self.assertIn('Eduardo Monteiro, 188', buscar_localizacao_unidade(1, self.cursor)['endereco_unidade'])
        self.assertIn('Barros e Almeida, 88', buscar_localizacao_unidade(2, self.cursor)['endereco_unidade'])
        self.assertIn('Odilon Santos, 14', buscar_localizacao_unidade(3, self.cursor)['endereco_unidade'])
        self.assertEqual(buscar_localizacao_unidade(1, self.cursor)['horarios_funcionamento'], HORARIOS_SANTO_ANDRE)
        for outra_unidade in (2, 3):
            self.assertIsNone(buscar_localizacao_unidade(outra_unidade, self.cursor)['horarios_funcionamento'])
        self.cursor.execute("UPDATE chatbot.endereco_unidade SET endereco='Endereço corrigido' WHERE id_unidade=1")
        self.cursor.execute("UPDATE chatbot.unidade SET horarios_funcionamento='segunda a sexta das 9h às 19h' WHERE id_unidade=1")
        self.migrar()
        self.assertEqual(buscar_localizacao_unidade(1, self.cursor), {
            'endereco_unidade': 'Endereço corrigido',
            'horarios_funcionamento': 'segunda a sexta das 9h às 19h',
        })
        self.assertEqual(buscar_localizacao_unidade(999, self.cursor), {
            'endereco_unidade': None, 'horarios_funcionamento': None,
        })
        self.assertEqual(self.cursor.execute('SELECT count(*) FROM chatbot.conversa').fetchone()[0], antes)
        texto = MIGRACAO.read_text(encoding='utf-8')
        ddl = texto.split('-- INICIO DDL ENDERECO UNIDADE', 1)[1].split('-- FIM DDL ENDERECO UNIDADE', 1)[0]
        self.assertEqual(' '.join(ddl.split()), ' '.join(DDL_ENDERECO_UNIDADE.split()))
        for vazio in ('', ' \n\t '):
            with self.subTest(horario_vazio=vazio):
                self.cursor.execute('UPDATE chatbot.unidade SET horarios_funcionamento=%s WHERE id_unidade=1', (vazio,))
                self.migrar()
                self.assertEqual(buscar_localizacao_unidade(1, self.cursor)['horarios_funcionamento'], HORARIOS_SANTO_ANDRE)

    def test_migracao_unidade_ausente_reverte_toda_criacao(self):
        self.cursor.execute('DROP TABLE chatbot.endereco_unidade')
        self.cursor.execute('ALTER TABLE chatbot.unidade DROP COLUMN horarios_funcionamento')
        self.conn.commit()
        with self.assertRaises(psycopg.errors.RaiseException):
            with self.conn.transaction():
                self.migrar()
        self.assertIsNone(self.cursor.execute("SELECT to_regclass('chatbot.endereco_unidade')").fetchone()[0])
        self.assertEqual(self.cursor.execute("SELECT count(*) FROM information_schema.columns WHERE table_schema='chatbot' AND table_name='unidade' AND column_name='horarios_funcionamento'").fetchone()[0], 0)

    def test_ddl_final_ja_cria_horarios_text_nullable_sem_precisar_da_migracao(self):
        coluna = self.cursor.execute("SELECT data_type,is_nullable,column_default FROM information_schema.columns WHERE table_schema='chatbot' AND table_name='unidade' AND column_name='horarios_funcionamento'").fetchone()
        self.assertEqual(coluna, ('text', 'YES', None))
        self.cursor.execute("UPDATE chatbot.unidade SET horarios_funcionamento='sábado das 8h30 às 13h30' WHERE id_unidade=1")
        self.assertEqual(buscar_localizacao_unidade(1, self.cursor), {
            'endereco_unidade': None, 'horarios_funcionamento': 'sábado das 8h30 às 13h30',
        })

    def test_atualiza_migracao_anterior_preservando_endereco(self):
        self.cadastrar_unidades()
        self.cursor.execute("INSERT INTO chatbot.endereco_unidade VALUES(1,'Rua A. Ponto de referência: praça central.')")
        self.conn.commit()
        self.cursor.execute('ALTER TABLE chatbot.unidade DROP COLUMN horarios_funcionamento')
        self.migrar()
        self.assertEqual(buscar_localizacao_unidade(1, self.cursor), {
            'endereco_unidade': 'Rua A. Ponto de referência: praça central.',
            'horarios_funcionamento': HORARIOS_SANTO_ANDRE,
        })

    def test_nao_aceita_endereco_vazio_duplicado_ou_unidade_inexistente(self):
        self.conn.commit()
        for valor in ('', '  ', '\n\t'):
            with self.assertRaises(psycopg.errors.CheckViolation):
                with self.conn.transaction():
                    self.cursor.execute('INSERT INTO chatbot.endereco_unidade VALUES(1,%s)', (valor,))
        with self.assertRaises(psycopg.errors.ForeignKeyViolation):
            with self.conn.transaction():
                self.cursor.execute("INSERT INTO chatbot.endereco_unidade VALUES(999,'Rua A')")
        with self.conn.transaction():
            self.cursor.execute("INSERT INTO chatbot.endereco_unidade VALUES(1,'Rua A')")
        with self.assertRaises(psycopg.errors.UniqueViolation):
            with self.conn.transaction():
                self.cursor.execute("INSERT INTO chatbot.endereco_unidade VALUES(1,'Rua B')")

    def test_reexecucao_do_catalogo_preserva_arestas_de_coleta(self):
        antes = self.cursor.execute('SELECT id_transicao,id_etapa_origem,evento,id_etapa_destino FROM chatbot.etapa_transicao ORDER BY id_transicao').fetchall()
        @contextmanager
        def transacao(*_):
            yield self.cursor
        with patch.object(etapa_transicao_script, 'transacao_deploy', transacao), patch.object(fireads_script, 'transacao_deploy', transacao):
            etapa_transicao_script.criar_e_povoar_transicoes_etapa(incluir_coleta=False)
            fireads_script.criar_estrutura_fireads()
            etapa_transicao_script.criar_e_povoar_transicoes_etapa()
        depois = self.cursor.execute('SELECT id_transicao,id_etapa_origem,evento,id_etapa_destino FROM chatbot.etapa_transicao ORDER BY id_transicao').fetchall()
        self.assertEqual(antes, depois)
        self.assertEqual(len(depois), 32)

    def test_maria_contexto_envio_persistencia_e_replay_etapa9(self):
        cid, msg, versao, contexto_banco = self.preparar_mensagem()
        self.cursor.execute("UPDATE chatbot.conversa SET id_etapa_atual=9,status_dependente=FALSE,last_message_from='bot' WHERE id_conversa=%s", (cid,))
        self.cursor.execute("UPDATE chatbot.cliente SET nome='Maria' WHERE id_cliente=1")
        self.cursor.execute("INSERT INTO chatbot.endereco_unidade VALUES(1,'Rua Dr. Eduardo Monteiro, 188')")
        self.cursor.execute("UPDATE chatbot.unidade SET horarios_funcionamento='segunda a sexta das 9h às 19h' WHERE id_unidade=1")
        contexto_banco['conversa'].update(id_etapa_atual=9, status_dependente=False, last_message_from='bot')
        msg.update(conteudo_texto='Aonde fica', tipo_mensagem='text',
                   data_recebimento=datetime.now(timezone.utc), id_phone_unidade='phone-teste',
                   unidade_telefone='5511999990000')
        cx = valida_historico(msg, contexto_banco, self.cursor)
        self.conn.commit()
        fake = MagicMock()
        fake.send_message.return_value = SimpleNamespace(id='wamid.endereco')
        with patch.object(cliente, 'WhatsApp', return_value=fake):
            envio = flow_sender(cx)
        self.assertIn('Nossa unidade fica localizada em Rua Dr. Eduardo Monteiro, 188.', envio['mensagem_bot'])
        self.assertIn('Nosso horário de funcionamento é de segunda a sexta das 9h às 19h.', envio['mensagem_bot'])
        atualizar_banco_com_contexto_final(cx, envio, self.cursor)
        self.conn.commit()
        self.assertEqual(self.cursor.execute('SELECT id_etapa_atual FROM chatbot.conversa WHERE id_conversa=%s', (cid,)).fetchone()[0], 9)
        self.assertEqual(self.cursor.execute("SELECT conteudo_texto FROM chatbot.historico_mensagens WHERE id_conversa=%s AND quem_enviou='bot' ORDER BY id_mensagem DESC LIMIT 1", (cid,)).fetchone()[0], fake.send_message.call_args.kwargs['text'])
        cx = valida_historico(msg, contexto_banco, self.cursor)
        with patch.object(cliente, 'WhatsApp') as meta:
            replay = flow_sender(cx)
        meta.assert_not_called()
        self.assertTrue(replay['resposta_ja_existia'])

    def verificar_tratamento_sem_resposta(self, etapa, pedido, *, dependente=False, destino=None):
        destino = etapa if destino is None else destino
        cid, msg, _, contexto_banco = self.preparar_mensagem()
        self.cursor.execute(
            "UPDATE chatbot.conversa SET id_etapa_atual=%s,status_dependente=%s,"
            "last_message_from='bot' WHERE id_conversa=%s", (etapa, dependente, cid),
        )
        self.cursor.execute("UPDATE chatbot.cliente SET nome='Maria',idade=35 WHERE id_cliente=1")
        if dependente:
            self.cursor.execute(
                "INSERT INTO chatbot.dependente(id_cliente,id_conversa,nome_dependente,idade) "
                "VALUES(1,%s,'Lucas',12)", (cid,),
            )
        self.cursor.execute("INSERT INTO chatbot.endereco_unidade VALUES(1,'Rua A, 10')")
        contexto_banco['conversa'].update(
            id_etapa_atual=etapa, status_dependente=dependente, last_message_from='bot',
        )
        msg.update(conteudo_texto=pedido, data_recebimento=datetime.now(timezone.utc),
                   id_phone_unidade='phone-teste', unidade_telefone='5511999990000')
        cx = valida_historico(msg, contexto_banco, self.cursor)
        self.conn.commit()
        fake = MagicMock()
        fake.send_message.return_value = SimpleNamespace(id='wamid.tratamento')
        with patch.object(cliente, 'WhatsApp', return_value=fake):
            envio = flow_sender(cx)
        self.assertEqual(bool(envio.get('tratamento')), etapa == destino)
        if etapa != destino:
            self.assertEqual((etapa, destino, envio.get('evento_transicao')), (8, 9, 'cliente_retornou'))
        else:
            self.assertNotIn('evento_transicao', envio)
        self.assertNotIn('Vamos lá', envio['mensagem_bot'])
        self.assertNotIn('\n\n\n', envio['mensagem_bot'])
        if dependente:
            self.assertIn('Lucas', envio['mensagem_bot'])
        atualizar_banco_com_contexto_final(cx, envio, self.cursor)
        self.conn.commit()
        self.assertEqual(self.cursor.execute(
            'SELECT id_etapa_atual FROM chatbot.conversa WHERE id_conversa=%s', (cid,),
        ).fetchone()[0], destino)
        for tabela in ('respostas_desafios', 'pesquisa_satisfacao'):
            self.assertEqual(self.cursor.execute(
                f'SELECT count(*) FROM chatbot.{tabela} WHERE id_conversa=%s', (cid,),
            ).fetchone()[0], 0)
        self.assertEqual(self.cursor.execute(
            "SELECT conteudo_texto FROM chatbot.historico_mensagens "
            "WHERE id_conversa=%s AND quem_enviou='bot'", (cid,),
        ).fetchone()[0], fake.send_message.call_args.kwargs['text'])
        replay_cx = valida_historico(msg, contexto_banco, self.cursor)
        with patch.object(cliente, 'WhatsApp') as transporte:
            replay = flow_sender(replay_cx)
        transporte.assert_not_called()
        self.assertTrue(replay['resposta_ja_existia'])
        self.assertEqual(replay['id_etapa_resultante'], destino)
        contexto_banco['conversa']['id_etapa_atual'] = destino
        return cid, msg, contexto_banco

    def responder_apos_tratamento(self, cid, msg, contexto_banco, resposta):
        fila = self.cursor.execute(
            "INSERT INTO chatbot.fila_mensagens "
            "(cliente_telefone,conteudo_texto,tipo_mensagem,id_phone_unidade,"
            "unidade_telefone,id_hash_msg,id_conversa,status,retry_count,processing_started_at,received_data_hora) "
            "VALUES(%s,%s,'text','phone-teste','5511999990000','wamid.resposta',%s,"
            "'processing',1,clock_timestamp(),clock_timestamp()) RETURNING id_mensagem",
            (msg['cliente_telefone'], resposta, cid),
        ).fetchone()[0]
        msg = dict(msg, id_mensagem=fila, id_hash='wamid.resposta',
                   conteudo_texto=resposta, data_recebimento=datetime.now(timezone.utc))
        cx = valida_historico(msg, contexto_banco, self.cursor)
        self.conn.commit()
        fake = MagicMock()
        fake.send_message.return_value = SimpleNamespace(id='wamid.proxima')
        with patch.object(cliente, 'WhatsApp', return_value=fake):
            envio = flow_sender(cx)
        atualizar_banco_com_contexto_final(cx, envio, self.cursor)
        self.conn.commit()
        return envio

    def test_financeiro_triagem_preserva_dependente_e_resposta_seguinte_avanca(self):
        dados = self.verificar_tratamento_sem_resposta(12, 'Quanto custa?', dependente=True)
        envio = self.responder_apos_tratamento(*dados, 'Nunca')
        self.assertEqual(envio['id_etapa_resultante'], 13)
        self.assertEqual(self.cursor.execute(
            'SELECT id_etapa,resposta FROM chatbot.respostas_desafios WHERE id_conversa=%s',
            (dados[0],),
        ).fetchall(), [(12, 'nunca')])

    def test_endereco_apos_adiamento_abre9_e_so_proxima_resposta_confirma_reserva(self):
        dados = self.verificar_tratamento_sem_resposta(8, 'Aonde q fca?', dependente=True, destino=9)
        envio = self.responder_apos_tratamento(*dados, 'Reservar agora')
        self.assertEqual(envio['id_etapa_resultante'], 10)
        self.assertEqual(self.cursor.execute(
            'SELECT id_etapa_atual FROM chatbot.conversa WHERE id_conversa=%s', (dados[0],),
        ).fetchone()[0], 10)

    def test_reforco_na_ultima_pergunta_nao_conclui_triagem(self):
        self.verificar_tratamento_sem_resposta(17, 'Vocês dão reforço escolar?')

    def test_endereco_na_satisfacao_nao_vira_nota_e_resposta_seguinte_avanca(self):
        dados = self.verificar_tratamento_sem_resposta(21, 'Aonde q fca?')
        envio = self.responder_apos_tratamento(*dados, '5')
        self.assertEqual(envio['id_etapa_resultante'], 22)
        self.assertEqual(self.cursor.execute(
            'SELECT nota,comentario FROM chatbot.pesquisa_satisfacao WHERE id_conversa=%s',
            (dados[0],),
        ).fetchall(), [(5, None)])


if __name__ == '__main__':
    unittest.main()
