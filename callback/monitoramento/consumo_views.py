"""Endpoints privados de consumo e downloads; somente leitura do banco."""

import logging

from django.db import DatabaseError
from django.http import HttpResponse, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from .consumo_services import carregar_consumo
from .views import _acesso, _headers_privados, MENSAGEM_DADOS_INDISPONIVEIS

logger = logging.getLogger(__name__)


@never_cache
@require_GET
def dados_consumo(request):
    acesso, resposta = _acesso(request, api=True)
    if resposta is not None:
        return resposta
    try:
        dados = carregar_consumo(acesso, request.GET.get("mes"))
        return _headers_privados(JsonResponse(dados))
    except ValueError as erro:
        return _headers_privados(JsonResponse({"erro": str(erro)}, status=400))
    except DatabaseError:
        logger.error("monitoramento_consumo_banco_indisponivel")
        return _headers_privados(JsonResponse({"erro": MENSAGEM_DADOS_INDISPONIVEIS}, status=503))


@never_cache
@require_GET
def consumo_pdf(request):
    acesso, resposta = _acesso(request, api=True)
    if resposta is not None:
        return resposta
    escopo = request.GET.get("escopo", "mes")
    if escopo not in {"mes", "todos"}:
        return _headers_privados(JsonResponse({"erro": "Relatório inválido."}, status=400))
    try:
        dados = carregar_consumo(acesso, request.GET.get("mes") if escopo == "mes" else None)
        registros = dados["historico"] if escopo == "todos" else [dados["selecionado"]] if dados["selecionado"] else []
        if not registros:
            return _headers_privados(JsonResponse({"erro": "Ainda não há dados disponíveis para este relatório."}, status=404))
        from .consumo_pdf import gerar_pdf_consumo
        conteudo = gerar_pdf_consumo(dados["unidade"]["nome"], registros, historico=escopo == "todos")
        nome = "todos-os-meses" if escopo == "todos" else registros[0]["mes"]
        resposta = HttpResponse(conteudo, content_type="application/pdf")
        resposta["Content-Disposition"] = f'attachment; filename="consumo-{nome}.pdf"'
        return _headers_privados(resposta)
    except ValueError as erro:
        return _headers_privados(JsonResponse({"erro": str(erro)}, status=400))
    except DatabaseError:
        logger.error("monitoramento_consumo_pdf_banco_indisponivel")
        return _headers_privados(JsonResponse({"erro": MENSAGEM_DADOS_INDISPONIVEIS}, status=503))
