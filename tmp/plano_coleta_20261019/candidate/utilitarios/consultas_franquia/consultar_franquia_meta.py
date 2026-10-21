"""Consultas manuais de franquia e faturas; somente GET, sem banco ou mensagens.

A API fornece consumo, não um saldo pronto. O saldo estimado vale para números
usados exclusivamente em atendimento individual pela WABA consultada. Grupos e
outras contas de mensagens no mesmo número também podem consumir a franquia.
"""

import argparse
import json
import re
import sys
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# A integração de produção não depende dos utilitários nem de seu bootstrap.
from core.integrations.whatsapp.consumo import (
    consultar_franquia_meta, _consultar_json, _validar_id,
)

CAMPOS_FATURA = (
    "id", "invoice_id", "invoice_date", "billing_period", "currency",
    "amount", "amount_due", "payment_status", "due_date", "type",
    "ad_account_ids",
)


def _resolver_periodo_faturas(meses, fuso_horario, agora):
    """Inclui o mês atual e os anteriores, pela data de emissão da fatura."""
    if type(meses) is not int or meses < 1:
        raise ValueError("meses deve ser um inteiro positivo")
    try:
        fuso = ZoneInfo(fuso_horario)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        raise ValueError("Informe um fuso IANA, como America/Sao_Paulo") from None
    instante = agora or datetime.now(timezone.utc)
    if instante.tzinfo is None or instante.utcoffset() is None:
        raise ValueError("O instante da consulta precisa conter fuso horário")
    instante = instante.astimezone(fuso)
    indice_mes_inicial = instante.year * 12 + instante.month - meses
    ano, mes_zero = divmod(indice_mes_inicial, 12)
    try:
        inicio = date(ano, mes_zero + 1, 1)
        # A Meta aceita datas, com início inclusivo e fim exclusivo. Amanhã
        # como limite inclui as faturas já emitidas hoje, sem excluir o dia.
        fim = instante.date() + timedelta(days=1)
    except ValueError:
        raise ValueError("O período de faturas está fora do calendário válido") from None
    return inicio, fim, instante


def consultar_faturas_meta(
    id_portfolio, *, meses=4, fuso_horario="America/Sao_Paulo",
    session=requests, agora=None,
):
    """Retorna as faturas empresariais acessíveis, sem presumir vínculo à WABA.

    O token precisa ter acesso financeiro ao portfólio. Uma lista vazia não
    comprova ausência de cobranças. Os valores e períodos são preservados como
    vieram da Meta, sem somar moedas ou interpretar o resultado como analytics.
    Inclui faturas de anúncios quando disponibilizadas por business_invoices;
    não aplica filtro de produto. O período inclui o mês atual e os anteriores
    (quatro meses por padrão), considerando a data de emissão da fatura.
    """
    id_portfolio = _validar_id(id_portfolio, "id_portfolio")
    inicio, fim, instante = _resolver_periodo_faturas(meses, fuso_horario, agora)
    caminho = f"{id_portfolio}/business_invoices"
    params = {
        "fields": ",".join(CAMPOS_FATURA), "limit": 100,
        "issue_start_date": inicio.isoformat(),
        "issue_end_date": fim.isoformat(),
    }
    faturas = {}
    cursores_vistos = set()

    while True:
        dados = _consultar_json(session, caminho, dict(params))
        pagina = dados.get("data")
        if not isinstance(pagina, list):
            raise RuntimeError("Lista de faturas ausente ou inválida na resposta da Meta")
        for fatura in pagina:
            if not isinstance(fatura, dict) or not fatura.get("id"):
                raise RuntimeError("Fatura sem identificação válida na resposta da Meta")
            identificador = _validar_id(fatura["id"], "id da fatura")
            # Não imprimir URLs autenticadas ou campos inesperados da resposta.
            faturas[identificador] = {
                campo: fatura[campo] for campo in CAMPOS_FATURA if campo in fatura
            }
            contas_anuncio = fatura.get("ad_account_ids") or []
            if not isinstance(contas_anuncio, list):
                raise RuntimeError("Contas de anúncios inválidas na resposta da Meta")
            faturas[identificador]["ad_account_ids"] = [
                _validar_id(conta, "id da conta de anúncios retornado")
                for conta in contas_anuncio
            ]
        paging = dados.get("paging") or {}
        if not isinstance(paging, dict):
            raise RuntimeError("Paginação de faturas inválida")
        if not paging.get("next"):
            break
        cursores = paging.get("cursors")
        cursor = cursores.get("after") if isinstance(cursores, dict) else None
        if not isinstance(cursor, str) or not cursor or cursor in cursores_vistos:
            raise RuntimeError("Paginação de faturas incompleta ou repetida")
        cursores_vistos.add(cursor)
        # Reconstruir a consulta no endpoint original, sem seguir URLs do payload.
        params["after"] = cursor

    return {
        "id_portfolio": id_portfolio,
        "consultado_em": instante.astimezone(timezone.utc).isoformat(),
        "periodo": {
            "criterio": "data_de_emissao",
            "meses_incluindo_atual": meses,
            "fuso_para_definir_datas": fuso_horario,
            "inicio_inclusivo": inicio.isoformat(),
            "fim_exclusivo": fim.isoformat(),
        },
        "status_consulta": "faturas_retornadas" if faturas else "sem_faturas_retornadas",
        "quantidade_faturas": len(faturas),
        "quantidade_faturas_com_contas_anuncio": sum(
            bool(fatura["ad_account_ids"]) for fatura in faturas.values()
        ),
        "faturas": list(faturas.values()),
        "avisos": [
            "Faturas empresariais acessíveis neste portfólio; não são necessariamente "
            "faturas do WhatsApp nem estão filtradas por WABA ou número.",
            "Faturas de anúncios são incluídas quando disponíveis neste endpoint. "
            "ad_account_ids identifica as contas vinculadas; sua ausência não "
            "identifica a fatura como sendo do WhatsApp.",
            "business_invoices consulta faturamento mensal, não todos os "
            "comprovantes de pagamentos por cartão ou recargas de anúncios.",
            "Nenhuma fatura retornada não significa ausência de cobranças. "
            "A disponibilidade depende da conta e das permissões financeiras.",
        ],
    }


def _exibir_resultado(resultado, *, mostrar_identificadores):
    exibicao = deepcopy(resultado)
    if not mostrar_identificadores:
        for campo in ("waba_id", "id_portfolio"):
            if campo in exibicao:
                exibicao[campo] = "..." + str(exibicao[campo])[-4:]
        for numero in exibicao.get("numeros", []):
            for campo in ("phone_number_id", "telefone"):
                numero[campo] = "..." + str(numero[campo])[-4:]
        for fatura in exibicao.get("faturas", []):
            for campo in ("id", "invoice_id"):
                if campo in fatura:
                    fatura[campo] = "..." + str(fatura[campo])[-4:]
            if "ad_account_ids" in fatura:
                fatura["ad_account_ids"] = [
                    "..." + str(conta)[-4:] for conta in fatura["ad_account_ids"]
                ]
    print(json.dumps(exibicao, ensure_ascii=False, indent=2))


def consultar_franquia(
    waba_id, phone_number_id=None, *, fuso_horario=None,
    mes=None, env_file=None, mostrar_identificadores=False,
):
    """Atalho para a IDE: configura o ambiente, consulta, imprime e retorna dados.

    Exemplo: consultar_franquia("ID_DA_WABA", "ID_DO_NUMERO").
    O fuso é obtido da WABA. Sem phone_number_id, consulta a WABA inteira.
    Sem mes, consulta o mês atual. Credenciais vêm do bootstrap local.
    O worker futuro deve usar consultar_franquia_meta com o ambiente carregado
    pelo processo, evitando este bootstrap de IDE a cada unidade do ciclo.
    """
    from utilitarios.bootstrap import configurar_ambiente_utilitario

    configurar_ambiente_utilitario(env_file)
    resultado = consultar_franquia_meta(
        waba_id, phone_number_id=phone_number_id,
        fuso_horario=fuso_horario, mes=mes,
    )
    _exibir_resultado(resultado, mostrar_identificadores=mostrar_identificadores)
    return resultado


def consultar_faturas(
    id_portfolio, *, meses=4, fuso_horario="America/Sao_Paulo",
    env_file=None, mostrar_identificadores=False,
):
    """Configura o ambiente, imprime e retorna as faturas acessíveis do portfólio.

    Exemplo: consultar_faturas("ID_DO_PORTFOLIO", meses=4). O ID não é o da WABA.
    Inclui anúncios, sem restringir produto. Meses inclui o atual até hoje.
    """
    from utilitarios.bootstrap import configurar_ambiente_utilitario

    configurar_ambiente_utilitario(env_file)
    resultado = consultar_faturas_meta(
        id_portfolio, meses=meses, fuso_horario=fuso_horario,
    )
    _exibir_resultado(resultado, mostrar_identificadores=mostrar_identificadores)
    return resultado


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Consulta somente leitura da franquia de serviço na Meta."
    )
    parser.add_argument("--waba-id", required=True)
    parser.add_argument("--phone-number-id", help="sem esta opção, consulta toda a WABA")
    parser.add_argument(
        "--fuso-horario", help="opcional: confere o fuso IANA retornado pela WABA",
    )
    parser.add_argument("--mes", help="AAAA-MM; padrão: mês atual")
    parser.add_argument("--env-file", help="arquivo de ambiente; padrão: local_settings.py")
    parser.add_argument("--mostrar-identificadores", action="store_true")
    args = parser.parse_args(argv)
    try:
        consultar_franquia(
            args.waba_id, args.phone_number_id,
            fuso_horario=args.fuso_horario, mes=args.mes, env_file=args.env_file,
            mostrar_identificadores=args.mostrar_identificadores,
        )
        return 0
    except (RuntimeError, ValueError) as exc:
        print(f"CONSULTA_FRANQUIA_META_FALHOU: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    if len(sys.argv) > 1:
        raise SystemExit(main())

    # Pela IDE, execute este arquivo sem argumentos. Edite as chamadas abaixo.
    # Credenciais continuam no ambiente; importar o módulo não faz consultas.
    consultar_franquia(
        833244752748897,
        1217356894795355,
        # Sem fuso_horario: utiliza automaticamente o fuso consultado na WABA.
        mes=None,  # Mês atual; ou "AAAA-MM" para um mês anterior.
    )

    print("\n/////////////////////////////////////////////////\n")

    # Quatro meses: o atual até hoje e os três anteriores; inclui anúncios.
    consultar_faturas(3514123935358885, meses=4)
