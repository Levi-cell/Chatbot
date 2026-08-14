import logging
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from core.logging_config import short_value


logger = logging.getLogger("webhook.alerta_flood_memoria")


def registrar_alerta_flood_memoria(
    wa_id_cliente,
    phone_id_unidade,
    origem,
    regra,
    total,
    meta_ok,
    motivo,
    id_hash_msg=None,
    erro_meta=None,
):
    try:
        diretorio = _diretorio_alertas()
        diretorio.mkdir(parents=True, exist_ok=True)

        agora = timezone.localtime()
        arquivo = diretorio / _nome_arquivo_diario(agora)

        with arquivo.open("a", encoding="utf-8") as arquivo_alerta:
            arquivo_alerta.write(
                _montar_conteudo(
                    agora=agora,
                    wa_id_cliente=wa_id_cliente,
                    phone_id_unidade=phone_id_unidade,
                    origem=origem,
                    regra=regra,
                    total=total,
                    meta_ok=meta_ok,
                    motivo=motivo,
                    id_hash_msg=id_hash_msg,
                    erro_meta=erro_meta,
                )
            )

        logger.warning(
            "alerta_flood_memoria_registrado | acao=adicionar_evento_txt wa_id_cliente=%s phone_id_unidade=%s meta_ok=%s arquivo=%s",
            short_value(wa_id_cliente),
            short_value(phone_id_unidade),
            meta_ok,
            arquivo,
        )
        return str(arquivo)

    except Exception as exc:
        logger.exception(
            "alerta_flood_memoria_falhou | acao=seguir_webhook wa_id_cliente=%s phone_id_unidade=%s erro=%s",
            short_value(wa_id_cliente),
            short_value(phone_id_unidade),
            exc,
        )
        return None


def _diretorio_alertas():
    return Path(settings.BASE_DIR).parent / "logs" / "reconciliacao_pendente"


def _nome_arquivo_diario(agora):
    return f"flood_memoria_{agora.strftime('%Y%m%d')}.txt"


def _montar_conteudo(
    agora,
    wa_id_cliente,
    phone_id_unidade,
    origem,
    regra,
    total,
    meta_ok,
    motivo,
    id_hash_msg,
    erro_meta,
):
    if meta_ok is True:
        acao_recomendada = (
            "executar python -m utilitarios.monitoring.blocked_users "
            "blocked-users quando o banco voltar"
        )
    elif meta_ok is False:
        acao_recomendada = (
            "acompanhar novas tentativas; a denylist local deve permanecer ativa"
        )
    else:
        acao_recomendada = (
            "restabelecer o banco; o webhook retornou 503 para reentrega"
        )

    linhas = [
        "================================================================",
        "EVENTO CRITICO: FLOOD DETECTADO PELA MEMORIA LOCAL",
        "================================================================",
        f"data_hora: {agora.isoformat()}",
        f"motivo: {motivo}",
        f"origem_rate_limit: {origem}",
        f"regra: {regra}",
        f"total_mensagens_na_janela: {total}",
        f"meta_ok: {meta_ok}",
        f"wa_id_cliente: {wa_id_cliente}",
        f"phone_id_unidade: {phone_id_unidade}",
        f"id_hash_msg: {id_hash_msg or '-'}",
        f"erro_meta: {erro_meta or '-'}",
        "",
        f"acao_recomendada: {acao_recomendada}",
        "",
        "contexto:",
        "- Redis falhou antes de detectar o flood.",
        "- Banco falhou como fallback do rate limit.",
        "- Memoria local detectou o flood e o webhook ignorou a mensagem.",
        "- A intencao local precisa ser persistida antes da tentativa na Meta.",
        "- Se o banco permaneceu indisponivel, o webhook pediu reentrega.",
        "",
    ]
    return "\n".join(linhas) + "\n"
