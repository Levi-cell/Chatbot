"""SQL de agenda, cadastro de fuso e totais mensais, sem chamadas externas."""

def _linhas(cursor):
    colunas = [item[0] for item in cursor.description]
    return [dict(zip(colunas, linha)) for linha in cursor.fetchall()]


def _linha(cursor):
    colunas = [item[0] for item in cursor.description]
    linha = cursor.fetchone()
    return dict(zip(colunas, linha)) if linha else None


def listar_unidades(cursor):
    cursor.execute("""
        SELECT id_unidade, nome_unidade, waba_id, phone_number_id, id_fuso, nome_fuso
          FROM chatbot.unidade
         WHERE waba_id IS NOT NULL AND phone_number_id IS NOT NULL
         ORDER BY id_unidade
    """)
    return _linhas(cursor)


def sincronizar_fuso(cursor, id_unidade, conta, verificado_em):
    cursor.execute("""
        UPDATE chatbot.unidade
           SET id_fuso = %s, nome_fuso = %s, fuso_verificado_em = %s
         WHERE id_unidade = %s AND waba_id = %s
           AND (fuso_verificado_em IS NULL OR fuso_verificado_em <= %s)
    """, (int(conta["timezone_id"]), conta["fuso_horario"], verificado_em,
          id_unidade, conta["waba_id"], verificado_em))
    if cursor.rowcount != 1:
        raise ValueError("Cadastro da unidade mudou durante a consulta do fuso.")


def listar_registros(cursor, id_unidade):
    cursor.execute("""
        SELECT * FROM chatbot.consumo_mensal_meta
         WHERE id_unidade = %s ORDER BY mes_referencia DESC
    """, (id_unidade,))
    return _linhas(cursor)


def listar_agenda(cursor, id_unidade):
    cursor.execute("SELECT * FROM chatbot.consumo_meta_coletas WHERE id_unidade = %s", (id_unidade,))
    return {linha["periodo"]: linha for linha in _linhas(cursor)}


def agendar(cursor, id_unidade, periodo, tentativa, proxima, erro=None):
    cursor.execute("""
        INSERT INTO chatbot.consumo_meta_coletas
            (id_unidade, periodo, ultima_tentativa_em, proxima_consulta_em, ultimo_erro, falhas_consecutivas)
        VALUES (%s,%s,%s,%s,%s,%s)
        ON CONFLICT (id_unidade, periodo) DO UPDATE
          SET ultima_tentativa_em = EXCLUDED.ultima_tentativa_em,
              proxima_consulta_em = EXCLUDED.proxima_consulta_em,
              ultimo_erro = EXCLUDED.ultimo_erro,
              falhas_consecutivas = CASE WHEN EXCLUDED.ultimo_erro IS NULL THEN 0
                  ELSE chatbot.consumo_meta_coletas.falhas_consecutivas + 1 END
        WHERE chatbot.consumo_meta_coletas.ultima_tentativa_em IS NULL
           OR chatbot.consumo_meta_coletas.ultima_tentativa_em <= EXCLUDED.ultima_tentativa_em
    """, (id_unidade, periodo, tentativa, proxima, erro, int(erro is not None)))


def buscar_para_atualizar(cursor, id_unidade, mes):
    cursor.execute("""
        SELECT * FROM chatbot.consumo_mensal_meta
         WHERE id_unidade = %s AND mes_referencia = %s FOR UPDATE
    """, (id_unidade, mes))
    return _linha(cursor)


def conferir_cadastro_coletado(cursor, id_unidade, resultado):
    """Uma edição durante o HTTP não pode atribuir o número antigo ao mês novo.

    O lock existe só nesta transação curta, depois da resposta da Meta. Impede
    edição do cadastro entre a comparação e a gravação dos totais.
    """
    cursor.execute("""
        SELECT waba_id, phone_number_id, id_fuso, nome_fuso
          FROM chatbot.unidade WHERE id_unidade = %s FOR SHARE
    """, (id_unidade,))
    unidade = _linha(cursor)
    identidade = (str(resultado["waba_id"]), str(resultado["numeros"][0]["phone_number_id"]))
    if not unidade or (str(unidade["waba_id"]), str(unidade["phone_number_id"])) != identidade:
        raise ValueError("Conta ou número da unidade mudou durante a coleta; tente no próximo ciclo.")
    if unidade["id_fuso"] is not None and (
        unidade["id_fuso"] != int(resultado["timezone_id"])
        or unidade["nome_fuso"] != resultado["fuso_horario"]
    ):
        raise ValueError("Fuso da unidade mudou durante a coleta; tente no próximo ciclo.")


def salvar_registro(cursor, valores):
    colunas = (
        "id_unidade", "mes_referencia", "waba_id", "phone_number_id", "timezone_id",
        "fuso_horario", "data_hora_inicio", "data_hora_fim", "qtd_janela_gratuita",
        "qtd_franquia_consumida", "qtd_cobradas_meta", "consultado_ate", "ultimo_sucesso_em",
        "status_apuracao", "data_proxima_consolidacao", "consolidado_em", "ultima_decisao_consolidacao_em",
    )
    # Nomes são constantes internas; todos os valores externos usam parâmetros.
    mutaveis = colunas[8:]
    atualizacoes = ", ".join(f"{coluna} = EXCLUDED.{coluna}" for coluna in mutaveis)
    cursor.execute(f"""
        INSERT INTO chatbot.consumo_mensal_meta ({', '.join(colunas)})
        VALUES ({', '.join(['%s'] * len(colunas))})
        ON CONFLICT (id_unidade, mes_referencia) DO UPDATE
          SET {atualizacoes}, atualizado_em = NOW()
        WHERE chatbot.consumo_mensal_meta.ultimo_sucesso_em < EXCLUDED.ultimo_sucesso_em
          AND chatbot.consumo_mensal_meta.status_apuracao <> 'consolidado'
        RETURNING id_registro
    """, tuple(valores[coluna] for coluna in colunas))
    return cursor.fetchone() is not None


def atualizar_pendencia(cursor, registro, estado, prazo, decisao_em):
    cursor.execute("""
        UPDATE chatbot.consumo_mensal_meta
           SET status_apuracao=%s, data_proxima_consolidacao=%s,
               ultima_decisao_consolidacao_em=%s, atualizado_em=NOW()
         WHERE id_registro=%s AND status_apuracao <> 'consolidado'
    """, (estado, prazo, decisao_em, registro["id_registro"]))
