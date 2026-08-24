import logging

from core.logging_config import short_value


logger = logging.getLogger("db.atendimento.clientes")


def inserindo_em_cliente_caso_seja_novo(waid_telefone, cursor):
    cursor.execute("""
        INSERT INTO chatbot.cliente (waid_telefone)
        VALUES (%s)
        ON CONFLICT (waid_telefone) DO NOTHING;
    """, (waid_telefone,))

    inserido = cursor.rowcount == 1

    cursor.execute("""
        SELECT id_cliente
        FROM chatbot.cliente
        WHERE waid_telefone = %s;
    """, (waid_telefone,))
    resultado = cursor.fetchone()

    if resultado:
        logger.debug(
            "cliente_insert_resultado | acao=obter_cliente telefone=%s id_cliente=%s inserido=%s",
            short_value(waid_telefone),
            resultado[0],
            inserido,
        )
        return resultado[0], inserido

    raise ValueError(
        "Anomalia Crítica: Cliente do telefone "
        f"{waid_telefone} desapareceu da base durante a verificação!"
    )


def atualizar_nome_cliente_por_telefone(waid_telefone, nome, cursor):
    if not waid_telefone:
        raise ValueError(
            "waid_telefone nao informado para atualizar nome do cliente"
        )

    if not nome:
        raise ValueError("nome nao informado para atualizar cliente")

    cursor.execute("""
        UPDATE chatbot.cliente
        SET nome = %s
        WHERE waid_telefone = %s;
    """, (nome, waid_telefone))

    logger.debug(
        "cliente_update | acao=atualizar_nome telefone=%s linhas=%s",
        short_value(waid_telefone),
        cursor.rowcount,
    )

    if cursor.rowcount != 1:
        raise ValueError(
            "Cliente nao foi atualizado com nome "
            f"(telefone={short_value(waid_telefone)}, linhas={cursor.rowcount})"
        )

    return cursor.rowcount


def atualizar_email_cliente(id_cliente, email, cursor):
    cursor.execute(
        """
        UPDATE chatbot.cliente
        SET email = %s
        WHERE id_cliente = %s;
        """,
        (email, id_cliente),
    )

    if cursor.rowcount != 1:
        raise RuntimeError(
            "Cliente não atualizado com email "
            f"(id_cliente={id_cliente}, linhas={cursor.rowcount})"
        )


def atualizar_idade_cliente(id_cliente, idade, cursor):
    cursor.execute(
        """
        UPDATE chatbot.cliente
        SET idade = %s
        WHERE id_cliente = %s;
        """,
        (idade, id_cliente),
    )

    if cursor.rowcount != 1:
        raise RuntimeError(
            "Cliente não atualizado com idade "
            f"(id_cliente={id_cliente}, linhas={cursor.rowcount})"
        )


def atualizar_profissao_cliente(id_cliente, profissao, cursor):
    if not id_cliente:
        raise ValueError(
            "id_cliente nao informado para atualizar profissao"
        )

    if not isinstance(profissao, str):
        raise ValueError("profissao deve ser um texto")

    profissao_normalizada = profissao.strip()

    if (
        not profissao_normalizada
        or len(profissao_normalizada) > 100
        or "\n" in profissao_normalizada
        or "\r" in profissao_normalizada
    ):
        raise ValueError(
            "profissao deve conter uma unica linha entre 1 e 100 caracteres"
        )

    cursor.execute(
        """
        UPDATE chatbot.cliente
        SET profissao = %s
        WHERE id_cliente = %s;
        """,
        (profissao_normalizada, id_cliente),
    )

    logger.debug(
        "cliente_update | acao=atualizar_profissao "
        "id_cliente=%s linhas=%s",
        id_cliente,
        cursor.rowcount,
    )

    if cursor.rowcount != 1:
        raise ValueError(
            "Cliente nao foi atualizado com profissao "
            f"(id_cliente={id_cliente}, linhas={cursor.rowcount})"
        )

    return cursor.rowcount
