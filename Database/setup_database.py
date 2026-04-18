from Database.bankScript import (
    criar_tabelas,
    criar_funcao_dequeue_message,
    criar_funcoes_lock,
    definir_timezone_role,
    alterar_banco
)


def setup_database_aws():
    definir_timezone_role()
    criar_tabelas()
    alterar_banco()
    criar_funcao_dequeue_message()
    criar_funcoes_lock()

    print("🚀 Banco totalmente configurado")


setup_database_aws()