from Database.connectionAWS import cursor, conn

"""Aqui não só existe querys de consulta mas também querys que
chama funções SQL, na dúvida consulte Bankscript.py"""

def pegar_unidades():
    cursor.execute("""
        SELECT phone_number_id, id_unidade
        FROM chatbot.unidade
        WHERE status_ativo = TRUE
    """)

    resultado = {row[0]: row[1] for row in cursor.fetchall()}

    print(f"📦 Cache de unidades carregado: {len(resultado)} unidades")

    return resultado

def pegar_mensagens_da_fila():
    """Aqui usamos uma função que criamos dentro do nosso script SQL

    a função chatbot.dequeue_message já consulta a fila de mensagens e
    também faz uma validação evitando que vários workers peguem a mesma mensagem,
    então o SELECT da função abaixo está pegando os registros validados a partir
    dessa função SQL, pense que a função python faz uma consulta e dentro da consulta o
    SQL executa outra função. Em suma, essa função serve para arquitetura complexas com
    varios workers e arquiteturas simples.

    OBS: dequeue_message é igual a fila de mensagens em inglês, a função mexe diretamente
    com a tabela e suas interligações pelo banco.

    """
    cursor.execute("SELECT * FROM chatbot.dequeue_message();")
    registro = cursor.fetchone()


    return registro

def buscar_id_unidade_por_phone_id(phone_number_id):
    cursor.execute("""
        SELECT id_unidade
        FROM chatbot.unidade
        WHERE phone_number_id = %s
    """, (phone_number_id,))

    result = cursor.fetchone()
    return result[0] if result else None


def buscar_last_message_from_conversa(cliente_telefone, id_phone_unidade):
    """
    Busca o campo last_message_from da conversa ativa do cliente
    para a unidade correspondente.
    """
    cursor.execute("""
        SELECT c.last_message_from
        FROM chatbot.conversa c
        JOIN chatbot.cliente cl ON cl.id_cliente = c.id_cliente
        JOIN chatbot.unidade u ON u.id_unidade = c.id_unidade
        WHERE cl.waid_telefone = %s
          AND u.phone_number_id = %s
          AND c.status_ativa = TRUE
        LIMIT 1;
    """, (cliente_telefone, id_phone_unidade))

    resultado = cursor.fetchone()
    return resultado[0] if resultado else None

def tentar_lock_conversa(id_conversa):
    cursor.execute("SELECT chatbot.lock_conversa(%s);", (id_conversa,))
    return cursor.fetchone()[0]


def unlock_conversa(id_conversa):
    cursor.execute("SELECT chatbot.unlock_conversa(%s);", (id_conversa,))

def verifica_existencia_conversa():
    print("hi")

def verifica_existencia_hist_msg():
    print("hi")


# def buscar_conversa_ativa(cliente_telefone, id_phone_unidade):
#     """
#     Busca a conversa ativa do cliente para a unidade correspondente.
#     Retorna todos os campos da tabela conversa.
#     """
#     cursor.execute("""
#         SELECT c.*
#         FROM chatbot.conversa c
#         JOIN chatbot.cliente cl ON cl.id_cliente = c.id_cliente
#         JOIN chatbot.unidade u ON u.id_unidade = c.id_unidade
#         WHERE cl.waid_telefone = %s
#           AND u.phone_number_id = %s
#           AND c.status_ativa = TRUE
#         LIMIT 1;
#     """, (cliente_telefone, id_phone_unidade))
#
#     return cursor.fetchone()