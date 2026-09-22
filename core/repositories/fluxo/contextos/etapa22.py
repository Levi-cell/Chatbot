"""Participante da conversa usado na despedida, a partir das etapas 20 e 21."""


def buscar_contexto_etapa22(id_conversa, id_unidade, cursor):
    cursor.execute(
        """
        SELECT c.status_dependente, d.nome_dependente
        FROM chatbot.conversa c
        LEFT JOIN chatbot.dependente d ON d.id_conversa = c.id_conversa
        WHERE c.id_conversa = %s
          AND c.id_unidade = %s
        LIMIT 1;
        """,
        (id_conversa, id_unidade),
    )
    resultado = cursor.fetchone()
    if not resultado:
        raise ValueError(
            "Contexto de finalização não encontrado "
            f"(id_conversa={id_conversa}, id_unidade={id_unidade})"
        )

    status_dependente, nome_dependente = resultado
    if type(status_dependente) is not bool:
        raise ValueError("Destino do atendimento ausente para a finalização")
    if status_dependente and (
        not isinstance(nome_dependente, str) or not nome_dependente.strip()
    ):
        raise ValueError("Nome do dependente ausente para a finalização")

    return {
        "status_dependente_contexto_finalizacao": status_dependente,
        "nome_dependente": nome_dependente.strip() if status_dependente else None,
    }
