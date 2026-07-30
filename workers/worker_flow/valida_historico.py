import logging

from core.logging_config import short_value
from core.repositories.atendimento.conversas import (
    atualizar_conversa_mensagem_cliente,
    atualizar_conversa_resposta_bot_sem_avancar,
)
from core.repositories.atendimento.historico import (
    buscar_resposta_bot_por_mensagem_cliente,
    inserir_historico_mensagem_cliente,
)
from core.repositories.fluxo.contextos.etapa1 import buscar_contexto_etapa1
from core.repositories.fluxo.contextos.etapa5 import buscar_contexto_etapa5
from core.repositories.fluxo.contextos.etapa6 import buscar_contexto_etapa6
from core.repositories.fluxo.contextos.etapa8 import buscar_contexto_etapa8
from core.repositories.fluxo.contextos.etapa17 import buscar_contexto_etapa17
from core.repositories.fluxo.contextos.triagem import buscar_contexto_triagem
from core.repositories.fluxo.transicoes import listar_transicoes_permitidas
from workers.worker_flow.response_flow.transicoes.contexto_transicao import (
    montar_contexto_transicao,
    prever_etapa_resposta,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_5_IDADE_ALUNO,
    ETAPA_6_OFERTA_AULA,
    ETAPA_7_OFERTA_ADIADA,
    ETAPA_8_RETORNO_OFERTA,
    ETAPA_10_INTRODUCAO_TRIAGEM,
    ETAPA_11_TRIAGEM_PERGUNTA_1,
    ETAPA_12_TRIAGEM_PERGUNTA_2,
    ETAPA_13_TRIAGEM_PERGUNTA_3,
    ETAPA_14_TRIAGEM_PERGUNTA_4,
    ETAPA_15_TRIAGEM_PERGUNTA_5,
    ETAPA_16_TRIAGEM_PERGUNTA_6,
    ETAPA_17_AGENDAMENTO,
)


logger = logging.getLogger("worker.valida_historico")

ETAPA_INICIAL = 1

ETAPAS_TRIAGEM = {
    ETAPA_10_INTRODUCAO_TRIAGEM,
    ETAPA_11_TRIAGEM_PERGUNTA_1,
    ETAPA_12_TRIAGEM_PERGUNTA_2,
    ETAPA_13_TRIAGEM_PERGUNTA_3,
    ETAPA_14_TRIAGEM_PERGUNTA_4,
    ETAPA_15_TRIAGEM_PERGUNTA_5,
    ETAPA_16_TRIAGEM_PERGUNTA_6,
}


def valida_historico(mensagem, contexto_banco, cursor):
    contexto_conversa = contexto_banco["conversa"]
    id_conversa = contexto_conversa["id_conversa"]

    last_message_from_entrada = contexto_conversa.get("last_message_from")
    id_etapa_para_insert = _resolver_etapa_cliente(contexto_conversa)

    (
        id_historico_cliente,
        data_historico_cliente,
        id_etapa_cliente,
        cliente_inserido_no_historico,
    ) = inserir_historico_mensagem_cliente(
        mensagem=mensagem,
        id_conversa=id_conversa,
        id_etapa=id_etapa_para_insert,
        cursor=cursor,
    )

    mensagem_cliente_atual = {
        "id_mensagem": id_historico_cliente,
        "id_conversa": id_conversa,
        "id_etapa": id_etapa_cliente,
        "received_data_hora": data_historico_cliente,
        "cliente_telefone": mensagem["cliente_telefone"],
        "conteudo_texto": mensagem["conteudo_texto"],
        "tipo_mensagem": mensagem["tipo_mensagem"],
        "id_hash_msg": mensagem["id_hash"],
        "id_mensagem_fila": mensagem["id_mensagem"],
        "id_hash_cliente_origem": None,
        "id_phone_unidade": mensagem["id_phone_unidade"],
        "unidade_telefone": mensagem["unidade_telefone"],
        "quem_enviou": "cliente",
        "status_envio": None,
    }

    resposta_bot_para_mensagem_atual = _normalizar_resposta_bot(
        buscar_resposta_bot_por_mensagem_cliente(
            id_conversa=id_conversa,
            id_mensagem_fila=mensagem["id_mensagem"],
            id_hash_cliente_origem=mensagem["id_hash"],
            cursor=cursor,
        )
    )

    transicoes_permitidas = listar_transicoes_permitidas(
        id_etapa_cliente,
        cursor,
    )
    contexto_transicao = montar_contexto_transicao(
        id_etapa_cliente,
        transicoes_permitidas,
    )
    contexto_especifico_etapa = {}

    # O nome da unidade vem do banco somente no primeiro contato. Respostas
    # posteriores da etapa 1 usam mensagens de tratamento sem nova saudacao.
    if contexto_conversa.get("id_etapa_atual") is None:
        contexto_especifico_etapa.update(
            buscar_contexto_etapa1(
                contexto_banco["id_unidade"],
                cursor,
            )
        )

    if id_etapa_cliente == ETAPA_5_IDADE_ALUNO:
        contexto_especifico_etapa = buscar_contexto_etapa5(
            id_conversa,
            contexto_banco["id_unidade"],
            cursor,
        )

        if (
            contexto_conversa.get("status_dependente")
            and not contexto_especifico_etapa["nome_dependente"]
        ):
            raise ValueError(
                "Etapa 5 de dependente sem nome persistido"
            )

        if (
            not contexto_conversa.get("status_dependente")
            and not contexto_especifico_etapa["nome_cliente"]
        ):
            raise ValueError(
                "Etapa 5 do cliente sem nome persistido"
            )

    if id_etapa_cliente == ETAPA_6_OFERTA_AULA:
        contexto_especifico_etapa = buscar_contexto_etapa6(
            id_conversa,
            contexto_banco["id_unidade"],
            cursor,
        )

        chave_nome = (
            "nome_dependente"
            if contexto_conversa.get("status_dependente")
            else "nome_cliente"
        )
        if not contexto_especifico_etapa[chave_nome]:
            raise ValueError(
                "Etapa 6 sem nome do aluno persistido "
                f"(campo={chave_nome})"
            )

    if id_etapa_cliente in {
        ETAPA_7_OFERTA_ADIADA,
        ETAPA_8_RETORNO_OFERTA,
    }:
        contexto_especifico_etapa = buscar_contexto_etapa8(
            id_conversa,
            contexto_banco["id_unidade"],
            cursor,
        )

        if not contexto_especifico_etapa["nome_cliente"]:
            raise ValueError(
                "Retorno da etapa 8 sem nome do cliente persistido "
                f"(etapa={id_etapa_cliente})"
            )

        if (
            contexto_conversa.get("status_dependente")
            and not contexto_especifico_etapa["nome_dependente"]
        ):
            raise ValueError(
                "Retorno de dependente sem nome persistido "
                f"(etapa={id_etapa_cliente})"
            )

    # As etapas 10-16 compartilham o nome do dependente. O dado sempre volta
    # do banco em cada ciclo para que retries reconstruam o contexto completo.
    if id_etapa_cliente in ETAPAS_TRIAGEM:
        contexto_especifico_etapa.update(
            buscar_contexto_triagem(
                id_conversa,
                contexto_banco["id_unidade"],
                cursor,
            )
        )

        if (
            contexto_conversa.get("status_dependente")
            and not contexto_especifico_etapa["nome_dependente"]
        ):
            raise ValueError(
                "Triagem de dependente sem nome persistido "
                f"(etapa={id_etapa_cliente}, id_conversa={id_conversa})"
            )

    # A resposta da pergunta 6 envia a etapa 17, e os tratamentos da própria
    # etapa 17 repetem a mensagem. Os dois ciclos precisam do link da unidade.
    if id_etapa_cliente in {
        ETAPA_16_TRIAGEM_PERGUNTA_6,
        ETAPA_17_AGENDAMENTO,
    }:
        contexto_especifico_etapa.update(
            buscar_contexto_etapa17(
                id_conversa,
                contexto_banco["id_unidade"],
                cursor,
            )
        )

    if resposta_bot_para_mensagem_atual:
        id_etapa_resposta = resposta_bot_para_mensagem_atual["id_etapa"]

        if last_message_from_entrada != "bot":
            atualizar_conversa_resposta_bot_sem_avancar(
                id_conversa,
                resposta_bot_para_mensagem_atual["received_data_hora"],
                cursor,
            )

        last_message_from_saida = "bot"
    else:
        id_etapa_resposta = prever_etapa_resposta(
            contexto_conversa.get("id_etapa_atual"),
            contexto_transicao["transicoes_permitidas"],
            etapa_inicial=ETAPA_INICIAL,
        )
        atualizar_conversa_mensagem_cliente(
            id_conversa,
            data_historico_cliente,
            cursor,
        )
        last_message_from_saida = "cliente"

    logger.info(
        "historico_validado | acao=registrar_cliente id_mensagem=%s id_historico=%s inserido=%s id_conversa=%s etapa_cliente=%s etapa_resposta_previa=%s eventos_transicao=%s last_from_entrada=%s last_from_saida=%s retry=%s resposta_bot_existente=%s cliente=%s phone_number_id=%s",
        mensagem["id_mensagem"],
        id_historico_cliente,
        cliente_inserido_no_historico,
        id_conversa,
        id_etapa_cliente,
        id_etapa_resposta,
        sorted(transicoes_permitidas),
        last_message_from_entrada,
        last_message_from_saida,
        mensagem["retry_count"],
        bool(resposta_bot_para_mensagem_atual),
        short_value(mensagem["cliente_telefone"]),
        short_value(mensagem["id_phone_unidade"]),
    )

    contexto_historico = {
        "id_conversa": id_conversa,
        "id_cliente": contexto_banco.get("id_cliente"),
        "id_unidade": contexto_banco.get("id_unidade"),
        "id_etapa_atual": contexto_conversa.get("id_etapa_atual"),
        "id_etapa_cliente": id_etapa_cliente,
        # Compatibilidade apenas para logs existentes. Este campo nunca decide
        # uma transição e pode ser None quando há mais de um destino.
        "id_etapa_resposta": id_etapa_resposta,
        "id_etapa_origem_transicao": contexto_transicao[
            "id_etapa_origem_transicao"
        ],
        "transicoes_permitidas": contexto_transicao[
            "transicoes_permitidas"
        ],
        "status_dependente": contexto_conversa.get("status_dependente"),
        "last_message_from": last_message_from_saida,
        "last_message_from_entrada": last_message_from_entrada,
        "mensagem_cliente_atual": mensagem_cliente_atual,
        "mensagem_cliente_inserida": cliente_inserido_no_historico,
        "resposta_bot_para_mensagem_atual": resposta_bot_para_mensagem_atual,
        "texto_cliente_atual": mensagem["conteudo_texto"],
        "tipo_mensagem_atual": mensagem["tipo_mensagem"],
        "retry_count": mensagem["retry_count"],
        "precisa_tratamento_erro": False,
        "motivo_tratamento_erro": None,
    }
    contexto_historico.update(contexto_especifico_etapa)
    return contexto_historico


def _resolver_etapa_cliente(contexto_conversa):
    id_etapa_atual = contexto_conversa.get("id_etapa_atual")

    if id_etapa_atual is None:
        return ETAPA_INICIAL

    return id_etapa_atual


def _normalizar_linha_historico(registro):
    (
        id_mensagem,
        id_conversa,
        id_etapa,
        received_data_hora,
        cliente_telefone,
        conteudo_texto,
        tipo_mensagem,
        id_hash_msg,
        id_mensagem_fila,
        id_hash_cliente_origem,
        id_phone_unidade,
        unidade_telefone,
        quem_enviou,
        status_envio,
    ) = registro

    return {
        "id_mensagem": id_mensagem,
        "id_conversa": id_conversa,
        "id_etapa": id_etapa,
        "received_data_hora": received_data_hora,
        "cliente_telefone": cliente_telefone,
        "conteudo_texto": conteudo_texto,
        "tipo_mensagem": tipo_mensagem,
        "id_hash_msg": id_hash_msg,
        "id_mensagem_fila": id_mensagem_fila,
        "id_hash_cliente_origem": id_hash_cliente_origem,
        "id_phone_unidade": id_phone_unidade,
        "unidade_telefone": unidade_telefone,
        "quem_enviou": quem_enviou,
        "status_envio": status_envio,
    }


def _normalizar_resposta_bot(registro):
    if not registro:
        return None

    return _normalizar_linha_historico(registro)
