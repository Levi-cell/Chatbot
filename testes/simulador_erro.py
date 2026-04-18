import sys
import os
import uuid
import time
from datetime import datetime

# Adiciona o diretório base para conseguir importar os módulos
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from Database.connectionAWS import cursor, conn


def simular_erro_banco():
    print("=" * 60)
    print(" INJETANDO ERRO (RETRY = 2) PARA TESTAR DELEÇÃO FINAL ")
    print("=" * 60)

    hash_alvo = f"wamid_erro_{uuid.uuid4().hex[:6]}"

    # Gerando erro de PostgreSQL estourando o VARCHAR(50)
    telefone_falso_gigante = "9" * 80

    agora = datetime.now()

    try:
        cursor.execute("""
            INSERT INTO chatbot.fila_mensagens (
                cliente_telefone, 
                conteudo_texto, 
                tipo_mensagem, 
                id_phone_unidade, 
                unidade_telefone, 
                received_data_hora, 
                id_hash_msg, 
                status,
                retry_count
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending', 2)
            RETURNING id_mensagem;
        """, (
            telefone_falso_gigante,
            "Esse veneno já entra na Fila com Retry=2. Vai direto pra vala!",
            "text",
            "1",
            "551188888888",
            agora,
            hash_alvo
        ))

        id_gerado = cursor.fetchone()[0]
        conn.commit()

        print("\n✅ MENSAGEM INJETADA COM SUCESSO (Status: pending / Retry: 2)")
        print(f"👉 ID na fila: {id_gerado}")
        print("\nAbra seu terminal do worker e veja: Ele vai dar erro e deletar a mensagem de primeira!")

    except Exception as e:
        conn.rollback()
        print(f"❌ Erro ao usar a injeção do simulador: {e}")


if __name__ == '__main__':
    simular_erro_banco()
