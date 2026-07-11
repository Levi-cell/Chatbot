import logging


logger = logging.getLogger("db.cache_control")

CACHE_UNIDADES_NOME = "unidades"


def buscar_versao_cache_unidades(cursor):
    cursor.execute("""
        SELECT versao
        FROM chatbot.cache_controle
        WHERE nome = %s
        LIMIT 1;
    """, (CACHE_UNIDADES_NOME,))

    resultado = cursor.fetchone()
    versao = int(resultado[0]) if resultado else 1
    logger.debug(
        "cache_controle_versao | acao=buscar nome=%s versao=%s",
        CACHE_UNIDADES_NOME,
        versao,
    )
    return versao


def incrementar_versao_cache_unidades(cursor):
    cursor.execute("""
        INSERT INTO chatbot.cache_controle (nome, versao, atualizado_em)
        VALUES (%s, 1, NOW())
        ON CONFLICT (nome)
        DO UPDATE SET
            versao = chatbot.cache_controle.versao + 1,
            atualizado_em = NOW()
        RETURNING versao;
    """, (CACHE_UNIDADES_NOME,))

    resultado = cursor.fetchone()
    versao = int(resultado[0])
    logger.info(
        "cache_controle_versao | acao=incrementar nome=%s versao=%s",
        CACHE_UNIDADES_NOME,
        versao,
    )
    return versao
