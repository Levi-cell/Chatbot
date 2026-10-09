"""Consulta inicial: executada sob posse da conversa, fora de transação HTTP."""

import logging
import psycopg
from core.integrations.fireads.cliente import ClienteFireAds
from core.integrations.fireads.contrato import selecionar, destino, ErroFireAds
from core.validacoes.email import validar_email_estrutural
from core.repositories.fireads.consulta import (
    buscar_abertura,
    reservar_consulta,
    concluir_consulta,
)
from core.repositories.atendimento.followup import (
    proteger_conversa,
    LockConversaPerdido,
)
from core.repositories.atendimento.dependentes import inserir_dependente_para_conversa
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_nome import (
    validar_nome_cliente,
)

logger = logging.getLogger("worker.fireads")


def classificar_tratamento_abertura(contexto):
    """A decisão fica no fluxo; messages apenas compõe o texto autorizado."""
    from workers.worker_flow.response_flow.etapas.validadores_universais.validador_midia import (
        validar_midia,
    )
    from workers.worker_flow.response_flow.etapas.validadores_universais.validador_financeiro import (
        validar_pergunta_financeira,
    )
    from workers.worker_flow.response_flow.etapas.validadores_universais.validador_reforco_escolar import (
        validar_duvida_reforco_escolar,
    )

    texto = contexto.get("texto_cliente_atual") or ""
    if validar_midia(contexto.get("tipo_mensagem_atual")):
        return "tipo_mensagem_nao_suportado"
    if validar_duvida_reforco_escolar(texto):
        return "duvida_reforco_escolar"
    if validar_pergunta_financeira(texto):
        return "pergunta_financeira"
    return None


def decisao_organica(resultado, motivo=None):
    return {
        "resultado": resultado,
        "origem": "organico",
        "motivo": motivo,
        "dados_titular": {},
    }


def interpretar(google, meta, numero, fuso):
    try:
        escolhido = selecionar(google, meta, numero, fuso)
    except ErroFireAds:
        return decisao_organica("ambiguidade", "data_ou_origem_ambigua")
    if escolhido is None:
        return decisao_organica("ausente")
    origem, row, data = escolhido
    nome = row.get("Nome") if origem == "google" else row.get("full_name")
    email = row.get("Email") if origem == "google" else row.get("email")
    alvo = row.get("Perfil/Faixa") if origem == "google" else row.get("para_quem")
    nome = validar_nome_cliente(nome)
    email = validar_email_estrutural(email)
    dependente = destino(alvo)
    if not nome.valido or not email.valido or dependente is None:
        return decisao_organica("incompleto", "coleta_invalida")
    return {
        "resultado": "importado",
        "origem": origem,
        "status_dependente": dependente,
        "id_registro_origem": str(row.get("id") or ""),
        "data_formulario": data.isoformat() if data else None,
        "dados_titular": {
            "nome": nome.primeiro_nome,
            "email": email.email,
            "resultado_email": "email_valido",
        },
    }


def preparar_abertura(contexto_banco, mensagem, lock_version, conn, cursor):
    cid = contexto_banco["conversa"]["id_conversa"]
    abertura = buscar_abertura(cid, cursor)
    if abertura["contexto"]:
        return aplicar_contexto(contexto_banco, abertura["contexto"])
    if abertura["etapa"] is not None or not abertura["aplicavel"]:
        return contexto_banco
    proteger_conversa(cid, lock_version, cursor)
    consulta = reservar_consulta(abertura, cid, cursor)
    conn.commit()
    cliente = None
    try:
        cliente = ClienteFireAds(abertura["url"], segundos=25)
        google = cliente.consultar(abertura["aba_google"])
        meta = cliente.consultar(abertura["aba_meta"])
        if not {"Nome", "Email", "WhatsApp", "Perfil/Faixa"} <= set(google["headers"]):
            raise ErroFireAds("Contrato Google incompleto")
        if not {"full_name", "email", "phone_number", "para_quem"} <= set(
            meta["headers"]
        ):
            raise ErroFireAds("Contrato Meta incompleto")
        decisao = interpretar(
            google["rows"], meta["rows"], mensagem["cliente_telefone"], abertura["fuso"]
        )
    except Exception as exc:
        # Falha externa usa a regra orgânica aprovada. Nada de payload/PII em log.
        logger.warning(
            "fireads_consulta_falhou | conversa=%s tipo=%s", cid, type(exc).__name__
        )
        decisao = decisao_organica("erro", type(exc).__name__)
    finally:
        if cliente:
            cliente.close()
    proteger_conversa(cid, lock_version, cursor)
    cursor.execute(
        """SELECT id_mensagem FROM chatbot.fila_mensagens
        WHERE id_mensagem=%s AND status='processing' AND retry_count=%s
          AND processing_started_at>clock_timestamp()-INTERVAL '120 seconds' FOR UPDATE""",
        (mensagem["id_mensagem"], mensagem["retry_count"]),
    )
    if cursor.fetchone() is None:
        raise LockConversaPerdido("Mensagem perdeu a reserva durante consulta FireAds")
    if decisao["resultado"] == "importado":
        cursor.execute("SAVEPOINT fireads_importacao")
        try:
            dados = decisao["dados_titular"]
            cursor.execute(
                "UPDATE chatbot.cliente SET nome=%s,email=%s WHERE id_cliente=%s",
                (dados["nome"], dados["email"], abertura["id_cliente"]),
            )
            cursor.execute(
                "UPDATE chatbot.conversa SET status_dependente=%s WHERE id_conversa=%s",
                (decisao["status_dependente"], cid),
            )
            if decisao["status_dependente"]:
                inserir_dependente_para_conversa(cid, cursor)
        except psycopg.errors.UniqueViolation:
            cursor.execute("ROLLBACK TO SAVEPOINT fireads_importacao")
            decisao = decisao_organica("incompleto", "conflito_email")
        finally:
            cursor.execute("RELEASE SAVEPOINT fireads_importacao")
    decisao = concluir_consulta(abertura, cid, consulta, decisao, cursor)
    conn.commit()
    return aplicar_contexto(contexto_banco, decisao)


def aplicar_contexto(contexto_banco, decisao):
    novo = dict(contexto_banco, contexto_fireads=decisao)
    if (
        decisao.get("resultado") == "importado"
        and novo["conversa"].get("id_etapa_atual") is None
    ):
        novo["conversa"] = dict(
            novo["conversa"], status_dependente=decisao["status_dependente"]
        )
    return novo


def email_importado(contexto):
    estado = contexto.get("contexto_fireads") or {}
    return (
        estado.get("concluida") is True
        and estado.get("resultado") == "importado"
        and estado.get("id_conversa") == contexto.get("id_conversa")
        and estado.get("dados_titular", {}).get("resultado_email") == "email_valido"
        and validar_email_estrutural(
            estado.get("dados_titular", {}).get("email")
        ).valido
    )
