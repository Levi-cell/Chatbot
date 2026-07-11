import logging

from core.cache.cache_reset import resetar_cache_redis_dev
from core.database.connection_check import connection_teste_psql
from core.database.deploy.bank_script import (
    configurar_role_banco,
    criar_funcao_dequeue_message,
    criar_funcoes_lock,
    criar_tabelas,
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

    # 1. Infraestrutura e configuração da role usada pela aplicação.
    connection_teste_psql()
    configurar_role_banco()

    # 2. Schema final e estruturas auxiliares por domínio.
    criar_tabelas()
    criar_cache_controle()
    criar_tabelas_bloqueio_flood()
    criar_indices_turno_cliente()

    # 3. Funções PostgreSQL consumidas pelo worker.
    criar_funcao_dequeue_message()
    criar_funcoes_lock()

    # 4. Catálogos executáveis do fluxo de atendimento.
    insere_etapa_once()
    criar_e_povoar_transicoes_etapa()

    # 5. O cache derivado só é reconstruído após o banco estar completo.
    resetar_cache_redis_dev()

    logger.info("banco_setup_finalizado | acao=configurar_banco")


if __name__ == "__main__":
    setup_database_aws()
