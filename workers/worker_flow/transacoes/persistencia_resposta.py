import logging

from core.logging_config import short_value
from core.repositories.inserts import (
    inserir_dependente_para_conversa,
    inserir_historico_mensagem_bot,
)
from core.repositories.updates import (
    atualizar_conversa_resposta_bot,
    atualizar_conversa_resposta_bot_sem_avancar,
    atualizar_nome_cliente_por_telefone,
    atualizar_status_dependente_conversa,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_segunda_etapa import (
    OPCAO_PARA_MIM,
    OPCAO_PARA_OUTRA_PESSOA,
    validar_segunda_etapa,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_nome import (
    validar_nome_cliente,
)


logger = logging.getLogger("worker.support")

ETAPA_1_CAPTURA_NOME = 1
ETAPA_2_DESTINO_ATENDIMENTO = 2
ETAPA_3_DADOS_ALUNO = 3


def _obter_data_interacao_bot_existente(contexto_historico):
    resposta_bot = (
        contexto_historico.get("resposta_bot_para_mensagem_atual") or {}
    )
    data_interacao = resposta_bot.get("received_data_hora")

    if data_interacao is None:
        raise ValueError(
            "Resposta do bot existente sem received_data_hora persistido"
        )

    return data_interacao


def atualizar_banco_com_contexto_final(contexto_historico, contexto_envio, cursor):
    id_conversa = contexto_historico["id_conversa"]
    id_etapa_resultante = contexto_envio.get("id_etapa_resultante")
    atualizar_conversa = contexto_envio.get("atualizar_conversa", True)
    atualizar_last_from_bot = contexto_envio.get("atualizar_last_from_bot", True)

    if contexto_envio.get("resposta_ja_existia"):
        data_interacao_bot = None
        if atualizar_conversa or atualizar_last_from_bot:
            data_interacao_bot = _obter_data_interacao_bot_existente(
                contexto_historico
            )

        if atualizar_conversa:
            atualizar_conversa_resposta_bot(
                id_conversa,
                id_etapa_resultante,
                data_interacao_bot,
                cursor,
            )
        elif atualizar_last_from_bot:
            atualizar_conversa_resposta_bot_sem_avancar(
                id_conversa,
                data_interacao_bot,
                cursor,
            )

        atualizar_banco_conforme_transicao_de_etapa(
            contexto_historico,
            contexto_envio,
            cursor,
        )

        logger.info(
            "resposta_bot_idempotente | motivo=resposta_ja_existia acao=atualizar_contexto id_conversa=%s etapa=%s id_hash_msg_bot=%s atualizar_conversa=%s atualizar_last_from_bot=%s",
            id_conversa,
            id_etapa_resultante,
            contexto_envio.get("id_hash_msg_bot"),
            atualizar_conversa,
            atualizar_last_from_bot,
        )
        return {
            "historico_bot_inserido": False,
            "resposta_ja_existia": True,
            "id_hash_msg_bot": contexto_envio.get("id_hash_msg_bot"),
            "id_etapa_resultante": id_etapa_resultante,
            "atualizar_conversa": atualizar_conversa,
            "atualizar_last_from_bot": atualizar_last_from_bot,
        }

    if not contexto_envio.get("enviou"):
        raise ValueError(
            "Contexto de envio sem resposta enviada e sem resposta existente"
        )

    id_historico_bot, data_historico_bot, historico_inserido = (
        inserir_historico_mensagem_bot(
            contexto_historico,
            contexto_envio,
            cursor,
        )
    )

    if atualizar_conversa:
        atualizar_conversa_resposta_bot(
            id_conversa,
            id_etapa_resultante,
            data_historico_bot,
            cursor,
        )
    elif atualizar_last_from_bot:
        atualizar_conversa_resposta_bot_sem_avancar(
            id_conversa,
            data_historico_bot,
            cursor,
        )

    atualizar_banco_conforme_transicao_de_etapa(
        contexto_historico,
        contexto_envio,
        cursor,
    )

    logger.info(
        "resposta_bot_persistida | acao=registrar_historico_e_contexto id_conversa=%s id_historico_bot=%s inserido=%s etapa=%s id_hash_msg_bot=%s atualizar_conversa=%s atualizar_last_from_bot=%s",
        id_conversa,
        id_historico_bot,
        historico_inserido,
        id_etapa_resultante,
        contexto_envio.get("id_hash_msg_bot"),
        atualizar_conversa,
        atualizar_last_from_bot,
    )

    return {
        "historico_bot_inserido": historico_inserido,
        "resposta_ja_existia": False,
        "id_historico_bot": id_historico_bot,
        "data_historico_bot": data_historico_bot,
        "id_hash_msg_bot": contexto_envio.get("id_hash_msg_bot"),
        "id_etapa_resultante": id_etapa_resultante,
        "atualizar_conversa": atualizar_conversa,
        "atualizar_last_from_bot": atualizar_last_from_bot,
    }


def atualizar_banco_conforme_transicao_de_etapa(
    contexto_historico,
    contexto_envio,
    cursor,
):
    # A etapa atual e anterior a resposta; a etapa resultante e seu destino.
    # Assim, o nome so e persistido na ponte entre as etapas 1 e 2.
    etapa_origem = contexto_historico.get("id_etapa_atual")
    etapa_destino = contexto_envio.get("id_etapa_resultante")

    if _esta_na_ponte_etapa_1_para_etapa_2(
        etapa_origem,
        etapa_destino,
        contexto_envio,
    ):
        return _persistir_nome_cliente_capturado_na_etapa_1(
            contexto_historico,
            contexto_envio,
            cursor,
        )

    if _esta_na_ponte_etapa_2_para_etapa_3(
        etapa_origem,
        etapa_destino,
        contexto_envio,
    ):
        return _persistir_destino_atendimento_da_etapa_2(
            contexto_historico,
            contexto_envio,
            cursor,
        )

    return None


def _esta_na_ponte_etapa_1_para_etapa_2(
    etapa_origem,
    etapa_destino,
    contexto_envio,
):
    return (
        etapa_origem == ETAPA_1_CAPTURA_NOME
        and etapa_destino == ETAPA_2_DESTINO_ATENDIMENTO
        and not contexto_envio.get("tratamento")
    )


def _persistir_nome_cliente_capturado_na_etapa_1(
    contexto_historico,
    contexto_envio,
    cursor,
):
    primeiro_nome = _resolver_primeiro_nome_cliente(
        contexto_historico,
        contexto_envio,
    )

    if not primeiro_nome:
        print(
            "\n"
            "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n"
            "!!! NOME VAZIO NA TRANSICAO 1 -> 2: ANOMALIA RARA E CRITICA !!!\n"
            "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n"
        )
        logger.critical(
            "cliente_nome_anomalia_critica | motivo=nome_vazio_na_transicao_1_2 acao=rollback_e_retry id_conversa=%s etapa_atual=%s etapa_resultante=%s",
            contexto_historico["id_conversa"],
            contexto_historico.get("id_etapa_atual"),
            contexto_envio.get("id_etapa_resultante"),
        )
        raise ValueError("Nome do cliente nao foi resolvido na transicao 1 -> 2")

    mensagem_cliente = contexto_historico["mensagem_cliente_atual"]
    cliente_telefone = mensagem_cliente["cliente_telefone"]

    atualizar_nome_cliente_por_telefone(
        cliente_telefone,
        primeiro_nome,
        cursor,
    )

    logger.info(
        "cliente_nome_persistido | acao=salvar_nome etapa_origem=%s etapa_resultante=%s id_conversa=%s cliente=%s",
        contexto_historico.get("id_etapa_atual"),
        contexto_envio.get("id_etapa_resultante"),
        contexto_historico["id_conversa"],
        short_value(cliente_telefone),
    )

    return {
        "cliente_nome_atualizado": True,
        "primeiro_nome_cliente": primeiro_nome,
    }


def _esta_na_ponte_etapa_2_para_etapa_3(
    etapa_origem,
    etapa_destino,
    contexto_envio,
):
    return (
        etapa_origem == ETAPA_2_DESTINO_ATENDIMENTO
        and etapa_destino == ETAPA_3_DADOS_ALUNO
        and not contexto_envio.get("tratamento")
    )


def _persistir_destino_atendimento_da_etapa_2(
    contexto_historico,
    contexto_envio,
    cursor,
):
    opcao_atendimento = _resolver_opcao_atendimento(
        contexto_historico,
        contexto_envio,
    )

    if opcao_atendimento not in {
        OPCAO_PARA_MIM,
        OPCAO_PARA_OUTRA_PESSOA,
    }:
        logger.critical(
            "destino_atendimento_anomalia_critica | motivo=opcao_invalida_na_transicao_2_3 acao=rollback_e_retry id_conversa=%s etapa_atual=%s etapa_resultante=%s",
            contexto_historico["id_conversa"],
            contexto_historico.get("id_etapa_atual"),
            contexto_envio.get("id_etapa_resultante"),
        )
        raise ValueError(
            "Opcao de atendimento nao foi resolvida na transicao 2 -> 3"
        )

    id_conversa = contexto_historico["id_conversa"]
    status_dependente = (
        opcao_atendimento == OPCAO_PARA_OUTRA_PESSOA
    )

    atualizar_status_dependente_conversa(
        id_conversa,
        status_dependente,
        cursor,
    )

    contexto_persistido = {
        "status_dependente_atualizado": True,
        "status_dependente": status_dependente,
        "opcao_atendimento": opcao_atendimento,
        "dependente_criado": False,
    }

    if status_dependente:
        dependente = inserir_dependente_para_conversa(
            id_conversa,
            cursor,
        )
        contexto_persistido.update({
            "dependente_criado": dependente["inserido"],
            "id_dependente": dependente["id_dependente"],
            "id_cliente_dependente": dependente["id_cliente"],
        })

    logger.info(
        "destino_atendimento_persistido | acao=salvar_transicao etapa_origem=%s etapa_resultante=%s id_conversa=%s opcao_atendimento=%s status_dependente=%s dependente_criado=%s",
        contexto_historico.get("id_etapa_atual"),
        contexto_envio.get("id_etapa_resultante"),
        id_conversa,
        opcao_atendimento,
        status_dependente,
        contexto_persistido["dependente_criado"],
    )

    return contexto_persistido


def _resolver_opcao_atendimento(contexto_historico, contexto_envio):
    opcao_atendimento = contexto_envio.get("opcao_atendimento")

    if opcao_atendimento:
        return opcao_atendimento

    return validar_segunda_etapa(
        contexto_historico.get("texto_cliente_atual") or ""
    )


def _resolver_primeiro_nome_cliente(contexto_historico, contexto_envio):
    primeiro_nome = contexto_envio.get("primeiro_nome_cliente")

    if primeiro_nome:
        return primeiro_nome

    resultado_nome = validar_nome_cliente(
        contexto_historico.get("texto_cliente_atual") or ""
    )

    if resultado_nome.valido:
        return resultado_nome.primeiro_nome

    return None
