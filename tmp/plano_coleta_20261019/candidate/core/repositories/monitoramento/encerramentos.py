"""Leituras de encerramentos por idade; nunca reclassifica ou grava histórico."""

from core.validacoes.encerramento_por_idade import MOTIVOS_IDADE
from .painel import _linhas, _periodo


def buscar_encerramentos_atuais(id_unidade, ids_conversas, cursor):
    """Só a última conversa real pode qualificar um chat do período selecionado.

    O histórico adicional é lido em lote. O hash de origem sobrevive à limpeza
    da fila; não depender de id_mensagem_fila nem do cadastro atual do dependente.
    """
    ids = sorted(set(ids_conversas))
    if not ids:
        return []
    motivos = sorted(MOTIVOS_IDADE)
    marcadores_ids = ', '.join(['%s'] * len(ids))
    marcadores_motivos = ', '.join(['%s'] * len(motivos))
    cursor.execute(f"""
        SELECT c.id_conversa, c.id_cliente, c.status_dependente,
               c.motivo_encerramento, c.finalizou_em,
               b.conteudo_texto AS resposta_bot, b.tipo_mensagem AS tipo_bot,
               h.conteudo_texto AS resposta_idade
          FROM chatbot.conversa c
          JOIN chatbot.historico_mensagens b ON b.id_mensagem = (
              SELECT b0.id_mensagem FROM chatbot.historico_mensagens b0
               WHERE b0.id_conversa = c.id_conversa AND b0.id_etapa = 6
                 AND b0.quem_enviou = 'bot' AND b0.status_envio = 'sent'
               ORDER BY b0.received_data_hora DESC, b0.id_mensagem DESC LIMIT 1
          )
          LEFT JOIN chatbot.historico_mensagens h ON h.id_mensagem = (
              SELECT h0.id_mensagem FROM chatbot.historico_mensagens h0
               WHERE h0.id_conversa = c.id_conversa AND h0.quem_enviou = 'cliente'
                 AND h0.id_hash_msg = b.id_hash_cliente_origem
               ORDER BY h0.id_mensagem DESC LIMIT 1
          )
         WHERE c.id_unidade = %s AND c.id_conversa IN ({marcadores_ids})
           AND c.status_ativa = FALSE AND c.id_etapa_atual = 6
           AND c.finalizou_em IS NOT NULL
           AND c.motivo_encerramento IN ({marcadores_motivos})
           AND NOT EXISTS (
               SELECT 1 FROM chatbot.conversa posterior
                WHERE posterior.id_unidade = c.id_unidade
                  AND posterior.id_cliente = c.id_cliente
                  AND posterior.id_conversa > c.id_conversa
           )
    """, tuple([id_unidade] + ids + motivos))
    return _linhas(cursor)


def contar_encerramentos_por_motivo(id_unidade, inicio, fim, cursor):
    """Conta conversas encerradas no período, sem deduplicar pelo cliente.

    Sem joins multiplicadores: cada conversa participa exatamente uma vez.
    O serviço filtra as categorias segundo a mesma configuração usada no rótulo.
    """
    parametros = [id_unidade]
    periodo = _periodo('c.finalizou_em', inicio, fim, parametros)
    motivos = sorted(MOTIVOS_IDADE)
    marcadores = ', '.join(['%s'] * len(motivos))
    cursor.execute(f"""
        SELECT c.motivo_encerramento, c.status_dependente, COUNT(*) AS conversas
          FROM chatbot.conversa c
         WHERE c.id_unidade = %s AND c.status_ativa = FALSE
           AND c.id_etapa_atual = 6 AND c.finalizou_em IS NOT NULL {periodo}
           AND c.motivo_encerramento IN ({marcadores})
         GROUP BY c.motivo_encerramento, c.status_dependente
    """, tuple(parametros + motivos))
    return _linhas(cursor)
