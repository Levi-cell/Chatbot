"""Extração, compatibilidade, etapas e entrega; nenhum serviço externo."""
from copy import deepcopy
from itertools import product
import unittest
from unittest.mock import patch

from core.validacoes.coleta_abertura import (
    extrair, criar_contexto, etapa_inicial, completo, campo, valor, email_coletado, destinatario,
)
from core.integrations.fireads.coleta_abertura import interpretar_parcial
from core.integrations.fireads.destino_coleta import escolher, preparar, identidade_entrega
from core.integrations.fireads.contrato import ABA_DESTINO, ErroFireAds, bloco_observacoes
from core.integrations.whatsapp.messages.abertura_coleta import montar_abertura
from workers.worker_flow.transacoes.movimento_conversa import resolver_movimento_conversa

NUMERO = '5511999990002'
FORM = 'Full name: Ana Paula Silva\nEmail: ana@example.com\nPara quem é o treino?: Para mim'
ROW = {'_row': 44, 'Nome': 'Ana Paula Silva', 'Email': 'ana@example.com', 'WhatsApp': NUMERO,
       'Canal': 'Meta Ads', 'Para quem é': 'Para mim', 'Data/Hora': '19/10/2026 10:00', 'Observação': 'Anotação da unidade'}


def estado(texto=FORM):
    coleta = criar_contexto(1, {'id_mensagem': 1, 'id_hash': 'wamid.teste', 'tipo_mensagem': 'text', 'conteudo_texto': texto})
    coleta.update(status='pronto', etapa_inicial=etapa_inicial(coleta))
    return coleta


def snapshot(texto=FORM):
    coleta = estado(texto)
    return {'versao': 3, 'aba': ABA_DESTINO, 'telefone': NUMERO, 'email': 'ana@example.com',
            'nome': 'Ana Paula', 'origem': 'meta', 'perfil': 'Titular (35 anos)', 'para_quem': 'Para mim',
            'fuso': None, 'referencia': None, 'rota_formulario_chat': True,
            'identidade_coleta': identidade_entrega(coleta), 'destino': None}


class ExtracaoTests(unittest.TestCase):
    def test_oito_combinacoes(self):
        partes = ['Full name: Ana Paula Silva', 'Email: ana@example.com', 'Para quem é: Para mim']
        for n, e, d in product((False, True), repeat=3):
            with self.subTest(nome=n, email=e, destinatario=d):
                coleta = estado('\n'.join(p for p, incluir in zip(partes, (n, e, d)) if incluir))
                self.assertEqual(etapa_inicial(coleta), 1 if not n else (4 if d else 2))
                self.assertEqual(completo(coleta), n and e and d)
                self.assertEqual(email_coletado({'id_conversa': 1, 'contexto_coleta': coleta}), e)

    def test_nome_titular_composto_biografia_e_nao_nome_dependente(self):
        campos = extrair('Nome do dependente: Carlos\nFull name: João Pedro Silva | Programador\nEmail: jp@example.com\nPara quem é: Para minha mãe')
        self.assertEqual(campos['nome']['valor'], 'João Pedro')
        self.assertEqual(campos['destinatario']['valor']['chave'], 'mae')
        self.assertEqual(extrair('Olá, quero informações')['nome']['status'], 'ausente')

    def test_duplicatas_identicas_nao_conflitam(self):
        self.assertEqual(extrair(FORM + '\nEmail: ANA@example.com')['email']['status'], 'aceito')

    def test_conflitos_por_campo_nao_apagam_outros(self):
        for extra, tipo in [('Email: outro@example.com', 'email'), ('Full name: Ana Paula Souza', 'nome'),
                            ('Para quem é: Para meu filho', 'destinatario')]:
            with self.subTest(tipo=tipo):
                campos = extrair(FORM + '\n' + extra)
                self.assertEqual(campos[tipo]['status'], 'conflitante')
                self.assertIsNone(campos[tipo]['valor'])
                self.assertTrue(all(campos[c]['status']=='aceito' for c in campos if c != tipo))

    def test_faixa_etaria_nao_inventa_destinatario(self):
        self.assertIsNone(destinatario('61 a 75 anos'))
        for parentesco in ('Para meu pai', 'Para minha tia', 'Para outra pessoa', 'Para mim e outra pessoa'):
            self.assertTrue(destinatario(parentesco)['dependente'])

    def test_telefone_de_formulario_nao_altera_identidade(self):
        self.assertTrue(completo(estado(FORM + '\nPhone number: +5511888880000')))
        self.assertNotIn('telefone', estado(FORM)['campos'])

    def test_sem_fireads_nao_alega_formulario_externo(self):
        coleta = estado()
        ctx = {'id_conversa': 1, 'contexto_coleta': coleta, 'genero': 'feminino', 'nome_agente': 'Dora', 'nome_unidade': 'Teste'}
        texto = montar_abertura(ctx, 'Bom dia')
        self.assertNotIn('formulários', texto)
        self.assertIn('profissão', texto)
        coleta['formulario_identificado'] = True
        self.assertIn('formulários', montar_abertura(ctx, 'Bom dia'))

    def test_inicializacao_so_na_etapa_persistida(self):
        coleta = estado('Full name: Ana\nEmail: ana@example.com')
        ctx = {'id_conversa': 1, 'id_etapa_atual': None, 'contexto_coleta': coleta}
        self.assertEqual(resolver_movimento_conversa(ctx, {'id_etapa_resultante': 2}), 'inicializacao')
        for etapa in (1, 4):
            with self.assertRaises(ValueError):
                resolver_movimento_conversa(ctx, {'id_etapa_resultante': etapa})


class MomentoEmailTests(unittest.TestCase):
    def test_email_pendente_so_e_perguntado_na_etapa_de_email(self):
        from workers.worker_flow.response_flow.etapas import resolver_etapa7, resolver_etapa9

        for trecho, aceito in (
            ('', False),
            ('Email: invalido', False),
            ('Email: ana@example.com\nEmail: outra@example.com', False),
            ('Email: ana@example.com', True),
        ):
            coleta = estado('Full name: Ana Paula Silva\nPara quem é: Para mim\n' + trecho)
            abertura = montar_abertura({
                'id_conversa': 1, 'contexto_coleta': coleta, 'genero': 'feminino',
                'nome_agente': 'Dora', 'nome_unidade': 'Teste',
            }, 'Bom dia')
            self.assertIn('profissão', abertura)
            self.assertNotIn('e-mail', abertura.casefold())
            for etapa, modulo, evento in (
                (7, resolver_etapa7, 'oferta_aceita'),
                (9, resolver_etapa9, 'retorno_confirmado'),
            ):
                with self.subTest(trecho=trecho, etapa=etapa):
                    contexto = {
                        'id_conversa': 1, 'id_etapa_atual': etapa,
                        'id_etapa_origem_transicao': etapa, 'id_etapa_cliente': etapa,
                        'contexto_coleta': coleta, 'tipo_mensagem_atual': 'text',
                        'texto_cliente_atual': 'sim',
                        'transicoes_permitidas': {evento: 10, evento + '_email_fireads': 11},
                        'mensagem_cliente_atual': {
                            'cliente_telefone': NUMERO, 'id_phone_unidade': 'teste',
                            'id_mensagem_fila': 1,
                        },
                    }
                    with patch.object(modulo, 'enviar_etapa10', return_value={'id_etapa_resultante': 10}) as email, patch.object(
                        modulo, 'enviar_etapa11', return_value={'id_etapa_resultante': 11}
                    ) as triagem:
                        resposta = getattr(modulo, f'resolve_etapa{etapa}')(contexto)
                    self.assertEqual(resposta['id_etapa_resultante'], 11 if aceito else 10)
                    self.assertEqual(email.call_count, 0 if aceito else 1)
                    self.assertEqual(triagem.call_count, 1 if aceito else 0)


class ComplementacaoTests(unittest.TestCase):
    def consulta(self, texto, rows):
        return interpretar_parcial(rows, NUMERO, None, ABA_DESTINO, estado(texto))

    def test_dashboard_preserva_extrator_de_email_estruturado(self):
        row = dict(ROW, Email=' ANA@INTRANET ')
        r = self.consulta('Full name: Ana Paula Silva\nPara quem é: Para mim', [row])
        self.assertEqual(valor(r['coleta'], 'email'), 'ana@intranet')
        self.assertEqual(r['resultado'], 'importado')
        self.assertEqual(extrair('Email: ANA@INTRANET')['email']['status'], 'invalido')

    def test_nome_composto_sem_sobrenome_compativel_com_cadastro_completo(self):
        texto = 'Full name: Ana Paula\nPara quem é: Para mim'
        resultado = self.consulta(texto, [ROW])
        self.assertEqual(resultado['resultado'], 'importado')
        self.assertEqual(valor(resultado['coleta'], 'email'), 'ana@example.com')
        diferente = dict(ROW, Nome='Ana Maria Silva')
        self.assertEqual(self.consulta(texto, [diferente])['resultado'], 'ausente')

    def test_completa_so_campo_faltante_de_um_registro_compativel(self):
        r = self.consulta('Full name: Ana Paula Silva\nPara quem é: Para mim', [ROW])
        self.assertEqual(valor(r['coleta'], 'email'), 'ana@example.com')
        self.assertEqual(r['coleta']['campos']['nome']['fonte'], 'mensagem')
        self.assertEqual(r['coleta']['campos']['email']['fonte'], 'dashboard')

    def test_email_conflitante_pode_ser_resolvido_por_terceiro_email(self):
        r = self.consulta(FORM + '\nEmail: outro@example.com', [dict(ROW, Email='terceiro@example.com')])
        self.assertEqual(valor(r['coleta'], 'email'), 'terceiro@example.com')

    def test_incompativel_nao_e_aproveitado_nem_vinculado(self):
        r = self.consulta('Full name: Ana Paula Silva\nEmail: novo@example.com', [ROW])
        self.assertIsNone(r['referencia'])
        self.assertIsNone(valor(r['coleta'], 'destinatario'))

    def test_nao_mistura_campos_entre_inscricoes(self):
        r = self.consulta('Oi', [dict(ROW, Email='', _row=45), dict(ROW, Nome='', _row=46)])
        self.assertEqual(r['referencia']['linha'], 46)
        self.assertIsNone(valor(r['coleta'], 'nome'))
        self.assertEqual(valor(r['coleta'], 'email'), 'ana@example.com')

    def test_canais_e_recencia_data_depois_linha(self):
        manual = dict(ROW, Canal='Indicação', _row=100, **{'Data/Hora': '20/10/2026'})
        for canal, origem in [('Meta Ads', 'meta'), ('Google Ads', 'google'), ('Organico Site', 'organico_site')]:
            r = self.consulta('Oi', [ROW, dict(ROW, _row=46, Canal=canal), manual])
            self.assertEqual(r['origem'], origem)
            self.assertEqual(r['referencia']['linha'], 46)
        self.assertEqual(self.consulta('Oi', [manual])['origem'], 'organico')

    def test_variante_nono_digito(self):
        self.assertIsNotNone(self.consulta('Oi', [dict(ROW, WhatsApp='551199990002')])['referencia'])


class EntregaTests(unittest.TestCase):
    def test_email_e_parentesco_precedem_recencia(self):
        snap = snapshot()
        alvo = escolher([ROW, dict(ROW, Email='outro@example.com', _row=46),
                         dict(ROW, _row=47, **{'Para quem é': 'Para minha mãe'})], snap)
        self.assertEqual(alvo['referencia']['linha'], 44)
        self.assertEqual(escolher([ROW, dict(ROW, _row=46)], snap)['referencia']['linha'], 46)

    def test_cria_quando_ausente_ou_incompativel(self):
        for rows in ([], [dict(ROW, Email='outro@example.com')], [dict(ROW, **{'Para quem é': 'Para minha mãe'})]):
            snap = snapshot()
            snap['destino'] = escolher(rows, snap)
            self.assertEqual(snap['destino'], {'tipo': 'create'})
            dados = preparar(rows, snap, bloco_observacoes(1, 1, 'Resumo'))['dados']
            self.assertEqual(dados['Canal'], 'Meta Ads')
            self.assertEqual(dados['Para quem é'], 'Para mim')

    def test_update_preserva_observacoes_e_demais_campos(self):
        snap = snapshot()
        snap['destino'] = escolher([ROW], snap)
        before = deepcopy(ROW)
        op = preparar([ROW], snap, bloco_observacoes(1, 1, 'Resumo'))
        self.assertEqual(set(op), {'row', 'observacoes'})
        self.assertTrue(op['observacoes'].startswith('Anotação da unidade'))
        self.assertEqual(ROW, before)

    def test_reconciliacao_apos_create_sem_novo_post(self):
        snap = snapshot()
        snap['destino'] = escolher([], snap)
        bloco = bloco_observacoes(1, 1, 'Resumo')
        self.assertIsNone(preparar([dict(ROW, **{'Observação': bloco})], snap, bloco))

    def test_alvo_persistido_deslocado_e_alvo_apagado(self):
        snap = snapshot()
        snap['destino'] = escolher([ROW], snap)
        self.assertEqual(preparar([dict(ROW, _row=100)], snap, bloco_observacoes(1, 1, 'Resumo'))['row'], 100)
        with self.assertRaises(ErroFireAds):
            preparar([dict(ROW, Email='mudou@example.com')], snap, bloco_observacoes(1, 1, 'Resumo'))

    def test_outro_telefone_com_mesmo_email_nao_autoriza_create(self):
        with self.assertRaises(ErroFireAds):
            escolher([dict(ROW, WhatsApp='5511999990003')], snapshot())

    def test_correcao_posterior_nao_troca_identidade_do_formulario(self):
        coleta = estado()
        coleta['campos']['email'] = campo(['corrigido@example.com'], 'email', 'atendimento')
        self.assertEqual(identidade_entrega(coleta)['email']['valor'], 'ana@example.com')


if __name__ == '__main__':
    unittest.main()
