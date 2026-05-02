from Database.connectionAWS import conn
from SQLfunctions.Deletes import deletar_mensagem_se_max_retry, deletar_mensagem_por_id
from SQLfunctions.Updates import reagendar_mensagem
import traceback

def tratar_erro_processamento(id_mensagem, erro, max_retry):
    print(f"❌ Erro ao processar mensagem: {erro}")

    if id_mensagem is None:
        print("⚠️ Erro antes de identificar mensagem")
        print(traceback.format_exc())
        return

    try:
        linhas_deletadas = deletar_mensagem_se_max_retry(id_mensagem, max_retry)

        if linhas_deletadas > 0:
            print(f"🗑️ Mensagem {id_mensagem} removida (max retry atingido)")
            conn.commit()
            return

        linhas_reagendadas = reagendar_mensagem(id_mensagem, erro, max_retry)

        if linhas_reagendadas > 0:
            print(f"🔁 Mensagem {id_mensagem} reagendada para nova tentativa")
        else:
            print(f"ℹ️ Nenhuma linha alterada para mensagem {id_mensagem}")

        conn.commit()

    except Exception as erro2:
        try:
            conn.rollback()

        except Exception as e:

            print(f"Erro ao fazer rollback, {e}")
            pass
        print(f"🚨 Erro crítico ao reagendar: {erro2}")

def tratar_unidade_nao_encontrada(id_mensagem, erro):

    try:
        conn.rollback()

    except Exception as e:

        print(f"Erro ao fazer rollback, {e}")
        pass

    print(f"⚠️ Unidade inválida: {erro}")

    if id_mensagem is None:
        return

    try:
        n = deletar_mensagem_por_id(id_mensagem)
        conn.commit()

        if n:
            print(f"🗑️ Removida da fila")
        else:
            print(f"ℹ️ Já não estava na fila")

    except Exception as e:

        try:
            conn.rollback()

        except Exception as err:

            print(f"Erro ao fazer rollback, {err}")
            pass

        print(f"🚨 Erro ao remover mensagem inválida: {e}")

def tratar_erro_generico(id_mensagem, erro, max_retry):
    try:
        conn.rollback()
    except Exception as e:
        print(f"⚠️ Erro ao dar rollback: {e}")
        pass

    try:
        tratar_erro_processamento(id_mensagem, erro, max_retry)
    except Exception as erro2:
        print(f"🚨 Erro crítico no handler: {erro2}")