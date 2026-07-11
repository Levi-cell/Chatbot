import logging

from core.database.deploy.transacao_deploy import transacao_deploy


logger = logging.getLogger("db.turno_cliente_setup")


def criar_indices_turno_cliente():
    with transacao_deploy("criar_indices_turno_cliente", logger) as cursor:
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_fila_cliente_unidade_aberta
            ON chatbot.fila_mensagens (
                cliente_telefone,
                id_phone_unidade,
                status,
                received_data_hora,
                id_mensagem
            )
            WHERE status IN ('pending', 'processing');

            CREATE INDEX IF NOT EXISTS idx_fila_cliente_unidade_conversa_aberta
            ON chatbot.fila_mensagens (
                cliente_telefone,
                id_phone_unidade,
                id_conversa,
                id_hash_msg,
                id_mensagem
            )
            WHERE status IN ('pending', 'processing');
        """)

    logger.info("banco_setup_ok | acao=criar_indices_turno_cliente")
