"""Autorização do painel, independente do webhook de mensagens da Meta."""

from django.core.exceptions import PermissionDenied
from django.db import connection

from core.repositories.monitoramento.acessos import buscar_acesso_monitoramento


def exigir_acesso_monitoramento(request, *, id_conversa=None, id_mensagem=None):
    """Busca a unidade que aponta ao usuario da sessao e nega recursos de outra unidade.

    Toda rota privada do painel deve chamar esta validação. Depois, suas consultas
    devem continuar limitadas ao id_unidade retornado; esta funcao nao filtra
    automaticamente QuerySets nem concede permissoes no Django Admin.
    O vinculo vem de unidade.id_usuario_monitoramento. Nao guarde o retorno
    na sessao/cache: revalide o vinculo a cada requisicao.
    """
    return exigir_acesso_usuario_monitoramento(
        getattr(request, 'user', None),
        id_conversa=id_conversa,
        id_mensagem=id_mensagem,
    )


def exigir_acesso_usuario_monitoramento(usuario, *, id_conversa=None, id_mensagem=None):
    """Permite validar a conta autenticada antes de criar sua sessao de login."""
    if (
        usuario is None
        or not usuario.is_authenticated
        or not usuario.is_active
        or usuario.is_staff
        or usuario.is_superuser
        or usuario.pk is None
    ):
        raise PermissionDenied('Acesso ao monitoramento não autorizado.')

    # O cursor do Django usa autocommit para esta unica leitura. Erros de banco
    # propagam: indisponibilidade nunca deve liberar acesso ou uma consulta global.
    with connection.cursor() as cursor:
        acesso = buscar_acesso_monitoramento(
            usuario.pk,
            cursor,
            id_conversa=id_conversa,
            id_mensagem=id_mensagem,
        )

    if acesso is None:
        # A mesma resposta cobre vinculo ausente, recurso inexistente ou de outro
        # atendimento, sem revelar a existencia de dados de outra unidade.
        raise PermissionDenied('Acesso ao monitoramento não autorizado.')

    return acesso
