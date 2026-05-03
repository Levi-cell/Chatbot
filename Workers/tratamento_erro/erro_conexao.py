import time

def handle_erro_conexao(erro, retry_delay):
    print(f"🌐 Banco indisponível / erro de rede: {erro}")

    print(f"⏳ Aguardando {retry_delay}s para tentar reconectar...")
    time.sleep(retry_delay)

    return min(retry_delay * 2, 60)