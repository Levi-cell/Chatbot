import logging
import time


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
    logger.debug("fila_vazia | acao=aguardar segundos=1.5")
    time.sleep(1.5)
