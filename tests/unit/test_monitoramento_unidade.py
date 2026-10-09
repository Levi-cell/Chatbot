import re
import sqlite3
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import OperationalError, models

from core.repositories.monitoramento.acessos import buscar_acesso_monitoramento
from monitoramento import monitoramento_guard
from webhook.models import Unidade


RAIZ = Path(__file__).resolve().parents[2]


class CursorMonitoramentoSQLite:
    """Executa o SQL real de autorizacao, adaptando somente os placeholders."""

    def __init__(self, banco):
        self.cursor = banco.cursor()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.cursor.close()

    def execute(self, sql, parametros):
        self.cursor.execute(sql.replace('%s', '?'), parametros)

    def fetchone(self):
        return self.cursor.fetchone()


def usuario(id_usuario=1, **campos):
    valores = {
        'pk': id_usuario, 'is_authenticated': True, 'is_active': True,
        'is_staff': False, 'is_superuser': False,
    }
    valores.update(campos)
    return SimpleNamespace(**valores)


class IsolamentoMonitoramentoTests(unittest.TestCase):
    def setUp(self):
        self.banco = sqlite3.connect(':memory:')
        self.addCleanup(self.banco.close)
        self.banco.executescript("""
            PRAGMA foreign_keys = ON;
            ATTACH DATABASE ':memory:' AS chatbot;
            CREATE TABLE chatbot.auth_user (
                id INTEGER PRIMARY KEY, is_active BOOLEAN,
                is_staff BOOLEAN, is_superuser BOOLEAN
            );
            CREATE TABLE chatbot.unidade (
                id_unidade INTEGER PRIMARY KEY, nome_unidade TEXT,
                id_usuario_monitoramento INTEGER NULL UNIQUE
                    REFERENCES auth_user(id) ON DELETE SET NULL
            );
            CREATE TABLE chatbot.conversa (
                id_conversa INTEGER PRIMARY KEY, id_unidade INTEGER,
                id_cliente INTEGER
            );
            CREATE TABLE chatbot.historico_mensagens (
                id_mensagem INTEGER PRIMARY KEY, id_conversa INTEGER
            );
            INSERT INTO chatbot.auth_user VALUES
                (1, TRUE, FALSE, FALSE), (2, TRUE, FALSE, FALSE),
                (3, TRUE, FALSE, FALSE), (4, FALSE, FALSE, FALSE),
                (5, TRUE, TRUE, FALSE), (6, TRUE, TRUE, TRUE);
            INSERT INTO chatbot.unidade VALUES
                (10, 'Unidade A', 1), (20, 'Unidade B', 2), (30, 'Unidade C', NULL),
                (40, 'Unidade D', 4), (50, 'Unidade E', 5), (60, 'Unidade F', 6),
                (70, 'Unidade G', NULL);
            -- O mesmo cliente global 7 conversou nas unidades A e B.
            INSERT INTO chatbot.conversa VALUES
                (101, 10, 7), (102, 20, 7), (103, 10, 8), (303, 30, 7);
            INSERT INTO chatbot.historico_mensagens VALUES
                (1001, 101), (1002, 102), (1003, 103);
        """)
        self.conexao = SimpleNamespace(cursor=lambda: CursorMonitoramentoSQLite(self.banco))
        self.patch_conexao = patch.object(monitoramento_guard, 'connection', self.conexao)
        self.patch_conexao.start()
        self.addCleanup(self.patch_conexao.stop)

    def exigir(self, id_usuario=1, **recursos):
        return monitoramento_guard.exigir_acesso_monitoramento(
            SimpleNamespace(user=usuario(id_usuario)), **recursos,
        )

    def test_cada_conta_resolve_somente_sua_unidade(self):
        self.assertEqual(self.exigir(1).id_unidade, 10)
        self.assertEqual(self.exigir(2).id_unidade, 20)

    def test_mesmo_cliente_em_duas_unidades_nao_libera_outra_conversa(self):
        self.assertEqual(self.exigir(1, id_conversa=101).id_unidade, 10)
        self.assertEqual(self.exigir(2, id_conversa=102).id_unidade, 20)
        for conta, conversa in ((1, 102), (2, 101)):
            with self.subTest(conta=conta), self.assertRaises(PermissionDenied):
                self.exigir(conta, id_conversa=conversa)

    def test_mensagem_exige_unidade_e_conversa_corretas(self):
        self.assertEqual(self.exigir(id_mensagem=1001).id_unidade, 10)
        self.assertEqual(self.exigir(id_conversa=101, id_mensagem=1001).id_unidade, 10)
        for recursos in (
            {'id_mensagem': 1002},
            {'id_conversa': 101, 'id_mensagem': 1002},
            {'id_conversa': 101, 'id_mensagem': 1003},
        ):
            with self.subTest(recursos=recursos), self.assertRaises(PermissionDenied):
                self.exigir(**recursos)

    def test_recurso_inexistente_e_de_outra_unidade_tem_mesma_resposta(self):
        respostas = []
        for conversa in (102, 9999):
            with self.assertRaises(PermissionDenied) as erro:
                self.exigir(id_conversa=conversa)
            respostas.append(str(erro.exception))
        self.assertEqual(respostas[0], respostas[1])

    def test_sem_vinculo_inativo_staff_ou_superusuario_nao_tem_acesso(self):
        # A sessao ainda parece ativa/comum; o banco e autoritativo.
        for conta in (3, 4, 5, 6, 999):
            with self.subTest(conta=conta), self.assertRaises(PermissionDenied):
                self.exigir(conta)

    def test_revogacao_e_reassociacao_nao_reutilizam_vinculo_antigo(self):
        self.assertEqual(self.exigir().id_unidade, 10)
        self.banco.execute(
            'UPDATE chatbot.unidade SET id_usuario_monitoramento = NULL WHERE id_unidade = 10',
        )
        self.banco.execute(
            'UPDATE chatbot.unidade SET id_usuario_monitoramento = 1 WHERE id_unidade = 30',
        )
        with self.assertRaises(PermissionDenied):
            self.exigir(id_conversa=101)
        self.assertEqual(self.exigir(id_conversa=303).id_unidade, 30)
        self.banco.execute(
            'UPDATE chatbot.unidade SET id_usuario_monitoramento = NULL WHERE id_unidade = 30',
        )
        with self.assertRaises(PermissionDenied):
            self.exigir()

    def test_varias_unidades_sem_conta_e_usuario_exclusivo_de_uma_unidade(self):
        sem_conta = self.banco.execute(
            'SELECT COUNT(*) FROM chatbot.unidade WHERE id_usuario_monitoramento IS NULL',
        ).fetchone()[0]
        self.assertEqual(sem_conta, 2)
        with self.assertRaises(sqlite3.IntegrityError):
            self.banco.execute(
                'UPDATE chatbot.unidade SET id_usuario_monitoramento = 1 WHERE id_unidade = 20',
            )
        self.assertEqual(self.exigir(1).id_unidade, 10)
        self.assertEqual(self.exigir(2).id_unidade, 20)

    def test_excluir_conta_limpa_vinculo_e_preserva_unidade_e_atendimentos(self):
        self.banco.execute('DELETE FROM chatbot.auth_user WHERE id = 1')
        self.assertEqual(
            self.banco.execute(
                'SELECT id_usuario_monitoramento FROM chatbot.unidade WHERE id_unidade = 10',
            ).fetchone(),
            (None,),
        )
        self.assertEqual(
            self.banco.execute('SELECT COUNT(*) FROM chatbot.conversa WHERE id_conversa = 101').fetchone()[0],
            1,
        )
        self.assertEqual(
            self.banco.execute('SELECT COUNT(*) FROM chatbot.historico_mensagens WHERE id_mensagem = 1001').fetchone()[0],
            1,
        )
        with self.assertRaises(PermissionDenied):
            self.exigir()

    def test_desativacao_da_conta_e_consultada_novamente(self):
        self.exigir()
        self.banco.execute('UPDATE chatbot.auth_user SET is_active = FALSE WHERE id = 1')
        with self.assertRaises(PermissionDenied):
            self.exigir()

    def test_identidade_e_unidade_enviadas_pelo_cliente_sao_ignoradas(self):
        request = SimpleNamespace(
            user=usuario(1), GET={'id_usuario': '2', 'id_unidade': '20'},
            POST={'id_usuario': '2', 'id_unidade': '20'},
        )
        acesso = monitoramento_guard.exigir_acesso_monitoramento(request)
        self.assertEqual((acesso.id_usuario, acesso.id_unidade), (1, 10))

    def test_identificadores_invalidos_sao_negados(self):
        for valor in (0, -1, True, '101', '101 OR 1=1'):
            with self.subTest(valor=valor), self.assertRaises(PermissionDenied):
                self.exigir(id_conversa=valor)
        with CursorMonitoramentoSQLite(self.banco) as cursor:
            self.assertIsNone(buscar_acesso_monitoramento(None, cursor))

    def test_sessao_ausente_ou_inapta_e_negada_antes_do_banco(self):
        sessoes = (
            None, AnonymousUser(), usuario(is_active=False),
            usuario(is_staff=True), usuario(is_superuser=True), usuario(None),
        )
        with patch.object(self.conexao, 'cursor') as abrir_cursor:
            for sessao in sessoes:
                with self.subTest(sessao=sessao), self.assertRaises(PermissionDenied):
                    monitoramento_guard.exigir_acesso_monitoramento(
                        SimpleNamespace(user=sessao),
                    )
            abrir_cursor.assert_not_called()

    def test_erro_do_banco_nao_libera_acesso(self):
        with patch.object(self.conexao, 'cursor', side_effect=OperationalError('indisponivel')):
            with self.assertRaises(OperationalError):
                self.exigir()


class CadastroMonitoramentoTests(unittest.TestCase):
    def test_admin_separa_edicao_sem_perder_cadastro_obrigatorio(self):
        from webhook.models import AtendimentoCustomizado

        request = SimpleNamespace(user=get_user_model()(
            is_active=True, is_staff=True, is_superuser=True,
        ))
        unidade = Unidade(id_unidade=10)
        customizacao = AtendimentoCustomizado(id_customizacao=20, id_unidade=unidade)
        unidade_admin = admin.site._registry[Unidade]
        customizacao_admin = admin.site._registry[AtendimentoCustomizado]
        self.assertEqual(unidade_admin.get_inline_instances(request, unidade), [])
        novos = unidade_admin.get_inline_instances(request)
        self.assertEqual(len(novos), 1)
        self.assertIs(novos[0].model, AtendimentoCustomizado)
        self.assertEqual(novos[0].min_num, 1)
        unidade_form = unidade_admin.get_form(request, obj=unidade, change=True)
        customizacao_form = customizacao_admin.get_form(request, obj=customizacao, change=True)
        for campo in ('nome_agente', 'genero', 'bpa_ativo', 'link_agendamento'):
            self.assertNotIn(campo, unidade_form.base_fields)
            self.assertNotIn(campo, unidade_admin.list_display)
            self.assertIn(campo, customizacao_form.base_fields)
            self.assertIn(campo, customizacao_admin.list_display)
        self.assertIn('status_pagamento', unidade_form.base_fields)
        self.assertNotIn('status_pagamento', customizacao_form.base_fields)
        with patch('webhook.admin.reverse', return_value='/personalizacao/20/') as url:
            self.assertIn('/personalizacao/20/', unidade_admin.abrir_atendimento_customizado(unidade))
        url.assert_called_once_with('admin:webhook_atendimentocustomizado_change', args=[20])

    def test_modelo_valida_conta_comum_e_rejeita_contas_administrativas(self):
        User = get_user_model()
        cadastro = Unidade(
            id_unidade=10, nome_unidade='Unidade A',
            id_usuario_monitoramento=User(id=1, username='unidade_a'),
        )
        cadastro.clean()
        self.assertEqual(str(cadastro), 'Unidade A')
        for flags in ({'is_staff': True}, {'is_superuser': True}):
            cadastro.id_usuario_monitoramento = User(id=2, username='administrativo', **flags)
            with self.subTest(flags=flags), self.assertRaises(ValidationError):
                cadastro.clean()

    def test_unidade_sem_conta_e_permitida(self):
        unidade = Unidade(id_unidade=10, nome_unidade='Unidade A')
        unidade.clean()
        self.assertIsNone(unidade.id_usuario_monitoramento_id)

    def test_relacao_opcional_e_campo_disponivel_no_admin_da_unidade(self):
        campo = Unidade._meta.get_field('id_usuario_monitoramento')
        self.assertTrue(campo.one_to_one)
        self.assertTrue(campo.null)
        self.assertTrue(campo.blank)
        self.assertIs(campo.remote_field.on_delete, models.SET_NULL)
        self.assertFalse(Unidade._meta.managed)
        self.assertNotIn(
            'unidade_monitoramento',
            {modelo._meta.db_table for modelo in admin.site._registry},
        )
        unidade_admin = admin.site._registry[Unidade]
        form = unidade_admin.get_form(
            SimpleNamespace(user=get_user_model()(is_active=True, is_staff=True, is_superuser=True)),
            obj=Unidade(id_unidade=10), change=True,
        )
        self.assertFalse(form.base_fields['id_usuario_monitoramento'].required)
        conta = get_user_model()(is_active=True, is_staff=False)
        self.assertFalse(admin.site.has_permission(SimpleNamespace(user=conta)))

    def test_ddl_final_e_migracao_tem_os_mesmos_contratos_da_coluna(self):
        ddl = (RAIZ / 'core/database/deploy_database/bank_script.py').read_text(encoding='utf-8')
        migracao = (
            RAIZ / 'deploy/migrations/20260902_adicionar_usuario_monitoramento_unidade.sql'
        ).read_text(encoding='utf-8')
        padroes = (
            r'id_usuario_monitoramento INT NULL',
            r'CONSTRAINT uq_unidade_usuario_monitoramento\s+UNIQUE\s*\(id_usuario_monitoramento\)',
            r'CONSTRAINT unidade_id_usuario_monitoramento_fkey\s+FOREIGN KEY\s*\(id_usuario_monitoramento\)\s+REFERENCES chatbot.auth_user\(id\)\s+ON DELETE SET NULL',
        )
        for padrao in padroes:
            contratos = [re.search(padrao, texto).group(0) for texto in (ddl, migracao)]
            self.assertEqual(' '.join(contratos[0].split()), ' '.join(contratos[1].split()))
        self.assertNotIn('ALTER TABLE', ddl.upper())
        self.assertNotRegex(ddl, r'CREATE TABLE (?:IF NOT EXISTS )?chatbot\.unidade_monitoramento')
        self.assertFalse((RAIZ / 'deploy/migrations/20260902_criar_unidade_monitoramento.sql').exists())


if __name__ == '__main__':
    unittest.main()
