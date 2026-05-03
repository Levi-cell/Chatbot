from SQLfunctions.Deletes import deletar_mensagem_se_max_retry, deletar_mensagem_por_id
from SQLfunctions.Updates import reagendar_mensagem
import traceback


def tratar_erro_processamento(id_mensagem, erro, max_retry, cursor):
    print(f"❌ Erro ao processar mensagem: {erro}")

    if id_mensagem is None:
        print("⚠️ Erro antes de identificar mensagem")
        print(traceback.format_exc())
        return "no_action"

    linhas_deletadas = deletar_mensagem_se_max_retry(id_mensagem, max_retry, cursor)

    if linhas_deletadas > 0:
        print(f"🗑️ Mensagem {id_mensagem} removida (max retry atingido)")
        return "delete"

    linhas_reagendadas = reagendar_mensagem(id_mensagem, erro, max_retry, cursor)

    if linhas_reagendadas > 0:
        print(f"🔁 Mensagem {id_mensagem} reagendada para nova tentativa")
        return "retry"

    print(f"ℹ️ Nenhuma linha alterada para mensagem {id_mensagem}")
    return "no_action"


def tratar_unidade_nao_encontrada(id_mensagem, erro, cursor):
    print(f"⚠️ Unidade inválida: {erro}")

    if id_mensagem is None:
        return "no_action"

    n = deletar_mensagem_por_id(id_mensagem, cursor)

    if n:
        print(f"🗑️ Removida da fila")
        return "delete"

    print(f"ℹ️ Já não estava na fila")
    return "no_action"