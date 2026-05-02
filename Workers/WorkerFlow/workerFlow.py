import time
from Database.connectionAWS import conn
from SQLfunctions.Deletes import deletar_mensagem_por_id
from SQLfunctions.Querys import pegar_mensagens_da_fila
from SQLfunctions.Updates import marcar_mensagem_como_enviada
from Workers.WorkerFlow.Flow.povoando_banco import povoa_banco
from Workers.cache.cache_unidade import (
    inicializar_cache_unidades,
    atualizar_cache_se_necessario,
    obter_id_unidade,
    UnidadeNaoEncontrada)
from Workers.tratamento_erro.expection_process import tratar_erro_processamento




def worker_flow():
    print("🚀 Worker(s) iniciado...")

    MAX_RETRY = 3

    # 🔥 Cache inicial de unidades
    unidades_map, last_reload = inicializar_cache_unidades()

    while True:

        # 🔄 Atualiza cache de unidades
        unidades_map, last_reload = atualizar_cache_se_necessario(
            unidades_map,
            last_reload
        )

        id_mensagem = None

        try:
            registro = pegar_mensagens_da_fila()


            print("ciclo")
            print(registro)

            if not registro:
                time.sleep(1)
                continue

            (
                id_mensagem,
                cliente_telefone,
                conteudo_texto,
                tipo_mensagem,
                id_phone_unidade,
                unidade_telefone,
                data_recebimento,
                id_hash,
                retry_count
            ) = registro

            print(f"📩 Processando mensagem {id_mensagem} de {cliente_telefone}")

            # 🔥 resolve unidade (cache + fallback)
            id_unidade = obter_id_unidade(id_phone_unidade, unidades_map)

            # 🔥 fluxo principal
            povoa_banco(
                id_mensagem,
                cliente_telefone,
                conteudo_texto,
                tipo_mensagem,
                id_phone_unidade,
                unidade_telefone,
                data_recebimento,
                id_hash,
                retry_count,
                id_unidade
            )

            # 🔥 marca como enviada
            marcar_mensagem_como_enviada(id_mensagem)

            conn.commit()

            print(f"✅ Mensagem {id_mensagem} processada com sucesso")

        except UnidadeNaoEncontrada as erro:
            conn.rollback()
            print(f"⚠️ Unidade inválida: {erro}")

            # Sem unidade no banco: não adianta retry (ex.: cliente cancelou / número só na Meta).
            if id_mensagem is not None:
                n = deletar_mensagem_por_id(id_mensagem)
                conn.commit()
                if n:
                    print(f"🗑️ Mensagem {id_mensagem} removida da fila (phone_number_id sem unidade)")
                else:
                    print(f"ℹ️ Mensagem {id_mensagem} já não estava na fila")

        except Exception as erro:
            conn.rollback()
            tratar_erro_processamento(id_mensagem, erro, MAX_RETRY)


worker_flow()


### WORKER COM REDIS

# import time
# from Database.connectionAWS import conn
# from SQLfunctions.Deletes import deletar_mensagem_por_id
# from SQLfunctions.Querys import pegar_mensagens_da_fila
# from SQLfunctions.Updates import marcar_mensagem_como_enviada
# from Workers.WorkerFlow.Flow.povoando_banco import povoa_banco
#
# from Workers.cache.cache_unidades import (
#     carregar_cache_redis,
#     atualizar_cache_se_necessario,
#     obter_id_unidade,
#     UnidadeNaoEncontrada
# )
#
# from Workers.tratamento_erro.expection_process import tratar_erro_processamento
#
#
# def worker_flow():
#     print("🚀 Worker(s) iniciado...")
#
#     MAX_RETRY = 3
#
#     # 🔥 inicializa cache Redis UMA VEZ
#     carregar_cache_redis()
#
#     while True:
#
#         # 🔄 verifica se precisa recarregar
#         atualizar_cache_se_necessario()
#
#         id_mensagem = None
#
#         try:
#             registro = pegar_mensagens_da_fila()
#             time.sleep(6)
#
#             print("ciclo")
#             print(registro)
#
#             if not registro:
#                 time.sleep(1)
#                 continue
#
#             conn.commit()
#
#             (
#                 id_mensagem,
#                 cliente_telefone,
#                 conteudo_texto,
#                 tipo_mensagem,
#                 id_phone_unidade,
#                 unidade_telefone,
#                 data_recebimento,
#                 id_hash,
#                 retry_count
#             ) = registro
#
#             print(f"📩 Processando mensagem {id_mensagem}")
#
#             # 🔥 AGORA USA REDIS
#             id_unidade = obter_id_unidade(id_phone_unidade)
#
#             povoa_banco(
#                 id_mensagem,
#                 cliente_telefone,
#                 conteudo_texto,
#                 tipo_mensagem,
#                 id_phone_unidade,
#                 unidade_telefone,
#                 data_recebimento,
#                 id_hash,
#                 retry_count,
#                 id_unidade
#             )
#
#             marcar_mensagem_como_enviada(id_mensagem)
#             conn.commit()
#
#             print(f"✅ Mensagem {id_mensagem} processada")
#
#         except UnidadeNaoEncontrada as erro:
#             conn.rollback()
#             print(f"⚠️ Unidade inválida: {erro}")
#
#             if id_mensagem is not None:
#                 n = deletar_mensagem_por_id(id_mensagem)
#                 conn.commit()
#
#                 if n:
#                     print(f"🗑️ Removida da fila")
#                 else:
#                     print(f"ℹ️ Já não estava na fila")
#
#         except Exception as erro:
#             conn.rollback()
#             tratar_erro_processamento(id_mensagem, erro, MAX_RETRY)
#
#
# worker_flow()