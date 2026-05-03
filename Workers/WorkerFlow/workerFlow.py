import time
import psycopg2

from Database.connectionAWS import get_conn
from SQLfunctions.Querys import pegar_mensagens_da_fila
from SQLfunctions.Updates import marcar_mensagem_como_enviada
from Workers.WorkerFlow.Flow.povoando_banco import povoa_banco

from Workers.cache.cache_unidade import (
    carregar_unidades_redis_primeira_vez,
    atualizar_unidade_redis_se_necessario,
    obter_id_unidade_redis_ou_plsql,
    UnidadeNaoEncontrada
)

from Workers.tratamento_erro.erro_conexao import handle_erro_conexao
from Workers.tratamento_erro.erro_generico import handle_erro_generico
from Workers.tratamento_erro.unidade_nao_encontrada import handle_unidade_nao_encontrada


def worker_flow():
    print("🚀 Worker(s) iniciado...")

    MAX_RETRY = 3
    retry_delay = 5

    try:
        carregar_unidades_redis_primeira_vez() ## ENCHE O REDIS
    except Exception as e:
        print(f"⚠️ Erro ao carregar cache Redis inicial: {e}")

    while True:

        conn_ciclo = None
        cursor_ciclo = None
        id_mensagem = None

        try:
            conn_ciclo = get_conn()
            cursor_ciclo = conn_ciclo.cursor()

            retry_delay = 5

            atualizar_unidade_redis_se_necessario(cursor_ciclo) # ATUALIZA O REDIS

            registro = pegar_mensagens_da_fila(cursor_ciclo)
            conn_ciclo.commit()

            print(f"🔁 ciclo | registro: {registro}")

            if not registro:
                print("😴 Nenhuma mensagem encontrada")
                time.sleep(30)
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

            # PEGA DO REDIS OU BANCO
            id_unidade = obter_id_unidade_redis_ou_plsql(id_phone_unidade, cursor_ciclo)

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
                id_unidade,
                cursor_ciclo
            )

            marcar_mensagem_como_enviada(id_mensagem, cursor_ciclo)
            conn_ciclo.commit()

            print(f"✅ Mensagem {id_mensagem} processada")

        except psycopg2.OperationalError as erro:
            retry_delay = handle_erro_conexao(erro, retry_delay)
            continue

        except UnidadeNaoEncontrada as erro:
            if conn_ciclo:
                conn_ciclo.rollback()

            handle_unidade_nao_encontrada(
                cursor_ciclo, id_mensagem, erro
            )

            if conn_ciclo:
                conn_ciclo.commit()

        except Exception as erro:
            if conn_ciclo:
                conn_ciclo.rollback()

            handle_erro_generico(
                cursor_ciclo, id_mensagem, erro, MAX_RETRY
            )

            if conn_ciclo:
                conn_ciclo.commit()

        finally:
            if conn_ciclo:
                try:
                    conn_ciclo.close()
                except Exception as e:
                    print(f"⚠️ Erro ao fechar conexão: {e}")