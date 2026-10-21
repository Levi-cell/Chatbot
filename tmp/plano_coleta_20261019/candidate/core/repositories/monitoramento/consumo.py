"""Leituras limitadas à unidade autenticada; nunca consultam a Meta."""

from .painel import _linha, _linhas


def buscar_unidade(cursor, id_unidade):
    cursor.execute("""
        SELECT u.id_unidade, u.nome_unidade, u.nome_fuso,
               c.ultimo_erro AS erro_conta, c.ultima_tentativa_em AS tentativa_conta
          FROM chatbot.unidade u
          LEFT JOIN chatbot.consumo_meta_coletas c
            ON c.id_unidade = u.id_unidade AND c.periodo = 'conta'
         WHERE u.id_unidade = %s
    """, (id_unidade,))
    return _linha(cursor)


def listar_meses(cursor, id_unidade):
    # Uma única leitura monta cartões, histórico e PDFs com os mesmos totais.
    cursor.execute("""
        SELECT m.*, c.ultimo_erro, c.ultima_tentativa_em
          FROM chatbot.consumo_mensal_meta m
          LEFT JOIN chatbot.consumo_meta_coletas c
            ON c.id_unidade = m.id_unidade AND c.periodo = TO_CHAR(m.mes_referencia, 'YYYY-MM')
         WHERE m.id_unidade = %s ORDER BY m.mes_referencia DESC
    """, (id_unidade,))
    return _linhas(cursor)


def buscar_falha_periodo(cursor, id_unidade, periodo):
    cursor.execute("""
        SELECT ultimo_erro, ultima_tentativa_em FROM chatbot.consumo_meta_coletas
         WHERE id_unidade = %s AND periodo = %s
    """, (id_unidade, periodo))
    return _linha(cursor)
