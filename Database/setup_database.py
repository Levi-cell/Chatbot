from Database.bankScript import (
    criar_tabelas,
    criar_funcao_dequeue_message,
    criar_funcoes_lock,
    definir_timezone_role,
    alterar_banco
)
from Database.connectionTest import connection_teste_psql

def setup_database_aws():
    connection_teste_psql()
    definir_timezone_role()
    criar_tabelas()
    alterar_banco()
    criar_funcao_dequeue_message()
    criar_funcoes_lock()

    print("🚀 Banco totalmente configurado")


setup_database_aws()
