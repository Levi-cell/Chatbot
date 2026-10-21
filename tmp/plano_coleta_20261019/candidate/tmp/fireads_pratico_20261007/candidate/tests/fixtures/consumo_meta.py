"""Respostas de analytics fictícias; nenhuma chamada externa nos testes."""

from datetime import date, datetime, timezone
from decimal import Decimal

from core.consumo_meta.periodos import fronteiras_mes, validar_mes


def instante(valor):
    return datetime.fromisoformat(valor).replace(tzinfo=timezone.utc)


def resultado(mes="2026-10", agora=None, volumes=(3000, 750, 0), *, waba="999", phone="111", fuso="America/Sao_Paulo", timezone_id=25):
    agora = agora or instante("2026-10-15T12:00:00")
    inicio, fim = fronteiras_mes(validar_mes(mes), fuso)
    return {
        "waba_id": waba, "mes": mes, "timezone_id": str(timezone_id), "fuso_horario": fuso,
        "data_hora_inicio": inicio.isoformat(), "data_hora_fim": fim.isoformat(),
        "fim_exclusivo": min(agora, fim).isoformat(),
        "numeros": [{"phone_number_id": phone, "volumes_por_tipo": dict(zip(
            ("FREE_ENTRY_POINT", "FREE_CUSTOMER_SERVICE", "REGULAR"), volumes))}],
    }


def registro(mes="2026-10", agora=None, volumes=(3000, 750, 0)):
    from core.consumo_meta.apuracao import decidir_apuracao, quantidades
    agora = agora or instante("2026-11-24T12:00:00")
    resposta = resultado(mes, agora, volumes)
    return {
        "id_registro": 1, "id_unidade": 10, "mes_referencia": validar_mes(mes),
        "waba_id": "999", "phone_number_id": "111", "timezone_id": 25,
        "fuso_horario": resposta["fuso_horario"],
        "data_hora_inicio": datetime.fromisoformat(resposta["data_hora_inicio"]),
        "data_hora_fim": datetime.fromisoformat(resposta["data_hora_fim"]),
        "consultado_ate": datetime.fromisoformat(resposta["fim_exclusivo"]),
        "ultimo_sucesso_em": agora, "franquia_meta_mensal": 1000, "beneficio_esl_mensal": 1000,
        "tarifa_referencia_brl": Decimal("0.035"), "tarifa_vigencia": date(2026, 10, 1),
        **quantidades(resposta), **decidir_apuracao(None, resposta, agora),
    }
