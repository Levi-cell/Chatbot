import logging
import time

from core.cache.runtime.cache_cliente import remover_cliente_cache, salvar_cliente_cache
from core.cache.cache_unidade import recarregar_cache_unidades
from core.logging_config import short_value
from core.repositories.inserts import inserir_historico_mensagem_bot
from core.repositories.querys import (
    existe_mensagem_anterior_aberta_conversa,
    unlock_conversa,
)
from core.repositories.updates import (
    atualizar_conversa_resposta_bot,
    atualizar_conversa_resposta_bot_sem_avancar,
    marcar_mensagem_como_enviada,
    reagendar_mensagem_sem_erro,
)


logger = logging.getLogger("worker.support")


def criar_estado_ciclo():
    return {
        "id_mensagem": None,
        "id_cliente": None,
        "id_conversa": None,
        "id_unidade": None,
        "estado": None,
        "lock_ok": False,
        "lock_version": None,
        "cliente_telefone": None,
        "id_phone_unidade": None,
        "tipo_mensagem": None,
    }


def montar_mensagem_fila(registro):
    (
        id_mensagem,
        cliente_telefone,
        conteudo_texto,
        tipo_mensagem,
        id_phone_unidade,
        unidade_telefone,
        data_recebimento,
        id_hash,
        retry_count,
    ) = registro

    return {
        "id_mensagem": id_mensagem,
        "cliente_telefone": cliente_telefone,
        "conteudo_texto": conteudo_texto,
        "tipo_mensagem": tipo_mensagem,
        "id_phone_unidade": id_phone_unidade,
        "unidade_telefone": unidade_telefone,
        "data_recebimento": data_recebimento,
        "id_hash": id_hash,
        "retry_count": retry_count,
    }


def atualizar_estado_com_mensagem(estado_ciclo, mensagem):
    estado_ciclo["id_mensagem"] = mensagem["id_mensagem"]
    estado_ciclo["cliente_telefone"] = mensagem["cliente_telefone"]
    estado_ciclo["id_phone_unidade"] = mensagem["id_phone_unidade"]
    estado_ciclo["tipo_mensagem"] = mensagem["tipo_mensagem"]


def atualizar_estado_com_contexto(estado_ciclo, contexto_banco):
    contexto_conversa = contexto_banco["conversa"]

    estado_ciclo["id_cliente"] = contexto_banco["id_cliente"]
    estado_ciclo["id_unidade"] = contexto_banco["id_unidade"]
    estado_ciclo["id_conversa"] = contexto_conversa["id_conversa"]
    estado_ciclo["estado"] = contexto_conversa["estado"]


def atualizar_estado_lock(estado_ciclo, lock_ok, lock_version):
    estado_ciclo["lock_ok"] = lock_ok
    estado_ciclo["lock_version"] = lock_version


def aguardar_fila_vazia():
    logger.debug("fila_vazia | acao=aguardar segundos=30")
    time.sleep(30)


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


def logar_lock_recusado(mensagem, contexto_banco):
    contexto_conversa = contexto_banco["conversa"]

    logger.info(
        "conversa_lock_recusado | motivo=conversa_em_processamento acao=continuar id_mensagem=%s cliente=%s phone_number_id=%s id_unidade=%s id_conversa=%s",
        mensagem["id_mensagem"],
        short_value(mensagem["cliente_telefone"]),
        short_value(mensagem["id_phone_unidade"]),
        contexto_banco["id_unidade"],
        contexto_conversa["id_conversa"],
    )


def reagendar_se_houver_mensagem_anterior(
    mensagem,
    contexto_banco,
    lock_version,
    cursor,
):
    contexto_conversa = contexto_banco["conversa"]
    id_conversa = contexto_conversa["id_conversa"]

    existe_anterior = existe_mensagem_anterior_aberta_conversa(
        id_conversa,
        mensagem["id_mensagem"],
        mensagem["data_recebimento"],
        cursor,
    )

    if not existe_anterior:
        return False

    reagendar_mensagem_sem_erro(
        mensagem["id_mensagem"],
        cursor,
        delay_seconds=30,
    )

    logger.info(
        "mensagem_reagendada | motivo=mensagem_anterior_aberta acao=aguardar_ordem id_mensagem=%s cliente=%s phone_number_id=%s id_conversa=%s lock_version=%s",
        mensagem["id_mensagem"],
        short_value(mensagem["cliente_telefone"]),
        short_value(mensagem["id_phone_unidade"]),
        id_conversa,
        lock_version,
    )
    return True


def _obter_data_interacao_bot_existente(contexto_historico):
    resposta_bot = (
        contexto_historico.get("resposta_bot_para_mensagem_atual") or {}
    )
    data_interacao = resposta_bot.get("received_data_hora")

    if data_interacao is None:
        raise ValueError(
            "Resposta do bot existente sem received_data_hora persistido"
        )

    return data_interacao


def atualizar_banco_com_contexto_final(contexto_historico, contexto_envio, cursor):
    id_conversa = contexto_historico["id_conversa"]
    id_etapa_resultante = contexto_envio.get("id_etapa_resultante")
    atualizar_conversa = contexto_envio.get("atualizar_conversa", True)
    atualizar_last_from_bot = contexto_envio.get("atualizar_last_from_bot", True)

    if contexto_envio.get("resposta_ja_existia"):
        data_interacao_bot = None
        if atualizar_conversa or atualizar_last_from_bot:
            data_interacao_bot = _obter_data_interacao_bot_existente(
                contexto_historico
            )

        if atualizar_conversa:
            atualizar_conversa_resposta_bot(
                id_conversa,
                id_etapa_resultante,
                data_interacao_bot,
                cursor,
            )
        elif atualizar_last_from_bot:
            atualizar_conversa_resposta_bot_sem_avancar(
                id_conversa,
                data_interacao_bot,
                cursor,
            )

        logger.info(
            "resposta_bot_idempotente | motivo=resposta_ja_existia acao=atualizar_contexto id_conversa=%s etapa=%s id_hash_msg_bot=%s atualizar_conversa=%s atualizar_last_from_bot=%s",
            id_conversa,
            id_etapa_resultante,
            contexto_envio.get("id_hash_msg_bot"),
            atualizar_conversa,
            atualizar_last_from_bot,
        )
        return {
            "historico_bot_inserido": False,
            "resposta_ja_existia": True,
            "id_hash_msg_bot": contexto_envio.get("id_hash_msg_bot"),
            "id_etapa_resultante": id_etapa_resultante,
            "atualizar_conversa": atualizar_conversa,
            "atualizar_last_from_bot": atualizar_last_from_bot,
        }

    if not contexto_envio.get("enviou"):
        raise ValueError(
            "Contexto de envio sem resposta enviada e sem resposta existente"
        )

    id_historico_bot, data_historico_bot, historico_inserido = (
        inserir_historico_mensagem_bot(
            contexto_historico,
            contexto_envio,
            cursor,
        )
    )

    if atualizar_conversa:
        atualizar_conversa_resposta_bot(
            id_conversa,
            id_etapa_resultante,
            data_historico_bot,
            cursor,
        )
    elif atualizar_last_from_bot:
        atualizar_conversa_resposta_bot_sem_avancar(
            id_conversa,
            data_historico_bot,
            cursor,
        )

    logger.info(
        "resposta_bot_persistida | acao=registrar_historico_e_contexto id_conversa=%s id_historico_bot=%s inserido=%s etapa=%s id_hash_msg_bot=%s atualizar_conversa=%s atualizar_last_from_bot=%s",
        id_conversa,
        id_historico_bot,
        historico_inserido,
        id_etapa_resultante,
        contexto_envio.get("id_hash_msg_bot"),
        atualizar_conversa,
        atualizar_last_from_bot,
    )

    return {
        "historico_bot_inserido": historico_inserido,
        "resposta_ja_existia": False,
        "id_historico_bot": id_historico_bot,
        "data_historico_bot": data_historico_bot,
        "id_hash_msg_bot": contexto_envio.get("id_hash_msg_bot"),
        "id_etapa_resultante": id_etapa_resultante,
        "atualizar_conversa": atualizar_conversa,
        "atualizar_last_from_bot": atualizar_last_from_bot,
    }


def finalizar_mensagem_processada(
    mensagem,
    contexto_banco,
    lock_version,
    cursor,
):
    contexto_conversa = contexto_banco["conversa"]

    marcar_mensagem_como_enviada(mensagem["id_mensagem"], cursor)

    logger.info(
        "mensagem_processada | acao=marcar_sent id_mensagem=%s cliente=%s phone_number_id=%s id_unidade=%s id_conversa=%s estado=%s lock_version=%s",
        mensagem["id_mensagem"],
        short_value(mensagem["cliente_telefone"]),
        short_value(mensagem["id_phone_unidade"]),
        contexto_banco["id_unidade"],
        contexto_conversa["id_conversa"],
        contexto_conversa["estado"],
        lock_version,
    )


def liberar_lock_conversa_se_necessario(cursor, estado_ciclo):
    if not (
        estado_ciclo["lock_ok"]
        and estado_ciclo["id_conversa"]
        and estado_ciclo["lock_version"] is not None
    ):
        return None

    unlock_realizado = unlock_conversa(
        estado_ciclo["id_conversa"],
        estado_ciclo["lock_version"],
        cursor,
    )

    logger.debug(
        "conversa_unlock | acao=liberar id_conversa=%s lock_version=%s liberada=%s",
        estado_ciclo["id_conversa"],
        estado_ciclo["lock_version"],
        unlock_realizado,
    )
    return unlock_realizado
