from Database.bankScript import (
    criar_tabelas,
    criar_funcao_dequeue_message,
    criar_funcoes_lock,
    definir_timezone_role,
    alterar_banco,
    configurar_timeouts_avancados
)
from Database.connectionTest import connection_teste_psql

def setup_database_aws():
    connection_teste_psql()
    definir_timezone_role()
    criar_tabelas()
    alterar_banco()
    criar_funcao_dequeue_message()
    criar_funcoes_lock()
    configurar_timeouts_avancados()

    print("🚀 Banco totalmente configurado")


setup_database_aws()
