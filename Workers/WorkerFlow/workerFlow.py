import time
from SQLfunctions.Querys import (
    pegar_mensagens_da_fila,
    pegar_unidades)
from Database.connectionAWS import cursor, conn
from Workers.WorkerFlow.Flow.povoando_banco import povoa_banco


def worker_flow():
    print("🚀 Worker(s) iniciado...")

    MAX_RETRY = 3

    # preparando cache para unidades
    unidades_map = pegar_unidades()
    last_reload = time.time()

    while True:

        # Atualizando cache para unidades
        if time.time() - last_reload > 60:
            unidades_map = pegar_unidades()
            last_reload = time.time()
            print("🔄 Cache atualizado")

        id_mensagem = None  # evita erro de variável não definida

        try:
            registro = pegar_mensagens_da_fila()
            time.sleep(6)

            # linhas de teste

            print("ciclo")
            print(registro)

            if not registro:
                time.sleep(1)
                continue

            id_mensagem = registro[0]
            cliente_telefone = registro[1]
            conteudo_texto = registro[2]
            tipo_mensagem = registro[3]

            id_phone_unidade = registro[4]

            # para setar unidade com cache perfomatico
            id_unidade = unidades_map.get(id_phone_unidade)

            if not id_unidade:
                # 🔥 fallback pro banco (caso unidade nova)
                cursor.execute("""
                    SELECT id_unidade
                    FROM chatbot.unidade
                    WHERE phone_number_id = %s
                """, (id_phone_unidade,))

                result = cursor.fetchone()

                if not result:
                    raise Exception(f"Unidade não encontrada: {id_phone_unidade}")

                id_unidade = result[0]

                # 🔥 opcional: já atualiza o cache em runtime
                unidades_map[id_phone_unidade] = id_unidade

            unidade_telefone = registro[5]
            data_recebimento = registro[6]
            id_hash = registro[7]
            retry_count = registro[8]

            print(id_mensagem, cliente_telefone, conteudo_texto, tipo_mensagem,
                  id_phone_unidade, unidade_telefone, data_recebimento, id_hash, retry_count)

            print(f"📩 Processando mensagem {id_mensagem} de {cliente_telefone}")

            # ============================================================
            # 🔥 FLUXO DO CHATBOT
            # ============================================================
            povoa_banco(id_mensagem,
                        cliente_telefone,
                        conteudo_texto,
                        tipo_mensagem,
                        id_unidade,
                        unidade_telefone,
                        data_recebimento,
                        id_hash,
                        retry_count)


            cursor.execute("""
                UPDATE chatbot.fila_mensagens
                SET 
                    status = 'sent',
                    last_error = NULL  -- limpa erro antigo se sucesso
                WHERE id_mensagem = %s
            """, (id_mensagem,))

            conn.commit()

            print(f"✅ Mensagem {id_mensagem} processada com sucesso")

        except Exception as erro:
            conn.rollback()  # REGRA DE OURO: Limpa tudo o que foi feito na tentativa antes de reagendar
            print(f"❌ Erro ao processar mensagem: {erro}")

            if id_mensagem is None:
                print("⚠️ Erro antes de identificar mensagem")
                continue

            try:
                # Primeiro tenta deletar se já bateu o limite de retries

                cursor.execute("""
                    DELETE FROM chatbot.fila_mensagens 
                    WHERE id_mensagem = %s AND retry_count >= %s;
                """, (id_mensagem, MAX_RETRY))



                # Para as que NÃO foram deletadas (ainda tem tentativas), volta para pending com 2 minutos
                cursor.execute("""
                    UPDATE chatbot.fila_mensagens
                    SET 
                        status = 'pending',
                        next_attempt_at = NOW() + INTERVAL '2 minutes',
                        last_error = %s
                    WHERE id_mensagem = %s AND retry_count < %s;
                """, (str(erro), id_mensagem, MAX_RETRY))

                conn.commit()

                print(f"🔁 Mensagem {id_mensagem} tratada (retry ou failed)")

            except Exception as erro2:
                conn.rollback()
                print(f"🚨 Erro crítico ao reagendar: {erro2}")


worker_flow()