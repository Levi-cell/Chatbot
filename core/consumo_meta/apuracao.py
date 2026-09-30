"""Decisões de consolidação: compara a leitura anterior antes do upsert."""

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

from .periodos import dia_consolidacao_seguinte

ESTADOS_APURACAO = (
    ("em_andamento", "Em andamento"),
    ("em_conferencia", "Em conferência"),
    ("consolidado", "Consolidado"),
)
CAMPOS_VOLUMES = ("qtd_janela_gratuita", "qtd_franquia_consumida", "qtd_cobradas_meta")
TARIFA_REFERENCIA_BRL = Decimal("0.035")


def quantidades(resultado):
    numeros = resultado["numeros"]
    if len(numeros) != 1:
        raise ValueError("A coleta mensal exige exatamente um número.")
    tipos = numeros[0]["volumes_por_tipo"]
    valores = (tipos["FREE_ENTRY_POINT"], tipos["FREE_CUSTOMER_SERVICE"], tipos["REGULAR"])
    if any(type(valor) is not int or valor < 0 for valor in valores):
        raise ValueError("Volumes inválidos.")
    if valores[1] > 1000:
        raise ValueError("Consumo de franquia incompatível; confira o recorte na Meta.")
    return dict(zip(CAMPOS_VOLUMES, valores))


def validar_identidade(registro, resultado):
    """Mudança no cadastro não permite misturar recortes mensais distintos."""
    if not registro:
        return
    numero = resultado["numeros"][0]["phone_number_id"]
    esperado = (str(registro["waba_id"]), str(registro["phone_number_id"]),
                registro["fuso_horario"], registro["data_hora_inicio"], registro["data_hora_fim"])
    recebido = (str(resultado["waba_id"]), str(numero), resultado["fuso_horario"],
                datetime.fromisoformat(resultado["data_hora_inicio"]),
                datetime.fromisoformat(resultado["data_hora_fim"]))
    if esperado != recebido or int(registro["timezone_id"]) != int(resultado["timezone_id"]):
        raise ValueError("Conta, número ou fuso mudou; o período histórico exige revisão.")


def decidir_apuracao(registro, resultado, agora):
    """Só o dia 25 previsto aprova; uma reprovação espera outro mês-calendário.

    `registro` é o estado persistido ANTES desta coleta. Comparar depois de
    gravar os volumes faria qualquer resposta coincidir consigo mesma.
    """
    inicio = datetime.fromisoformat(resultado["data_hora_inicio"])
    fim = datetime.fromisoformat(resultado["data_hora_fim"])
    fuso = ZoneInfo(resultado["fuso_horario"])
    hoje = agora.astimezone(fuso).date()
    prazo = (registro or {}).get("data_proxima_consolidacao") or dia_consolidacao_seguinte(inicio.date())
    if registro and registro["status_apuracao"] == "consolidado":
        raise ValueError("Mês consolidado não aceita coleta automática.")
    decisao = {
        "status_apuracao": "em_andamento" if agora < fim else "em_conferencia",
        "data_proxima_consolidacao": prazo,
        "consolidado_em": None,
        "ultima_decisao_consolidacao_em": (registro or {}).get("ultima_decisao_consolidacao_em"),
    }
    if agora < fim or hoje < prazo:
        return decisao
    leitura_anterior_completa = bool(
        registro and registro["consultado_ate"] >= fim
        and registro["ultimo_sucesso_em"].astimezone(fuso).date() < hoje
    )
    iguais = leitura_anterior_completa and all(
        registro[campo] == valor for campo, valor in quantidades(resultado).items()
    )
    decisao["ultima_decisao_consolidacao_em"] = agora
    if hoje == prazo and iguais and datetime.fromisoformat(resultado["fim_exclusivo"]) >= fim:
        decisao.update(status_apuracao="consolidado", data_proxima_consolidacao=None, consolidado_em=agora)
    else:
        # Inclui prazo perdido por indisponibilidade: nunca aprova retroativamente.
        decisao["data_proxima_consolidacao"] = dia_consolidacao_seguinte(hoje)
        if hoje > prazo and hoje.day < 25:
            decisao["data_proxima_consolidacao"] = hoje.replace(day=25)
    return decisao


def calcular_resumo(registro):
    janela, usada, cobradas = (int(registro[campo]) for campo in CAMPOS_VOLUMES)
    cobertura = min(cobradas, registro["beneficio_esl_mensal"])
    excedente = max(cobradas - cobertura, 0)
    tarifa = Decimal(str(registro["tarifa_referencia_brl"]))
    return {
        "total_mensagens": janela + usada + cobradas,
        "franquia_restante": max(registro["franquia_meta_mensal"] - usada, 0),
        "assumidas_esl": cobertura,
        "excedentes_unidade": excedente,
        "valor_referencia_excedente": str((tarifa * excedente).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
    }
