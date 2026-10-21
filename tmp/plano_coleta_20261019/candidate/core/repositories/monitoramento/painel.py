"""Consultas somente leitura do painel, sempre limitadas à unidade autorizada."""


def _linhas(cursor):
    colunas = [item[0] for item in cursor.description]
    return [dict(zip(colunas, linha)) for linha in cursor.fetchall()]


def _linha(cursor):
    colunas = [item[0] for item in cursor.description]
    valor = cursor.fetchone()
    return dict(zip(colunas, valor)) if valor else None


def _periodo(coluna, inicio, fim, parametros):
    trecho = f' AND {coluna} < %s'
    if inicio is not None:
        trecho = f' AND {coluna} >= %s' + trecho
        parametros.extend((inicio, fim))
    else:
        parametros.append(fim)
    return trecho


def buscar_unidade(id_unidade, cursor):
    cursor.execute("""
        SELECT u.id_unidade, u.nome_unidade, ac.nome_agente, ac.idade_minima_suporte,
               ac.email_obrigatorio, ac.bpa_ativo,
               MIN(CASE WHEN h.quem_enviou = 'cliente' THEN h.received_data_hora END) AS inicio_historico
          FROM chatbot.unidade u
          JOIN chatbot.atendimento_customizado ac ON ac.id_unidade = u.id_unidade
          LEFT JOIN chatbot.conversa c ON c.id_unidade = u.id_unidade
          LEFT JOIN chatbot.historico_mensagens h ON h.id_conversa = c.id_conversa
         WHERE u.id_unidade = %s
         GROUP BY u.id_unidade, u.nome_unidade, ac.nome_agente,
                  ac.idade_minima_suporte, ac.email_obrigatorio, ac.bpa_ativo
    """, (id_unidade,))
    return _linha(cursor)


def listar_conversas(id_unidade, inicio, fim, cursor):
    p_contato = [id_unidade]
    filtro_contato = _periodo('h0.received_data_hora', inicio, fim, p_contato)
    p_funil = []
    filtro_funil = _periodo('f.enviado_em', inicio, fim, p_funil)
    p_avaliacao = []
    filtro_avaliacao = _periodo('p.criado_em', inicio, fim, p_avaliacao)
    p_atividade = []
    filtro_atividade = _periodo('h.received_data_hora', inicio, fim, p_atividade)
    cursor.execute(f"""
        WITH conversas_periodo AS (
            SELECT c.*
              FROM chatbot.conversa c
             WHERE c.id_unidade = %s
               AND EXISTS (
                   SELECT 1 FROM chatbot.historico_mensagens h0
                    WHERE h0.id_conversa = c.id_conversa
                      AND h0.quem_enviou = 'cliente' {filtro_contato}
               )
        )
        SELECT c.id_cliente, c.id_conversa, c.status_dependente,
               c.id_etapa_atual, c.turno, cl.nome AS nome_cliente, cl.waid_telefone,
               cl.email, cl.idade AS idade_titular,
               cl.profissao AS profissao_cliente, c.profissao AS profissao_conversa,
               d.nome_dependente, d.idade AS idade_dependente,
               CASE WHEN c.followup_stage IN (1, 2) AND NOT EXISTS (
                   -- Considera atendimentos novos até fora do período selecionado.
                   SELECT 1 FROM chatbot.conversa posterior
                   WHERE posterior.id_cliente = c.id_cliente
                     AND posterior.id_unidade = c.id_unidade
                     AND posterior.id_conversa > c.id_conversa
               ) THEN c.followup_stage ELSE 0 END AS followup_stage_atual,
               EXISTS (SELECT 1 FROM chatbot.funil_envios f
                        WHERE f.id_conversa = c.id_conversa AND f.status = 'sent'
                        {filtro_funil}) AS foi_funil,
               EXISTS (SELECT 1 FROM chatbot.pesquisa_satisfacao p
                        WHERE p.id_conversa = c.id_conversa AND p.nota IS NOT NULL
                        {filtro_avaliacao}) AS avaliada,
               (SELECT h.received_data_hora FROM chatbot.historico_mensagens h
                 WHERE h.id_conversa = c.id_conversa {filtro_atividade}
                   AND (h.quem_enviou = 'cliente' OR (h.quem_enviou = 'bot' AND h.status_envio = 'sent'))
                 ORDER BY h.received_data_hora DESC, h.id_mensagem DESC LIMIT 1) AS ultima_atividade,
               (SELECT h.conteudo_texto FROM chatbot.historico_mensagens h
                 WHERE h.id_conversa = c.id_conversa {filtro_atividade}
                   AND (h.quem_enviou = 'cliente' OR (h.quem_enviou = 'bot' AND h.status_envio = 'sent'))
                 ORDER BY h.received_data_hora DESC, h.id_mensagem DESC LIMIT 1) AS ultima_mensagem,
               (SELECT h.id_mensagem FROM chatbot.historico_mensagens h
                 WHERE h.id_conversa = c.id_conversa {filtro_atividade}
                   AND (h.quem_enviou = 'cliente' OR (h.quem_enviou = 'bot' AND h.status_envio = 'sent'))
                 ORDER BY h.received_data_hora DESC, h.id_mensagem DESC LIMIT 1) AS ultima_mensagem_id
          FROM conversas_periodo c
          JOIN chatbot.cliente cl ON cl.id_cliente = c.id_cliente
          LEFT JOIN chatbot.dependente d ON d.id_conversa = c.id_conversa
         ORDER BY ultima_atividade DESC NULLS LAST, c.id_conversa DESC
    """, tuple(
        p_contato + p_funil + p_avaliacao
        + p_atividade + p_atividade + p_atividade
    ))
    return _linhas(cursor)


def buscar_mensagens(id_unidade, id_cliente, inicio, fim, cursor):
    parametros = [id_unidade, id_cliente]
    filtro = _periodo('h.received_data_hora', inicio, fim, parametros)
    cursor.execute(f"""
        SELECT h.id_mensagem, h.id_conversa, h.id_etapa,
               h.received_data_hora AS data, h.quem_enviou,
               h.tipo_mensagem AS tipo, h.conteudo_texto AS texto
          FROM chatbot.historico_mensagens h
          JOIN chatbot.conversa c ON c.id_conversa = h.id_conversa
         WHERE c.id_unidade = %s AND c.id_cliente = %s {filtro}
           AND (h.quem_enviou = 'cliente' OR (h.quem_enviou = 'bot' AND h.status_envio = 'sent'))
         ORDER BY h.received_data_hora, h.id_mensagem
    """, tuple(parametros))
    return _linhas(cursor)


def buscar_metricas(id_unidade, inicio, fim, cursor):
    parametros = [id_unidade]
    filtro = _periodo('h.received_data_hora', inicio, fim, parametros)
    p_msg = []
    f_msg = _periodo('h.received_data_hora', inicio, fim, p_msg)
    p_funil = []
    f_funil = _periodo('f.enviado_em', inicio, fim, p_funil)
    p_nota = []
    f_nota = _periodo('p.criado_em', inicio, fim, p_nota)
    cursor.execute(f"""
        WITH contatos AS (
          SELECT DISTINCT c.id_cliente
            FROM chatbot.conversa c JOIN chatbot.historico_mensagens h ON h.id_conversa=c.id_conversa
           WHERE c.id_unidade=%s AND h.quem_enviou='cliente' {filtro}
        )
        SELECT (SELECT COUNT(*) FROM contatos) AS leads,
               (SELECT COUNT(*) FROM chatbot.historico_mensagens h
                 JOIN chatbot.conversa c ON c.id_conversa=h.id_conversa
                WHERE c.id_unidade=%s AND c.id_cliente IN (SELECT id_cliente FROM contatos)
                  {f_msg} AND (h.quem_enviou='cliente' OR (h.quem_enviou='bot' AND h.status_envio='sent'))) AS mensagens,
               (SELECT COUNT(DISTINCT c.id_cliente) FROM chatbot.funil_envios f
                 JOIN chatbot.conversa c ON c.id_conversa=f.id_conversa
                WHERE c.id_unidade=%s AND c.id_cliente IN (SELECT id_cliente FROM contatos)
                  AND f.status='sent' {f_funil}) AS funil,
               (SELECT COUNT(DISTINCT c.id_cliente) FROM chatbot.pesquisa_satisfacao p
                 JOIN chatbot.conversa c ON c.id_conversa=p.id_conversa
                WHERE c.id_unidade=%s AND c.id_cliente IN (SELECT id_cliente FROM contatos)
                  AND p.nota IS NOT NULL {f_nota}) AS avaliacoes,
               (SELECT ROUND(AVG(p.nota)::numeric,2) FROM chatbot.pesquisa_satisfacao p
                 JOIN chatbot.conversa c ON c.id_conversa=p.id_conversa
                WHERE c.id_unidade=%s AND c.id_cliente IN (SELECT id_cliente FROM contatos)
                  AND p.nota IS NOT NULL {f_nota}) AS nota_media
    """, tuple(parametros + [id_unidade] + p_msg + [id_unidade] + p_funil + [id_unidade] + p_nota + [id_unidade] + p_nota))
    return _linha(cursor)


def contar_encaminhados_comercial_por_idade(id_unidade, inicio, fim, cursor):
    """Conta o fato concluído, pela data de encerramento, sem inferir pela idade."""
    parametros = [id_unidade]
    filtro = _periodo('c.finalizou_em', inicio, fim, parametros)
    cursor.execute(f"""
        SELECT COUNT(DISTINCT c.id_cliente)
          FROM chatbot.conversa c
         WHERE c.id_unidade = %s
           AND c.status_ativa = FALSE
           AND c.motivo_encerramento = 'encaminhado_suporte_idoso'
           AND c.finalizou_em IS NOT NULL {filtro}
    """, tuple(parametros))
    return int(cursor.fetchone()[0])


def buscar_perfis(id_unidade, inicio, fim, cursor):
    parametros = [id_unidade]
    filtro = _periodo('h.received_data_hora', inicio, fim, parametros)
    parametros_funil = []
    filtro_funil = _periodo('f.enviado_em', inicio, fim, parametros_funil)
    cursor.execute(f"""
        SELECT DISTINCT c.id_cliente, c.id_conversa, c.status_dependente,
               cl.idade AS idade_titular, d.idade AS idade_dependente,
               d.id_dependente, d.nome_dependente,
               EXISTS (SELECT 1 FROM chatbot.funil_envios f
                        WHERE f.id_conversa=c.id_conversa AND f.status='sent'
                        {filtro_funil}) AS foi_funil
          FROM chatbot.conversa c JOIN chatbot.cliente cl ON cl.id_cliente=c.id_cliente
          LEFT JOIN chatbot.dependente d ON d.id_conversa=c.id_conversa
         WHERE c.id_unidade=%s AND EXISTS (
               SELECT 1 FROM chatbot.historico_mensagens h
                WHERE h.id_conversa=c.id_conversa AND h.quem_enviou='cliente' {filtro})
    """, tuple(parametros_funil + parametros))
    return _linhas(cursor)


def buscar_satisfacao(id_unidade, inicio, fim, cursor):
    parametros = [id_unidade]
    filtro = _periodo('p.criado_em', inicio, fim, parametros)
    cursor.execute(f"""
        SELECT p.nota, COUNT(*) AS quantidade
          FROM chatbot.pesquisa_satisfacao p
          JOIN chatbot.conversa c ON c.id_conversa=p.id_conversa
         WHERE c.id_unidade=%s AND p.nota IS NOT NULL {filtro}
         GROUP BY p.nota ORDER BY p.nota
    """, tuple(parametros))
    return _linhas(cursor)


def buscar_etapas(id_unidade, inicio, fim, cursor):
    parametros = [id_unidade]
    filtro = _periodo('h.received_data_hora', inicio, fim, parametros)
    cursor.execute(f"""
        WITH conversas_periodo AS (
            SELECT c.id_cliente, c.id_conversa, c.id_etapa_atual,
                   MAX(h.received_data_hora) AS ultima_atividade
              FROM chatbot.conversa c
              JOIN chatbot.historico_mensagens h
                ON h.id_conversa = c.id_conversa
             WHERE c.id_unidade = %s AND h.quem_enviou = 'cliente' {filtro}
             GROUP BY c.id_cliente, c.id_conversa, c.id_etapa_atual
        ),
        ultimas_conversas AS (
            SELECT *, ROW_NUMBER() OVER (
                       PARTITION BY id_cliente
                       ORDER BY ultima_atividade DESC, id_conversa DESC
                   ) AS ordem
              FROM conversas_periodo
        )
        SELECT e.id_etapa, e.nome_etapa, COUNT(c.id_cliente) AS quantidade
          FROM chatbot.etapa e
          LEFT JOIN ultimas_conversas c
            ON c.id_etapa_atual = e.id_etapa AND c.ordem = 1
         WHERE e.id_etapa BETWEEN 1 AND 24
         GROUP BY e.id_etapa, e.nome_etapa ORDER BY e.id_etapa
    """, tuple(parametros))
    return _linhas(cursor)


def buscar_atividade(id_unidade, inicio, fim, cursor, granularidade):
    unidade_tempo = {'dia': 'day', 'semana': 'week', 'mes': 'month'}[granularidade]
    parametros = [id_unidade]
    filtro = _periodo('h.received_data_hora', inicio, fim, parametros)
    cursor.execute(f"""
        SELECT DATE_TRUNC('{unidade_tempo}', h.received_data_hora AT TIME ZONE 'America/Sao_Paulo') AS periodo,
               COUNT(*) FILTER (WHERE h.quem_enviou='cliente' OR (h.quem_enviou='bot' AND h.status_envio='sent')) AS mensagens,
               COUNT(DISTINCT c.id_cliente) FILTER (WHERE h.quem_enviou='cliente') AS leads
          FROM chatbot.historico_mensagens h JOIN chatbot.conversa c ON c.id_conversa=h.id_conversa
         WHERE c.id_unidade=%s {filtro}
         GROUP BY 1 ORDER BY 1
    """, tuple(parametros))
    return _linhas(cursor)


def listar_contatos(id_unidade, inicio, fim, cursor):
    parametros = [id_unidade]
    filtro = _periodo('h.received_data_hora', inicio, fim, parametros)
    cursor.execute(f"""
        SELECT cl.id_cliente, cl.nome, cl.email, cl.waid_telefone
          FROM chatbot.cliente cl
         WHERE EXISTS (
             SELECT 1 FROM chatbot.conversa c
             JOIN chatbot.historico_mensagens h ON h.id_conversa=c.id_conversa
              WHERE c.id_cliente=cl.id_cliente AND c.id_unidade=%s
                AND h.quem_enviou='cliente' {filtro})
         ORDER BY cl.nome NULLS LAST, cl.id_cliente
    """, tuple(parametros))
    return _linhas(cursor)
