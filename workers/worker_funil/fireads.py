"""Entrega independente, depois do Funil. Reconsulta antes de qualquer escrita."""

import hashlib
import logging
import psycopg
from core.integrations.fireads.cliente import ClienteFireAds
from core.integrations.fireads.contrato import (
    CANAIS,
    ErroFireAds,
    telefone,
    identidade_telefone,
    localizar,
    bloco_observacoes,
    acrescentar_observacoes,
)
from core.repositories.fireads.envios import (
    reservar,
    conferir_posse,
    concluir,
    reagendar,
)

logger = logging.getLogger("worker.funil.fireads")


def preparar_escrita(rows, snapshot, bloco):
    acrescentar_observacoes(None, bloco)  # Mesmo limite no append e no update.
    encontrados = localizar(
        rows, snapshot["telefone"], "WhatsApp", incluir_equivalentes=True
    )
    if len(encontrados) > 1:
        # Nunca escolher arbitrariamente uma pessoa/linha duplicada preexistente.
        raise ErroFireAds("Mais de uma linha de destino para este telefone")
    if encontrados:
        row = encontrados[0]
        if "Observação" not in row:
            raise ErroFireAds(
                "Observação ausente na leitura do registro; não sobrescrever"
            )
        email_existente = str(row.get("Email") or "").strip().casefold()
        email_novo = str(snapshot.get("email") or "").strip().casefold()
        if email_existente and email_novo and email_existente != email_novo:
            raise ErroFireAds(
                "Mesmo telefone com emails diferentes; conferir identidade"
            )
        numero_linha = row.get("_row")
        if type(numero_linha) is not int or numero_linha < 2:
            raise ErroFireAds("Linha de destino inválida")
        observacoes, mudou = acrescentar_observacoes(row.get("Observação"), bloco)
        return {"row": numero_linha, "observacoes": observacoes} if mudou else None
    # Um e-mail já presente com outro telefone não é identidade suficiente para
    # alterar outra pessoa nem para criar silenciosamente um possível duplicado.
    email = str(snapshot.get("email") or "").strip().casefold()
    if email and any(
        str(r.get("Email") or "").strip().casefold() == email for r in rows
    ):
        raise ErroFireAds("Email já presente em outro telefone; conferir identidade")
    return {
        "dados": {
            "Nome": snapshot["nome"],
            "Email": snapshot["email"],
            "WhatsApp": telefone(snapshot["telefone"]),
            "Perfil/Faixa": snapshot["perfil"],
            "Canal": CANAIS[snapshot["origem"]][0],
            "Observação": bloco,
        }
    }


def processar(envio, conn, cursor):
    snapshot = envio["snapshot"]
    # Lock de sessão (não de transação): serializa nossos envios ao mesmo contato,
    # sem manter transação aberta durante HTTP. Outros sistemas não usam este lock.
    identidade = f"fireads:{envio['integracao']}:{identidade_telefone(snapshot['telefone'])}"
    chave = int.from_bytes(
        hashlib.sha256(identidade.encode()).digest()[:8], "big", signed=True
    )
    bloqueado = False
    cliente = None
    try:
        cursor.execute("SELECT pg_try_advisory_lock(%s)", (chave,))
        bloqueado = cursor.fetchone()[0]
        if not bloqueado:
            raise ErroFireAds("Outro envio deste contato está em andamento")
        conferir_posse(envio, cursor)
        conn.commit()
        cliente = ClienteFireAds(snapshot["url"], segundos=40)
        dados = cliente.consultar(snapshot["aba"])
        if not {"Nome", "Email", "WhatsApp", "Observação"} <= set(dados["headers"]):
            raise ErroFireAds("Cabeçalhos de destino incompletos")
        bloco = bloco_observacoes(
            envio["integracao"], envio["conversa"], snapshot["observacoes"]
        )
        operacao = preparar_escrita(dados["rows"], snapshot, bloco)
        conferir_posse(envio, cursor)
        conn.commit()
        recibo = (
            {"success": True, "reconciliado": True}
            if operacao is None
            else cliente.enviar(snapshot["aba"], **operacao)
        )
        concluir(envio, recibo, cursor)
        conn.commit()
        logger.info(
            "dash_enviado | conversa=%s tentativa=%s",
            envio["conversa"],
            envio["tentativa"],
        )
        return True
    except psycopg.Error:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        # Armazenar apenas erros de contrato controlados, sem URLs ou corpos externos.
        seguro = (
            exc if isinstance(exc, ErroFireAds) else ErroFireAds(type(exc).__name__)
        )
        reagendar(envio, seguro, cursor)
        conn.commit()
        logger.warning(
            "dash_pendente | conversa=%s tipo=%s", envio["conversa"], type(exc).__name__
        )
        return False
    finally:
        if cliente:
            cliente.close()
        if bloqueado and not conn.closed:
            cursor.execute("SELECT pg_advisory_unlock(%s)", (chave,))
            conn.commit()


def processar_lote(conn, cursor, limite=100):
    resumo = {"processados": 0, "enviados": 0, "falhas": 0}
    for _ in range(limite):
        envio = reservar(cursor)
        conn.commit()
        if envio is None:
            break
        resumo["processados"] += 1
        resumo["enviados" if processar(envio, conn, cursor) else "falhas"] += 1
    return resumo
