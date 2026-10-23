"""Ordem real das filas, snapshots e recuperação; HTTP somente simulado."""

from copy import deepcopy
import unittest
from unittest.mock import Mock, patch

import psycopg
from tests.integration import test_coleta_abertura_postgres as coleta_testes
from tests.integration.test_fireads_postgres import DSN
from tests.unit.test_coleta_abertura import ROW, FORM
from core.repositories.atendimento.coleta_abertura import guardar_coletas
from core.integrations.fireads.atribuicao import CHAVE, ler
from core.integrations.fireads.cliente import TelefoneDuplicadoFireAds
from core.repositories.fireads import envios, pendencias
from core.repositories.funil.envios import sincronizar_envios_elegiveis, reivindicar_proximo_envio
from workers.worker_flow.fireads import preparar_abertura
from workers.worker_funil.processamento import processar_envio_funil
from workers.worker_flow.suporte.consultas_fireads import ConsultaFireAdsPendente


@unittest.skipUnless(DSN, 'Exige PostgreSQL descartável em loopback')
class EntregaPrimeiroTests(unittest.TestCase):
    setUp = coleta_testes.ColetaPostgresTests.setUp
    limpar = coleta_testes.ColetaPostgresTests.limpar
    nova_conversa = coleta_testes.ColetaPostgresTests.nova_conversa
    preparar_mensagem = coleta_testes.ColetaPostgresTests.preparar_mensagem
    inicio = coleta_testes.ColetaPostgresTests.inicio

    def concluida(self, fireads=True):
        cid, msg, v, ctx = self.inicio(fireads=fireads)
        ctx = preparar_abertura(ctx, msg, v, self.cursor)
        self.cursor.execute('UPDATE chatbot.conversa SET id_etapa_atual=19,profissao=%s WHERE id_conversa=%s', ('Professora', cid))
        self.cursor.execute('UPDATE chatbot.cliente SET idade=35 WHERE id_cliente=1')
        guardar_coletas({'id_conversa': cid, 'id_cliente': 1, 'contexto_coleta': ctx['contexto_coleta']},
                        {'destino_dado': 'cliente'}, self.cursor)
        self.cursor.execute("INSERT INTO chatbot.respostas_desafios(id_conversa,id_etapa,resposta) SELECT %s,e,'Às vezes' FROM generate_series(12,17) e", (cid,))
        sincronizar_envios_elegiveis(self.cursor)
        envio = reivindicar_proximo_envio(self.cursor)
        self.conn.commit()
        return cid, envio

    def simular(self, rows):
        eventos = []
        externo = Mock()

        def ler(*_):
            self.assertEqual(self.conn.info.transaction_status, psycopg.pq.TransactionStatus.IDLE)
            eventos.append('GET')
            return {'headers': list(ROW) + ['Período preferido'], 'rows': deepcopy(rows)}

        def escrever(_aba, **op):
            self.assertEqual(self.conn.info.transaction_status, psycopg.pq.TransactionStatus.IDLE)
            eventos.append('DASH')
            if 'row' in op:
                row = next(r for r in rows if r['_row'] == op['row'])
                row.update(op['campos'])
                row['Observação'] = op['observacoes']
                return {'success': True, 'row': op['row'], 'aba': _aba,
                        'updated': [*op['campos'], 'Observação']}
            rows.append(dict(op['dados'], _row=max([r['_row'] for r in rows] + [1]) + 1))
            return {'success': True, 'inserted': 1, 'aba': _aba}

        def funil(**kwargs):
            self.assertEqual(self.conn.info.transaction_status, psycopg.pq.TransactionStatus.IDLE)
            eventos.append('FUNIL')
            with psycopg.connect(DSN) as verificar:
                row = verificar.execute('SELECT status,snapshot FROM chatbot.envios_dash').fetchone()
            if row is not None:
                self.assertEqual(row[0], 'sent')
                self.assertEqual(kwargs['codigo_canal_venda'], row[1]['canal'])
                self.assertEqual(kwargs['payload'], row[1]['payload_funil'])
            return {'status_http': 200, 'resposta': {'success': True}}

        externo.consultar.side_effect = ler
        externo.enviar.side_effect = escrever
        self.enterContext(patch('workers.worker_funil.preparacao_fireads.ClienteFireAds', return_value=externo))
        self.enterContext(patch('workers.worker_funil.fireads.ClienteFireAds', return_value=externo))
        postar_funil = self.enterContext(patch('workers.worker_funil.processamento.enviar_oportunidade', side_effect=funil))
        return externo, postar_funil, eventos

    def retry(self):
        self.cursor.execute("UPDATE chatbot.funil_envios SET next_attempt_at=clock_timestamp()-INTERVAL '1 second'")
        self.cursor.execute("UPDATE chatbot.envios_dash SET next_attempt_at=clock_timestamp()-INTERVAL '1 second'")
        envio = reivindicar_proximo_envio(self.cursor)
        self.conn.commit()
        return envio

    def test_completo_resolve_chat_fire_por_telefone_e_grava_dash_antes_funil(self):
        cid, envio = self.concluida()
        rows = [dict(ROW, _row=751, Nome='Ed', Email='divergente@example.com', Canal='Chat Fire',
                     **{'Para quem é': '', 'Período preferido': 'Noite'})]
        externo, funil, eventos = self.simular(rows)
        self.assertTrue(processar_envio_funil(envio, self.conn, self.cursor))
        self.assertEqual(eventos, ['GET', 'GET', 'DASH', 'FUNIL'])
        self.assertEqual(rows[0]['Nome'], 'Ana Paula Silva')
        self.assertEqual(rows[0]['Período preferido'], 'Tarde')
        self.assertEqual(rows[0]['Canal'], 'Chat Fire')
        self.assertTrue(rows[0]['Observação'].startswith(ROW['Observação']))
        self.assertIn('CHAT FIRE', rows[0]['Observação'])
        self.assertEqual(funil.call_args.kwargs['codigo_canal_venda'], '113481')
        self.assertEqual(self.conn.execute('SELECT count(*) FROM chatbot.consulta_fireads').fetchone()[0], 0)
        self.assertEqual(self.conn.execute('SELECT origem_fireads,lead_no_dash,lead_no_funil FROM chatbot.conversa WHERE id_conversa=%s', (cid,)).fetchone(), ('chat_fire', True, True))

    def test_get_timeout_nao_congela_origem_nem_envia_nem_cria(self):
        cid, envio = self.concluida()
        externo, funil, eventos = self.simular([])
        externo.consultar.side_effect = TimeoutError('Leitura indisponível')
        self.assertFalse(processar_envio_funil(envio, self.conn, self.cursor))
        funil.assert_not_called()
        externo.enviar.assert_not_called()
        self.assertEqual(self.conn.execute('SELECT count(*) FROM chatbot.envios_dash').fetchone()[0], 0)
        self.assertEqual(self.conn.execute('SELECT status,snapshot FROM chatbot.funil_envios').fetchone(), ('pending', None))

    def test_post_com_resposta_perdida_reconcilia_destino_e_so_depois_envia_funil(self):
        cid, envio = self.concluida()
        rows = [dict(ROW, Canal='Chat Fire', **{'Período preferido': 'Noite'})]
        externo, funil, eventos = self.simular(rows)
        escrever = externo.enviar.side_effect

        def perder_resposta(*args, **kwargs):
            escrever(*args, **kwargs)
            raise TimeoutError('Gravou e perdeu resposta')

        externo.enviar.side_effect = perder_resposta
        self.assertFalse(processar_envio_funil(envio, self.conn, self.cursor))
        funil.assert_not_called()
        congelado = self.conn.execute('SELECT snapshot FROM chatbot.envios_dash').fetchone()[0]
        # Novo cadastro e edição local não mudam o destino de uma entrega iniciada.
        rows.append(dict(ROW, _row=999, Canal='Google Ads', **{'Período preferido': 'Manhã'}))
        self.assertTrue(processar_envio_funil(self.retry(), self.conn, self.cursor))
        self.assertEqual(externo.enviar.call_count, 1)
        self.assertEqual(rows[0]['Observação'].count('[INICIO CHATBOT:'), 1)
        self.assertEqual(rows[1]['Observação'], ROW['Observação'])
        self.assertEqual(self.conn.execute('SELECT snapshot FROM chatbot.envios_dash').fetchone()[0], congelado)
        self.assertEqual(funil.call_args.kwargs['codigo_canal_venda'], '113481')

    def test_somente_manuais_cria_organico_e_retry_funil_nao_reenvia_dashboard(self):
        cid, envio = self.concluida()
        rows = [dict(ROW, Canal='Indicação'), dict(ROW, _row=45, Canal='Lead Franqueador')]
        antes = deepcopy(rows)
        externo, funil, eventos = self.simular(rows)
        sucesso_funil = funil.side_effect
        funil.side_effect = TimeoutError('Funil indisponível')
        self.assertFalse(processar_envio_funil(envio, self.conn, self.cursor))
        self.assertEqual(rows[:2], antes)
        self.assertEqual(rows[2]['Canal'], 'Orgânico')
        self.assertEqual(self.conn.execute('SELECT status FROM chatbot.envios_dash').fetchone()[0], 'sent')
        funil.side_effect = sucesso_funil
        self.assertTrue(processar_envio_funil(self.retry(), self.conn, self.cursor))
        self.assertEqual(externo.enviar.call_count, 1)
        self.assertEqual(externo.consultar.call_count, 2)
        self.assertEqual(funil.call_args.kwargs['codigo_canal_venda'], '113481')

    def test_sem_fireads_envia_direto_com_codigo_da_unidade(self):
        cid, envio = self.concluida(fireads=False)
        externo, funil, eventos = self.simular([])
        self.assertTrue(processar_envio_funil(envio, self.conn, self.cursor))
        externo.consultar.assert_not_called()
        externo.enviar.assert_not_called()
        self.assertEqual(funil.call_args.kwargs['codigo_canal_venda'], '113340')

    def test_anuncio_confirmado_no_banco_e_snapshot_sem_consulta_inicial(self):
        cid, envio = self.concluida()
        contexto = self.conn.execute('SELECT contexto_fireads FROM chatbot.conversa WHERE id_conversa=%s', (cid,)).fetchone()[0]
        self.assertIsNone(ler(contexto, cid))
        self.conn.commit()
        rows = [dict(ROW, Canal='Meta Ads', Anuncio='QR001 [form-8.0]', **{'Período preferido': ''})]
        self.simular(rows)
        self.assertTrue(processar_envio_funil(envio, self.conn, self.cursor))
        ctx = self.conn.execute('SELECT contexto_fireads FROM chatbot.conversa WHERE id_conversa=%s', (cid,)).fetchone()[0]
        snap = self.conn.execute('SELECT snapshot FROM chatbot.envios_dash').fetchone()[0]
        self.assertEqual(ler(ctx, cid)['anuncio'], 'QR001 [form-8.0]')
        self.assertEqual(snap[CHAVE], ctx[CHAVE])
        self.assertEqual(ctx['id_conversa'], cid)

    def test_so_organico_cria_novo_e_resposta_perdida_reconcilia_sem_duplicar(self):
        cid, envio = self.concluida()
        rows = [dict(ROW, Canal='Orgânico')]
        antigo = deepcopy(rows[0])
        externo, funil, _ = self.simular(rows)
        escrever = externo.enviar.side_effect
        def perder(*args, **kwargs):
            escrever(*args, **kwargs)
            raise TimeoutError('Resposta perdida')
        externo.enviar.side_effect = perder
        self.assertFalse(processar_envio_funil(envio, self.conn, self.cursor))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0], antigo)
        self.assertTrue(processar_envio_funil(self.retry(), self.conn, self.cursor))
        externo.enviar.assert_called_once()
        self.assertEqual(len(rows), 2)

    def test_duplicidade_explicita_recupera_atualizando_so_o_organico(self):
        cid, envio = self.concluida()
        rows = [dict(ROW, Canal='Orgânico', **{'Período preferido': ''}), dict(ROW, _row=99, Canal='Indicação')]
        externo, funil, _ = self.simular(rows)
        escrever = externo.enviar.side_effect
        externo.enviar.side_effect = TelefoneDuplicadoFireAds('Telefone duplicado')
        self.assertFalse(processar_envio_funil(envio, self.conn, self.cursor))
        funil.assert_not_called()
        snap = self.conn.execute('SELECT snapshot FROM chatbot.envios_dash').fetchone()[0]
        self.assertTrue(snap['append_recusado_duplicidade'])
        externo.enviar.side_effect = escrever
        self.assertTrue(processar_envio_funil(self.retry(), self.conn, self.cursor))
        self.assertEqual(externo.enviar.call_args.kwargs['row'], 44)
        self.assertEqual(rows[1]['Observação'], ROW['Observação'])
        self.assertEqual(len(rows), 2)

    def test_consulta_inicial_captura_anuncio_mesmo_com_dados_parciais(self):
        cid, msg, v, ctx = self.inicio('Olá')
        with self.assertRaises(ConsultaFireAdsPendente):
            preparar_abertura(ctx, msg, v, self.cursor)
        self.conn.commit()
        coleta_testes.ColetaPostgresTests.concluir(self, [dict(ROW, Canal='Meta Ads', Anuncio='QR002', Email='')])
        novo = preparar_abertura(ctx, msg, v, self.cursor)
        self.conn.commit()
        self.assertEqual(ler(novo['contexto_fireads'], cid)['anuncio'], 'QR002')
        self.assertNotEqual(novo['contexto_coleta']['campos']['email']['status'], 'aceito')

    def test_reserva_apos_fila_recebe_300s_e_margem_sem_disputa(self):
        cid, msg, v, ctx = self.inicio('Oi')
        with self.assertRaises(ConsultaFireAdsPendente):
            preparar_abertura(ctx, msg, v, self.cursor)
        self.cursor.execute("UPDATE chatbot.consulta_fireads SET prazo_final=clock_timestamp()+INTERVAL '1 second'")
        self.conn.commit()
        reserva = pendencias.reservar(self.cursor)
        self.conn.commit()
        self.assertGreater(float(reserva['restante']), 325)
        with psycopg.connect(DSN) as outra:
            self.assertIsNone(pendencias.reservar(outra.cursor()))
        pendencias.liberar_reserva(reserva['id_consulta'], self.cursor)
        self.conn.commit()

    def test_reserva_dash_nao_expira_aos_tres_minutos(self):
        cid, envio = self.concluida()
        externo, funil, eventos = self.simular([])
        externo.enviar.side_effect = TimeoutError('Sem recibo')
        self.assertFalse(processar_envio_funil(envio, self.conn, self.cursor))
        self.cursor.execute("UPDATE chatbot.envios_dash SET status='processing',processing_started_at=clock_timestamp()-INTERVAL '5 minutes'")
        self.conn.commit()
        self.assertIsNone(envios.reservar(self.cursor))
        self.conn.commit()
