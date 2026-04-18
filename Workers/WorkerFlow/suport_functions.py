from SQLfunctions.Inserts import inserindo_em_cliente_caso_seja_novo


def verifica_se_cliente_novo_ou_nao(wa_id_telefone):
    id_cliente, inserido = inserindo_em_cliente_caso_seja_novo(wa_id_telefone)

    if inserido:
        print(f"O cliente é novo e seu ID é {id_cliente}")
    else:
        print(f"O cliente não é novo, o seu ID é {id_cliente}")
        
    return id_cliente

def adiciona_ou_valida_conversa_ativa_entre_cliente_unidade(id_cliente, id_unidade):
    from Database.connectionAWS import cursor

    # tenta buscar conversa ativa
    cursor.execute("""
        SELECT id_conversa, lock_version
        FROM chatbot.conversa
        WHERE id_cliente = %s
          AND id_unidade = %s
          AND status_ativa = TRUE
        LIMIT 1
    """, (id_cliente, id_unidade))

    conversa = cursor.fetchone()

    if conversa:
        return conversa  # já existe

    # se não existe → cria
    cursor.execute("""
        INSERT INTO chatbot.conversa (id_cliente, id_unidade)
        VALUES (%s, %s)
        RETURNING id_conversa, lock_version
    """, (id_cliente, id_unidade))

    return cursor.fetchone()

def tentar_lock_conversa(id_conversa):
    from Database.connectionAWS import cursor

    cursor.execute(
        "SELECT chatbot.lock_conversa(%s);",
        (id_conversa,)
    )

    return cursor.fetchone()[0]
