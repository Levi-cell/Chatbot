import logging

from core.logging_config import short_value
from core.repositories.inserts import inserir_dependente_para_conversa
from core.repositories.updates import (
    atualizar_nome_cliente_por_telefone,
    atualizar_nome_dependente_por_conversa,
    atualizar_status_dependente_conversa,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_nome import (
    validar_nome_cliente,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_DESTINO_ATENDIMENTO,
    ETAPA_IDADE_ALUNO,
    ETAPA_NOME_CLIENTE,
    ETAPA_NOME_DEPENDENTE,
    EVENTO_NOME_CLIENTE_VALIDO,
    EVENTO_NOME_DEPENDENTE_VALIDO,
    EVENTO_PARA_MIM,
    EVENTO_PARA_OUTRA_PESSOA,
)


logger = logging.getLogger("worker.support")


def atualizar_banco_conforme_transicao_de_etapa(
    contexto_historico,
    contexto_envio,
    cursor,
):
    """
    Aplica somente os efeitos de negócio da aresta já autorizada.

    A navegação é definida pelo mapa etapa_transicao e persistida antes desta
    função. Os ifs abaixo tornam explícito o efeito de cada origem + evento.
    """
    etapa_origem = contexto_historico.get(
        "id_etapa_origem_transicao"
    )
    evento = contexto_envio.get("evento_transicao")
    etapa_destino = contexto_envio.get("id_etapa_resultante")

    # Sem evento não existe transição nem efeito específico de etapa.
    if not evento:
        return None

    # Etapa 1 -> 2: o cliente informou o próprio nome.
    if (
        etapa_origem == ETAPA_NOME_CLIENTE
        and evento == EVENTO_NOME_CLIENTE_VALIDO
    ):
        _exigir_destino(
            etapa_origem,
            evento,
            etapa_destino,
            ETAPA_DESTINO_ATENDIMENTO,
        )
        return _persistir_nome_cliente_capturado_na_etapa1(
            contexto_historico,
            contexto_envio,
            cursor,
        )

    # Etapa 2 -> 4: o atendimento será para o próprio cliente.
    if (
        etapa_origem == ETAPA_DESTINO_ATENDIMENTO
        and evento == EVENTO_PARA_MIM
    ):
        _exigir_destino(
            etapa_origem,
            evento,
            etapa_destino,
            ETAPA_IDADE_ALUNO,
        )
        return _persistir_destino_atendimento_da_etapa2(
            contexto_historico,
            evento,
            etapa_destino,
            status_dependente=False,
            cursor=cursor,
        )

    # Etapa 2 -> 3: o atendimento será para um dependente.
    if (
        etapa_origem == ETAPA_DESTINO_ATENDIMENTO
        and evento == EVENTO_PARA_OUTRA_PESSOA
    ):
        _exigir_destino(
            etapa_origem,
            evento,
            etapa_destino,
            ETAPA_NOME_DEPENDENTE,
        )
        return _persistir_destino_atendimento_da_etapa2(
            contexto_historico,
            evento,
            etapa_destino,
            status_dependente=True,
            cursor=cursor,
        )

    # Etapa 3 -> 4: o cliente informou o nome do dependente.
    if (
        etapa_origem == ETAPA_NOME_DEPENDENTE
        and evento == EVENTO_NOME_DEPENDENTE_VALIDO
    ):
        _exigir_destino(
            etapa_origem,
            evento,
            etapa_destino,
            ETAPA_IDADE_ALUNO,
        )
        return _persistir_nome_dependente_capturado_na_etapa3(
            contexto_historico,
            contexto_envio,
            cursor,
        )

    raise ValueError(
        "Transicao sem efeitos conhecidos "
        f"(origem={etapa_origem}, evento={evento}, "
        f"destino={etapa_destino})"
    )


def _exigir_destino(
    etapa_origem,
    evento,
    etapa_destino,
    destino_esperado,
):
    if etapa_destino != destino_esperado:
        raise ValueError(
            "Efeito de transicao recebeu destino incompativel "
            f"(origem={etapa_origem}, evento={evento}, "
            f"destino={etapa_destino}, "
            f"destino_esperado={destino_esperado})"
        )


def _persistir_nome_cliente_capturado_na_etapa1(
    contexto_historico,
    contexto_envio,
    cursor,
):
    primeiro_nome = _resolver_primeiro_nome_capturado(
        contexto_historico,
        contexto_envio,
        "primeiro_nome_cliente",
    )

    if not primeiro_nome:
        print(
            "\n"
            "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n"
            "!!! NOME VAZIO NA TRANSICAO 1 -> 2: ANOMALIA RARA E CRITICA !!!\n"
            "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n"
        )
        logger.critical(
            "cliente_nome_anomalia_critica | motivo=nome_vazio_na_transicao_1_2 acao=rollback_e_retry id_conversa=%s etapa_origem=%s etapa_resultante=%s",
            contexto_historico["id_conversa"],
            contexto_historico.get("id_etapa_origem_transicao"),
            contexto_envio.get("id_etapa_resultante"),
        )
        raise ValueError(
            "Nome do cliente nao foi resolvido na transicao 1 -> 2"
        )

    mensagem_cliente = contexto_historico["mensagem_cliente_atual"]
    cliente_telefone = mensagem_cliente["cliente_telefone"]

    atualizar_nome_cliente_por_telefone(
        cliente_telefone,
        primeiro_nome,
        cursor,
    )

    logger.info(
        "cliente_nome_persistido | acao=salvar_nome evento=%s etapa_origem=%s etapa_resultante=%s id_conversa=%s cliente=%s",
        EVENTO_NOME_CLIENTE_VALIDO,
        contexto_historico.get("id_etapa_origem_transicao"),
        contexto_envio.get("id_etapa_resultante"),
        contexto_historico["id_conversa"],
        short_value(cliente_telefone),
    )

    return {
        "cliente_nome_atualizado": True,
        "primeiro_nome_cliente": primeiro_nome,
    }


def _persistir_destino_atendimento_da_etapa2(
    contexto_historico,
    evento,
    etapa_destino,
    *,
    status_dependente,
    cursor,
):
    id_conversa = contexto_historico["id_conversa"]

    atualizar_status_dependente_conversa(
        id_conversa,
        status_dependente,
        cursor,
    )

    contexto_persistido = {
        "status_dependente_atualizado": True,
        "status_dependente": status_dependente,
        "opcao_atendimento": evento,
        "dependente_criado": False,
    }

    if status_dependente:
        dependente = inserir_dependente_para_conversa(
            id_conversa,
            cursor,
        )
        contexto_persistido.update(
            {
                "dependente_criado": dependente["inserido"],
                "id_dependente": dependente["id_dependente"],
                "id_cliente_dependente": dependente["id_cliente"],
            }
        )

    logger.info(
        "destino_atendimento_persistido | acao=salvar_efeitos_transicao evento=%s etapa_origem=%s etapa_resultante=%s id_conversa=%s status_dependente=%s dependente_criado=%s",
        evento,
        contexto_historico.get("id_etapa_origem_transicao"),
        etapa_destino,
        id_conversa,
        status_dependente,
        contexto_persistido["dependente_criado"],
    )

    return contexto_persistido


def _persistir_nome_dependente_capturado_na_etapa3(
    contexto_historico,
    contexto_envio,
    cursor,
):
    primeiro_nome = _resolver_primeiro_nome_capturado(
        contexto_historico,
        contexto_envio,
        "primeiro_nome_dependente",
    )

    if not primeiro_nome:
        logger.critical(
            "dependente_nome_anomalia_critica | motivo=nome_vazio_na_transicao_3_4 acao=rollback_e_retry id_conversa=%s etapa_origem=%s etapa_resultante=%s",
            contexto_historico["id_conversa"],
            contexto_historico.get("id_etapa_origem_transicao"),
            contexto_envio.get("id_etapa_resultante"),
        )
        raise ValueError(
            "Nome do dependente nao foi resolvido na transicao 3 -> 4"
        )

    id_conversa = contexto_historico["id_conversa"]
    atualizar_nome_dependente_por_conversa(
        id_conversa,
        primeiro_nome,
        cursor,
    )

    logger.info(
        "dependente_nome_persistido | acao=salvar_nome evento=%s etapa_origem=%s etapa_resultante=%s id_conversa=%s",
        EVENTO_NOME_DEPENDENTE_VALIDO,
        contexto_historico.get("id_etapa_origem_transicao"),
        contexto_envio.get("id_etapa_resultante"),
        id_conversa,
    )

    return {
        "dependente_nome_atualizado": True,
        "primeiro_nome_dependente": primeiro_nome,
    }


def _resolver_primeiro_nome_capturado(
    contexto_historico,
    contexto_envio,
    chave_contexto,
):
    primeiro_nome = contexto_envio.get(chave_contexto)

    if primeiro_nome:
        return primeiro_nome

    resultado_nome = validar_nome_cliente(
        contexto_historico.get("texto_cliente_atual") or ""
    )

    if resultado_nome.valido:
        return resultado_nome.primeiro_nome

    return None
