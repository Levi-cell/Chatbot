import logging

from core.repositories.atendimento.turnos import salvar_turno_conversa
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa18 import validar_etapa18

from core.logging_config import short_value
from core.repositories.atendimento.clientes import (
    atualizar_email_cliente,
    atualizar_idade_cliente,
    atualizar_nome_cliente_por_telefone,
    atualizar_profissao_cliente,
)
from core.repositories.atendimento.conversas import (
    atualizar_profissao_conversa,
    atualizar_status_dependente_conversa,
)
from core.repositories.atendimento.dependentes import (
    atualizar_idade_dependente,
    atualizar_nome_dependente_por_conversa,
    inserir_dependente_para_conversa,
    remover_dependente_placeholder_da_conversa,
)
from core.repositories.fluxo.triagem import registrar_resposta_triagem
from core.repositories.fluxo.pesquisa_satisfacao import (
    salvar_comentario_satisfacao,
    salvar_nota_satisfacao,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa21 import (
    validar_etapa21,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa22 import (
    TIPOS_MENSAGEM_ACEITOS_ETAPA22,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa23 import (
    normalizar_comentario_etapa23,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_nome import (
    validar_nome_cliente,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_triagem import (
    validar_resposta_triagem,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa6 import (
    validar_idade,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa2 import (
    OPCAO_PARA_OUTRA_PESSOA,
    validar_etapa2,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa4 import (
    validar_profissao_etapa4,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa10 import (
    CLASSIFICACAO_EMAIL_AUSENTE,
    CLASSIFICACAO_EMAIL_NAO_INFORMADO,
    CLASSIFICACAO_EMAIL_VALIDO,
    calcular_email_obrigatorio_efetivo,
    classificar_resposta_email,
    classificar_resposta_email_aceita,
    validar_etapa10,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_1_NOME_CLIENTE,
    ETAPA_2_DESTINO_ATENDIMENTO,
    ETAPA_3_CONFIRMACAO_DESTINO,
    ETAPA_4_PROFISSAO,
    ETAPA_5_NOME_DEPENDENTE,
    ETAPA_6_IDADE_ALUNO,
    ETAPA_7_OFERTA_AULA,
    ETAPA_8_OFERTA_ADIADA,
    ETAPA_9_RETORNO_OFERTA,
    ETAPA_10_EMAIL,
    ETAPA_11_INTRODUCAO_TRIAGEM,
    ETAPA_12_TRIAGEM_PERGUNTA_1,
    ETAPA_13_TRIAGEM_PERGUNTA_2,
    ETAPA_14_TRIAGEM_PERGUNTA_3,
    ETAPA_15_TRIAGEM_PERGUNTA_4,
    ETAPA_16_TRIAGEM_PERGUNTA_5,
    ETAPA_17_TRIAGEM_PERGUNTA_6,
    ETAPA_18_ESCOLHA_TURNO,
    ETAPA_19_ENCAMINHAMENTO_COMERCIAL,
    EVENTO_TRIAGEM_CONCLUIDA_SEM_LINK,
    EVENTO_TURNO_ESCOLHIDO,
    EVENTO_AVALIACAO_SOLICITADA,
    ETAPA_20_AGENDAMENTO,
    ETAPA_21_PESQUISA_SATISFACAO,
    ETAPA_22_DECISAO_COMENTARIO,
    ETAPA_23_COMENTARIO_SATISFACAO,
    ETAPA_24_FINALIZACAO,
    EVENTO_AGENDAMENTO_CONFIRMADO,
    EVENTO_CLIENTE_RETORNOU,
    EVENTO_COMENTARIO_SATISFACAO_ACEITO,
    EVENTO_COMENTARIO_SATISFACAO_RECUSADO,
    EVENTO_COMENTARIO_SATISFACAO_RECEBIDO,
    EVENTO_DESTINO_ATENDIMENTO_DEFINIDO,
    EVENTO_DESTINO_ATENDIMENTO_CONFIRMADO,
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

MOTIVO_ENCAMINHAMENTO_SUPORTE_IDOSO = "encaminhado_suporte_idoso"


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

    if (
        etapa_origem == ETAPA_6_IDADE_ALUNO
        and contexto_envio.get("encerrar_atendimento")
        and contexto_envio.get("motivo_encerramento")
        == MOTIVO_ENCAMINHAMENTO_SUPORTE_IDOSO
    ):
        return _persistir_idade_encaminhamento_suporte_idoso(
            contexto_historico,
            contexto_envio,
            cursor,
        )

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
        # 2 -> 3: a opção foi validada e aguarda confirmação explícita.
        if evento == EVENTO_DESTINO_ATENDIMENTO_DEFINIDO:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_3_CONFIRMACAO_DESTINO,
            )
            return _persistir_destino_atendimento_da_etapa2(
                contexto_historico,
                contexto_envio,
                etapa_destino,
                cursor=cursor,
            )

    # ETAPA 3
    if etapa_origem == ETAPA_3_CONFIRMACAO_DESTINO:
        if evento == EVENTO_DESTINO_ATENDIMENTO_CONFIRMADO:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_4_PROFISSAO,
            )
            return _persistir_confirmacao_destino_da_etapa3(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    # ETAPA 4
    if etapa_origem == ETAPA_4_PROFISSAO:
        if evento == EVENTO_PROFISSAO_DEPENDENTE_VALIDA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_5_NOME_DEPENDENTE,
            )
            return _persistir_profissao_capturada_na_etapa4(
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
                ETAPA_6_IDADE_ALUNO,
            )
            return _persistir_profissao_capturada_na_etapa4(
                contexto_historico,
                contexto_envio,
                cursor,
                status_dependente_esperado=False,
            )

    # ETAPA 5
    if etapa_origem == ETAPA_5_NOME_DEPENDENTE:
        # 5 -> 6: o cliente informou o nome do dependente.
        if evento == EVENTO_NOME_DEPENDENTE_VALIDO:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_6_IDADE_ALUNO,
            )
            return _persistir_nome_dependente_capturado_na_etapa5(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    # ETAPA 6
    if etapa_origem == ETAPA_6_IDADE_ALUNO:
        # 6 -> 7: a idade do aluno foi validada.
        if evento == EVENTO_IDADE_VALIDA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_7_OFERTA_AULA,
            )
            return _persistir_idade_capturada_na_etapa6(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    # ETAPA 7
    if etapa_origem == ETAPA_7_OFERTA_AULA:
        # 7 -> 10: o cliente aceitou agendar.
        if evento == EVENTO_OFERTA_ACEITA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_10_EMAIL,
            )
            return _confirmar_decisao_oferta_da_etapa7(
                contexto_historico,
                evento,
                etapa_destino,
            )

        # 7 -> 8: o cliente preferiu adiar.
        if evento == EVENTO_OFERTA_ADIADA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_8_OFERTA_ADIADA,
            )
            return _confirmar_decisao_oferta_da_etapa7(
                contexto_historico,
                evento,
                etapa_destino,
            )

    # ETAPA 8
    if etapa_origem == ETAPA_8_OFERTA_ADIADA:
        # 8 -> 9: o cliente enviou uma nova mensagem após adiar a oferta.
        if evento == EVENTO_CLIENTE_RETORNOU:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_9_RETORNO_OFERTA,
            )
            return _confirmar_retorno_cliente_da_etapa8(
                contexto_historico,
                evento,
                etapa_destino,
            )

    # ETAPA 9
    if etapa_origem == ETAPA_9_RETORNO_OFERTA:
        # 9 -> 10: o cliente retomou e confirmou o agendamento.
        if evento == EVENTO_RETORNO_CONFIRMADO:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_10_EMAIL,
            )
            return _confirmar_decisao_retorno_da_etapa9(
                contexto_historico,
                evento,
                etapa_destino,
            )

        # 9 -> 8: o cliente preferiu adiar novamente.
        if evento == EVENTO_RETORNO_ADIADO:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_8_OFERTA_ADIADA,
            )
            return _confirmar_decisao_retorno_da_etapa9(
                contexto_historico,
                evento,
                etapa_destino,
            )

    # ETAPA 10
    if etapa_origem == ETAPA_10_EMAIL:
        # 10 -> 11: a coleta foi aceita. A aresta técnica legada é única;
        # o resultado semântico distingue endereço, ausência e não informado.
        if evento == EVENTO_EMAIL_VALIDO:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_11_INTRODUCAO_TRIAGEM,
            )
            return _persistir_email_capturado_na_etapa10(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    # ETAPA 11
    if etapa_origem == ETAPA_11_INTRODUCAO_TRIAGEM:
        # 11 -> 12: o cliente iniciou a triagem cognitiva.
        if evento == EVENTO_TRIAGEM_INICIADA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_12_TRIAGEM_PERGUNTA_1,
            )
            return _confirmar_inicio_triagem_da_etapa11(
                contexto_historico,
                evento,
                etapa_destino,
            )

    # ETAPA 12
    if etapa_origem == ETAPA_12_TRIAGEM_PERGUNTA_1:
        # 12 -> 13: registra a resposta da pergunta 1.
        if evento == EVENTO_TRIAGEM_PERGUNTA_1_RESPONDIDA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_13_TRIAGEM_PERGUNTA_2,
            )
            return _persistir_resposta_triagem(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    # ETAPA 13
    if etapa_origem == ETAPA_13_TRIAGEM_PERGUNTA_2:
        # 13 -> 14: registra a resposta da pergunta 2.
        if evento == EVENTO_TRIAGEM_PERGUNTA_2_RESPONDIDA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_14_TRIAGEM_PERGUNTA_3,
            )
            return _persistir_resposta_triagem(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    # ETAPA 14
    if etapa_origem == ETAPA_14_TRIAGEM_PERGUNTA_3:
        # 14 -> 15: registra a resposta da pergunta 3.
        if evento == EVENTO_TRIAGEM_PERGUNTA_3_RESPONDIDA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_15_TRIAGEM_PERGUNTA_4,
            )
            return _persistir_resposta_triagem(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    # ETAPA 15
    if etapa_origem == ETAPA_15_TRIAGEM_PERGUNTA_4:
        # 15 -> 16: registra a resposta da pergunta 4.
        if evento == EVENTO_TRIAGEM_PERGUNTA_4_RESPONDIDA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_16_TRIAGEM_PERGUNTA_5,
            )
            return _persistir_resposta_triagem(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    # ETAPA 16
    if etapa_origem == ETAPA_16_TRIAGEM_PERGUNTA_5:
        # 16 -> 17: registra a resposta da pergunta 5.
        if evento == EVENTO_TRIAGEM_PERGUNTA_5_RESPONDIDA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_17_TRIAGEM_PERGUNTA_6,
            )
            return _persistir_resposta_triagem(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    # ETAPA 17
    if etapa_origem == ETAPA_17_TRIAGEM_PERGUNTA_6:
        destinos = {
            EVENTO_TRIAGEM_PERGUNTA_6_RESPONDIDA: ETAPA_20_AGENDAMENTO,
            EVENTO_TRIAGEM_CONCLUIDA_SEM_LINK: ETAPA_18_ESCOLHA_TURNO,
        }
        if evento in destinos:
            # 17 -> 18 ou 20: as duas rotas preservam a sexta resposta da triagem.
            _exigir_destino(etapa_origem, evento, etapa_destino, destinos[evento])
            return _persistir_resposta_triagem(contexto_historico, contexto_envio, cursor)

    # ETAPA 18
    if etapa_origem == ETAPA_18_ESCOLHA_TURNO and evento == EVENTO_TURNO_ESCOLHIDO:
        # 18 -> 19: salvar o turno no mesmo commit do movimento da conversa.
        _exigir_destino(etapa_origem, evento, etapa_destino, ETAPA_19_ENCAMINHAMENTO_COMERCIAL)
        turno = contexto_envio.get("turno")
        if turno is None:
            # A resposta do bot já persistida dispensa novo envio; a mensagem
            # original contém a preferência necessária para reconstruir o efeito.
            turno = validar_etapa18(
                contexto_historico.get("texto_cliente_atual"),
                contexto_historico.get("tipo_mensagem_atual"),
            )
        return salvar_turno_conversa(
            contexto_historico["id_conversa"], contexto_historico["id_unidade"], turno, cursor,
        )

    # ETAPA 19
    if etapa_origem == ETAPA_19_ENCAMINHAMENTO_COMERCIAL and evento == EVENTO_AVALIACAO_SOLICITADA:
        # 19 -> 21: apenas apresenta a pesquisa, sem salvar uma nota nesta aresta.
        _exigir_destino(etapa_origem, evento, etapa_destino, ETAPA_21_PESQUISA_SATISFACAO)
        return {"pesquisa_apresentada": True}

    # ETAPA 20
    if etapa_origem == ETAPA_20_AGENDAMENTO:
        # 20 -> 21: o cliente confirmou o agendamento e inicia a pesquisa.
        if evento == EVENTO_AGENDAMENTO_CONFIRMADO:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_21_PESQUISA_SATISFACAO,
            )
            return _confirmar_agendamento_da_etapa20(
                contexto_historico,
                evento,
                etapa_destino,
            )

    # ETAPA 21
    if etapa_origem == ETAPA_21_PESQUISA_SATISFACAO:
        # 21 -> 22: registra a nota normalizada da pesquisa de satisfacao.
        if evento == EVENTO_SATISFACAO_AVALIADA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_22_DECISAO_COMENTARIO,
            )
            return _persistir_nota_satisfacao_da_etapa21(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    # ETAPA 22
    if etapa_origem == ETAPA_22_DECISAO_COMENTARIO:
        # 22 -> 23: confirma que o cliente deseja escrever um comentario.
        if evento == EVENTO_COMENTARIO_SATISFACAO_ACEITO:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_23_COMENTARIO_SATISFACAO,
            )
            return _confirmar_decisao_comentario_da_etapa22(
                contexto_historico,
                evento,
                etapa_destino,
            )

        # 22 -> 24: registra a recusa explicita e encerra o atendimento.
        if evento == EVENTO_COMENTARIO_SATISFACAO_RECUSADO:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_24_FINALIZACAO,
            )
            return _persistir_recusa_comentario_da_etapa22(
                contexto_historico,
                cursor,
            )

    # ETAPA 23
    if etapa_origem == ETAPA_23_COMENTARIO_SATISFACAO:
        # 23 -> 24: registra o comentario livre antes da finalizacao.
        if evento == EVENTO_COMENTARIO_SATISFACAO_RECEBIDO:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_24_FINALIZACAO,
            )
            return _persistir_comentario_satisfacao_da_etapa23(
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


def _persistir_confirmacao_destino_da_etapa3(
    contexto_historico,
    contexto_envio,
    cursor,
):
    """Aplica o destino final como valor absoluto e seguro para replay.

    No primeiro processamento, o validador produz o valor absoluto. Em replay,
    movimento e efeito já foram confirmados juntos, então o worker relê esse
    mesmo valor da conversa. A resposta relativa nunca é reinterpretada.
    """
    status_dependente_final = contexto_envio.get(
        "status_dependente_final"
    )
    if not isinstance(status_dependente_final, bool):
        raise ValueError(
            "Confirmacao da etapa 3 sem status_dependente_final booleano "
            f"(valor={status_dependente_final!r})"
        )

    id_conversa = contexto_historico["id_conversa"]
    status_anterior = contexto_historico.get("status_dependente")
    if not isinstance(status_anterior, bool):
        raise ValueError(
            "Confirmacao da etapa 3 sem status_dependente anterior booleano "
            f"(valor={status_anterior!r})"
        )

    atualizar_status_dependente_conversa(
        id_conversa,
        status_dependente_final,
        cursor,
    )

    resultado = {
        "status_dependente_atualizado": True,
        "status_dependente": status_dependente_final,
        "status_dependente_alterado": (
            status_anterior != status_dependente_final
        ),
        "dependente_criado": False,
        "dependente_removido": False,
    }

    if status_dependente_final:
        dependente = inserir_dependente_para_conversa(id_conversa, cursor)
        resultado.update(
            {
                "dependente_criado": dependente["inserido"],
                "id_dependente": dependente["id_dependente"],
                "id_cliente_dependente": dependente["id_cliente"],
            }
        )
    else:
        resultado["dependente_removido"] = (
            remover_dependente_placeholder_da_conversa(
                id_conversa,
                cursor,
            )
        )

    logger.info(
        "destino_atendimento_confirmado | acao=aplicar_status_absoluto "
        "evento=%s etapa_origem=%s etapa_resultante=%s id_conversa=%s "
        "status_anterior=%s status_final=%s dependente_criado=%s "
        "dependente_removido=%s",
        contexto_envio.get("evento_transicao"),
        contexto_historico.get("id_etapa_origem_transicao"),
        contexto_envio.get("id_etapa_resultante"),
        id_conversa,
        status_anterior,
        status_dependente_final,
        resultado["dependente_criado"],
        resultado["dependente_removido"],
    )

    return resultado


def _persistir_profissao_capturada_na_etapa4(
    contexto_historico,
    contexto_envio,
    cursor,
    *,
    status_dependente_esperado,
):
    status_dependente = contexto_historico.get("status_dependente")
    if not isinstance(status_dependente, bool):
        raise ValueError(
            "Profissao sem status_dependente booleano persistido "
            f"(valor={status_dependente!r})"
        )

    if status_dependente != status_dependente_esperado:
        raise ValueError(
            "Evento da profissao incompativel com o destino do atendimento "
            f"(id_conversa={contexto_historico['id_conversa']}, "
            f"status_dependente={status_dependente})"
        )

    profissao = contexto_envio.get("profissao")

    if profissao is None:
        resultado = validar_profissao_etapa4(
            contexto_historico.get("texto_cliente_atual") or "",
            contexto_historico.get("tipo_mensagem_atual"),
        )
        if resultado.valida:
            profissao = resultado.profissao

    if not profissao:
        raise ValueError(
            "Profissao nao reconstruida na transicao da etapa 4"
        )

    atualizar_profissao_conversa(
        contexto_historico["id_conversa"],
        profissao,
        cursor,
    )
    atualizar_profissao_cliente(
        contexto_historico["id_cliente"],
        profissao,
        cursor,
    )

    logger.info(
        "profissao_persistida | acao=salvar_snapshot_e_atualizar_cliente "
        "evento=%s etapa_origem=%s etapa_resultante=%s "
        "id_conversa=%s id_cliente=%s profissao=%s",
        contexto_envio.get("evento_transicao"),
        contexto_historico["id_etapa_origem_transicao"],
        contexto_envio["id_etapa_resultante"],
        contexto_historico["id_conversa"],
        contexto_historico["id_cliente"],
        short_value(profissao),
    )

    return {
        "profissao_atualizada": True,
        "profissao": profissao,
    }


def _persistir_nome_dependente_capturado_na_etapa5(
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
            "dependente_nome_anomalia_critica | motivo=nome_vazio_na_transicao_5_6 acao=rollback_e_retry id_conversa=%s etapa_origem=%s etapa_resultante=%s",
            contexto_historico["id_conversa"],
            contexto_historico.get("id_etapa_origem_transicao"),
            contexto_envio.get("id_etapa_resultante"),
        )
        raise ValueError(
            "Nome do dependente nao foi resolvido na transicao 5 -> 6"
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


def _persistir_idade_capturada_na_etapa6(
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
            "Idade não reconstruída na transição 6 -> 7"
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


def _persistir_idade_encaminhamento_suporte_idoso(
    contexto_historico,
    contexto_envio,
    cursor,
):
    if contexto_historico.get("status_dependente"):
        raise ValueError(
            "Encaminhamento de suporte ao idoso não aceita dependente"
        )

    idade = contexto_envio.get("idade_aluno")
    if idade is None:
        resultado = validar_idade(
            contexto_historico.get("texto_cliente_atual") or ""
        )
        idade = resultado.idade if resultado.valida else None

    if (
        isinstance(idade, bool)
        or not isinstance(idade, int)
        or not 50 <= idade <= 99
    ):
        raise ValueError(
            "Idade inválida no encaminhamento de suporte ao idoso "
            f"(idade={idade!r})"
        )

    atualizar_idade_cliente(
        contexto_historico["id_cliente"],
        idade,
        cursor,
    )

    logger.info(
        "idade_titular_persistida | acao=encaminhar_suporte_idoso "
        "id_conversa=%s id_cliente=%s faixa=50_99",
        contexto_historico["id_conversa"],
        contexto_historico["id_cliente"],
    )
    return {
        "idade_aluno_atualizada": True,
        "idade_aluno": idade,
        "destino_dado": "cliente",
        "encaminhamento_suporte_idoso": True,
    }


def _confirmar_decisao_oferta_da_etapa7(
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


def _confirmar_retorno_cliente_da_etapa8(
    contexto_historico,
    evento,
    etapa_destino,
):
    """
    Confirma a continuidade sem criar dado de negócio adicional.

    A mudança de id_etapa_atual já foi persistida pelo movimento genérico da
    conversa. Esta etapa apenas torna explícita a aresta 8 -> 9.
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


def _confirmar_decisao_retorno_da_etapa9(
    contexto_historico,
    evento,
    etapa_destino,
):
    """
    Torna explícita a decisão do retorno sem duplicar persistência.

    A mudança de id_etapa_atual já foi persistida pelo movimento genérico da
    conversa. Esta função confirma apenas as arestas 9 -> 10 e 9 -> 8.
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


def _persistir_email_capturado_na_etapa10(
    contexto_historico,
    contexto_envio,
    cursor,
):
    """Persiste de forma absoluta o resultado aceito na conversa atual."""
    classificacao = contexto_envio.get("resultado_coleta_email")
    email = contexto_envio.get("email_cliente")

    if classificacao is None and email:
        classificacao = CLASSIFICACAO_EMAIL_VALIDO
        email = validar_etapa10(email).email

    if classificacao is None:
        texto_cliente = contexto_historico.get("texto_cliente_atual") or ""

        if contexto_envio.get("resposta_ja_existia"):
            resultado_email = classificar_resposta_email_aceita(
                texto_cliente
            )
        else:
            email_obrigatorio = calcular_email_obrigatorio_efetivo(
                contexto_historico.get("email_obrigatorio_unidade"),
                contexto_historico.get("status_dependente"),
                contexto_historico.get("idade_cliente"),
            )
            resultado_email = classificar_resposta_email(
                texto_cliente,
                email_obrigatorio=email_obrigatorio,
            )

        if not resultado_email.aceita:
            raise ValueError(
                "Resultado de email nao reconstruido na transicao 10 -> 11"
            )

        classificacao = resultado_email.classificacao
        email = resultado_email.email

    classificacoes_validas = {
        CLASSIFICACAO_EMAIL_VALIDO,
        CLASSIFICACAO_EMAIL_AUSENTE,
        CLASSIFICACAO_EMAIL_NAO_INFORMADO,
    }
    if classificacao not in classificacoes_validas:
        raise ValueError(
            "Classificacao de email invalida na transicao 10 -> 11 "
            f"(classificacao={classificacao!r})"
        )

    if classificacao == CLASSIFICACAO_EMAIL_VALIDO:
        resultado_estrutural = validar_etapa10(email)
        if not resultado_estrutural.valido:
            raise ValueError(
                "Email valido sem endereco reconstruivel na transicao 10 -> 11"
            )
        email = resultado_estrutural.email
    else:
        email = None

    atualizar_email_cliente(
        contexto_historico["id_cliente"],
        email,
        cursor,
    )

    logger.info(
        "cliente_email_persistido | acao=salvar_efeito_transicao "
        "evento=%s etapa_origem=%s etapa_resultante=%s "
        "id_conversa=%s id_cliente=%s email_preenchido=%s "
        "resultado_coleta=%s",
        EVENTO_EMAIL_VALIDO,
        contexto_historico["id_etapa_origem_transicao"],
        contexto_envio["id_etapa_resultante"],
        contexto_historico["id_conversa"],
        contexto_historico["id_cliente"],
        bool(email),
        classificacao,
    )

    return {
        "cliente_email_atualizado": True,
        "email_preenchido": bool(email),
        "resultado_coleta_email": classificacao,
    }


def _confirmar_inicio_triagem_da_etapa11(
    contexto_historico,
    evento,
    etapa_destino,
):
    """
    Confirma a continuidade sem criar dado de negócio adicional.

    A mudança de id_etapa_atual já foi persistida pelo movimento genérico da
    conversa. Esta função torna explícita somente a aresta 11 -> 12.
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


def _confirmar_agendamento_da_etapa20(
    contexto_historico,
    evento,
    etapa_destino,
):
    """Confirma a aresta 20 -> 21 sem criar dado de negocio adicional."""
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


def _persistir_nota_satisfacao_da_etapa21(
    contexto_historico,
    contexto_envio,
    cursor,
):
    """Persiste a nota; em retry, reconstrói o valor pela mensagem original."""
    nota_satisfacao = contexto_envio.get("nota_satisfacao")

    if nota_satisfacao is None:
        nota_satisfacao = validar_etapa21(
            contexto_historico.get("texto_cliente_atual") or ""
        )

    if nota_satisfacao is None:
        raise ValueError(
            "Nota de satisfacao ausente na transicao 21 -> 22 "
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


def _confirmar_decisao_comentario_da_etapa22(
    contexto_historico,
    evento,
    etapa_destino,
):
    """Confirma a escolha sem criar dado antes do comentário efetivo."""
    logger.info(
        "decisao_comentario_persistida | acao=confirmar_transicao "
        "evento=%s etapa_origem=%s etapa_resultante=%s id_conversa=%s",
        evento,
        contexto_historico["id_etapa_origem_transicao"],
        etapa_destino,
        contexto_historico["id_conversa"],
    )

    return {
        "decisao_comentario_persistida": True,
        "decisao_comentario": evento,
    }


def _persistir_recusa_comentario_da_etapa22(
    contexto_historico,
    cursor,
):
    """Registra NULL de forma idempotente para a recusa explícita."""
    resultado = salvar_comentario_satisfacao(
        contexto_historico["id_conversa"],
        None,
        cursor,
    )

    logger.info(
        "recusa_comentario_satisfacao_persistida | "
        "acao=salvar_comentario_nulo evento=%s etapa_origem=%s "
        "etapa_resultante=%s id_conversa=%s inserido=%s",
        EVENTO_COMENTARIO_SATISFACAO_RECUSADO,
        contexto_historico["id_etapa_origem_transicao"],
        ETAPA_24_FINALIZACAO,
        contexto_historico["id_conversa"],
        resultado["inserido"],
    )

    return {
        "comentario_satisfacao_persistido": True,
        **resultado,
    }


def _persistir_comentario_satisfacao_da_etapa23(
    contexto_historico,
    contexto_envio,
    cursor,
):
    """Persiste o texto; em retry, reconstrói a mensagem original."""
    if "comentario_satisfacao" in contexto_envio:
        comentario_satisfacao = contexto_envio["comentario_satisfacao"]
    else:
        texto_cliente = contexto_historico.get("texto_cliente_atual") or ""
        tipo_mensagem = contexto_historico.get("tipo_mensagem_atual")
        # Reconstruir o mesmo resultado do primeiro processamento, inclusive NULL
        # quando não houve texto ou o cliente recusou comentar. Mídia não avança.
        if tipo_mensagem not in TIPOS_MENSAGEM_ACEITOS_ETAPA22:
            raise ValueError(
                "Tipo de mensagem não permitido na transição 23 -> 24 "
                f"(id_conversa={contexto_historico['id_conversa']})"
            )
        comentario_satisfacao = normalizar_comentario_etapa23(
            texto_cliente,
            tipo_mensagem,
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
