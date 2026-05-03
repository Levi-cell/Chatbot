import time
import traceback
from Workers.tratamento_erro.expection_process import tratar_unidade_nao_encontrada

def handle_unidade_nao_encontrada(cursor, id_mensagem, erro):
    try:
        if cursor:
            tratar_unidade_nao_encontrada(id_mensagem, erro, cursor)

    except Exception:
        print("🚨 Erro crítico (Unidade):")
        print(traceback.format_exc())

    time.sleep(2)