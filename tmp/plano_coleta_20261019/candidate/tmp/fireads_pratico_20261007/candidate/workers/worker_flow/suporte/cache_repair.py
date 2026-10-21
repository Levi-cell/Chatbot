import logging

from core.cache.cache_unidade import recarregar_cache_unidades
from core.cache.runtime.cache_cliente import remover_cliente_cache, salvar_cliente_cache
from core.logging_config import short_value


logger = logging.getLogger("worker.support")


def confirmar_cache_cliente_se_pendente(contexto_banco):
    if not contexto_banco.get("cliente_cache_pendente"):
        return False

    salvar_cliente_cache(
        contexto_banco["cliente_telefone"],
        contexto_banco["id_cliente"],
    )
    contexto_banco["cliente_cache_pendente"] = False

    logger.debug(
        "cliente_cache_confirmado | acao=salvar cliente=%s id_cliente=%s",
        short_value(contexto_banco["cliente_telefone"]),
        contexto_banco["id_cliente"],
    )
    return True


def reparar_cache_cliente_stale_se_fk_invalida(erro, estado_ciclo):
    erro_texto = str(erro)

    if "conversa_id_cliente_fkey" not in erro_texto:
        return False

    cliente_telefone = estado_ciclo.get("cliente_telefone")

    if not cliente_telefone:
        return False

    removido = remover_cliente_cache(cliente_telefone)

    logger.warning(
        "cliente_cache_stale_reparado | motivo=fk_cliente_inexistente acao=remover_cache cliente=%s id_mensagem=%s removido=%s",
        short_value(cliente_telefone),
        estado_ciclo.get("id_mensagem"),
        removido,
    )
    return removido


def reparar_cache_unidade_stale_se_fk_invalida(erro, estado_ciclo):
    erro_texto = str(erro)

    if "conversa_id_unidade_fkey" not in erro_texto:
        return False

    total_unidades = recarregar_cache_unidades()

    logger.warning(
        "unidade_cache_stale_reparado | motivo=fk_unidade_inexistente acao=recarregar_cache_unidades phone_number_id=%s id_mensagem=%s unidades=%s",
        short_value(estado_ciclo.get("id_phone_unidade")),
        estado_ciclo.get("id_mensagem"),
        total_unidades,
    )
    return total_unidades is not None
