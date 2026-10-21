import logging

from core.logging_config import short_value


logger = logging.getLogger("db.suspeita_bot")

LIMITE_TURNOS_SEM_AVANCO = 12


def incrementar_turnos_sem_avanco(id_conversa, cursor):
    cursor.execute("""
        UPDATE chatbot.conversa
        SET turnos_sem_avanco = LEAST(
            turnos_sem_avanco + 1,
            %s
        )
        WHERE id_conversa = %s
        RETURNING turnos_sem_avanco;
    """, (LIMITE_TURNOS_SEM_AVANCO, id_conversa))

    resultado = cursor.fetchone()

    if not resultado:
        raise ValueError(
            "Conversa ausente ao incrementar turnos sem avanço "
            f"(id_conversa={id_conversa})"
        )

    contador = int(resultado[0])
    logger.info(
        "turnos_sem_avanco_incrementados | acao=incrementar "
        "id_conversa=%s turnos_sem_avanco=%s limite=%s",
        id_conversa,
        contador,
        LIMITE_TURNOS_SEM_AVANCO,
    )
    return contador


def resetar_turnos_sem_avanco(id_conversa, cursor):
    cursor.execute("""
        UPDATE chatbot.conversa
        SET turnos_sem_avanco = 0
        WHERE id_conversa = %s
        RETURNING turnos_sem_avanco;
    """, (id_conversa,))

    resultado = cursor.fetchone()

    if not resultado:
        raise ValueError(
            "Conversa ausente ao resetar turnos sem avanço "
            f"(id_conversa={id_conversa})"
        )

    logger.info(
        "turnos_sem_avanco_resetados | acao=resetar "
        "id_conversa=%s turnos_sem_avanco=0",
        id_conversa,
    )
    return 0


def buscar_conversa_no_limite_sem_avanco(
    wa_id_cliente,
    phone_id_unidade,
    cursor,
):
    cursor.execute("""
        SELECT
            conversa.id_conversa,
            conversa.id_cliente,
            cliente.nome,
            conversa.id_unidade,
            unidade.phone_number_id,
            conversa.turnos_sem_avanco
        FROM chatbot.conversa AS conversa
        JOIN chatbot.cliente AS cliente
          ON cliente.id_cliente = conversa.id_cliente
        JOIN chatbot.unidade AS unidade
          ON unidade.id_unidade = conversa.id_unidade
        WHERE cliente.waid_telefone = %s
          AND unidade.phone_number_id = %s
          AND conversa.status_ativa = TRUE
          AND conversa.turnos_sem_avanco >= %s
        ORDER BY conversa.id_conversa DESC
        LIMIT 1;
    """, (
        wa_id_cliente,
        phone_id_unidade,
        LIMITE_TURNOS_SEM_AVANCO,
    ))

    resultado = cursor.fetchone()

    if not resultado:
        logger.debug(
            "turnos_sem_avanco_consulta | acao=seguir_fluxo "
            "wa_id_cliente=%s phone_id_unidade=%s limite=%s",
            short_value(wa_id_cliente),
            short_value(phone_id_unidade),
            LIMITE_TURNOS_SEM_AVANCO,
        )
        return None

    dados = {
        "id_conversa": resultado[0],
        "id_cliente": resultado[1],
        "nome_cliente": resultado[2],
        "id_unidade": resultado[3],
        "phone_id_unidade": resultado[4],
        "turnos_sem_avanco": int(resultado[5]),
    }
    logger.warning(
        "turnos_sem_avanco_limite_encontrado | "
        "acao=promover_para_denylist "
        "id_conversa=%s id_cliente=%s id_unidade=%s "
        "wa_id_cliente=%s phone_id_unidade=%s "
        "turnos_sem_avanco=%s limite=%s",
        dados["id_conversa"],
        dados["id_cliente"],
        dados["id_unidade"],
        short_value(wa_id_cliente),
        short_value(phone_id_unidade),
        dados["turnos_sem_avanco"],
        LIMITE_TURNOS_SEM_AVANCO,
    )
    return dados
