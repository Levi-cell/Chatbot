"""Processa uma reserva do Funil preservando a fronteira transacional."""

import json
import logging

import psycopg

from core.integrations.funil.cliente import enviar_oportunidade
from core.integrations.funil.oportunidades import montar_payload_oportunidade
from core.repositories.funil.envios import (
    marcar_envio_como_concluido,
    registrar_falha_envio,
)
from core.repositories.funil.integracao import (
    buscar_integracao_funil_por_unidade,
)
from core.repositories.funil.leads import buscar_dados_lead_funil
from workers.worker_funil.config import (
    FUNIL_HTTP_TIMEOUT,
    FUNIL_RETRY_LEAD_SEGUNDOS,
)
from workers.worker_funil.exceptions import BancoFalhouAposEnvioFunil


logger = logging.getLogger("worker.funil.processamento")


def processar_envio_funil(envio, conn, cursor):
    """Envia um lead reservado; erros externos ficam para o próximo ciclo."""
    id_funil_envio = envio["id_funil_envio"]
    id_conversa = envio["id_conversa"]
    sucesso_externo = False

    try:
        dados_lead = buscar_dados_lead_funil(id_conversa, cursor)
        if dados_lead is None:
            raise ValueError("Conversa não está mais elegível ao Funil")

        integracao = buscar_integracao_funil_por_unidade(
            dados_lead["id_unidade"],
            cursor,
        )
        _validar_integracao_ativa(integracao)

        payload = montar_payload_oportunidade(dados_lead)

        # O SELECT não deve manter uma transação aberta durante a chamada HTTP.
        conn.commit()

        resultado = enviar_oportunidade(
            link_api_carrossel=integracao["link_api_carrossel"],
            codigo_canal_venda=integracao["codigo_canal_venda"],
            payload=payload,
            timeout=FUNIL_HTTP_TIMEOUT,
        )
        sucesso_externo = True

        # JANELA RARA CONHECIDA:
        # o Funil já confirmou a oportunidade, mas o banco ainda não marcou
        # lead_no_funil. Se o processo ou o banco cair exatamente aqui, o lease
        # permitirá uma nova tentativa e poderá gerar duplicidade. A futura
        # reconciliação por título [C{id_conversa}] deve fechar essa janela.
        resposta_serializada = json.dumps(
            resultado["resposta"],
            ensure_ascii=False,
        )[:4000]
        marcar_envio_como_concluido(
            id_funil_envio,
            id_conversa,
            resposta_serializada,
            cursor,
        )
        conn.commit()

        logger.info(
            "funil_lead_enviado | acao=confirmar_envio "
            "id_funil_envio=%s id_conversa=%s tentativa=%s status_http=%s",
            id_funil_envio,
            id_conversa,
            envio["attempt_count"],
            resultado["status_http"],
        )
        return True

    except psycopg.Error:
        conn.rollback()
        if sucesso_externo:
            logger.critical(
                "funil_banco_falhou_apos_envio | acao=preservar_processing "
                "id_funil_envio=%s id_conversa=%s",
                id_funil_envio,
                id_conversa,
                exc_info=True,
            )
            raise BancoFalhouAposEnvioFunil(
                "Banco falhou depois de o Funil confirmar a oportunidade"
            )
        raise

    except Exception as exc:
        conn.rollback()

        if sucesso_externo:
            logger.critical(
                "funil_estado_local_falhou_apos_envio | "
                "acao=preservar_processing id_funil_envio=%s id_conversa=%s "
                "erro=%s",
                id_funil_envio,
                id_conversa,
                exc,
            )
            raise BancoFalhouAposEnvioFunil(
                "Estado local falhou depois de o Funil confirmar o lead"
            ) from exc

        try:
            registrado = registrar_falha_envio(
                id_funil_envio,
                exc,
                cursor,
                retry_segundos=FUNIL_RETRY_LEAD_SEGUNDOS,
            )
            if not registrado:
                raise RuntimeError(
                    "Não foi possível devolver o lead reservado para pending"
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

        logger.exception(
            "funil_lead_falhou | acao=reagendar_proximo_ciclo "
            "id_funil_envio=%s id_conversa=%s tentativa=%s erro=%s",
            id_funil_envio,
            id_conversa,
            envio["attempt_count"],
            exc,
        )
        return False


def _validar_integracao_ativa(integracao):
    if integracao is None:
        raise ValueError("Unidade sem configuração do Funil")
    if not integracao["integracao_ativa"]:
        raise ValueError("Integração do Funil está desativada para a unidade")
    if not integracao["widget_ativo"]:
        raise ValueError("Widget do Funil está desativado para a unidade")
