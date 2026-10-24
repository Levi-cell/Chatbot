"""Consulta somente leitura, conclusão sem canal, orçamento e retomada por estado."""

import os
import unittest
from copy import deepcopy
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock, patch

from core.integrations.fireads.atribuicao import CHAVE, CHAVE_VERIFICACAO, capturar, ler, vincular
from core.integrations.fireads.contrato import ABA_DESTINO, ErroFireAds
from core.integrations.fireads.origem import identificar
from tests.unit.test_coleta_abertura import ROW
from workers.worker_origem_fireads import origem_worker as worker
from workers.worker_origem_fireads.config import configuracao, INTERVALO_SEGUNDOS
from callback.monitoramento.origens import montar_origens


def resposta(rows):
    return {'aba': ABA_DESTINO, 'headers': ['WhatsApp', 'Canal', 'Data/Hora'], 'rows': rows}


def consultar(rows):
    return identificar(resposta(rows), numero=ROW['WhatsApp'], aba=ABA_DESTINO,
                       fuso='America/Sao_Paulo', id_conversa=1, id_integracao=1)


class ClassificacaoTests(unittest.TestCase):
    def test_canais_conhecidos_e_anuncios(self):
        for canal in ('Meta Ads', 'Google Ads', 'Chat Fire', 'Orgânico Site'):
            resultado = consultar([dict(ROW, Canal=canal, Anuncio=' Novo  criativo ')])
            self.assertEqual(resultado[CHAVE_VERIFICACAO]['status'], 'concluida')
            self.assertEqual(ler(resultado, 1)['anuncio'],
                             'Novo criativo' if canal in ('Meta Ads', 'Google Ads') else None)

    def test_ausencia_e_canais_manuais_sao_organicos(self):
        for rows in ([], [dict(ROW, Canal='Orgânico')], [dict(ROW, Canal='Indicação')],
                     [dict(ROW, Canal='Lead Franqueador')]):
            self.assertEqual(ler(consultar(rows), 1)['canal'], 'organico')

    def test_canal_nao_informado_conclui_sem_erro_sem_fallback(self):
        for valor in (None, '', 'Canal futuro'):
            r = consultar([dict(ROW, Canal=valor)])
            self.assertNotIn(CHAVE, r)
            self.assertEqual(r[CHAVE_VERIFICACAO]['resultado'], 'canal_nao_informado')
            r.update(origem='organico')
            self.assertIsNone(ler(r, 1, {'decisao': {'resultado': 'ausente', 'motivo': 'telefone_ausente'}}))

    def test_formulario_valido_tem_prioridade_sobre_canal_vazio(self):
        r = consultar([dict(ROW, Canal=None, _row=999), dict(ROW, Canal='Chat Fire')])
        self.assertEqual(ler(r, 1)['canal'], 'chat_fire')

    def test_recencia_e_variantes_nao_filtram_por_nome_email(self):
        for numero in ('(11) 99999-0002', '+55 11 99999-0002', 'p:+5511999990002', '551199990002'):
            row = dict(ROW, WhatsApp=numero, Nome='Outro nome', Email='outro@example.org', Canal='Google Ads', _row=99)
            r = identificar(resposta([dict(row, _row=2, Canal='Meta Ads'), row]), numero='5511999990002',
                            aba=ABA_DESTINO, fuso=None, id_conversa=1, id_integracao=1)
            self.assertEqual(r[CHAVE]['canal'], 'google')
            self.assertEqual(r[CHAVE]['referencia']['linha'], 99)

    def test_resposta_invalida_nao_gera_organico(self):
        for r in ({}, resposta([None]), dict(resposta([]), headers=['WhatsApp']),
                  resposta([{'WhatsApp': ROW['WhatsApp']}])):
            with self.assertRaises(ErroFireAds):
                identificar(r, numero=ROW['WhatsApp'], aba=ABA_DESTINO, fuso=None, id_conversa=1, id_integracao=1)

    def test_funil_preserva_evidencia_periodica_e_corrige_anuncio(self):
        anterior = consultar([dict(ROW, Canal='Meta Ads', Anuncio='Antes')])[CHAVE]
        copia = deepcopy(anterior)
        atual = vincular(capturar(dict(ROW, Canal='Meta Ads', Anuncio='Depois'), ABA_DESTINO,
                                 momento='preparacao_entrega'), 1, anterior)
        self.assertEqual(atual['periodica'], copia)
        self.assertEqual(ler({CHAVE: atual}, 1)['anuncio'], 'Depois')
        self.assertEqual(anterior, copia)


class CicloTests(unittest.TestCase):
    def setUp(self):
        self.conn = MagicMock()
        self.cursor = self.conn.cursor.return_value.__enter__.return_value
        self.enterContext(patch.object(worker, 'get_conn', return_value=self.conn))
        self.repo = self.enterContext(patch.object(worker, 'origens'))
        self.repo.adquirir_ciclo.return_value = True
        self.repo.limite_ciclo.return_value = 2
        self.repo.concluir.return_value = True
        self.repo.revalidar_grupo.side_effect = lambda cursor, grupo, desde: grupo
        self.http = self.enterContext(patch.object(worker, 'ClienteFireAds'))
        self.item = dict(id_conversa=1, id_unidade=1, id_integracao=1, url='https://script.google.com/macros/s/teste/exec',
                         aba=ABA_DESTINO, fuso=None, numero=ROW['WhatsApp'])
        self.repo.listar.side_effect = [[self.item], [dict(self.item, id_conversa=2)], []]
        self.http.return_value.consultar.return_value = resposta([dict(ROW, Canal='Meta Ads')])

    def rodar(self):
        return worker.executar_ciclo(datetime(2026, 10, 24, tzinfo=timezone.utc))

    def test_reaproveita_leitura_entre_paginas_sem_post(self):
        r = self.rodar()
        self.assertEqual((r['identificados'], r['consultas']), (2, 1))
        self.http.assert_called_once_with(self.item['url'], segundos=300, timeout_leitura=None)
        self.http.return_value.enviar.assert_not_called()
        self.conn.close.assert_called_once()
        self.assertEqual(self.repo.listar.call_args_list[1].kwargs['apos'], 1)

    def test_timeout_nao_grava_nem_repete_no_mesmo_ciclo(self):
        self.http.return_value.consultar.side_effect = TimeoutError
        r = self.rodar()
        self.assertEqual((r['falhas'], r['consultas']), (2, 1))
        self.repo.concluir.assert_not_called()

    def test_funil_resolve_durante_http_descarta_resultado(self):
        self.repo.concluir.return_value = False
        self.assertEqual(self.rodar()['descartados'], 2)

    def test_instancia_ocupada_nao_consulta(self):
        self.repo.adquirir_ciclo.return_value = False
        self.assertTrue(self.rodar()['ocupado'])
        self.http.assert_not_called()

    def test_configuracao_exige_marco_fixo_com_fuso(self):
        self.assertEqual(INTERVALO_SEGUNDOS, 7200)
        with patch.dict(os.environ, {'FIREADS_ORIGEM_ATIVO': 'false'}):
            self.assertIsNone(configuracao())
        for data in ('', '2026-10-24', 'ontem'):
            with patch.dict(os.environ, {'FIREADS_ORIGEM_ATIVO': 'true', 'FIREADS_ORIGEM_DESDE': data}):
                with self.assertRaises(ValueError): configuracao()
        with patch.dict(os.environ, {'FIREADS_ORIGEM_ATIVO': 'true', 'FIREADS_ORIGEM_DESDE': '2026-10-24T09:00:00-03:00'}):
            self.assertIsNotNone(configuracao().tzinfo)


class PerfisTests(unittest.TestCase):
    def test_somas_por_canal_e_anuncio_com_desconhecidos_e_dependentes(self):
        linhas = []
        casos = [('meta', True, 65), ('meta', False, 30), ('google', True, 13),
                 ('google', True, None), ('google', None, 40), ('meta', True, 3)]
        for cid, (canal, dependente, idade) in enumerate(casos, 1):
            ctx = {CHAVE: vincular(capturar(dict(ROW, Canal={'meta':'Meta Ads','google':'Google Ads'}[canal],
                                               Anuncio='Mesmo texto'), ABA_DESTINO), cid)}
            linhas.append(dict(id_conversa=cid, id_cliente=1, status_dependente=dependente,
                               idade_dependente=idade, idade_titular=30, contexto_fireads=ctx, foi_funil=cid % 2 == 0))
        r = montar_origens(linhas + [linhas[0]], bpa_ativo=False)
        self.assertEqual(r['contatos_unicos'], 1)
        self.assertEqual(r['atendimentos'], 6)
        for item in r['canais'] + r['anuncios'] + r['anuncios_google']:
            self.assertEqual(sum(p['atendimentos'] for p in item['perfis']), item['atendimentos'])
            self.assertEqual(sum(p['funil'] for p in item['perfis']), item['funil'])
        self.assertEqual(r['anuncios'][0]['atendimentos'], 3)
        self.assertEqual(r['anuncios_google'][0]['atendimentos'], 3)
        chaves = {p['chave'] for c in r['canais'] for p in c['perfis']}
        self.assertTrue({'dependente_idoso', 'dependente_abaixo_minimo', 'dependente_sem_idade', 'nao_informado'} <= chaves)
