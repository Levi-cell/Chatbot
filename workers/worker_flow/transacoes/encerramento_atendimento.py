import logging

from core.validacoes.encerramento_por_idade import (
    MOTIVO_TITULAR_MENOR,
    MOTIVO_UNIVERSAL,
    motivo_dependente,
    motivo_suporte,
    reconstruir_limite_suporte,
)

from core.integrations.whatsapp.messages.etapa6_messages import (
    reconhecer_encerramento_etapa6,
)
from core.repositories.atendimento.conversas import encerrar_conversa
from core.repositories.atendimento.dependentes import (
    excluir_dependente_da_conversa,
)
from core.repositories.fluxo.politicas import buscar_politica_etapa
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa6 import (
    validar_idade,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_6_IDADE_ALUNO,
)


logger = logging.getLogger("worker.support")

MOTIVO_CLIENTE_MENOR_18 = "cliente_menor_18"
MOTIVO_DEPENDENTE_MENOR_5 = "dependente_menor_5"
MOTIVO_IDADE_ACIMA_99 = "idade_acima_99"
MOTIVO_SUPORTE_IDOSO = "encaminhado_suporte_idoso"
MOTIVO_ETAPA_FINAL = "etapa_final"

MOTIVO_ENCERRAMENTO_IDADE_INVALIDA = "idade_invalida"
MOTIVO_ENCERRAMENTO_FOI_AGENDADO = "foi_agendado"
MOTIVO_ENCERRAMENTO_SUPORTE_IDOSO = "encaminhado_suporte_idoso"


def resolver_intencao_encerramento(
    contexto_historico,
    contexto_envio,
    cursor,
):
    if contexto_envio.get("encerrar_atendimento"):
        motivo = contexto_envio["motivo_encerramento"]
        # O resolver carrega o limite que realmente gerou a resposta enviada.
        # Não reler a unidade aqui: ela pode ter mudado depois do envio.
        if motivo == MOTIVO_SUPORTE_IDOSO:
            motivo_banco = motivo_suporte(contexto_envio["limite_idade_encerramento"])
        elif motivo == MOTIVO_DEPENDENTE_MENOR_5:
            motivo_banco = motivo_dependente(contexto_envio["limite_idade_encerramento"])
        elif motivo == MOTIVO_CLIENTE_MENOR_18:
            motivo_banco = MOTIVO_TITULAR_MENOR
        elif motivo == MOTIVO_IDADE_ACIMA_99:
            motivo_banco = MOTIVO_UNIVERSAL
        else:
            raise ValueError(f"Categoria de encerramento desconhecida: {motivo!r}")
        return {
            "motivo": motivo,
            "motivo_encerramento": motivo_banco,
            "excluir_dependente": bool(
                contexto_envio.get("excluir_dependente")
            ),
            "bloqueio_dias": 0,
        }

    # No retry, a resposta já existe e a decisão é reconstruída pela mesma
    # mensagem original da etapa 6, sem consultar conversas anteriores.
    if contexto_envio.get("resposta_ja_existia"):
        intencao_reconstruida = _reconstruir_encerramento_etapa6(
            contexto_historico
        )
        if intencao_reconstruida:
            return intencao_reconstruida

    if not contexto_envio.get("evento_transicao"):
        return None

    id_etapa_destino = contexto_envio.get("id_etapa_resultante")
    politica_destino = buscar_politica_etapa(
        id_etapa_destino,
        cursor,
    )

    if not politica_destino.encerra_automaticamente:
        return None

    return {
        "motivo": MOTIVO_ETAPA_FINAL,
        "motivo_encerramento": MOTIVO_ENCERRAMENTO_FOI_AGENDADO,
        "excluir_dependente": False,
        "bloqueio_dias": politica_destino.bloqueio_dias,
    }


def _reconstruir_encerramento_etapa6(contexto_historico):
    """Conclui somente a resposta já comprovada para a entrada em recuperação.

    A busca anterior exige conversa + fila + hash de origem. Aqui não procuramos
    uma mensagem solta no histórico e não usamos cliente.idade, pois os efeitos
    da idade podem estar pendentes. Sem resposta conhecida, não deduzir fechamento.
    """
    if contexto_historico.get("id_etapa_origem_transicao") != ETAPA_6_IDADE_ALUNO:
        return None
    resposta = contexto_historico.get("resposta_bot_para_mensagem_atual") or {}
    reconhecida = reconhecer_encerramento_etapa6(
        resposta.get("conteudo_texto"), resposta.get("tipo_mensagem"),
    )
    if not reconhecida:
        return None

    resultado = validar_idade(contexto_historico.get("texto_cliente_atual") or "")
    idade = resultado.idade if resultado.valida or resultado.acima_limite else None
    dependente = bool(contexto_historico.get("status_dependente"))
    categoria = reconhecida["categoria"]
    motivo_banco = MOTIVO_ENCERRAMENTO_IDADE_INVALIDA
    excluir_dependente = False

    if categoria == "suporte":
        if dependente:
            return None
        motivo = MOTIVO_SUPORTE_IDOSO
        motivo_banco = MOTIVO_ENCERRAMENTO_SUPORTE_IDOSO
        limite_atual = contexto_historico["idade_minima_suporte"]
        limite = reconstruir_limite_suporte(idade, limite_atual)
        if limite is not None:
            motivo_banco = motivo_suporte(limite)
            logger.info(
                "encerramento_reconstruido_por_compatibilidade | "
                "id_conversa=%s id_mensagem_fila=%s idade=%s "
                "limite_atual=%s limite_reconstruido=%s",
                contexto_historico.get("id_conversa"),
                (contexto_historico.get("mensagem_cliente_atual") or {}).get("id_mensagem_fila"),
                idade, limite_atual, limite,
            )
        # Suporte antigo de 90–99 continua genérico: não virar universal/80+.
    elif categoria == "titular_menor":
        if dependente:
            return None
        motivo = MOTIVO_CLIENTE_MENOR_18
        if idade is not None and idade < 18:
            motivo_banco = MOTIVO_TITULAR_MENOR
    elif categoria == "dependente_menor":
        if not dependente:
            return None
        motivo = MOTIVO_DEPENDENTE_MENOR_5
        excluir_dependente = True
        minimo_enviado = reconhecida["idade_minima"]
        if idade is not None and idade < minimo_enviado:
            # Preserva o mínimo que o cliente leu, mesmo que o BPA tenha mudado.
            motivo_banco = motivo_dependente(minimo_enviado)
    else:
        motivo = MOTIVO_IDADE_ACIMA_99
        if idade is not None and 90 <= idade < 100:
            motivo_banco = MOTIVO_UNIVERSAL
        # O corpo de 100+ é igual entre versões. Sem motivo confirmado, manter
        # legado em vez de afirmar qual limiar histórico foi usado.

    return {
        "motivo": motivo,
        "motivo_encerramento": motivo_banco,
        "excluir_dependente": excluir_dependente,
        "bloqueio_dias": 0,
    }


def aplicar_encerramento_se_necessario(
    id_conversa,
    intencao_encerramento,
    cursor,
):
    if not intencao_encerramento:
        return {
            "atendimento_encerrado": False,
            "finalizou_em": None,
            "bloqueio_dias": 0,
            "motivo": None,
            "motivo_encerramento": None,
        }

    if intencao_encerramento["excluir_dependente"]:
        excluir_dependente_da_conversa(id_conversa, cursor)

    motivo_encerramento = intencao_encerramento["motivo_encerramento"]
    finalizou_em = encerrar_conversa(
        id_conversa,
        motivo_encerramento,
        cursor,
    )
    bloqueio_dias = int(
        intencao_encerramento.get("bloqueio_dias") or 0
    )

    logger.info(
        "atendimento_encerrado | acao=encerrar_conversa "
        "id_conversa=%s motivo=%s motivo_encerramento=%s "
        "dependente_excluido=%s",
        id_conversa,
        intencao_encerramento["motivo"],
        motivo_encerramento,
        intencao_encerramento["excluir_dependente"],
    )
    return {
        "atendimento_encerrado": True,
        "finalizou_em": finalizou_em,
        "bloqueio_dias": bloqueio_dias,
        "motivo": intencao_encerramento["motivo"],
        "motivo_encerramento": motivo_encerramento,
    }
