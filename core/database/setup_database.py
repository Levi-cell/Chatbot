import logging

from core.database.bank_script import (
    criar_tabelas,
    criar_funcao_dequeue_message,
    criar_funcoes_lock,
    definir_timezone_role,
    alterar_banco,
    configurar_timeouts_avancados,
)
from core.database.floodscript import criar_tabelas_bloqueio_flood
from core.database.cache_control_script import criar_cache_controle
from core.database.connection_test import connection_teste_psql
from core.database.povoar_etapas import insere_etapa_once
from core.database.turno_cliente_script import criar_indices_turno_cliente
from core.cache.cache_conversas_bloqueadas import limpar_cache_conversas_bloqueadas_dev
from core.cache.cache_unidade import recarregar_cache_unidades


logger = logging.getLogger("db.setup")


def setup_database_aws():
    logger.info("banco_setup_iniciado | acao=configurar_banco")
    connection_teste_psql()
    definir_timezone_role()
    criar_tabelas()
    criar_cache_controle()
    alterar_banco()
    criar_tabelas_bloqueio_flood()
    criar_indices_turno_cliente()
    criar_funcao_dequeue_message()
    criar_funcoes_lock()
    configurar_timeouts_avancados()
    insere_etapa_once()
    recarregar_cache_unidades()
    # Linha exclusiva para DEV: limpa bloqueios antigos quando o banco for recriado.
    limpar_cache_conversas_bloqueadas_dev()

    logger.info("banco_setup_finalizado | acao=configurar_banco")


setup_database_aws()
