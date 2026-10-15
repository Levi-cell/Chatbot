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
    bloquear_contato,
    liberar_contato,
)
from core.integrations.fireads.destino_dashboard import (
    destinatario_perfil,
    linhas_com_bloco,
    numero_linha,
    selecionar_destino,
    selecionar_destino_atual,
)

logger = logging.getLogger("worker.funil.fireads")


def preparar_escrita(rows, snapshot, bloco):
    acrescentar_observacoes(None, bloco)  # Mesmo limite no append e no update.
    encontrados = localizar(
        rows, snapshot["telefone"], "WhatsApp", incluir_equivalentes=True
    )
    if linhas_com_bloco(encontrados, bloco):
        return None
    if snapshot.get("versao") == 2 and (encontrados or snapshot.get("referencia") is not None):
        row = selecionar_destino_atual(encontrados, snapshot)
        if "Observação" not in row:
            raise ErroFireAds("Observação ausente na leitura do registro; não sobrescrever")
        observacoes, mudou = acrescentar_observacoes(row.get("Observação"), bloco)
        return {"row": numero_linha(row), "observacoes": observacoes} if mudou else None
    if encontrados:
        dependente = snapshot.get("status_dependente")
        if type(dependente) is not bool:
            # Envios pendentes anteriores à correção já guardam o perfil textual.
            dependente = destinatario_perfil(snapshot.get("perfil"))
        row = selecionar_destino(encontrados, snapshot["origem"], dependente)
        if "Observação" not in row:
            raise ErroFireAds(
                "Observação ausente na leitura do registro; não sobrescrever"
            )
        linha = numero_linha(row)
        # O telefone identifica o contato; e-mail e demais campos ficam intactos.
        observacoes, mudou = acrescentar_observacoes(row.get("Observação"), bloco)
        return {"row": linha, "observacoes": observacoes} if mudou else None
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
        bloqueado = bloquear_contato(chave, cursor)
        if not bloqueado:
            raise ErroFireAds("Outro envio deste contato está em andamento")
        conferir_posse(envio, cursor)
        conn.commit()
        cliente = ClienteFireAds(snapshot["url"], segundos=40)
        dados = cliente.consultar(snapshot["aba"])
        if not {"Nome", "Email", "WhatsApp", "Observação"} <= set(dados["headers"]):
            raise ErroFireAds("Cabeçalhos de destino incompletos")
        if snapshot.get("versao") == 2:
            bloco = snapshot["observacoes"]
        elif "versao" not in snapshot:
            bloco = bloco_observacoes(
                envio["integracao"], envio["conversa"], snapshot["observacoes"]
            )
        else:
            raise ErroFireAds("Versão de envio desconhecida")
        operacao = preparar_escrita(dados["rows"], snapshot, bloco)
        conferir_posse(envio, cursor)
        conn.commit()
        if operacao is None:
            encontrados = localizar(
                dados["rows"], snapshot["telefone"], "WhatsApp", incluir_equivalentes=True
            )
            recibo = {
                "success": True,
                "reconciliado": True,
                "aba": snapshot["aba"],
                "linhas_reconciliadas": linhas_com_bloco(encontrados, bloco),
            }
        else:
            recibo = cliente.enviar(snapshot["aba"], **operacao)
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
            liberar_contato(chave, cursor)
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
