"""Regressões das novas regras, prova do retry e recortes do painel."""

import sqlite3
import unittest
from unittest.mock import patch

from core.integrations.whatsapp.messages.etapa6_messages import (
    montar_mensagem_cliente_menor_18_etapa6,
    montar_mensagem_dependente_menor_5_etapa6,
    montar_mensagem_idade_acima_99_etapa6,
    montar_mensagem_suporte_idoso_etapa6,
)
from core.repositories.monitoramento.encerramentos import (
    buscar_encerramentos_atuais, contar_encerramentos_por_motivo,
)
from monitoramento.encerramentos import apresentar_encerramento, montar_tabela_encerramentos
from tests.unit.test_suporte_idoso_email_obrigatorio import contexto_etapa6, contexto_envio
from workers.worker_flow.response_flow.etapas import resolver_etapa6
from workers.worker_flow.transacoes.encerramento_atendimento import resolver_intencao_encerramento


class RecuperacaoIdadeTests(unittest.TestCase):
    def recuperar(self, idade, resposta, *, suporte=80, dependente=False, tipo='interactive_cta_url', bpa=False):
        contexto = contexto_etapa6(idade, suporte=suporte, dependente=dependente)
        contexto.update(idade_cliente=88, bpa_ativo_unidade=bpa)
        contexto['resposta_bot_para_mensagem_atual'] = {
            'tipo_mensagem': tipo, 'conteudo_texto': 'Bom te ver novamente ☺️\n\n' + resposta,
        }
        return resolver_intencao_encerramento(contexto, {'resposta_ja_existia': True}, object())

    def test_faixa_compativel_usa_entrada_e_nao_cadastro_global(self):
        for idade, suporte, motivo in (
            (51, 60, 'suporte_idoso_50'), (60, 80, 'suporte_idoso_60'),
            (71, 80, 'suporte_idoso_70'), (71, 60, 'suporte_idoso_60'),
            (61, None, 'suporte_idoso_60'), (95, 80, 'encaminhado_suporte_idoso'),
            ('71 anos', 80, 'suporte_idoso_70'),
            ('71 anos de idade', 80, 'suporte_idoso_70'),
            ('Setenta e um', 80, 'suporte_idoso_70'),
            ('não sei', 60, 'encaminhado_suporte_idoso'),
        ):
            with self.subTest(idade=idade, suporte=suporte):
                resultado = self.recuperar(idade, montar_mensagem_suporte_idoso_etapa6(50), suporte=suporte)
                self.assertEqual(resultado['motivo_encerramento'], motivo)
                self.assertEqual(resultado['bloqueio_dias'], 0)

    def test_bpa_mudou_mas_corpo_preserva_minimo_enviado(self):
        resposta = montar_mensagem_dependente_menor_5_etapa6('João', 5)
        resultado = self.recuperar(4, resposta, dependente=True, tipo='text', bpa=True)
        self.assertEqual(resultado['motivo_encerramento'], 'dependente_menor_5')
        self.assertTrue(resultado['excluir_dependente'])

    def test_oferta_ou_tratamento_nao_vira_encerramento(self):
        for idade, dependente, texto, tipo in (
            (95, False, 'Vamos reservar sua experiência?', 'interactive_button'),
            (4, True, 'Vamos reservar sua experiência?', 'interactive_button'),
            (12, False, 'Olha, digite apenas texto.', 'text'),
            (51, False, montar_mensagem_suporte_idoso_etapa6(50), 'text'),
        ):
            with self.subTest(idade=idade, tipo=tipo):
                self.assertIsNone(self.recuperar(idade, texto, dependente=dependente, tipo=tipo))

    def test_menor_e_universal_comprovados(self):
        menor = self.recuperar(17, montar_mensagem_cliente_menor_18_etapa6(), tipo='text')
        self.assertEqual(menor['motivo_encerramento'], 'titular_menor_18')
        for dependente in (False, True):
            atual = self.recuperar(90, montar_mensagem_idade_acima_99_etapa6(), dependente=dependente)
            legado = self.recuperar(100, montar_mensagem_idade_acima_99_etapa6(), dependente=dependente)
            self.assertEqual(atual['motivo_encerramento'], 'idade_universal_90')
            self.assertEqual(legado['motivo_encerramento'], 'idade_invalida')

    def test_nova_conversa_71_com_limite80_segue_e_90_encerra(self):
        with patch.object(resolver_etapa6, 'enviar_etapa7_cliente', return_value=contexto_envio(7)) as oferta:
            resultado = resolver_etapa6.resolve_etapa6(contexto_etapa6(71, suporte=80))
        oferta.assert_called_once()
        self.assertNotIn('encerrar_atendimento', resultado)
        with patch.object(resolver_etapa6, 'enviar_etapa6_idade_acima_99', return_value=contexto_envio(6)):
            resultado = resolver_etapa6.resolve_etapa6(contexto_etapa6(90, suporte=None))
        intencao = resolver_intencao_encerramento({}, resultado, object())
        self.assertEqual(intencao['motivo_encerramento'], 'idade_universal_90')
        self.assertEqual(intencao['bloqueio_dias'], 0)

    def test_retry_universal_preserva_categoria_apos_ativar_suporte80(self):
        for texto_idade, dependente in (
            ('Noventa e um anos', False),
            ('92 anos de idade', True),
        ):
            with self.subTest(texto_idade=texto_idade, dependente=dependente):
                # Primeira tentativa: sem suporte, ambos saem pela universal.
                with patch.object(
                    resolver_etapa6, 'enviar_etapa6_idade_acima_99',
                    return_value=contexto_envio(6),
                ) as enviar:
                    envio = resolver_etapa6.resolve_etapa6(
                        contexto_etapa6(texto_idade, suporte=None, dependente=dependente)
                    )
                    enviar.assert_called_once()
                    original = resolver_intencao_encerramento({}, envio, object())
                    enviar.reset_mock()
                    # Histórico salvo, finalização pendente; suporte mudou para 80.
                    recuperada = self.recuperar(
                        texto_idade, montar_mensagem_idade_acima_99_etapa6(),
                        suporte=80, dependente=dependente,
                    )
                    enviar.assert_not_called()
                self.assertEqual(recuperada, original)
                self.assertEqual(recuperada['motivo_encerramento'], 'idade_universal_90')
                self.assertEqual(recuperada['bloqueio_dias'], 0)
                self.assertFalse(recuperada['excluir_dependente'])


class CursorSQLite:
    def __init__(self, conexao):
        self.conexao = conexao

    def execute(self, sql, parametros):
        self.cursor = self.conexao.execute(sql.replace('%s', '?'), parametros)
        self.description = self.cursor.description

    def fetchall(self):
        return self.cursor.fetchall()


class PainelEncerramentosTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        self.addCleanup(self.conn.close)
        self.conn.execute("ATTACH DATABASE ':memory:' AS chatbot")
        self.conn.executescript('''
            CREATE TABLE chatbot.conversa (
                id_conversa INTEGER PRIMARY KEY, id_cliente INTEGER, id_unidade INTEGER,
                status_dependente BOOLEAN, status_ativa BOOLEAN, id_etapa_atual INTEGER,
                motivo_encerramento TEXT, finalizou_em TEXT
            );
            CREATE TABLE chatbot.historico_mensagens (
                id_mensagem INTEGER PRIMARY KEY, id_conversa INTEGER, id_etapa INTEGER,
                quem_enviou TEXT, status_envio TEXT, conteudo_texto TEXT, tipo_mensagem TEXT,
                received_data_hora TEXT, id_hash_msg TEXT, id_hash_cliente_origem TEXT
            );
        ''')
        self.cursor = CursorSQLite(self.conn)

    def conversa(self, numero, cliente=1, unidade=1, motivo='suporte_idoso_60', dependente=False,
                 data='2026-09-15', ativa=False, etapa=6):
        self.conn.execute('INSERT INTO chatbot.conversa VALUES(?,?,?,?,?,?,?,?)',
                          (numero, cliente, unidade, dependente, ativa, etapa, motivo, data))

    def historico(self, conversa, idade='61', resposta=None, tipo='interactive_cta_url'):
        base = conversa * 10
        self.conn.execute('INSERT INTO chatbot.historico_mensagens VALUES(?,?,?,?,?,?,?,?,?,?)',
                          (base, conversa, 6, 'cliente', None, idade, 'text', '2026-09-15', f'entrada-{base}', None))
        self.conn.execute('INSERT INTO chatbot.historico_mensagens VALUES(?,?,?,?,?,?,?,?,?,?)',
                          (base+1, conversa, 6, 'bot', 'sent', resposta or montar_mensagem_suporte_idoso_etapa6(60),
                           tipo, '2026-09-15', f'saida-{base}', f'entrada-{base}'))

    def test_nova_conversa_remove_tag_inclusive_fora_do_periodo(self):
        self.conversa(1)
        self.historico(1)
        rows = buscar_encerramentos_atuais(1, [1], self.cursor)
        self.assertEqual(apresentar_encerramento(rows[0])['tag'], '60+')
        # Outra unidade não interfere, mesmo com o mesmo cliente e ID maior.
        self.conversa(2, unidade=2, ativa=True, motivo=None, data=None)
        self.assertEqual(len(buscar_encerramentos_atuais(1, [1, 2], self.cursor)), 1)
        self.assertEqual(buscar_encerramentos_atuais(2, [1], self.cursor), [])
        self.conversa(3, ativa=True, motivo=None, data=None, etapa=1)
        self.assertEqual(buscar_encerramentos_atuais(1, [1], self.cursor), [])
        # O relatório continua contando a conversa antiga encerrada no período.
        contagens = contar_encerramentos_por_motivo(1, '2026-09-01', '2026-10-01', self.cursor)
        self.assertEqual(contagens[0]['conversas'], 1)

    def test_historico_pareado_sobrevive_sem_fila_e_sem_dependente(self):
        self.conversa(1, motivo='dependente_menor_5', dependente=True)
        self.historico(1, '4', montar_mensagem_dependente_menor_5_etapa6('Lia', 5), 'text')
        # Não existem tabelas fila/dependente neste cenário: o vínculo é histórico.
        row = buscar_encerramentos_atuais(1, [1], self.cursor)[0]
        item = apresentar_encerramento(row)
        self.assertEqual((item['nome_dependente'], item['resposta_idade']), ('Lia', '4'))
        self.assertFalse(item['contato_enviado'])
        self.assertEqual(item['tag'], 'Limite mínimo')

    def test_conta_conversas_configuracao_atual_periodo_e_unidade(self):
        self.conversa(1, data='2026-09-01')
        self.conversa(2)  # Mesmo titular, duas conversas: contar duas.
        self.conversa(3, motivo='suporte_idoso_50')
        self.conversa(4, motivo='idade_universal_90')
        self.conversa(5, motivo='idade_universal_90', dependente=True)
        self.conversa(6, motivo='titular_menor_18')
        self.conversa(7, motivo='dependente_menor_4', dependente=True)
        self.conversa(8, motivo='dependente_menor_5', dependente=True)
        self.conversa(9, unidade=2)
        self.conversa(10, data='2026-10-01')
        self.conversa(11, data='2026-08-31')
        self.conversa(12, ativa=True)
        self.conversa(13, motivo='encaminhado_suporte_idoso')
        self.conversa(14, data=None)
        self.conversa(15, etapa=18)
        contagens = contar_encerramentos_por_motivo(1, '2026-09-01', '2026-10-01', self.cursor)
        tabela = montar_tabela_encerramentos(contagens, idade_minima_suporte=60, bpa_ativo=True)
        self.assertEqual([l['conversas'] for l in tabela['linhas']], [2, 1, 1, 1, 1])
        self.assertEqual((tabela['total_encaminhadas'], tabela['total_sem_encaminhamento']), (4, 2))
        desligada = montar_tabela_encerramentos(contagens, idade_minima_suporte=None, bpa_ativo=False)
        self.assertEqual(len(desligada['linhas']), 4)
        self.assertEqual(desligada['total_encaminhadas'], 2)
        self.assertEqual(desligada['linhas'][-1]['motivo'], 'dependente_menor_5')
        self.assertEqual(desligada['linhas'][-1]['conversas'], 1)

    def test_nao_transformar_legado_em_faixa_inventada(self):
        self.conversa(1, motivo='encaminhado_suporte_idoso')
        self.historico(1, '71')
        row = buscar_encerramentos_atuais(1, [1], self.cursor)[0]
        self.assertEqual(apresentar_encerramento(row)['tag'], 'Suporte por idade')


if __name__ == '__main__':
    unittest.main()
