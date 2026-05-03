import time
import traceback
from Workers.tratamento_erro.expection_process import tratar_erro_processamento

def handle_erro_generico(cursor, id_mensagem, erro, max_retry):
    try:
        if cursor:
            tratar_erro_processamento(
                id_mensagem, erro, max_retry, cursor
            )

    except Exception:
        print("🚨 Erro crítico no handler:")
        print(traceback.format_exc())

    time.sleep(2)