import logging

from core.cache.cache_reset import resetar_cache_redis_dev
from core.database.connection_check import connection_teste_psql
from core.database.deploy.bank_script import (
    configurar_timeouts_avancados,
    criar_funcao_dequeue_message,
    criar_funcoes_lock,
    criar_tabelas,
    definir_timezone_role,
)
from core.database.deploy.cache_control_script import criar_cache_controle
from core.database.deploy.etapa_transicao_script import (
    criar_e_povoar_transicoes_etapa,
)
from core.database.deploy.floodscript import criar_tabelas_bloqueio_flood
from core.database.deploy.povoar_etapas import insere_etapa_once
from core.database.deploy.turno_cliente_script import (
    criar_indices_turno_cliente,
)


logger = logging.getLogger("db.deploy")


def setup_database_aws():
    logger.info("banco_setup_iniciado | acao=configurar_banco")
    connection_teste_psql()
    definir_timezone_role()
    criar_tabelas()
    criar_cache_controle()
    criar_tabelas_bloqueio_flood()
    criar_indices_turno_cliente()
    criar_funcao_dequeue_message()
    criar_funcoes_lock()
    configurar_timeouts_avancados()
    insere_etapa_once()
    criar_e_povoar_transicoes_etapa()

    # Linha exclusiva para DEV/deploy: remove cache antigo dependente do banco
    # e recria unidades.
    resetar_cache_redis_dev()

    logger.info("banco_setup_finalizado | acao=configurar_banco")


if __name__ == "__main__":
    setup_database_aws()
