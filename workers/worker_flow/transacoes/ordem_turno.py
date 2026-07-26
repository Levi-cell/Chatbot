import logging

from core.logging_config import short_value
from core.repositories.atendimento.fila import (
    existe_mensagem_anterior_aberta_atendimento,
    reagendar_mensagem_sem_erro,
)


logger = logging.getLogger("worker.support")


def logar_lock_recusado(mensagem, contexto_banco):
    contexto_conversa = contexto_banco["conversa"]

    logger.info(
        "conversa_lock_recusado | motivo=conversa_em_processamento "
        "acao=reagendar_sem_erro delay_seconds=5 "
        "id_mensagem=%s cliente=%s phone_number_id=%s "
        "id_unidade=%s id_conversa=%s",
        mensagem["id_mensagem"],
        short_value(mensagem["cliente_telefone"]),
        short_value(mensagem["id_phone_unidade"]),
        contexto_banco["id_unidade"],
        contexto_conversa["id_conversa"],
    )


def reagendar_se_houver_mensagem_anterior(
    mensagem,
    cursor,
):
    existe_anterior = existe_mensagem_anterior_aberta_atendimento(
        mensagem["cliente_telefone"],
        mensagem["id_phone_unidade"],
        mensagem["id_mensagem"],
        mensagem["data_recebimento"],
        cursor,
    )

    if not existe_anterior:
        return False

    linhas_reagendadas = reagendar_mensagem_sem_erro(
        mensagem["id_mensagem"],
        cursor,
        delay_seconds=30,
    )

    if linhas_reagendadas != 1:
        logger.warning(
            "mensagem_ordem_nao_reagendada | "
            "motivo=linha_nao_disponivel acao=interromper_ciclo "
            "id_mensagem=%s cliente=%s phone_number_id=%s linhas=%s",
            mensagem["id_mensagem"],
            short_value(mensagem["cliente_telefone"]),
            short_value(mensagem["id_phone_unidade"]),
            linhas_reagendadas,
        )

    logger.info(
        "mensagem_reagendada | "
        "motivo=mensagem_anterior_aberta_mesmo_atendimento "
        "acao=aguardar_ordem id_mensagem=%s cliente=%s "
        "phone_number_id=%s",
        mensagem["id_mensagem"],
        short_value(mensagem["cliente_telefone"]),
        short_value(mensagem["id_phone_unidade"]),
    )
    return True
