import logging

from core.logging_config import short_value


logger = logging.getLogger("worker.valida_resposta")

TIPOS_MENSAGEM_SUPORTADOS = {"text", "interactive"}

RESULTADO_RESPOSTA_VALIDA = "resposta_valida"
RESULTADO_TIPO_MENSAGEM_NAO_SUPORTADO = "tipo_mensagem_nao_suportado"
RESULTADO_MENSAGEM_FORA_DE_CONTEXTO = "mensagem_fora_de_contexto"


def validar_resposta_cliente(contexto_historico):
    tipo_mensagem = contexto_historico.get("tipo_mensagem_atual")

    if tipo_mensagem in TIPOS_MENSAGEM_SUPORTADOS:
        return {
            "resultado": RESULTADO_RESPOSTA_VALIDA,
            "tipo_tratamento": None,
            "motivo": None,
        }

    mensagem_cliente_atual = contexto_historico["mensagem_cliente_atual"]

    logger.info(
        "resposta_cliente_invalida | motivo=tipo_mensagem_nao_suportado acao=tratar_sem_avancar id_conversa=%s id_mensagem_fila=%s cliente=%s phone_number_id=%s tipo=%s etapa_cliente=%s etapa_resposta=%s",
        contexto_historico["id_conversa"],
        mensagem_cliente_atual["id_mensagem_fila"],
        short_value(mensagem_cliente_atual["cliente_telefone"]),
        short_value(mensagem_cliente_atual["id_phone_unidade"]),
        tipo_mensagem,
        contexto_historico["id_etapa_cliente"],
        contexto_historico["id_etapa_resposta"],
    )

    return {
        "resultado": RESULTADO_TIPO_MENSAGEM_NAO_SUPORTADO,
        "tipo_tratamento": RESULTADO_TIPO_MENSAGEM_NAO_SUPORTADO,
        "motivo": RESULTADO_TIPO_MENSAGEM_NAO_SUPORTADO,
        "tipo_mensagem": tipo_mensagem,
        "avancar_etapa": False,
    }
