import logging
from datetime import datetime, timezone, date

from core.database.connection_aws import get_conn


logger = logging.getLogger("db.particoes")

# so executar manualmente quando precisar criar particoes


def add_months(base_date, months):
    """Avanca meses corretamente."""
    year = base_date.year + (base_date.month - 1 + months) // 12
    month = (base_date.month - 1 + months) % 12 + 1
    return date(year, month, 1)


def criar_particoes_historico_mensagens(meses_a_frente=3):
    """
    Cria particoes mensais para historico_mensagens.

    Estrategia:
    - Cria mes atual + N meses a frente
    - Seguro para rodar 1x por mes
    """

    if meses_a_frente < 0:
        raise ValueError("meses_a_frente nao pode ser negativo")

    hoje = datetime.now(timezone.utc).date()
    primeiro_dia_mes = hoje.replace(day=1)

    particoes_criadas = []

    conn = None

    try:
        conn = get_conn(application_name="script_chatbot")
        cursor = conn.cursor()

        for i in range(meses_a_frente + 1):
            inicio = add_months(primeiro_dia_mes, i)
            fim = add_months(primeiro_dia_mes, i + 1)

            nome_particao = f"historico_{inicio.year}_{inicio.month:02d}"

            sql = f"""
            CREATE TABLE IF NOT EXISTS chatbot.{nome_particao}
            PARTITION OF chatbot.historico_mensagens
            FOR VALUES FROM (%s) TO (%s);
            """

            cursor.execute(sql, (inicio, fim))
            particoes_criadas.append(nome_particao)

        conn.commit()

        logger.info(
            "particoes_garantidas | acao=criar_particoes meses_a_frente=%s total=%s particoes=%s",
            meses_a_frente,
            len(particoes_criadas),
            ",".join(particoes_criadas),
        )

    except Exception as erro:
        if conn:
            conn.rollback()
        logger.exception(
            "particoes_erro | acao=criar_particoes meses_a_frente=%s erro=%s",
            meses_a_frente,
            erro,
        )

    finally:
        if conn:
            conn.close()


# criar_particoes_historico_mensagens(3)
