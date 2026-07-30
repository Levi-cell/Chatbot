import logging

from core.logging_config import short_value
from core.repositories.atendimento.clientes import (
    atualizar_email_cliente,
    atualizar_idade_cliente,
    atualizar_nome_cliente_por_telefone,
)
from core.repositories.atendimento.conversas import (
    atualizar_profissao_conversa,
    atualizar_status_dependente_conversa,
)
from core.repositories.atendimento.dependentes import (
    atualizar_idade_dependente,
    atualizar_nome_dependente_por_conversa,
    inserir_dependente_para_conversa,
)
from core.repositories.fluxo.triagem import registrar_resposta_triagem
from core.repositories.fluxo.pesquisa_satisfacao import (
    salvar_comentario_satisfacao,
    salvar_nota_satisfacao,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa18 import (
    validar_etapa18,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa19 import (
    normalizar_comentario_etapa19,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_nome import (
    validar_nome_cliente,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_triagem import (
    validar_resposta_triagem,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa5 import (
    validar_idade,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa2 import (
    OPCAO_PARA_OUTRA_PESSOA,
    validar_etapa2,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa3 import (
    validar_profissao_etapa3,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa9 import (
    validar_etapa9,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_1_NOME_CLIENTE,
    ETAPA_2_DESTINO_ATENDIMENTO,
    ETAPA_3_PROFISSAO,
    ETAPA_4_NOME_DEPENDENTE,
    ETAPA_5_IDADE_ALUNO,
    ETAPA_6_OFERTA_AULA,
    ETAPA_7_OFERTA_ADIADA,
    ETAPA_8_RETORNO_OFERTA,
    ETAPA_9_EMAIL,
    ETAPA_10_INTRODUCAO_TRIAGEM,
    ETAPA_11_TRIAGEM_PERGUNTA_1,
    ETAPA_12_TRIAGEM_PERGUNTA_2,
    ETAPA_13_TRIAGEM_PERGUNTA_3,
    ETAPA_14_TRIAGEM_PERGUNTA_4,
    ETAPA_15_TRIAGEM_PERGUNTA_5,
    ETAPA_16_TRIAGEM_PERGUNTA_6,
    ETAPA_17_AGENDAMENTO,
    ETAPA_18_PESQUISA_SATISFACAO,
    ETAPA_19_COMENTARIO_SATISFACAO,
    ETAPA_20_FINALIZACAO,
    EVENTO_AGENDAMENTO_CONFIRMADO,
    EVENTO_CLIENTE_RETORNOU,
    EVENTO_COMENTARIO_SATISFACAO_RECEBIDO,
    EVENTO_DESTINO_ATENDIMENTO_DEFINIDO,
    EVENTO_EMAIL_VALIDO,
    EVENTO_IDADE_VALIDA,
    EVENTO_NOME_CLIENTE_VALIDO,
    EVENTO_NOME_DEPENDENTE_VALIDO,
    EVENTO_OFERTA_ACEITA,
    EVENTO_OFERTA_ADIADA,
    EVENTO_PROFISSAO_DEPENDENTE_VALIDA,
    EVENTO_PROFISSAO_TITULAR_VALIDA,
    EVENTO_RETORNO_ADIADO,
    EVENTO_RETORNO_CONFIRMADO,
    EVENTO_SATISFACAO_AVALIADA,
    EVENTO_TRIAGEM_INICIADA,
    EVENTO_TRIAGEM_PERGUNTA_1_RESPONDIDA,
    EVENTO_TRIAGEM_PERGUNTA_2_RESPONDIDA,
    EVENTO_TRIAGEM_PERGUNTA_3_RESPONDIDA,
    EVENTO_TRIAGEM_PERGUNTA_4_RESPONDIDA,
    EVENTO_TRIAGEM_PERGUNTA_5_RESPONDIDA,
    EVENTO_TRIAGEM_PERGUNTA_6_RESPONDIDA,
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

    # ETAPA 1
    if etapa_origem == ETAPA_1_NOME_CLIENTE:
        # 1 -> 2: o cliente informou o próprio nome.
        if evento == EVENTO_NOME_CLIENTE_VALIDO:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_2_DESTINO_ATENDIMENTO,
            )
            return _persistir_nome_cliente_capturado_na_etapa1(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    # ETAPA 2
    if etapa_origem == ETAPA_2_DESTINO_ATENDIMENTO:
        # 2 -> 3: a opção foi validada; a profissão vem antes da bifurcação.
        if evento == EVENTO_DESTINO_ATENDIMENTO_DEFINIDO:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_3_PROFISSAO,
            )
            return _persistir_destino_atendimento_da_etapa2(
                contexto_historico,
                contexto_envio,
                etapa_destino,
                cursor=cursor,
            )

    # ETAPA 3
    if etapa_origem == ETAPA_3_PROFISSAO:
        if evento == EVENTO_PROFISSAO_DEPENDENTE_VALIDA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_4_NOME_DEPENDENTE,
            )
            return _persistir_profissao_capturada_na_etapa3(
                contexto_historico,
                contexto_envio,
                cursor,
                status_dependente_esperado=True,
            )

        if evento == EVENTO_PROFISSAO_TITULAR_VALIDA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_5_IDADE_ALUNO,
            )
            return _persistir_profissao_capturada_na_etapa3(
                contexto_historico,
                contexto_envio,
                cursor,
                status_dependente_esperado=False,
            )

    # ETAPA 4
    if etapa_origem == ETAPA_4_NOME_DEPENDENTE:
        # 4 -> 5: o cliente informou o nome do dependente.
        if evento == EVENTO_NOME_DEPENDENTE_VALIDO:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_5_IDADE_ALUNO,
            )
            return _persistir_nome_dependente_capturado_na_etapa4(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    # ETAPA 5
    if etapa_origem == ETAPA_5_IDADE_ALUNO:
        # 5 -> 6: a idade do aluno foi validada.
        if evento == EVENTO_IDADE_VALIDA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_6_OFERTA_AULA,
            )
            return _persistir_idade_capturada_na_etapa5(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    # ETAPA 6
    if etapa_origem == ETAPA_6_OFERTA_AULA:
        # 6 -> 9: o cliente aceitou agendar.
        if evento == EVENTO_OFERTA_ACEITA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_9_EMAIL,
            )
            return _confirmar_decisao_oferta_da_etapa6(
                contexto_historico,
                evento,
                etapa_destino,
            )

        # 6 -> 7: o cliente preferiu adiar.
        if evento == EVENTO_OFERTA_ADIADA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_7_OFERTA_ADIADA,
            )
            return _confirmar_decisao_oferta_da_etapa6(
                contexto_historico,
                evento,
                etapa_destino,
            )

    # ETAPA 7
    if etapa_origem == ETAPA_7_OFERTA_ADIADA:
        # 7 -> 8: o cliente enviou uma nova mensagem após adiar a oferta.
        if evento == EVENTO_CLIENTE_RETORNOU:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_8_RETORNO_OFERTA,
            )
            return _confirmar_retorno_cliente_da_etapa7(
                contexto_historico,
                evento,
                etapa_destino,
            )

    # ETAPA 8
    if etapa_origem == ETAPA_8_RETORNO_OFERTA:
        # 8 -> 9: o cliente retomou e confirmou o agendamento.
        if evento == EVENTO_RETORNO_CONFIRMADO:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_9_EMAIL,
            )
            return _confirmar_decisao_retorno_da_etapa8(
                contexto_historico,
                evento,
                etapa_destino,
            )

        # 8 -> 7: o cliente preferiu adiar novamente.
        if evento == EVENTO_RETORNO_ADIADO:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_7_OFERTA_ADIADA,
            )
            return _confirmar_decisao_retorno_da_etapa8(
                contexto_historico,
                evento,
                etapa_destino,
            )

    # ETAPA 9
    if etapa_origem == ETAPA_9_EMAIL:
        # 9 -> 10: o cliente informou um email estruturalmente válido.
        if evento == EVENTO_EMAIL_VALIDO:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_10_INTRODUCAO_TRIAGEM,
            )
            return _persistir_email_capturado_na_etapa9(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    # ETAPA 10
    if etapa_origem == ETAPA_10_INTRODUCAO_TRIAGEM:
        # 10 -> 11: o cliente iniciou a triagem cognitiva.
        if evento == EVENTO_TRIAGEM_INICIADA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_11_TRIAGEM_PERGUNTA_1,
            )
            return _confirmar_inicio_triagem_da_etapa10(
                contexto_historico,
                evento,
                etapa_destino,
            )

    # ETAPA 11
    if etapa_origem == ETAPA_11_TRIAGEM_PERGUNTA_1:
        # 11 -> 12: registra a resposta da pergunta 1.
        if evento == EVENTO_TRIAGEM_PERGUNTA_1_RESPONDIDA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_12_TRIAGEM_PERGUNTA_2,
            )
            return _persistir_resposta_triagem(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    # ETAPA 12
    if etapa_origem == ETAPA_12_TRIAGEM_PERGUNTA_2:
        # 12 -> 13: registra a resposta da pergunta 2.
        if evento == EVENTO_TRIAGEM_PERGUNTA_2_RESPONDIDA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_13_TRIAGEM_PERGUNTA_3,
            )
            return _persistir_resposta_triagem(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    # ETAPA 13
    if etapa_origem == ETAPA_13_TRIAGEM_PERGUNTA_3:
        # 13 -> 14: registra a resposta da pergunta 3.
        if evento == EVENTO_TRIAGEM_PERGUNTA_3_RESPONDIDA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_14_TRIAGEM_PERGUNTA_4,
            )
            return _persistir_resposta_triagem(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    # ETAPA 14
    if etapa_origem == ETAPA_14_TRIAGEM_PERGUNTA_4:
        # 14 -> 15: registra a resposta da pergunta 4.
        if evento == EVENTO_TRIAGEM_PERGUNTA_4_RESPONDIDA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_15_TRIAGEM_PERGUNTA_5,
            )
            return _persistir_resposta_triagem(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    # ETAPA 15
    if etapa_origem == ETAPA_15_TRIAGEM_PERGUNTA_5:
        # 15 -> 16: registra a resposta da pergunta 5.
        if evento == EVENTO_TRIAGEM_PERGUNTA_5_RESPONDIDA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_16_TRIAGEM_PERGUNTA_6,
            )
            return _persistir_resposta_triagem(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    # ETAPA 16
    if etapa_origem == ETAPA_16_TRIAGEM_PERGUNTA_6:
        # 16 -> 17: registra a resposta da pergunta 6.
        if evento == EVENTO_TRIAGEM_PERGUNTA_6_RESPONDIDA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_17_AGENDAMENTO,
            )
            return _persistir_resposta_triagem(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    # ETAPA 17
    if etapa_origem == ETAPA_17_AGENDAMENTO:
        # 17 -> 18: o cliente confirmou o agendamento e inicia a pesquisa.
        if evento == EVENTO_AGENDAMENTO_CONFIRMADO:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_18_PESQUISA_SATISFACAO,
            )
            return _confirmar_agendamento_da_etapa17(
                contexto_historico,
                evento,
                etapa_destino,
            )

    # ETAPA 18
    if etapa_origem == ETAPA_18_PESQUISA_SATISFACAO:
        # 18 -> 19: registra a nota normalizada da pesquisa de satisfacao.
        if evento == EVENTO_SATISFACAO_AVALIADA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_19_COMENTARIO_SATISFACAO,
            )
            return _persistir_nota_satisfacao_da_etapa18(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    # ETAPA 19
    if etapa_origem == ETAPA_19_COMENTARIO_SATISFACAO:
        # 19 -> 20: registra o comentario opcional antes da finalizacao.
        if evento == EVENTO_COMENTARIO_SATISFACAO_RECEBIDO:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_20_FINALIZACAO,
            )
            return _persistir_comentario_satisfacao_da_etapa19(
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
    contexto_envio,
    etapa_destino,
    *,
    cursor,
):
    id_conversa = contexto_historico["id_conversa"]
    opcao_atendimento = contexto_envio.get("opcao_atendimento")

    if opcao_atendimento is None:
        opcao_atendimento = validar_etapa2(
            contexto_historico.get("texto_cliente_atual") or ""
        )

    if opcao_atendimento is None:
        raise ValueError(
            "Destino do atendimento nao reconstruido na transicao 2 -> 3"
        )

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
        contexto_persistido.update(
            {
                "dependente_criado": dependente["inserido"],
                "id_dependente": dependente["id_dependente"],
                "id_cliente_dependente": dependente["id_cliente"],
            }
        )

    logger.info(
        "destino_atendimento_persistido | acao=salvar_efeitos_transicao evento=%s etapa_origem=%s etapa_resultante=%s id_conversa=%s status_dependente=%s dependente_criado=%s",
        EVENTO_DESTINO_ATENDIMENTO_DEFINIDO,
        contexto_historico.get("id_etapa_origem_transicao"),
        etapa_destino,
        id_conversa,
        status_dependente,
        contexto_persistido["dependente_criado"],
    )

    return contexto_persistido


def _persistir_profissao_capturada_na_etapa3(
    contexto_historico,
    contexto_envio,
    cursor,
    *,
    status_dependente_esperado,
):
    status_dependente = bool(
        contexto_historico.get("status_dependente")
    )

    if status_dependente != status_dependente_esperado:
        raise ValueError(
            "Evento da profissao incompativel com o destino do atendimento "
            f"(id_conversa={contexto_historico['id_conversa']}, "
            f"status_dependente={status_dependente})"
        )

    profissao = contexto_envio.get("profissao")

    if profissao is None:
        resultado = validar_profissao_etapa3(
            contexto_historico.get("texto_cliente_atual") or "",
            contexto_historico.get("tipo_mensagem_atual"),
        )
        if resultado.valida:
            profissao = resultado.profissao

    if not profissao:
        raise ValueError(
            "Profissao nao reconstruida na transicao da etapa 3"
        )

    atualizar_profissao_conversa(
        contexto_historico["id_conversa"],
        profissao,
        cursor,
    )

    logger.info(
        "profissao_persistida | acao=salvar_efeito_transicao "
        "evento=%s etapa_origem=%s etapa_resultante=%s "
        "id_conversa=%s profissao=%s",
        contexto_envio.get("evento_transicao"),
        contexto_historico["id_etapa_origem_transicao"],
        contexto_envio["id_etapa_resultante"],
        contexto_historico["id_conversa"],
        short_value(profissao),
    )

    return {
        "profissao_atualizada": True,
        "profissao": profissao,
    }


def _persistir_nome_dependente_capturado_na_etapa4(
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
            "dependente_nome_anomalia_critica | motivo=nome_vazio_na_transicao_4_5 acao=rollback_e_retry id_conversa=%s etapa_origem=%s etapa_resultante=%s",
            contexto_historico["id_conversa"],
            contexto_historico.get("id_etapa_origem_transicao"),
            contexto_envio.get("id_etapa_resultante"),
        )
        raise ValueError(
            "Nome do dependente nao foi resolvido na transicao 4 -> 5"
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


def _persistir_idade_capturada_na_etapa5(
    contexto_historico,
    contexto_envio,
    cursor,
):
    idade = contexto_envio.get("idade_aluno")

    if idade is None:
        resultado = validar_idade(
            contexto_historico.get("texto_cliente_atual") or ""
        )
        if resultado.valida:
            idade = resultado.idade

    if idade is None:
        raise ValueError(
            "Idade não reconstruída na transição 5 -> 6"
        )

    if contexto_historico.get("status_dependente"):
        atualizar_idade_dependente(
            contexto_historico["id_conversa"],
            idade,
            cursor,
        )
        destino_dado = "dependente"
    else:
        atualizar_idade_cliente(
            contexto_historico["id_cliente"],
            idade,
            cursor,
        )
        destino_dado = "cliente"

    logger.info(
        "idade_aluno_persistida | acao=salvar_efeito_transicao "
        "evento=%s etapa_origem=%s etapa_resultante=%s "
        "id_conversa=%s idade=%s destino_dado=%s",
        EVENTO_IDADE_VALIDA,
        contexto_historico["id_etapa_origem_transicao"],
        contexto_envio["id_etapa_resultante"],
        contexto_historico["id_conversa"],
        idade,
        destino_dado,
    )

    return {
        "idade_aluno_atualizada": True,
        "idade_aluno": idade,
        "destino_dado": destino_dado,
    }


def _confirmar_decisao_oferta_da_etapa6(
    contexto_historico,
    evento,
    etapa_destino,
):
    """
    Torna explícita a aresta da oferta sem duplicar persistência.

    A mudança de id_etapa_atual já foi executada e revalidada no PostgreSQL
    por persistir_movimento_conversa antes dos efeitos específicos.
    """
    logger.info(
        "decisao_oferta_persistida | acao=confirmar_transicao "
        "evento=%s etapa_origem=%s etapa_resultante=%s id_conversa=%s",
        evento,
        contexto_historico["id_etapa_origem_transicao"],
        etapa_destino,
        contexto_historico["id_conversa"],
    )

    return {
        "decisao_oferta_persistida": True,
        "decisao_oferta": evento,
    }


def _confirmar_retorno_cliente_da_etapa7(
    contexto_historico,
    evento,
    etapa_destino,
):
    """
    Confirma a continuidade sem criar dado de negócio adicional.

    A mudança de id_etapa_atual já foi persistida pelo movimento genérico da
    conversa. Esta etapa apenas torna explícita a aresta 7 -> 8.
    """
    logger.info(
        "retorno_cliente_persistido | acao=confirmar_transicao "
        "evento=%s etapa_origem=%s etapa_resultante=%s id_conversa=%s",
        evento,
        contexto_historico["id_etapa_origem_transicao"],
        etapa_destino,
        contexto_historico["id_conversa"],
    )

    return {
        "retorno_cliente_persistido": True,
        "evento_retorno": evento,
    }


def _confirmar_decisao_retorno_da_etapa8(
    contexto_historico,
    evento,
    etapa_destino,
):
    """
    Torna explícita a decisão do retorno sem duplicar persistência.

    A mudança de id_etapa_atual já foi persistida pelo movimento genérico da
    conversa. Esta função confirma apenas as arestas 8 -> 9 e 8 -> 7.
    """
    logger.info(
        "decisao_retorno_persistida | acao=confirmar_transicao "
        "evento=%s etapa_origem=%s etapa_resultante=%s id_conversa=%s",
        evento,
        contexto_historico["id_etapa_origem_transicao"],
        etapa_destino,
        contexto_historico["id_conversa"],
    )

    return {
        "decisao_retorno_persistida": True,
        "decisao_retorno": evento,
    }


def _persistir_email_capturado_na_etapa9(
    contexto_historico,
    contexto_envio,
    cursor,
):
    """
    Persiste somente o email extraído e validado na etapa 9.

    Em reaplicação idempotente, o contexto de envio não carrega o email.
    Nesse caso, o dado é revalidado na mensagem original do cliente.
    """
    email = contexto_envio.get("email_cliente")

    if email is None:
        resultado_email = validar_etapa9(
            contexto_historico.get("texto_cliente_atual") or ""
        )

        if not resultado_email.valido:
            raise ValueError(
                "Email nao reconstruido na transicao 9 -> 10"
            )

        email = resultado_email.email

    email = str(email).strip()

    atualizar_email_cliente(
        contexto_historico["id_cliente"],
        email,
        cursor,
    )

    logger.info(
        "cliente_email_persistido | acao=salvar_efeito_transicao "
        "evento=%s etapa_origem=%s etapa_resultante=%s "
        "id_conversa=%s id_cliente=%s email_preenchido=%s",
        EVENTO_EMAIL_VALIDO,
        contexto_historico["id_etapa_origem_transicao"],
        contexto_envio["id_etapa_resultante"],
        contexto_historico["id_conversa"],
        contexto_historico["id_cliente"],
        bool(email),
    )

    return {
        "cliente_email_atualizado": True,
        "email_preenchido": bool(email),
    }


def _confirmar_inicio_triagem_da_etapa10(
    contexto_historico,
    evento,
    etapa_destino,
):
    """
    Confirma a continuidade sem criar dado de negócio adicional.

    A mudança de id_etapa_atual já foi persistida pelo movimento genérico da
    conversa. Esta função torna explícita somente a aresta 10 -> 11.
    """
    logger.info(
        "inicio_triagem_persistido | acao=confirmar_transicao "
        "evento=%s etapa_origem=%s etapa_resultante=%s id_conversa=%s",
        evento,
        contexto_historico["id_etapa_origem_transicao"],
        etapa_destino,
        contexto_historico["id_conversa"],
    )

    return {
        "inicio_triagem_persistido": True,
        "evento_triagem": evento,
    }


def _persistir_resposta_triagem(
    contexto_historico,
    contexto_envio,
    cursor,
):
    """
    Persiste a opção da pergunta de origem dentro da transação final.

    Em reaplicação idempotente, o contexto de envio não possui a resposta.
    Nesse caso, a opção é reconstruída pela mensagem original do cliente.
    """
    resposta_triagem = contexto_envio.get("resposta_triagem")

    if resposta_triagem is None:
        resposta_triagem = validar_resposta_triagem(
            contexto_historico.get("texto_cliente_atual") or "",
            contexto_historico.get("tipo_mensagem_atual"),
        )

    if resposta_triagem is None:
        raise ValueError(
            "Resposta da triagem não foi reconstruída na transição "
            f"(etapa={contexto_historico.get('id_etapa_origem_transicao')})"
        )

    mensagem_cliente = contexto_historico["mensagem_cliente_atual"]
    resultado = registrar_resposta_triagem(
        contexto_historico["id_conversa"],
        contexto_historico["id_etapa_origem_transicao"],
        resposta_triagem,
        mensagem_cliente.get("id_mensagem"),
        cursor,
    )

    logger.info(
        "efeito_resposta_triagem_persistido | acao=salvar_resposta "
        "evento=%s etapa_origem=%s etapa_resultante=%s "
        "id_conversa=%s resposta=%s inserido=%s",
        contexto_envio.get("evento_transicao"),
        contexto_historico["id_etapa_origem_transicao"],
        contexto_envio["id_etapa_resultante"],
        contexto_historico["id_conversa"],
        resposta_triagem,
        resultado["inserido"],
    )

    return {
        "resposta_triagem_persistida": True,
        **resultado,
    }


def _confirmar_agendamento_da_etapa17(
    contexto_historico,
    evento,
    etapa_destino,
):
    """Confirma a aresta 17 -> 18 sem criar dado de negocio adicional."""
    logger.info(
        "agendamento_confirmado_persistido | acao=confirmar_transicao "
        "evento=%s etapa_origem=%s etapa_resultante=%s id_conversa=%s",
        evento,
        contexto_historico["id_etapa_origem_transicao"],
        etapa_destino,
        contexto_historico["id_conversa"],
    )

    return {
        "agendamento_confirmado": True,
        "evento_agendamento": evento,
    }


def _persistir_nota_satisfacao_da_etapa18(
    contexto_historico,
    contexto_envio,
    cursor,
):
    """Persiste a nota; em retry, reconstrói o valor pela mensagem original."""
    nota_satisfacao = contexto_envio.get("nota_satisfacao")

    if nota_satisfacao is None:
        nota_satisfacao = validar_etapa18(
            contexto_historico.get("texto_cliente_atual") or ""
        )

    if nota_satisfacao is None:
        raise ValueError(
            "Nota de satisfacao ausente na transicao 18 -> 19 "
            f"(id_conversa={contexto_historico['id_conversa']})"
        )

    resultado = salvar_nota_satisfacao(
        contexto_historico["id_conversa"],
        nota_satisfacao,
        cursor,
    )

    logger.info(
        "efeito_nota_satisfacao_persistido | acao=salvar_nota "
        "evento=%s etapa_origem=%s etapa_resultante=%s "
        "id_conversa=%s nota=%s inserido=%s",
        contexto_envio.get("evento_transicao"),
        contexto_historico["id_etapa_origem_transicao"],
        contexto_envio["id_etapa_resultante"],
        contexto_historico["id_conversa"],
        nota_satisfacao,
        resultado["inserido"],
    )

    return {
        "nota_satisfacao_persistida": True,
        **resultado,
    }


def _persistir_comentario_satisfacao_da_etapa19(
    contexto_historico,
    contexto_envio,
    cursor,
):
    """Persiste texto integral ou NULL para mídia e recusa explícita."""
    if "comentario_satisfacao" in contexto_envio:
        comentario_satisfacao = contexto_envio["comentario_satisfacao"]
    else:
        comentario_satisfacao = normalizar_comentario_etapa19(
            contexto_historico.get("texto_cliente_atual") or "",
            contexto_historico.get("tipo_mensagem_atual"),
        )

    resultado = salvar_comentario_satisfacao(
        contexto_historico["id_conversa"],
        comentario_satisfacao,
        cursor,
    )

    logger.info(
        "efeito_comentario_satisfacao_persistido | "
        "acao=salvar_comentario evento=%s etapa_origem=%s "
        "etapa_resultante=%s id_conversa=%s "
        "comentario_preenchido=%s inserido=%s",
        contexto_envio.get("evento_transicao"),
        contexto_historico["id_etapa_origem_transicao"],
        contexto_envio["id_etapa_resultante"],
        contexto_historico["id_conversa"],
        bool(comentario_satisfacao),
        resultado["inserido"],
    )

    return {
        "comentario_satisfacao_persistido": True,
        **resultado,
    }
