"""Coleta por campo em PostgreSQL descartável; rede e WhatsApp substituídos."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

import psycopg
from tests.integration import test_fireads_postgres as legado
from tests.unit.test_coleta_abertura import FORM, ROW, snapshot
from core.repositories.fireads import pendencias, envios
from core.repositories.atendimento.coleta_abertura import guardar_coletas
from core.repositories.atendimento.conversas import inicializar_conversa_resposta_bot
from core.repositories.atendimento.followup import LockConversaPerdido
from core.integrations.fireads.coleta_abertura import interpretar_parcial
from core.integrations.fireads.contrato import ABA_DESTINO
from core.repositories.funil.leads import buscar_dados_lead_funil
from core.integrations.funil.oportunidades import montar_payload_oportunidade
from workers.worker_flow.fireads import preparar_abertura
from workers.worker_flow.valida_historico import valida_historico
from workers.worker_flow.response_flow.flow_sender import flow_sender
from workers.worker_flow.transacoes.persistencia_resposta import atualizar_banco_com_contexto_final
from workers.worker_flow.suporte.consultas_fireads import ConsultaFireAdsPendente
from workers.worker_funil.fireads import processar


@unittest.skipUnless(legado.DSN, 'Exige FIREADS_TEST_DSN em loopback e test_chatbot_fireads vazio')
class ColetaPostgresTests(unittest.TestCase):
    # Reutiliza somente a montagem segura do banco, não os testes da versão antiga.
    setUp = legado.FireAdsPostgresTests.setUp
    limpar = legado.FireAdsPostgresTests.limpar
    nova_conversa = legado.FireAdsPostgresTests.nova_conversa
    preparar_mensagem = legado.FireAdsPostgresTests.preparar_mensagem

    def inicio(self, texto=FORM + '\nTurno: Tarde', fireads=True):
        cid, msg, versao, ctx = self.preparar_mensagem()
        msg.update(conteudo_texto=texto, tipo_mensagem='text', id_hash='wamid.fireads',
                   data_recebimento=datetime.now(timezone.utc), id_phone_unidade='phone-teste',
                   unidade_telefone='5511999990000')
        self.cursor.execute('UPDATE chatbot.fila_mensagens SET conteudo_texto=%s WHERE id_mensagem=%s',
                            (texto, msg['id_mensagem']))
        if not fireads:
            self.cursor.execute('DELETE FROM chatbot.integracao_fireads')
        self.conn.commit()
        return cid, msg, versao, ctx

    def concluir(self, rows):
        reserva = pendencias.reservar(self.cursor)
        self.conn.commit()
        entrada = reserva['entrada']
        decisao = interpretar_parcial(rows, entrada['numero'], entrada['fuso'], entrada['aba'], entrada['coleta'])
        self.assertTrue(pendencias.concluir(reserva, {'decisao': decisao, 'fontes': {'geral': rows}}, self.cursor))
        pendencias.liberar_reserva(reserva['id_consulta'], self.cursor)
        self.conn.commit()

    def test_completo_sem_consulta_recupera_sem_reextrair(self):
        cid, msg, v, ctx = self.inicio()
        novo = preparar_abertura(ctx, msg, v, self.cursor)
        self.conn.commit()
        self.assertEqual(novo['contexto_coleta']['etapa_inicial'], 4)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM chatbot.consulta_fireads').fetchone()[0], 0)
        with patch('workers.worker_flow.coleta_abertura.criar_contexto', side_effect=AssertionError('Não reextrair')):
            retomado = preparar_abertura(ctx, dict(msg, conteudo_texto='Texto posterior'), v, self.cursor)
        self.assertEqual(retomado['contexto_coleta'], novo['contexto_coleta'])
        self.assertEqual(retomado['contexto_fireads']['origem'], 'organico')
        self.assertEqual(retomado['contexto_fireads']['motivo'], 'canal_pendente_entrega')

    def test_tres_campos_sem_turno_consulta_e_persiste_preferencia_do_dashboard(self):
        cid, msg, v, ctx = self.inicio(FORM)
        with self.assertRaises(ConsultaFireAdsPendente):
            preparar_abertura(ctx, msg, v, self.cursor)
        self.conn.commit()
        self.concluir([dict(ROW, Canal='Chat Fire', **{'Período preferido': 'Sábado'})])
        novo = preparar_abertura(ctx, msg, v, self.cursor)
        self.conn.commit()
        self.assertEqual(novo['contexto_fireads']['origem'], 'chat_fire')
        self.assertEqual(novo['contexto_coleta']['campos']['turno']['fonte'], 'dashboard')
        self.assertEqual(self.conn.execute('SELECT turno FROM chatbot.conversa WHERE id_conversa=%s', (cid,)).fetchone()[0], 'sabado')
        self.assertEqual(self.conn.execute('SELECT count(*) FROM chatbot.consulta_fireads').fetchone()[0], 1)

    def test_chat_fire_parcial_nome_turno_da_mensagem_email_do_dashboard(self):
        texto = 'Olá! Sou Ana Paula. Vim pelo site.\nQuem vai fazer: Criança\nMelhor período: Sábado'
        cid, msg, v, ctx = self.inicio(texto)
        with self.assertRaises(ConsultaFireAdsPendente):
            preparar_abertura(ctx, msg, v, self.cursor)
        self.conn.commit()
        self.concluir([dict(ROW, Canal='Chat Fire', **{'Para quem é': '', 'Perfil/Faixa': 'Criança'})])
        novo = preparar_abertura(ctx, msg, v, self.cursor)
        self.assertEqual(novo['contexto_coleta']['etapa_inicial'], 2)
        self.assertEqual(novo['contexto_coleta']['campos']['email']['valor'], 'ana@example.com')
        self.assertEqual(novo['contexto_coleta']['campos']['turno']['valor'], 'sabado')
        self.assertEqual(novo['contexto_coleta']['campos']['destinatario']['status'], 'invalido')
        self.conn.rollback()
        retomado = preparar_abertura(ctx, msg, v, self.cursor)
        self.assertEqual(novo['contexto_coleta'], retomado['contexto_coleta'])
        self.conn.commit()
        self.assertEqual(self.conn.execute('SELECT origem_fireads,turno FROM chatbot.conversa WHERE id_conversa=%s', (cid,)).fetchone(), ('chat_fire', 'sabado'))

    def test_unidade_com_link_ignora_turno_na_abertura(self):
        cid, msg, v, ctx = self.inicio(FORM + '\nTurno: Sábado')
        self.cursor.execute("UPDATE chatbot.atendimento_customizado SET link_agendamento='https://example.com/agendar'")
        novo = preparar_abertura(ctx, msg, v, self.cursor)
        self.assertNotIn('turno', novo['contexto_coleta']['campos'])
        self.assertIsNone(self.conn.execute('SELECT turno FROM chatbot.conversa WHERE id_conversa=%s', (cid,)).fetchone()[0])
        self.assertEqual(self.conn.execute('SELECT count(*) FROM chatbot.consulta_fireads').fetchone()[0], 0)

    def test_unidade_sem_fireads_persiste_turno_sem_consulta(self):
        cid, msg, v, ctx = self.inicio('Eu me chamo Ana\nMelhor período: Sábado', fireads=False)
        novo = preparar_abertura(ctx, msg, v, self.cursor)
        self.assertEqual(novo['contexto_coleta']['etapa_inicial'], 2)
        self.assertEqual(self.conn.execute('SELECT turno FROM chatbot.conversa WHERE id_conversa=%s', (cid,)).fetchone()[0], 'sabado')
        self.assertEqual(self.conn.execute('SELECT count(*) FROM chatbot.consulta_fireads').fetchone()[0], 0)

    def test_turno_coletado_preserva_sexta_resposta_e_replay_sem_novo_envio(self):
        cid, msg, v, ctx = self.inicio(FORM + '\nTurno: Sábado', fireads=False)
        ctx = preparar_abertura(ctx, msg, v, self.cursor)
        self.cursor.execute('UPDATE chatbot.cliente SET idade=40 WHERE id_cliente=1')
        self.cursor.execute('UPDATE chatbot.conversa SET id_etapa_atual=17 WHERE id_conversa=%s', (cid,))
        self.cursor.execute("INSERT INTO chatbot.respostas_desafios(id_conversa,id_etapa,resposta) SELECT %s,etapa,'Nunca' FROM generate_series(12,16) etapa", (cid,))
        msg['conteudo_texto'] = 'Nunca'
        self.cursor.execute('UPDATE chatbot.fila_mensagens SET conteudo_texto=%s WHERE id_mensagem=%s', ('Nunca', msg['id_mensagem']))
        ctx['conversa']['id_etapa_atual'] = 17
        hist = valida_historico(msg, ctx, self.cursor)
        with patch('workers.worker_flow.response_flow.etapas.resolver_etapa17.enviar_etapa19', return_value={
            'enviou': True, 'resposta_ja_existia': False, 'mensagem_bot': 'Fale com o comercial',
            'id_hash_msg_bot': 'wamid.comercial', 'id_etapa_resultante': 19, 'tipo_mensagem': 'text',
            'canal': 'meta_whatsapp', 'atualizar_conversa': True, 'atualizar_last_from_bot': True,
        }) as sender:
            resposta = flow_sender(hist)
        sender.assert_called_once()
        self.assertEqual(resposta['evento_transicao'], 'triagem_concluida_turno_coletado')
        atualizar_banco_com_contexto_final(hist, resposta, self.cursor)
        self.conn.commit()
        self.assertEqual(self.conn.execute('SELECT id_etapa_atual,turno FROM chatbot.conversa WHERE id_conversa=%s', (cid,)).fetchone(), (19, 'sabado'))
        self.assertEqual(self.conn.execute('SELECT count(*) FROM chatbot.respostas_desafios WHERE id_conversa=%s', (cid,)).fetchone()[0], 6)
        # O replay parte da etapa do cliente registrada no histórico.
        ctx['conversa']['id_etapa_atual'] = 19
        replay = valida_historico(msg, ctx, self.cursor)
        with patch('workers.worker_flow.response_flow.etapas.resolver_etapa17.enviar_etapa19', side_effect=AssertionError('Não reenviar')):
            resposta = flow_sender(replay)
        self.assertTrue(resposta['resposta_ja_existia'])
        atualizar_banco_com_contexto_final(replay, resposta, self.cursor)
        self.conn.commit()
        self.assertEqual(self.conn.execute('SELECT count(*) FROM chatbot.respostas_desafios WHERE id_conversa=%s', (cid,)).fetchone()[0], 6)

    def test_migracao_chat_fire_sabado_reexecucao_preserva_contexto(self):
        cid, msg, v, ctx = self.inicio(FORM + '\nTurno: Sábado')
        preparar_abertura(ctx, msg, v, self.cursor)
        self.conn.commit()
        sql = 'SELECT contexto_coleta,turno,origem_fireads FROM chatbot.conversa WHERE id_conversa=%s'
        antes = self.conn.execute(sql, (cid,)).fetchone()
        self.conn.commit()
        migration = Path(__file__).resolve().parents[2] / 'deploy/migrations/20261021_chat_fire_turno_coleta.sql'
        self.conn.execute(migration.read_text(encoding='utf-8'), prepare=False)
        self.assertEqual(self.conn.execute(sql, (cid,)).fetchone(), antes)
        with self.conn.transaction():
            with self.assertRaises(psycopg.errors.CheckViolation):
                with self.conn.transaction():
                    self.conn.execute("UPDATE chatbot.conversa SET turno='sexta' WHERE id_conversa=%s", (cid,))

    def test_sem_fireads_preserva_canal_da_unidade(self):
        cid, msg, v, ctx = self.inicio(fireads=False)
        novo = preparar_abertura(ctx, msg, v, self.cursor)
        self.assertNotIn('contexto_fireads', novo)
        self.assertEqual(self.conn.execute('SELECT origem_fireads FROM chatbot.conversa WHERE id_conversa=%s', (cid,)).fetchone()[0], None)
        payload = {'teste': True}
        self.assertEqual(envios.congelar({'id_conversa': cid}, payload, {'codigo_canal_venda': '113340', 'link_api_carrossel': 'https://example.com'}, self.cursor)[1], '113340')
        self.assertEqual(self.conn.execute('SELECT count(*) FROM chatbot.envios_dash').fetchone()[0], 0)

    def test_parcial_recupera_consulta_salva_apos_rollback(self):
        cid, msg, v, ctx = self.inicio('Full name: Ana Paula Silva\nPara quem é: Para mim')
        with self.assertRaises(ConsultaFireAdsPendente):
            preparar_abertura(ctx, msg, v, self.cursor)
        self.conn.commit()
        self.concluir([ROW])
        novo = preparar_abertura(ctx, msg, v, self.cursor)
        self.assertEqual(novo['contexto_coleta']['campos']['email']['valor'], 'ana@example.com')
        self.conn.rollback()
        reaplicado = preparar_abertura(ctx, msg, v, self.cursor)
        self.assertEqual(reaplicado['contexto_coleta'], novo['contexto_coleta'])
        self.assertEqual(self.conn.execute('SELECT count(*) FROM chatbot.consulta_fireads').fetchone()[0], 1)

    def test_timeout_nao_reconsulta_e_pergunta_so_o_que_falta(self):
        cid, msg, v, ctx = self.inicio('Full name: Ana Paula Silva')
        with self.assertRaises(ConsultaFireAdsPendente):
            preparar_abertura(ctx, msg, v, self.cursor)
        self.cursor.execute("UPDATE chatbot.consulta_fireads SET solicitado_em=clock_timestamp()-INTERVAL '301 seconds', prazo_final=clock_timestamp()-INTERVAL '1 second'")
        self.conn.commit()
        novo = preparar_abertura(ctx, msg, v, self.cursor)
        self.assertEqual(novo['contexto_coleta']['etapa_inicial'], 2)
        self.conn.commit()
        self.assertEqual(preparar_abertura(ctx, msg, v, self.cursor)['contexto_coleta'], novo['contexto_coleta'])
        self.assertEqual(self.conn.execute('SELECT count(*) FROM chatbot.consulta_fireads').fetchone()[0], 1)

    def test_lock_perdido_nao_importa(self):
        cid, msg, v, ctx = self.inicio()
        self.cursor.execute('UPDATE chatbot.conversa SET lock_version=lock_version+1 WHERE id_conversa=%s', (cid,))
        self.conn.commit()
        with self.assertRaises(LockConversaPerdido):
            preparar_abertura(ctx, msg, v, self.cursor)
        self.conn.rollback()
        self.assertIsNone(self.conn.execute('SELECT contexto_coleta FROM chatbot.conversa WHERE id_conversa=%s', (cid,)).fetchone()[0])

    def test_email_duplicado_no_cadastro_preserva_os_outros_campos(self):
        cid, msg, v, ctx = self.inicio()
        self.cursor.execute("INSERT INTO chatbot.cliente(nome,waid_telefone,email) VALUES('Outro','5511999990003','ana@example.com')")
        novo = preparar_abertura(ctx, msg, v, self.cursor)
        coleta = novo['contexto_coleta']
        self.assertEqual(coleta['campos']['email']['status'], 'conflitante')
        self.assertEqual(coleta['campos']['nome']['valor'], 'Ana Paula')
        self.assertEqual(coleta['etapa_inicial'], 4)
        self.assertEqual(novo['contexto_fireads']['resultado'], 'incompleto')

    def test_inicializacao2_sql_e_replay_da_resposta(self):
        cid, msg, v, ctx = self.inicio('Full name: Ana Paula Silva\nEmail: ana@example.com', fireads=False)
        ctx = preparar_abertura(ctx, msg, v, self.cursor)
        hist = valida_historico(msg, ctx, self.cursor)
        self.assertEqual(hist['id_etapa_cliente'], 2)
        with patch('core.integrations.whatsapp.pywa_functions.pywa_senders.abertura_coleta.conta_wa') as wa:
            wa.return_value.send_message.return_value = {'messages': [{'id': 'wamid.resposta'}]}
            with patch('core.integrations.whatsapp.pywa_functions.pywa_senders.abertura_coleta.extrair_id_hash_msg_bot', return_value='wamid.resposta'):
                resposta = flow_sender(hist)
        atualizar_banco_com_contexto_final(hist, resposta, self.cursor)
        self.conn.commit()
        self.assertEqual(self.conn.execute('SELECT id_etapa_atual FROM chatbot.conversa WHERE id_conversa=%s', (cid,)).fetchone()[0], 2)
        ctx['conversa']['id_etapa_atual'] = 2
        replay = valida_historico(msg, ctx, self.cursor)
        with patch('core.integrations.whatsapp.pywa_functions.pywa_senders.abertura_coleta.conta_wa', side_effect=AssertionError('Não reenviar')):
            self.assertTrue(flow_sender(replay)['resposta_ja_existia'])

    def test_migracao_idempotente_preserva_coletas(self):
        cid, msg, v, ctx = self.inicio()
        preparar_abertura(ctx, msg, v, self.cursor)
        self.conn.commit()
        antes = self.conn.execute('SELECT contexto_coleta FROM chatbot.conversa WHERE id_conversa=%s', (cid,)).fetchone()[0]
        arquivo = Path(__file__).resolve().parents[2] / 'deploy/migrations/20261019_coleta_abertura.sql'
        self.conn.commit()
        self.conn.execute(arquivo.read_text(encoding='utf-8'), prepare=False)
        depois = self.conn.execute('SELECT contexto_coleta FROM chatbot.conversa WHERE id_conversa=%s', (cid,)).fetchone()[0]
        self.assertEqual(antes, depois)

    def test_nome_pendente_salta_destinatario_somente_pelo_mapa(self):
        cid, msg, v, ctx = self.inicio('Email: ana@example.com\nPara quem é: Para minha mãe', fireads=False)
        ctx = preparar_abertura(ctx, msg, v, self.cursor)
        self.assertEqual(ctx['contexto_coleta']['etapa_inicial'], 1)
        inicializar_conversa_resposta_bot(cid, 1, datetime.now(timezone.utc), self.cursor)
        self.cursor.execute("""INSERT INTO chatbot.fila_mensagens(cliente_telefone,conteudo_texto,tipo_mensagem,
            id_phone_unidade,unidade_telefone,id_hash_msg,id_conversa,status,retry_count,
            processing_started_at,received_data_hora)
            VALUES(%s,'Ana Paula','text','phone-teste','5511999990000','wamid.nome',%s,'processing',1,
            clock_timestamp(),clock_timestamp()) RETURNING id_mensagem""", (legado.NUMERO, cid))
        msg.update(id_mensagem=self.cursor.fetchone()[0], id_hash='wamid.nome', conteudo_texto='Ana Paula')
        self.conn.commit()
        ctx['conversa']['id_etapa_atual'] = 1
        ctx = preparar_abertura(ctx, msg, v, self.cursor)
        hist = valida_historico(msg, ctx, self.cursor)
        self.assertEqual(hist['transicoes_permitidas']['nome_cliente_valido_destino_coletado'], 4)
        with patch('workers.worker_flow.response_flow.etapas.resolver_etapa1.enviar_etapa4', return_value={
            'enviou': True, 'resposta_ja_existia': False, 'mensagem_bot': 'Qual sua profissão?',
            'id_hash_msg_bot': 'wamid.profissao', 'id_etapa_resultante': 4, 'tipo_mensagem': 'text',
            'canal': 'meta_whatsapp', 'atualizar_conversa': True, 'atualizar_last_from_bot': True,
        }):
            resposta = flow_sender(hist)
        atualizar_banco_com_contexto_final(hist, resposta, self.cursor)
        self.conn.commit()
        etapa, coleta = self.conn.execute('SELECT id_etapa_atual,contexto_coleta FROM chatbot.conversa WHERE id_conversa=%s', (cid,)).fetchone()
        self.assertEqual(etapa, 4)
        self.assertEqual(coleta['campos']['nome']['valor'], 'Ana Paula')
        self.assertTrue(coleta['campos']['destinatario']['valor']['dependente'])

    def test_funil_retrato_por_conversa_e_destino_congelado_antes_do_post(self):
        cid, msg, v, ctx = self.inicio()
        ctx = preparar_abertura(ctx, msg, v, self.cursor)
        self.cursor.execute('UPDATE chatbot.conversa SET id_etapa_atual=19,turno=%s,profissao=%s WHERE id_conversa=%s', ('manha', 'Professora', cid))
        self.cursor.execute('UPDATE chatbot.cliente SET idade=35 WHERE id_cliente=1')
        guardar_coletas({'id_conversa': cid, 'id_cliente': 1, 'contexto_coleta': ctx['contexto_coleta']}, {'destino_dado': 'cliente'}, self.cursor)
        self.cursor.execute("INSERT INTO chatbot.respostas_desafios(id_conversa,id_etapa,resposta) SELECT %s,etapa,'Às vezes' FROM generate_series(12,17) etapa", (cid,))
        dados = buscar_dados_lead_funil(cid, self.cursor)
        payload = montar_payload_oportunidade(dados)
        envios.congelar(dados, payload, {'codigo_canal_venda': '113340', 'link_api_carrossel': 'https://example.com/api'}, self.cursor)
        self.cursor.execute('UPDATE chatbot.conversa SET lead_no_funil=TRUE WHERE id_conversa=%s', (cid,))
        envio = envios.reservar(self.cursor)
        self.conn.commit()
        externo = Mock()
        externo.consultar.return_value = {'headers': list(ROW) + ['Período preferido'], 'rows': []}

        def enviar(*args, **kwargs):
            with psycopg.connect(legado.DSN) as verificador:
                alvo = verificador.execute("SELECT snapshot->'destino' FROM chatbot.envios_dash WHERE id_envio_dash=%s", (envio['id'],)).fetchone()[0]
                self.assertEqual(alvo, {'tipo': 'create'})
            return {'success': True, 'inserted': 1, 'aba': ABA_DESTINO}

        externo.enviar.side_effect = enviar
        with patch('workers.worker_funil.fireads.ClienteFireAds', return_value=externo):
            self.assertTrue(processar(envio, self.conn, self.cursor))
        self.assertEqual(externo.enviar.call_args.kwargs['dados']['Canal'], 'Orgânico')
        self.assertEqual(externo.enviar.call_args.kwargs['dados']['Nome'], 'Ana Paula Silva')
        self.assertEqual(externo.enviar.call_args.kwargs['dados']['Período preferido'], 'Tarde')
        self.assertEqual(self.conn.execute('SELECT status FROM chatbot.envios_dash').fetchone()[0], 'sent')

    def test_sincronizacao_retomada_apos_escrita_parcial_e_resposta_perdida(self):
        cid, msg, v, ctx = self.inicio()
        ctx = preparar_abertura(ctx, msg, v, self.cursor)
        self.cursor.execute('UPDATE chatbot.conversa SET id_etapa_atual=19,profissao=%s WHERE id_conversa=%s', ('Professora', cid))
        self.cursor.execute('UPDATE chatbot.cliente SET idade=35 WHERE id_cliente=1')
        guardar_coletas({'id_conversa': cid, 'id_cliente': 1, 'contexto_coleta': ctx['contexto_coleta']},
                        {'destino_dado': 'cliente'}, self.cursor)
        self.cursor.execute("INSERT INTO chatbot.respostas_desafios(id_conversa,id_etapa,resposta) SELECT %s,etapa,'Às vezes' FROM generate_series(12,17) etapa", (cid,))
        dados = buscar_dados_lead_funil(cid, self.cursor)
        payload = montar_payload_oportunidade(dados)
        config = {'codigo_canal_venda': '113340', 'link_api_carrossel': 'https://example.com/api'}
        envios.congelar(dados, payload, config, self.cursor)
        self.cursor.execute('UPDATE chatbot.conversa SET lead_no_funil=TRUE WHERE id_conversa=%s', (cid,))
        envio = envios.reservar(self.cursor)
        self.conn.commit()
        self.assertEqual(envio['snapshot']['versao'], 4)
        externo = Mock()
        planilha = dict(ROW, Nome='Nome antigo', Email='antigo@example.com', **{'Período preferido': 'Manhã'})
        externo.consultar.side_effect = lambda *_: {'headers': list(planilha), 'rows': [deepcopy(planilha)]}
        tentativas = []

        def enviar(_aba, **op):
            with psycopg.connect(legado.DSN) as verificador:
                congelado = verificador.execute('SELECT snapshot FROM chatbot.envios_dash WHERE id_envio_dash=%s', (envio['id'],)).fetchone()[0]
                self.assertEqual(congelado['destino']['referencia']['linha'], 44)
                self.assertEqual(congelado['campos_dashboard'], op['campos'])
            tentativas.append(deepcopy(op))
            if len(tentativas) == 1:
                planilha['Nome'] = op['campos']['Nome']
                raise TimeoutError('Queda após gravar nome')
            planilha.update(op['campos'])
            planilha['Observação'] = op['observacoes']
            raise TimeoutError('Resposta perdida após gravar tudo')

        externo.enviar.side_effect = enviar
        with patch('workers.worker_funil.fireads.ClienteFireAds', return_value=externo):
            self.assertFalse(processar(envio, self.conn, self.cursor))
            self.assertEqual(self.conn.execute('SELECT status FROM chatbot.envios_dash').fetchone()[0], 'pending')
            # Uma alteração posterior no cadastro não muda o envio congelado.
            dados['nome_cliente'] = 'Não reenviar este nome'
            envios.congelar(dados, {}, config, self.cursor)
            for sucesso in (False, True):
                planilha['_row'] = 70  # Moveu; a identidade e o bloco permitem reencontrar.
                self.cursor.execute("UPDATE chatbot.envios_dash SET next_attempt_at=clock_timestamp()-INTERVAL '1 second'")
                envio = envios.reservar(self.cursor)
                self.conn.commit()
                self.assertEqual(processar(envio, self.conn, self.cursor), sucesso)
        self.assertEqual(len(tentativas), 2)
        self.assertEqual(tentativas[0]['campos'], tentativas[1]['campos'])
        self.assertEqual(planilha['Nome'], 'Ana Paula Silva')
        self.assertEqual(planilha['Período preferido'], 'Tarde')
        self.assertEqual(planilha['Observação'].count('[INICIO CHATBOT:'), 1)
        status, recibo = self.conn.execute('SELECT status,recibo FROM chatbot.envios_dash').fetchone()
        self.assertEqual(status, 'sent')
        self.assertTrue(recibo['reconciliado'])


if __name__ == '__main__':
    unittest.main()
