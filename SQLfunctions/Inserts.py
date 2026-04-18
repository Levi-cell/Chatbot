from Database.connectionAWS import cursor, conn

def inserindo_em_cliente_caso_seja_novo(waid_telefone):
    try:
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
        result = cursor.fetchone()

        if result:
            return result[0], inserido

        raise ValueError(f"Anomalia Crítica: Cliente do telefone {waid_telefone} desapareceu da base durante a verificação!")

    except Exception as e:
        conn.rollback()
        print(f"Erro ao inserir cliente: {e}")
        raise e  # Propagando o erro para acionar o except no worker_flow




