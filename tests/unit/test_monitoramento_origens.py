"""Origens comprovadas, contagem por conversa e recusa explícita de duplicidade."""
from copy import deepcopy
import json
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace
from datetime import datetime, timezone

from callback.monitoramento.origens import montar_origens
from callback.monitoramento.apresentacao import consolidar_conversas
from core.integrations.fireads.atribuicao import CHAVE, capturar, vincular, ler
from core.integrations.fireads.cliente import ClienteFireAds, TelefoneDuplicadoFireAds
from core.integrations.fireads.contrato import ABA_DESTINO, ErroFireAds
from tests.unit.test_coleta_abertura import ROW
from core.repositories.monitoramento import painel as repositorio_painel


def contexto(cid, canal='Meta Ads', anuncio=None, momento='consulta_inicial'):
    row = dict(ROW, Canal=canal, Anuncio=anuncio) if canal else None
    return {CHAVE: vincular(capturar(row, ABA_DESTINO, momento=momento), cid)}


class OrigensTests(unittest.TestCase):
    def test_json_textual_do_django_preserva_origem_nova_e_legada(self):
        row = dict(ROW, Canal='Meta Ads', Anuncio='QR001 legado')
        legado = {'referencia': capturar(row, ABA_DESTINO)['referencia']}
        dados = {'fontes': {'geral': [row]}}
        colunas = ['id_conversa', 'id_cliente', 'contexto_fireads', 'dados_consulta', 'ultima_mensagem']
        for serializar in (lambda v: v, json.dumps):
            cursor = Mock(description=[(c,) for c in colunas])
            cursor.fetchall.return_value = [
                (1, 10, serializar(contexto(1, anuncio='QR001 novo')), None, '{texto da mensagem}'),
                (2, 11, serializar(legado), serializar(dados), 'Olá'),
            ]
            linhas = repositorio_painel._linhas(cursor)
            self.assertEqual(linhas[0]['ultima_mensagem'], '{texto da mensagem}')
            conversas = consolidar_conversas(linhas)
            self.assertEqual({c['origem']['anuncio'] for c in conversas}, {'QR001 novo', 'QR001 legado'})
            relatorio = montar_origens(linhas)
            meta = next(c for c in relatorio['canais'] if c['canal'] == 'meta')
            self.assertEqual(meta['atendimentos'], 2)

    def test_json_ausente_ou_invalido_nao_inventa_origem_nem_quebra_painel(self):
        for valor in (None, '', '{invalido', 'null', '[]', 'true', '12', '"texto"', [], False):
            with self.subTest(valor=valor):
                cursor = Mock(description=[(c,) for c in ('id_conversa', 'id_cliente', 'contexto_fireads', 'dados_consulta')])
                cursor.fetchall.return_value = [(1, 10, valor, valor)]
                linhas = repositorio_painel._linhas(cursor)
                self.assertIsNone(consolidar_conversas(linhas)[0]['origem'])
                self.assertEqual(montar_origens(linhas)['sem_origem'], 1)

    def test_provisorio_codigo_compartilhado_e_lead_no_dash_nao_provam_origem(self):
        for ctx in ({}, {'origem': 'meta'}, {'origem': 'organico', 'lead_no_dash': True},
                    {'codigo_canal_venda': '113481'}, {CHAVE: {'versao': 2}}, contexto(99)):
            self.assertIsNone(ler(ctx, 1))

    def test_anuncio_so_meta_google_e_payload_publico_nao_expoe_referencia(self):
        for canal in ('Google Ads', 'Meta Ads', 'Chat Fire', 'Orgânico Site', None):
            ctx = contexto(1, canal, '  QR001  [form-8.0] \n')
            origem = ler(ctx, 1)
            self.assertEqual(origem['fireads'], bool(canal))
            self.assertEqual(origem['anuncio'], 'QR001 [form-8.0]' if canal in ('Meta Ads', 'Google Ads') else None)
            self.assertEqual(set(origem), {'canal', 'rotulo', 'anuncio', 'fireads'})
            self.assertNotIn('ana@example.com', str(origem))

    def test_final_preserva_captura_inicial_e_nao_muda_outro_contexto(self):
        inicial = contexto(1, anuncio='Primeiro')[CHAVE]
        antes = deepcopy(inicial)
        final = vincular(capturar(dict(ROW, Canal='Meta Ads', Anuncio='Segundo'),
                                 ABA_DESTINO, momento='entrega'), 1, inicial)
        self.assertEqual(final['inicial'], antes)
        self.assertEqual(inicial, antes)
        self.assertEqual(ler({CHAVE: final}, 1)['anuncio'], 'Segundo')

    def test_legado_so_usa_anuncio_da_linha_salva_sem_inferir_o_atual(self):
        row = dict(ROW, Canal='Meta Ads', Anuncio='Criativo antigo')
        ref = capturar(row, ABA_DESTINO)['referencia']
        ctx = {'referencia': ref}
        self.assertIsNone(ler(ctx, 1)['anuncio'])
        outro = dict(row, Nome='Outro', Anuncio='Criativo de outro lead')
        dados = {'fontes': {'geral': [outro, row]}}
        self.assertEqual(ler(ctx, 1, dados)['anuncio'], 'Criativo antigo')
        dados['fontes']['geral'] = [outro]
        self.assertIsNone(ler(ctx, 1, dados)['anuncio'])

    def test_relatorio_conta_conversas_e_contatos_separadamente(self):
        linhas = [
            {'id_conversa': 1, 'id_cliente': 10, 'contexto_fireads': contexto(1, anuncio='QR001'), 'foi_funil': True},
            {'id_conversa': 2, 'id_cliente': 10, 'contexto_fireads': contexto(2, 'Google Ads'), 'foi_funil': False},
            {'id_conversa': 3, 'id_cliente': 11, 'contexto_fireads': contexto(3), 'foi_funil': True},
            {'id_conversa': 4, 'id_cliente': 12, 'contexto_fireads': contexto(4, None)},
            {'id_conversa': 5, 'id_cliente': 13, 'contexto_fireads': {'origem': 'meta'}},
        ]
        r = montar_origens(linhas + [linhas[0]])
        self.assertEqual((r['atendimentos'], r['contatos_unicos'], r['sem_origem']), (5, 4, 1))
        canais = {x['canal']: x for x in r['canais']}
        self.assertEqual((canais['meta']['atendimentos'], canais['meta']['funil']), (2, 2))
        self.assertEqual(canais['organico']['atendimentos'], 1)
        self.assertEqual({a['anuncio'] for a in r['anuncios']}, {None, 'QR001'})

    def test_ultima_conversa_nao_herda_avaliacao_funil_destinatario_ou_origem(self):
        antiga = {'id_cliente': 1, 'id_conversa': 10, 'iniciou_em': '2026-10-01',
                  'status_dependente': True, 'avaliada': True, 'foi_funil': True,
                  'followup_stage_atual': 2, 'contexto_fireads': contexto(10)}
        nova = dict(antiga, id_conversa=11, iniciou_em='2026-10-02', status_dependente=None,
                    avaliada=False, foi_funil=False, followup_stage_atual=0, contexto_fireads={})
        r = consolidar_conversas([nova, antiga])[0]
        self.assertFalse(r['avaliada'])
        self.assertFalse(r['foi_funil'])
        self.assertIsNone(r['destinatario'])
        self.assertIsNone(r['origem'])
        self.assertEqual(r['ids_conversa'], [10, 11])
        self.assertTrue(consolidar_conversas([antiga])[0]['avaliada'])


class DuplicidadeTests(unittest.TestCase):
    def test_apenas_recusa_explicita_autoriza_fallback(self):
        for corpo, esperado in (({'success': False, 'code': 'DUPLICATE_PHONE'}, TelefoneDuplicadoFireAds),
                                ({'success': False, 'error': 'Telefone já cadastrado'}, TelefoneDuplicadoFireAds),
                                ({'success': False, 'error': 'Falha no servidor'}, ErroFireAds)):
            with self.subTest(corpo=corpo):
                session = Mock()
                session.request.return_value = Mock(status_code=200, json=Mock(return_value=corpo))
                cliente = ClienteFireAds('https://script.google.com/macros/s/teste/exec', session=session)
                with self.assertRaises(esperado) as erro:
                    cliente.enviar(ABA_DESTINO, dados={})
                self.assertIs(type(erro.exception), esperado)
                session.request.assert_called_once()
                cliente.close()


class ServicoOrigensTests(unittest.TestCase):
    def test_unidade_sem_fireads_nao_expoe_origem_e_nem_consulta_metricas_fireads(self):
        from callback.monitoramento import services
        unidade = {'nome_unidade': 'Teste', 'nome_agente': 'Dora', 'fireads_habilitada': False,
                   'idade_minima_suporte': None, 'email_obrigatorio': True, 'bpa_ativo': True}
        periodo = SimpleNamespace(inicio=None, fim=datetime.now(timezone.utc),
                                  chave='total', rotulo='Todo o histórico', inicio_anterior=None)
        linha = {'id_conversa': 1, 'id_cliente': 1, 'contexto_fireads': contexto(1)}
        for habilitada in (False, True):
            unidade['fireads_habilitada'] = habilitada
            with patch.object(services, 'connection'), \
                 patch.object(services.repositorio, 'buscar_unidade', return_value=unidade), \
                 patch.object(services.repositorio, 'listar_conversas', return_value=[linha]), \
                 patch.object(services.repositorio, 'buscar_metricas', return_value={}), \
                 patch.object(services.repositorio_encerramentos, 'buscar_encerramentos_atuais', return_value=[]):
                r = services.carregar_conversas(SimpleNamespace(id_unidade=1), periodo)
                self.assertEqual(r['unidade']['fireads_habilitada'], habilitada)
                self.assertEqual(r['conversas'][0]['origem'] is not None, habilitada)
                self.assertNotIn('contexto_fireads', r['conversas'][0])
        with patch.object(services, 'connection'), \
             patch.object(services.repositorio, 'buscar_unidade', return_value=dict(unidade, fireads_habilitada=False)), \
             patch.object(services.repositorio, 'buscar_metricas', return_value={}), \
             patch.object(services.repositorio_encerramentos, 'contar_encerramentos_por_motivo', return_value=[]), \
             patch.object(services.repositorio, 'buscar_perfis', return_value=[]), \
             patch.object(services.repositorio, 'buscar_satisfacao', return_value=[]), \
             patch.object(services.repositorio, 'buscar_etapas', return_value=[]), \
             patch.object(services.repositorio, 'buscar_atividade', return_value=[]), \
             patch.object(services, 'distribuir_dependentes_por_titular', return_value={}), \
             patch.object(services.repositorio, 'buscar_origens') as origens:
            r = services.carregar_relatorio(SimpleNamespace(id_unidade=1), periodo)
            origens.assert_not_called()
            self.assertIsNone(r['origens'])
