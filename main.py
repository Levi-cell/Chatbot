
#### NÂO EXECUTAR POR ENQUANTO

from Database.setup_database import setup_database_aws
from Database.redis_client import confirmar_conexao_redis

def run_workers():


    setup_database_aws()
    confirmar_conexao_redis()