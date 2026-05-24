from core.database.bank_script import (
    criar_tabelas,
    criar_funcao_dequeue_message,
    criar_funcoes_lock,
    definir_timezone_role,
    alterar_banco,
    configurar_timeouts_avancados
)
from core.database.connection_test import connection_teste_psql
from core.database.povoar_etapas import insere_etapa_once
from core.cache.cache_conversas_bloqueadas import limpar_cache_conversas_bloqueadas_dev
from core.cache.cache_unidade import recarregar_cache_unidades

def setup_database_aws():
    connection_teste_psql()
    definir_timezone_role()
    criar_tabelas()
    alterar_banco()
    criar_funcao_dequeue_message()
    criar_funcoes_lock()
    configurar_timeouts_avancados()
    insere_etapa_once()
    recarregar_cache_unidades()
    # Linha exclusiva para DEV: limpa bloqueios antigos quando o banco for recriado.
    limpar_cache_conversas_bloqueadas_dev()

    print("🚀 Banco totalmente configurado")


setup_database_aws()
