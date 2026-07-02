from core.repositories.updates import (
    atualizar_conversa_por_transicao,
    atualizar_conversa_resposta_bot_sem_avancar,
    inicializar_conversa_resposta_bot,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_1_NOME_CLIENTE,
)


MOVIMENTO_INICIALIZACAO = "inicializacao"
MOVIMENTO_TRANSICAO = "transicao"
MOVIMENTO_SEM_AVANCO = "sem_avanco"


def persistir_movimento_conversa(
    contexto_historico,
    contexto_envio,
    data_interacao_bot,
    cursor,
):
    movimento = resolver_movimento_conversa(
        contexto_historico,
        contexto_envio,
    )
    id_conversa = contexto_historico["id_conversa"]
    id_etapa_destino = contexto_envio.get("id_etapa_resultante")

    if movimento == MOVIMENTO_INICIALIZACAO:
        inicializar_conversa_resposta_bot(
            id_conversa,
            id_etapa_destino,
            data_interacao_bot,
            cursor,
        )
        return movimento

    if movimento == MOVIMENTO_TRANSICAO:
        atualizar_conversa_por_transicao(
            id_conversa,
            contexto_historico["id_etapa_origem_transicao"],
            contexto_envio["evento_transicao"],
            id_etapa_destino,
            data_interacao_bot,
            cursor,
            permitir_reaplicacao=bool(
                contexto_envio.get("resposta_ja_existia")
            ),
        )
        return movimento

    atualizar_conversa_resposta_bot_sem_avancar(
        id_conversa,
        data_interacao_bot,
        cursor,
    )
    return movimento


def resolver_movimento_conversa(
    contexto_historico,
    contexto_envio,
):
    etapa_atual = contexto_historico.get("id_etapa_atual")
    etapa_origem = contexto_historico.get(
        "id_etapa_origem_transicao"
    )
    etapa_destino = contexto_envio.get("id_etapa_resultante")
    evento_transicao = contexto_envio.get("evento_transicao")
    tratamento = bool(contexto_envio.get("tratamento"))

    if etapa_destino is None:
        raise ValueError("Resposta do bot sem id_etapa_resultante")

    # Primeiro contato: apenas apresenta a etapa 1, sem transição.
    if etapa_atual is None:
        if etapa_destino != ETAPA_1_NOME_CLIENTE:
            raise ValueError(
                "Conversa sem etapa so pode ser inicializada na etapa 1"
            )

        if evento_transicao:
            raise ValueError(
                "Inicializacao da conversa nao aceita evento de transicao"
            )

        return MOVIMENTO_INICIALIZACAO

    # Uma resposta válida produz evento e pode mudar de etapa.
    if evento_transicao:
        if tratamento:
            raise ValueError(
                "Tratamento nao pode avancar por evento de transicao"
            )

        if etapa_origem is None:
            raise ValueError(
                "Evento de transicao sem etapa de origem persistida"
            )

        return MOVIMENTO_TRANSICAO

    # Tratamentos não produzem evento e obrigatoriamente permanecem na origem.
    if etapa_destino != etapa_origem:
        raise ValueError(
            "Resposta sem evento tentou alterar a etapa da conversa "
            f"(origem={etapa_origem}, destino={etapa_destino})"
        )

    return MOVIMENTO_SEM_AVANCO
