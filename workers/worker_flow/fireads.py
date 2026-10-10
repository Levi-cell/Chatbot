"""Consulta inicial assíncrona; a decisão só é persistida sob posse da conversa."""

import logging
import time
from core.integrations.fireads.cliente import ClienteFireAds, PrazoConsultaFireAdsEsgotado
from core.integrations.fireads.contrato import selecionar, destino, ErroFireAds
from core.validacoes.email import validar_email_estrutural
from core.repositories.fireads.consulta import (
    buscar_abertura,
    reservar_consulta,
    concluir_consulta,
    proteger_mensagem_abertura,
    importar_dados_abertura,
    segundos_restantes_consulta,
)
from core.repositories.atendimento.followup import proteger_conversa
from workers.worker_flow.suporte.consultas_fireads import (
    ConsultaFireAdsPendente,
    ConsultasFireAdsEmAndamento,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_nome import (
    validar_nome_cliente,
)

logger = logging.getLogger("worker.fireads")
PRAZO_ABERTURA_SEGUNDOS = 300
consultas_em_andamento = ConsultasFireAdsEmAndamento()


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


def decisao_por_prazo_esgotado(id_conversa):
    logger.warning(
        "fireads_consulta_prazo_esgotado | conversa=%s limite_segundos=%s acao=seguir_organico",
        id_conversa, PRAZO_ABERTURA_SEGUNDOS,
    )
    return decisao_organica("erro", "tempo_limite_300s")


def consultar_formularios(abertura, numero, id_conversa, prazo_final=None):
    """Somente HTTP e interpretação; não recebe cursor nem altera banco/WhatsApp."""
    inicio = time.monotonic()
    if prazo_final is None:
        prazo_final = inicio + PRAZO_ABERTURA_SEGUNDOS
    logger.info(
        "fireads_consulta_iniciada | conversa=%s limite_segundos=%s",
        id_conversa, PRAZO_ABERTURA_SEGUNDOS,
    )
    cliente = None
    try:
        cliente = ClienteFireAds(
            abertura["url"], segundos=max(0, prazo_final - time.monotonic()),
            timeout_leitura=None,
        )
        google = cliente.consultar(abertura["aba_google"])
        meta = cliente.consultar(abertura["aba_meta"])
        if not {"Nome", "Email", "WhatsApp", "Perfil/Faixa"} <= set(google["headers"]):
            raise ErroFireAds("Contrato Google incompleto")
        if not {"full_name", "email", "phone_number", "para_quem"} <= set(
            meta["headers"]
        ):
            raise ErroFireAds("Contrato Meta incompleto")
        decisao = interpretar(
            google["rows"], meta["rows"], numero, abertura["fuso"]
        )
        if time.monotonic() >= prazo_final:
            raise PrazoConsultaFireAdsEsgotado("Interpretação concluída após o prazo")
    except PrazoConsultaFireAdsEsgotado:
        decisao = decisao_por_prazo_esgotado(id_conversa)
    except Exception as exc:
        # Falha externa usa a regra orgânica aprovada. Nada de payload/PII em log.
        logger.warning(
            "fireads_consulta_falhou | conversa=%s tipo=%s", id_conversa, type(exc).__name__
        )
        decisao = decisao_organica("erro", type(exc).__name__)
    finally:
        if cliente:
            cliente.close()
    logger.info(
        "fireads_consulta_concluida | conversa=%s resultado=%s duracao_segundos=%.1f",
        id_conversa, decisao["resultado"], time.monotonic() - inicio,
    )
    return decisao


def preparar_abertura(contexto_banco, mensagem, lock_version, conn, cursor):
    cid = contexto_banco["conversa"]["id_conversa"]
    abertura = buscar_abertura(cid, cursor)
    if abertura["contexto"]:
        return aplicar_contexto(contexto_banco, abertura["contexto"])
    if abertura["etapa"] is not None or not abertura["aplicavel"]:
        return contexto_banco
    proteger_conversa(cid, lock_version, cursor)
    consulta = reservar_consulta(abertura, cid, cursor)
    restante = segundos_restantes_consulta(consulta, cid, PRAZO_ABERTURA_SEGUNDOS, cursor)
    prazo_final = time.monotonic() + restante
    conn.commit()
    # Mudanças de configuração ou uma nova conversa nunca reutilizam outra leitura.
    chave = (
        cid, abertura["id_integracao"], abertura["url"], abertura["aba_google"],
        abertura["aba_meta"], abertura["fuso"], mensagem["cliente_telefone"],
    )
    futuro = None
    if time.monotonic() >= prazo_final:
        decisao = decisao_por_prazo_esgotado(cid)
    else:
        futuro = consultas_em_andamento.obter(
            chave, consultar_formularios, abertura, mensagem["cliente_telefone"], cid,
            prazo_final,
        )
        if not futuro.done():
            raise ConsultaFireAdsPendente("consultando")
        decisao = futuro.result()
        if time.monotonic() >= prazo_final:
            decisao = decisao_por_prazo_esgotado(cid)
    # A espera devolve a mensagem à fila. Cada retomada adquire reservas novas,
    # portanto uma consulta longa não depende dos locks de 110/120 segundos.
    proteger_conversa(cid, lock_version, cursor)
    proteger_mensagem_abertura(mensagem, cursor)
    if decisao["resultado"] == "importado":
        if not importar_dados_abertura(abertura["id_cliente"], cid, decisao, cursor):
            decisao = decisao_organica("incompleto", "conflito_email")
    decisao = concluir_consulta(abertura, cid, consulta, decisao, cursor)
    conn.commit()
    if futuro is not None:
        consultas_em_andamento.confirmar(chave, futuro)
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
