import logging
import threading
import time
from collections import OrderedDict, deque

from core.logging_config import short_value


logger = logging.getLogger("cache.flood_memoria")

MAX_CHAVES_MEMORIA = 10000
LIMPEZA_INTERVALO_SEGUNDOS = 60

_lock = threading.Lock()
_eventos_por_chave = OrderedDict()
_ultima_limpeza = 0.0


def avaliar_flood_memoria(wa_id_cliente, phone_id_unidade, regras):
    if not wa_id_cliente or not phone_id_unidade:
        return {
            "memoria_ok": True,
            "flood": False,
            "total": 0,
            "motivo": "dados_invalidos",
            "regra": None,
        }

    agora = time.monotonic()
    chave = _cache_key(wa_id_cliente, phone_id_unidade)

    with _lock:
        _limpar_chaves_expiradas(agora, regras)

        eventos = _eventos_por_chave.get(chave)

        if eventos is None:
            eventos = deque()
            _eventos_por_chave[chave] = eventos

        eventos.append(agora)
        _eventos_por_chave.move_to_end(chave)

        maior_janela = max(regra["janela_segundos"] for regra in regras)
        _remover_eventos_antigos(eventos, agora, maior_janela)

        maior_total = 0

        for regra in regras:
            total = _contar_eventos_na_janela(
                eventos,
                agora,
                regra["janela_segundos"],
            )
            maior_total = max(maior_total, total)

            if total >= regra["limite"]:
                logger.warning(
                    "rate_limit_memoria_estourou | acao=detectar_flood wa_id_cliente=%s phone_id_unidade=%s regra=%s total=%s limite=%s janela=%s",
                    short_value(wa_id_cliente),
                    short_value(phone_id_unidade),
                    regra["nome"],
                    total,
                    regra["limite"],
                    regra["janela_segundos"],
                )
                return {
                    "memoria_ok": True,
                    "flood": True,
                    "total": total,
                    "limite": regra["limite"],
                    "janela_segundos": regra["janela_segundos"],
                    "motivo": "memoria",
                    "regra": regra["nome"],
                }

        _limitar_total_chaves()

        return {
            "memoria_ok": True,
            "flood": False,
            "total": maior_total,
            "motivo": "memoria",
            "regra": None,
        }


def _cache_key(wa_id_cliente, phone_id_unidade):
    return f"{str(phone_id_unidade).strip()}:{str(wa_id_cliente).strip()}"


def _contar_eventos_na_janela(eventos, agora, janela_segundos):
    inicio_janela = agora - janela_segundos
    return sum(1 for evento in eventos if evento >= inicio_janela)


def _remover_eventos_antigos(eventos, agora, janela_segundos):
    limite = agora - janela_segundos

    while eventos and eventos[0] < limite:
        eventos.popleft()


def _limpar_chaves_expiradas(agora, regras):
    global _ultima_limpeza

    if agora - _ultima_limpeza < LIMPEZA_INTERVALO_SEGUNDOS:
        return

    maior_janela = max(regra["janela_segundos"] for regra in regras)
    chaves_vazias = []

    for chave, eventos in _eventos_por_chave.items():
        _remover_eventos_antigos(eventos, agora, maior_janela)

        if not eventos:
            chaves_vazias.append(chave)

    for chave in chaves_vazias:
        _eventos_por_chave.pop(chave, None)

    _ultima_limpeza = agora


def _limitar_total_chaves():
    while len(_eventos_por_chave) > MAX_CHAVES_MEMORIA:
        _eventos_por_chave.popitem(last=False)
