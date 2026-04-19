from Database.connectionAWS import conn
from SQLfunctions.Deletes import deletar_mensagem_se_max_retry
from SQLfunctions.Updates import reagendar_mensagem


def tratar_erro_processamento(id_mensagem, erro, max_retry):
    print(f"❌ Erro ao processar mensagem: {erro}")

    if id_mensagem is None:
        print("⚠️ Erro antes de identificar mensagem")
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
        conn.rollback()
        print(f"🚨 Erro crítico ao reagendar: {erro2}")