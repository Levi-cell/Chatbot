"""Login real do Django, com usuarios/sessoes em SQLite descartavel."""

import re
import unittest
from unittest.mock import patch

from django.contrib.auth import SESSION_KEY, get_user_model
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.sessions.models import Session
from django.db import OperationalError, connections
from django.db.backends.sqlite3.base import DatabaseWrapper
from django.test import Client, override_settings


class LoginMonitoramentoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.senha_a = 'Acesso-Ficticio-A-827!'
        cls.senha_b = 'Acesso-Ficticio-B-916!'
        cls.hash_a = make_password(cls.senha_a)
        cls.hash_b = make_password(cls.senha_b)

    def setUp(self):
        configuracao_teste = override_settings(
            ROOT_URLCONF='callback.callback.urls',
            AUTHENTICATION_BACKENDS=['django.contrib.auth.backends.ModelBackend'],
            SESSION_ENGINE='django.contrib.sessions.backends.db',
            SECURE_SSL_REDIRECT=False,
            SESSION_COOKIE_SECURE=False,
            CSRF_COOKIE_SECURE=False,
            ALLOWED_HOSTS=['testserver'],
        )
        configuracao_teste.enable()
        self.addCleanup(configuracao_teste.disable)
        # A conexao real configurada no projeto nunca e aberta. Apenas o wrapper
        # da thread deste teste e substituido e restaurado ao terminar.
        self.conexao_original = connections['default']
        configuracao = dict(self.conexao_original.settings_dict)
        configuracao.update(ENGINE='django.db.backends.sqlite3', NAME=':memory:', OPTIONS={})
        self.banco = DatabaseWrapper(configuracao, alias='default')
        connections['default'] = self.banco
        self.addCleanup(self.restaurar_conexao)

        # SQLite nao possui o search_path do PostgreSQL. O SQL de autorizacao
        # permanece real, com somente o qualificador de schema adaptado no teste.
        self.escopo_sql = self.banco.execute_wrapper(
            lambda executar, sql, parametros, many, contexto:
                executar(sql.replace('chatbot.', ''), parametros, many, contexto)
        )
        self.escopo_sql.__enter__()
        self.addCleanup(self.escopo_sql.__exit__, None, None, None)

        self.Usuario = get_user_model()
        with self.banco.schema_editor() as schema:
            for modelo in (ContentType, Permission, Group, self.Usuario, Session):
                schema.create_model(modelo)
        with self.banco.cursor() as cursor:
            cursor.execute('''CREATE TABLE unidade (
                id_unidade INTEGER PRIMARY KEY,
                nome_unidade TEXT NOT NULL,
                id_usuario_monitoramento INTEGER UNIQUE REFERENCES auth_user(id)
            )''')
        self.usuario_a = self.Usuario.objects.create(username='unidade_a', password=self.hash_a)
        self.usuario_b = self.Usuario.objects.create(username='unidade_b', password=self.hash_b)
        with self.banco.cursor() as cursor:
            cursor.execute('INSERT INTO unidade VALUES (%s, %s, %s)', (10, 'Unidade A', self.usuario_a.pk))
            cursor.execute('INSERT INTO unidade VALUES (%s, %s, %s)', (20, 'Unidade B', self.usuario_b.pk))
        self.cliente = Client()

    def restaurar_conexao(self):
        self.banco.close()
        connections['default'] = self.conexao_original

    def entrar(self, username='unidade_a', password=None, **extras):
        return self.cliente.post('/login/', {
            'username': username,
            'password': self.senha_a if password is None else password,
            **extras,
        })

    def test_formulario_oculta_senha_e_nao_oferece_cadastro_ou_recuperacao(self):
        resposta = self.cliente.get('/login/')
        html = resposta.content.decode()
        self.assertEqual(resposta.status_code, 200)
        self.assertIn('type="password"', html)
        self.assertIn('autocomplete="current-password"', html)
        self.assertIn('autocomplete="username"', html)
        self.assertIn('csrfmiddlewaretoken', html)
        self.assertIn('/static/monitoramento/css/login.css', html)
        self.assertIn('no-store', resposta.headers['Cache-Control'])
        self.assertEqual(resposta.headers['X-Frame-Options'], 'DENY')
        self.assertNotIn('type="checkbox"', html)
        self.assertNotIn('password_reset', html)
        self.assertNotIn('Criar conta', html)
        self.assertEqual(self.cliente.get('/password_reset/').status_code, 404)

    def test_username_a_com_senha_b_nao_autentica(self):
        resposta = self.entrar(password=self.senha_b)
        self.assertEqual(resposta.status_code, 200)
        self.assertIn('Username ou senha incorretos', resposta.content.decode())
        self.assertNotIn(SESSION_KEY, self.cliente.session)
        self.assertNotIn(self.senha_b, resposta.content.decode())

    def test_usuario_inexistente_e_senha_errada_recebem_mesmo_aviso(self):
        for dados in ({'username': 'nao_existe'}, {'password': 'Senha-Errada'}):
            with self.subTest(dados=dados):
                resposta = self.entrar(**dados)
                self.assertIn('Username ou senha incorretos', resposta.content.decode())
                self.assertNotIn(SESSION_KEY, self.cliente.session)

    def test_credenciais_corretas_criam_sessao_e_confirmam_a_unidade(self):
        for usuario, senha, unidade in ((self.usuario_a, self.senha_a, 'Unidade A'), (self.usuario_b, self.senha_b, 'Unidade B')):
            with self.subTest(unidade=unidade):
                resposta = self.entrar(username=usuario.username, password=senha)
                self.assertEqual(resposta.status_code, 302)
                self.assertEqual(resposta.headers['Location'], '/')
                self.assertEqual(self.cliente.session[SESSION_KEY], str(usuario.pk))
                html = self.cliente.get('/login/').content.decode()
                self.assertIn('Acesso confirmado.', html)
                self.assertIn(unidade, html)
                self.assertNotIn('name="password"', html)

    def test_login_troca_a_chave_da_sessao_anonima(self):
        sessao = self.cliente.session
        sessao['preferencia_teste'] = 'preservada'
        sessao.save()
        chave_antiga = sessao.session_key
        self.entrar()
        self.assertNotEqual(self.cliente.session.session_key, chave_antiga)
        self.assertFalse(Session.objects.filter(session_key=chave_antiga).exists())

    def test_campos_vazios_mostram_avisos_em_portugues(self):
        html = self.entrar(username='', password='').content.decode()
        self.assertIn('Informe seu username.', html)
        self.assertIn('Informe sua senha.', html)
        self.assertIn('aria-invalid="true"', html)
        self.assertNotIn(SESSION_KEY, self.cliente.session)

    def test_conta_inativa_administrativa_ou_sem_unidade_nao_entra(self):
        for flags in ({'is_active': False}, {'is_staff': True}, {'is_superuser': True}, {}):
            with self.subTest(flags=flags):
                self.Usuario.objects.filter(pk=self.usuario_a.pk).update(is_active=True, is_staff=False, is_superuser=False)
                if flags:
                    self.Usuario.objects.filter(pk=self.usuario_a.pk).update(**flags)
                else:
                    with self.banco.cursor() as cursor:
                        cursor.execute('UPDATE unidade SET id_usuario_monitoramento = NULL WHERE id_unidade = 10')
                resposta = self.entrar()
                self.assertEqual(resposta.status_code, 200)
                self.assertNotIn(SESSION_KEY, self.cliente.session)
                self.assertNotIn('Acesso confirmado.', resposta.content.decode())

    def test_next_do_navegador_nao_controla_o_redirecionamento(self):
        for destino in ('https://outro.example/', '/admin/', '//outro.example/'):
            resposta = self.entrar(next=destino)
            self.assertEqual(resposta.headers['Location'], '/')

    def test_nao_ha_bloqueio_apos_tres_tentativas(self):
        for _ in range(4):
            self.entrar(password='Senha-Incorreta')
        self.assertEqual(self.entrar().status_code, 302)

    def test_falha_de_banco_nao_cria_sessao_e_nao_expoe_detalhes(self):
        with patch.object(self.Usuario._default_manager, 'get_by_natural_key', side_effect=OperationalError('segredo-interno-de-teste')):
            resposta = self.entrar()
        self.assertEqual(resposta.status_code, 503)
        self.assertIn('Não foi possível entrar agora', resposta.content.decode())
        self.assertNotIn('segredo-interno-de-teste', resposta.content.decode())
        self.assertNotIn(self.senha_a, resposta.content.decode())
        self.assertNotIn(SESSION_KEY, self.cliente.session)

    def test_falha_ao_validar_vinculo_nao_cria_sessao(self):
        with patch('monitoramento.monitoramento_guard.buscar_acesso_monitoramento', side_effect=OperationalError('indisponivel')):
            resposta = self.entrar()
        self.assertEqual(resposta.status_code, 503)
        self.assertNotIn(SESSION_KEY, self.cliente.session)

    def test_csrf_exigido_no_login_e_na_saida(self):
        self.cliente = Client(enforce_csrf_checks=True)
        self.assertEqual(self.entrar().status_code, 403)
        self.assertNotIn(SESSION_KEY, self.cliente.session)
        pagina = self.cliente.get('/login/')
        token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', pagina.content.decode()).group(1)
        self.assertEqual(self.entrar(csrfmiddlewaretoken=token).status_code, 302)
        self.assertEqual(self.cliente.get('/sair/').status_code, 405)
        self.assertEqual(self.cliente.post('/sair/').status_code, 403)
        self.assertIn(SESSION_KEY, self.cliente.session)
        pagina = self.cliente.get('/login/')
        token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', pagina.content.decode()).group(1)
        self.assertEqual(self.cliente.post('/sair/', {'csrfmiddlewaretoken': token}).status_code, 302)
        self.assertNotIn(SESSION_KEY, self.cliente.session)

    def test_csrf_invalido_mostra_login_utilizavel_em_portugues(self):
        self.cliente = Client(enforce_csrf_checks=True)
        resposta = self.entrar(csrfmiddlewaretoken='invalido')
        html = resposta.content.decode()
        self.assertEqual(resposta.status_code, 403)
        self.assertIn('A verificação de segurança expirou ou é inválida', html)
        self.assertIn('name="csrfmiddlewaretoken"', html)
        self.assertIn('no-store', resposta.headers['Cache-Control'])

    def test_origem_estrangeira_nao_pode_enviar_formulario(self):
        self.cliente = Client(enforce_csrf_checks=True)
        pagina = self.cliente.get('/login/')
        token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', pagina.content.decode()).group(1)
        resposta = self.cliente.post('/login/', {'username': 'unidade_a', 'password': self.senha_a, 'csrfmiddlewaretoken': token}, HTTP_ORIGIN='https://outro.example')
        self.assertEqual(resposta.status_code, 403)
        self.assertNotIn(SESSION_KEY, self.cliente.session)

    def test_username_e_nome_de_unidade_sao_escapados_no_html(self):
        html = self.entrar(username='<script>alert(1)</script>').content.decode()
        self.assertNotIn('<script>alert(1)</script>', html)
        self.assertIn('&lt;script&gt;', html)
        with self.banco.cursor() as cursor:
            cursor.execute('UPDATE unidade SET nome_unidade = %s WHERE id_unidade = 10', ('<img src=x onerror=alert(1)>',))
        self.entrar()
        html = self.cliente.get('/login/').content.decode()
        self.assertNotIn('<img src=x', html)
        self.assertIn('&lt;img', html)

    def test_revogar_vinculo_remove_confirmacao_da_proxima_pagina(self):
        self.entrar()
        with self.banco.cursor() as cursor:
            cursor.execute('UPDATE unidade SET id_usuario_monitoramento = NULL WHERE id_unidade = 10')
        html = self.cliente.get('/login/').content.decode()
        self.assertNotIn('Acesso confirmado.', html)
        self.assertIn('Sua conta não possui acesso', html)
