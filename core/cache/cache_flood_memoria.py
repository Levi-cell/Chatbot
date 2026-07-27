import hashlib
import logging
import threading
import time
from collections import OrderedDict

from core.logging_config import short_value


logger = logging.getLogger("cache.flood_memoria")

MAX_CHAVES_MEMORIA = 1000
MAX_WAMIDS_POR_PAR_MEMORIA = 200
LIMPEZA_INTERVALO_SEGUNDOS = 60
DEDUPLICACAO_TTL_SEGUNDOS = 2 * 60 * 60

_lock = threading.Lock()
_eventos_por_chave = OrderedDict()
_ultima_limpeza = 0.0


def avaliar_flood_memoria(
    wa_id_cliente,
    phone_id_unidade,
    id_hash_msg,
    regras,
):
    if (
        not wa_id_cliente
        or not phone_id_unidade
        or not id_hash_msg
        or not regras
    ):
        return {
            "memoria_ok": True,
            "flood": False,
            "total": 0,
            "motivo": "dados_invalidos",
            "regra": None,
            "evento_novo": False,
        }

    agora = time.monotonic()
    chave = _cache_key(
        wa_id_cliente,
        phone_id_unidade,
    )
    membro_wamid = _digest_wamid(id_hash_msg)

    with _lock:
        _limpar_chaves_expiradas(agora, regras)

        eventos = _eventos_por_chave.get(chave)

        if eventos is None:
            eventos = OrderedDict()
            _eventos_por_chave[chave] = eventos

        _remover_eventos_antigos(
            eventos,
            agora,
            DEDUPLICACAO_TTL_SEGUNDOS,
        )

        evento_novo = membro_wamid not in eventos

        if evento_novo:
            eventos[membro_wamid] = agora
            _limitar_wamids_por_par(eventos)

        _eventos_por_chave.move_to_end(chave)
        _limitar_total_chaves()
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
                    "rate_limit_memoria_estourou | "
                    "acao=detectar_flood wa_id_cliente=%s "
                    "phone_id_unidade=%s regra=%s total=%s "
                    "limite=%s janela=%s evento_novo=%s",
                    short_value(wa_id_cliente),
                    short_value(phone_id_unidade),
                    regra["nome"],
                    total,
                    regra["limite"],
                    regra["janela_segundos"],
                    evento_novo,
                )
                return {
                    "memoria_ok": True,
                    "flood": True,
                    "total": total,
                    "limite": regra["limite"],
                    "janela_segundos": regra["janela_segundos"],
                    "motivo": "memoria",
                    "regra": regra["nome"],
                    "evento_novo": evento_novo,
                }

        return {
            "memoria_ok": True,
            "flood": False,
            "total": maior_total,
            "motivo": "memoria",
            "regra": None,
            "evento_novo": evento_novo,
        }


def _cache_key(wa_id_cliente, phone_id_unidade):
    return (
        f"{str(phone_id_unidade).strip()}:"
        f"{str(wa_id_cliente).strip()}"
    )


def _digest_wamid(id_hash_msg):
    return hashlib.sha256(
        str(id_hash_msg).strip().encode("utf-8")
    ).hexdigest()


def _contar_eventos_na_janela(
    eventos,
    agora,
    janela_segundos,
):
    inicio_janela = agora - janela_segundos
    return sum(
        1
        for instante in eventos.values()
        if instante >= inicio_janela
    )


def _remover_eventos_antigos(
    eventos,
    agora,
    janela_segundos,
):
    limite = agora - janela_segundos

    while eventos:
        _wamid, instante = next(iter(eventos.items()))

        if instante >= limite:
            break

        eventos.popitem(last=False)


def _limpar_chaves_expiradas(agora, regras):
    global _ultima_limpeza

    if (
        agora - _ultima_limpeza
        < LIMPEZA_INTERVALO_SEGUNDOS
    ):
        return

    chaves_vazias = []

    for chave, eventos in _eventos_por_chave.items():
        _remover_eventos_antigos(
            eventos,
            agora,
            DEDUPLICACAO_TTL_SEGUNDOS,
        )

        if not eventos:
            chaves_vazias.append(chave)

    for chave in chaves_vazias:
        _eventos_por_chave.pop(chave, None)

    _ultima_limpeza = agora


def _limitar_total_chaves():
    while len(_eventos_por_chave) > MAX_CHAVES_MEMORIA:
        _eventos_por_chave.popitem(last=False)


def _limitar_wamids_por_par(eventos):
    while len(eventos) > MAX_WAMIDS_POR_PAR_MEMORIA:
        eventos.popitem(last=False)
