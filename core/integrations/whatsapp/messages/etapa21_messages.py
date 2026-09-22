"""Etapa 21: comentário livre; somente mídia precisa de orientação para texto."""

from core.integrations.whatsapp.messages.tratamentos.midia import (
    montar_mensagem_tratamento_midia,
)


### MENSAGEM COMPLETA PARA A ENTRADA NA ETAPA
MENSAGEM_PADRAO_ETAPA21 = (
    "Perfeito! 😊\n" "Deixe aqui abaixo seu comentário para melhorar nosso atendimento."
)

### REPETIÇÃO DA PERGUNTA, SEM REAPRESENTAR A ABERTURA
MENSAGEM_REPETICAO_ETAPA21 = (
    "Deixe aqui abaixo seu comentário para melhorar nosso atendimento."
)


def montar_mensagem_etapa21(*, repeticao=False):
    mensagem = MENSAGEM_REPETICAO_ETAPA21 if repeticao else MENSAGEM_PADRAO_ETAPA21
    return mensagem


### MÍDIA: ORIENTAÇÃO + REPETIÇÃO, SEM JULGAR O CONTEÚDO DO COMENTÁRIO
def montar_mensagem_midia_etapa21():
    return montar_mensagem_tratamento_midia(MENSAGEM_REPETICAO_ETAPA21)
