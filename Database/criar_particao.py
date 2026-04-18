from datetime import datetime, timezone, date
from Database.connectionAWS import conn, cursor

# so executar manualmente quando precisar criar partições

def add_months(base_date, months):
    """Avança meses corretamente"""
    year = base_date.year + (base_date.month - 1 + months) // 12
    month = (base_date.month - 1 + months) % 12 + 1
    return date(year, month, 1)


def criar_particoes_historico_mensagens(meses_a_frente=3):
    """
    Cria partições mensais para historico_mensagens.

    Estratégia:
    - Cria mês atual + N meses à frente
    - Seguro para rodar 1x por mês
    """

    if meses_a_frente < 0:
        raise ValueError("meses_a_frente não pode ser negativo")

    hoje = datetime.now(timezone.utc).date()
    primeiro_dia_mes = hoje.replace(day=1)

    particoes_criadas = []

    try:

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

        print("✅ Partições garantidas:")
        for p in particoes_criadas:
            print(f"   - {p}")

        print(f"🚀 Mês atual + {meses_a_frente} meses à frente prontos!")

    except Exception as e:
        conn.rollback()
        print("❌ Erro criando partições")
        print(e)

criar_particoes_historico_mensagens(3)