import time
from Database.connectionAWS import conn
from SQLfunctions.Querys import pegar_mensagens_da_fila
from SQLfunctions.Updates import marcar_mensagem_como_enviada
from Workers.WorkerFlow.Flow.povoando_banco import povoa_banco

from Workers.cache.cache_unidade import (
    carregar_cache_redis,
    atualizar_cache_se_necessario,
    obter_id_unidade,
    UnidadeNaoEncontrada
)

from Workers.tratamento_erro.expection_process import (
    tratar_unidade_nao_encontrada,
    tratar_erro_generico)


def worker_flow():
    print("🚀 Worker(s) iniciado...")

    MAX_RETRY = 3

    # 🔥 inicializa cache Redis UMA VEZ
    carregar_cache_redis()

    while True:

        id_mensagem = None

        try:
            atualizar_cache_se_necessario()

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

            print(f"📩 Processando mensagem {id_mensagem}")

            # 🔥 AGORA USA REDIS
            id_unidade = obter_id_unidade(id_phone_unidade)

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

            marcar_mensagem_como_enviada(id_mensagem)
            conn.commit()

            print(f"✅ Mensagem {id_mensagem} processada")

        ## Como unidades só são adicionadas via django iremos tratar elas na estrutura principal do worker
        except UnidadeNaoEncontrada as erro:
            tratar_unidade_nao_encontrada(id_mensagem, erro)
            time.sleep(2)

        except Exception as erro:
            tratar_erro_generico(id_mensagem, erro, MAX_RETRY)
            time.sleep(2)


worker_flow()