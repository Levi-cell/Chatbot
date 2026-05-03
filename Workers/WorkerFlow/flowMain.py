from Workers.WorkerFlow.workerFlow import worker_flow
import time

def inicia_flow_main():
    while True:
        try:
            print("🚀 Iniciando sistema...")
            worker_flow()
        except Exception as e:
            print(f"💥 Worker morreu: {e}")
            print("🔁 Reiniciando em 5s...")
            time.sleep(5)



inicia_flow_main()