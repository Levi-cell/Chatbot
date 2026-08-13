import logging

from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa1 import (
    enviar_etapa1,
    enviar_etapa1_contexto_nome_invalido,
    enviar_etapa1_financeiro,
    enviar_etapa1_financeiro_inicio,
    enviar_etapa1_midia,
    enviar_etapa1_midia_inicio,
    enviar_etapa1_reforco_escolar,
    enviar_etapa1_reforco_escolar_inicio,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa2 import (
    enviar_etapa2,
)
from core.logging_config import short_value
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_financeiro import (
    TIPO_TRATAMENTO_FINANCEIRO,
    validar_pergunta_financeira,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_midia import (
    TIPO_TRATAMENTO_TIPO_NAO_SUPORTADO,
    validar_midia,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_reforco_escolar import (
    TIPO_TRATAMENTO_REFORCO_ESCOLAR,
    validar_duvida_reforco_escolar,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_nome import (
    TIPO_TRATAMENTO_NOME_INVALIDO,
    validar_nome_cliente,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_2_DESTINO_ATENDIMENTO,
    EVENTO_NOME_CLIENTE_VALIDO,
)
from workers.worker_flow.response_flow.transicoes.resolver_transicao import (
    anexar_transicao_ao_contexto_envio,
    resolver_destino_transicao,
)


"""
ESSE ARQUIVO TEM DUAS RESPONSABILIDADES

- VALIDAR PRIMEIRA ETAPA
- ENCAMINHAR PARA SEGUNDA ETAPA
"""


logger = logging.getLogger("worker.etapa1")


def resolve_etapa1(contexto_historico):
    """
    id_etapa_atual is None não é uma etapa separada.
    É apenas o primeiro contato antes da etapa 1 ser persistida.

    Nome inválido, mídia e pergunta financeira possuem tratamento próprio.
    Somente nome válido produz o evento nome_cliente_valido.
    """
    id_conversa = contexto_historico["id_conversa"]
    id_etapa_atual = contexto_historico.get("id_etapa_atual")
    tipo_mensagem = contexto_historico.get("tipo_mensagem_atual")
    texto_cliente = contexto_historico.get("texto_cliente_atual") or ""
    mensagem_cliente_atual = contexto_historico["mensagem_cliente_atual"]
    cliente_telefone = mensagem_cliente_atual["cliente_telefone"]
    phone_id_unidade = mensagem_cliente_atual["id_phone_unidade"]

    conversa_sem_etapa = id_etapa_atual is None
    nome_unidade = contexto_historico.get("nome_unidade")
    nome_agente = contexto_historico.get("nome_agente")
    genero = contexto_historico.get("genero")

    if conversa_sem_etapa:
        campos_ausentes = [
            campo
            for campo, valor in (
                ("nome_unidade", nome_unidade),
                ("nome_agente", nome_agente),
                ("genero", genero),
            )
            if not valor
        ]
        if campos_ausentes:
            raise ValueError(
                "Etapa 1 inicial sem dados de apresentacao da unidade "
                f"(id_conversa={id_conversa}, "
                f"campos_ausentes={campos_ausentes})"
            )

        if genero not in {"masculino", "feminino"}:
            raise ValueError(
                "Etapa 1 inicial com genero de agente invalido "
                f"(id_conversa={id_conversa}, genero={genero!r})"
            )

    # Mídia tem prioridade sobre todas as validações de texto.
    if validar_midia(tipo_mensagem):
        _logar_tipo_nao_suportado(contexto_historico)

        if conversa_sem_etapa:
            return enviar_etapa1_midia_inicio(
                cliente_telefone,
                phone_id_unidade,
                nome_unidade,
                nome_agente,
                genero,
            )

        return enviar_etapa1_midia(
            cliente_telefone,
            phone_id_unidade,
        )

    # A dúvida sobre reforço é mais específica que o financeiro e o nome.
    if validar_duvida_reforco_escolar(texto_cliente):
        _logar_tratamento_texto(
            contexto_historico,
            TIPO_TRATAMENTO_REFORCO_ESCOLAR,
        )

        if conversa_sem_etapa:
            return enviar_etapa1_reforco_escolar_inicio(
                cliente_telefone,
                phone_id_unidade,
                nome_unidade,
                nome_agente,
                genero,
            )

        return enviar_etapa1_reforco_escolar(
            cliente_telefone,
            phone_id_unidade,
        )

    if validar_pergunta_financeira(texto_cliente):
        _logar_tratamento_texto(
            contexto_historico,
            TIPO_TRATAMENTO_FINANCEIRO,
        )

        if conversa_sem_etapa:
            return enviar_etapa1_financeiro_inicio(
                cliente_telefone,
                phone_id_unidade,
                nome_unidade,
                nome_agente,
                genero,
            )

        return enviar_etapa1_financeiro(
            cliente_telefone,
            phone_id_unidade,
        )

    # Primeiro contato normal: inicializa a conversa na etapa 1.
    if conversa_sem_etapa:
        return enviar_etapa1(
            cliente_telefone,
            phone_id_unidade,
            nome_unidade,
            nome_agente,
            genero,
        )

    ### VALIDANDO NOME

    resultado_nome = validar_nome_cliente(texto_cliente)

    if not resultado_nome.valido:
        _logar_tratamento_texto(
            contexto_historico,
            TIPO_TRATAMENTO_NOME_INVALIDO,
            motivo_detalhado=resultado_nome.motivo,
        )

        return enviar_etapa1_contexto_nome_invalido(
            cliente_telefone,
            phone_id_unidade,
        )

    # VALIDANDO DESTINO(S)
    # A resposta já passou pelos tratamentos; agora o mapa autoriza a aresta.
    etapa_destino = resolver_destino_transicao(
        contexto_historico,
        EVENTO_NOME_CLIENTE_VALIDO,
        destinos_esperados={ETAPA_2_DESTINO_ATENDIMENTO},
    )

    logger.debug(
        "etapa1_nome_validado | acao=enviar_etapa_destino id_conversa=%s evento=%s etapa_destino=%s primeiro_nome=%s",
        id_conversa,
        EVENTO_NOME_CLIENTE_VALIDO,
        etapa_destino,
        short_value(resultado_nome.primeiro_nome),
    )

    contexto_envio = enviar_etapa2(
        cliente_telefone,
        phone_id_unidade,
        nome=resultado_nome.primeiro_nome,
    )
    contexto_envio["primeiro_nome_cliente"] = resultado_nome.primeiro_nome

    return anexar_transicao_ao_contexto_envio(
        contexto_historico,
        contexto_envio,
        EVENTO_NOME_CLIENTE_VALIDO,
        etapa_destino,
    )


















def _logar_tipo_nao_suportado(contexto_historico):
    mensagem_cliente_atual = contexto_historico["mensagem_cliente_atual"]

    logger.info(
        "resposta_cliente_invalida | motivo=tipo_mensagem_nao_suportado acao=tratar_sem_avancar id_conversa=%s id_mensagem_fila=%s cliente=%s phone_number_id=%s tipo=%s etapa_cliente=%s",
        contexto_historico["id_conversa"],
        mensagem_cliente_atual["id_mensagem_fila"],
        short_value(mensagem_cliente_atual["cliente_telefone"]),
        short_value(mensagem_cliente_atual["id_phone_unidade"]),
        contexto_historico.get("tipo_mensagem_atual"),
        contexto_historico["id_etapa_cliente"],
    )


def _logar_tratamento_texto(
    contexto_historico,
    motivo,
    *,
    motivo_detalhado=None,
):
    mensagem_cliente_atual = contexto_historico["mensagem_cliente_atual"]

    logger.info(
        "resposta_cliente_tratamento | motivo=%s motivo_detalhado=%s acao=tratar_sem_avancar id_conversa=%s id_mensagem_fila=%s cliente=%s phone_number_id=%s etapa_cliente=%s",
        motivo,
        motivo_detalhado,
        contexto_historico["id_conversa"],
        mensagem_cliente_atual["id_mensagem_fila"],
        short_value(mensagem_cliente_atual["cliente_telefone"]),
        short_value(mensagem_cliente_atual["id_phone_unidade"]),
        contexto_historico["id_etapa_cliente"],
    )
