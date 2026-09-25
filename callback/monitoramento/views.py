"""Entrada do portal; credenciais sao verificadas pelo Django e nunca por SQL proprio."""

import logging
import csv
from io import StringIO

from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render, resolve_url
from django.views.decorators.http import require_GET
from django.views.csrf import csrf_failure
from django.views.decorators.cache import never_cache

from core.validacoes.email import validar_email_estrutural

from .forms import LoginMonitoramentoForm
from .faixa_etaria import validar_consulta_faixa_etaria
from .monitoramento_guard import exigir_acesso_monitoramento
from .periodos import PERIODOS, resolver_periodo
from .services import (
    carregar_contatos,
    carregar_conversas,
    carregar_mensagens,
    carregar_relatorio,
    carregar_faixa_etaria,
)
from .apresentacao import (
    CABECALHO_CSV_ESSENCIAL,
    CABECALHO_CSV_GOOGLE_CONTATOS,
    montar_linha_csv_essencial,
    montar_linha_csv_google_contatos,
    normalizar_telefone_google,
    separar_nome,
)


logger = logging.getLogger(__name__)
MENSAGEM_LOGIN_INDISPONIVEL = (
    'Não foi possível entrar agora. Aguarde um instante e tente novamente.'
)
MENSAGEM_DADOS_INDISPONIVEIS = (
    'Não foi possível atualizar os dados agora. Aguarde um instante e tente novamente.'
)


class LoginMonitoramentoView(LoginView):
    authentication_form = LoginMonitoramentoForm
    template_name = 'monitoramento/login.html'
    http_method_names = ['get', 'post', 'head', 'options']

    def get_success_url(self):
        # Destino fixo evita redirecionamentos enviados pelo navegador.
        return resolve_url('monitoramento:painel')

    def render_to_response(self, context, **response_kwargs):
        return _headers_privados(
            super().render_to_response(context, **response_kwargs)
        )

    def get(self, request, *args, **kwargs):
        try:
            return super().get(request, *args, **kwargs)
        except DatabaseError:
            return self.resposta_indisponivel()

    def post(self, request, *args, **kwargs):
        try:
            return super().post(request, *args, **kwargs)
        except DatabaseError:
            return self.resposta_indisponivel()

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        if not getattr(self, 'banco_indisponivel', False) and self.request.method in ('GET', 'HEAD'):
            if self.request.user.is_authenticated:
                try:
                    contexto['acesso_confirmado'] = exigir_acesso_monitoramento(self.request)
                except PermissionDenied:
                    contexto['aviso_acesso'] = (
                        'Sua conta não possui acesso ao monitoramento. '
                        'Entre com uma conta vinculada à sua unidade.'
                    )
        return contexto

    def resposta_indisponivel(self):
        # Nao registrar usuario, senha ou o detalhe da excecao de autenticacao.
        logger.error('monitoramento_login_banco_indisponivel')
        self.banco_indisponivel = True
        formulario = self.authentication_form(
            request=self.request,
            initial={'username': self.request.POST.get('username', '')},
        )
        contexto = self.get_context_data(form=formulario)
        contexto['aviso_acesso'] = MENSAGEM_LOGIN_INDISPONIVEL
        return self.render_to_response(contexto, status=503)


class LogoutMonitoramentoView(LogoutView):
    def get_success_url(self):
        return resolve_url('monitoramento:login')


def _headers_privados(resposta):
    resposta['Cache-Control'] = 'private, no-store, max-age=0'
    resposta['Pragma'] = 'no-cache'
    resposta['Content-Security-Policy'] = (
        "default-src 'self'; img-src 'self' data:; style-src 'self'; "
        "script-src 'self'; connect-src 'self'; font-src 'self'; "
        "frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    )
    return resposta


def _acesso(request, *, api=False):
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        if api:
            return None, _headers_privados(JsonResponse(
                {'erro': 'Sua sessão expirou. Entre novamente.'}, status=401
            ))
        return None, redirect('monitoramento:login')
    try:
        return exigir_acesso_monitoramento(request), None
    except PermissionDenied:
        if api:
            return None, _headers_privados(JsonResponse(
                {'erro': 'Acesso ao monitoramento não autorizado.'}, status=403
            ))
        return None, _headers_privados(render(
            request, 'monitoramento/sem_acesso.html', status=403
        ))


def _resolver_periodo_request(request):
    try:
        return resolver_periodo(request.GET.get('periodo', 'total'))
    except ValueError:
        return None


@never_cache
@require_GET
def painel(request):
    acesso, resposta = _acesso(request)
    if resposta:
        return resposta
    return _headers_privados(render(request, 'monitoramento/painel.html', {
        'nome_unidade': acesso.nome_unidade,
        'periodos': [('total', 'Todo o histórico')] + [
            (chave, configuracao[0]) for chave, configuracao in PERIODOS.items()
        ],
    }))


@never_cache
@require_GET
def dados_conversas(request):
    acesso, resposta = _acesso(request, api=True)
    if resposta:
        return resposta
    periodo = _resolver_periodo_request(request)
    if periodo is None:
        return _headers_privados(JsonResponse({'erro': 'Período inválido.'}, status=400))
    try:
        return _headers_privados(JsonResponse(carregar_conversas(acesso, periodo)))
    except DatabaseError:
        logger.error('monitoramento_conversas_banco_indisponivel')
        return _headers_privados(JsonResponse({'erro': MENSAGEM_DADOS_INDISPONIVEIS}, status=503))


@never_cache
@require_GET
def dados_mensagens(request, id_cliente):
    acesso, resposta = _acesso(request, api=True)
    if resposta:
        return resposta
    periodo = _resolver_periodo_request(request)
    if periodo is None:
        return _headers_privados(JsonResponse({'erro': 'Período inválido.'}, status=400))
    try:
        dados = carregar_mensagens(acesso, id_cliente, periodo)
        if not dados['mensagens']:
            return _headers_privados(JsonResponse({'erro': 'Conversa não encontrada.'}, status=404))
        return _headers_privados(JsonResponse(dados))
    except DatabaseError:
        logger.error('monitoramento_mensagens_banco_indisponivel')
        return _headers_privados(JsonResponse({'erro': MENSAGEM_DADOS_INDISPONIVEIS}, status=503))


@never_cache
@require_GET
def dados_relatorio(request):
    acesso, resposta = _acesso(request, api=True)
    if resposta:
        return resposta
    periodo = _resolver_periodo_request(request)
    if periodo is None:
        return _headers_privados(JsonResponse({'erro': 'Período inválido.'}, status=400))
    try:
        return _headers_privados(JsonResponse(carregar_relatorio(acesso, periodo)))
    except DatabaseError:
        logger.error('monitoramento_relatorio_banco_indisponivel')
        return _headers_privados(JsonResponse({'erro': MENSAGEM_DADOS_INDISPONIVEIS}, status=503))


@never_cache
@require_GET
def dados_faixa_etaria(request):
    acesso, resposta = _acesso(request, api=True)
    if resposta:
        return resposta
    if len(request.GET.getlist('periodo')) > 1:
        return _headers_privados(JsonResponse({'erro': 'Selecione apenas um período.'}, status=400))
    periodo = _resolver_periodo_request(request)
    if periodo is None:
        return _headers_privados(JsonResponse({'erro': 'Período inválido.'}, status=400))
    try:
        idade_minima, publico = validar_consulta_faixa_etaria(request.GET)
    except ValueError as erro:
        return _headers_privados(JsonResponse({'erro': str(erro)}, status=400))
    try:
        dados = carregar_faixa_etaria(acesso, periodo, idade_minima, publico)
        return _headers_privados(JsonResponse(dados))
    except DatabaseError:
        logger.error('monitoramento_faixa_etaria_banco_indisponivel')
        return _headers_privados(JsonResponse({'erro': MENSAGEM_DADOS_INDISPONIVEIS}, status=503))


@never_cache
@require_GET
def contatos_csv(request):
    acesso, resposta = _acesso(request, api=True)
    if resposta:
        return resposta
    periodo = _resolver_periodo_request(request)
    if periodo is None:
        return _headers_privados(JsonResponse({'erro': 'Período inválido.'}, status=400))
    formato = request.GET.get('formato', 'google')
    if formato not in ('google', 'essencial'):
        return _headers_privados(JsonResponse({'erro': 'Formato inválido.'}, status=400))
    essencial = formato == 'essencial'
    apenas_elegiveis = request.GET.get('tipo') == 'elegiveis'
    try:
        contatos = carregar_contatos(acesso, periodo)
    except DatabaseError:
        logger.error('monitoramento_csv_banco_indisponivel')
        return _headers_privados(JsonResponse({'erro': MENSAGEM_DADOS_INDISPONIVEIS}, status=503))
    saida = StringIO(newline='')
    # O formato essencial facilita a abertura em planilhas configuradas em pt-BR.
    # O Google CSV mantém seu separador, codificação e cabeçalhos originais.
    escritor = csv.writer(saida, delimiter=';' if essencial else ',', lineterminator='\r\n')
    escritor.writerow(CABECALHO_CSV_ESSENCIAL if essencial else CABECALHO_CSV_GOOGLE_CONTATOS)
    for contato in contatos:
        primeiro, sobrenome = separar_nome(contato.get('nome'))
        email = str(contato.get('email') or '').strip()
        validacao_email = validar_email_estrutural(email)
        email_exportado = validacao_email.email if validacao_email.valido else email
        telefone = normalizar_telefone_google(contato.get('waid_telefone'))
        if apenas_elegiveis and not (
            primeiro and validacao_email.valido and telefone
        ):
            continue
        dados_linha = {
            'primeiro_nome': primeiro,
            'sobrenome': sobrenome,
            'email': email_exportado,
            'telefone': telefone,
        }
        if essencial:
            linha = montar_linha_csv_essencial(**dados_linha)
        else:
            linha = montar_linha_csv_google_contatos(
                **dados_linha, nome_unidade=acesso.nome_unidade,
            )
        escritor.writerow(linha)
    conteudo = saida.getvalue().encode('utf-8-sig' if essencial else 'utf-8')
    resposta = HttpResponse(conteudo, content_type='text/csv; charset=utf-8')
    prefixo = 'contatos_essenciais' if essencial else 'contatos'
    resposta['Content-Disposition'] = (
        f'attachment; filename="{prefixo}_{periodo.chave}_{"elegiveis" if apenas_elegiveis else "todos"}.csv"'
    )
    return _headers_privados(resposta)


@never_cache
def falha_csrf(request, reason='', template_name='403_csrf.html'):
    if getattr(request.resolver_match, 'app_name', None) != 'monitoramento':
        return csrf_failure(request, reason=reason, template_name=template_name)
    return _headers_privados(render(request, 'monitoramento/login.html', {
        'form': LoginMonitoramentoForm(request=request),
        'aviso_acesso': 'A verificação de segurança expirou ou é inválida. Digite seus dados e tente novamente.',
    }, status=403))
